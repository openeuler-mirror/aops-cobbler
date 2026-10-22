"""安装轮次与收尾：事务保存结果，串行处理同一主机的外部清理。"""

from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import uuid4

from cobbled.database.table import InstallationCleanup, RawHost
from cobbled.log.log import LOGGER


class InstallationConflict(ValueError):
    """当前主机或安装轮次不允许执行该操作。"""


class InstallationLifecycle:
    def __init__(self, session, clock=None):
        self.session = session
        # MySQL DATETIME 使用秒精度，避免提交时四舍五入使新任务暂时落在未来。
        self.clock = clock or (lambda: datetime.now().replace(microsecond=0))

    def _host(self, host_id):
        # 所有写入按主机、清理记录的顺序加锁，避免完成通知和清理交叉死锁。
        return (self.session.query(RawHost).filter_by(host_id=host_id)
                .populate_existing().with_for_update().one_or_none())

    def _cleanup(self, host_id):
        return (self.session.query(InstallationCleanup).filter_by(host_id=host_id)
                .populate_existing().with_for_update().one_or_none())

    def begin(self, host_id):
        """在产生该主机的远端副作用前，持久化并独占一个安装轮次。"""
        try:
            host = self._host(host_id)
            if host is None:
                raise InstallationConflict("主机不存在")
            task = self._cleanup(host_id)
            if task is not None and task.state != "done":
                raise InstallationConflict("上次安装配置尚未清理完成")
            if host.status == 3:
                raise InstallationConflict("主机正在安装")
            round_id = str(uuid4())
            host.installation_round = round_id
            host.installation_started_at = self.clock()
            host.installation_system = f"{host.host_name}-{host.host_id}-{round_id}"
            host.status = 3
            if task is not None:
                self.session.delete(task)
            system_name = host.installation_system
            self.session.commit()
            return round_id, system_name
        except Exception:
            self.session.rollback()
            raise

    @contextmanager
    def active(self, host_id, round_id):
        """远端准备/重启期间持有数据库锁，收尾不能同时删除该轮配置。

        不使用会过期的领取租约：旧执行者仍在操作远端时，不能让新执行者接管。
        进程退出会释放连接及锁，下一次调度即可恢复。
        """
        try:
            host = self._host(host_id)
            if host is None or host.installation_round != round_id or host.status != 3:
                raise InstallationConflict("安装轮次已结束或已被替换")
            yield host
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def prepare_start(self, host_id, round_id, host_ip):
        # 必须在重启前提交；随后 active 再次检查状态并与收尾互斥。
        with self.active(host_id, round_id) as host:
            host.host_ip = host_ip
            host.installation_started_at = self.clock()

    def finish(self, host_id, round_id, *, succeeded, host_ip=None, expected_started_at=None):
        """结果与清理任务同事务提交；失败不能覆盖已确认的安装完成。"""
        try:
            host = self._host(host_id)
            if host is None or not round_id or host.installation_round != round_id:
                raise InstallationConflict("安装轮次缺失或不匹配")
            if expected_started_at is not None and host.installation_started_at != expected_started_at:
                raise InstallationConflict("安装启动时间已更新")
            task = self._cleanup(host_id)
            if succeeded:
                host.status = 1
                if host_ip:
                    host.host_ip = host_ip
            elif host.status == 3:
                host.status = 4
            if task is None:
                self.session.add(InstallationCleanup(
                    host_id=host_id, round_id=round_id,
                    system_name=host.installation_system, state="pending",
                    failures=0, next_attempt_at=self.clock()))
            elif task.round_id != round_id:
                raise InstallationConflict("清理任务与安装轮次不匹配")
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def notify(self, bmc_ip, round_id, host_ip):
        host = self.session.query(RawHost).filter_by(bmc_ip=bmc_ip).one_or_none()
        if host is None:
            raise InstallationConflict("主机不存在")
        self.finish(host.host_id, round_id, succeeded=True, host_ip=host_ip)

    def clean_due(self, connect_cobbler, limit=100):
        now = self.clock()
        ids = [row[0] for row in (
            self.session.query(InstallationCleanup.host_id)
            .filter(InstallationCleanup.state == "pending",
                    InstallationCleanup.next_attempt_at <= now)
            .order_by(InstallationCleanup.next_attempt_at, InstallationCleanup.host_id)
            .limit(limit).all())]
        self.session.rollback()  # 结束候选快照；锁定后重新检查是否仍到期。
        for host_id in ids:
            self._clean_one(host_id, connect_cobbler)

    def _clean_one(self, host_id, connect_cobbler):
        try:
            self._host(host_id)
            task = self._cleanup(host_id)
            if task is None or task.state != "pending" or task.next_attempt_at > self.clock():
                self.session.rollback()
                return
            stage = "连接 Cobbler"
            try:
                remote, token = connect_cobbler()
                stage = "查询 Cobbler 配置"
                system = remote.get_system(task.system_name)
                # 删除已完成、DHCP 同步尚未完成的任务，重试时仍需同步。
                if system and system != "~":
                    stage = "删除 Cobbler 配置"
                    if not remote.remove_system(task.system_name, token):
                        raise RuntimeError("Cobbler 删除配置失败")
                stage = "同步 DHCP"
                if not remote.sync_dhcp(token):
                    raise RuntimeError("Cobbler 同步 DHCP 失败")
            except Exception as error:
                task.failures += 1
                delay = min(300 * (2 ** min(task.failures - 1, 3)), 1800)
                task.next_attempt_at = self.clock() + timedelta(seconds=delay)
                # 外部异常可能包含凭据；对外只保留固定摘要及异常类型。
                task.last_error = f"{stage}失败（{type(error).__name__}），等待重试"
                LOGGER.warning("Installation cleanup failed for host %s, round %s (%s)",
                               host_id, task.round_id, type(error).__name__)
            else:
                task.state = "done"
                task.next_attempt_at = None
                task.last_error = None
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

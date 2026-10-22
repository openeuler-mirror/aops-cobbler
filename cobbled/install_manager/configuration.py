"""安装配置：集中 Cobbler 协议约定，不管理轮次、事务或重试。"""

from contextlib import contextmanager

from cobbled.conf.constant import InstallCons


class InstallationConfigurationError(RuntimeError):
    """保留原始错误文本供启动流程使用，同时提供安全的收尾摘要。"""

    def __init__(self, stage, error):
        super().__init__(str(error))
        self.stage = stage
        self.error_type = type(error).__name__

    @property
    def cleanup_summary(self):
        return f"{self.stage}失败（{self.error_type}），等待重试"


@contextmanager
def _operation(stage):
    try:
        yield
    except Exception as error:
        raise InstallationConfigurationError(stage, error) from error


class CobblerInstallationConfiguration:
    """一批安装使用的远端配置；通过 for_image 读取镜像后才可准备。

    connect_cobbler 是返回远端对象与 token 的适配器工厂。
    本模块不修正本地 PXE，也不决定持锁、提交和重启的时机。
    """

    def __init__(self, remote, token, distro_name, profile):
        self._remote = remote
        self._token = token
        self._distro_name = distro_name
        self._profile = profile

    @classmethod
    def for_image(cls, connect_cobbler, distro_name):
        """只读检查镜像并加载配置；镜像不存在时返回 None。"""
        with _operation("连接 Cobbler"):
            remote, token = connect_cobbler()
        with _operation("查询安装镜像"):
            target = remote.get_distro(distro_name)
            if not target or target == '~':
                return None
            profile = remote.get_profile(distro_name)
        return cls(remote, token, distro_name, profile)

    def prepare_shared(self, ks_content):
        """写入共享模板、切换启动菜单并同步；仅在有可安装主机后执行。"""
        with _operation("写入安装模板"):
            if not self._remote.write_autoinstall_template(
                    self._profile["autoinstall"], ks_content, self._token):
                raise RuntimeError(InstallCons.WRITE_AUTOINSTALL_KS_TIPS)
        with _operation("设置 PXE 菜单"):
            for profile in self._remote.get_profiles():
                handle = "profile::" + profile["name"]
                enabled = '1' if profile["name"] == self._distro_name else '0'
                if not self._remote.modify_profile(handle, 'enable_menu', enabled, self._token):
                    raise RuntimeError(InstallCons.SET_ENABLE_PXE_TIPS)
                # 保留原行为：保存抛异常时失败，但不判断返回值。
                self._remote.save_profile(handle, self._token)
        with _operation("同步 Cobbler"):
            if not self._remote.sync(self._token):
                raise RuntimeError(InstallCons.COBBLER_SYNC_TIPS)

    def prepare_host(self, *, system_name, host_name, round_id, host_mac, host_ip):
        """准备单轮配置并同步 DHCP；调用方负责持有该主机的轮次锁。"""
        with _operation("创建 Cobbler 配置"):
            system_id = self._remote.new_system(self._token)
            settings = (
                ("name", system_name),
                ("hostname", host_name),
                ("profile", self._profile.get("name")),
                ("kernel_options", {"aops_installation_round": round_id}),
                ("modify_interface", {
                    "macaddress-net0": host_mac,
                    "ipaddress-net0": host_ip,
                    "dhcptag-net0": "default",
                }),
            )
            if not system_id or not all(
                    self._remote.modify_system(system_id, field, value, self._token)
                    for field, value in settings):
                raise RuntimeError(InstallCons.COBBLER_SYSTEM_TIPS)
        with _operation("保存 Cobbler 配置"):
            if not self._remote.save_system(system_id, self._token):
                raise RuntimeError(InstallCons.COBBLER_SYSTEM_TIPS)
        with _operation("同步 DHCP"):
            if not self._remote.sync_dhcp(self._token):
                raise RuntimeError(InstallCons.COBBLER_SYSTEM_TIPS)

    @staticmethod
    def clean_system(connect_cobbler, system_name):
        """删除单轮配置后确认 DHCP 同步；配置已不存在也必须同步。"""
        with _operation("连接 Cobbler"):
            remote, token = connect_cobbler()
        with _operation("查询 Cobbler 配置"):
            system = remote.get_system(system_name)
        if system and system != '~':
            with _operation("删除 Cobbler 配置"):
                if not remote.remove_system(system_name, token):
                    raise RuntimeError("Cobbler 删除配置失败")
        with _operation("同步 DHCP"):
            if not remote.sync_dhcp(token):
                raise RuntimeError("Cobbler 同步 DHCP 失败")

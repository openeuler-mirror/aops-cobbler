"""可选 MySQL 验证：创建独立随机数据库，验证迁移和真实行锁竞争。"""

import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from cobbled.database.table import RawHost, InstallationCleanup
from cobbled.install_manager.lifecycle import InstallationLifecycle, InstallationConflict


@unittest.skipUnless(os.environ.get('AOPS_TEST_MYSQL_URL'), '需要独立 MySQL 测试实例')
class TestLifecycleMySQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = 'aops_cleanup_test_' + uuid4().hex
        url = make_url(os.environ['AOPS_TEST_MYSQL_URL'])
        cls.admin = create_engine(url.set(database=None), isolation_level='AUTOCOMMIT')
        cls.addClassCleanup(cls.admin.dispose)
        with cls.admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE `{cls.database}` CHARACTER SET utf8mb4')
        def drop_database():
            with cls.admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE `{cls.database}`')
        cls.addClassCleanup(drop_database)
        cls.engine = create_engine(url.set(database=cls.database))
        cls.addClassCleanup(cls.engine.dispose)
        cls.sessions = sessionmaker(bind=cls.engine)
        root = Path(__file__).parents[3]
        # 以旧表结构启动，再执行仓库提供的真实升级脚本。
        schema = (root / 'database/aops-cobbler.sql').read_text()
        table = 'CREATE TABLE IF NOT EXISTS `raw_host`' + schema.split(
            'CREATE TABLE IF NOT EXISTS `raw_host`', 1)[1].split(';', 1)[0]
        table = '\n'.join(line for line in table.splitlines() if '`installation_' not in line)
        migration = (root / 'database/migrations/001-installation-cleanup.sql').read_text()
        with cls.engine.begin() as connection:
            connection.exec_driver_sql(table)
            migration = '\n'.join(line for line in migration.splitlines()
                                  if not line.startswith('--') and not line.startswith('USE '))
            for statement in migration.split(';'):
                if statement.strip():
                    connection.exec_driver_sql(statement)

    def setUp(self):
        with self.sessions() as session:
            session.query(InstallationCleanup).delete()
            session.query(RawHost).delete()
            session.add(RawHost(host_id='test', host_name='test', bmc_ip='192.0.2.1',
                                bmc_user_name='user', bmc_passwd='secret',
                                host_mac='aa:bb:cc:dd:ee:ff', status=0))
            session.commit()

    def test_two_connections_cannot_start_same_host(self):
        barrier = threading.Barrier(2)
        def start():
            with self.sessions() as session:
                barrier.wait(timeout=5)
                try:
                    InstallationLifecycle(session).begin('test')
                    return 'started'
                except InstallationConflict:
                    return 'blocked'
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: start(), range(2)))
        self.assertCountEqual(results, ['started', 'blocked'])

    def test_host_edit_uses_current_cleanup_state_after_older_snapshot(self):
        from cobbled.database.host import HostProxy
        with self.sessions() as writer:
            round_id, _ = InstallationLifecycle(writer).begin('test')
        with self.sessions() as stale:
            stale.query(RawHost).all()  # 建立 REPEATABLE READ 旧快照。
            with self.sessions() as writer:
                InstallationLifecycle(writer).finish('test', round_id, succeeded=True)
            proxy = HostProxy.__new__(HostProxy)
            proxy.session = stale
            try:
                self.assertFalse(proxy.update_host_info({'host_id': 'test', 'host_name': 'renamed'}))
            finally:
                proxy.session = None

    def test_cleanup_holds_lock_until_remote_operation_and_commit_complete(self):
        with self.sessions() as session:
            lifecycle = InstallationLifecycle(session)
            round_id, old_name = lifecycle.begin('test')
            lifecycle.finish('test', round_id, succeeded=True)
        entered, release, waiting = threading.Event(), threading.Event(), threading.Event()
        deleted = []
        class Remote:
            def get_system(self, name):
                return {'name': name}
            def remove_system(self, name, token):
                entered.set()
                if not release.wait(timeout=10):
                    raise TimeoutError()
                deleted.append(name)
                return True
            def sync_dhcp(self, token):
                return True
        remote = Remote()
        def clean():
            with self.sessions() as session:
                InstallationLifecycle(session)._clean_one('test', lambda: (remote, 'token'))
        def start():
            with self.sessions() as session:
                waiting.set()
                return InstallationLifecycle(session).begin('test')
        with ThreadPoolExecutor(max_workers=3) as executor:
            first = executor.submit(clean)
            if not entered.wait(timeout=5):
                first.result(timeout=1)
                self.fail("到期任务未进入远端清理")
            second = executor.submit(clean)
            restart = executor.submit(start)
            try:
                self.assertTrue(waiting.wait(timeout=5))
                self.assertFalse(restart.done())
            finally:
                release.set()
            first.result(timeout=10)
            second.result(timeout=10)
            new_round, new_name = restart.result(timeout=10)
        self.assertEqual(deleted, [old_name])
        self.assertNotEqual(new_round, round_id)
        self.assertNotEqual(old_name, new_name)


from cobbled.tests.install_manager import test_lifecycle as behavior


@unittest.skipUnless(os.environ.get('AOPS_TEST_MYSQL_URL'), '需要独立 MySQL 测试实例')
class TestLifecycleMySQLBehavior(behavior.TestInstallationLifecycle):
    """同一组行为契约同时在 SQLite 和迁移后的 MySQL 上执行。"""

    @classmethod
    def setUpClass(cls):
        TestLifecycleMySQL.setUpClass.__func__(cls)

    def make_engine(self):
        return type(self).engine

    def setUp(self):
        with type(self).sessions() as session:
            session.query(InstallationCleanup).delete()
            session.query(RawHost).delete()
            session.commit()
        super().setUp()

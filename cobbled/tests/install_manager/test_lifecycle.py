"""从真实事务及业务入口验证安装收尾，不把 SQLite 当作 MySQL 行锁验证。"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from flask import Flask
from flask_restful import Api
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from cobbled.database.host import HostProxy
from cobbled.database.table import Base, RawHost, InstallationCleanup
from cobbled.install_manager.lifecycle import InstallationConflict, InstallationLifecycle
from cobbled.install_manager import view


class TestInstallationLifecycle(unittest.TestCase):
    def make_engine(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return create_engine('sqlite:///' + str(Path(directory.name) / 'test.db'))

    def setUp(self):
        self.engine = self.make_engine()
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.session = self.sessions()
        self.addCleanup(self.session.close)
        self.now = datetime(2026, 10, 20, 12)
        self.lifecycle = InstallationLifecycle(self.session, clock=lambda: self.now)
        self.session.add(RawHost(
            host_id='host-1', host_name='test', bmc_ip='192.0.2.1',
            bmc_user_name='user', bmc_passwd='secret', host_mac='aa:bb:cc:dd:ee:ff',
            status=0, update_time=self.now))
        self.session.commit()
        self.round_id, self.system_name = self.lifecycle.begin('host-1')
        self.remote = Mock()
        self.remote.get_system.return_value = {'name': self.system_name}
        self.remote.remove_system.return_value = True
        self.remote.sync_dhcp.return_value = True
        self.connect = Mock(return_value=(self.remote, 'token'))

    def task(self):
        return self.session.query(InstallationCleanup).one()

    def host(self):
        return self.session.get(RawHost, 'host-1')

    def finish(self, succeeded=True):
        self.lifecycle.finish('host-1', self.round_id, succeeded=succeeded)

    def test_completion_is_durable_and_does_not_call_remote(self):
        self.lifecycle.notify('192.0.2.1', self.round_id, '192.0.2.100')
        with self.sessions() as observer:
            self.assertEqual(observer.get(RawHost, 'host-1').status, 1)
            self.assertEqual(observer.get(RawHost, 'host-1').host_ip, '192.0.2.100')
            self.assertEqual(observer.get(InstallationCleanup, 'host-1').state, 'pending')
        self.connect.assert_not_called()

    def test_result_rolls_back_if_task_cannot_be_inserted(self):
        def reject_task(connection, cursor, statement, parameters, context, executemany):
            if statement.startswith('INSERT INTO installation_cleanup'):
                raise RuntimeError('database write failed')
        event.listen(self.engine, 'before_cursor_execute', reject_task)
        try:
            with self.assertRaises(RuntimeError):
                self.finish()
        finally:
            event.remove(self.engine, 'before_cursor_execute', reject_task)
        self.assertEqual(self.host().status, 3)
        self.assertEqual(self.session.query(InstallationCleanup).count(), 0)

    def test_duplicate_notification_does_not_reset_completed_cleanup(self):
        self.finish()
        self.lifecycle.clean_due(self.connect)
        self.finish()
        self.lifecycle.clean_due(self.connect)
        self.assertEqual(self.session.query(InstallationCleanup).count(), 1)
        self.assertEqual(self.task().state, 'done')
        self.remote.remove_system.assert_called_once_with(self.system_name, 'token')

    def test_completed_installation_wins_over_timeout(self):
        self.finish()
        self.finish(succeeded=False)
        self.assertEqual(self.host().status, 1)

    def test_late_current_round_completion_overrides_timeout(self):
        self.finish(succeeded=False)
        self.assertEqual(self.host().status, 4)
        self.finish()
        self.assertEqual(self.host().status, 1)
        self.assertEqual(self.session.query(InstallationCleanup).count(), 1)

    def test_old_round_cannot_finish_new_installation(self):
        self.finish()
        self.lifecycle.clean_due(self.connect)
        new_round, new_system = self.lifecycle.begin('host-1')
        self.assertNotEqual(self.round_id, new_round)
        self.assertNotEqual(self.system_name, new_system)
        with self.assertRaises(InstallationConflict):
            self.finish()
        self.assertEqual(self.host().status, 3)
        self.assertEqual(self.host().installation_round, new_round)
        self.assertEqual(self.session.query(InstallationCleanup).count(), 0)

    def test_installation_and_pending_cleanup_both_block_reinstallation(self):
        with self.assertRaisesRegex(InstallationConflict, '正在安装'):
            self.lifecycle.begin('host-1')
        self.finish()
        with self.assertRaisesRegex(InstallationConflict, '尚未清理'):
            self.lifecycle.begin('host-1')

    def test_failure_retains_result_and_backs_off_without_limit(self):
        self.finish()
        self.remote.remove_system.return_value = False
        for expected_delay in (300, 600, 1200, 1800, 1800, 1800):
            self.lifecycle.clean_due(self.connect)
            task = self.task()
            self.assertEqual(task.state, 'pending')
            self.assertEqual(task.next_attempt_at, self.now + timedelta(seconds=expected_delay))
            self.assertEqual(self.host().status, 1)
            calls = self.connect.call_count
            self.lifecycle.clean_due(self.connect)
            self.assertEqual(self.connect.call_count, calls)
            self.now = task.next_attempt_at
        self.assertEqual(self.task().failures, 6)
        self.remote.sync_dhcp.assert_not_called()

    def test_missing_system_still_requires_successful_dhcp_sync(self):
        self.finish()
        self.remote.get_system.return_value = '~'
        self.remote.sync_dhcp.return_value = False
        self.lifecycle.clean_due(self.connect)
        self.assertEqual(self.task().state, 'pending')
        self.remote.remove_system.assert_not_called()
        self.remote.sync_dhcp.return_value = True
        self.now = self.task().next_attempt_at
        self.lifecycle.clean_due(self.connect)
        self.assertEqual(self.task().state, 'done')
        self.assertIsNone(self.task().next_attempt_at)

    def test_retry_survives_session_restart_after_remote_delete(self):
        self.finish()
        self.remote.sync_dhcp.side_effect = TimeoutError('password=secret')
        self.lifecycle.clean_due(self.connect)
        self.assertNotIn('secret', self.task().last_error)
        self.now = self.task().next_attempt_at
        self.session.close()
        self.session = self.sessions()
        self.addCleanup(self.session.close)
        self.lifecycle = InstallationLifecycle(self.session, clock=lambda: self.now)
        self.remote.get_system.return_value = None
        self.remote.sync_dhcp.side_effect = None
        self.lifecycle.clean_due(self.connect)
        self.assertEqual(self.task().state, 'done')
        self.assertEqual(self.task().failures, 1)
        self.remote.remove_system.assert_called_once()

    def test_worker_rechecks_task_after_another_worker_completed_it(self):
        self.finish()
        self.lifecycle.clean_due(self.connect)
        self.lifecycle._clean_one('host-1', self.connect)
        self.connect.assert_called_once()

    def test_retry_does_not_touch_host_update_time(self):
        self.finish()
        old_time = self.host().update_time
        self.remote.sync_dhcp.return_value = False
        self.lifecycle.clean_due(self.connect)
        self.assertEqual(self.host().update_time, old_time)

    def test_new_start_time_invalidates_timeout_snapshot(self):
        snapshot = self.host().installation_started_at
        self.now += timedelta(minutes=1)
        self.lifecycle.prepare_start('host-1', self.round_id, '192.0.2.2')
        with self.assertRaises(InstallationConflict):
            self.lifecycle.finish('host-1', self.round_id, succeeded=False,
                                  expected_started_at=snapshot)
        self.assertEqual(self.host().status, 3)

    def test_closed_round_cannot_prepare_or_reset_host(self):
        self.finish(succeeded=False)
        with self.assertRaises(InstallationConflict):
            with self.lifecycle.active('host-1', self.round_id):
                self.fail('ended round must not execute power operation')

    def test_host_query_exposes_cleanup_and_protects_mutations(self):
        self.finish()
        proxy = HostProxy.__new__(HostProxy)
        proxy.session = self.session
        try:
            result, data = proxy.query_hosts({'page_no': 1, 'page_size': 10})
            self.assertTrue(result)
            self.assertEqual(data['host_infos'][0]['cleanup']['state'], 'pending')
            self.assertEqual(data['host_infos'][0]['installation_round'], self.round_id)
            self.assertFalse(proxy.delete_host(['host-1']))
            self.assertFalse(proxy.update_host_info({'host_id': 'host-1', 'host_name': 'renamed'}))
        finally:
            proxy.session = None

    def test_http_acknowledges_saved_result_and_rejects_missing_or_old_round(self):
        app = Flask(__name__)
        Api(app).add_resource(view.Notify, '/notify')
        client = app.test_client()
        proxy = Mock()
        proxy.session = self.session
        proxy.__enter__ = Mock(return_value=proxy)
        proxy.__exit__ = Mock(return_value=False)
        with patch.object(view, 'HostProxy', return_value=proxy), patch.object(view, 'RemoteServer') as remote:
            for round_id in (None, '', str(uuid4()), [], 123):
                response = client.post('/notify', json={
                    'bmc_ip': '192.0.2.1', 'installation_round': round_id})
                self.assertEqual(response.status_code, 400)
            response = client.post('/notify', json={
                'bmc_ip': '192.0.2.1', 'installation_round': self.round_id})
            self.assertEqual(response.status_code, 200)
            remote.assert_not_called()
        self.assertEqual(self.task().state, 'pending')

    def test_http_does_not_acknowledge_failed_commit(self):
        app = Flask(__name__)
        Api(app).add_resource(view.Notify, '/notify')
        proxy = Mock()
        proxy.session = self.session
        proxy.__enter__ = Mock(return_value=proxy)
        proxy.__exit__ = Mock(return_value=False)
        with patch.object(view, 'HostProxy', return_value=proxy), \
                patch.object(self.session, 'commit', side_effect=RuntimeError('database failed')):
            response = app.test_client().post('/notify', json={
                'bmc_ip': '192.0.2.1', 'installation_round': self.round_id})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.host().status, 3)
        self.assertEqual(self.session.query(InstallationCleanup).count(), 0)

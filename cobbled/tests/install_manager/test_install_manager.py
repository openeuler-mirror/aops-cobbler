#!/usr/bin/python3
# ******************************************************************************
# Copyright (c) iSoftStone Technologies Co., Ltd. 2023-2024. All rights reserved.
# licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#     http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN 'AS IS' BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v2 for more details.
# ******************************************************************************
"""
Time:
Author:
Description: test install manager.
"""

import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cobbled.database.host import HostProxy
from cobbled.database.table import Base, RawHost
from cobbled.install_manager import view
from cobbled.install_manager.lifecycle import InstallationConflict
from cobbled.install_manager.workflow import (
    InstallationSettings, InstallationWorkflow, distribute_ip,
    render_after_os_installed_script)


class TestDistributeIpCache(unittest.TestCase):
    def test_rechecks_cached_occupied_ip_when_range_is_exhausted(self):
        occupied = {"192.0.2.100"}
        proxy = Mock()
        proxy.query_host_by_host_ip.side_effect = lambda ip: (
            True, [object()] if ip in occupied else [])
        cached_occupied = set()

        first = distribute_ip(proxy, [], "192.0.2.100", "192.0.2.101",
                              occupied_ips=cached_occupied)
        occupied.clear()  # 数据库中的旧 IP 在两次分配之间被释放
        second = distribute_ip(proxy, [first], "192.0.2.100", "192.0.2.101",
                               occupied_ips=cached_occupied)

        self.assertEqual(first, "192.0.2.101")
        self.assertEqual(second, "192.0.2.100")


class TestAfterInstallScriptRendering(unittest.TestCase):

    def test_after_install_script_uses_configured_subnet_mask(self):
        script_path = Path(__file__).parents[3] / "script" / "after_os_installed.sh"
        script = script_path.read_text(encoding="utf-8")

        rendered_script = render_after_os_installed_script(
            script, "10.10.192.1", 8888, prefix=16)

        self.assertIn("prefix='16'", rendered_script)
        self.assertNotIn("s_u_b_n_e_t_m_a_s_k", rendered_script)
        self.assertIn("configured_gateway=''", rendered_script)

    def test_gateway_in_allocatable_pool_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "sample.ks").write_text("", encoding="utf-8")
            for gateway in ("192.0.2.100", "192.0.2.105", "192.0.2.110"):
                with self.subTest(gateway=gateway):
                    settings = InstallationSettings(
                        ks_dir=directory, script_dir=directory, client_ip="192.0.2.254",
                        port=8888, subnet_mask=24, os_start_ip="192.0.2.100",
                        os_end_ip="192.0.2.110", gateway=gateway)
                    workflow = InstallationWorkflow(
                        settings, connect_cobbler=Mock(),
                        host_store=MagicMock(), power=Mock())
                    with patch("cobbled.install_manager.workflow."
                               "CobblerInstallationConfiguration.for_image",
                               return_value=MagicMock()), \
                            patch("cobbled.install_manager.workflow."
                                  "FileUtil.read_file_content", return_value="echo installed"):
                        result = workflow.run(host_list=[], ks_name="sample",
                                              iso_name="sample", arch="x86_64")
                    self.assertEqual(result.code, 400)
                    self.assertIn("网关", result.msg)


class TestRpmLookup(unittest.TestCase):

    def test_lookup_uses_the_same_normalized_names_as_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "sample.ks").write_text("", encoding="utf-8")
            settings = InstallationSettings(
                ks_dir=directory, script_dir=directory, client_ip="10.0.0.1",
                port=8888, subnet_mask=24, os_start_ip="10.0.0.2",
                os_end_ip="10.0.0.3")
            workflow = InstallationWorkflow(
                settings, connect_cobbler=Mock(), host_store=Mock(), power=Mock())
            with patch("cobbled.install_manager.workflow.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 0, stderr="")) as run, \
                    patch("cobbled.install_manager.workflow."
                          "CobblerInstallationConfiguration.for_image", return_value=None):
                workflow.run(host_list=[], ks_name="sample", iso_name="sample",
                             arch="x86_64", install_rpm=" vim, ,git, ")
            self.assertEqual([call.args[0] for call in run.call_args_list],
                             [["yum", "search", "vim"], ["yum", "search", "git"]])

    def test_yum_lookup_is_bounded_and_timeout_returns_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "sample.ks").write_text("", encoding="utf-8")
            settings = InstallationSettings(
                ks_dir=directory, script_dir=directory, client_ip="10.0.0.1",
                port=8888, subnet_mask=24, os_start_ip="10.0.0.2",
                os_end_ip="10.0.0.3", rpm_search_timeout=45)
            workflow = InstallationWorkflow(
                settings, connect_cobbler=Mock(), host_store=Mock(), power=Mock())
            with patch("cobbled.install_manager.workflow.subprocess.run",
                       side_effect=subprocess.TimeoutExpired(["yum", "search", "vim"], 45)) as run:
                result = workflow.run(
                    host_list=[], ks_name="sample", iso_name="sample",
                    arch="x86_64", install_rpm="vim")
        self.assertEqual(result.code, 400)
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs["timeout"], 45)

    def test_lookup_errors_are_logged_and_distinguished(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "sample.ks").write_text("", encoding="utf-8")
            settings = InstallationSettings(
                ks_dir=directory, script_dir=directory, client_ip="10.0.0.1",
                port=8888, subnet_mask=24, os_start_ip="10.0.0.2",
                os_end_ip="10.0.0.3")
            workflow = InstallationWorkflow(
                settings, connect_cobbler=Mock(), host_store=Mock(), power=Mock())
            for error, message in (
                    (subprocess.TimeoutExpired(["yum", "search", "vim"], 30), "timed out"),
                    (OSError("yum missing"), "Failed to run")):
                with self.subTest(error=error), \
                        patch("cobbled.install_manager.workflow.subprocess.run", side_effect=error), \
                        patch("cobbled.install_manager.workflow.LOGGER") as logger:
                    result = workflow.run(
                        host_list=[], ks_name="sample", iso_name="sample",
                        arch="x86_64", install_rpm="vim")
                    self.assertIn(message, result.msg)
                    logger.exception.assert_called_once()


class TestHostScheduler(unittest.TestCase):

    def test_checks_all_installing_hosts_across_batches(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE TRIGGER raw_host_update_time
                AFTER UPDATE ON raw_host
                FOR EACH ROW
                BEGIN
                    UPDATE raw_host
                       SET update_time = datetime(OLD.update_time, '+1 day')
                     WHERE host_id = NEW.host_id;
                END
            """)
        session = sessionmaker(bind=engine)()
        self.addCleanup(engine.dispose)
        self.addCleanup(session.close)

        update_time = datetime.now() - timedelta(minutes=10)
        for index in range(11):
            session.add(RawHost(
                host_id=str(index),
                host_name=f"host-{index}",
                bmc_ip=f"10.0.0.{index + 1}",
                bmc_user_name="user",
                bmc_passwd="password",
                host_mac=f"00:00:00:00:00:{index:02x}",
                status=3,
                installation_round=f"round-{index}",
                installation_system=f"system-{index}",
                installation_started_at=update_time,
                update_time=update_time,
            ))
        session.commit()

        host_proxy = HostProxy.__new__(HostProxy)
        host_proxy.session = session
        remote_server = Mock()
        remote_factory = Mock()
        remote_factory.get_remote_server.return_value = (remote_server, "token")

        with patch.object(view, "HostProxy", return_value=host_proxy), \
                patch.object(view, "RemoteServer", return_value=remote_factory), \
                patch.object(view, "HOST_SCHEDULER_BATCH_SIZE", 10, create=True), \
                patch.object(view.os.path, "exists", return_value=False):
            view.host_scheduler()

        installing_count = session.query(RawHost).filter(RawHost.status == 3).count()
        failed_count = session.query(RawHost).filter(RawHost.status == 4).count()
        self.assertEqual(installing_count, 0)
        self.assertEqual(failed_count, 11)
        self.assertEqual(remote_server.remove_system.call_count, 11)
        self.assertEqual(remote_server.sync_dhcp.call_count, 11)


class TestCheckInstallationStatus(unittest.TestCase):

    @staticmethod
    def _make_host(host_id="1", host_name="host-1", round_id="round-1",
                   started_at=None, update_time=None):
        now = datetime.now()
        started_at = started_at if started_at is not None else now - timedelta(minutes=10)
        update_time = update_time if update_time is not None else started_at
        return SimpleNamespace(
            host_id=host_id,
            host_name=host_name,
            installation_round=round_id,
            installation_started_at=started_at,
            update_time=update_time,
        )

    @staticmethod
    def _write_log(directory, host_name, host_id, mtime_offset_seconds=0):
        log_path = Path(directory, f"{host_name}-{host_id}.log")
        log_path.write_text("installing...\n", encoding="utf-8")
        target_mtime = (datetime.now() - timedelta(seconds=mtime_offset_seconds)).timestamp()
        os.utime(log_path, (target_mtime, target_mtime))
        return log_path

    def test_query_failure_logs_error_and_stops(self):
        host_proxy = Mock()
        host_proxy.session = Mock()
        host_proxy.query_hosts_by_status_batch.return_value = (False, [])
        lifecycle = Mock()

        with patch.object(view, "InstallationLifecycle", return_value=lifecycle), \
                patch.object(view, "LOGGER") as logger:
            view._check_installation_status(host_proxy)

        host_proxy.query_hosts_by_status_batch.assert_called_once_with(
            3, view.HOST_SCHEDULER_BATCH_SIZE, None, None)
        logger.error.assert_called_once_with(
            "Query installing hosts failed during scheduled task.")
        lifecycle.finish.assert_not_called()

    def test_empty_hosts_exits_cleanly(self):
        host_proxy = Mock()
        host_proxy.session = Mock()
        host_proxy.query_hosts_by_status_batch.return_value = (True, [])
        lifecycle = Mock()

        with patch.object(view, "InstallationLifecycle", return_value=lifecycle), \
                patch.object(view, "LOGGER") as logger:
            view._check_installation_status(host_proxy)

        host_proxy.query_hosts_by_status_batch.assert_called_once_with(
            3, view.HOST_SCHEDULER_BATCH_SIZE, None, None)
        logger.error.assert_not_called()
        lifecycle.finish.assert_not_called()

    def test_skips_host_installing_less_than_300_seconds(self):
        started_at = datetime.now() - timedelta(seconds=120)
        host = self._make_host(started_at=started_at)
        host_proxy = Mock()
        host_proxy.session = Mock()
        host_proxy.query_hosts_by_status_batch.return_value = (True, [host])
        lifecycle = Mock()

        with tempfile.TemporaryDirectory() as log_dir, \
                patch.object(view, "os_install_log_dir", log_dir), \
                patch.object(view, "os_installed_time", 30), \
                patch.object(view, "InstallationLifecycle", return_value=lifecycle):
            view._check_installation_status(host_proxy)

        lifecycle.finish.assert_not_called()

    def test_keeps_installing_when_log_recently_updated_and_within_limit(self):
        started_at = datetime.now() - timedelta(seconds=600)
        host = self._make_host(started_at=started_at)
        host_proxy = Mock()
        host_proxy.session = Mock()
        host_proxy.query_hosts_by_status_batch.return_value = (True, [host])
        lifecycle = Mock()

        with tempfile.TemporaryDirectory() as log_dir:
            self._write_log(log_dir, host.host_name, host.host_id, mtime_offset_seconds=30)
            with patch.object(view, "os_install_log_dir", log_dir), \
                    patch.object(view, "os_installed_time", 30), \
                    patch.object(view, "InstallationLifecycle", return_value=lifecycle):
                view._check_installation_status(host_proxy)

        lifecycle.finish.assert_not_called()

    def test_marks_failed_when_log_mtime_exceeds_120_seconds(self):
        started_at = datetime.now() - timedelta(seconds=600)
        host = self._make_host(started_at=started_at)
        host_proxy = Mock()
        host_proxy.session = Mock()
        host_proxy.query_hosts_by_status_batch.return_value = (True, [host])
        lifecycle = Mock()

        with tempfile.TemporaryDirectory() as log_dir:
            self._write_log(log_dir, host.host_name, host.host_id, mtime_offset_seconds=180)
            with patch.object(view, "os_install_log_dir", log_dir), \
                    patch.object(view, "os_installed_time", 30), \
                    patch.object(view, "InstallationLifecycle", return_value=lifecycle):
                view._check_installation_status(host_proxy)

        lifecycle.finish.assert_called_once_with(
            "1", "round-1", succeeded=False, expected_started_at=started_at)

    def test_marks_failed_when_total_duration_exceeds_os_installed_time(self):
        started_at = datetime.now() - timedelta(minutes=31)
        host = self._make_host(started_at=started_at)
        host_proxy = Mock()
        host_proxy.session = Mock()
        host_proxy.query_hosts_by_status_batch.return_value = (True, [host])
        lifecycle = Mock()

        with tempfile.TemporaryDirectory() as log_dir:
            self._write_log(log_dir, host.host_name, host.host_id, mtime_offset_seconds=10)
            with patch.object(view, "os_install_log_dir", log_dir), \
                    patch.object(view, "os_installed_time", 30), \
                    patch.object(view, "InstallationLifecycle", return_value=lifecycle):
                view._check_installation_status(host_proxy)

        lifecycle.finish.assert_called_once_with(
            "1", "round-1", succeeded=False, expected_started_at=started_at)

    def test_logs_error_and_skips_legacy_host_without_installation_round(self):
        started_at = datetime.now() - timedelta(seconds=600)
        legacy_host = self._make_host(
            host_id="1", host_name="legacy-host", round_id=None, started_at=started_at)
        normal_host = self._make_host(
            host_id="2", host_name="normal-host", round_id="round-2", started_at=started_at)
        host_proxy = Mock()
        host_proxy.session = Mock()
        host_proxy.query_hosts_by_status_batch.return_value = (True, [legacy_host, normal_host])
        lifecycle = Mock()

        with tempfile.TemporaryDirectory() as log_dir, \
                patch.object(view, "os_install_log_dir", log_dir), \
                patch.object(view, "os_installed_time", 30), \
                patch.object(view, "InstallationLifecycle", return_value=lifecycle), \
                patch.object(view, "LOGGER") as logger:
            view._check_installation_status(host_proxy)

        logger.error.assert_called_once_with(
            "Legacy installation requires manual cleanup: %s", "1")
        lifecycle.finish.assert_called_once_with(
            "2", "round-2", succeeded=False, expected_started_at=started_at)

    def test_ignores_installation_conflict_and_continues(self):
        started_at = datetime.now() - timedelta(seconds=600)
        host_1 = self._make_host(
            host_id="1", host_name="host-1", round_id="round-1", started_at=started_at)
        host_2 = self._make_host(
            host_id="2", host_name="host-2", round_id="round-2", started_at=started_at)
        host_proxy = Mock()
        host_proxy.session = Mock()
        host_proxy.query_hosts_by_status_batch.return_value = (True, [host_1, host_2])
        lifecycle = Mock()
        lifecycle.finish.side_effect = [InstallationConflict("new round started"), None]

        with tempfile.TemporaryDirectory() as log_dir, \
                patch.object(view, "os_install_log_dir", log_dir), \
                patch.object(view, "os_installed_time", 30), \
                patch.object(view, "InstallationLifecycle", return_value=lifecycle):
            view._check_installation_status(host_proxy)

        self.assertEqual(lifecycle.finish.call_args_list, [
            call("1", "round-1", succeeded=False, expected_started_at=started_at),
            call("2", "round-2", succeeded=False, expected_started_at=started_at),
        ])


if __name__ == "__main__":
    unittest.main()

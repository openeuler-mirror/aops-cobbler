"""Installation must prepare boot configuration before resetting any host."""

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cobbled.conf.constant import HostCons, InstallCons
from cobbled.install_manager import power, workflow
from cobbled.install_manager.power import IPMIPower
from cobbled.install_manager.workflow import InstallationSettings, InstallationWorkflow


class TestAutoInstallBootOrder(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        config_dir = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.config_path = Path(config_dir) / "default"
        self.events = []
        self.boot_snapshots = []
        self.failure = None
        self.fail_bmc = "192.0.2.1"
        self.states = {}
        self.hosts = {
            f"192.0.2.{index}": SimpleNamespace(
                host_id=str(index), host_name=f"host-{index}",
                host_mac=f"00:11:22:33:44:{index:02x}",
                bmc_user_name="test", bmc_passwd="encrypted-test-password")
            for index in (1, 2)
        }
        self.proxy = Mock()
        self.proxy.__enter__ = Mock(return_value=self.proxy)
        self.proxy.__exit__ = Mock(return_value=False)
        self.proxy.query_host_by_bmc_ip.side_effect = lambda bmc: (True, [self.hosts[bmc]])
        self.proxy.update_host_info.side_effect = self.persist
        self.remote = Mock()
        self.remote.get_distro.return_value = {"name": "test-x86_64"}
        self.remote.get_profile.return_value = {
            "name": "test-x86_64", "autoinstall": "test.ks"}
        self.remote.get_profiles.return_value = []
        self.remote.sync.side_effect = self.sync
        self.remote.new_system.side_effect = self.new_system
        self.remote.modify_system.side_effect = self.modify_system
        self.remote.save_system.side_effect = self.save_system
        self.remote.sync_dhcp.side_effect = self.sync_dhcp
        self.proxy.query_host_by_host_ip.return_value = (True, [])
        root = Path(config_dir)
        (root / "test.ks").write_text("test-template")
        after_script = root / "after.sh"
        after_script.write_text("echo 127.0.0.1 8888 s_u_b_n_e_t_m_a_s_k")
        self.bmc_check = self.stack.enter_context(patch.object(
            power.HostChecker, "bmc_connection_error", return_value=None))
        self.stack.enter_context(patch.object(power.AesUtil, "decrypt",
                                            return_value="test-password"))
        self.stack.enter_context(patch.object(power, "run_ipmitool", side_effect=self.ipmi))
        self.update_pxe = workflow.update_pxe_config_files
        self.stack.enter_context(patch.object(workflow, "update_pxe_config_files",
                                            side_effect=self.patch_pxe))
        self.workflow = InstallationWorkflow(
            InstallationSettings(
                ks_dir=config_dir, script_dir=config_dir, client_ip="192.0.2.254",
                port=8888, subnet_mask="24", os_start_ip="192.0.2.100",
                os_end_ip="192.0.2.101", pxe_config_dir=config_dir,
                after_install_script=str(after_script),
            ),
            connect_cobbler=lambda: (self.remote, "token"),
            host_store=lambda: self.proxy,
            power=IPMIPower(),
        )

    def sync(self, token):
        self.events.append(("sync", None))
        self.config_path.write_text("append ks=http://test/ks repo=http://test/repo kssendmac\n")
        return self.failure != "sync"

    def new_system(self, token):
        self.current_id = str(self.remote.new_system.call_count)
        self.events.append(("new_system", self.current_id))
        return False if self.failure == "new_system" and self.current_id == "1" else self.current_id

    def modify_system(self, system_id, *args):
        self.events.append(("modify_system", system_id))
        return not (self.failure == "modify_system" and system_id == "1")

    def save_system(self, system_id, token):
        self.events.append(("save_system", system_id))
        # A later Cobbler write may regenerate legacy arguments in existing files.
        self.config_path.write_text("append ks=http://test/ks repo=http://test/repo kssendmac\n")
        return not (self.failure == "save_system" and system_id == "1")

    def sync_dhcp(self, token):
        self.events.append(("sync_dhcp", self.current_id))
        return not (self.failure == "sync_dhcp" and self.current_id == "1")

    def patch_pxe(self, config_dir):
        self.events.append(("pxe_update", None))
        if self.failure == "pxe_update":
            raise OSError("simulated PXE write failure")
        return self.update_pxe(config_dir)

    def persist(self, info):
        self.events.append((f"status_{info['status']}", info["host_id"]))
        if self.failure == "persist" and info["status"] == 3 and info["host_id"] == "1":
            return False
        if self.failure == "failure_status" and info["status"] == 4:
            return False
        self.states[info["host_id"]] = info["status"]
        return True

    def ipmi(self, bmc, user, password, *command):
        command = " ".join(command)
        host_id = self.hosts[bmc].host_id
        self.events.append((command, host_id))
        if command == "power reset":
            self.boot_snapshots.append((host_id, self.config_path.read_text(),
                                        self.states.get(host_id)))
        if bmc == self.fail_bmc:
            if self.failure == "ipmi_exception":
                raise RuntimeError("simulated startup error")
            if self.failure == command or (self.failure == "failure_status" and command == "power reset"):
                return 1
        return 0

    def install(self, host_count=1):
        self.events.clear()
        self.boot_snapshots.clear()
        self.states.clear()
        self.remote.new_system.reset_mock()
        payload = {"host_list": [{"bmc_ip": bmc} for bmc in list(self.hosts)[:host_count]],
                   "iso_name": "test", "arch": "x86_64", "ks_name": "test"}
        return self.workflow.run(**payload)

    def test_all_configuration_is_ready_before_any_host_resets(self):
        response = self.install(host_count=2)
        self.assertEqual(response.code, 200)
        self.assertEqual([host["result"] for host in response.data], ["succeed", "succeed"])
        self.assertEqual(len(self.boot_snapshots), 2)
        for host_id, config, status in self.boot_snapshots:
            self.assertEqual(status, 3)
            self.assertIn("inst.ks=", config)
            self.assertIn("inst.repo=", config)
            self.assertIn("inst.kssendmac", config)
            reset_index = self.events.index(("power reset", host_id))
            for operation in ("save_system", "sync_dhcp", "pxe_update"):
                self.assertTrue(all(index < reset_index for index, event in enumerate(self.events)
                                    if event[0] == operation), self.events)

    def test_preparation_failure_never_resets_host(self):
        for failure in ("sync", "new_system", "modify_system", "save_system",
                        "sync_dhcp", "pxe_update", "persist"):
            with self.subTest(failure=failure):
                self.failure = failure
                response = self.install()
                self.assertEqual(self.boot_snapshots, [], self.events)
                if failure != "sync":
                    self.assertEqual(response.data[0]["result"], "failed")
                    self.assertTrue(response.data[0]["reason"])
                self.assertNotIn(3, self.states.values())

    def test_startup_failure_marks_failed_and_continues_next_host(self):
        for failure in ("chassis bootdev pxe", "power reset", "ipmi_exception"):
            with self.subTest(failure=failure):
                self.failure = failure
                response = self.install(host_count=2)
                first, second = response.data
                self.assertEqual(first["result"], "failed")
                self.assertEqual(first["reason"], InstallCons.IPMI_COMMAND_EXECUTE_TIPS)
                self.assertEqual(self.states["1"], 4)
                self.assertEqual(second["result"], "succeed")
                self.assertEqual(self.states["2"], 3)
                if failure != "power reset":
                    self.assertNotIn(("power reset", "1"), self.events)

    def test_preparation_failure_skips_only_the_failed_host(self):
        for failure in ("new_system", "modify_system", "save_system", "sync_dhcp", "persist"):
            with self.subTest(failure=failure):
                self.failure = failure
                response = self.install(host_count=2)
                first, second = response.data
                self.assertEqual(first["result"], "failed")
                self.assertNotIn(("power reset", "1"), self.events)
                self.assertEqual(second["result"], "succeed")
                self.assertEqual(self.states["2"], 3)
                self.assertEqual([host_id for host_id, _, _ in self.boot_snapshots], ["2"])

    def test_pxe_update_failure_reports_all_prepared_hosts_as_failed(self):
        self.failure = "pxe_update"
        response = self.install(host_count=2)
        self.assertEqual(response.code, 400)
        self.assertEqual(self.boot_snapshots, [])
        self.assertEqual(self.states, {})
        for host in response.data:
            self.assertEqual(host["result"], "failed")
            self.assertEqual(host["reason"], InstallCons.MODIFY_PXE_LINUX_DEFAULT_TIPS)

    def test_failed_startup_status_update_is_reported(self):
        self.failure = "failure_status"
        response = self.install()
        result = response.data[0]
        self.assertEqual(result["result"], "failed")
        self.assertIn(InstallCons.IPMI_COMMAND_EXECUTE_TIPS, result["reason"])
        self.assertIn(HostCons.UPDATE_HOST_FAILED_TIPS, result["reason"])

    def test_bmc_failure_is_a_plain_result_without_flask_context(self):
        self.bmc_check.return_value = HostCons.CHECK_BMC_CONNECTION_TIPS
        result = self.install()
        self.assertEqual(result.code, 200)
        self.assertEqual(result.data[0]["reason"], HostCons.CHECK_BMC_CONNECTION_TIPS)
        self.assertEqual(self.boot_snapshots, [])
        self.remote.new_system.assert_not_called()
        self.proxy.__exit__.assert_called_once()

    def test_no_available_ip_never_prepares_or_resets_host(self):
        self.proxy.query_host_by_host_ip.return_value = (True, [object()])
        result = self.install()
        self.assertEqual(result.data[0]["reason"], InstallCons.NO_AVAILABLE_IP_LEFT_TIPS)
        self.assertEqual(self.boot_snapshots, [])
        self.remote.new_system.assert_not_called()

    def test_storage_exception_preserves_partial_results_and_closes_session(self):
        self.proxy.query_host_by_bmc_ip.side_effect = RuntimeError("storage failed")
        result = self.install()
        self.assertEqual(result.code, 400)
        self.assertEqual(result.msg, "storage failed")
        self.assertEqual(result.data, [{"bmc_ip": "192.0.2.1", "result": "failed"}])
        self.assertEqual(self.boot_snapshots, [])
        self.proxy.__exit__.assert_called_once()

    def test_remote_exception_does_not_open_host_storage(self):
        self.remote.get_distro.side_effect = RuntimeError("remote failed")
        result = self.install()
        self.assertEqual(result.code, 400)
        self.assertEqual(result.msg, "remote failed")
        self.assertEqual(result.data, [])
        self.proxy.__enter__.assert_not_called()
        self.assertEqual(self.boot_snapshots, [])


if __name__ == "__main__":
    unittest.main()

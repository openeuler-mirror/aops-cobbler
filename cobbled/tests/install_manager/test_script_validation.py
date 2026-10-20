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
"""Regression tests for custom script selection during automatic installation."""

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask

from cobbled.conf.constant import ScriptCons
from cobbled.install_manager import view, workflow


class TestAutoInstallScriptValidation(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.context = ExitStack()
        self.addCleanup(self.context.close)
        root = Path(self.context.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.script_dir = root / "scripts"
        self.script_dir.mkdir()
        self.ks_dir = root / "ks"
        self.ks_dir.mkdir()
        (self.ks_dir / "test.ks").write_text("kickstart content", encoding="utf-8")
        outside_dir = root / "scripts-outside"
        outside_dir.mkdir()
        self.outside_script = outside_dir / "external.sh"
        self.outside_script.write_text("echo outside-script", encoding="utf-8")
        self.payload = {
            "host_list": [{"bmc_ip": "192.0.2.1"}],
            "iso_name": "test", "arch": "x86_64", "ks_name": "test",
        }

        self.remote = MagicMock()
        self.remote.get_profile.return_value = {"autoinstall": "test.ks"}
        self.remote.get_profiles.return_value = []
        remote_factory = self.context.enter_context(patch.object(view, "RemoteServer"))
        remote_factory.return_value.get_remote_server.return_value = (self.remote, "token")
        self.remote_factory = remote_factory
        host_proxy = self.context.enter_context(patch.object(view, "HostProxy"))
        proxy = host_proxy.return_value.__enter__.return_value
        proxy.query_host_by_bmc_ip.return_value = (True, [SimpleNamespace(
            host_id="host-1", host_name="host", host_mac="aa:bb:cc:dd:ee:ff",
            bmc_user_name="user", bmc_passwd="encrypted")])
        proxy.query_host_by_host_ip.return_value = (True, [])
        lifecycle = self.context.enter_context(patch.object(workflow, "InstallationLifecycle"))
        lifecycle.return_value.begin.return_value = ("round", "system-round")
        power = self.context.enter_context(patch.object(view, "IPMIPower"))
        power.return_value.check_connection.return_value = None
        power.return_value.start.return_value = 0
        self.context.enter_context(patch.object(view, "script_dir", str(self.script_dir)))
        self.context.enter_context(patch.object(view, "ks_dir", str(self.ks_dir)))
        self.context.enter_context(patch.object(workflow, "update_pxe_config_files"))
        self.read_file = self.context.enter_context(patch.object(
            workflow.FileUtil, "read_file_content", side_effect=self.read_content))

    @staticmethod
    def read_content(path):
        if path == "/opt/aops/script/after_os_installed.sh":
            return "echo installation-complete"
        return Path(path).read_text(encoding="utf-8")

    def post(self, **fields):
        with self.app.test_request_context(json={**self.payload, **fields}):
            return view.AutoInstall().post()

    def assert_rejected_before_read(self, response, message=ScriptCons.CHECK_SCRIPT_NAME_TIPS):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["msg"], message)
        self.read_file.assert_not_called()
        self.remote_factory.assert_not_called()
        self.remote.write_autoinstall_template.assert_not_called()

    def test_rejects_existing_script_outside_directory(self):
        for name in ("../scripts-outside/external", str(self.outside_script.with_suffix(""))):
            with self.subTest(name=name):
                response = self.post(script_name=name)
                self.assert_rejected_before_read(response)

    def test_rejects_symlink_resolving_outside_directory(self):
        (self.script_dir / "external.sh").symlink_to(self.outside_script)
        (self.script_dir / "chain.sh").symlink_to(self.script_dir / "external.sh")
        for name in ("external", "chain"):
            with self.subTest(name=name):
                response = self.post(script_name=name)
                self.assert_rejected_before_read(response)

    def test_rejects_invalid_script_names(self):
        for name in ("subdir/script", "..\\external", "script.sh", "script\n", "a" * 129,
                     " ", 42, 0, False, [], {}, ["script"]):
            with self.subTest(name=name):
                response = self.post(script_name=name)
                self.assert_rejected_before_read(response)

    def test_missing_script_keeps_existing_error(self):
        response = self.post(script_name="missing")
        self.assert_rejected_before_read(response, ScriptCons.CHECK_SCRIPT_EXITS_TIPS)

    def test_valid_script_content_is_written_to_install_template(self):
        for name in ("setup_A-1", "a" * 128):
            with self.subTest(name=name):
                script = self.script_dir / (name + ".sh")
                script.write_text("echo custom-script", encoding="utf-8")
                response = self.post(script_name=name)
                self.assertEqual(response.status_code, 200)
                content = self.remote.write_autoinstall_template.call_args.args[1]
                self.assertIn("\n%post\necho custom-script\n%end\n", content)
                self.read_file.assert_any_call(str(script))

    def test_script_is_optional(self):
        for fields in ({}, {"script_name": None}, {"script_name": ""}):
            with self.subTest(fields=fields):
                response = self.post(**fields)
                self.assertEqual(response.status_code, 200)
                content = self.remote.write_autoinstall_template.call_args.args[1]
                self.assertNotIn("outside-script", content)
                self.assertEqual(content.count("%post"), 1)

    def test_allows_symlink_resolving_inside_directory(self):
        script = self.script_dir / "setup.sh"
        script.write_text("echo custom-script", encoding="utf-8")
        (self.script_dir / "alias.sh").symlink_to(script)
        response = self.post(script_name="alias")
        self.assertEqual(response.status_code, 200)
        content = self.remote.write_autoinstall_template.call_args.args[1]
        self.assertIn("\n%post\necho custom-script\n%end\n", content)

    def test_allows_script_directory_configured_as_symlink(self):
        alias_dir = self.script_dir.parent / "script-link"
        alias_dir.symlink_to(self.script_dir, target_is_directory=True)
        (self.script_dir / "setup.sh").write_text("echo custom-script", encoding="utf-8")
        with patch.object(view, "script_dir", str(alias_dir)):
            response = self.post(script_name="setup")
        self.assertEqual(response.status_code, 200)
        content = self.remote.write_autoinstall_template.call_args.args[1]
        self.assertIn("\n%post\necho custom-script\n%end\n", content)


if __name__ == "__main__":
    unittest.main()

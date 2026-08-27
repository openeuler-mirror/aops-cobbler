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
"""Regression tests for command-injection vulnerabilities."""

import os
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from flask import Flask

from cobbled.install_manager import view as install_view
from cobbled.util import validate_util
from cobbled.util.validate_util import HostChecker


class TestCommandInjectionRegressions(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_install_log_archive_does_not_invoke_a_shell_and_streams_in_memory(self):
        log_file_name = "host-test-12345"

        with tempfile.TemporaryDirectory() as log_dir:
            log_path = os.path.join(log_dir, log_file_name + ".log")
            with open(log_path, "w", encoding="utf-8") as log_file:
                log_file.write("installation log")

            with self.app.test_request_context(
                    json={"log_file_name": log_file_name}), \
                    patch.object(install_view, "os_install_log_dir", log_dir), \
                    patch.object(install_view.os, "system") as system:
                response = install_view.GetInstallLogFile().post()

            system.assert_not_called()
            self.assertEqual(response.status_code, 200)
            # Ensure no zip file is created or left on disk
            self.assertFalse(os.path.exists(os.path.join(log_dir, log_file_name + ".zip")))
            # Verify the response body is a valid zip stream containing the log file
            import io
            stream_data = b"".join(response.response)
            with zipfile.ZipFile(io.BytesIO(stream_data)) as archive:
                self.assertEqual(archive.namelist(), [log_file_name + ".log"])
                self.assertEqual(archive.read(log_file_name + ".log").decode("utf-8"), "installation log")

    def test_install_log_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as log_dir:
            # Create a file outside or in log_dir
            traversal_payloads = [
                "../../etc/passwd",
                "../sensitive",
                "/etc/passwd",
                "subdir/test",
                "test/../../etc",
            ]
            for payload in traversal_payloads:
                with self.app.test_request_context(
                        json={"log_file_name": payload}), \
                        patch.object(install_view, "os_install_log_dir", log_dir):
                    response = install_view.GetInstallLogFile().post()
                self.assertEqual(response.json["code"], 400)

    def test_install_log_rejects_empty_name(self):
        with tempfile.TemporaryDirectory() as log_dir:
            for empty_val in ["", "   ", None]:
                with self.app.test_request_context(
                        json={"log_file_name": empty_val}), \
                        patch.object(install_view, "os_install_log_dir", log_dir):
                    response = install_view.GetInstallLogFile().post()
                self.assertEqual(response.json["code"], 400)

    def test_bmc_connection_passes_untrusted_values_as_atomic_arguments(self):
        host = {
            "bmc_ip": "192.0.2.1;touch command-injected",
            "bmc_user_name": "admin;touch command-injected",
            "bmc_passwd": "encrypted-password",
        }
        password = "quote' ; touch command-injected"

        with patch.object(validate_util.configuration, "host", {"CHECK_BMC_CONNECTION": 1}), \
                patch.object(validate_util.AesUtil, "decrypt", return_value=password), \
                patch.object(validate_util.subprocess, "run") as run:
            run.return_value.returncode = 0
            result = HostChecker.check_bmc_connection(host)

        self.assertIsNone(result)
        run.assert_called_once_with([
            "ipmitool", "-H", host["bmc_ip"], "-I", "lanplus",
            "-U", host["bmc_user_name"], "-P", password,
            "power", "status"
        ])

    def test_pxe_boot_argument_prefixing_is_idempotent(self):
        original = (
            "append initrd=initrd.img ks=http://host/a.ks "
            "repo=http://host/repo kssendmac "
            "inst.ks=http://old inst.repo=http://old inst.kssendmac\n"
        )
        expected = (
            "append initrd=initrd.img inst.ks=http://host/a.ks "
            "inst.repo=http://host/repo inst.kssendmac "
            "inst.ks=http://old inst.repo=http://old inst.kssendmac\n"
        )

        updated = install_view.prefix_pxe_boot_arguments(original)
        updated_twice = install_view.prefix_pxe_boot_arguments(updated)

        self.assertEqual(updated, expected)
        self.assertEqual(updated_twice, expected)

    def test_pxe_config_update_only_rewrites_regular_files(self):
        original = "append ks=http://host/a.ks repo=http://host/repo kssendmac\n"
        expected = "append inst.ks=http://host/a.ks inst.repo=http://host/repo inst.kssendmac\n"

        with tempfile.TemporaryDirectory() as config_dir:
            config_path = os.path.join(config_dir, "default")
            with open(config_path, "w", encoding="utf-8") as config_file:
                config_file.write(original)

            os.mkdir(os.path.join(config_dir, "entries"))
            with open(os.path.join(config_dir, ".lock"), "w", encoding="utf-8") as hidden_file:
                hidden_file.write(original)

            first_update_count = install_view.update_pxe_config_files(config_dir)
            second_update_count = install_view.update_pxe_config_files(config_dir)

            with open(config_path, "r", encoding="utf-8") as config_file:
                self.assertEqual(config_file.read(), expected)
            self.assertEqual(first_update_count, 1)
            self.assertEqual(second_update_count, 0)


if __name__ == "__main__":
    unittest.main()

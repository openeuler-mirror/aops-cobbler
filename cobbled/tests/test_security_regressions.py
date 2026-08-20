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

    def test_install_log_archive_does_not_invoke_a_shell(self):
        log_file_name = "host;touch command-injected;#"

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
            with zipfile.ZipFile(os.path.join(log_dir, log_file_name + ".zip")) as archive:
                self.assertEqual(archive.namelist(), [log_file_name + ".log"])

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


if __name__ == "__main__":
    unittest.main()

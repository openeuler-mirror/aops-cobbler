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
# ******************************************************************************/
"""
Time:
Author:
Description: Host id validation test.
"""

import unittest
from unittest.mock import patch

from flask import Flask

from cobbled.conf.constant import HostCons
from cobbled.util.validate_util import HostChecker


class TestHostIdValidation(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_check_host_id_accepts_uuid(self):
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = HostChecker.check_host_id(valid_uuid)
        self.assertIsNone(result)

    def test_check_host_id_rejects_invalid_string(self):
        result = HostChecker.check_host_id("not-a-uuid")
        self.assertIsNotNone(result)
        self.assertEqual(result.json["msg"], HostCons.CHECK_HOST_ID_TIPS)

    def test_check_host_id_rejects_nonstandard_uuid_format(self):
        result = HostChecker.check_host_id("123e4567e89b12d3a456426614174000")
        self.assertIsNotNone(result)
        self.assertEqual(result.json["msg"], HostCons.CHECK_HOST_ID_TIPS)

    def test_check_host_id_rejects_empty_value(self):
        result = HostChecker.check_host_id("   ")
        self.assertIsNotNone(result)
        self.assertEqual(result.json["msg"], HostCons.CHECK_HOST_ID_TIPS)


class TestHostFieldValidation(unittest.TestCase):
    """Tests for the remaining HostChecker field validators."""

    def setUp(self):
        context = Flask(__name__).app_context()
        context.push()
        self.addCleanup(context.pop)

    def assert_rejected(self, result, message):
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json["msg"], message)

    def test_check_host_name(self):
        self.assertIsNone(HostChecker.check_host_name("valid-host-01"))
        for value in ("", "  ", "-leading", "trailing-", "under_score",
                      "with space", "a" * 64, None):
            with self.subTest(value=value):
                self.assert_rejected(
                    HostChecker.check_host_name(value),
                    HostCons.CHECK_HOST_NAME_TIPS)

    def test_check_bmc_ip(self):
        self.assertIsNone(HostChecker.check_bmc_ip("192.0.2.10"))
        for value in ("", "256.1.1.1", "not-an-ip", "192.0.2",
                      "192.0.2.10.8", None):
            with self.subTest(value=value):
                self.assert_rejected(
                    HostChecker.check_bmc_ip(value),
                    HostCons.CHECK_BMC_IP_TIPS)

    def test_check_bmc_user_name(self):
        self.assertIsNone(HostChecker.check_bmc_user_name("admin"))
        self.assertIsNone(HostChecker.check_bmc_user_name("a" * 128))
        for value in ("", None, "a" * 129):
            with self.subTest(value=value):
                self.assert_rejected(
                    HostChecker.check_bmc_user_name(value),
                    HostCons.CHECK_BMC_USER_NAME_TIPS)

    def test_check_bmc_passwd(self):
        self.assertIsNone(HostChecker.check_bmc_passwd("secret"))
        self.assertIsNone(HostChecker.check_bmc_passwd("a" * 128))
        for value in ("", None, "a" * 129):
            with self.subTest(value=value):
                self.assert_rejected(
                    HostChecker.check_bmc_passwd(value),
                    HostCons.CHECK_BMC_PASSWD_TIPS)

    def test_check_host_status(self):
        for value in (0, 1, 2, 3, 4):
            with self.subTest(value=value):
                self.assertIsNone(HostChecker.check_host_status(value))
        for value in (-1, 5, 6, None, "1"):
            with self.subTest(value=value):
                self.assert_rejected(
                    HostChecker.check_host_status(value),
                    HostCons.CHECK_HOST_STATUS_TIPS)

    def test_check_host_mac(self):
        self.assertIsNone(HostChecker.check_host_mac("AA:BB:CC:DD:EE:FF"))
        for value in ("", "not-a-mac", "AA:BB:CC:DD:EE",
                      "GG:BB:CC:DD:EE:FF", None):
            with self.subTest(value=value):
                self.assert_rejected(
                    HostChecker.check_host_mac(value),
                    HostCons.CHECK_HOST_MAC_TIPS)

    def test_check_page_no_and_page_size(self):
        self.assertIsNone(HostChecker.check_page_no_and_page_size(1, 10))
        self.assertIsNone(HostChecker.check_page_no_and_page_size(1, 100))
        for value in (0, -1, "abc", "0", None):
            with self.subTest(value=value):
                self.assert_rejected(
                    HostChecker.check_page_no_and_page_size(value, 10),
                    HostCons.CHECK_PAGE_NO_TIPS)
        for value in (0, -1, "abc", 101, None):
            with self.subTest(value=value):
                self.assert_rejected(
                    HostChecker.check_page_no_and_page_size(1, value),
                    HostCons.CHECK_PAGE_SIZE_TIPS)

    def test_check_bmc_connection_disabled(self):
        """Test check_bmc_connection returns early when disabled in config."""
        with patch("cobbled.util.validate_util.configuration") as mock_config:
            mock_config.host.get.return_value = 0
            self.assertIsNone(HostChecker.check_bmc_connection({}))

    def test_check_bmc_composite(self):
        """Test check_bmc chains the individual BMC validators."""
        valid = {"bmc_ip": "192.0.2.10", "bmc_user_name": "admin",
                 "bmc_passwd": "encrypted-secret"}
        with patch("cobbled.util.validate_util.configuration") as mock_config:
            mock_config.host.get.return_value = 0
            self.assertIsNone(HostChecker.check_bmc(valid))
        # the first failing field short-circuits the chain
        self.assert_rejected(HostChecker.check_bmc(
            dict(valid, bmc_ip="not-an-ip")), HostCons.CHECK_BMC_IP_TIPS)
        self.assert_rejected(HostChecker.check_bmc(
            dict(valid, bmc_user_name="")),
            HostCons.CHECK_BMC_USER_NAME_TIPS)
        self.assert_rejected(HostChecker.check_bmc(
            dict(valid, bmc_passwd="")),
            HostCons.CHECK_BMC_PASSWD_TIPS)


if __name__ == "__main__":
    unittest.main()

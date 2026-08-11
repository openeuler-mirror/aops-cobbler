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


if __name__ == "__main__":
    unittest.main()

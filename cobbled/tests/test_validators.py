#!/usr/bin/python3
# ******************************************************************************
# Copyright (c) iSoftStone Technologies Co., Ltd. 2023-2024. All rights reserved.
# licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#     http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v2 for more details.
# ******************************************************************************/
"""
Time:
Author:
Description: tests for the standard-library host field validators.
"""

import unittest

from cobbled.util.validate_util import (
    _is_valid_hostname,
    _is_valid_ipv4,
    _is_valid_mac,
)


class TestHostnameValidator(unittest.TestCase):

    def test_accepts_simple_and_dotted_names(self):
        for value in ("host-01", "host-01.example.com", "a" * 63):
            with self.subTest(value=value):
                self.assertTrue(_is_valid_hostname(value))

    def test_rejects_invalid_names(self):
        for value in ("", "  ", "-host", "host-", "under_score",
                      "with space", "host..example", "a" * 64):
            with self.subTest(value=value):
                self.assertFalse(_is_valid_hostname(value))


class TestIPv4Validator(unittest.TestCase):

    def test_accepts_plain_address(self):
        self.assertTrue(_is_valid_ipv4("192.0.2.10"))


if __name__ == "__main__":
    unittest.main()

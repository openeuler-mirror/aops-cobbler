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

import unittest

from cobbled.install_manager.view import get_default_gateway


class TestGetDefaultGateway(unittest.TestCase):

    def test_accepts_integer_mask_from_config(self):
        """Config parses a purely numeric subnet_mask into an int."""
        self.assertEqual(get_default_gateway("10.10.192.213", 24), "10.10.192.254")


if __name__ == "__main__":
    unittest.main()

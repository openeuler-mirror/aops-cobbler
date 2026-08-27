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
"""Unit tests for ResUtil falsy data handling."""

import unittest
from flask import Flask

from cobbled.util.response_util import ResUtil


class TestResUtil(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_success_with_none_omits_data(self):
        response = ResUtil.success("success message")
        self.assertEqual(response.json, {"code": 200, "msg": "success message"})

    def test_success_with_falsy_values_includes_data(self):
        for falsy_value in [[], {}, 0, False, ""]:
            with self.subTest(data=falsy_value):
                response = ResUtil.success("success message", falsy_value)
                self.assertEqual(
                    response.json,
                    {"code": 200, "msg": "success message", "data": falsy_value}
                )

    def test_failed_with_none_omits_data(self):
        response = ResUtil.failed("failed message")
        self.assertEqual(response.json, {"code": 400, "msg": "failed message"})

    def test_failed_with_falsy_values_includes_data(self):
        for falsy_value in [[], {}, 0, False, ""]:
            with self.subTest(data=falsy_value):
                response = ResUtil.failed("failed message", falsy_value)
                self.assertEqual(
                    response.json,
                    {"code": 400, "msg": "failed message", "data": falsy_value}
                )

    def test_success_or_failed_with_falsy_values(self):
        response = ResUtil.success_or_failed(200, "ok", [])
        self.assertEqual(response.json, {"code": 200, "msg": "ok", "data": []})

        response_none = ResUtil.success_or_failed(200, "ok")
        self.assertEqual(response_none.json, {"code": 200, "msg": "ok"})


if __name__ == "__main__":
    unittest.main()

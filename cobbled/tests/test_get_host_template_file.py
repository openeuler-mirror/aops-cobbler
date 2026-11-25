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
Description: unit tests for GetHostTemplateFile resource in host_manager/view.py
"""

import unittest

from flask import Flask
from flask_restful import Api

from cobbled.conf.constant import HostCons, RouteCons
from cobbled.host_manager.view import GetHostTemplateFile


class TestGetHostTemplateFile(unittest.TestCase):
    """Tests for GetHostTemplateFile.get interface."""

    def setUp(self):
        self.app = Flask(__name__)
        self.api = Api(self.app)
        self.api.add_resource(GetHostTemplateFile, RouteCons.GET_HOST_TEMPLATE_FILE)
        self.client = self.app.test_client()

    def test_get_via_client_returns_template_csv(self):
        """测试通过路由 GET /cobbler/getHostTemplateFile 返回 200、正确响应头及 CSV 模板内容."""
        response = self.client.get(RouteCons.GET_HOST_TEMPLATE_FILE)
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "application/octet-stream")
            self.assertEqual(
                response.headers.get("Content-Disposition"),
                "attachment; filename=template.csv",
            )
            self.assertEqual(
                response.get_data(as_text=True),
                HostCons.HOST_TEMPLATE_FILE_CONTENT,
            )
            self.assertEqual(
                response.data,
                HostCons.HOST_TEMPLATE_FILE_CONTENT.encode("utf-8"),
            )
        finally:
            response.close()

    def test_get_direct_call_returns_template_csv(self):
        """测试直接调用 GetHostTemplateFile().get() 返回正确的 Flask 响应对象."""
        with self.app.test_request_context(RouteCons.GET_HOST_TEMPLATE_FILE, method="GET"):
            response = GetHostTemplateFile().get()
            try:
                response.direct_passthrough = False
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "application/octet-stream")
                self.assertEqual(
                    response.headers.get("Content-Disposition"),
                    "attachment; filename=template.csv",
                )
                self.assertEqual(
                    response.get_data(as_text=True),
                    HostCons.HOST_TEMPLATE_FILE_CONTENT,
                )
            finally:
                response.close()

    def test_post_method_not_allowed(self):
        """测试不支持的 POST 请求返回 405."""
        response = self.client.post(RouteCons.GET_HOST_TEMPLATE_FILE)
        try:
            self.assertEqual(response.status_code, 405)
        finally:
            response.close()


if __name__ == "__main__":
    unittest.main()

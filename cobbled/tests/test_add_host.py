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
Description: unit tests for AddHost resource in host_manager/view.py
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask
from flask_restful import Api

from cobbled.conf.constant import HostCons, RouteCons
from cobbled.host_manager import view
from cobbled.host_manager.view import AddHost
from cobbled.util.response_util import ResUtil


class TestAddHost(unittest.TestCase):
    """Tests for AddHost.post interface."""

    def setUp(self):
        self.app = Flask(__name__)
        self.api = Api(self.app)
        self.api.add_resource(AddHost, RouteCons.ADD_HOST)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    @staticmethod
    def _valid_host_payload(**overrides):
        payload = {
            "host_name": "test-host",
            "bmc_ip": "192.0.2.1",
            "bmc_user_name": "admin",
            "bmc_passwd": "password",
            "host_ip": "192.168.1.10",
            "host_mac": "00:11:22:33:44:55",
        }
        payload.update(overrides)
        return payload

    def test_post_param_validation_failed(self):
        """测试单机添加请求参数校验失败分支."""
        payload = self._valid_host_payload(host_name="invalid_hostname_with_underscore")
        with self.app.test_request_context(json=payload), patch.object(view, "HostProxy") as mock_proxy_cls:
            response = AddHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_NAME_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_param_validation_failed_mocked(self):
        """测试单机添加请求参数校验失败（mock校验函数返回失败）."""
        payload = self._valid_host_payload()
        custom_error = ResUtil.failed("Custom parameter validation error")
        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=custom_error), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = AddHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], "Custom parameter validation error")
            mock_proxy_cls.assert_not_called()

    def test_post_bmc_ip_duplicated_rejected(self):
        """测试 BMC IP 重复入库被拦截分支."""
        payload = self._valid_host_payload()
        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_host_by_bmc_ip.return_value = (
            True, [SimpleNamespace(host_id="existing-host-id-001")]
        )

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = AddHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.BMC_IP_DUPLICATED_TIPS)
            mock_proxy.query_host_by_bmc_ip.assert_called_once_with(payload["bmc_ip"])
            mock_proxy.query_host_by_mac.assert_not_called()
            mock_proxy.add_host.assert_not_called()

    def test_post_host_mac_duplicated_rejected(self):
        """测试 MAC 地址重复入库被拦截分支."""
        payload = self._valid_host_payload()
        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_host_by_bmc_ip.return_value = (True, [])
        mock_proxy.query_host_by_mac.return_value = (
            True, [SimpleNamespace(host_id="existing-host-id-002")]
        )

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = AddHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.HOST_MAC_DUPLICATED_TIPS)
            mock_proxy.query_host_by_bmc_ip.assert_called_once_with(payload["bmc_ip"])
            mock_proxy.query_host_by_mac.assert_called_once_with(payload["host_mac"])
            mock_proxy.add_host.assert_not_called()

    def test_post_add_host_db_failed(self):
        """测试 host_proxy.add_host 数据库入库失败分支."""
        payload = self._valid_host_payload()
        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_host_by_bmc_ip.return_value = (True, [])
        mock_proxy.query_host_by_mac.return_value = (True, [])
        mock_proxy.add_host.return_value = False

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = AddHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.ADD_HOST_FAILED_TIPS)
            mock_proxy.query_host_by_bmc_ip.assert_called_once_with(payload["bmc_ip"])
            mock_proxy.query_host_by_mac.assert_called_once_with(payload["host_mac"])
            mock_proxy.add_host.assert_called_once_with(payload)

    def test_post_success(self):
        """测试单机添加成功分支."""
        payload = self._valid_host_payload()
        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_host_by_bmc_ip.return_value = (True, [])
        mock_proxy.query_host_by_mac.return_value = (True, [])
        mock_proxy.add_host.return_value = True

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = AddHost().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.ADD_HOST_SUCCESS_TIPS)
            mock_proxy.query_host_by_bmc_ip.assert_called_once_with(payload["bmc_ip"])
            mock_proxy.query_host_by_mac.assert_called_once_with(payload["host_mac"])
            mock_proxy.add_host.assert_called_once_with(payload)

    def test_post_via_client_success(self):
        """测试通过客户端调用 /cobbler/addHost 成功."""
        payload = self._valid_host_payload()
        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_host_by_bmc_ip.return_value = (True, [])
        mock_proxy.query_host_by_mac.return_value = (True, [])
        mock_proxy.add_host.return_value = True

        with patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = self.client.post(RouteCons.ADD_HOST, json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.ADD_HOST_SUCCESS_TIPS)

    def test_post_via_client_rejects_non_dict_body(self):
        """测试非 JSON 对象请求体被 JsonObjectResource 拦截."""
        response = self.client.post(RouteCons.ADD_HOST, json=[self._valid_host_payload()])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["code"], 400)
        self.assertEqual(response.json["msg"], "Request body must be a JSON object.")

    def test_post_query_bmc_ip_failed(self):
        """测试查询 BMC IP 数据库异常分支."""
        payload = self._valid_host_payload()
        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_host_by_bmc_ip.return_value = (False, [])

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = AddHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_FAILED_TIPS)
            mock_proxy.query_host_by_mac.assert_not_called()
            mock_proxy.add_host.assert_not_called()

    def test_post_query_mac_failed(self):
        """测试查询 MAC 地址数据库异常分支."""
        payload = self._valid_host_payload()
        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_host_by_bmc_ip.return_value = (True, [])
        mock_proxy.query_host_by_mac.return_value = (False, [])

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = AddHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_FAILED_TIPS)
            mock_proxy.add_host.assert_not_called()


if __name__ == "__main__":
    unittest.main()

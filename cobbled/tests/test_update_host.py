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
Description: unit tests for UpdateHost resource in host_manager/view.py
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask
from flask_restful import Api

from cobbled.conf.constant import HostCons, RouteCons
from cobbled.host_manager import view
from cobbled.host_manager.view import UpdateHost
from cobbled.util.response_util import ResUtil
from cobbled.util.validate_util import HostChecker


class TestUpdateHost(unittest.TestCase):
    """Tests for UpdateHost.post interface."""

    def setUp(self):
        self.app = Flask(__name__)
        self.api = Api(self.app)
        self.api.add_resource(UpdateHost, RouteCons.UPDATE_HOST)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    @staticmethod
    def _valid_host_payload(**overrides):
        payload = {
            "host_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": 0,
            "host_name": "test-host",
            "bmc_ip": "192.0.2.1",
            "bmc_user_name": "admin",
            "bmc_passwd": "password",
            "host_ip": "192.168.1.10",
            "host_mac": "00:11:22:33:44:55",
        }
        payload.update(overrides)
        return payload

    def _setup_mock_proxy(self, existing_host=None, query_host_result=True):
        """Helper to create a configured mock HostProxy."""
        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        if existing_host is None and query_host_result:
            existing_host = SimpleNamespace(
                host_id="123e4567-e89b-12d3-a456-426614174000",
                bmc_passwd="password",
            )
        hosts = [existing_host] if existing_host else []
        mock_proxy.query_host_by_host_id.return_value = (query_host_result, hosts)
        mock_proxy.query_host_by_bmc_ip.return_value = (True, [])
        mock_proxy.query_host_by_mac.return_value = (True, [])
        mock_proxy.update_host_info.return_value = True
        return mock_proxy

    # =========================================================================
    # 1. 请求参数校验失败 (host_id、status、bmc 等)
    # =========================================================================

    def test_post_rejects_invalid_host_id(self):
        """测试 host_id 校验失败分支（非 UUID、空字符串、全空格等）."""
        for invalid_id in (None, "", "   ", "not-a-uuid", "123e4567e89b12d3a456426614174000"):
            with self.subTest(host_id=invalid_id):
                payload = self._valid_host_payload(host_id=invalid_id)
                with self.app.test_request_context(json=payload), \
                        patch.object(view, "HostProxy") as mock_proxy_cls:
                    response = UpdateHost().post()
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json["code"], 400)
                    self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_ID_TIPS)
                    mock_proxy_cls.assert_not_called()

    def test_post_rejects_invalid_status(self):
        """测试 status 校验失败分支（非法状态值、字符串类型、布尔类型、None等）."""
        for invalid_status in (None, 5, -1, 100, "0", "1", True, False):
            with self.subTest(status=invalid_status):
                payload = self._valid_host_payload(status=invalid_status)
                with self.app.test_request_context(json=payload), \
                        patch.object(view, "HostProxy") as mock_proxy_cls:
                    response = UpdateHost().post()
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json["code"], 400)
                    self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_STATUS_TIPS)
                    mock_proxy_cls.assert_not_called()

    def test_post_rejects_invalid_host_name(self):
        """测试 host_name 参数校验失败分支."""
        payload = self._valid_host_payload(host_name="invalid_host_name")
        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_NAME_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_rejects_invalid_host_mac(self):
        """测试 host_mac 格式非法校验失败分支."""
        payload = self._valid_host_payload(host_mac="not-a-valid-mac")
        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_MAC_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_rejects_invalid_bmc_ip(self):
        """测试 bmc_ip 非法校验失败分支."""
        payload = self._valid_host_payload(bmc_ip="256.0.0.1")
        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_BMC_IP_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_rejects_invalid_bmc_user_name(self):
        """测试 bmc_user_name 非法校验失败分支."""
        payload = self._valid_host_payload(bmc_user_name="")
        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_BMC_USER_NAME_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_rejects_invalid_bmc_passwd(self):
        """测试 bmc_passwd 非法校验失败分支."""
        payload = self._valid_host_payload(bmc_passwd="")
        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_BMC_PASSWD_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_rejects_bmc_connection_failure(self):
        """测试 BMC 连通性校验失败分支."""
        payload = self._valid_host_payload()
        with self.app.test_request_context(json=payload), \
                patch.object(HostChecker, "bmc_connection_error", return_value=HostCons.CHECK_BMC_CONNECTION_TIPS), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_BMC_CONNECTION_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_param_validation_failed_mocked(self):
        """测试 check_host_params 返回自定义错误分支."""
        payload = self._valid_host_payload()
        custom_error = ResUtil.failed("Custom parameter validation error")
        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=custom_error), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], "Custom parameter validation error")
            mock_proxy_cls.assert_not_called()

    # =========================================================================
    # 2. 待更新主机不存在校验 (query_host_by_host_id 为空或查询失败)
    # =========================================================================

    def test_post_query_host_by_id_failed(self):
        """测试通过 host_id 查询主机时数据库异常分支."""
        payload = self._valid_host_payload()
        mock_proxy = self._setup_mock_proxy(query_host_result=False)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_FAILED_TIPS)
            mock_proxy.query_host_by_host_id.assert_called_once_with(payload["host_id"])
            mock_proxy.query_host_by_bmc_ip.assert_not_called()
            mock_proxy.query_host_by_mac.assert_not_called()
            mock_proxy.update_host_info.assert_not_called()

    def test_post_host_not_exists(self):
        """测试待更新的主机在数据库中不存在分支 (query_host_by_host_id 返回空列表)."""
        payload = self._valid_host_payload()
        mock_proxy = self._setup_mock_proxy(existing_host=None, query_host_result=True)
        mock_proxy.query_host_by_host_id.return_value = (True, [])

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_EXITS_TIPS)
            mock_proxy.query_host_by_host_id.assert_called_once_with(payload["host_id"])
            mock_proxy.query_host_by_bmc_ip.assert_not_called()
            mock_proxy.query_host_by_mac.assert_not_called()
            mock_proxy.update_host_info.assert_not_called()

    # =========================================================================
    # 3. BMC IP / MAC 与其他主机重复校验
    # =========================================================================

    def test_post_bmc_ip_duplicated_rejected(self):
        """测试 BMC IP 与其他主机重复时被拦截分支."""
        payload = self._valid_host_payload()
        mock_proxy = self._setup_mock_proxy()
        # 查询到相同 BMC IP 但属于不同 host_id
        mock_proxy.query_host_by_bmc_ip.return_value = (
            True, [SimpleNamespace(host_id="other-host-id-001")]
        )

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.BMC_IP_DUPLICATED_TIPS)
            mock_proxy.query_host_by_bmc_ip.assert_called_once_with(payload["bmc_ip"])
            mock_proxy.query_host_by_mac.assert_not_called()
            mock_proxy.update_host_info.assert_not_called()

    def test_post_bmc_ip_same_host_allowed(self):
        """测试 BMC IP 与当前待更新主机相同（未更改 BMC IP）时不视为重复."""
        payload = self._valid_host_payload()
        mock_proxy = self._setup_mock_proxy()
        # 查询到相同 BMC IP，但正是当前 host_id
        mock_proxy.query_host_by_bmc_ip.return_value = (
            True, [SimpleNamespace(host_id=payload["host_id"])]
        )

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.UPDATE_HOST_SUCCESS_TIPS)
            mock_proxy.query_host_by_bmc_ip.assert_called_once_with(payload["bmc_ip"])
            mock_proxy.query_host_by_mac.assert_called_once()
            mock_proxy.update_host_info.assert_called_once()

    def test_post_query_bmc_ip_failed(self):
        """测试校验 BMC IP 重复时数据库查询异常分支."""
        payload = self._valid_host_payload()
        mock_proxy = self._setup_mock_proxy()
        mock_proxy.query_host_by_bmc_ip.return_value = (False, [])

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_FAILED_TIPS)
            mock_proxy.query_host_by_mac.assert_not_called()
            mock_proxy.update_host_info.assert_not_called()

    def test_post_host_mac_duplicated_rejected(self):
        """测试 host_mac 与其他主机重复时被拦截分支."""
        payload = self._valid_host_payload()
        mock_proxy = self._setup_mock_proxy()
        mock_proxy.query_host_by_bmc_ip.return_value = (True, [])
        # 查询到相同 MAC 但属于不同 host_id
        mock_proxy.query_host_by_mac.return_value = (
            True, [SimpleNamespace(host_id="other-host-id-002")]
        )

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.HOST_MAC_DUPLICATED_TIPS)
            mock_proxy.query_host_by_mac.assert_called_once_with(payload["host_mac"])
            mock_proxy.update_host_info.assert_not_called()

    def test_post_host_mac_same_host_allowed(self):
        """测试 host_mac 与当前待更新主机相同（未更改 MAC）时不视为重复."""
        payload = self._valid_host_payload()
        mock_proxy = self._setup_mock_proxy()
        mock_proxy.query_host_by_bmc_ip.return_value = (True, [])
        # 查询到相同 MAC，但正是当前 host_id
        mock_proxy.query_host_by_mac.return_value = (
            True, [SimpleNamespace(host_id=payload["host_id"])]
        )

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.UPDATE_HOST_SUCCESS_TIPS)
            mock_proxy.query_host_by_mac.assert_called_once_with(payload["host_mac"])
            mock_proxy.update_host_info.assert_called_once()

    def test_post_query_host_mac_failed(self):
        """测试校验 host_mac 重复时数据库查询异常分支."""
        payload = self._valid_host_payload()
        mock_proxy = self._setup_mock_proxy()
        mock_proxy.query_host_by_bmc_ip.return_value = (True, [])
        mock_proxy.query_host_by_mac.return_value = (False, [])

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_FAILED_TIPS)
            mock_proxy.update_host_info.assert_not_called()

    # =========================================================================
    # 4. 密码有修改时的 AES 加密分支及未修改分支
    # =========================================================================

    def test_post_password_changed_triggers_encryption(self):
        """测试密码修改时触发 AES 加密分支."""
        payload = self._valid_host_payload(bmc_passwd="new_secret_password")
        existing_host = SimpleNamespace(
            host_id=payload["host_id"],
            bmc_passwd="old_password",
        )
        mock_proxy = self._setup_mock_proxy(existing_host=existing_host)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy), \
                patch.object(view.AesUtil, "encrypt", return_value="encrypted_new_pwd") as mock_encrypt:
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.UPDATE_HOST_SUCCESS_TIPS)
            mock_encrypt.assert_called_once_with("new_secret_password")
            updated_data = mock_proxy.update_host_info.call_args[0][0]
            self.assertEqual(updated_data["bmc_passwd"], "encrypted_new_pwd")

    def test_post_password_unchanged_skips_encryption(self):
        """测试密码未修改时不触发 AES 加密分支."""
        payload = self._valid_host_payload(bmc_passwd="same_password")
        existing_host = SimpleNamespace(
            host_id=payload["host_id"],
            bmc_passwd="same_password",
        )
        mock_proxy = self._setup_mock_proxy(existing_host=existing_host)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy), \
                patch.object(view.AesUtil, "encrypt") as mock_encrypt:
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.UPDATE_HOST_SUCCESS_TIPS)
            mock_encrypt.assert_not_called()
            updated_data = mock_proxy.update_host_info.call_args[0][0]
            self.assertEqual(updated_data["bmc_passwd"], "same_password")

    # =========================================================================
    # 5. MAC 地址转小写标准化
    # =========================================================================

    def test_post_mac_normalized_to_lowercase(self):
        """测试大写或混合大小写 MAC 地址被自动转换为小写标准化分支."""
        payload = self._valid_host_payload(host_mac="AA:BB:CC:DD:EE:FF")
        existing_host = SimpleNamespace(
            host_id=payload["host_id"],
            bmc_passwd=payload["bmc_passwd"],
        )
        mock_proxy = self._setup_mock_proxy(existing_host=existing_host)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.UPDATE_HOST_SUCCESS_TIPS)
            updated_data = mock_proxy.update_host_info.call_args[0][0]
            self.assertEqual(updated_data["host_mac"], "aa:bb:cc:dd:ee:ff")

    def test_post_mac_none_safely_handled(self):
        """测试 payload 中无 host_mac 或为 None 时能安全处理."""
        payload = self._valid_host_payload()
        payload["host_mac"] = None
        existing_host = SimpleNamespace(
            host_id=payload["host_id"],
            bmc_passwd=payload["bmc_passwd"],
        )
        mock_proxy = self._setup_mock_proxy(existing_host=existing_host)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "check_host_mac_duplicated", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.UPDATE_HOST_SUCCESS_TIPS)
            updated_data = mock_proxy.update_host_info.call_args[0][0]
            self.assertIsNone(updated_data["host_mac"])

    # =========================================================================
    # 6. 更新成功与更新失败分支
    # =========================================================================

    def test_post_update_host_info_failed(self):
        """测试底层数据库更新返回失败分支."""
        payload = self._valid_host_payload()
        existing_host = SimpleNamespace(
            host_id=payload["host_id"],
            bmc_passwd=payload["bmc_passwd"],
        )
        mock_proxy = self._setup_mock_proxy(existing_host=existing_host)
        mock_proxy.update_host_info.return_value = False

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.UPDATE_HOST_FAILED_TIPS)
            mock_proxy.update_host_info.assert_called_once_with(payload)

    def test_post_update_host_info_success(self):
        """测试更新主机全部成功分支."""
        payload = self._valid_host_payload()
        existing_host = SimpleNamespace(
            host_id=payload["host_id"],
            bmc_passwd=payload["bmc_passwd"],
        )
        mock_proxy = self._setup_mock_proxy(existing_host=existing_host)
        mock_proxy.update_host_info.return_value = True

        with self.app.test_request_context(json=payload), \
                patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = UpdateHost().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.UPDATE_HOST_SUCCESS_TIPS)
            mock_proxy.update_host_info.assert_called_once_with(payload)

    # =========================================================================
    # 7. 客户端端到端调用与请求体验证
    # =========================================================================

    def test_post_via_client_success(self):
        """测试通过客户端路由 /cobbler/updateHost 调用更新成功."""
        payload = self._valid_host_payload()
        existing_host = SimpleNamespace(
            host_id=payload["host_id"],
            bmc_passwd=payload["bmc_passwd"],
        )
        mock_proxy = self._setup_mock_proxy(existing_host=existing_host)

        with patch.object(view, "check_host_params", return_value=None), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = self.client.post(RouteCons.UPDATE_HOST, json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.UPDATE_HOST_SUCCESS_TIPS)

    def test_post_via_client_rejects_non_dict_body(self):
        """测试非 JSON 对象请求体（如列表）被 JsonObjectResource 拦截."""
        response = self.client.post(RouteCons.UPDATE_HOST, json=[self._valid_host_payload()])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["code"], 400)
        self.assertEqual(response.json["msg"], "Request body must be a JSON object.")


if __name__ == "__main__":
    unittest.main()

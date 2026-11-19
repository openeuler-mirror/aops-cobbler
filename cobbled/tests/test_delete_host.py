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
Description: unit tests for DeleteHost resource in host_manager/view.py
"""

import unittest
import uuid
from unittest.mock import MagicMock, patch

from flask import Flask
from flask_restful import Api

from cobbled.conf.constant import HostCons, RouteCons
from cobbled.host_manager import view
from cobbled.host_manager.view import DeleteHost
from cobbled.util.response_util import ResUtil
from cobbled.util.validate_util import HostChecker


class TestDeleteHost(unittest.TestCase):
    """Tests for DeleteHost.post interface."""

    def setUp(self):
        self.app = Flask(__name__)
        self.api = Api(self.app)
        self.api.add_resource(DeleteHost, RouteCons.DELETE_HOST)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    @staticmethod
    def _valid_host_id(index=0):
        return str(uuid.UUID(int=index + 1))

    # =========================================================================
    # 1. 请求体与 host_list 容器校验
    # =========================================================================

    def test_post_via_client_rejects_non_dict_body(self):
        """测试非 JSON 对象请求体（如列表、字符串）被 JsonObjectResource 拦截."""
        response = self.client.post(RouteCons.DELETE_HOST, json=[self._valid_host_id()])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["code"], 400)
        self.assertEqual(response.json["msg"], "Request body must be a JSON object.")

    def test_post_rejects_missing_or_non_list_host_list(self):
        """测试 host_list 为非列表或缺失时被拒绝分支."""
        for invalid_host_list in ({}, {"host": "id"}, "host", 123, None):
            with self.subTest(host_list=invalid_host_list):
                payload = {} if invalid_host_list == {} else {"host_list": invalid_host_list}
                with self.app.test_request_context(json=payload), \
                        patch.object(view, "HostProxy") as mock_proxy_cls:
                    response = DeleteHost().post()
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json["code"], 400)
                    self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_LIST_TIPS)
                    mock_proxy_cls.assert_not_called()

    def test_post_rejects_empty_host_list(self):
        """测试 host_list 为空列表时被拒绝分支."""
        payload = {"host_list": []}
        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = DeleteHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_LIST_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_rejects_host_list_exceeding_max_limit(self):
        """测试 host_list 数量超过 100 时被拒绝分支."""
        payload = {"host_list": [self._valid_host_id(i) for i in range(101)]}
        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = DeleteHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_LIST_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_host_list_validation_mocked_failure(self):
        """测试 mock check_host_list 校验失败时直接返回错误."""
        payload = {"host_list": [self._valid_host_id()]}
        custom_error = ResUtil.failed("Custom host_list error")
        with self.app.test_request_context(json=payload), \
                patch.object(view.HostChecker, "check_host_list", return_value=custom_error), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = DeleteHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], "Custom host_list error")
            mock_proxy_cls.assert_not_called()

    # =========================================================================
    # 2. host_id 元素校验（L219-L222）
    # =========================================================================

    def test_post_rejects_invalid_host_id_single(self):
        """测试 host_list 中单个 host_id 校验失败（非 UUID、空值、非法格式等）."""
        invalid_ids = [
            None,
            "",
            "   ",
            "not-a-uuid",
            "123e4567e89b12d3a456426614174000",
            "123e4567-e89b-12d3-a456-42661417400g",
            12345,
            {"id": "test"},
        ]
        for invalid_id in invalid_ids:
            with self.subTest(invalid_id=invalid_id):
                payload = {"host_list": [invalid_id]}
                with self.app.test_request_context(json=payload), \
                        patch.object(view, "HostProxy") as mock_proxy_cls:
                    response = DeleteHost().post()
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json["code"], 400)
                    self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_ID_TIPS)
                    mock_proxy_cls.assert_not_called()

    def test_post_rejects_invalid_host_id_in_batch(self):
        """测试批量删除中任意一个 host_id 非法时被拦截."""
        valid_id = self._valid_host_id(0)
        invalid_id = "invalid-uuid"
        payload = {"host_list": [valid_id, invalid_id]}

        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = DeleteHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_HOST_ID_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_host_id_validation_mocked_failure(self):
        """测试 mock check_host_id 校验失败时直接返回错误."""
        payload = {"host_list": [self._valid_host_id()]}
        custom_error = ResUtil.failed("Custom host_id error")
        with self.app.test_request_context(json=payload), \
                patch.object(view.HostChecker, "check_host_id", return_value=custom_error), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = DeleteHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], "Custom host_id error")
            mock_proxy_cls.assert_not_called()

    # =========================================================================
    # 3. 删除执行逻辑：失败与成功分支（L224-L229）
    # =========================================================================

    def test_post_delete_host_failed(self):
        """测试调用 HostProxy.delete_host 执行删除失败分支（L224-L226）."""
        host_list = [self._valid_host_id(0), self._valid_host_id(1)]
        payload = {"host_list": host_list}

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.delete_host.return_value = False

        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = DeleteHost().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.DELETE_HOST_FAILED_TIPS)
            mock_proxy.delete_host.assert_called_once_with(host_list)
            mock_proxy.__enter__.assert_called_once()
            mock_proxy.__exit__.assert_called_once()

    def test_post_delete_single_host_success(self):
        """测试单台主机删除成功分支（L228-L229）."""
        host_list = [self._valid_host_id(0)]
        payload = {"host_list": host_list}

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.delete_host.return_value = True

        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = DeleteHost().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.DELETE_HOST_SUCCESS_TIPS)
            mock_proxy.delete_host.assert_called_once_with(host_list)
            mock_proxy.__enter__.assert_called_once()
            mock_proxy.__exit__.assert_called_once()

    def test_post_delete_multiple_hosts_success(self):
        """测试多台主机批量删除成功分支（L228-L229）."""
        host_list = [self._valid_host_id(i) for i in range(5)]
        payload = {"host_list": host_list}

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.delete_host.return_value = True

        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = DeleteHost().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.DELETE_HOST_SUCCESS_TIPS)
            mock_proxy.delete_host.assert_called_once_with(host_list)
            mock_proxy.__enter__.assert_called_once()
            mock_proxy.__exit__.assert_called_once()

    # =========================================================================
    # 4. 客户端路由端到端调用（/cobbler/deleteHost）
    # =========================================================================

    def test_post_via_client_success(self):
        """测试通过客户端路由 /cobbler/deleteHost 调用删除成功."""
        host_list = [self._valid_host_id(0)]
        payload = {"host_list": host_list}

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.delete_host.return_value = True

        with patch.object(view, "HostProxy", return_value=mock_proxy):
            response = self.client.post(RouteCons.DELETE_HOST, json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.DELETE_HOST_SUCCESS_TIPS)
            mock_proxy.delete_host.assert_called_once_with(host_list)

    def test_post_via_client_delete_failed(self):
        """测试通过客户端路由 /cobbler/deleteHost 调用删除失败."""
        host_list = [self._valid_host_id(0)]
        payload = {"host_list": host_list}

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.delete_host.return_value = False

        with patch.object(view, "HostProxy", return_value=mock_proxy):
            response = self.client.post(RouteCons.DELETE_HOST, json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.DELETE_HOST_FAILED_TIPS)
            mock_proxy.delete_host.assert_called_once_with(host_list)


if __name__ == "__main__":
    unittest.main()

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
Description: unit tests for QueryHosts resource in host_manager/view.py
"""

import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from flask_restful import Api
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from cobbled.conf.constant import HostCons, RouteCons
from cobbled.database.host import HostProxy
from cobbled.database.proxy import MysqlProxy
from cobbled.database.table import Base, RawHost
from cobbled.host_manager import view
from cobbled.host_manager.view import QueryHosts
from cobbled.util.response_util import ResUtil
from cobbled.util.validate_util import HostChecker


class TestQueryHosts(unittest.TestCase):
    """Tests for QueryHosts.post interface."""

    def setUp(self):
        self.app = Flask(__name__)
        self.api = Api(self.app)
        self.api.add_resource(QueryHosts, RouteCons.QUERY_HOSTS)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    @staticmethod
    def _valid_query_payload(**overrides):
        payload = {
            "page_no": 1,
            "page_size": 10,
        }
        payload.update(overrides)
        return payload

    # =========================================================================
    # 1. 请求体格式校验 (JsonObjectResource 拦截)
    # =========================================================================

    def test_post_via_client_rejects_non_dict_body(self):
        """测试非 JSON 对象请求体（如列表、字符串、数字）被 JsonObjectResource 拦截."""
        invalid_bodies = (
            [{"page_no": 1, "page_size": 10}],
            "plain string",
            123,
            True,
        )
        for body in invalid_bodies:
            with self.subTest(body=body):
                response = self.client.post(RouteCons.QUERY_HOSTS, json=body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json["code"], 400)
                self.assertEqual(response.json["msg"], "Request body must be a JSON object.")

    def test_post_via_client_preserves_flask_errors_for_invalid_json_requests(self):
        """测试空请求体与非 JSON Content-Type 请求的错误处理."""
        empty_response = self.client.post(
            RouteCons.QUERY_HOSTS, data="", content_type="application/json")
        self.assertEqual(empty_response.status_code, 400)

        content_type_response = self.client.post(
            RouteCons.QUERY_HOSTS, data="{}", content_type="text/plain")
        self.assertEqual(content_type_response.status_code, 415)

    # =========================================================================
    # 2. 分页参数校验 (check_page_no_and_page_size)
    # =========================================================================

    def test_post_rejects_missing_page_no(self):
        """测试缺少 page_no 参数时被校验拦截."""
        payload = {"page_size": 10}
        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = QueryHosts().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_PAGE_NO_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_rejects_invalid_page_no(self):
        """测试 page_no 为非法值（0, 负数, 字符串, 浮点数, None, 布尔值等）时被拦截."""
        invalid_page_nos = (0, -1, "0", "-1", "abc", 1.5, None, True, False, [], {})
        for page_no in invalid_page_nos:
            with self.subTest(page_no=page_no):
                payload = {"page_no": page_no, "page_size": 10}
                with self.app.test_request_context(json=payload), \
                        patch.object(view, "HostProxy") as mock_proxy_cls:
                    response = QueryHosts().post()
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json["code"], 400)
                    self.assertEqual(response.json["msg"], HostCons.CHECK_PAGE_NO_TIPS)
                    mock_proxy_cls.assert_not_called()

    def test_post_rejects_missing_page_size(self):
        """测试缺少 page_size 参数时被校验拦截."""
        payload = {"page_no": 1}
        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = QueryHosts().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_PAGE_SIZE_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_rejects_invalid_page_size(self):
        """测试 page_size 为非法值（0, 负数, 超过100, 非数字, None 等）时被拦截."""
        invalid_page_sizes = (0, -1, "0", "-1", 101, 1000, "101", "abc", 1.5, None, True, False, [], {})
        for page_size in invalid_page_sizes:
            with self.subTest(page_size=page_size):
                payload = {"page_no": 1, "page_size": page_size}
                with self.app.test_request_context(json=payload), \
                        patch.object(view, "HostProxy") as mock_proxy_cls:
                    response = QueryHosts().post()
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json["code"], 400)
                    self.assertEqual(response.json["msg"], HostCons.CHECK_PAGE_SIZE_TIPS)
                    mock_proxy_cls.assert_not_called()

    def test_post_param_validation_failed_mocked(self):
        """测试通过 mock 校验函数返回自定义失败响应."""
        payload = self._valid_query_payload()
        custom_error = ResUtil.failed("Custom page parameter validation error")
        with self.app.test_request_context(json=payload), \
                patch.object(HostChecker, "check_page_no_and_page_size", return_value=custom_error), \
                patch.object(view, "HostProxy") as mock_proxy_cls:
            response = QueryHosts().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], "Custom page parameter validation error")
            mock_proxy_cls.assert_not_called()

    # =========================================================================
    # 3. HostProxy.query_hosts 查询失败分支 (query_result=False, L249-L250)
    # =========================================================================

    def test_post_query_hosts_failed_with_result_data(self):
        """测试 HostProxy.query_hosts 返回失败且包含结果数据分支."""
        payload = self._valid_query_payload()
        failed_result = {"host_infos": [], "total_count": 0, "total_page": 0}

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_hosts.return_value = (False, failed_result)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = QueryHosts().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_FAILED_TIPS)
            self.assertEqual(response.json["data"], failed_result)
            mock_proxy.query_hosts.assert_called_once_with(payload)
            mock_proxy.__enter__.assert_called_once()
            mock_proxy.__exit__.assert_called_once()

    def test_post_query_hosts_failed_without_result_data(self):
        """测试 HostProxy.query_hosts 返回失败且未附带数据分支."""
        payload = self._valid_query_payload()

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_hosts.return_value = (False, None)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = QueryHosts().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_FAILED_TIPS)
            self.assertNotIn("data", response.json)
            mock_proxy.query_hosts.assert_called_once_with(payload)
            mock_proxy.__enter__.assert_called_once()
            mock_proxy.__exit__.assert_called_once()

    def test_post_query_hosts_failed_with_error_message(self):
        """测试 HostProxy.query_hosts 返回失败且附带错误字符串分支."""
        payload = self._valid_query_payload()
        error_detail = "Database connection timed out."

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_hosts.return_value = (False, error_detail)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = QueryHosts().post()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_FAILED_TIPS)
            self.assertEqual(response.json["data"], error_detail)
            mock_proxy.query_hosts.assert_called_once_with(payload)

    # =========================================================================
    # 4. HostProxy.query_hosts 查询成功分支 (query_result=True, L252-L253)
    # =========================================================================

    def test_post_query_hosts_success_empty_result(self):
        """测试 HostProxy.query_hosts 查询成功但无主机记录分支."""
        payload = self._valid_query_payload()
        empty_data = {"host_infos": [], "total_count": 0, "total_page": 0}

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_hosts.return_value = (True, empty_data)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = QueryHosts().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_SUCCESS_TIPS)
            self.assertEqual(response.json["data"], empty_data)
            mock_proxy.query_hosts.assert_called_once_with(payload)
            mock_proxy.__enter__.assert_called_once()
            mock_proxy.__exit__.assert_called_once()

    def test_post_query_hosts_success_with_host_list(self):
        """测试 HostProxy.query_hosts 查询成功且包含主机列表分支."""
        payload = self._valid_query_payload(
            host_name="test-server",
            bmc_ip="192.0.2.1",
            status=1,
        )
        success_data = {
            "host_infos": [
                {
                    "host_id": "123e4567-e89b-12d3-a456-426614174000",
                    "host_name": "test-server",
                    "bmc_ip": "192.0.2.1",
                    "bmc_user_name": "admin",
                    "bmc_passwd": "encrypted_secret",
                    "host_ip": "192.168.1.10",
                    "host_mac": "00:11:22:33:44:55",
                    "status": 1,
                    "created_time": "2026-11-12T00:00:00",
                    "installation_round": None,
                    "cleanup": {
                        "state": "none",
                        "failures": 0,
                        "next_attempt_at": None,
                        "last_error": None,
                    },
                }
            ],
            "total_count": 1,
            "total_page": 1,
        }

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_hosts.return_value = (True, success_data)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = QueryHosts().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_SUCCESS_TIPS)
            self.assertEqual(response.json["data"], success_data)
            mock_proxy.query_hosts.assert_called_once_with(payload)

    def test_post_query_hosts_success_without_result_data(self):
        """测试 HostProxy.query_hosts 查询成功且返回 None 数据分支."""
        payload = self._valid_query_payload()

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_hosts.return_value = (True, None)

        with self.app.test_request_context(json=payload), \
                patch.object(view, "HostProxy", return_value=mock_proxy):
            response = QueryHosts().post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_SUCCESS_TIPS)
            self.assertNotIn("data", response.json)
            mock_proxy.query_hosts.assert_called_once_with(payload)

    # =========================================================================
    # 5. 客户端路由端到端调用 (/cobbler/queryHosts)
    # =========================================================================

    def test_post_via_client_success(self):
        """测试通过客户端路由 /cobbler/queryHosts 成功查询."""
        payload = self._valid_query_payload()
        success_data = {"host_infos": [], "total_count": 0, "total_page": 0}

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_hosts.return_value = (True, success_data)

        with patch.object(view, "HostProxy", return_value=mock_proxy):
            response = self.client.post(RouteCons.QUERY_HOSTS, json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["code"], 200)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_SUCCESS_TIPS)
            self.assertEqual(response.json["data"], success_data)
            mock_proxy.query_hosts.assert_called_once_with(payload)

    def test_post_via_client_failed(self):
        """测试通过客户端路由 /cobbler/queryHosts 查询失败分支."""
        payload = self._valid_query_payload()
        failed_data = {"host_infos": [], "total_count": 0, "total_page": 0}

        mock_proxy = MagicMock()
        mock_proxy.__enter__.return_value = mock_proxy
        mock_proxy.query_hosts.return_value = (False, failed_data)

        with patch.object(view, "HostProxy", return_value=mock_proxy):
            response = self.client.post(RouteCons.QUERY_HOSTS, json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_FAILED_TIPS)
            self.assertEqual(response.json["data"], failed_data)
            mock_proxy.query_hosts.assert_called_once_with(payload)

    def test_post_via_client_invalid_page_no(self):
        """测试通过客户端路由 /cobbler/queryHosts 传递非法 page_no."""
        payload = {"page_no": 0, "page_size": 10}
        with patch.object(view, "HostProxy") as mock_proxy_cls:
            response = self.client.post(RouteCons.QUERY_HOSTS, json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_PAGE_NO_TIPS)
            mock_proxy_cls.assert_not_called()

    def test_post_via_client_invalid_page_size(self):
        """测试通过客户端路由 /cobbler/queryHosts 传递非法 page_size."""
        payload = {"page_no": 1, "page_size": 101}
        with patch.object(view, "HostProxy") as mock_proxy_cls:
            response = self.client.post(RouteCons.QUERY_HOSTS, json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.CHECK_PAGE_SIZE_TIPS)
            mock_proxy_cls.assert_not_called()


class TestQueryHostsIntegration(unittest.TestCase):
    """Integration tests for QueryHosts using an in-memory SQLite database."""

    def setUp(self):
        self.app = Flask(__name__)
        self.api = Api(self.app)
        self.api.add_resource(QueryHosts, RouteCons.QUERY_HOSTS)
        self.client = self.app.test_client()

        self.original_engine = MysqlProxy.engine
        self.engine = create_engine(
            "sqlite://",
            poolclass=QueuePool,
            pool_size=1,
            max_overflow=0)
        MysqlProxy.engine = self.engine
        Base.metadata.create_all(self.engine)

        self.proxy = HostProxy()
        self.addCleanup(self._teardown)

    def _teardown(self):
        self.proxy.close()
        MysqlProxy.engine = self.original_engine
        self.engine.dispose()

    @staticmethod
    def _make_host_data(index=1, **overrides):
        data = {
            "host_id": "123e4567-e89b-12d3-a456-%012d" % index,
            "host_name": "host-%d" % index,
            "bmc_ip": "192.0.2.%d" % index,
            "bmc_user_name": "admin",
            "bmc_passwd": "secret",
            "host_ip": "192.0.2.1%02d" % index,
            "host_mac": "aa:bb:cc:dd:ee:%02x" % index,
            "status": 0,
        }
        data.update(overrides)
        return data

    def test_integration_query_empty_database(self):
        """测试集成数据库：数据库为空时查询主机返回成功及空列表."""
        payload = {"page_no": 1, "page_size": 10}
        response = self.client.post(RouteCons.QUERY_HOSTS, json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["code"], 200)
        self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_SUCCESS_TIPS)
        self.assertEqual(response.json["data"]["host_infos"], [])
        self.assertEqual(response.json["data"]["total_count"], 0)
        self.assertEqual(response.json["data"]["total_page"], 0)

    def test_integration_query_with_hosts_and_pagination(self):
        """测试集成数据库：存在主机数据时的分页查询."""
        for i in range(1, 4):
            self.proxy.insert(RawHost, self._make_host_data(index=i))

        # 第一页，每页 2 条
        response1 = self.client.post(
            RouteCons.QUERY_HOSTS, json={"page_no": 1, "page_size": 2})
        self.assertEqual(response1.status_code, 200)
        data1 = response1.json["data"]
        self.assertEqual(data1["total_count"], 3)
        self.assertEqual(data1["total_page"], 2)
        self.assertEqual(len(data1["host_infos"]), 2)

        # 第二页，每页 2 条
        response2 = self.client.post(
            RouteCons.QUERY_HOSTS, json={"page_no": 2, "page_size": 2})
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json["data"]
        self.assertEqual(data2["total_count"], 3)
        self.assertEqual(data2["total_page"], 2)
        self.assertEqual(len(data2["host_infos"]), 1)

    def test_integration_query_with_filter(self):
        """测试集成数据库：按 bmc_ip 条件过滤查询."""
        self.proxy.insert(RawHost, self._make_host_data(index=1))
        self.proxy.insert(RawHost, self._make_host_data(index=2))

        payload = {"page_no": 1, "page_size": 10, "bmc_ip": "192.0.2.2"}
        response = self.client.post(RouteCons.QUERY_HOSTS, json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json["data"]
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(len(data["host_infos"]), 1)
        self.assertEqual(data["host_infos"][0]["bmc_ip"], "192.0.2.2")

    def test_integration_query_database_error(self):
        """测试集成数据库：数据库查询抛出异常时走入失败分支."""
        mock_result = {"host_infos": [], "total_count": 0, "total_page": 0}
        with patch.object(HostProxy, "query_hosts", return_value=(False, mock_result)):
            payload = {"page_no": 1, "page_size": 10}
            response = self.client.post(RouteCons.QUERY_HOSTS, json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], 400)
            self.assertEqual(response.json["msg"], HostCons.QUERY_HOST_FAILED_TIPS)


if __name__ == "__main__":
    unittest.main()

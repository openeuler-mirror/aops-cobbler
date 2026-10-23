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
Description: unit tests for database/host.py
"""
import json
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from cobbled.database.host import HostProxy
from cobbled.database.proxy import MysqlProxy
from cobbled.database.table import Base, RawHost

HOST_ID = "host-001"
HOST_NAME = "test-host"
BMC_IP = "10.0.0.1"
BMC_USER_NAME = "admin"
HOST_IP = "192.168.1.10"
BMC_PASSWD = "secret"


class TestHostProxyAddHost(unittest.TestCase):
    """Tests for HostProxy.add_host method."""

    @patch("cobbled.database.host.AesUtil")
    @patch("cobbled.database.host.MysqlProxy")
    def test_add_host_encrypts_password(self, mock_proxy, mock_aes):
        """Test add_host encrypts bmc_passwd."""
        mock_aes.encrypt.return_value = "encrypted"
        proxy = HostProxy.__new__(HostProxy)
        proxy.session = MagicMock()
        params = {
            "host_id": HOST_ID,
            "host_name": HOST_NAME,
            "bmc_ip": BMC_IP,
            "bmc_user_name": BMC_USER_NAME,
            "host_ip": HOST_IP,
            "bmc_passwd": BMC_PASSWD,
            "host_mac": "AA:BB:CC:DD:EE:FF",
        }
        with patch.object(proxy, "insert", return_value=True) as insert:
            result = proxy.add_host(params)
            self.assertTrue(result)
            self.assertEqual(params["bmc_passwd"], BMC_PASSWD)
            self.assertEqual(params["host_mac"], "AA:BB:CC:DD:EE:FF")
            inserted = insert.call_args.args[1]
            self.assertEqual(inserted["bmc_passwd"], "encrypted")
            self.assertEqual(inserted["host_mac"], "aa:bb:cc:dd:ee:ff")


class TestHostProxyQueryHosts(unittest.TestCase):
    """Tests for HostProxy.query_hosts method."""

    @patch("cobbled.database.host.RawHost")
    def test_query_hosts_empty(self, mock_host):
        """Test query_hosts returns empty result when no hosts exist."""
        proxy = HostProxy.__new__(HostProxy)
        proxy.session = MagicMock()
        params = {"host_id": None, "host_name": None, "bmc_ip": None, "page_no": 1, "page_size": 10}
        with patch.object(proxy, "count", return_value=(True, 0)):
            query_result, data = proxy.query_hosts(params)
        self.assertTrue(query_result)
        self.assertEqual(data, {"host_infos": [], "total_count": 0, "total_page": 0})


class TestHostProxyCRUD(unittest.TestCase):
    """HostProxy data operations against an in-memory sqlite database."""

    def setUp(self):
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

    def make_host_data(self, index=0, **overrides):
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

    def host_id_of(self, index):
        return "123e4567-e89b-12d3-a456-%012d" % index

    def test_add_host_batch_assigns_missing_host_ids(self):
        """Test add_host_batch fills missing host_id and inserts all rows."""
        first_data = self.make_host_data(index=1)
        first_data.pop("host_id")
        first = RawHost(**first_data)
        second = RawHost(**self.make_host_data(index=2))
        self.assertTrue(self.proxy.add_host_batch([first, second]))
        self.assertIsNotNone(first.host_id)
        self.assertEqual(second.host_id, self.host_id_of(2))
        self.assertEqual(self.proxy.session.query(RawHost).count(), 2)

    def test_query_hosts_returns_matching_hosts(self):
        """Test query_hosts maps rows into the host_infos payload."""
        t1 = datetime(2026, 1, 1, 0, 0, 0)
        t2 = datetime(2026, 1, 2, 0, 0, 0)
        self.proxy.insert(RawHost, self.make_host_data(index=1, status=1,
                                                       update_time=t1))
        self.proxy.insert(RawHost, self.make_host_data(index=2, status=2,
                                                       update_time=t2))
        params = {"host_id": None, "host_name": None, "bmc_ip": None,
                  "page_no": 1, "page_size": 10}
        ok, data = self.proxy.query_hosts(params)
        self.assertTrue(ok)
        self.assertEqual(data["total_count"], 2)
        self.assertEqual(data["total_page"], 1)
        self.assertEqual(len(data["host_infos"]), 2)
        # select() sorts by desc(update_time): newest first
        info = data["host_infos"][0]
        self.assertEqual(info["host_id"], self.host_id_of(2))
        self.assertEqual(info["host_name"], "host-2")
        self.assertEqual(info["bmc_ip"], "192.0.2.2")
        self.assertEqual(info["status"], 2)
        self.assertEqual(info["host_mac"], "aa:bb:cc:dd:ee:02")
        self.assertEqual(info["created_time"], None)

    def test_query_hosts_with_bmc_ip_filter(self):
        self.proxy.insert(RawHost, self.make_host_data(index=1))
        self.proxy.insert(RawHost, self.make_host_data(index=2))
        params = {"host_id": None, "host_name": None,
                  "bmc_ip": "192.0.2.2", "page_no": 1, "page_size": 10}
        ok, data = self.proxy.query_hosts(params)
        self.assertTrue(ok)
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(data["host_infos"][0]["host_id"],
                         self.host_id_of(2))

    def test_query_hosts_page_beyond_last_page(self):
        """Test query_hosts returns an empty page with totals set."""
        self.proxy.insert(RawHost, self.make_host_data(index=1))
        params = {"host_id": None, "host_name": None, "bmc_ip": None,
                  "page_no": 5, "page_size": 10}
        ok, data = self.proxy.query_hosts(params)
        self.assertTrue(ok)
        self.assertEqual(data["host_infos"], [])
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(data["total_page"], 1)

    def test_query_host_by_bmc_ip(self):
        self.proxy.insert(RawHost, self.make_host_data(index=1))
        ok, rows = self.proxy.query_host_by_bmc_ip("192.0.2.1")
        self.assertTrue(ok)
        self.assertEqual([row.host_id for row in rows],
                         [self.host_id_of(1)])

    def test_query_host_by_host_id(self):
        self.proxy.insert(RawHost, self.make_host_data(index=1))
        ok, rows = self.proxy.query_host_by_host_id(self.host_id_of(1))
        self.assertTrue(ok)
        self.assertEqual([row.host_name for row in rows], ["host-1"])

    def test_query_host_by_status(self):
        self.proxy.insert(RawHost, self.make_host_data(index=1, status=1))
        self.proxy.insert(RawHost, self.make_host_data(index=2, status=2))
        ok, rows = self.proxy.query_host_by_status(1)
        self.assertTrue(ok)
        self.assertEqual([row.host_id for row in rows],
                         [self.host_id_of(1)])

    def test_query_host_by_mac_normalizes_case(self):
        """Test query_host_by_mac lowercases the input."""
        self.proxy.insert(RawHost, self.make_host_data(index=1))
        ok, rows = self.proxy.query_host_by_mac("AA:BB:CC:DD:EE:01")
        self.assertTrue(ok)
        self.assertEqual([row.host_id for row in rows],
                         [self.host_id_of(1)])

    def test_query_host_by_host_ip(self):
        self.proxy.insert(RawHost, self.make_host_data(index=1))
        ok, rows = self.proxy.query_host_by_host_ip("192.0.2.101")
        self.assertTrue(ok)
        self.assertEqual([row.host_id for row in rows],
                         [self.host_id_of(1)])

    def test_delete_host(self):
        self.proxy.insert(RawHost, self.make_host_data(index=1))
        self.proxy.insert(RawHost, self.make_host_data(index=2))
        self.assertTrue(self.proxy.delete_host(
            [self.host_id_of(1), self.host_id_of(2)]))
        self.assertEqual(self.proxy.session.query(RawHost).count(), 0)

    def test_update_host_info(self):
        self.proxy.insert(RawHost, self.make_host_data(index=1))
        self.assertTrue(self.proxy.update_host_info(
            {"host_id": self.host_id_of(1), "host_name": "renamed-host"}))
        row = self.proxy.session.query(RawHost).one()
        self.assertEqual(row.host_name, "renamed-host")

    def test_update_host_info_filters_non_writable_fields(self):
        self.proxy.insert(RawHost, self.make_host_data(index=1))
        self.assertTrue(self.proxy.update_host_info({
            "host_id": self.host_id_of(1),
            "host_name": "renamed-host",
            "installation_round": "client-supplied-round",
            "unexpected": "ignored",
        }))
        row = self.proxy.session.query(RawHost).one()
        self.assertEqual(row.host_name, "renamed-host")
        self.assertIsNone(row.installation_round)

    def test_query_hosts_by_status_batch(self):
        t1 = datetime(2026, 2, 1, 0, 0, 0)
        t2 = datetime(2026, 2, 2, 0, 0, 0)
        t3 = datetime(2026, 2, 3, 0, 0, 0)
        self.proxy.insert(RawHost, self.make_host_data(
            index=1, status=3, update_time=t1))
        self.proxy.insert(RawHost, self.make_host_data(
            index=2, status=3, update_time=t2))
        self.proxy.insert(RawHost, self.make_host_data(
            index=3, status=4, update_time=t3))
        ok, hosts = self.proxy.query_hosts_by_status_batch(3, 2)
        self.assertTrue(ok)
        # asc(update_time): only status=3 rows returned
        self.assertEqual([host.host_id for host in hosts],
                         [self.host_id_of(1), self.host_id_of(2)])

    def test_query_hosts_by_status_batch_keyset_cursor(self):
        t1 = datetime(2026, 2, 1, 0, 0, 0)
        t2 = datetime(2026, 2, 2, 0, 0, 0)
        t3 = datetime(2026, 2, 3, 0, 0, 0)
        for index, t in enumerate((t1, t2, t3), start=1):
            self.proxy.insert(RawHost, self.make_host_data(
                index=index, status=3, update_time=t))
        ok, hosts = self.proxy.query_hosts_by_status_batch(
            3, 10, after_update_time=t2, after_host_id=self.host_id_of(2))
        self.assertTrue(ok)
        self.assertEqual([host.host_id for host in hosts],
                         [self.host_id_of(3)])

    def test_query_hosts_by_status_batch_db_error(self):
        self.proxy.session = MagicMock()
        self.proxy.session.query.side_effect = \
            SQLAlchemyError("connection lost")
        ok, hosts = self.proxy.query_hosts_by_status_batch(3, 10)
        self.assertFalse(ok)
        self.assertEqual(hosts, [])

    def test_query_existing_identities_empty_input(self):
        ok, rows = self.proxy.query_existing_identities(set(), set())
        self.assertTrue(ok)
        self.assertEqual(rows, [])

    def test_query_existing_identities(self):
        self.proxy.insert(RawHost, self.make_host_data(index=1))
        self.proxy.insert(RawHost, self.make_host_data(index=2))
        self.proxy.insert(RawHost, self.make_host_data(index=3))
        ok, rows = self.proxy.query_existing_identities(
            {"192.0.2.1"}, {"AA:BB:CC:DD:EE:02"})
        self.assertTrue(ok)
        self.assertEqual(len(rows), 2)

    def test_query_existing_identities_db_error(self):
        self.proxy.session = MagicMock()
        self.proxy.session.query.side_effect = \
            SQLAlchemyError("connection lost")
        ok, rows = self.proxy.query_existing_identities({"192.0.2.1"}, set())
        self.assertFalse(ok)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()

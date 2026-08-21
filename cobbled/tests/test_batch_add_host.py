#!/usr/bin/python3
"""Tests for optimized batch host duplicate checks."""

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from cobbled.conf.constant import HostCons
from cobbled.database.host import HostProxy
from cobbled.database.table import Base, RawHost
from cobbled.host_manager import view


class TestBatchAddHost(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_uses_one_query_and_sets_for_duplicate_checks(self):
        hosts = [
            self._host("new", "192.0.2.1", "00:00:00:00:00:01"),
            self._host("db-mac", "192.0.2.2", "AA:BB:CC:DD:EE:FF"),
            self._host("db-ip", "192.0.2.99", "00:00:00:00:00:03"),
            self._host("batch-mac", "192.0.2.4", "00:00:00:00:00:01"),
        ]
        proxy = MagicMock()
        proxy.query_existing_identities.return_value = (
            True,
            [SimpleNamespace(bmc_ip="192.0.2.99", host_mac="aa:bb:cc:dd:ee:ff")],
        )
        proxy.add_host_batch.return_value = True

        response = self._post(hosts, proxy, encrypt=True)

        proxy.query_existing_identities.assert_called_once_with(
            {host["bmc_ip"] for host in hosts},
            {host["host_mac"] for host in hosts})
        self.assertEqual(len(proxy.add_host_batch.call_args.args[0]), 1)
        results = {item["host_name"]: item for item in response.json["data"]["result"]}
        self.assertEqual(results["new"]["result"], "succeed")
        self.assertEqual(results["db-mac"]["reason"], HostCons.HOST_MAC_DUPLICATED_TIPS)
        self.assertEqual(results["db-ip"]["reason"], HostCons.BMC_IP_DUPLICATED_TIPS)
        self.assertEqual(results["batch-mac"]["reason"], HostCons.HOST_MAC_DUPLICATED_TIPS)

    def test_preserves_mac_precedence_and_failure_order(self):
        hosts = [
            self._host("both-duplicate", "192.0.2.99", "00:00:00:00:00:99"),
            self._host("invalid", "192.0.2.2", "00:00:00:00:00:02"),
        ]
        proxy = MagicMock()
        proxy.query_existing_identities.return_value = (
            True,
            [SimpleNamespace(bmc_ip="192.0.2.99", host_mac="00:00:00:00:00:99")],
        )
        proxy.add_host_batch.return_value = True
        invalid = MagicMock()
        invalid.json = {"msg": HostCons.CHECK_HOST_NAME_TIPS}

        response = self._post(
            hosts,
            proxy,
            check_side_effect=lambda host: invalid if host["host_name"] == "invalid" else None)

        results = response.json["data"]["result"]
        self.assertEqual([item["host_name"] for item in results], ["both-duplicate", "invalid"])
        self.assertEqual(results[0]["reason"], HostCons.HOST_MAC_DUPLICATED_TIPS)

    def test_database_lookup_executes_one_query_and_normalizes_mac(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        session.add(RawHost(
            host_id="123e4567-e89b-12d3-a456-426614174000",
            host_name="existing",
            bmc_ip="192.0.2.10",
            bmc_user_name="admin",
            bmc_passwd="encrypted",
            host_mac="aa:bb:cc:dd:ee:ff"))
        session.commit()

        statements = []
        event.listen(
            engine,
            "before_cursor_execute",
            lambda conn, cursor, statement, parameters, context, executemany:
                statements.append(statement))
        proxy = HostProxy.__new__(HostProxy)
        proxy.session = session

        query_result, hosts = proxy.query_existing_identities(
            {"192.0.2.20"}, {"AA:BB:CC:DD:EE:FF"})

        self.assertTrue(query_result)
        self.assertEqual(len(hosts), 1)
        self.assertEqual(sum(statement.lstrip().upper().startswith("SELECT")
                             for statement in statements), 1)
        session.close()

    def _post(self, hosts, proxy, encrypt=False, check_side_effect=None):
        with self.app.test_request_context(json={"host_list": hosts}), ExitStack() as stack:
            stack.enter_context(patch.object(view, "HostProxy", return_value=proxy))
            stack.enter_context(patch.object(
                view, "check_host_params", return_value=None, side_effect=check_side_effect))
            if encrypt:
                stack.enter_context(patch.object(view.AesUtil, "encrypy", return_value="encrypted"))
            return view.BatchAddHost().post()

    @staticmethod
    def _host(name, bmc_ip, host_mac):
        return {
            "host_name": name,
            "bmc_ip": bmc_ip,
            "bmc_user_name": "admin",
            "bmc_passwd": "password",
            "host_mac": host_mac,
        }


if __name__ == "__main__":
    unittest.main()

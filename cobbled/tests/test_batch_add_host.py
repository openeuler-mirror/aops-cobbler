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

    def test_marks_duplicate_bmc_ip_within_same_batch(self):
        hosts = [
            self._host("first", "192.0.2.10", "00:00:00:00:00:01"),
            self._host("batch-ip", "192.0.2.10", "00:00:00:00:00:02"),
        ]
        proxy = MagicMock()
        proxy.query_existing_identities.return_value = (True, [])
        proxy.add_host_batch.return_value = True

        response = self._post(hosts, proxy, encrypt=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["msg"], HostCons.BATCH_ADD_HOST_SUCCESS_TIPS)
        inserted = proxy.add_host_batch.call_args.args[0]
        self.assertEqual([item.host_name for item in inserted], ["first"])
        results = {item["host_name"]: item for item in response.json["data"]["result"]}
        self.assertEqual(results["first"]["result"], "succeed")
        self.assertEqual(results["first"]["reason"], "")
        self.assertEqual(results["batch-ip"]["result"], "failed")
        self.assertEqual(results["batch-ip"]["reason"], HostCons.BMC_IP_DUPLICATED_TIPS)

    def test_returns_400_in_original_order_when_identity_query_fails(self):
        hosts = [
            self._host("valid-first", "192.0.2.1", "00:00:00:00:00:01"),
            self._host("invalid-middle", "192.0.2.2", "00:00:00:00:00:02"),
            self._host("valid-last", "192.0.2.3", "00:00:00:00:00:03"),
        ]
        proxy = MagicMock()
        proxy.query_existing_identities.return_value = (False, [])
        invalid = MagicMock()
        invalid.json = {"msg": HostCons.CHECK_HOST_NAME_TIPS}

        response = self._post(
            hosts,
            proxy,
            check_side_effect=lambda host: invalid if host["host_name"] == "invalid-middle" else None)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["msg"], HostCons.BATCH_ADD_HOST_FAILED_TIPS)
        proxy.add_host_batch.assert_not_called()
        results = response.json["data"]["result"]
        self.assertEqual(
            [item["host_name"] for item in results],
            ["valid-first", "invalid-middle", "valid-last"])
        self.assertEqual(results[0]["result"], "failed")
        self.assertEqual(results[0]["reason"], HostCons.QUERY_HOST_FAILED_TIPS)
        self.assertEqual(results[1]["result"], "failed")
        self.assertEqual(results[1]["reason"], HostCons.CHECK_HOST_NAME_TIPS)
        self.assertEqual(results[2]["result"], "failed")
        self.assertEqual(results[2]["reason"], HostCons.QUERY_HOST_FAILED_TIPS)

    def test_returns_400_and_marks_checked_hosts_failed_when_add_host_batch_fails(self):
        hosts = [
            self._host("valid", "192.0.2.1", "00:00:00:00:00:01"),
            self._host("invalid", "192.0.2.2", "00:00:00:00:00:02"),
        ]
        proxy = MagicMock()
        proxy.query_existing_identities.return_value = (True, [])
        proxy.add_host_batch.return_value = False
        invalid = MagicMock()
        invalid.json = {"msg": HostCons.CHECK_HOST_NAME_TIPS}

        response = self._post(
            hosts,
            proxy,
            encrypt=True,
            check_side_effect=lambda host: invalid if host["host_name"] == "invalid" else None)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["msg"], HostCons.BATCH_ADD_HOST_FAILED_TIPS)
        proxy.add_host_batch.assert_called_once()
        results = response.json["data"]["result"]
        self.assertEqual([item["host_name"] for item in results], ["invalid", "valid"])
        self.assertEqual(results[0]["result"], "failed")
        self.assertEqual(results[0]["reason"], HostCons.CHECK_HOST_NAME_TIPS)
        self.assertEqual(results[1]["result"], "failed")
        self.assertEqual(results[1]["reason"], HostCons.ADD_HOST_FAILED_TIPS)

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

    def test_ignores_unknown_host_fields(self):
        host = self._host("new", "192.0.2.1", "00:00:00:00:00:01")
        host["unexpected"] = "ignored"
        proxy = MagicMock()
        proxy.query_existing_identities.return_value = (True, [])
        proxy.add_host_batch.return_value = True

        response = self._post([host], proxy, encrypt=True)

        self.assertEqual(response.status_code, 200)
        inserted = proxy.add_host_batch.call_args.args[0]
        self.assertEqual(len(inserted), 1)
        self.assertEqual(inserted[0].host_name, "new")
        self.assertFalse(hasattr(inserted[0], "unexpected"))

    def test_rejects_invalid_optional_host_fields(self):
        cases = (
            ("status", 5, HostCons.CHECK_HOST_STATUS_TIPS),
            ("host_id", "not-a-uuid", HostCons.CHECK_HOST_ID_TIPS),
            ("host_ip", "not-an-ip", HostCons.CHECK_HOST_IP_TIPS),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                host = self._host("new", "192.0.2.1", "00:00:00:00:00:01")
                host[field] = value
                result = view.check_host_params(host)
                self.assertIsNotNone(result)
                self.assertEqual(result.json["msg"], message)

    def test_validates_every_optional_host_field(self):
        valid_host_id = "123e4567-e89b-12d3-a456-426614174000"
        cases = (
            ({"host_id": valid_host_id, "status": 5, "host_ip": "not-an-ip"},
             HostCons.CHECK_HOST_STATUS_TIPS),
            ({"host_id": valid_host_id, "status": 0, "host_ip": "not-an-ip"},
             HostCons.CHECK_HOST_IP_TIPS),
        )
        for fields, message in cases:
            with self.subTest(fields=fields):
                result = view.check_optional_host_fields(fields)
                self.assertIsNotNone(result)
                self.assertEqual(result.json["msg"], message)

    def test_treats_null_optional_host_fields_as_absent(self):
        result = view.check_optional_host_fields(
            {"host_id": None, "status": None, "host_ip": None})
        self.assertIsNone(result)

    def test_treats_empty_string_host_id_and_host_ip_as_absent(self):
        cases = (
            {"host_id": ""},
            {"host_ip": ""},
            {"host_id": "", "host_ip": ""},
            {"host_id": "", "status": 0, "host_ip": ""},
        )
        for fields in cases:
            with self.subTest(fields=fields):
                self.assertIsNone(view.check_optional_host_fields(fields))

        with patch.object(view.HostChecker, "check_host_id") as mock_check_id, \
                patch.object(view.HostChecker, "check_host_ip") as mock_check_ip:
            result = view.check_optional_host_fields({"host_id": "", "host_ip": ""})
            self.assertIsNone(result)
            mock_check_id.assert_not_called()
            mock_check_ip.assert_not_called()

        host = self._host("new", "192.0.2.1", "00:00:00:00:00:01")
        host["host_id"] = ""
        host["host_ip"] = ""
        with patch.object(view.HostChecker, "check_bmc_connection", return_value=None):
            self.assertIsNone(view.check_host_params(host))

    def test_rejects_empty_string_status(self):
        cases = (
            {"status": ""},
            {"host_id": "", "status": "", "host_ip": ""},
        )
        for fields in cases:
            with self.subTest(fields=fields):
                result = view.check_optional_host_fields(fields)
                self.assertIsNotNone(result)
                self.assertEqual(result.status_code, 400)
                self.assertEqual(result.json["msg"], HostCons.CHECK_HOST_STATUS_TIPS)

        host = self._host("new", "192.0.2.1", "00:00:00:00:00:01")
        host["host_id"] = ""
        host["status"] = ""
        host["host_ip"] = ""
        result = view.check_host_params(host)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json["msg"], HostCons.CHECK_HOST_STATUS_TIPS)

    def test_host_name_column_matches_hostname_length_limit(self):
        self.assertEqual(RawHost.__table__.c.host_name.type.length, 63)

    def _post(self, hosts, proxy, encrypt=False, check_side_effect=None):
        proxy.__enter__.return_value = proxy
        with self.app.test_request_context(json={"host_list": hosts}), ExitStack() as stack:
            stack.enter_context(patch.object(view, "HostProxy", return_value=proxy))
            stack.enter_context(patch.object(
                view, "check_host_params", return_value=None, side_effect=check_side_effect))
            if encrypt:
                stack.enter_context(patch.object(view.AesUtil, "encrypt", return_value="encrypted"))
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

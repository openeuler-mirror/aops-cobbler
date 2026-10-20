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
# ******************************************************************************/

import unittest
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from cobbled.database.proxy import MysqlProxy
from cobbled.database.table import Base, RawHost


class TestMysqlProxyLifecycle(unittest.TestCase):
    def setUp(self):
        self.original_engine = MysqlProxy.engine
        self.engine = create_engine(
            "sqlite://",
            poolclass=QueuePool,
            pool_size=1,
            max_overflow=0)
        MysqlProxy.engine = self.engine

    def tearDown(self):
        MysqlProxy.engine = self.original_engine
        self.engine.dispose()

    def test_context_manager_returns_connection_after_success(self):
        with MysqlProxy() as proxy:
            proxy.session.execute(text("select 1")).scalar()
            self.assertEqual(self.engine.pool.checkedout(), 1)

        self.assertEqual(self.engine.pool.checkedout(), 0)

    def test_context_manager_returns_connection_after_exception(self):
        with self.assertRaises(RuntimeError), MysqlProxy() as proxy:
            proxy.session.execute(text("select 1")).scalar()
            raise RuntimeError("database request failed")

        self.assertEqual(self.engine.pool.checkedout(), 0)


class TestMysqlProxyInit(unittest.TestCase):
    """Tests for MysqlProxy session initialization failures."""

    def test_init_raises_when_engine_not_initialized(self):
        """Test __init__ raises when the engine is not initialized."""
        original = MysqlProxy.engine
        MysqlProxy.engine = None
        try:
            with self.assertRaisesRegex(Exception, "Engine is not initialized"):
                MysqlProxy()
        finally:
            MysqlProxy.engine = original

    def test_create_session_failure_raises(self):
        """Test _create_session wraps connection errors."""
        original = MysqlProxy.engine
        try:
            MysqlProxy.engine = create_engine("sqlite://")
            with patch("cobbled.database.proxy.sessionmaker") as mock_sm:
                mock_sm.return_value.configure.side_effect = \
                    SQLAlchemyError("no database")
                with self.assertRaisesRegex(Exception,
                                            "Database connection failed"):
                    MysqlProxy()
        finally:
            MysqlProxy.engine = original


class TestMysqlProxyCRUD(unittest.TestCase):
    """Tests for MysqlProxy data operations against an in-memory sqlite DB."""

    def setUp(self):
        self.original_engine = MysqlProxy.engine
        self.engine = create_engine(
            "sqlite://",
            poolclass=QueuePool,
            pool_size=1,
            max_overflow=0)
        MysqlProxy.engine = self.engine
        Base.metadata.create_all(self.engine)
        self.proxy = MysqlProxy()
        self.addCleanup(self._teardown)

    def _teardown(self):
        self.proxy.close()
        MysqlProxy.engine = self.original_engine
        self.engine.dispose()

    def make_host_data(self, **overrides):
        data = {
            "host_name": "test-host",
            "bmc_ip": "192.0.2.10",
            "bmc_user_name": "admin",
            "bmc_passwd": "secret",
            "host_ip": "192.0.2.100",
            "host_mac": "aa:bb:cc:dd:ee:ff",
            "status": 0,
        }
        data.update(overrides)
        return data

    def test_insert_success(self):
        """Test insert persists a new row."""
        self.assertTrue(self.proxy.insert(RawHost, self.make_host_data()))
        self.assertEqual(self.proxy.session.query(RawHost).count(), 1)

    def test_insert_failure_returns_false_and_rolls_back(self):
        """Test insert returns False and rolls back on constraint violation."""
        data = self.make_host_data()
        del data["host_name"]  # nullable=False -> IntegrityError on commit
        self.assertFalse(self.proxy.insert(RawHost, data))
        self.assertEqual(self.proxy.session.query(RawHost).count(), 0)

    def test_delete_success(self):
        """Test delete removes rows matching the condition."""
        self.proxy.insert(RawHost, self.make_host_data())
        host = self.proxy.session.query(RawHost).one()
        self.assertTrue(self.proxy.delete(
            RawHost, {RawHost.host_id == host.host_id}))
        self.assertEqual(self.proxy.session.query(RawHost).count(), 0)

    def test_delete_failure_returns_false(self):
        """Test delete returns False and rolls back on DB error."""
        self.proxy.session = MagicMock()
        (self.proxy.session.query.return_value.filter.return_value
         .delete.side_effect) = SQLAlchemyError("connection lost")
        self.assertFalse(self.proxy.delete(
            RawHost, {RawHost.host_id == "unknown"}))
        self.proxy.session.rollback.assert_called_once()

    def test_update_success(self):
        """Test update applies the data dict to matching rows."""
        self.proxy.insert(RawHost, self.make_host_data())
        host = self.proxy.session.query(RawHost).one()
        self.assertTrue(self.proxy.update(
            RawHost, {RawHost.host_id == host.host_id},
            {"host_name": "renamed-host"}))
        updated = self.proxy.session.query(RawHost).one()
        self.assertEqual(updated.host_name, "renamed-host")

    def test_update_failure_returns_false(self):
        """Test update returns False and rolls back on DB error."""
        self.proxy.session = MagicMock()
        (self.proxy.session.query.return_value.filter.return_value
         .update.side_effect) = SQLAlchemyError("connection lost")
        self.assertFalse(self.proxy.update(
            RawHost, {RawHost.host_id == "unknown"}, {"host_name": "x"}))
        self.proxy.session.rollback.assert_called_once()

    def test_select_success_with_pagination(self):
        """Test select returns the first page in descending order_by."""
        for i in range(3):
            self.proxy.insert(RawHost, self.make_host_data(
                host_id="host-%03d" % i, host_name="host-%d" % i))
        ok, rows = self.proxy.select(RawHost, set(), page_no=1, page_size=2,
                                     order_by=RawHost.host_id)
        self.assertTrue(ok)
        # select() applies desc(order_by): newest first
        self.assertEqual([row.host_id for row in rows],
                         ["host-002", "host-001"])

    def test_select_default_order_by(self):
        """Test select without order_by falls back to update_time."""
        self.proxy.insert(RawHost, self.make_host_data(host_id="only"))
        ok, rows = self.proxy.select(RawHost, set())
        self.assertTrue(ok)
        self.assertEqual([row.host_id for row in rows], ["only"])

    def test_select_failure_returns_false_and_empty(self):
        """Test select returns (False, []) on DB error."""
        self.proxy.session = MagicMock()
        self.proxy.session.query.side_effect = SQLAlchemyError("connection lost")
        ok, rows = self.proxy.select(RawHost, set())
        self.assertFalse(ok)
        self.assertEqual(rows, [])

    def test_count_success(self):
        """Test count returns (True, total)."""
        self.proxy.insert(RawHost, self.make_host_data())
        self.proxy.insert(RawHost, self.make_host_data(host_id="second"))
        ok, total = self.proxy.count(RawHost.host_id, set())
        self.assertTrue(ok)
        self.assertEqual(total, 2)

    def test_count_failure_returns_false_and_zero(self):
        """Test count returns (False, 0) on DB error."""
        self.proxy.session = MagicMock()
        self.proxy.session.query.side_effect = SQLAlchemyError("connection lost")
        ok, total = self.proxy.count(RawHost.host_id, set())
        self.assertFalse(ok)
        self.assertEqual(total, 0)

    def test_add_batch_assigns_missing_host_ids(self):
        """Test add_batch fills missing host_id with a uuid and inserts."""
        first = RawHost(**self.make_host_data())
        second = RawHost(**self.make_host_data(host_id="fixed-id"))
        self.assertTrue(self.proxy.add_batch([first, second]))
        self.assertIsNotNone(first.host_id)
        self.assertNotEqual(first.host_id, second.host_id)
        self.assertEqual(second.host_id, "fixed-id")
        self.assertEqual(self.proxy.session.query(RawHost).count(), 2)

    def test_add_batch_failure_returns_false(self):
        """Test add_batch returns False and rolls back on DB error."""
        self.proxy.session = MagicMock()
        self.proxy.session.add_all.side_effect = \
            SQLAlchemyError("connection lost")
        self.assertFalse(
            self.proxy.add_batch([RawHost(**self.make_host_data())]))
        self.proxy.session.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()

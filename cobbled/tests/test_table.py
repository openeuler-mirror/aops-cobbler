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
Description: unit tests for database/table.py
"""
import unittest
import warnings
from datetime import datetime

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError, SAWarning
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import DateTime, Integer, String

from cobbled.database.table import Base, InstallationCleanup, MyBase, RawHost


class TestMyBase(unittest.TestCase):
    """Tests for MyBase class."""

    def test_init_sets_table_none(self):
        """Test MyBase.__init__ initializes __table__ to None."""
        base = MyBase()
        self.assertIsNone(base.__table__)
        with self.assertRaises(AttributeError):
            base.to_dict()

    def test_to_dict(self):
        """Test to_dict returns column data as dict."""
        host = RawHost()
        host.host_id = "test-id"
        host.host_name = "test-host"
        d = host.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["host_id"], "test-id")
        self.assertEqual(d["host_name"], "test-host")


class TestRawHost(unittest.TestCase):
    """Tests for RawHost table definition."""

    def test_table_name(self):
        """Test RawHost has correct table name."""
        self.assertEqual(RawHost.__tablename__, "raw_host")

    def test_has_columns(self):
        """Test RawHost has expected columns."""
        self.assertIsNotNone(RawHost.host_id)
        self.assertIsNotNone(RawHost.host_name)
        self.assertIsNotNone(RawHost.bmc_ip)
        self.assertIsNotNone(RawHost.host_mac)

    def test_host_id_default(self):
        """Test RawHost host_id gets a uuid4 value when inserted."""
        # Column default is applied at INSERT time by the ORM, not on
        # instance creation, so verify it through a real insert.
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        host = RawHost()
        host.host_name = "test-host"
        host.bmc_ip = "10.0.0.1"
        host.bmc_user_name = "admin"
        host.bmc_passwd = "secret"
        host.host_mac = "aa:bb:cc:dd:ee:ff"
        with Session(engine) as session:
            session.add(host)
            session.commit()
            # Read the value while the session is open: the instance is
            # detached after the session closes.
            self.assertIsNotNone(host.host_id)
            self.assertIsInstance(host.host_id, str)
            self.assertRegex(host.host_id,
                             r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class TestInstallationCleanup(unittest.TestCase):
    """Tests for InstallationCleanup table definition and constraints."""

    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)

    def _make_cleanup(self, **overrides):
        data = {
            "host_id": "host-001",
            "round_id": "round-001",
            "system_name": "sys-host-001",
        }
        data.update(overrides)
        return InstallationCleanup(**data)

    def test_table_name(self):
        """Test InstallationCleanup has expected table name in metadata and DB."""
        self.assertEqual(InstallationCleanup.__tablename__, "installation_cleanup")
        self.assertEqual(InstallationCleanup.__table__.name, "installation_cleanup")
        self.assertIn("installation_cleanup", Base.metadata.tables)
        self.assertIn("installation_cleanup", inspect(self.engine).get_table_names())

    def test_columns_and_constraints(self):
        """Test InstallationCleanup column types, lengths, constraints, and defaults."""
        expected_columns = (
            ("host_id", String, 36, True, False, None),
            ("round_id", String, 36, False, False, None),
            ("system_name", String, 160, False, False, None),
            ("state", String, 16, False, False, "pending"),
            ("failures", Integer, None, False, False, 0),
            ("next_attempt_at", DateTime, None, False, True, None),
            ("last_error", String, 512, False, True, None),
        )
        columns = InstallationCleanup.__table__.columns
        self.assertEqual([col.name for col in columns], [spec[0] for spec in expected_columns])

        for name, col_type, length, primary_key, nullable, default_val in expected_columns:
            with self.subTest(column=name):
                col = columns[name]
                self.assertIs(type(col.type), col_type)
                self.assertEqual(getattr(col.type, "length", None), length)
                self.assertIs(col.primary_key, primary_key)
                self.assertIs(col.nullable, nullable)
                if default_val is None:
                    self.assertIsNone(col.default)
                else:
                    self.assertIsNotNone(col.default)
                    self.assertEqual(col.default.arg, default_val)
                    self.assertIs(type(col.default.arg), type(default_val))

        self.assertEqual(
            inspect(self.engine).get_pk_constraint("installation_cleanup")["constrained_columns"],
            ["host_id"],
        )

    def test_cleanup_due_index(self):
        """Test cleanup_due composite index in metadata and reflected SQLite schema."""
        indexes = {idx.name: idx for idx in InstallationCleanup.__table__.indexes}
        self.assertEqual(set(indexes.keys()), {"cleanup_due"})
        cleanup_due = indexes["cleanup_due"]
        self.assertEqual([col.name for col in cleanup_due.columns], ["state", "next_attempt_at"])
        self.assertFalse(cleanup_due.unique)

        reflected = {
            idx["name"]: idx for idx in inspect(self.engine).get_indexes("installation_cleanup")
        }
        self.assertIn("cleanup_due", reflected)
        self.assertEqual(reflected["cleanup_due"]["column_names"], ["state", "next_attempt_at"])
        self.assertFalse(reflected["cleanup_due"]["unique"])

    def test_defaults_applied_on_insert(self):
        """Test state='pending', failures=0, and nullable defaults on insert."""
        with Session(self.engine) as session:
            session.add(self._make_cleanup())
            session.commit()

        with Session(self.engine) as session:
            row = session.get(InstallationCleanup, "host-001")
            self.assertIsNotNone(row)
            self.assertEqual(row.host_id, "host-001")
            self.assertEqual(row.round_id, "round-001")
            self.assertEqual(row.system_name, "sys-host-001")
            self.assertEqual(row.state, "pending")
            self.assertEqual(row.failures, 0)
            self.assertIs(type(row.failures), int)
            self.assertIsNone(row.next_attempt_at)
            self.assertIsNone(row.last_error)

    def test_explicit_values_override_defaults(self):
        """Test explicit state, failures, next_attempt_at, and last_error values persist."""
        next_attempt = datetime(2026, 11, 19, 12, 0, 0)
        with Session(self.engine) as session:
            session.add(
                self._make_cleanup(
                    state="failed",
                    failures=3,
                    next_attempt_at=next_attempt,
                    last_error="cobbler timeout",
                )
            )
            session.commit()

        with Session(self.engine) as session:
            row = session.get(InstallationCleanup, "host-001")
            self.assertIsNotNone(row)
            self.assertEqual(row.host_id, "host-001")
            self.assertEqual(row.round_id, "round-001")
            self.assertEqual(row.system_name, "sys-host-001")
            self.assertEqual(row.state, "failed")
            self.assertEqual(row.failures, 3)
            self.assertEqual(row.next_attempt_at, next_attempt)
            self.assertEqual(row.last_error, "cobbler timeout")

    def test_required_columns_not_null_on_insert(self):
        """Test omitting required non-default columns raises IntegrityError on insert."""
        cases = (
            ("host_id", {"round_id": "round-001", "system_name": "sys-1"}),
            ("round_id", {"host_id": "host-missing-round", "system_name": "sys-1"}),
            ("system_name", {"host_id": "host-missing-sys", "round_id": "round-001"}),
        )
        for missing_col, kwargs in cases:
            with self.subTest(missing=missing_col), Session(self.engine) as session:
                session.add(InstallationCleanup(**kwargs))
                try:
                    if missing_col == "host_id":
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", SAWarning)
                            with self.assertRaises(IntegrityError):
                                session.commit()
                    else:
                        with self.assertRaises(IntegrityError):
                            session.commit()
                finally:
                    session.rollback()

        with Session(self.engine) as session:
            self.assertEqual(session.query(InstallationCleanup).count(), 0)

    def test_defaulted_non_null_columns_reject_null_update(self):
        """Test updating state or failures to None violates NOT NULL constraint."""
        with Session(self.engine) as session:
            session.add(self._make_cleanup())
            session.commit()

        for field in ("state", "failures"):
            with self.subTest(field=field), Session(self.engine) as session:
                row = session.get(InstallationCleanup, "host-001")
                setattr(row, field, None)
                try:
                    with self.assertRaises(IntegrityError):
                        session.commit()
                finally:
                    session.rollback()

        with Session(self.engine) as session:
            row = session.get(InstallationCleanup, "host-001")
            self.assertIsNotNone(row)
            self.assertEqual(row.state, "pending")
            self.assertEqual(row.failures, 0)

    def test_primary_key_uniqueness(self):
        """Test inserting duplicate host_id primary key raises IntegrityError."""
        with Session(self.engine) as session:
            session.add(self._make_cleanup(host_id="dup-host", round_id="round-1"))
            session.commit()

        with Session(self.engine) as session:
            session.add(self._make_cleanup(host_id="dup-host", round_id="round-2"))
            try:
                with self.assertRaises(IntegrityError):
                    session.commit()
            finally:
                session.rollback()

        with Session(self.engine) as session:
            self.assertEqual(session.query(InstallationCleanup).count(), 1)
            row = session.get(InstallationCleanup, "dup-host")
            self.assertIsNotNone(row)
            self.assertEqual(row.round_id, "round-1")


if __name__ == "__main__":
    unittest.main()

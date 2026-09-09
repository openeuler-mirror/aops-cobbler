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

from cobbled.database.table import Base, RawHost, MyBase


class TestMyBase(unittest.TestCase):
    """Tests for MyBase class."""

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
        """Test RawHost host_id has default value."""
        import uuid
        host = RawHost()
        self.assertIsNotNone(host.host_id)
        self.assertIsInstance(host.host_id, str)


if __name__ == "__main__":
    unittest.main()

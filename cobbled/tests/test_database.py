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
"""
Description: unit tests for cobbled/database/__init__.py
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.engine import Engine

from cobbled.conf import configuration
from cobbled.database import ENGINE, create_database_engine, make_mysql_engine_url


class TestMakeMysqlEngineUrl(unittest.TestCase):
    """Tests for make_mysql_engine_url."""

    def test_builds_standard_mysql_url(self):
        """Test URL assembly with standard host, port, format, and database name."""
        config = SimpleNamespace(
            mysql={
                "IP": "127.0.0.1",
                "PORT": 3306,
                "DATABASE_NAME": "aops",
                "ENGINE_FORMAT": "mysql+pymysql://root:@%s:%s/%s",
            }
        )

        url = make_mysql_engine_url(config)

        self.assertEqual(url, "mysql+pymysql://root:@127.0.0.1:3306/aops")

    def test_builds_url_with_custom_credentials_port_and_query_params(self):
        """Test URL assembly preserves custom format string and parameter order."""
        config = SimpleNamespace(
            mysql={
                "IP": "db.example.local",
                "PORT": 13306,
                "DATABASE_NAME": "cobbler_db",
                "ENGINE_FORMAT": "mysql+pymysql://admin:secret@%s:%s/%s?charset=utf8mb4",
            }
        )

        url = make_mysql_engine_url(config)

        self.assertEqual(
            url,
            "mysql+pymysql://admin:secret@db.example.local:13306/cobbler_db?charset=utf8mb4",
        )

    def test_missing_engine_format_raises_type_error(self):
        """Test missing ENGINE_FORMAT raises TypeError during string formatting."""
        config = SimpleNamespace(
            mysql={
                "IP": "127.0.0.1",
                "PORT": 3306,
                "DATABASE_NAME": "aops",
            }
        )

        with self.assertRaises(TypeError):
            make_mysql_engine_url(config)


class TestCreateDatabaseEngine(unittest.TestCase):
    """Tests for create_database_engine and module-level ENGINE."""

    @patch("cobbled.database.create_engine")
    def test_passes_url_pool_params_and_pool_pre_ping(self, mock_create_engine):
        """Test create_database_engine forwards pool_size, pool_recycle, and pool_pre_ping=True."""
        expected_engine = MagicMock(name="engine")
        mock_create_engine.return_value = expected_engine
        url = "mysql+pymysql://root:@127.0.0.1:3306/aops"

        engine = create_database_engine(url, pool_size=50, pool_recycle=3600)

        self.assertIs(engine, expected_engine)
        mock_create_engine.assert_called_once_with(
            url,
            pool_size=50,
            pool_recycle=3600,
            pool_pre_ping=True,
        )

    def test_module_engine_configured_from_configuration(self):
        """Test module-level ENGINE is created with pool_pre_ping=True and configured pool values."""
        self.assertIsInstance(ENGINE, Engine)
        self.assertTrue(ENGINE.pool._pre_ping)
        self.assertEqual(ENGINE.pool.size(), configuration.mysql.get("POOL_SIZE"))
        self.assertEqual(ENGINE.pool._recycle, configuration.mysql.get("POOL_RECYCLE"))


if __name__ == "__main__":
    unittest.main()

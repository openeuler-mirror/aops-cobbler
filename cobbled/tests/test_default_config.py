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
Description: unit tests for conf/default_config.py
"""
import importlib.util
import ipaddress
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from cobbled.conf import Config, default_config


EXPECTED_SCHEMA = {
    "cobbler_client": {
        "IP": str,
        "PORT": int,
    },
    "cobbler_server": {
        "SERVER": str,
        "USER": str,
        "PASSWD": str,
    },
    "uwsgi": {
        "WSGI-FILE": str,
        "DAEMONIZE": str,
        "HTTP-TIMEOUT": int,
        "HARAKIRI": int,
        "PROCESSES": int,
        "GEVENT": int,
    },
    "log": {
        "LOG_DIR": str,
        "LOG_LEVEL": str,
        "MAX_BYTES": int,
        "BACKUP_COUNT": int,
    },
    "iso": {
        "UPLOAD_DIR": str,
        "MAX_CONTENT_LENGTH": int,
        "ARCH": str,
    },
    "ks": {
        "HTTP_DIR": str,
    },
    "mysql": {
        "IP": str,
        "PORT": int,
        "DATABASE_NAME": str,
        "ENGINE_FORMAT": str,
        "POOL_SIZE": int,
        "POOL_RECYCLE": int,
    },
    "host": {
        "CHECK_BMC_CONNECTION": int,
        "SCHEDULER_INTERVAL_TIME": int,
        "OS_INSTALLED_TIME": int,
        "RPM_SEARCH_TIMEOUT": int,
        "OS_INSTALL_LOG_DIR": str,
        "OS_START_IP": str,
        "OS_END_IP": str,
        "SUBNET_MASK": str,
        "GATEWAY": str,
    },
    "script": {
        "SCRIPT_DIR": str,
        "MAX_CONTENT_LENGTH": int,
    },
}


def _load_fresh_default_config():
    """Load default_config.py directly so tests inspect unmutated defaults."""
    module_path = Path(default_config.__file__).resolve()
    spec = importlib.util.spec_from_file_location("_fresh_default_config", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load default_config spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDefaultConfig(unittest.TestCase):
    """Tests for default configuration structure, types, and valid ranges."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = _load_fresh_default_config()

    def _assert_valid_ipv4(self, value):
        parsed = ipaddress.IPv4Address(value)
        self.assertEqual(str(parsed), value)
        return parsed

    def _assert_valid_port(self, value):
        self.assertIs(type(value), int)
        self.assertGreaterEqual(value, 1)
        self.assertLessEqual(value, 65535)

    def _assert_abs_path(self, value):
        self.assertIs(type(value), str)
        self.assertTrue(value)
        self.assertTrue(os.path.isabs(value))

    def test_expected_sections_and_keys_structure(self):
        """Test default_config defines exact expected sections and uppercase keys."""
        actual_sections = {
            name
            for name, value in vars(self.cfg).items()
            if not name.startswith("_") and isinstance(value, dict)
        }
        self.assertEqual(actual_sections, set(EXPECTED_SCHEMA.keys()))

        for section_name, expected_keys in EXPECTED_SCHEMA.items():
            with self.subTest(section=section_name):
                fresh_section = getattr(self.cfg, section_name)
                self.assertIsInstance(fresh_section, dict)
                self.assertEqual(set(fresh_section.keys()), set(expected_keys.keys()))
                for key in fresh_section:
                    self.assertIs(type(key), str)
                    self.assertTrue(key)
                    self.assertEqual(key, key.upper())

                imported_section = getattr(default_config, section_name, None)
                self.assertIsInstance(imported_section, dict)
                self.assertTrue(set(expected_keys.keys()).issubset(imported_section.keys()))

    def test_option_exact_types(self):
        """Test every default option uses its exact declared Python type."""
        for section_name, expected_keys in EXPECTED_SCHEMA.items():
            section = getattr(self.cfg, section_name)
            for key, expected_type in expected_keys.items():
                with self.subTest(section=section_name, key=key):
                    self.assertIs(type(section[key]), expected_type)

    def test_cobbler_client_defaults_and_range(self):
        """Test cobbler_client IP and TCP port defaults."""
        client = self.cfg.cobbler_client
        self._assert_valid_ipv4(client["IP"])
        self.assertEqual(client["IP"], "127.0.0.1")
        self._assert_valid_port(client["PORT"])
        self.assertEqual(client["PORT"], 8888)

    def test_cobbler_server_defaults_and_format(self):
        """Test cobbler_server URL, USER, and PASSWD defaults."""
        server = self.cfg.cobbler_server
        parsed = urlparse(server["SERVER"])
        self.assertIn(parsed.scheme, ("http", "https"))
        self.assertTrue(parsed.netloc)
        self.assertEqual(parsed.path, "/cobbler_api")
        self.assertEqual(server["SERVER"], "http://127.0.0.1/cobbler_api")

        self.assertEqual(server["USER"], "cobbler")
        self.assertTrue(server["USER"].strip())
        self.assertEqual(server["PASSWD"], "cobbler")
        self.assertTrue(server["PASSWD"].strip())

    def test_uwsgi_defaults_and_ranges(self):
        """Test uwsgi file, path, timeout, and concurrency defaults."""
        uwsgi = self.cfg.uwsgi
        self.assertEqual(uwsgi["WSGI-FILE"], "manage.py")
        self.assertTrue(uwsgi["WSGI-FILE"].endswith(".py"))
        self._assert_abs_path(uwsgi["DAEMONIZE"])
        self.assertEqual(uwsgi["DAEMONIZE"], "/var/log/aops/uwsgi/aops-cobbler.log")

        self.assertGreater(uwsgi["HTTP-TIMEOUT"], 0)
        self.assertEqual(uwsgi["HTTP-TIMEOUT"], 600)
        self.assertGreater(uwsgi["HARAKIRI"], 0)
        self.assertEqual(uwsgi["HARAKIRI"], 600)
        self.assertGreaterEqual(uwsgi["PROCESSES"], 1)
        self.assertEqual(uwsgi["PROCESSES"], 2)
        self.assertGreaterEqual(uwsgi["GEVENT"], 1)
        self.assertEqual(uwsgi["GEVENT"], 100)

    def test_log_defaults_and_ranges(self):
        """Test log directory, level, rotation size, and backup count defaults."""
        log = self.cfg.log
        self._assert_abs_path(log["LOG_DIR"])
        self.assertEqual(log["LOG_DIR"], os.path.join("/", "var", "log", "aops", "cobbler"))

        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        self.assertIn(log["LOG_LEVEL"], valid_levels)
        self.assertIsInstance(logging.getLevelName(log["LOG_LEVEL"]), int)
        self.assertEqual(log["LOG_LEVEL"], "INFO")

        self.assertGreater(log["MAX_BYTES"], 0)
        self.assertEqual(log["MAX_BYTES"], 31457280)
        self.assertGreater(log["BACKUP_COUNT"], 0)
        self.assertEqual(log["BACKUP_COUNT"], 30)

    def test_iso_defaults_and_ranges(self):
        """Test iso upload path, content size limit, and architecture list."""
        iso = self.cfg.iso
        self._assert_abs_path(iso["UPLOAD_DIR"])
        self.assertEqual(iso["UPLOAD_DIR"], "/opt/aops/cobbler/iso/upload")
        self.assertGreater(iso["MAX_CONTENT_LENGTH"], 0)
        self.assertEqual(iso["MAX_CONTENT_LENGTH"], 5 * 1024 * 1024 * 1024)

        arches = iso["ARCH"].split(",")
        self.assertEqual(arches, ["x86_64", "aarch64"])
        self.assertTrue(all(arch and arch == arch.strip() for arch in arches))
        self.assertEqual(len(arches), len(set(arches)))

    def test_ks_defaults_and_format(self):
        """Test kickstart HTTP directory default."""
        ks = self.cfg.ks
        self._assert_abs_path(ks["HTTP_DIR"])
        self.assertEqual(ks["HTTP_DIR"], "/var/www/html/")

    def test_mysql_defaults_and_ranges(self):
        """Test mysql connection, engine URL format, and pool defaults."""
        mysql = self.cfg.mysql
        self._assert_valid_ipv4(mysql["IP"])
        self.assertEqual(mysql["IP"], "10.10.192.213")
        self._assert_valid_port(mysql["PORT"])
        self.assertEqual(mysql["PORT"], 3306)

        self.assertEqual(mysql["DATABASE_NAME"], "aops")
        self.assertTrue(mysql["DATABASE_NAME"])
        self.assertEqual(mysql["DATABASE_NAME"], mysql["DATABASE_NAME"].strip())
        self.assertFalse(any(ch.isspace() for ch in mysql["DATABASE_NAME"]))

        self.assertTrue(mysql["ENGINE_FORMAT"].startswith("mysql+"))
        formatted_url = mysql["ENGINE_FORMAT"] % (
            mysql["IP"],
            mysql["PORT"],
            mysql["DATABASE_NAME"],
        )
        self.assertEqual(formatted_url, "mysql+pymysql://root:@10.10.192.213:3306/aops")

        self.assertGreater(mysql["POOL_SIZE"], 0)
        self.assertEqual(mysql["POOL_SIZE"], 100)
        self.assertGreater(mysql["POOL_RECYCLE"], 0)
        self.assertEqual(mysql["POOL_RECYCLE"], 7200)

    def test_host_defaults_and_ranges(self):
        """Test host check, scheduler, timeout, IP pool, mask, and gateway defaults."""
        host = self.cfg.host
        self.assertIn(host["CHECK_BMC_CONNECTION"], {0, 1})
        self.assertEqual(host["CHECK_BMC_CONNECTION"], 1)

        self.assertGreaterEqual(host["SCHEDULER_INTERVAL_TIME"], 1)
        self.assertLessEqual(host["SCHEDULER_INTERVAL_TIME"], 59)
        self.assertEqual(host["SCHEDULER_INTERVAL_TIME"], 5)

        self.assertGreater(host["OS_INSTALLED_TIME"], 0)
        self.assertEqual(host["OS_INSTALLED_TIME"], 30)

        self.assertGreaterEqual(host["RPM_SEARCH_TIMEOUT"], 1)
        self.assertLessEqual(host["RPM_SEARCH_TIMEOUT"], 30)
        self.assertEqual(host["RPM_SEARCH_TIMEOUT"], 30)

        self._assert_abs_path(host["OS_INSTALL_LOG_DIR"])
        self.assertEqual(host["OS_INSTALL_LOG_DIR"], "/var/log/osinstall/")

        start_ip = self._assert_valid_ipv4(host["OS_START_IP"])
        end_ip = self._assert_valid_ipv4(host["OS_END_IP"])
        self.assertEqual(host["OS_START_IP"], "10.10.192.210")
        self.assertEqual(host["OS_END_IP"], "10.10.192.211")
        self.assertLessEqual(start_ip, end_ip)

        self.assertTrue(host["SUBNET_MASK"].isdigit())
        prefix_len = int(host["SUBNET_MASK"])
        self.assertGreaterEqual(prefix_len, 1)
        self.assertLessEqual(prefix_len, 32)
        self.assertEqual(host["SUBNET_MASK"], "24")

        self.assertEqual(host["GATEWAY"], "")

    def test_script_defaults_and_ranges(self):
        """Test script upload directory and size limit defaults."""
        script = self.cfg.script
        self._assert_abs_path(script["SCRIPT_DIR"])
        self.assertEqual(script["SCRIPT_DIR"], "/opt/aops/cobbler/script/upload")
        self.assertGreater(script["MAX_CONTENT_LENGTH"], 0)
        self.assertEqual(script["MAX_CONTENT_LENGTH"], 10240)

    def test_config_loads_default_config_when_ini_missing(self):
        """Test Config preserves all sections and passes runtime timeout bounds."""
        with tempfile.TemporaryDirectory() as directory:
            missing_file = str(Path(directory) / "missing.ini")
            loaded = Config(missing_file, default=self.cfg)
            for section_name in EXPECTED_SCHEMA:
                with self.subTest(section=section_name):
                    self.assertEqual(getattr(loaded, section_name), getattr(self.cfg, section_name))

            ini_file = Path(directory) / "timeout.ini"
            default_timeout = self.cfg.host["RPM_SEARCH_TIMEOUT"]
            ini_file.write_text(f"[host]\nrpm_search_timeout={default_timeout}\n", encoding="utf-8")
            fresh_defaults = _load_fresh_default_config()
            fresh_defaults.host["RPM_SEARCH_TIMEOUT"] = 1 if default_timeout != 1 else 2
            with patch("cobbled.conf.default_config", fresh_defaults):
                parsed = Config(str(ini_file), default=fresh_defaults)
            self.assertIs(type(parsed.host["RPM_SEARCH_TIMEOUT"]), int)
            self.assertEqual(parsed.host["RPM_SEARCH_TIMEOUT"], default_timeout)


if __name__ == "__main__":
    unittest.main()

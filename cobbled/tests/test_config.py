"""Regression tests for configuration value types."""

import copy
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

from cobbled.conf import Config, default_config


class TestConfig(unittest.TestCase):
    def load_config(self, content, default=None):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "test.ini"
            config_file.write_text(content, encoding="utf-8")
            return Config(config_file, default)

    def test_credentials_remain_strings(self):
        for value in ("001234", "true", "false", "TRUE", "2*3"):
            for key in ("user", "passwd"):
                with self.subTest(value=value, key=key):
                    config = self.load_config(f"[cobbler_server]\n{key}={value}\n")
                    actual = config.cobbler_server[key.upper()]
                    self.assertIsInstance(actual, str)
                    self.assertEqual(actual, value)

    def test_declared_integer_options_are_converted(self):
        for section, defaults in vars(default_config).items():
            if not isinstance(defaults, dict):
                continue
            for key, value in defaults.items():
                if type(value) is not int:
                    continue
                with self.subTest(section=section, key=key):
                    config = self.load_config(f"[{section}]\n{key.lower()}=0012\n")
                    actual = getattr(config, section)[key]
                    self.assertIs(type(actual), int)
                    self.assertEqual(actual, 12)

    def test_upload_size_multiplication_is_supported(self):
        config = self.load_config(
            "[iso]\nmax_content_length=5 * 1024 * 1024 * 1024\n"
            "[script]\nmax_content_length=10 * 1024\n"
        )
        self.assertEqual(config.iso["MAX_CONTENT_LENGTH"], 5 * 1024 ** 3)
        self.assertEqual(config.script["MAX_CONTENT_LENGTH"], 10240)

    def test_rpm_search_timeout_is_bounded(self):
        for value in (0, -1, 31):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.load_config(f"[host]\nrpm_search_timeout={value}\n")

    def test_other_values_remain_strings(self):
        config = self.load_config(
            "[mysql]\ndatabase_name=001234\n"
            "[host]\nsubnet_mask=24\n"
            "[custom]\nnumber=001234\nflag=false\nexpression=2*3\n"
        )
        self.assertEqual(config.mysql["DATABASE_NAME"], "001234")
        self.assertEqual(config.host["SUBNET_MASK"], "24")
        self.assertEqual(config.custom, {
            "NUMBER": "001234", "FLAG": "false", "EXPRESSION": "2*3"
        })

    def test_string_overrides_merge_with_defaults(self):
        default = ModuleType("test_defaults")
        default.cobbler_server = copy.deepcopy(default_config.cobbler_server)
        config = self.load_config("[cobbler_server]\npasswd=001234\n", default)
        self.assertEqual(config.cobbler_server["PASSWD"], "001234")
        self.assertEqual(config.cobbler_server["USER"], default_config.cobbler_server["USER"])


if __name__ == "__main__":
    unittest.main()

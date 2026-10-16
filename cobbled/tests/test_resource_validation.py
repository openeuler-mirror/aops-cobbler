"""Regression tests for ISO, kickstart and script field validation."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from cobbled.conf.constant import HostCons, ISOCons, KsCons, ScriptCons
from cobbled.util.validate_util import (
    ISOChecker, InstallChecker, KsChecker, ScriptChecker)


class TestResourceValidation(unittest.TestCase):

    def setUp(self):
        context = Flask(__name__).app_context()
        context.push()
        self.addCleanup(context.pop)
        self.name_checkers = (
            (ISOChecker.check_iso_name, ISOCons.CHECK_ISO_NAME_TIPS),
            (KsChecker.check_ks_name, KsCons.CHECK_KS_NAME_TIPS),
            (ScriptChecker.check_script_name, ScriptCons.CHECK_SCRIPT_NAME_TIPS),
        )

    def assert_rejected(self, checker, value, message):
        response = checker(value)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"code": 400, "msg": message})

    def test_names_reject_non_string_values(self):
        for checker, message in self.name_checkers:
            for value in (None, 123, 0, 1.5, True, False, [], ["name"], {}, {"name": "demo"}, b"name"):
                with self.subTest(checker=checker.__name__, value=value):
                    self.assert_rejected(checker, value, message)

    def test_names_reject_invalid_strings(self):
        for checker, message in self.name_checkers:
            for value in ("", " ", "name\n", "name\r\n", "../name", "name.ext", "a" * 129):
                with self.subTest(checker=checker.__name__, value=value):
                    self.assert_rejected(checker, value, message)

    def test_names_accept_allowed_characters_and_maximum_length(self):
        for checker, _ in self.name_checkers:
            for value in ("a", "Demo_01-test", "a" * 128):
                with self.subTest(checker=checker.__name__, value=value):
                    self.assertIsNone(checker(value))

    def test_iso_names_still_reject_architecture_markers(self):
        for value in ("demo-x86_64", "demo_x86_64", "demo-aarch64", "demo_aarch64"):
            with self.subTest(value=value):
                self.assert_rejected(ISOChecker.check_iso_name, value, ISOCons.CHECK_ISO_NAME_TIPS)

    def test_kickstart_content_rejects_non_strings_and_empty_string(self):
        for value in (None, "", 123, 0, 1.5, True, False, [], ["content"], {}, {"content": "text"}, b"text"):
            with self.subTest(value=value):
                self.assert_rejected(KsChecker.check_ks_content, value, KsCons.CHECK_KS_CONTENT_TIPS)

    def test_kickstart_content_accepts_nonempty_multiline_text(self):
        self.assertIsNone(KsChecker.check_ks_content("lang en_US.UTF-8\n%packages\n@core\n%end\n"))


class TestResourceExtraValidation(unittest.TestCase):
    """Tests for ISO arch/suffix, script file and host list validation."""

    def setUp(self):
        context = Flask(__name__).app_context()
        context.push()
        self.addCleanup(context.pop)

    def assert_rejected(self, response, message):
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"code": 400, "msg": message})

    @patch("cobbled.util.validate_util.configuration")
    def test_check_iso_arch(self, mock_config):
        mock_config.iso.get.return_value = "x86_64,aarch64"
        self.assertIsNone(ISOChecker.check_iso_arch("x86_64"))
        self.assertIsNone(ISOChecker.check_iso_arch("aarch64"))
        for value in ("riscv64", "", None):
            with self.subTest(value=value):
                self.assert_rejected(ISOChecker.check_iso_arch(value),
                                     ISOCons.CHECK_ISO_ARCH_TIPS)

    def test_check_iso_suffix(self):
        self.assertIsNone(ISOChecker.check_iso_suffix("demo.iso"))
        for value in ("demo.txt", "demo", "demo.ISO"):
            with self.subTest(value=value):
                self.assert_rejected(ISOChecker.check_iso_suffix(value),
                                     ISOCons.CHECK_ISO_SUFFIX_TIPS)

    def test_check_script_file(self):
        self.assertIsNone(ScriptChecker.check_script_file(
            SimpleNamespace(filename="demo.sh")))
        self.assert_rejected(ScriptChecker.check_script_file(None),
                             ScriptCons.CHECK_SCRIPT_FILE_TIPS)
        self.assert_rejected(ScriptChecker.check_script_file(
            SimpleNamespace(filename="")),
            ScriptCons.CHECK_SCRIPT_FILE_TIPS)
        self.assert_rejected(ScriptChecker.check_script_file(
            SimpleNamespace(filename="demo.txt")),
            ScriptCons.CHECK_SCRIPT_SUFFIX_TIPS)
        self.assert_rejected(ScriptChecker.check_script_file(
            SimpleNamespace(filename="demo")),
            ScriptCons.CHECK_SCRIPT_SUFFIX_TIPS)

    def test_check_host_list_rejects_invalid_bmc_ip(self):
        valid_host = {"bmc_ip": "192.0.2.10"}
        self.assertIsNone(InstallChecker.check_host_list([valid_host]))
        bad_list = [dict(valid_host), dict(valid_host, bmc_ip="not-an-ip")]
        self.assert_rejected(
            InstallChecker.check_host_list(bad_list),
            HostCons.CHECK_BMC_IP_TIPS)


if __name__ == "__main__":
    unittest.main()

"""Regression tests for ISO, kickstart and script field validation."""

import unittest

from flask import Flask

from cobbled.conf.constant import ISOCons, KsCons, ScriptCons
from cobbled.util.validate_util import ISOChecker, KsChecker, ScriptChecker


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


if __name__ == "__main__":
    unittest.main()

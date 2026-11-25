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
Description: unit tests for manage.py
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask
from flask_restful import Resource

from cobbled.conf import configuration
from cobbled.util.file_util import FileUtil

with patch.object(FileUtil, "makedirs"):
    from cobbled.manage import init_application, _register_blue_point


class TestRegisterBluePoint(unittest.TestCase):
    """Tests for _register_blue_point function."""

    def test_register_blue_point(self):
        """Test _register_blue_point creates Api with routes."""
        mock_view = MagicMock()
        mock_view.__name__ = "TestView"
        urls = [(mock_view, "/test")]
        api = _register_blue_point(urls)
        self.assertIsNotNone(api)


class TestInitApplication(unittest.TestCase):
    """Tests for init_application function."""

    def test_init_application(self):
        """Test init_application returns Flask app and syncs settings."""
        settings = SimpleNamespace(test_key="test_value")
        self.addCleanup(lambda: hasattr(configuration, "test_key") and delattr(configuration, "test_key"))
        app = init_application("cobbled", settings)
        self.assertIsInstance(app, Flask)
        self.assertEqual(app.name, "cobbled")
        self.assertNotIn("manager", app.blueprints)
        self.assertEqual(configuration.test_key, "test_value")

    def test_init_application_applies_config_dict(self):
        """Test init_application writes config dictionary entries into app.config."""
        settings = SimpleNamespace()
        app_config = {"CUSTOM_KEY": "custom_value", "MAX_ITEMS": 10}
        app = init_application("cobbled", settings, config=app_config)
        self.assertEqual(app.config["CUSTOM_KEY"], "custom_value")
        self.assertEqual(app.config["MAX_ITEMS"], 10)

    def test_init_application_registers_urls_and_manager_blueprint(self):
        """Test init_application registers Api resources and manager blueprint."""
        class DummyResource(Resource):
            def get(self):
                return {"status": "ok"}, 200

        settings = SimpleNamespace()
        app = init_application("cobbled", settings, register_urls=[(DummyResource, "/test/dummy")])
        self.assertIn("manager", app.blueprints)
        self.assertEqual(app.blueprints["manager"].name, "manager")
        registered_rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/test/dummy", registered_rules)
        response = app.test_client().get("/test/dummy")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_init_application_skips_underscore_settings(self):
        """Test init_application skips attributes starting with underscore when syncing settings."""
        settings = SimpleNamespace(
            public_setting="public_value",
            _private_setting="private_value",
            __dunder_setting__="dunder_value",
        )
        for attr in ("public_setting", "_private_setting", "__dunder_setting__"):
            self.addCleanup(lambda name=attr: hasattr(configuration, name) and delattr(configuration, name))

        init_application("cobbled", settings)
        self.assertEqual(configuration.public_setting, "public_value")
        self.assertFalse(hasattr(configuration, "_private_setting"))
        self.assertFalse(hasattr(configuration, "__dunder_setting__"))


if __name__ == "__main__":
    unittest.main()

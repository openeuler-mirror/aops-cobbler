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
from unittest.mock import patch, MagicMock

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

    @patch("cobbled.manage.configuration")
    def test_init_application(self, mock_config):
        """Test init_application returns Flask app."""
        mock_settings = MagicMock()
        mock_settings.__dict__ = {"test_key": "test_value"}
        with patch("cobbled.manage.__import__", return_value=MagicMock()):
            app = init_application("cobbled", mock_settings)
            self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()

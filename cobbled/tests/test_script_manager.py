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
Description: unit tests for script_manager/view.py
"""
import os
import unittest
from unittest.mock import patch, MagicMock

from cobbled.script_manager.view import QueryScript, DeleteScript

SCRIPT_NAME = "test_script"
SCRIPT_CONTENT = "#!/bin/bash\necho hello"
UPLOAD_DIR = "/tmp/test_scripts"


class TestQueryScript(unittest.TestCase):
    """Tests for QueryScript post method."""

    @patch("cobbled.script_manager.view.upload_dir", UPLOAD_DIR)
    @patch("cobbled.script_manager.view.FileUtil")
    @patch("cobbled.script_manager.view.request")
    def test_query_script(self, mock_request, mock_file):
        """Test post returns list of scripts."""
        mock_request.json = {"script_name": ""}
        mock_file.read_file_content.return_value = SCRIPT_CONTENT
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(os.path.join(UPLOAD_DIR, SCRIPT_NAME + ".sh"), "w") as f:
            f.write(SCRIPT_CONTENT)
        resource = QueryScript()
        result = resource.post()
        self.assertIsInstance(result, list)
        os.remove(os.path.join(UPLOAD_DIR, SCRIPT_NAME + ".sh"))


class TestDeleteScript(unittest.TestCase):
    """Tests for DeleteScript post method."""

    @patch("cobbled.script_manager.view.upload_dir", UPLOAD_DIR)
    @patch("cobbled.script_manager.view.ScriptChecker")
    @patch("cobbled.script_manager.view.request")
    def test_delete_script_success(self, mock_request, mock_checker):
        """Test post returns success for existing file."""
        mock_request.json = {"script_name": SCRIPT_NAME}
        mock_checker.check_script_name.return_value = None
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(os.path.join(UPLOAD_DIR, SCRIPT_NAME + ".sh"), "w") as f:
            f.write(SCRIPT_CONTENT)
        resource = DeleteScript()
        result = resource.post()
        self.assertFalse(os.path.exists(os.path.join(UPLOAD_DIR, SCRIPT_NAME + ".sh")))

    @patch("cobbled.script_manager.view.upload_dir", UPLOAD_DIR)
    @patch("cobbled.script_manager.view.ScriptChecker")
    @patch("cobbled.script_manager.view.request")
    def test_delete_script_not_found(self, mock_request, mock_checker):
        """Test post returns error for non-existent file."""
        mock_request.json = {"script_name": "nonexistent"}
        mock_checker.check_script_name.return_value = None
        resource = DeleteScript()
        result = resource.post()
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()

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
import io
import os
import unittest
from unittest.mock import patch, MagicMock

from flask import Flask
from flask_restful import Api

from cobbled.script_manager.view import UploadScript, QueryScript, DeleteScript
from cobbled.util.response_util import ResUtil

SCRIPT_NAME = "test_script"
SCRIPT_CONTENT = "#!/bin/bash\necho hello"
UPLOAD_DIR = "/tmp/test_scripts"

# A real Flask app is used to provide the request context. Patching the flask
# `request` proxy directly makes the proxy resolve at patch setup time and
# raise "Working outside of request context".
APP = Flask("script-test")
Api(APP).add_resource(UploadScript, "/script")


class TestUploadScript(unittest.TestCase):
    """Tests for UploadScript post method."""

    @patch("cobbled.script_manager.view.upload_dir", UPLOAD_DIR)
    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_upload_script_success(self, mock_checker):
        """Test post saves a valid script file."""
        mock_checker.check_script_name.return_value = None
        mock_checker.check_script_file.return_value = None
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        data = {"script_file": (io.BytesIO(SCRIPT_CONTENT.encode()), "test_script.sh"),
                "script_name": SCRIPT_NAME}
        response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(os.path.exists(os.path.join(UPLOAD_DIR, SCRIPT_NAME + ".sh")))
        os.remove(os.path.join(UPLOAD_DIR, SCRIPT_NAME + ".sh"))

    @patch("cobbled.script_manager.view.upload_dir", UPLOAD_DIR)
    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_upload_script_invalid_name(self, mock_checker):
        """Test post returns error for invalid script name."""
        # Build the response at call time, inside the request context:
        # jsonify requires an active application context.
        mock_checker.check_script_name.side_effect = lambda name: ResUtil.failed("invalid script name")
        data = {"script_file": (io.BytesIO(SCRIPT_CONTENT.encode()), "bad name.sh"),
                "script_name": "bad name"}
        response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)

    @patch("cobbled.script_manager.view.upload_dir", UPLOAD_DIR)
    @patch("cobbled.script_manager.view.ScriptChecker")
    @patch("cobbled.script_manager.view.subprocess")
    def test_upload_script_syntax_error(self, mock_subprocess, mock_checker):
        """Test post returns error when bash -n fails."""
        mock_checker.check_script_name.return_value = None
        mock_checker.check_script_file.return_value = None
        mock_subprocess.run.return_value = MagicMock(returncode=1, stderr="syntax error near line 1")
        data = {"script_file": (io.BytesIO(b"if\n"), "broken.sh"),
                "script_name": SCRIPT_NAME}
        response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)

    @patch("cobbled.script_manager.view.upload_dir", UPLOAD_DIR)
    @patch("cobbled.script_manager.view.max_content_length", 2)
    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_upload_script_too_large(self, mock_checker):
        """Test post returns error when script exceeds max size."""
        mock_checker.check_script_name.return_value = None
        mock_checker.check_script_file.return_value = None
        data = {"script_file": (io.BytesIO(SCRIPT_CONTENT.encode()), "test_script.sh"),
                "script_name": SCRIPT_NAME}
        response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)


class TestQueryScript(unittest.TestCase):
    """Tests for QueryScript post method."""

    @patch("cobbled.script_manager.view.upload_dir", UPLOAD_DIR)
    @patch("cobbled.script_manager.view.FileUtil")
    def test_query_script(self, mock_file):
        """Test post returns list of scripts."""
        mock_file.read_file_content.return_value = SCRIPT_CONTENT
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(os.path.join(UPLOAD_DIR, SCRIPT_NAME + ".sh"), "w") as f:
            f.write(SCRIPT_CONTENT)
        with APP.test_request_context(json={"script_name": ""}):
            resource = QueryScript()
            result = resource.post()
        self.assertIsInstance(result, list)
        os.remove(os.path.join(UPLOAD_DIR, SCRIPT_NAME + ".sh"))


class TestDeleteScript(unittest.TestCase):
    """Tests for DeleteScript post method."""

    @patch("cobbled.script_manager.view.upload_dir", UPLOAD_DIR)
    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_delete_script_success(self, mock_checker):
        """Test post returns success for existing file."""
        mock_checker.check_script_name.return_value = None
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(os.path.join(UPLOAD_DIR, SCRIPT_NAME + ".sh"), "w") as f:
            f.write(SCRIPT_CONTENT)
        with APP.test_request_context(json={"script_name": SCRIPT_NAME}):
            resource = DeleteScript()
            result = resource.post()
        self.assertFalse(os.path.exists(os.path.join(UPLOAD_DIR, SCRIPT_NAME + ".sh")))
        self.assertIsNotNone(result)

    @patch("cobbled.script_manager.view.upload_dir", UPLOAD_DIR)
    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_delete_script_not_found(self, mock_checker):
        """Test post returns error for non-existent file."""
        mock_checker.check_script_name.return_value = None
        with APP.test_request_context(json={"script_name": "nonexistent"}):
            resource = DeleteScript()
            result = resource.post()
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()

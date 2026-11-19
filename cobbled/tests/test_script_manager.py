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
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from flask import Flask
from flask_restful import Api
from werkzeug.datastructures import FileStorage

from cobbled.conf.constant import ScriptCons
from cobbled.util.file_util import FileUtil
from cobbled.util.response_util import ResUtil

with patch.object(FileUtil, "makedirs"):
    from cobbled.script_manager.view import UploadScript, QueryScript, DeleteScript

SCRIPT_NAME = "test_script"
SCRIPT_CONTENT = "#!/bin/bash\necho hello"

# A real Flask app is used to provide the request context. Patching the flask
# `request` proxy directly makes the proxy resolve at patch setup time and
# raise "Working outside of request context".
APP = Flask("script-test")
Api(APP).add_resource(UploadScript, "/script")


class TestUploadScript(unittest.TestCase):
    """Tests for UploadScript post method."""

    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_upload_script_success(self, mock_checker):
        """Test post saves a valid script file."""
        mock_checker.check_script_name.return_value = None
        mock_checker.check_script_file.return_value = None
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            data = {"script_file": (io.BytesIO(SCRIPT_CONTENT.encode()), "test_script.sh"),
                    "script_name": SCRIPT_NAME}
            response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
            saved_path = os.path.join(upload_dir, SCRIPT_NAME + ".sh")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.get_json(),
                {"code": 200, "msg": ScriptCons.UPLOAD_SCRIPT_SUCCESS_TIPS},
            )
            self.assertTrue(os.path.exists(saved_path))
            with open(saved_path, "r", encoding="utf-8") as saved_file:
                self.assertEqual(saved_file.read(), SCRIPT_CONTENT)

    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_upload_script_invalid_name(self, mock_checker):
        """Test post returns error for invalid script name."""
        # Build the response at call time, inside the request context:
        # jsonify requires an active application context.
        mock_checker.check_script_name.side_effect = lambda name: ResUtil.failed("invalid script name")
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            data = {"script_file": (io.BytesIO(SCRIPT_CONTENT.encode()), "bad name.sh"),
                    "script_name": "bad name"}
            response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json(), {"code": 400, "msg": "invalid script name"})

    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_upload_script_invalid_file(self, mock_checker):
        """Test post returns error for invalid script file."""
        mock_checker.check_script_name.return_value = None
        mock_checker.check_script_file.side_effect = lambda file_obj: ResUtil.failed(ScriptCons.CHECK_SCRIPT_SUFFIX_TIPS)
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            data = {"script_file": (io.BytesIO(SCRIPT_CONTENT.encode()), "test_script.txt"),
                    "script_name": SCRIPT_NAME}
            response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json(), {"code": 400, "msg": ScriptCons.CHECK_SCRIPT_SUFFIX_TIPS})

    @patch("cobbled.script_manager.view.ScriptChecker")
    @patch("cobbled.script_manager.view.subprocess")
    def test_upload_script_syntax_error(self, mock_subprocess, mock_checker):
        """Test post returns error when bash -n fails."""
        mock_checker.check_script_name.return_value = None
        mock_checker.check_script_file.return_value = None
        mock_subprocess.run.return_value = MagicMock(returncode=1, stderr="syntax error near line 1")
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            data = {"script_file": (io.BytesIO(b"if\n"), "broken.sh"),
                    "script_name": SCRIPT_NAME}
            response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json(), {"code": 400, "msg": "syntax error near line 1"})
            mock_subprocess.run.assert_called_once()
            cmd = mock_subprocess.run.call_args.args[0]
            self.assertEqual(cmd[:2], ["bash", "-n"])
            self.assertTrue(cmd[2].endswith(".sh"))
            self.assertEqual(
                mock_subprocess.run.call_args.kwargs,
                {"capture_output": True, "text": True},
            )
            self.assertFalse(os.path.exists(os.path.join(upload_dir, SCRIPT_NAME + ".sh")))

    @patch("cobbled.script_manager.view.max_content_length", 1024)
    @patch("cobbled.script_manager.view.ScriptChecker")
    @patch("cobbled.script_manager.view.subprocess")
    def test_upload_script_too_large(self, mock_subprocess, mock_checker):
        """Test post rejects scripts exceeding max_content_length before syntax check."""
        mock_checker.check_script_name.return_value = None
        mock_checker.check_script_file.return_value = None
        oversized_content = b"a" * 1025
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            data = {"script_file": (io.BytesIO(oversized_content), "test_script.sh"),
                    "script_name": SCRIPT_NAME}
            response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.get_json(),
                {"code": 400, "msg": ScriptCons.CHECK_SCRIPT_SIZE_TIPS + "1KiB"},
            )
            mock_subprocess.run.assert_not_called()
            self.assertFalse(os.path.exists(os.path.join(upload_dir, SCRIPT_NAME + ".sh")))

    @patch("cobbled.script_manager.view.max_content_length", len(SCRIPT_CONTENT.encode()))
    @patch("cobbled.script_manager.view.ScriptChecker")
    @patch("cobbled.script_manager.view.subprocess")
    def test_upload_script_exact_max_size(self, mock_subprocess, mock_checker):
        """Test post allows scripts whose size equals max_content_length."""
        mock_checker.check_script_name.return_value = None
        mock_checker.check_script_file.return_value = None
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            data = {"script_file": (io.BytesIO(SCRIPT_CONTENT.encode()), "test_script.sh"),
                    "script_name": SCRIPT_NAME}
            response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(os.path.exists(os.path.join(upload_dir, SCRIPT_NAME + ".sh")))

    @patch("cobbled.script_manager.view.ScriptChecker")
    @patch("cobbled.script_manager.view.subprocess")
    def test_upload_script_write_error(self, mock_subprocess, mock_checker):
        """Test post catches file write exceptions and returns HTTP 500."""
        mock_checker.check_script_name.return_value = None
        mock_checker.check_script_file.return_value = None
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir), \
                patch.object(FileStorage, "save", side_effect=[None, OSError("disk full")]):
            data = {"script_file": (io.BytesIO(SCRIPT_CONTENT.encode()), "test_script.sh"),
                    "script_name": SCRIPT_NAME}
            response = APP.test_client().post("/script", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.get_json(), {"code": 500, "msg": "disk full"})
            self.assertFalse(os.path.exists(os.path.join(upload_dir, SCRIPT_NAME + ".sh")))


class TestQueryScript(unittest.TestCase):
    """Tests for QueryScript post method."""

    @patch("cobbled.script_manager.view.FileUtil")
    def test_query_script(self, mock_file):
        """Test post returns list of scripts when filter is empty."""
        mock_file.read_file_content.return_value = SCRIPT_CONTENT
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            with open(os.path.join(upload_dir, SCRIPT_NAME + ".sh"), "w", encoding="utf-8") as f:
                f.write(SCRIPT_CONTENT)
            with APP.test_request_context(json={"script_name": ""}):
                result = QueryScript().post()
            self.assertEqual(result, [{"script_name": SCRIPT_NAME + ".sh", "script_content": SCRIPT_CONTENT}])

    @patch("cobbled.script_manager.view.FileUtil")
    def test_query_script_filter_by_name(self, mock_file):
        """Test post excludes scripts whose filename does not match script_name."""
        mock_file.read_file_content.side_effect = lambda path: f"content:{os.path.basename(path)}"
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            for name in ("alpha_deploy.sh", "beta_cleanup.sh"):
                with open(os.path.join(upload_dir, name), "w", encoding="utf-8") as f:
                    f.write(SCRIPT_CONTENT)

            with APP.test_request_context(json={"script_name": "alpha"}):
                result = QueryScript().post()
            self.assertEqual(
                result,
                [{"script_name": "alpha_deploy.sh", "script_content": "content:alpha_deploy.sh"}],
            )

            with APP.test_request_context(json={"script_name": "gamma"}):
                empty_result = QueryScript().post()
            self.assertEqual(empty_result, [])


class TestDeleteScript(unittest.TestCase):
    """Tests for DeleteScript post method."""

    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_delete_script_success(self, mock_checker):
        """Test post returns success for existing file."""
        mock_checker.check_script_name.return_value = None
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            script_path = os.path.join(upload_dir, SCRIPT_NAME + ".sh")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(SCRIPT_CONTENT)
            with APP.test_request_context(json={"script_name": SCRIPT_NAME}):
                result = DeleteScript().post()
            self.assertFalse(os.path.exists(script_path))
            self.assertEqual(result.status_code, 200)
            self.assertEqual(
                result.get_json(),
                {"code": 200, "msg": ScriptCons.DELETE_SCRIPT_SUCCESS_TIPS},
            )

    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_delete_script_not_found(self, mock_checker):
        """Test post returns error for non-existent file."""
        mock_checker.check_script_name.return_value = None
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            with APP.test_request_context(json={"script_name": "nonexistent"}):
                result = DeleteScript().post()
            self.assertEqual(result.status_code, 400)
            self.assertEqual(
                result.get_json(),
                {"code": 400, "msg": ScriptCons.CHECK_SCRIPT_EXITS_TIPS},
            )

    @patch("cobbled.script_manager.view.ScriptChecker")
    def test_delete_script_invalid_name(self, mock_checker):
        """Test post returns validation error for invalid script name."""
        mock_checker.check_script_name.side_effect = lambda name: ResUtil.failed(ScriptCons.CHECK_SCRIPT_NAME_TIPS)
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch("cobbled.script_manager.view.upload_dir", upload_dir):
            with APP.test_request_context(json={"script_name": "bad name"}):
                result = DeleteScript().post()
            self.assertEqual(result.status_code, 400)
            self.assertEqual(
                result.get_json(),
                {"code": 400, "msg": ScriptCons.CHECK_SCRIPT_NAME_TIPS},
            )


if __name__ == "__main__":
    unittest.main()

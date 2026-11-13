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
Description: unit tests for ks_manager/view.py
"""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from flask import Flask

from cobbled.conf.constant import KsCons
from cobbled.util.file_util import FileUtil

with patch.object(FileUtil, "makedirs"):
    from cobbled.ks_manager.view import AddKickstart, UpdateKickstart, DeleteKickstart, QueryKickstart

KS_NAME = "test_ks"
KS_CONTENT = "auth --enableshadow --passalgo=sha512"

# A real Flask app is used to provide the request context. Patching the flask
# `request` proxy directly makes the proxy resolve at patch setup time and
# raise "Working outside of request context".
APP = Flask("ks-test")


class KickstartTestBase(unittest.TestCase):
    """Base test case providing an isolated temporary kickstart directory."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.ks_dir_patcher = patch("cobbled.ks_manager.view.ks_dir", self.temp_dir.name)
        self.ks_dir_patcher.start()
        self.addCleanup(self.ks_dir_patcher.stop)

    def _ks_path(self, ks_name):
        return os.path.join(self.temp_dir.name, f"{ks_name}.ks")

    def _write_ks_file(self, ks_name, content=KS_CONTENT, mtime=None):
        path = self._ks_path(ks_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path


class TestAddKickstart(KickstartTestBase):
    """Tests for AddKickstart post method."""

    @patch("cobbled.ks_manager.view.subprocess.run")
    def test_add_kickstart_success(self, mock_run):
        """Test post returns success and writes file for valid kickstart."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        with APP.test_request_context(json={"ks_name": KS_NAME, "ks_content": KS_CONTENT}):
            result = AddKickstart().post()

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json(), {"code": 200, "msg": KsCons.ADD_KS_SUCCESS_TIPS})
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args.args[0][0], "ksvalidator")
        with open(self._ks_path(KS_NAME), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), KS_CONTENT)

    @patch("cobbled.ks_manager.view.subprocess.run")
    def test_add_kickstart_validation_fail(self, mock_run):
        """Test post returns 400 for invalid ks_name or ks_content."""
        cases = (
            ("", KS_CONTENT, KsCons.CHECK_KS_NAME_TIPS),
            ("../invalid", KS_CONTENT, KsCons.CHECK_KS_NAME_TIPS),
            (KS_NAME, "", KsCons.CHECK_KS_CONTENT_TIPS),
            (KS_NAME, None, KsCons.CHECK_KS_CONTENT_TIPS),
        )
        for ks_name, ks_content, expected_msg in cases:
            with self.subTest(ks_name=ks_name, ks_content=ks_content):
                with APP.test_request_context(json={"ks_name": ks_name, "ks_content": ks_content}):
                    result = AddKickstart().post()
                self.assertEqual(result.status_code, 400)
                self.assertEqual(result.get_json(), {"code": 400, "msg": expected_msg})
        mock_run.assert_not_called()
        self.assertFalse(os.path.exists(self._ks_path(KS_NAME)))

    @patch("cobbled.ks_manager.view.subprocess.run")
    def test_add_kickstart_syntax_error(self, mock_run):
        """Test post returns ksvalidator stderr when syntax validation fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Unknown command: badcmd")
        with APP.test_request_context(json={"ks_name": KS_NAME, "ks_content": "badcmd"}):
            result = AddKickstart().post()

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.get_json(), {"code": 400, "msg": "Unknown command: badcmd"})
        mock_run.assert_called_once()
        self.assertFalse(os.path.exists(self._ks_path(KS_NAME)))


class TestUpdateKickstart(KickstartTestBase):
    """Tests for UpdateKickstart post method."""

    @patch("cobbled.ks_manager.view.subprocess.run")
    def test_update_kickstart_validation_fail(self, mock_run):
        """Test post returns 400 when ks_name or ks_content is invalid."""
        cases = (
            ("", KS_CONTENT, KsCons.CHECK_KS_NAME_TIPS),
            ("bad/name", KS_CONTENT, KsCons.CHECK_KS_NAME_TIPS),
            (KS_NAME, "", KsCons.CHECK_KS_CONTENT_TIPS),
            (KS_NAME, None, KsCons.CHECK_KS_CONTENT_TIPS),
        )
        for ks_name, ks_content, expected_msg in cases:
            with self.subTest(ks_name=ks_name, ks_content=ks_content):
                with APP.test_request_context(json={"ks_name": ks_name, "ks_content": ks_content}):
                    result = UpdateKickstart().post()
                self.assertEqual(result.status_code, 400)
                self.assertEqual(result.get_json(), {"code": 400, "msg": expected_msg})
        mock_run.assert_not_called()

    @patch("cobbled.ks_manager.view.subprocess.run")
    def test_update_kickstart_not_found(self, mock_run):
        """Test post returns 400 when target kickstart file does not exist."""
        with APP.test_request_context(json={"ks_name": "nonexistent", "ks_content": KS_CONTENT}):
            result = UpdateKickstart().post()

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.get_json(), {"code": 400, "msg": KsCons.CHECK_KS_EXITS_TIPS})
        mock_run.assert_not_called()

    @patch("cobbled.ks_manager.view.subprocess.run")
    def test_update_kickstart_syntax_error(self, mock_run):
        """Test post returns ksvalidator stderr and preserves existing file on syntax error."""
        self._write_ks_file(KS_NAME, KS_CONTENT)
        mock_run.return_value = MagicMock(returncode=1, stderr="Syntax error on line 1")
        with APP.test_request_context(json={"ks_name": KS_NAME, "ks_content": "invalid content"}):
            result = UpdateKickstart().post()

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.get_json(), {"code": 400, "msg": "Syntax error on line 1"})
        mock_run.assert_called_once()
        with open(self._ks_path(KS_NAME), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), KS_CONTENT)

    @patch("cobbled.ks_manager.view.subprocess.run")
    def test_update_kickstart_success(self, mock_run):
        """Test post updates file content and returns success when validation passes."""
        self._write_ks_file(KS_NAME, KS_CONTENT)
        updated_content = "lang en_US.UTF-8\nkeyboard us"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        with APP.test_request_context(json={"ks_name": KS_NAME, "ks_content": updated_content}):
            result = UpdateKickstart().post()

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json(), {"code": 200, "msg": KsCons.UPDATE_KS_SUCCESS_TIPS})
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args.args[0][0], "ksvalidator")
        with open(self._ks_path(KS_NAME), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), updated_content)


class TestDeleteKickstart(KickstartTestBase):
    """Tests for DeleteKickstart post method."""

    def test_delete_kickstart_validation_fail(self):
        """Test post returns 400 when ks_name is invalid."""
        self._write_ks_file(KS_NAME, KS_CONTENT)
        for bad_name in ("", None, "../test_ks"):
            with self.subTest(ks_name=bad_name):
                with APP.test_request_context(json={"ks_name": bad_name}):
                    result = DeleteKickstart().post()
                self.assertEqual(result.status_code, 400)
                self.assertEqual(result.get_json(), {"code": 400, "msg": KsCons.CHECK_KS_NAME_TIPS})
        self.assertTrue(os.path.exists(self._ks_path(KS_NAME)))

    def test_delete_kickstart_success(self):
        """Test post deletes existing file and returns success."""
        ks_path = self._write_ks_file(KS_NAME, KS_CONTENT)
        with APP.test_request_context(json={"ks_name": KS_NAME}):
            result = DeleteKickstart().post()

        self.assertFalse(os.path.exists(ks_path))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json(), {"code": 200, "msg": KsCons.DELETE_KS_SUCCESS_TIPS})

    def test_delete_kickstart_not_found(self):
        """Test post returns 400 for non-existent file."""
        with APP.test_request_context(json={"ks_name": "nonexistent"}):
            result = DeleteKickstart().post()

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.get_json(), {"code": 400, "msg": KsCons.CHECK_KS_EXITS_TIPS})


class TestQueryKickstart(KickstartTestBase):
    """Tests for QueryKickstart post method."""

    @patch("cobbled.ks_manager.view.configuration")
    def test_query_kickstart(self, mock_config):
        """Test post returns all kickstart files ordered by mtime descending."""
        mock_config.cobbler_client.get.return_value = "127.0.0.1"
        self._write_ks_file("older_ks", "old content", mtime=1000)
        self._write_ks_file("newer_ks", "new content", mtime=2000)

        with APP.test_request_context(json={"ks_name": ""}):
            result = QueryKickstart().post()

        self.assertEqual(result, [
            {
                "ks_name": "newer_ks.ks",
                "ks_content": "new content",
                "ks_address": "http://127.0.0.1/ks/newer_ks.ks",
            },
            {
                "ks_name": "older_ks.ks",
                "ks_content": "old content",
                "ks_address": "http://127.0.0.1/ks/older_ks.ks",
            },
        ])

    @patch("cobbled.ks_manager.view.configuration")
    def test_query_kickstart_filter_by_name(self, mock_config):
        """Test post filters out kickstart files not matching ks_name."""
        mock_config.cobbler_client.get.return_value = "127.0.0.1"
        self._write_ks_file("openeuler_base", "base content", mtime=1000)
        self._write_ks_file("centos_base", "centos content", mtime=1500)
        self._write_ks_file("openeuler_custom", "custom content", mtime=2000)

        with APP.test_request_context(json={"ks_name": "openeuler"}):
            result = QueryKickstart().post()

        self.assertEqual(result, [
            {
                "ks_name": "openeuler_custom.ks",
                "ks_content": "custom content",
                "ks_address": "http://127.0.0.1/ks/openeuler_custom.ks",
            },
            {
                "ks_name": "openeuler_base.ks",
                "ks_content": "base content",
                "ks_address": "http://127.0.0.1/ks/openeuler_base.ks",
            },
        ])


if __name__ == "__main__":
    unittest.main()

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

from cobbled.ks_manager.view import AddKickstart, UpdateKickstart, DeleteKickstart, QueryKickstart

KS_NAME = "test_ks"
KS_CONTENT = "auth --enableshadow --passalgo=sha512"
HTTP_DIR = "/tmp/test_ks"


class TestAddKickstart(unittest.TestCase):
    """Tests for AddKickstart post method."""

    @patch("cobbled.ks_manager.view.ks_dir", HTTP_DIR)
    @patch("cobbled.ks_manager.view.FileUtil")
    @patch("cobbled.ks_manager.view.KsChecker")
    @patch("cobbled.ks_manager.view.request")
    @patch("cobbled.ks_manager.view.subprocess")
    def test_add_kickstart_success(self, mock_subprocess, mock_request, mock_checker, mock_file):
        """Test post returns success for valid kickstart."""
        mock_request.json = {"ks_name": KS_NAME, "ks_content": KS_CONTENT}
        mock_checker.check_ks_name.return_value = None
        mock_checker.check_ks_content.return_value = None
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        os.makedirs(HTTP_DIR, exist_ok=True)
        resource = AddKickstart()
        result = resource.post()
        mock_file.write_file_content.assert_called_once()

    @patch("cobbled.ks_manager.view.ks_dir", HTTP_DIR)
    @patch("cobbled.ks_manager.view.KsChecker")
    @patch("cobbled.ks_manager.view.request")
    def test_add_kickstart_validation_fail(self, mock_request, mock_checker):
        """Test post returns error for invalid kickstart."""
        mock_request.json = {"ks_name": "", "ks_content": KS_CONTENT}
        mock_checker.check_ks_name.return_value = "invalid name"
        resource = AddKickstart()
        result = resource.post()
        self.assertIsNotNone(result)


class TestDeleteKickstart(unittest.TestCase):
    """Tests for DeleteKickstart post method."""

    @patch("cobbled.ks_manager.view.ks_dir", HTTP_DIR)
    @patch("cobbled.ks_manager.view.KsChecker")
    @patch("cobbled.ks_manager.view.request")
    def test_delete_kickstart_success(self, mock_request, mock_checker):
        """Test post returns success for existing file."""
        mock_request.json = {"ks_name": KS_NAME}
        mock_checker.check_ks_name.return_value = None
        os.makedirs(HTTP_DIR, exist_ok=True)
        with open(os.path.join(HTTP_DIR, KS_NAME + ".ks"), "w") as f:
            f.write(KS_CONTENT)
        resource = DeleteKickstart()
        result = resource.post()
        self.assertFalse(os.path.exists(os.path.join(HTTP_DIR, KS_NAME + ".ks")))

    @patch("cobbled.ks_manager.view.ks_dir", HTTP_DIR)
    @patch("cobbled.ks_manager.view.KsChecker")
    @patch("cobbled.ks_manager.view.request")
    def test_delete_kickstart_not_found(self, mock_request, mock_checker):
        """Test post returns error for non-existent file."""
        mock_request.json = {"ks_name": "nonexistent"}
        mock_checker.check_ks_name.return_value = None
        resource = DeleteKickstart()
        result = resource.post()
        self.assertIsNotNone(result)


class TestQueryKickstart(unittest.TestCase):
    """Tests for QueryKickstart post method."""

    @patch("cobbled.ks_manager.view.ks_dir", HTTP_DIR)
    @patch("cobbled.ks_manager.view.FileUtil")
    @patch("cobbled.ks_manager.view.request")
    def test_query_kickstart(self, mock_request, mock_file):
        """Test post returns list of kickstart files."""
        mock_request.json = {"ks_name": ""}
        mock_file.read_file_content.return_value = KS_CONTENT
        os.makedirs(HTTP_DIR, exist_ok=True)
        with open(os.path.join(HTTP_DIR, KS_NAME + ".ks"), "w") as f:
            f.write(KS_CONTENT)
        resource = QueryKickstart()
        result = resource.post()
        self.assertIsInstance(result, list)
        os.remove(os.path.join(HTTP_DIR, KS_NAME + ".ks"))


if __name__ == "__main__":
    unittest.main()

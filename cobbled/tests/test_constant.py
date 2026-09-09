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
Description: unit tests for conf/constant.py
"""
import unittest

from cobbled.conf.constant import ConfigCons, RouteCons, HostCons, ISOCons, KsCons, InstallCons, ScriptCons


class TestConfigCons(unittest.TestCase):
    """Tests for ConfigCons constants."""

    def test_base_config_path(self):
        """Test BASE_CONFIG_PATH is a valid path."""
        self.assertIn("/etc", ConfigCons.BASE_CONFIG_PATH)

    def test_aes_key_exists(self):
        """Test AES_KEY is not empty."""
        self.assertTrue(len(ConfigCons.AES_KEY) > 0)


class TestRouteCons(unittest.TestCase):
    """Tests for RouteCons constants."""

    def test_upload_iso(self):
        """Test UPLOAD_ISO route."""
        self.assertEqual(RouteCons.UPLOAD_ISO, "/cobbler/uploadISO")

    def test_add_kickstart(self):
        """Test ADD_KICKSTART route."""
        self.assertEqual(RouteCons.ADD_KICKSTART, "/cobbler/addKickstart")

    def test_add_host(self):
        """Test ADD_HOST route."""
        self.assertEqual(RouteCons.ADD_HOST, "/cobbler/addHost")

    def test_upload_script(self):
        """Test UPLOAD_SCRIPT route."""
        self.assertEqual(RouteCons.UPLOAD_SCRIPT, "/cobbler/uploadScript")


class TestHostCons(unittest.TestCase):
    """Tests for HostCons constants."""

    def test_host_template_content(self):
        """Test HOST_TEMPLATE_FILE_CONTENT is not empty."""
        self.assertTrue(len(HostCons.HOST_TEMPLATE_FILE_CONTENT) > 0)

    def test_add_host_success_tips(self):
        """Test ADD_HOST_SUCCESS_TIPS is not empty."""
        self.assertTrue(len(HostCons.ADD_HOST_SUCCESS_TIPS) > 0)


class TestKsCons(unittest.TestCase):
    """Tests for KsCons constants."""

    def test_add_ks_success_tips(self):
        """Test ADD_KS_SUCCESS_TIPS is not empty."""
        self.assertTrue(len(KsCons.ADD_KS_SUCCESS_TIPS) > 0)


class TestScriptCons(unittest.TestCase):
    """Tests for ScriptCons constants."""

    def test_upload_script_success_tips(self):
        """Test UPLOAD_SCRIPT_SUCCESS_TIPS is not empty."""
        self.assertTrue(len(ScriptCons.UPLOAD_SCRIPT_SUCCESS_TIPS) > 0)


if __name__ == "__main__":
    unittest.main()

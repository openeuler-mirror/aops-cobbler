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
Description: unit tests for url.py
"""
import unittest

from cobbled.url import URLS, SPECIFIC_URLS


class TestUrlModule(unittest.TestCase):
    """Tests for url module constants."""

    def test_url_list_not_empty(self):
        """Test URLS list is not empty."""
        self.assertGreater(len(URLS), 0)

    def test_specific_urls_keys(self):
        """Test SPECIFIC_URLS contains expected keys."""
        self.assertIn("ISO_URLS", SPECIFIC_URLS)
        self.assertIn("KS_URLS", SPECIFIC_URLS)
        self.assertIn("AUTO_INSTALL_URLS", SPECIFIC_URLS)
        self.assertIn("HOST_URLS", SPECIFIC_URLS)
        self.assertIn("SCRIPT_URLS", SPECIFIC_URLS)

    def test_iso_urls_count(self):
        """Test ISO_URLS has 3 entries."""
        self.assertEqual(len(SPECIFIC_URLS["ISO_URLS"]), 3)

    def test_ks_urls_count(self):
        """Test KS_URLS has 4 entries."""
        self.assertEqual(len(SPECIFIC_URLS["KS_URLS"]), 4)

    def test_host_urls_count(self):
        """Test HOST_URLS has 6 entries."""
        self.assertEqual(len(SPECIFIC_URLS["HOST_URLS"]), 6)

    def test_script_urls_count(self):
        """Test SCRIPT_URLS has 3 entries."""
        self.assertEqual(len(SPECIFIC_URLS["SCRIPT_URLS"]), 3)

    def test_url_entries_are_tuples(self):
        """Test URL entries are (view_class, route) tuples."""
        for url_list in SPECIFIC_URLS.values():
            for entry in url_list:
                self.assertIsInstance(entry, tuple)
                self.assertEqual(len(entry), 2)


if __name__ == "__main__":
    unittest.main()

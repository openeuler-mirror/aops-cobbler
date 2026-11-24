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
Description: unit tests for util/aes_util.py
"""
import unittest
from unittest.mock import MagicMock, patch

from cobbled.util.aes_util import AesUtil
from cobbled.util.validate_util import run_ipmitool

PLAINTEXT = "hello world"
ENCRYPTED = AesUtil.encrypt(PLAINTEXT)


class TestAesUtilEncrypt(unittest.TestCase):
    """Tests for AesUtil.encrypt method."""

    def test_encrypt_returns_string(self):
        """Test encrypt returns a string."""
        result = AesUtil.encrypt("test")
        self.assertIsInstance(result, str)

    def test_encrypt_non_empty(self):
        """Test encrypt returns non-empty string."""
        result = AesUtil.encrypt("test")
        self.assertTrue(len(result) > 0)

    def test_encrypt_decrypt_roundtrip(self):
        """Test encrypt then decrypt returns original."""
        encrypted = AesUtil.encrypt(PLAINTEXT)
        decrypted = AesUtil.decrypt(encrypted)
        self.assertEqual(decrypted, PLAINTEXT)


class TestAesUtilDecrypt(unittest.TestCase):
    """Tests for AesUtil.decrypt method."""

    def test_decrypt_valid(self):
        """Test decrypt returns original text."""
        encrypted = AesUtil.encrypt(PLAINTEXT)
        result = AesUtil.decrypt(encrypted)
        self.assertEqual(result, PLAINTEXT)

    def test_decrypt_invalid_token(self):
        """Test decrypt returns ciphertext for invalid token."""
        result = AesUtil.decrypt("invalid_ciphertext")
        self.assertEqual(result, "invalid_ciphertext")

    def test_decrypt_empty(self):
        """Test decrypt handles empty string."""
        result = AesUtil.decrypt("")
        self.assertEqual(result, "")

    def test_decrypt_non_string_returns_empty_string(self):
        """Non-string ciphertext must yield a safe empty string, not raise."""
        for value in (None, 123, b"raw-bytes"):
            with self.subTest(value=value):
                result = AesUtil.decrypt(value)
                self.assertIsInstance(result, str)
                self.assertEqual(result, "")

    @patch("cobbled.util.validate_util.subprocess.run")
    def test_missing_password_reaches_ipmitool_without_type_error(self, mock_run):
        """A missing bmc password must not crash the ipmitool command path."""
        mock_run.return_value = MagicMock(returncode=1)
        host = {"bmc_ip": "192.0.2.1", "bmc_user_name": "test", "bmc_passwd": None}
        password = AesUtil.decrypt(host.get("bmc_passwd"))
        self.assertEqual(run_ipmitool(host["bmc_ip"], host["bmc_user_name"], password,
                                      "power", "status"), 1)
        self.assertEqual(mock_run.call_args.args[0][8], "")


if __name__ == "__main__":
    unittest.main()

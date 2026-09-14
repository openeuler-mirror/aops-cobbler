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

from cobbled.util.aes_util import AesUtil

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


if __name__ == "__main__":
    unittest.main()

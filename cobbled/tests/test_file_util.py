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
Description: unit tests for util/file_util.py
"""
import hashlib
import os
import tempfile
import unittest

from cobbled.util.file_util import FileUtil

TEST_CONTENT = "hello world"


class TestFileUtilWriteAndRead(unittest.TestCase):
    """Tests for FileUtil write and read methods."""

    def test_write_and_read(self):
        """Test write_file_content then read_file_content returns same content."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name
        try:
            FileUtil.write_file_content(path, TEST_CONTENT)
            result = FileUtil.read_file_content(path)
            self.assertEqual(result, TEST_CONTENT)
        finally:
            os.unlink(path)

    def test_read_nonexistent(self):
        """Test read_file_content returns empty string for missing file."""
        result = FileUtil.read_file_content("/nonexistent/file.txt")
        self.assertEqual(result, "")


class TestFileUtilGetSize(unittest.TestCase):
    """Tests for FileUtil.get_file_size method."""

    def test_get_size(self):
        """Test get_file_size returns correct size."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            path = f.name
        try:
            size = FileUtil.get_file_size(path)
            self.assertEqual(size, 4)
        finally:
            os.unlink(path)

    def test_get_size_nonexistent(self):
        """Test get_file_size returns 0 for missing file."""
        result = FileUtil.get_file_size("/nonexistent/file.txt")
        self.assertEqual(result, 0)


class TestFileUtilCalculateSha256(unittest.TestCase):
    """Tests for FileUtil.calculate_file_sha256 method."""

    def test_calculate_sha256(self):
        """Test calculate_file_sha256 returns correct hash."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            path = f.name
        try:
            expected = hashlib.sha256(b"test").hexdigest()
            result = FileUtil.calculate_file_sha256(path)
            self.assertEqual(result, expected)
        finally:
            os.unlink(path)

    def test_calculate_sha256_nonexistent(self):
        """Test calculate_file_sha256 returns None for missing file."""
        result = FileUtil.calculate_file_sha256("/nonexistent/file.txt")
        self.assertIsNone(result)


class TestFileUtilMakedirs(unittest.TestCase):
    """Tests for FileUtil.makedirs method."""

    def test_makedirs(self):
        """Test makedirs creates directory."""
        with tempfile.TemporaryDirectory() as d:
            new_path = os.path.join(d, "subdir")
            FileUtil.makedirs(new_path)
            self.assertTrue(os.path.isdir(new_path))


if __name__ == "__main__":
    unittest.main()

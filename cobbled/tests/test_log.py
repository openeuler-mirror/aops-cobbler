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
Description: unit tests for log/log.py
"""
import logging
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from concurrent_log_handler import ConcurrentRotatingFileHandler

from cobbled.log.log import Logger

MODULE_LOGGER_NAME = "cobbled.log.log"


class LoggerTestCase(unittest.TestCase):
    """Base class: isolate the shared module logger for each test."""

    def setUp(self):
        self.module_logger = logging.getLogger(MODULE_LOGGER_NAME)
        self.original_handlers = list(self.module_logger.handlers)
        self.module_logger.handlers.clear()
        self.addCleanup(self._restore_handlers)
        self.tmpdir = tempfile.mkdtemp(prefix="aops_cobbler_log_test_")
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def _restore_handlers(self):
        self.module_logger.handlers.extend(self.original_handlers)

    def make_logger(self, log_dir, max_bytes=1048576, backup_count=3):
        config = {"LOG_DIR": log_dir, "LOG_LEVEL": logging.DEBUG,
                  "MAX_BYTES": max_bytes, "BACKUP_COUNT": backup_count}
        with patch("cobbled.log.log.configuration") as mock_config:
            mock_config.log.get.side_effect = config.get
            return Logger()


class TestLoggerCheckInteger(LoggerTestCase):
    """Tests for Logger.check (via the private __check_integer helper)."""

    def test_check_integer_rejects_non_int(self):
        with self.assertRaises(ValueError):
            Logger._Logger__check_integer("1048576", "max bytes")

    def test_check_integer_rejects_non_positive(self):
        for value in (0, -1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Logger._Logger__check_integer(value, "backup count")

    def test_check_integer_accepts_positive_int(self):
        self.assertIsNone(Logger._Logger__check_integer(100, "max bytes"))

    def test_init_rejects_invalid_rotation_config(self):
        """Test Logger init raises ValueError for invalid max_bytes."""
        config = {"LOG_DIR": self.tmpdir, "LOG_LEVEL": logging.DEBUG,
                  "MAX_BYTES": 0, "BACKUP_COUNT": 3}
        with patch("cobbled.log.log.configuration") as mock_config:
            mock_config.log.get.side_effect = config.get
            with self.assertRaises(ValueError):
                Logger()


class TestLoggerInit(LoggerTestCase):
    """Tests for Logger initialization."""

    def test_init_creates_missing_log_dir(self):
        log_dir = os.path.join(self.tmpdir, "nested", "logs")
        logger = self.make_logger(log_dir)
        self.assertIsNotNone(logger)
        self.assertTrue(os.path.isdir(log_dir))

    def test_init_swallows_makedirs_failure(self):
        """Test Logger init does not raise when the log dir cannot be created."""
        config = {"LOG_DIR": os.path.join(self.tmpdir, "blocked"),
                  "LOG_LEVEL": logging.DEBUG, "MAX_BYTES": 1024, "BACKUP_COUNT": 1}
        with patch("cobbled.log.log.configuration") as mock_config, \
                patch("cobbled.log.log.os.makedirs",
                      side_effect=OSError("read-only file system")):
            mock_config.log.get.side_effect = config.get
            logger = Logger()
        self.assertIsNotNone(logger)


class TestLoggerGetLogger(LoggerTestCase):
    """Tests for Logger.get_logger handler wiring."""

    def test_get_logger_returns_module_logger_with_handlers(self):
        logger = self.make_logger(self.tmpdir)
        result = logger.get_logger()
        self.assertIs(result, self.module_logger)
        self.assertEqual(len(result.handlers), 2)
        self.assertTrue(any(isinstance(h, logging.StreamHandler)
                            and not isinstance(h, ConcurrentRotatingFileHandler)
                            for h in result.handlers))
        self.assertTrue(any(isinstance(h, ConcurrentRotatingFileHandler)
                            for h in result.handlers))

    def test_get_logger_is_idempotent(self):
        """Test calling get_logger twice does not duplicate handlers."""
        logger = self.make_logger(self.tmpdir)
        first = logger.get_logger()
        self.assertEqual(len(first.handlers), 2)
        second = logger.get_logger()
        self.assertIs(second, first)
        self.assertEqual(len(second.handlers), 2)

    def test_get_logger_skips_file_handler_on_os_error(self):
        """Test a failing file handler is swallowed, console handler stays."""
        logger = self.make_logger(self.tmpdir)
        with patch("cobbled.log.log.ConcurrentRotatingFileHandler",
                   side_effect=OSError("disk full")):
            result = logger.get_logger()
        self.assertEqual(len(result.handlers), 1)
        self.assertIsInstance(result.handlers[0], logging.StreamHandler)

    def test_file_handler_writes_log_records(self):
        logger = self.make_logger(self.tmpdir)
        result = logger.get_logger()
        result.info("unit test record")
        for handler in result.handlers:
            handler.flush()
        log_file = os.path.join(self.tmpdir, "aops-cobbler.log")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("unit test record", content)


if __name__ == "__main__":
    unittest.main()

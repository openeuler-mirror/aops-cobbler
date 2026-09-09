#!/usr/bin/python3
# ******************************************************************************
# Copyright (c) iSoftStone Technologies Co., Ltd. 2023-2024. All rights reserved.
# licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#     http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN 'AS IS' BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v2 for more details.
# ******************************************************************************/
"""
Time:
Author:
Description: test iso manager
"""


import hashlib
import io
import os
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from cobbled.util.file_util import FileUtil

with patch.object(FileUtil, 'makedirs'):
    from cobbled.iso_manager import view


def calculate_iso_sha256(file_path):
    with open(file_path, 'rb') as f:
        hash_obj = hashlib.new('sha256')
        for chunk in iter(lambda: f.read(2 ** 20), b''):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def write_iso_sha256(file_path, sha256_code):
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(sha256_code)


def read_iso_sha256(file_path):
    content = ''
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    return content


class TestUploadISO(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)

    def _post_iso(self, run_side_effect=None, is_mounted=False):
        remote_server = MagicMock()
        remote_server.get_distro.return_value = None
        remote_factory = MagicMock()
        remote_factory.get_remote_server.return_value = (remote_server, 'token')

        request_context = self.app.test_request_context(
            '/cobbler/uploadISO',
            method='POST',
            data={
                'iso_name': 'demo',
                'arch': 'x86_64',
                'file': (io.BytesIO(b'iso'), 'demo.iso'),
            },
        )
        with request_context, \
                patch.object(view.ISOChecker, 'check_iso_name', return_value=None), \
                patch.object(view.ISOChecker, 'check_iso_arch', return_value=None), \
                patch.object(view.ISOChecker, 'check_iso_suffix', return_value=None), \
                patch.object(view, 'RemoteServer', return_value=remote_factory), \
                patch.object(view.os.path, 'exists', return_value=True), \
                patch.object(view.os.path, 'ismount', return_value=is_mounted), \
                patch.object(view.os, 'makedirs'), \
                patch.object(view.subprocess, 'run', side_effect=run_side_effect):
            response = view.UploadISO().post()

        return response, remote_server

    def test_mount_failure_does_not_start_cobbler_import(self):
        mount_error = subprocess.CalledProcessError(32, ['mount'])

        response, remote_server = self._post_iso(run_side_effect=mount_error)

        self.assertEqual(500, response.get_json()['code'])
        self.assertEqual('Failed to mount the iso file.', response.get_json()['msg'])
        remote_server.background_import.assert_not_called()

    def test_unmount_failure_does_not_start_cobbler_import(self):
        unmount_error = subprocess.CalledProcessError(32, ['umount'])

        response, remote_server = self._post_iso(
            run_side_effect=unmount_error, is_mounted=True
        )

        self.assertEqual(500, response.get_json()['code'])
        remote_server.background_import.assert_not_called()

    def test_mount_success_starts_cobbler_import(self):
        response, remote_server = self._post_iso()

        self.assertEqual(200, response.get_json()['code'])
        remote_server.background_import.assert_called_once()

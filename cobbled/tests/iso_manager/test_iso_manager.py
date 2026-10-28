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
import tempfile
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
        with tempfile.TemporaryDirectory() as upload_dir, request_context, \
                patch.object(view.ISOChecker, 'check_iso_name', return_value=None), \
                patch.object(view.ISOChecker, 'check_iso_arch', return_value=None), \
                patch.object(view.ISOChecker, 'check_iso_suffix', return_value=None), \
                patch.object(view, 'RemoteServer', return_value=remote_factory), \
                patch.object(view, 'upload_dir', upload_dir), \
                patch.object(view.os.path, 'ismount', return_value=is_mounted), \
                patch.object(view.os, 'makedirs'), \
                patch.object(view.subprocess, 'run', side_effect=run_side_effect):
            response = view.UploadISO().post()

        return response, remote_server

    def test_missing_file_returns_bad_request(self):
        with self.app.test_request_context('/cobbler/uploadISO', method='POST',
                                           data={'iso_name': 'demo', 'arch': 'x86_64'}):
            response = view.UploadISO().post()
        self.assertEqual(400, response.status_code)

    def test_same_name_different_architecture_has_separate_files(self):
        with tempfile.TemporaryDirectory() as upload_dir, \
                patch.object(view, 'upload_dir', upload_dir), \
                patch.object(view, 'RemoteServer') as remote_factory, \
                patch.object(view.os.path, 'ismount', return_value=False), \
                patch.object(view.os, 'makedirs'), \
                patch.object(view.subprocess, 'run') as run:
            remote_factory.return_value.get_remote_server.return_value = (
                MagicMock(get_distro=MagicMock(return_value=None)), 'token')
            for arch, contents in [('x86_64', b'x86'), ('aarch64', b'arm')]:
                with self.app.test_request_context(
                        '/cobbler/uploadISO', method='POST', data={
                            'iso_name': 'demo', 'arch': arch,
                            'file': (io.BytesIO(contents), 'demo.iso')}):
                    self.assertEqual(200, view.UploadISO().post().status_code)
                with open(os.path.join(upload_dir, 'demo-' + arch + '.iso'), 'rb') as f:
                    self.assertEqual(contents, f.read())
            self.assertEqual(2, run.call_count)

    def test_mount_failure_does_not_start_cobbler_import(self):
        mount_error = subprocess.CalledProcessError(32, ['mount'])

        response, remote_server = self._post_iso(run_side_effect=mount_error)

        self.assertEqual(500, response.get_json()['code'])
        self.assertEqual('Failed to mount the iso file.', response.get_json()['msg'])
        remote_server.background_import.assert_not_called()

    def test_mounted_destination_does_not_overwrite_or_import(self):
        response, remote_server = self._post_iso(is_mounted=True)
        self.assertEqual(400, response.get_json()['code'])
        remote_server.background_import.assert_not_called()

    def test_mount_success_starts_cobbler_import(self):
        response, remote_server = self._post_iso()

        self.assertEqual(200, response.get_json()['code'])
        remote_server.background_import.assert_called_once()


class TestDeleteISO(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_unmount_failure_keeps_distro_and_file(self):
        with tempfile.TemporaryDirectory() as upload_dir:
            iso_path = os.path.join(upload_dir, 'demo-x86_64.iso')
            with open(iso_path, 'wb') as f:
                f.write(b'iso')
            remote = MagicMock()
            remote.get_distro.return_value = {'name': 'demo-x86_64'}
            factory = MagicMock()
            factory.get_remote_server.return_value = (remote, 'token')
            with self.app.test_request_context('/cobbler/deleteISO', method='POST',
                                               json={'iso_name': 'demo', 'arch': 'x86_64'}), \
                    patch.object(view, 'upload_dir', upload_dir), \
                    patch.object(view, 'RemoteServer', return_value=factory), \
                    patch.object(view.os.path, 'ismount', return_value=True), \
                    patch.object(view.subprocess, 'run', side_effect=subprocess.CalledProcessError(32, ['umount'])):
                response = view.DeleteISO().post()
            self.assertEqual(500, response.status_code)
            self.assertTrue(os.path.exists(iso_path))
            remote.remove_distro.assert_not_called()


class TestQueryISO(unittest.TestCase):
    def test_reads_architecture_specific_metadata_and_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as upload_dir:
            for filename, data in [('demo-x86_64.iso', b'x86'),
                                   ('demo-x86_64.txt', b'x86-hash'),
                                   ('demo.iso', b'legacy'),
                                   ('demo.txt', b'legacy-hash')]:
                with open(os.path.join(upload_dir, filename), 'wb') as f:
                    f.write(data)
            remote = MagicMock()
            remote.get_distros.return_value = [
                {'name': 'demo-x86_64', 'arch': 'x86_64', 'ctime': 2},
                {'name': 'demo-aarch64', 'arch': 'aarch64', 'ctime': 1}]
            factory = MagicMock()
            factory.get_remote_server.return_value = (remote, 'token')
            with patch.object(view, 'upload_dir', upload_dir), \
                    patch.object(view, 'RemoteServer', return_value=factory):
                result = view.QueryISO().get()
            self.assertEqual([3, 6], [item['iso_size'] for item in result])
            self.assertEqual(['x86-hash', 'legacy-hash'],
                             [item['iso_sha256_value'] for item in result])

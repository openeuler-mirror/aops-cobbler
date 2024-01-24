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
Description: File Util
"""


import hashlib
import os


class FileUtil:
    @staticmethod
    def calculate_file_sha256(file_path):
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                hash_obj = hashlib.new('sha256')
                for chunk in iter(lambda: f.read(2 ** 20), b''):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()

    @staticmethod
    def write_file_content(file_path, content):
        with open(file_path, 'w') as f:
            f.write(content)

    @staticmethod
    def read_file_content(file_path):
        content = ''
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
        return content

    @staticmethod
    def get_file_size(file_path):
        if os.path.exists(file_path):
            return os.stat(file_path).st_size
        return 0

    @staticmethod
    def makedirs(path, mode=0o755, exist_ok=True):
        head, tail = os.path.split(path)
        if not tail:
            head, tail = os.path.split(head)
        if head and tail and not os.path.exists(head):
            FileUtil.makedirs(head, mode, exist_ok=exist_ok)
            cdir = os.curdir
            if isinstance(tail, bytes):
                cdir = bytes(os.curdir, 'ASCII')
            if tail == cdir:  # xxx/newdir/. exists if xxx/newdir exists
                return
        try:
            os.mkdir(path, mode)
        except OSError:
            # Cannot rely on checking for EEXIST, since the operating system
            # could give priority to other errors like EACCES or EROFS
            if not exist_ok or not os.path.isdir(path):
                raise

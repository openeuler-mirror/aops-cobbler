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
import os


def calculate_iso_sha256(file_path):
    with open(file_path, 'rb') as f:
        hash_obj = hashlib.new('sha256')
        for chunk in iter(lambda: f.read(2 ** 20), b''):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def write_iso_sha256(file_path, sha256_code):
    with open(file_path, 'w') as file:
        file.write(sha256_code)


def read_iso_sha256(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            content = f.read()
    return content

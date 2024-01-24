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
Description: Aes Util
"""


from cobbled.conf.constant import ConfigCons
from cryptography.fernet import Fernet, InvalidToken

# 创建加密解密器
cipher_suite = Fernet(ConfigCons.AES_KEY)


class AesUtil:

    @staticmethod
    def encrypy(plaintext):
        # 加密明文
        return cipher_suite.encrypt(bytes(plaintext, 'utf-8')).decode()

    @staticmethod
    def decrypt(ciphertext):
        # 解密密文
        try:
            return cipher_suite.decrypt(bytes(ciphertext, 'utf-8')).decode()
        except InvalidToken:
            return ciphertext

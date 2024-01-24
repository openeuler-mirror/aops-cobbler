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


from flask import jsonify


class ResUtil:

    @staticmethod
    def success(msg: str, data=None):
        if data:
            return jsonify({'code': 200, 'msg': msg, 'data': data})
        else:
            return jsonify({'code': 200, 'msg': msg})

    @staticmethod
    def failed(msg: str, data=None):
        if data:
            return jsonify({'code': 400, 'msg': msg, 'data': data})
        else:
            return jsonify({'code': 400, 'msg': msg})

    @staticmethod
    def success_or_failed(code: int, msg: str, data=None):
        if data:
            return jsonify({'code': code, 'msg': msg, 'data': data})
        else:
            return jsonify({'code': code, 'msg': msg})

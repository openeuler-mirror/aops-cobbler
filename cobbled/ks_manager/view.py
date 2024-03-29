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
Description: Restful APIs for kickstart manager
"""


import json
import os.path
import subprocess

from flask_restful import Resource
from flask import request
from cobbled.log.log import LOGGER
from cobbled.util.response_util import ResUtil
from cobbled.util.validate_util import KsChecker
from cobbled.util.file_util import FileUtil
from cobbled.conf import configuration
from cobbled.conf.constant import KsCons

# 从配置文件里获取ks文件保存地址
ks_dir = os.path.join(configuration.ks.get("HTTP_DIR"), "ks")
if not os.path.exists(ks_dir):
    FileUtil.makedirs(ks_dir)


class AddKickstart(Resource):
    """
    Interface for add kickstart file.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to add kickstart file")
        # 获取并校验请求参数
        ks_name = request.json.get("ks_name")
        ks_content = request.json.get("ks_content")
        check_ks_result = KsChecker.check_ks_name(ks_name) or KsChecker.check_ks_content(ks_content)
        if check_ks_result:
            return check_ks_result

        # 写入ks文件
        ks_full_path = os.path.join(ks_dir, ks_name + ".ks")
        FileUtil.write_file_content(ks_full_path, ks_content)

        # 使用ksvalidator命令校验ks文件是否有语法错误
        check_ks_result = subprocess.run(['ksvalidator', ks_full_path], capture_output=True, text=True)
        if check_ks_result.returncode:
            os.remove(ks_full_path)
            return ResUtil.failed(check_ks_result.stderr)

        LOGGER.info("end to add kickstart file")
        return ResUtil.success(KsCons.ADD_KS_SUCCESS_TIPS)


class UpdateKickstart(Resource):
    """
    Interface for update kickstart file.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to update kickstart file")
        # 获取并校验请求参数
        ks_name = request.json.get("ks_name")
        ks_content = request.json.get("ks_content")
        check_ks_result = KsChecker.check_ks_name(ks_name) or KsChecker.check_ks_content(ks_content)
        if check_ks_result:
            return check_ks_result

        ks_full_path = os.path.join(ks_dir, ks_name + ".ks")
        # 检查文件是否存在
        if not os.path.exists(ks_full_path):
            return ResUtil.failed(KsCons.CHECK_KS_EXITS_TIPS)

        # 先写入临时文件
        ks_full_path_temp = os.path.join(ks_dir, ks_name + "_temp.ks")
        FileUtil.write_file_content(ks_full_path_temp, ks_content)

        # 使用ksvalidator命令校验ks文件是否有语法错误
        check_ks_result = subprocess.run(['ksvalidator', ks_full_path_temp], capture_output=True, text=True)
        os.remove(ks_full_path_temp)
        if check_ks_result.returncode:
            return ResUtil.failed(check_ks_result.stderr)

        # 更新ks文件
        FileUtil.write_file_content(ks_full_path, ks_content)
        LOGGER.info("end to update kickstart file")
        return ResUtil.success(KsCons.UPDATE_KS_SUCCESS_TIPS)


class DeleteKickstart(Resource):
    """
    Interface for delete kickstart file.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to delete kickstart file")
        # 获取并校验请求参数
        ks_name = request.json.get("ks_name")
        check_ks_result = KsChecker.check_ks_name(ks_name)
        if check_ks_result:
            return check_ks_result

        # 删除ks文件
        ks_full_path = os.path.join(ks_dir, ks_name + ".ks")
        if os.path.exists(ks_full_path):
            os.remove(ks_full_path)
        else:
            return ResUtil.failed(KsCons.CHECK_KS_EXITS_TIPS)

        LOGGER.info("end to delete kickstart file")
        return ResUtil.success(KsCons.DELETE_KS_SUCCESS_TIPS)


class QueryKickstart(Resource):
    """
    Interface for query kickstart file.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to query kickstart file")
        ks_name = request.json.get("ks_name")
        ks_list = os.listdir(ks_dir)

        ks_arr = []
        http_addr = "http://" + configuration.cobbler_client.get("IP") + "/ks/"

        for ks in ks_list:
            if ks_name and ks_name not in ks:
                continue
            ks_full_path = os.path.join(ks_dir, ks)
            if os.path.exists(ks_full_path):
                rep_data = {"ks_name": ks,
                            "ks_content": FileUtil.read_file_content(ks_full_path),
                            "ks_address": http_addr + ks}
                ks_arr.append(rep_data)

        # 按照文件修改时间进行降序排列
        ks_arr = sorted(ks_arr, key=lambda x: os.path.getmtime(os.path.join(ks_dir, x.get("ks_name"))), reverse=True)
        LOGGER.info("end to query kickstart file")
        return json.loads(json.dumps(ks_arr))

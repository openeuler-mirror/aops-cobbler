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
Description: Restful APIs for script manager
"""


import json
import os
import subprocess
from io import SEEK_END

from flask_restful import Resource
from flask import request
from cobbled.log.log import LOGGER
from cobbled.conf import configuration
from cobbled.conf.constant import ScriptCons
from cobbled.util.response_util import ResUtil
from cobbled.util.validate_util import ScriptChecker
from cobbled.util.file_util import FileUtil

# 从配置文件里获取脚本文件大小的上限值
max_content_length = configuration.script.get("MAX_CONTENT_LENGTH")

# 从配置文件里获取脚本文件上传地址
upload_dir = configuration.script.get("SCRIPT_DIR")
if not os.path.exists(upload_dir):
    FileUtil.makedirs(upload_dir)


class UploadScript(Resource):
    """
    Interface for upload script file.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to upload script file")
        code = 200
        msg = ScriptCons.UPLOAD_SCRIPT_SUCCESS_TIPS

        # 获取请求参数
        script_file = request.files.get('script_file')
        script_name = request.form.get('script_name')

        # 校验请求参数
        check_script_result = ScriptChecker.check_script_name(script_name) or ScriptChecker.check_script_file(
            script_file)
        if check_script_result:
            return check_script_result

        script_file.seek(0, SEEK_END)
        # 校验上传文件大小是否超过上限
        if script_file.tell() > max_content_length:
            return ResUtil.failed(ScriptCons.CHECK_SCRIPT_SIZE_TIPS + str(max_content_length//1024) + 'MB')

        script_full_path_temp = os.path.join(upload_dir, script_name + "_temp.sh")
        try:
            # 先写入临时文件
            script_file.stream.seek(0)
            script_file.save(script_full_path_temp)

            # 使用bash -n命令校验脚本文件是否有语法错误
            check_script_result = subprocess.run(['bash', '-n', script_full_path_temp], capture_output=True, text=True)
            if check_script_result.returncode:
                return ResUtil.failed(check_script_result.stderr)

            # 写入该脚本文件
            script_file.stream.seek(0)
            script_file.save(os.path.join(upload_dir, script_name + ".sh"))
            LOGGER.info("end to upload script file")
        except Exception as e:
            LOGGER.error(f'fail to upload script file:{str(e)}')
            code = 500
            msg = str(e)
        finally:
            if os.path.exists(script_full_path_temp):
                os.remove(script_full_path_temp)

        return ResUtil.success_or_failed(code, msg)


class QueryScript(Resource):
    """
    Interface for query script file.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to query script file")
        script_name = request.json.get("script_name")
        script_list = os.listdir(upload_dir)

        script_arr = []
        for script in script_list:
            if script_name and script_name not in script:
                continue
            script_full_path = os.path.join(upload_dir, script)
            if os.path.exists(script_full_path):
                rep_data = {"script_name": script,
                            "script_content": FileUtil.read_file_content(script_full_path)}
                script_arr.append(rep_data)

        # 按照文件修改时间进行降序排列
        script_arr = sorted(script_arr, key=lambda x: os.path.getmtime(os.path.join(upload_dir, x.get("script_name"))),
                            reverse=True)
        LOGGER.info("end to query script file")
        return json.loads(json.dumps(script_arr))


class DeleteScript(Resource):
    """
    Interface for delete script file.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to delete script file")

        # 获取请求参数
        script_name = request.json.get('script_name')
        check_script_result = ScriptChecker.check_script_name(script_name)
        if check_script_result:
            return check_script_result

        # 删除脚本文件
        script_full_path = os.path.join(upload_dir, script_name + ".sh")
        if os.path.exists(script_full_path):
            os.remove(script_full_path)
        else:
            return ResUtil.failed(ScriptCons.CHECK_SCRIPT_EXITS_TIPS)

        LOGGER.info("end to delete script file")
        return ResUtil.success(ScriptCons.DELETE_SCRIPT_SUCCESS_TIPS)

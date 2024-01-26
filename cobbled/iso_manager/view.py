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
Description: Restful APIs for iso manager
"""


import json
import os

from flask_restful import Resource
from flask import request
from cobbled.log.log import LOGGER
from cobbled.conf import configuration
from cobbled.conf.constant import ISOCons, InstallCons
from cobbled.server.remote import RemoteServer
from cobbled.util.response_util import ResUtil
from cobbled.util.validate_util import ISOChecker
from cobbled.util.file_util import FileUtil

# 从配置文件里获取镜像文件上传地址
upload_dir = configuration.iso.get("UPLOAD_DIR")
if not os.path.exists(upload_dir):
    FileUtil.makedirs(upload_dir)


class UploadISO(Resource):
    """
    Interface for upload iso file.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to upload iso file")
        code = 200
        msg = ISOCons.UPLOAD_ISO_SUCCESS_TIPS

        # 获取请求参数
        iso_file = request.files['file']
        iso_name = request.form.get('iso_name')
        arch = request.form.get('arch')

        # 校验请求参数
        check_iso_result = ISOChecker.check_iso_name(iso_name) or ISOChecker.check_iso_arch(
            arch) or ISOChecker.check_iso_suffix(iso_file.filename)
        if check_iso_result:
            return check_iso_result

        try:
            # 判断该镜像文件是否已经上传
            distro_name = iso_name + "-" + arch
            remote_server, token = RemoteServer().get_remote_server()
            target = remote_server.get_distro(distro_name)
            if target and target != '~':
                LOGGER.error("The iso file already exists in remote cobbler server.")
                return ResUtil.failed(ISOCons.CHECK_ISO_EXITS_TIPS)

            # 写入该iso文件
            iso_full_path = os.path.join(upload_dir, iso_name + ".iso")
            if not os.path.exists(iso_full_path):
                iso_file.save(iso_full_path)
                # 计算iso文件的sha256值
                sha256_value = FileUtil.calculate_file_sha256(iso_full_path)
                # 将iso文件的sha256值写入同名文件中
                FileUtil.write_file_content(iso_full_path.replace('.iso', '.txt'), sha256_value)

            # 挂载该iso文件
            mount_dir = '/mnt/' + distro_name
            os.makedirs(mount_dir, mode=0o644, exist_ok=True)
            os.system('umount ' + mount_dir)
            os.system('mount ' + iso_full_path + ' ' + mount_dir)

            # 调用Cobbler API导入iso文件到Cobbler服务端
            options = {
                "name": iso_name,
                "path": mount_dir,
                "breed": "",
                "arch": arch
            }
            remote_server.background_import(options, token)
            LOGGER.info("end to upload iso file")
        except Exception as e:
            LOGGER.error(f'fail to upload iso file:{str(e)}')
            code = 500
            msg = str(e)

        return ResUtil.success_or_failed(code, msg)


class QueryISO(Resource):
    """
    Interface for query iso file.
    Restful API: POST
    """

    def get(self):
        LOGGER.info("start to query iso file")
        rep_arr = []
        try:
            remote_server, token = RemoteServer().get_remote_server()
            distros = remote_server.get_distros()
            # 按照导入时间进行降序排列
            distros = sorted(distros, key=lambda x: x.get("ctime"), reverse=True)
            for distro in distros:
                arch = distro["arch"]
                iso_name = distro["name"]
                iso_name = iso_name[:iso_name.rfind('-' + arch)]
                rep_data = {"iso_name": iso_name + '.iso',
                            "arch": arch,
                            "iso_size": FileUtil.get_file_size(os.path.join(upload_dir, iso_name + '.iso')),
                            "iso_sha256_value": FileUtil.read_file_content(os.path.join(upload_dir, iso_name + '.txt'))}
                rep_arr.append(rep_data)
        except Exception as e:
            LOGGER.error(f'fail to query iso file:{str(e)}')
        return json.loads(json.dumps(rep_arr))


class DeleteISO(Resource):
    """
    Interface for delete iso file.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to delete iso file")
        code = 200
        msg = ISOCons.DELETE_ISO_SUCCESS_TIPS

        # 获取请求参数
        iso_name = request.json.get('iso_name')
        arch = request.json.get('arch')
        check_iso_result = ISOChecker.check_iso_name(iso_name) or ISOChecker.check_iso_arch(arch)
        if check_iso_result:
            return check_iso_result

        try:
            # 从Cobbler服务端删除
            distro_name = iso_name + "-" + arch
            remote_server, token = RemoteServer().get_remote_server()
            target = remote_server.get_distro(distro_name)
            if not target or target == '~':
                LOGGER.error("The iso file not exists in remote cobbler server!")
                return ResUtil.failed(InstallCons.CHECK_ISO_EXITS_TIPS)

            remote_server.remove_profile(distro_name, token)
            remote_server.remove_distro(distro_name, token)
            remote_server.sync(token)

            # 取消挂载，删除本地镜像文件
            os.system('umount ' + '/mnt/' + distro_name)
            iso_absolute_path = os.path.join(upload_dir, iso_name + '.iso')
            txt_absolute_path = iso_absolute_path.replace('.iso', '.txt')
            iso_mount_path = os.path.join('/mnt/', distro_name)
            if os.path.exists(iso_mount_path):
                os.rmdir(iso_mount_path)

            if os.path.exists(iso_absolute_path):
                os.remove(iso_absolute_path)

            if os.path.exists(txt_absolute_path):
                os.remove(txt_absolute_path)

            LOGGER.info("end to delete iso file")
        except Exception as e:
            LOGGER.error(f'fail to delete iso file:{str(e)}')
            code = 500
            msg = str(e)

        return ResUtil.success_or_failed(code, msg)

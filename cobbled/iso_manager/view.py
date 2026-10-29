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


import os
import stat
import subprocess
import tempfile

from flask import request
from flask_restful import Resource

from cobbled.conf import configuration
from cobbled.conf.constant import InstallCons, ISOCons
from cobbled.log.log import LOGGER
from cobbled.server.remote import RemoteServer
from cobbled.util.file_util import FileUtil
from cobbled.util.request_util import JsonObjectResource
from cobbled.util.response_util import ResUtil
from cobbled.util.validate_util import ISOChecker

# 从配置文件里获取镜像文件上传地址
upload_dir = configuration.iso.get("UPLOAD_DIR")
if not os.path.exists(upload_dir):
    FileUtil.makedirs(upload_dir)


def iso_paths(iso_name, arch):
    base = os.path.join(upload_dir, iso_name + '-' + arch)
    return base + '.iso', base + '.txt'


def existing_iso_paths(iso_name, arch):
    paths = iso_paths(iso_name, arch)
    if os.path.exists(paths[0]):
        return paths
    legacy = os.path.join(upload_dir, iso_name)
    return legacy + '.iso', legacy + '.txt'


def save_iso(iso_file, iso_path, txt_path):
    """Publish a complete ISO and its checksum from temporary files."""
    temporary_iso = None
    temporary_txt = None
    try:
        iso_fd, temporary_iso = tempfile.mkstemp(prefix='.iso-', dir=upload_dir)
        os.close(iso_fd)
        txt_fd, temporary_txt = tempfile.mkstemp(prefix='.sha-', dir=upload_dir)
        os.close(txt_fd)
        iso_file.save(temporary_iso)
        checksum = FileUtil.calculate_file_sha256(temporary_iso)
        FileUtil.write_file_content(temporary_txt, checksum)
        os.chmod(temporary_iso, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        os.chmod(temporary_txt, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        os.replace(temporary_iso, iso_path)
        os.replace(temporary_txt, txt_path)
    finally:
        for path in (temporary_iso, temporary_txt):
            if path and os.path.exists(path):
                os.remove(path)


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
        iso_file = request.files.get('file')
        if iso_file is None or not iso_file.filename:
            return ResUtil.failed('The iso file can not be empty.')
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
            iso_full_path, txt_path = iso_paths(iso_name, arch)
            mount_dir = '/mnt/' + distro_name
            if os.path.ismount(mount_dir):
                subprocess.run(["umount", mount_dir], check=True,
                               capture_output=True, text=True)
            save_iso(iso_file, iso_full_path, txt_path)

            # 挂载该iso文件
            os.makedirs(mount_dir, mode=0o755, exist_ok=True)
            try:
                subprocess.run(
                    ["mount", "-o", "loop,ro", iso_full_path, mount_dir],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except (subprocess.CalledProcessError, OSError) as e:
                LOGGER.error("fail to mount iso file %s: %s", iso_full_path, str(e))
                return ResUtil.success_or_failed(500, ISOCons.MOUNT_ISO_FAILED_TIPS)

            # 调用Cobbler API导入iso文件到Cobbler服务端
            options = {
                "name": iso_name,
                "path": mount_dir,
                "breed": "",
                "arch": arch
            }
            try:
                remote_server.background_import(options, token)
            except Exception:
                # A failed import may not create a distro, so leave the mount
                # available for a later retry whenever cleanup succeeds.
                try:
                    subprocess.run(["umount", mount_dir], check=True,
                                   capture_output=True, text=True)
                except (subprocess.CalledProcessError, OSError) as cleanup_error:
                    LOGGER.error("fail to clean up iso mount %s: %s", mount_dir, cleanup_error)
                raise
            LOGGER.info("end to upload iso file")
        except Exception as e:
            LOGGER.error(f'fail to upload iso file:{str(e)}')
            code = 500
            msg = str(e)

        return ResUtil.success_or_failed(code, msg)


class QueryISO(Resource):
    """
    Interface for query iso file.
    Restful API: GET
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
                idx = iso_name.rfind('-' + arch)
                if idx != -1:
                    iso_name = iso_name[:idx]
                iso_path, txt_path = existing_iso_paths(iso_name, arch)
                rep_data = {"iso_name": iso_name + '.iso',
                            "arch": arch,
                            "iso_size": FileUtil.get_file_size(iso_path),
                            "iso_sha256_value": FileUtil.read_file_content(txt_path)}
                rep_arr.append(rep_data)
        except Exception as e:
            LOGGER.error(f'fail to query iso file:{str(e)}')
        return rep_arr


class DeleteISO(JsonObjectResource):
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
            has_distro = bool(target and target != '~')
            iso_absolute_path, txt_absolute_path = iso_paths(iso_name, arch)
            iso_mount_path = os.path.join('/mnt/', distro_name)
            legacy_path = os.path.join(upload_dir, iso_name + '.iso')
            if not has_distro and not os.path.ismount(iso_mount_path) and \
                    not os.path.exists(iso_absolute_path) and not os.path.exists(legacy_path):
                LOGGER.error("The iso file not exists in remote cobbler server!")
                return ResUtil.failed(InstallCons.CHECK_ISO_EXITS_TIPS)

            # Read before mutation so a lookup failure cannot turn a completed
            # deletion into a reported failure. Match the exact base name.
            other_distros = remote_server.get_distros()
            legacy_in_use = any(
                distro.get('name') != distro_name and
                distro.get('name') == iso_name + '-' + str(distro.get('arch')) and
                not os.path.exists(iso_paths(iso_name, distro.get('arch'))[0])
                for distro in other_distros
            )

            if os.path.ismount(iso_mount_path):
                subprocess.run(["umount", iso_mount_path], check=True,
                               capture_output=True, text=True)

            if has_distro:
                remote_server.remove_profile(distro_name, token)
                remote_server.remove_distro(distro_name, token)
                remote_server.sync(token)

            if os.path.exists(iso_mount_path):
                os.rmdir(iso_mount_path)

            if os.path.exists(iso_absolute_path):
                os.remove(iso_absolute_path)

            if os.path.exists(txt_absolute_path):
                os.remove(txt_absolute_path)

            # Legacy files are shared by all architectures of the same name.
            if not legacy_in_use:
                legacy_base = os.path.join(upload_dir, iso_name)
                for path in (legacy_base + '.iso', legacy_base + '.txt'):
                    if os.path.exists(path):
                        os.remove(path)

            LOGGER.info("end to delete iso file")
        except Exception as e:
            LOGGER.error(f'fail to delete iso file:{str(e)}')
            code = 500
            msg = str(e)

        return ResUtil.success_or_failed(code, msg)

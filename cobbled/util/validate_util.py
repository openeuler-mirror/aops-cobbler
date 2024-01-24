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
Description: Validate Util
"""


import os

import validators

from cobbled.conf import configuration
from cobbled.conf.constant import ISOCons, KsCons, HostCons, ScriptCons
import re

from cobbled.util.aes_util import AesUtil
from cobbled.util.response_util import ResUtil


class ISOChecker:

    @staticmethod
    def check_iso_name(iso_name):
        # iso_name不能为空，且必须满足26个大小写字母、数字、下划线、中划线
        pattern = re.compile('^[A-Za-z0-9_-]+$')
        if not iso_name or not pattern.match(iso_name) or len(str(iso_name)) > 128:
            return ResUtil.failed(ISOCons.CHECK_ISO_NAME_TIPS)
        arch_list = {"-x86", "_x86", "-aarch64", "_aarch64"}
        for arch in arch_list:
            if arch in iso_name:
                return ResUtil.failed(ISOCons.CHECK_ISO_NAME_TIPS)

    @staticmethod
    def check_iso_arch(arch):
        # 从配置文件里获取镜像架构的值，取值为x86_64、aarch64
        arch_list = configuration.iso.get("ARCH").split(",")
        if not arch or arch not in arch_list:
            return ResUtil.failed(ISOCons.CHECK_ISO_ARCH_TIPS)

    @staticmethod
    def check_iso_suffix(file_name):
        # 校验上传文件后缀是否是.iso文件
        base, ext = os.path.splitext(file_name)
        if ext != '.iso':
            return ResUtil.failed(ISOCons.CHECK_ISO_SUFFIX_TIPS)


class KsChecker:

    @staticmethod
    def check_ks_name(ks_name):
        # ks_name不能为空，且必须满足26个大小写字母、数字、下划线、中划线
        pattern = re.compile('^[A-Za-z0-9_-]+$')
        if not ks_name or not pattern.match(ks_name) or len(str(ks_name)) > 128:
            return ResUtil.failed(KsCons.CHECK_KS_NAME_TIPS)

    @staticmethod
    def check_ks_content(ks_content):
        if not ks_content:
            return ResUtil.failed(KsCons.CHECK_KS_CONTENT_TIPS)


class InstallChecker:
    @staticmethod
    def check_host_list(host_list):
        if not host_list or len(host_list) > 100:
            return ResUtil.failed(HostCons.CHECK_HOST_LIST_TIPS)
        for host in host_list:
            check_result = HostChecker.check_bmc_ip(host.get("bmc_ip"))
            if check_result:
                return check_result


class HostChecker:

    @staticmethod
    def check_page_no_and_page_size(page_no, page_size):
        # page_no、page_size不能为空，且必须是大于1的整数
        pattern = re.compile('^[1-9][0-9]*$')
        if not pattern.match(str(page_no)):
            return ResUtil.failed(HostCons.CHECK_PAGE_NO_TIPS)

        if not pattern.match(str(page_size)) or int(page_size) > 100:
            return ResUtil.failed(HostCons.CHECK_PAGE_SIZE_TIPS)

    @staticmethod
    def check_host_id(host_id):
        pattern = re.compile('^[1-9][0-9]*$')
        # host_id不能为空，且必须是大于1的整数
        if not pattern.match(str(host_id)):
            return ResUtil.failed(HostCons.CHECK_HOST_ID_TIPS)

    @staticmethod
    def check_host_name(host_name):
        # host_name不能为空，且且必须满足相应规则
        # 1.主机名长度不超过63个字符；
        # 2.主机名中只能包含英文字母（A - Z）、数字（0 - 9）和连字符（-），不能包含其他字符；
        # 3.主机名的开头和结尾不得出现连字符（-）；
        if not validators.hostname(host_name):
            return ResUtil.failed(HostCons.CHECK_HOST_NAME_TIPS)

    @staticmethod
    def check_bmc_ip(bmc_ip):
        # bmc_ip不能为空，且必须满足相应规则
        if not validators.ip_address.ipv4(bmc_ip):
            return ResUtil.failed(HostCons.CHECK_BMC_IP_TIPS)

    @staticmethod
    def check_bmc_user_name(bmc_user_name):
        # bmc_user_name不能为空，且长度不超过128个字符
        if not bmc_user_name or len(str(bmc_user_name)) > 128:
            return ResUtil.failed(HostCons.CHECK_BMC_USER_NAME_TIPS)

    @staticmethod
    def check_bmc_passwd(bmc_passwd):
        # bmc_passwd不能为空，且长度不超过128个字符
        if not bmc_passwd or len(str(bmc_passwd)) > 128:
            return ResUtil.failed(HostCons.CHECK_BMC_PASSWD_TIPS)

    @staticmethod
    def check_host_status(status):
        # status不能为空，且只能是0，1，2，3，4
        # 0表示裸机，1表示已安装，2表示已纳管，3表示装机中，4表示安装失败
        if status not in {0, 1, 2, 3, 4}:
            return ResUtil.failed(HostCons.CHECK_HOST_STATUS_TIPS)

    @staticmethod
    def check_bmc_connection(host):
        if configuration.host.get("CHECK_BMC_CONNECTION") == 0:
            return
        bmc_ip = host.get("bmc_ip")
        bmc_user_name = host.get("bmc_user_name")
        bmc_passwd = AesUtil.decrypt(host.get("bmc_passwd"))
        ipmi_command = "ipmitool -H " + bmc_ip + " -I lanplus -U " + bmc_user_name + " -P '" + bmc_passwd + "'"
        if os.system(ipmi_command + ' power status'):
            return ResUtil.failed(HostCons.CHECK_BMC_CONNECTION_TIPS)

    @staticmethod
    def check_bmc(host):
        return HostChecker.check_bmc_ip(host.get("bmc_ip")) or HostChecker.check_bmc_user_name(
            host.get("bmc_user_name")) or HostChecker.check_bmc_passwd(
            host.get("bmc_passwd")) or HostChecker.check_bmc_connection(host)

    @staticmethod
    def check_host_mac(host_mac):
        # Mac地址不能为空，且必须满足相应规则
        if not validators.mac_address(host_mac):
            return ResUtil.failed(HostCons.CHECK_HOST_MAC_TIPS)


class ScriptChecker:

    @staticmethod
    def check_script_name(script_name):
        # script_name不能为空，且必须满足26个大小写字母、数字、下划线、中划线
        pattern = re.compile('^[A-Za-z0-9_-]+$')
        if not script_name or not pattern.match(script_name) or len(str(script_name)) > 128:
            return ResUtil.failed(ScriptCons.CHECK_SCRIPT_NAME_TIPS)

    @staticmethod
    def check_script_file(script_file):
        # 校验上传脚本文件不能为空
        if script_file is None or script_file.filename == '':
            return ResUtil.failed(ScriptCons.CHECK_SCRIPT_FILE_TIPS)

        # 校验上传文件后缀是否是.sh文件
        base, ext = os.path.splitext(script_file.filename)
        if ext != '.sh':
            return ResUtil.failed(ScriptCons.CHECK_SCRIPT_SUFFIX_TIPS)

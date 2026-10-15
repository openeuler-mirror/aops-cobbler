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
Description: Restful APIs for auto install os
"""


import os.path
import zipfile
from datetime import datetime
from io import BytesIO

from flask import request, send_file

from cobbled.conf import configuration
from cobbled.conf.constant import HostCons, InstallCons
from cobbled.database.host import HostProxy
from cobbled.install_manager.power import IPMIPower
from cobbled.install_manager.workflow import InstallationSettings, InstallationWorkflow
from cobbled.log.log import LOGGER
from cobbled.server.remote import RemoteServer
from cobbled.util.request_util import JsonObjectResource
from cobbled.util.response_util import ResUtil
from cobbled.util.validate_util import (
    HostChecker,
    InstallChecker,
    ISOChecker,
    KsChecker,
    ScriptChecker,
)

# 从配置文件里获取ks文件保存地址
ks_dir = os.path.join(configuration.ks.get("HTTP_DIR"), "ks")

# 从配置文件里获取脚本文件保存地址
script_dir = configuration.script.get("SCRIPT_DIR")

# 从配置文件里获取操作系统已安装时间的上限值
os_installed_time = configuration.host.get("OS_INSTALLED_TIME")

# 从配置文件里获取操作系统安装日志存放路径
os_install_log_dir = configuration.host.get("OS_INSTALL_LOG_DIR")

# 从配置文件里获取操作系统安装可使用的IP范围
os_start_ip = configuration.host.get("OS_START_IP")
os_end_ip = configuration.host.get("OS_END_IP")

# 从配置文件里获取装机网段掩码
subnet_mask = configuration.host.get("SUBNET_MASK")

HOST_SCHEDULER_BATCH_SIZE = 100


class AutoInstall(JsonObjectResource):
    """
    Interface for auto install os.
    Restful API: POST
    """

    def post(self):
        # 1，获取请求参数
        host_list = request.json.get("host_list")
        ks_name = request.json.get("ks_name")
        iso_name = request.json.get("iso_name")
        arch = request.json.get("arch")
        script_name = request.json.get("script_name")
        install_rpm = request.json.get("install_rpm")

        # 2，基本校验
        check_result = ISOChecker.check_iso_name(iso_name) or ISOChecker.check_iso_arch(
            arch) or KsChecker.check_ks_name(ks_name) or InstallChecker.check_host_list(host_list)
        if check_result:
            return check_result

        if script_name is not None and script_name != "":
            check_result = ScriptChecker.check_script_name(script_name)
            if check_result:
                return check_result

        workflow = InstallationWorkflow(
            InstallationSettings(
                ks_dir=ks_dir,
                script_dir=script_dir,
                client_ip=configuration.cobbler_client.get("IP"),
                port=configuration.cobbler_client.get("PORT"),
                subnet_mask=subnet_mask,
                os_start_ip=os_start_ip,
                os_end_ip=os_end_ip,
            ),
            connect_cobbler=lambda: RemoteServer().get_remote_server(),
            host_store=HostProxy,
            power=IPMIPower(),
        )
        result = workflow.run(
            host_list=host_list, ks_name=ks_name, iso_name=iso_name, arch=arch,
            script_name=script_name, install_rpm=install_rpm,
        )
        return ResUtil.success_or_failed(result.code, result.msg, result.data)


class Notify(JsonObjectResource):
    """
    Interface for notify.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to notify aops-cobbler to update host info.")
        # 获取并校验请求参数
        bmc_ip = request.json.get("bmc_ip")
        service_ip = request.environ.get("REMOTE_ADDR")
        check_result = HostChecker.check_bmc_ip(bmc_ip)
        if check_result:
            return check_result

        # 根据bmc_ip更新主机相关信息
        with HostProxy() as host_proxy:
            query_result, hosts = host_proxy.query_host_by_bmc_ip(bmc_ip)
            if not query_result:
                return ResUtil.failed(HostCons.QUERY_HOST_FAILED_TIPS)
            if not hosts:
                return ResUtil.failed(HostCons.CHECK_HOST_EXITS_TIPS)

            host_info = {
                "host_id": hosts[0].host_id,
                "host_name": hosts[0].host_name,
                "bmc_ip": hosts[0].bmc_ip,
                "bmc_user_name": hosts[0].bmc_user_name,
                "bmc_passwd": hosts[0].bmc_passwd,
                "host_ip": service_ip,
                "status": 1,
            }
            system_name = hosts[0].host_name + "-" + str(hosts[0].host_id)

            update_result = host_proxy.update_host_info(host_info)
            if not update_result:
                return ResUtil.failed(HostCons.UPDATE_HOST_FAILED_TIPS)

        # 根据名称删除对应的cobbler system，清理DHCP白名单
        remote_server, token = RemoteServer().get_remote_server()
        remote_server.remove_system(system_name, token)
        remote_server.sync_dhcp(token)

        LOGGER.info("end to notify aops-cobbler to update host info.")
        return ResUtil.success(InstallCons.AUTO_INSTALL_NOTIFY_TIPS)


def host_scheduler():
    with HostProxy() as host_proxy:
        return _check_installation_status(host_proxy)


def _check_installation_status(host_proxy):
    LOGGER.info("start to execute scheduled tasks to check if the os has failed to install.")
    failed_hosts = []
    after_update_time = None
    after_host_id = None

    while True:
        query_result, hosts = host_proxy.query_hosts_by_status_batch(
            3,
            HOST_SCHEDULER_BATCH_SIZE,
            after_update_time,
            after_host_id,
        )
        if not query_result:
            LOGGER.error("Query installing hosts failed during scheduled task.")
            break
        if not hosts:
            break

        # Preserve the cursor before updates expire and refresh ORM objects.
        # MySQL advances update_time via ON UPDATE CURRENT_TIMESTAMP when a
        # host status changes, which would otherwise move this cursor past
        # unprocessed hosts from the next batch.
        after_update_time = hosts[-1].update_time
        after_host_id = hosts[-1].host_id

        for host in hosts:
            interval_seconds = (datetime.now() - host.update_time).total_seconds()
            if interval_seconds < 300:
                continue

            # 检查日志文件是否存在，如果5分钟后安装日志还未生成，则说明已经安装失败。
            # 状态为装机中，日志文件也已经生成，但是日志文件内容却不再更新，则说明也是安装失败的
            # 如果安装时间已经超过了30分钟，状态依然是装机中，则按照安装失败来处理。
            os_install_log_path = os.path.join(
                os_install_log_dir,
                host.host_name + "-" + str(host.host_id) + ".log")
            if not os.path.exists(os_install_log_path) \
                    or (datetime.now() - datetime.fromtimestamp(
                        os.path.getmtime(os_install_log_path))).total_seconds() > 120 \
                    or interval_seconds > os_installed_time * 60:
                host_info = {
                    "host_id": host.host_id,
                    "status": 4
                }
                if host_proxy.update_host_info(host_info):
                    failed_hosts.append(host)

        if len(hosts) < HOST_SCHEDULER_BATCH_SIZE:
            break

    # 根据名称删除对应的cobbler system，清理DHCP白名单
    if failed_hosts:
        remote_server, token = RemoteServer().get_remote_server()
        for host in failed_hosts:
            remote_server.remove_system(host.host_name + "-" + str(host.host_id), token)
        remote_server.sync_dhcp(token)

    LOGGER.info("end to execute scheduled tasks to check if the os has failed to install.")


class GetInstallLogFile(JsonObjectResource):
    """
    Interface for get os install log file.
    Restful API: POST
    """

    def post(self):
        # 获取请求参数
        if not request.json:
            return ResUtil.failed(InstallCons.CHECK_LOG_FILE_NAME_TIPS)

        log_file_name = request.json.get("log_file_name")
        if not log_file_name or not isinstance(log_file_name, str) or not log_file_name.strip():
            return ResUtil.failed(InstallCons.CHECK_LOG_FILE_NAME_TIPS)

        log_file_name = log_file_name.strip()
        # 防御路径遍历：禁止包含目录分隔符或路径穿越字符
        if os.path.basename(log_file_name) != log_file_name or ".." in log_file_name or "/" in log_file_name or "\\" in log_file_name:
            return ResUtil.failed(InstallCons.CHECK_LOG_FILE_EXITS_TIPS)

        expected_base_dir = os.path.abspath(os_install_log_dir)
        os_install_log_path = os.path.abspath(os.path.join(expected_base_dir, log_file_name + ".log"))

        # 校验解析后的路径是否严格在目标日志目录范围内
        try:
            common = os.path.commonpath([expected_base_dir, os_install_log_path])
            if common != expected_base_dir or os_install_log_path == expected_base_dir:
                return ResUtil.failed(InstallCons.CHECK_LOG_FILE_EXITS_TIPS)
        except ValueError:
            return ResUtil.failed(InstallCons.CHECK_LOG_FILE_EXITS_TIPS)

        # 检查日志文件是否存在
        if not os.path.exists(os_install_log_path) or not os.path.isfile(os_install_log_path):
            return ResUtil.failed(InstallCons.CHECK_LOG_FILE_EXITS_TIPS)

        # 对日志文件进行内存中压缩，避免在磁盘产生临时文件堆积
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(os_install_log_path, arcname=log_file_name + ".log")
        zip_buffer.seek(0)

        response = send_file(zip_buffer, mimetype="application/octet-stream")
        response.headers['Content-Disposition'] = f'attachment; filename={log_file_name}.zip'
        return response

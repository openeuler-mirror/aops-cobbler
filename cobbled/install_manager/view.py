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


import ipaddress
import os.path
import re
import subprocess
import zipfile
from datetime import datetime
from io import BytesIO

from flask import request, send_file

from cobbled.conf import configuration
from cobbled.conf.constant import HostCons, InstallCons, KsCons, ScriptCons
from cobbled.database.host import HostProxy
from cobbled.log.log import LOGGER
from cobbled.server.remote import RemoteServer
from cobbled.util.aes_util import AesUtil
from cobbled.util.file_util import FileUtil
from cobbled.util.request_util import JsonObjectResource
from cobbled.util.response_util import ResUtil
from cobbled.util.validate_util import (
    HostChecker,
    InstallChecker,
    ISOChecker,
    KsChecker,
    run_ipmitool,
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

_LEGACY_PXE_VALUE_ARGUMENT = re.compile(r"(?<!\S)(ks|repo)=")
_LEGACY_PXE_FLAG_ARGUMENT = re.compile(r"(?<!\S)kssendmac(?=\s|$)")
HOST_SCHEDULER_BATCH_SIZE = 100


def prefix_pxe_boot_arguments(content):
    """Add the Anaconda ``inst.`` prefix to legacy PXE boot arguments."""
    content = _LEGACY_PXE_VALUE_ARGUMENT.sub(
        lambda match: "inst." + match.group(0), content)
    return _LEGACY_PXE_FLAG_ARGUMENT.sub("inst.kssendmac", content)


def render_after_os_installed_script(template, client_ip, port, subnet_mask, install_rpm=None):
    """Render values that are only known when an installation is started."""
    rendered = template.replace("127.0.0.1", client_ip).replace("8888", str(port))
    rendered = rendered.replace("127.0.0.254", get_default_gateway(client_ip, subnet_mask))
    rendered = rendered.replace("s_u_b_n_e_t_m_a_s_k", str(subnet_mask))
    if install_rpm:
        rendered = rendered.replace("r_p_m_s", install_rpm.replace(',', ' '), 1)
    return rendered


def update_pxe_config_files(config_dir=InstallCons.PXE_CONFIG_DIR):
    """Update regular PXE config files without invoking a shell."""
    updated_count = 0
    with os.scandir(config_dir) as entries:
        config_paths = [
            entry.path for entry in entries
            if not entry.name.startswith(".") and entry.is_file(follow_symlinks=False)
        ]

    for config_path in config_paths:
        with open(config_path, "r+", encoding="utf-8") as config_file:
            content = config_file.read()
            updated_content = prefix_pxe_boot_arguments(content)
            if updated_content == content:
                continue

            config_file.seek(0)
            config_file.write(updated_content)
            config_file.truncate()
            updated_count += 1

    return updated_count


class AutoInstall(JsonObjectResource):
    """
    Interface for auto install os.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to auto install")
        code = 200
        msg = InstallCons.AUTO_INSTALL_SUCCESS_TIPS
        result_list = []

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

        try:
            # 3，检查ks文件是否存在
            ks_full_path = os.path.join(ks_dir, ks_name + ".ks")
            if not os.path.exists(ks_full_path):
                return ResUtil.failed(KsCons.CHECK_KS_EXITS_TIPS)

            # 4，如果脚本名称不为空，则校验脚本文件是否存在
            if script_name:
                script_full_path = os.path.join(script_dir, script_name + ".sh")
                if not os.path.exists(script_full_path):
                    return ResUtil.failed(ScriptCons.CHECK_SCRIPT_EXITS_TIPS)

            # 5，如果install_rpm不为空，则检查rpm包是否存在
            if install_rpm:
                rpm_list = install_rpm.split(",")
                for rpm in rpm_list:
                    check_rpm_result = subprocess.run(['yum', 'search', rpm], capture_output=True, text=True)
                    if check_rpm_result.returncode or 'No matches found' in check_rpm_result.stderr:
                        return ResUtil.failed(InstallCons.CHECK_RPM_EXITS_TIPS + rpm)

            # 6，判断该镜像文件是否已经上传
            distro_name = iso_name + "-" + arch
            remote_server, token = RemoteServer().get_remote_server()
            target = remote_server.get_distro(distro_name)
            if not target or target == '~':
                LOGGER.error("The iso file not exists in remote cobbler server.")
                return ResUtil.failed(InstallCons.CHECK_ISO_EXITS_TIPS)

            # 7，获取该镜像安装所使用的ks文件，读取本地ks文件内容
            profile = remote_server.get_profile(distro_name)
            ks_content = FileUtil.read_file_content(ks_full_path)

            # 8，在ks内容中添加系统安装日志转发配置
            client_ip = configuration.cobbler_client.get('IP')
            port = configuration.cobbler_client.get('PORT')
            ks_content += InstallCons.INSTALL_LOG_FORWARD_CMD.replace('ip_addr', client_ip)

            # 读取操作系统安装完成以后需要执行的脚本:ipmitool等自定义rpm包的安装
            # 在ks文件内容中添加调用通知接口内容，用于在操作系统安装完成后更新主机状态，否则aops-cobbler服务将无法知道操作系统是否已经安装完成
            after_os_installed = FileUtil.read_file_content("/opt/aops/script/after_os_installed.sh")
            after_os_installed = render_after_os_installed_script(
                after_os_installed, client_ip, port, subnet_mask, install_rpm)
            ks_content = ks_content + "\n%post\n" + after_os_installed + "\n%end\n"

            # 11，将自定义脚本内容添加到在ks内容中
            if script_name:
                script_content = FileUtil.read_file_content(script_full_path)
                ks_content = ks_content + "\n%post\n" + script_content + "\n%end\n"

            # 12，将ks内容更新到Cobbler服务端ks文件中
            write_result = remote_server.write_autoinstall_template(profile["autoinstall"], ks_content, token)
            if not write_result:
                LOGGER.error("Write autoinstall ks template to cobbler server error.")
                return ResUtil.failed(InstallCons.WRITE_AUTOINSTALL_KS_TIPS)

            # 13，设置当前镜像PXE menu启用，其他镜像PXE menu不启用
            profiles = remote_server.get_profiles()
            for pro in profiles:
                enable_menu = '1' if pro["name"] == distro_name else '0'
                modify_result = remote_server.modify_profile("profile::" + pro["name"], 'enable_menu', enable_menu,
                                                             token)
                if not modify_result:
                    LOGGER.error("Modify cobbler server profile to set enable pxe menu error.")
                    return ResUtil.failed(InstallCons.SET_ENABLE_PXE_TIPS)
                # 保存profile
                remote_server.save_profile("profile::" + pro["name"], token)

            # 14， Cobbler服务端同步操作
            if not remote_server.sync(token):
                LOGGER.error("Cobbler sync error.")
                return ResUtil.failed(InstallCons.COBBLER_SYNC_TIPS)

            host_proxy = HostProxy()
            host_ip_list = []  # 记录已经使用的IP地址
            for host in host_list:
                host["result"] = "failed"
                result_list.append(host)

                # 15，检查当前bmc_ip是否存在
                query_result, hosts = host_proxy.query_host_by_bmc_ip(host.get("bmc_ip"))
                if not query_result or not hosts:
                    host["reason"] = HostCons.CHECK_HOST_EXITS_TIPS
                    continue

                # 16，分配主机IP
                host_ip = distribute_ip(host_proxy, host_ip_list)
                if not host_ip:
                    host["reason"] = InstallCons.NO_AVAILABLE_IP_LEFT_TIPS
                    continue

                # 17，校验bmc联通性
                host["bmc_user_name"] = hosts[0].bmc_user_name
                host["bmc_passwd"] = hosts[0].bmc_passwd
                host["host_name"] = hosts[0].host_name
                host["host_mac"] = hosts[0].host_mac
                check_result = HostChecker.check_bmc_connection(host)
                if check_result:
                    host["reason"] = check_result.json["msg"]
                    continue

                # 18，调用ipmitool命令设置服务器由PXE启动，并下发主机开机或者重启指令
                ipmi_log = 'ipmitool -H ' + host.get("bmc_ip") + ' -I lanplus -U ' + host.get("bmc_user_name")
                bmc_passwd = AesUtil.decrypt(host.get("bmc_passwd"))

                if run_ipmitool(host.get("bmc_ip"), host.get("bmc_user_name"), bmc_passwd,
                                "chassis", "bootdev", "pxe") or \
                        run_ipmitool(host.get("bmc_ip"), host.get("bmc_user_name"), bmc_passwd,
                                     "power", "reset"):
                    LOGGER.error(ipmi_log + '' + InstallCons.IPMI_COMMAND_EXECUTE_TIPS)
                    host["reason"] = InstallCons.IPMI_COMMAND_EXECUTE_TIPS
                    continue

                # 19，创建cobbler system，将主机的mac地址写入DHCP配置文件的白名单里面，并同步DHCP服务生效
                system_id = remote_server.new_system(token)
                host_name = hosts[0].host_name + "-" + str(hosts[0].host_id)
                remote_server.modify_system(system_id, "name", host_name, token)
                remote_server.modify_system(system_id, "hostname", host_name, token)
                remote_server.modify_system(system_id, "profile", profile.get("name"), token)
                remote_server.modify_system(system_id, 'modify_interface', {
                    "macaddress-net0": hosts[0].host_mac,
                    "ipaddress-net0": host_ip,
                    "dhcptag-net0": "default"
                }, token)

                # 保存system、同步DHCP生效
                if not remote_server.save_system(system_id, token) or not remote_server.sync_dhcp(token):
                    LOGGER.error(InstallCons.COBBLER_SYSTEM_TIPS)
                    host["reason"] = InstallCons.COBBLER_SYSTEM_TIPS
                    continue

                host_ip_list.append(host_ip)

                # 20，持久化分配的IP并更新主机状态为装机中
                update_result = host_proxy.update_host_info({
                    "host_id": hosts[0].host_id,
                    "host_ip": host_ip,
                    "status": 3
                })
                if not update_result:
                    LOGGER.error(f'The host update failed:{str(hosts[0].host_id)}')
                    host["reason"] = HostCons.UPDATE_HOST_FAILED_TIPS
                    continue

                host["result"] = "succeed"
                host["reason"] = ""

            # 21，新版本的Anaconda做了调整，参数前必须要加inst.前缀，否则系统无法识别
            try:
                update_pxe_config_files()
            except (OSError, UnicodeError):
                LOGGER.exception(InstallCons.MODIFY_PXE_LINUX_DEFAULT_TIPS)
                return ResUtil.failed(InstallCons.MODIFY_PXE_LINUX_DEFAULT_TIPS, result_list)
        except Exception as e:
            LOGGER.error(f'fail to auto install:{str(e)}')
            code = 400
            msg = str(e)

        LOGGER.info("end to auto install")
        return ResUtil.success_or_failed(code, msg, result_list)


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
        host_proxy = HostProxy()
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

        update_result = host_proxy.update_host_info(host_info)
        if not update_result:
            return ResUtil.failed(HostCons.UPDATE_HOST_FAILED_TIPS)

        # 根据名称删除对应的cobbler system，清理DHCP白名单
        remote_server, token = RemoteServer().get_remote_server()
        remote_server.remove_system(hosts[0].host_name + "-" + str(hosts[0].host_id), token)
        remote_server.sync_dhcp(token)

        LOGGER.info("end to notify aops-cobbler to update host info.")
        return ResUtil.success(InstallCons.AUTO_INSTALL_NOTIFY_TIPS)


def host_scheduler():
    LOGGER.info("start to execute scheduled tasks to check if the os has failed to install.")
    host_proxy = HostProxy()
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

        after_update_time = hosts[-1].update_time
        after_host_id = hosts[-1].host_id
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


def distribute_ip(host_proxy, host_ip_list):
    start_ip = ipaddress.IPv4Address(os_start_ip)
    end_ip = ipaddress.IPv4Address(os_end_ip)

    if start_ip > end_ip:
        LOGGER.error("Invalid IP range: %s - %s", start_ip, end_ip)
        return None

    allocated_ips = set(host_ip_list)

    for ip_int in range(int(start_ip), int(end_ip) + 1):
        ip_str = str(ipaddress.IPv4Address(ip_int))

        if ip_str in allocated_ips:
            continue

        query_result, hosts = host_proxy.query_host_by_host_ip(ip_str)
        if not query_result:
            LOGGER.error("Failed to query host IP: %s", ip_str)
            return None

        if hosts:
            continue

        return ip_str

    return None


def get_default_gateway(ip_addr, subnet_mask):
    # 配置文件里纯数字的掩码会被 Config 解析成 int，拼接前统一转成字符串
    network = ipaddress.IPv4Network((ip_addr + '/' + str(subnet_mask)), strict=False)
    # 网关取网段内最后一个可用主机地址
    if network.num_addresses >= 4:
        default_gateway = str(network.network_address + (network.num_addresses - 2))
    else:
        # /31、/32 这类小网段没有可用的网关地址，使用网络地址本身
        default_gateway = str(network.network_address)
    return default_gateway

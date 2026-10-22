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
"""安装启动编排：配置全部就绪后，逐主机持久化状态并启动。"""

import ipaddress
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional, Union

from cobbled.conf.constant import HostCons, InstallCons, KsCons, ScriptCons
from cobbled.install_manager.configuration import CobblerInstallationConfiguration
from cobbled.install_manager.lifecycle import (
    InstallationConflict,
    InstallationLifecycle,
)
from cobbled.log.log import LOGGER
from cobbled.util.file_util import FileUtil


@dataclass(frozen=True)
class InstallationSettings:
    ks_dir: str
    script_dir: str
    client_ip: str
    port: int
    subnet_mask: Union[str, int]
    os_start_ip: str
    os_end_ip: str
    pxe_config_dir: str = InstallCons.PXE_CONFIG_DIR
    after_install_script: str = "/opt/aops/script/after_os_installed.sh"


@dataclass
class InstallationResult:
    code: int
    msg: str
    data: Optional[list] = None

    @classmethod
    def failed(cls, msg, data=None):
        return cls(400, msg, data)


class InstallationWorkflow:
    """接收已完成字段校验的输入，返回与传输协议无关的安装启动结果。

    connect_cobbler 延迟建立连接并返回远端对象与 token；host_store 提供
    上下文管理的主机存储。power.check_connection 返回错误信息或 None，
    power.start 返回命令退出码（零表示成功）。
    本流程保留逐主机提交与部分成功语义，不承诺跨外部操作的回滚。
    """

    def __init__(self, settings, *, connect_cobbler, host_store, power,
                 lifecycle_factory=None):
        self.settings = settings
        self.connect_cobbler = connect_cobbler
        self.host_store = host_store
        self.power = power
        self.lifecycle_factory = lifecycle_factory or InstallationLifecycle

    def run(self, *, host_list, ks_name, iso_name, arch, script_name=None, install_rpm=None):
        LOGGER.info("start to auto install")
        code = 200
        msg = InstallCons.AUTO_INSTALL_SUCCESS_TIPS
        result_list = []
        reserved = {}

        try:
            # 3，检查ks文件是否存在
            ks_full_path = os.path.join(self.settings.ks_dir, ks_name + ".ks")
            if not os.path.exists(ks_full_path):
                return InstallationResult.failed(KsCons.CHECK_KS_EXITS_TIPS)

            # 4，如果脚本名称不为空，则校验脚本文件是否存在
            if script_name:
                script_root = os.path.realpath(self.settings.script_dir)
                script_full_path = os.path.realpath(os.path.join(script_root, script_name + ".sh"))
                # 符号链接解析后的路径也必须位于脚本目录内。
                if os.path.commonpath([script_root, script_full_path]) != script_root:
                    return InstallationResult.failed(ScriptCons.CHECK_SCRIPT_NAME_TIPS)
                if not os.path.exists(script_full_path):
                    return InstallationResult.failed(ScriptCons.CHECK_SCRIPT_EXITS_TIPS)

            # 5，如果install_rpm不为空，则检查rpm包是否存在
            if install_rpm:
                rpm_list = install_rpm.split(",")
                for rpm in rpm_list:
                    check_rpm_result = subprocess.run(['yum', 'search', rpm], capture_output=True, text=True)
                    if check_rpm_result.returncode or 'No matches found' in check_rpm_result.stderr:
                        return InstallationResult.failed(InstallCons.CHECK_RPM_EXITS_TIPS + rpm)

            # 6，判断该镜像文件是否已经上传
            distro_name = iso_name + "-" + arch
            installation_config = CobblerInstallationConfiguration.for_image(
                self.connect_cobbler, distro_name)
            if installation_config is None:
                LOGGER.error("The iso file not exists in remote cobbler server.")
                return InstallationResult.failed(InstallCons.CHECK_ISO_EXITS_TIPS)

            ks_content = FileUtil.read_file_content(ks_full_path)

            # 8，在ks文件中添加系统安装日志转发配置
            client_ip = self.settings.client_ip
            port = self.settings.port
            ks_content += InstallCons.INSTALL_LOG_FORWARD_CMD.replace('ip_addr', client_ip)

            # 读取操作系统安装完成以后需要执行的脚本:ipmitool等自定义rpm包的安装
            # 在ks文件中添加调用通知接口内容，用于在操作系统安装完成后更新主机状态，否则aops-cobbler服务将无法知道操作系统是否已经安装完成
            after_os_installed = FileUtil.read_file_content(self.settings.after_install_script)
            after_os_installed = render_after_os_installed_script(
                after_os_installed, client_ip, port, self.settings.subnet_mask, install_rpm)
            ks_content = ks_content + "\n%post\n" + after_os_installed + "\n%end\n"

            # 11，将自定义脚本内容添加到ks文件中
            if script_name:
                script_content = FileUtil.read_file_content(script_full_path)
                ks_content = ks_content + "\n%post\n" + script_content + "\n%end\n"

            with self.host_store() as host_proxy:
                lifecycle = self.lifecycle_factory(host_proxy.session)
                reserved = {}
                host_ip_list = []  # 记录已经使用的IP地址
                prepared_hosts = []
                configuration_ready = False
                for host in host_list:
                    host["result"] = "failed"
                    result_list.append(host)

                    # 15，检查当前bmc_ip是否存在
                    query_result, hosts = host_proxy.query_host_by_bmc_ip(host.get("bmc_ip"))
                    if not query_result or not hosts:
                        host["reason"] = HostCons.CHECK_HOST_EXITS_TIPS
                        continue

                    # 16，分配主机IP
                    host_ip = distribute_ip(
                        host_proxy, host_ip_list, self.settings.os_start_ip, self.settings.os_end_ip)
                    if not host_ip:
                        host["reason"] = InstallCons.NO_AVAILABLE_IP_LEFT_TIPS
                        continue

                    # 17，校验bmc联通性
                    host["bmc_user_name"] = hosts[0].bmc_user_name
                    host["bmc_passwd"] = hosts[0].bmc_passwd
                    host["host_name"] = hosts[0].host_name
                    host["host_mac"] = hosts[0].host_mac
                    check_result = self.power.check_connection(host)
                    if check_result:
                        host["reason"] = check_result
                        continue

                    # 先预留轮次；准备与收尾通过同一主机数据库锁互斥。
                    try:
                        round_id, system_name = lifecycle.begin(hosts[0].host_id)
                    except InstallationConflict as error:
                        host["reason"] = str(error)
                        continue
                    reserved[hosts[0].host_id] = round_id
                    host["installation_round"] = round_id
                    if not configuration_ready:
                        installation_config.prepare_shared(ks_content)
                        configuration_ready = True
                    host_name = hosts[0].host_name + "-" + str(hosts[0].host_id)
                    try:
                        with lifecycle.active(hosts[0].host_id, round_id):
                            installation_config.prepare_host(
                                system_name=system_name, host_name=host_name,
                                round_id=round_id, host_mac=hosts[0].host_mac,
                                host_ip=host_ip)
                    except Exception:
                        host["reason"] = InstallCons.COBBLER_SYSTEM_TIPS
                        lifecycle.finish(hosts[0].host_id, round_id, succeeded=False)
                        reserved.pop(hosts[0].host_id)
                        continue

                    host_ip_list.append(host_ip)
                    prepared_hosts.append((host, hosts[0].host_id, host_ip))

                if not prepared_hosts:
                    return InstallationResult(code, msg, result_list)

                # 19，所有Cobbler写入结束后修正PXE参数，避免后续同步覆盖修正结果
                try:
                    update_pxe_config_files(self.settings.pxe_config_dir)
                except (OSError, UnicodeError):
                    LOGGER.exception(InstallCons.MODIFY_PXE_LINUX_DEFAULT_TIPS)
                    for host, _, _ in prepared_hosts:
                        host["reason"] = InstallCons.MODIFY_PXE_LINUX_DEFAULT_TIPS
                    for host_id, round_id in reserved.items():
                        lifecycle.finish(host_id, round_id, succeeded=False)
                    reserved.clear()
                    return InstallationResult.failed(InstallCons.MODIFY_PXE_LINUX_DEFAULT_TIPS, result_list)

                for host, host_id, host_ip in prepared_hosts:
                    round_id = reserved[host_id]
                    try:
                        lifecycle.prepare_start(host_id, round_id, host_ip)
                    except Exception:
                        host["reason"] = HostCons.UPDATE_HOST_FAILED_TIPS
                        lifecycle.finish(host_id, round_id, succeeded=False)
                        reserved.pop(host_id)
                        continue

                    # 状态/IP 已提交后才允许重启；锁内复查，防止超时收尾抢先结束轮次。
                    try:
                        with lifecycle.active(host_id, round_id):
                            start_failed = self.power.start(host)
                    except Exception:
                        LOGGER.exception("Failed to start installation for host %s", host_id)
                        start_failed = True

                    if start_failed:
                        host["reason"] = InstallCons.IPMI_COMMAND_EXECUTE_TIPS
                        try:
                            lifecycle.finish(host_id, round_id, succeeded=False)
                        except Exception:
                            host["reason"] += "; " + HostCons.UPDATE_HOST_FAILED_TIPS
                        reserved.pop(host_id)
                        continue

                    reserved.pop(host_id)
                    host["result"] = "succeed"
                    host["reason"] = ""
        except Exception as e:
            LOGGER.error(f'fail to auto install:{str(e)}')
            code = 400
            msg = str(e)
            for host in result_list:
                if host.get("result") == "failed" and not host.get("reason"):
                    host["reason"] = msg
            # 连接中断/进程终止时未能入队的轮次仍保持装机中，由超时扫描恢复。
            if reserved:
                try:
                    with self.host_store() as recovery_store:
                        recovery = self.lifecycle_factory(recovery_store.session)
                        for host_id, round_id in reserved.items():
                            recovery.finish(host_id, round_id, succeeded=False)
                except Exception:
                    LOGGER.exception("Failed to enqueue installation cleanup; timeout scan will retry")

        LOGGER.info("end to auto install")
        return InstallationResult(code, msg, result_list)


_LEGACY_PXE_VALUE_ARGUMENT = re.compile(r"(?<!\S)(ks|repo)=")
_LEGACY_PXE_FLAG_ARGUMENT = re.compile(r"(?<!\S)kssendmac(?=\s|$)")


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


def distribute_ip(host_proxy, host_ip_list, os_start_ip, os_end_ip):
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

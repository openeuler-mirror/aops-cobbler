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
"""安装流程使用的 IPMI adapter。"""

from cobbled.util.aes_util import AesUtil
from cobbled.util.validate_util import HostChecker, run_ipmitool


class IPMIPower:
    def check_connection(self, host):
        return HostChecker.bmc_connection_error(host)

    def start(self, host):
        """Configure PXE boot, then reset; return the first nonzero exit code."""
        password = AesUtil.decrypt(host.get("bmc_passwd"))
        return run_ipmitool(
            host.get("bmc_ip"), host.get("bmc_user_name"), password,
            "chassis", "bootdev", "pxe") or run_ipmitool(
                host.get("bmc_ip"), host.get("bmc_user_name"), password,
                "power", "reset")

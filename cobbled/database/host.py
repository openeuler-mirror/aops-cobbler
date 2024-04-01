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
Description:
"""


import math

from cobbled.database.proxy import MysqlProxy
from cobbled.database.table import RawHost
from cobbled.log.log import LOGGER
from cobbled.util.aes_util import AesUtil


class HostProxy(MysqlProxy):
    """
    Host related table operation
    """

    def add_host(self, params) -> bool:
        """
        add host to table

        Args:
            params(dict): parameter

        Returns:
            bool: True or False
        """
        params["bmc_passwd"] = AesUtil.encrypy(params["bmc_passwd"])
        return self.insert(RawHost, params)

    def add_host_batch(self, host_list) -> bool:
        """
        Add host to the table in batches

        Args:
            host_list: list of host object

        Returns:
            bool: True or False
        """
        return self.add_batch(host_list)

    def query_hosts(self, params: dict):
        """
        Query hosts from table

        Args:
            params(dict): query condition

        Returns:
            bool: query succeed or fail
        """
        host_id = params.get("host_id")
        host_name = params.get("host_name")
        bmc_ip = params.get("bmc_ip")
        page_no = int(params.get("page_no"))
        page_size = int(params.get("page_size"))
        result = {"host_infos": [], "total_count": 0, "total_page": 0}

        filters = {RawHost.host_id == host_id} if host_id else set()
        filters.add(RawHost.host_name == host_name) if host_name else filters
        filters.add(RawHost.bmc_ip == bmc_ip) if bmc_ip else filters

        query_result, total_count = self.count(RawHost.host_id, filters)
        if not query_result or total_count == 0:
            return query_result, result

        # 如果传递过来的页数大于实际页数，则返回空集合
        if page_no > math.ceil(total_count / page_size):
            result["total_count"] = total_count
            result["total_page"] = math.ceil(total_count / page_size)
            return True, result

        query_result, hosts = self.select(RawHost, filters, page_no, page_size)
        if not query_result:
            return query_result, result

        for host in hosts:
            host_info = {
                "host_id": host.host_id,
                "host_name": host.host_name,
                "bmc_ip": host.bmc_ip,
                "bmc_user_name": host.bmc_user_name,
                "bmc_passwd": host.bmc_passwd,
                "host_ip": host.host_ip,
                "status": host.status,
                "host_mac": host.host_mac
            }
            result['host_infos'].append(host_info)

        result["total_count"] = total_count
        result["total_page"] = math.ceil(total_count / page_size)

        LOGGER.info("query hosts info succeed")
        return True, result

    def query_host_by_bmc_ip(self, bmc_ip: str):
        """
        Get host info from table by bmc ip

        Args:
            bmc_ip(str): query condition

        Returns:
            bool: query succeed or fail
        """
        return self.select(RawHost, {RawHost.bmc_ip == bmc_ip})

    def query_host_by_host_id(self, host_id: str):
        """
        Get host info from table by host id

        Args:
            host_id(str): query condition

        Returns:
            bool: query succeed or fail
        """
        return self.select(RawHost, {RawHost.host_id == host_id})

    def query_host_by_status(self, status: int):
        """
        Get host info from table by status

        Args:
            status(int): query condition

        Returns:
            bool: query succeed or fail
        """
        return self.select(RawHost, {RawHost.status == status})

    def query_host_by_mac(self, host_mac: str):
        """
        Get host info from table by host mac

        Args:
            host_mac(str): query condition

        Returns:
            bool: query succeed or fail
        """
        return self.select(RawHost, {RawHost.host_mac == host_mac})

    def query_host_by_host_ip(self, host_ip: str):
        """
        Get host info from table by host ip

        Args:
            host_ip(str): query condition

        Returns:
            bool: query succeed or fail
        """
        return self.select(RawHost, {RawHost.host_ip == host_ip})

    def delete_host(self, host_list: list):
        """
        Delete host from table

        Args:
            host_list(list): delete condition

        Returns:
            bool: delete succeed or fail
        """
        return self.delete(RawHost, {RawHost.host_id.in_(host_list)})

    def update_host_info(self, update_info: dict) -> bool:
        """
        update host info to host table

        Args:
            update_info(dict): e.g
                {
                    "host_id": host_id,
                    "host_name": "new_host_name",
                    ...
                }

        Returns:
            str: True or False
        """
        return self.update(RawHost, {RawHost.host_id == update_info.get("host_id")}, update_info)

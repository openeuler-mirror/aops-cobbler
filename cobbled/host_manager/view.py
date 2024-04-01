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
Description: Restful APIs for host manager
"""


from io import BytesIO

from flask_restful import Resource
from flask import request, send_file

from cobbled.conf.constant import HostCons
from cobbled.database.host import HostProxy
from cobbled.database.table import RawHost
from cobbled.log.log import LOGGER
from cobbled.util.aes_util import AesUtil
from cobbled.util.response_util import ResUtil
from cobbled.util.validate_util import HostChecker


class AddHost(Resource):
    """
    Interface for add host.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to add host.")
        # 校验请求参数及bmc连通性
        check_result = check_host_params(request.json)
        if check_result:
            return check_result

        host_proxy = HostProxy()
        # 校验是否重复入库
        check_result = check_bmc_ip_duplicated(host_proxy, request.json) or check_host_mac_duplicated(host_proxy,
                                                                                                      request.json)
        if check_result:
            return check_result

        # 数据入库
        if not host_proxy.add_host(request.json):
            return ResUtil.failed(HostCons.ADD_HOST_FAILED_TIPS)

        LOGGER.info("end to add host.")
        return ResUtil.success(HostCons.ADD_HOST_SUCCESS_TIPS)


class BatchAddHost(Resource):
    """
    Interface for batch add host.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to batch add host.")

        # 获取请求参数
        host_list = request.json.get("host_list")
        if not host_list or len(host_list) > 100:
            return ResUtil.failed(HostCons.CHECK_HOST_LIST_TIPS)

        # 校验通过的hosts
        check_ok_list = []

        # 校验失败或者bmc ip重复或者host_mac重复的hosts
        check_failed_list = []

        # 记录bmc ip list，用来校验bmc ip是否重复
        bmc_ip_list = []

        # 记录host mac list，用来校验host mac是否重复
        host_mac_list = []

        # 用于入库的host list
        data_list = []

        host_proxy = HostProxy()

        for host in host_list:
            check_result = check_host_params(host)
            if check_result:
                host["result"] = "failed"
                host["reason"] = check_result.json["msg"]
                check_failed_list.append(host)
                continue

            if host["host_mac"] in host_mac_list or check_host_mac_duplicated(host_proxy, host):
                host["result"] = "failed"
                host["reason"] = HostCons.HOST_MAC_DUPLICATED_TIPS
                check_failed_list.append(host)
                continue

            if host["bmc_ip"] in bmc_ip_list or check_bmc_ip_duplicated(host_proxy, host):
                host["result"] = "failed"
                host["reason"] = HostCons.BMC_IP_DUPLICATED_TIPS
                check_failed_list.append(host)
                continue

            bmc_passwd = host["bmc_passwd"]
            host["bmc_passwd"] = AesUtil.encrypy(bmc_passwd)
            data_list.append(RawHost(**host))

            host["result"] = "succeed"
            host["reason"] = ""
            host["bmc_passwd"] = bmc_passwd
            bmc_ip_list.append(host["bmc_ip"])
            host_mac_list.append(host["host_mac"])
            check_ok_list.append(host)

        # 数据批量入库
        result = host_proxy.add_host_batch(data_list)
        if result:
            LOGGER.info(f"batch add host {[host['bmc_ip'] for host in check_ok_list]}succeed")
            return ResUtil.success(HostCons.BATCH_ADD_HOST_SUCCESS_TIPS, {"result": check_failed_list + check_ok_list})
        else:
            for host in check_ok_list:
                host["result"] = "failed"
                host["reason"] = HostCons.ADD_HOST_FAILED_TIPS
            return ResUtil.failed(HostCons.BATCH_ADD_HOST_FAILED_TIPS, {"result": check_failed_list + check_ok_list})


class UpdateHost(Resource):
    """
    Interface for update host.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to update host.")
        # 校验请求参数及bmc连通性
        check_result = HostChecker.check_host_id(request.json.get("host_id")) or HostChecker.check_host_status(
            request.json.get("status")) or check_host_params(request.json)
        if check_result:
            return check_result

        host_proxy = HostProxy()
        # 校验host是否存在
        query_result, hosts = host_proxy.query_host_by_host_id(request.json.get("host_id"))
        if not query_result:
            return ResUtil.failed(HostCons.QUERY_HOST_FAILED_TIPS)

        if not hosts:
            return ResUtil.failed(HostCons.CHECK_HOST_EXITS_TIPS)

        # 校验是否重复入库
        check_result = check_bmc_ip_duplicated(host_proxy, request.json) or check_host_mac_duplicated(host_proxy,
                                                                                                      request.json)
        if check_result:
            return check_result

        if hosts[0].bmc_passwd != request.json.get("bmc_passwd"):
            request.json["bmc_passwd"] = AesUtil.encrypy(request.json["bmc_passwd"])

        if not host_proxy.update_host_info(request.json):
            return ResUtil.failed(HostCons.UPDATE_HOST_FAILED_TIPS)

        LOGGER.info("end to update host.")
        return ResUtil.success(HostCons.UPDATE_HOST_SUCCESS_TIPS)


class DeleteHost(Resource):
    """
    Interface for delete host.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to delete host.")
        # 校验请求参数
        host_list = request.json.get("host_list")
        if not host_list or len(host_list) > 100:
            return ResUtil.failed(HostCons.CHECK_HOST_LIST_TIPS)

        for host_id in host_list:
            check_result = HostChecker.check_host_id(host_id)
            if check_result:
                return check_result

        if not HostProxy().delete_host(host_list):
            return ResUtil.failed(HostCons.DELETE_HOST_FAILED_TIPS)

        LOGGER.info("end to delete host.")
        return ResUtil.success(HostCons.DELETE_HOST_SUCCESS_TIPS)


class QueryHosts(Resource):
    """
    Interface for query hosts.
    Restful API: POST
    """

    def post(self):
        LOGGER.info("start to query hosts.")
        # 校验请求参数
        page_no = request.json.get("page_no")
        page_size = request.json.get("page_size")
        check_result = HostChecker.check_page_no_and_page_size(page_no, page_size)
        if check_result:
            return check_result

        query_result, result = HostProxy().query_hosts(request.json)
        if not query_result:
            return ResUtil.failed(HostCons.QUERY_HOST_FAILED_TIPS, result)

        LOGGER.info("end to query hosts.")
        return ResUtil.success(HostCons.QUERY_HOST_SUCCESS_TIPS, result)


class GetHostTemplateFile(Resource):
    """
    Interface for get host template file.
    Restful API: GET
    """

    def get(self):
        """
            download host template file
            Returns: BytesIO
            """
        file = BytesIO()
        file.write(HostCons.HOST_TEMPLATE_FILE_CONTENT.encode('utf-8'))
        file.seek(0)
        response = send_file(file, mimetype="application/octet-stream")
        response.headers['Content-Disposition'] = 'attachment; filename=template.csv'
        return response


def check_host_params(data):
    return HostChecker.check_host_name(data.get("host_name")) or HostChecker.check_host_mac(
        data.get("host_mac")) or HostChecker.check_bmc(data)


def check_bmc_ip_duplicated(host_proxy, params):
    query_result, hosts = host_proxy.query_host_by_bmc_ip(params.get("bmc_ip"))
    if not query_result:
        return ResUtil.failed(HostCons.QUERY_HOST_FAILED_TIPS)

    if hosts and str(hosts[0].host_id) != str(params.get("host_id")):
        return ResUtil.failed(HostCons.BMC_IP_DUPLICATED_TIPS)


def check_host_mac_duplicated(host_proxy, params):
    query_result, hosts = host_proxy.query_host_by_mac(params.get("host_mac"))
    if not query_result:
        return ResUtil.failed(HostCons.QUERY_HOST_FAILED_TIPS)

    if hosts and str(hosts[0].host_id) != str(params.get("host_id")):
        return ResUtil.failed(HostCons.HOST_MAC_DUPLICATED_TIPS)

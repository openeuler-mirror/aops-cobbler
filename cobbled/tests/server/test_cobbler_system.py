#!/usr/bin/python3
# ******************************************************************************
# Copyright (c) iSoftStone Technologies Co., Ltd. 2023-2024. All rights reserved.
# licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#     http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v2 for more details.
# ******************************************************************************/
"""
Time:
Author:
Description: cobbler remote system test.
"""


import xmlrpc.client

if __name__ == '__main__':

    server = 'http://192.168.235.106/cobbler_api'
    user = 'cobbler'
    passwd = 'cobbler'

    try:
        remote_server = xmlrpc.client.Server(server)
        token = remote_server.login(user, passwd)

        # 新建cobbler system
        system_id = remote_server.new_system(token)
        remote_server.modify_system(system_id, "name", "ISSEOS-V22", token)
        remote_server.modify_system(system_id, "hostname", "ISSEOS", token)
        remote_server.modify_system(system_id, "profile", "ISSEOS-V22-x86_64", token)

        remote_server.modify_system(system_id, 'modify_interface', {
            "macaddress-ens33": "00:0C:29:e1:8a:5c",
            "ipaddress-ens33": "192.168.235.155",
            "ifgateway-ens33": "192.168.235.2",
            "subnet-ens33": "255.255.255.0",
            "dnsname-ens33": "isseos01",
            "dhcptag-ens33":"default"
        }, token)

        remote_server.modify_system(system_id, 'modify_interface', {
            "macaddress-en04": "00:0C:29:e1:8a:5d",
            "ipaddress-en04": "192.168.235.156",
            "ifgateway-en04": "192.168.235.2",
            "subnet-en04": "255.255.255.0",
            "dnsname-en04": "isseos02",
            "dhcptag-en04": "default"
        }, token)

        # 保存system、同步cobbler
        remote_server.save_system(system_id, token)
        remote_server.sync_dhcp(token)
        print(remote_server.get_systems())

        # 根据名称删除对应的system
        # system_list = remote_server.find_system()
        # for sys in system_list:
        #     remote_server.remove_system(sys, token)
        #
        # remote_server.sync_dhcp(token)
        print(remote_server.find_system())
    except Exception as e:
        print(e)
        exit('remote server:%s error occurred' % server)

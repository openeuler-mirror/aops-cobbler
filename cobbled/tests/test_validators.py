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
Description: validators test.
"""


import validators

if __name__ == "__main__":
    # 1，校验 URL 地址是否合法
    url = "https://www.example.com"
    if validators.url(url):
        print("URL is valid")
    else:
        print("URL is invalid")

    # 2，检查电子邮件地址是否合法
    email = "example@example.com"
    if validators.email(email):
        print("Email is valid")
    else:
        print("Email is invalid")

    # 3，检查IP地址是否合法
    ip_address = "192.168.1.1"
    if validators.ip_address.ipv4(ip_address):
        print("IP address is valid")
    else:
        print("IP address is invalid")

    # 4，检查mac地址是否合法
    mac_address = "00:0C:29:e1:8a:5d"
    if validators.mac_address(mac_address):
        print("Mac address is valid")
    else:
        print("Mac address is invalid")

    # 5，检查hostname是否合法
    host_name = "openEuler2203-LTS-SP1"
    if validators.hostname(host_name):
        print("Host name is valid")
    else:
        print("Host name is invalid")

    # 6，检查域名是否合法
    domain = "www.baidu.com"
    if validators.domain(domain):
        print("domain is valid")
    else:
        print("domain is invalid")

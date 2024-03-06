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
Description: cobbler remote server.
"""


import xmlrpc.client
from cobbled.conf import configuration
from cobbled.log.log import LOGGER


class RemoteServer:
    """
    RemoteServer class.
    """

    def __init__(self):
        """
        Class instance initialization.
        """
        self.__server = configuration.cobbler_server.get("SERVER")
        self.__user = configuration.cobbler_server.get("USER")
        self.__passwd = configuration.cobbler_server.get("PASSWD")

    def get_remote_server(self):
        """
        get remote server.

        Returns:
            remote_server, token
        """
        try:
            remote_server = xmlrpc.client.Server(self.__server)
            token = remote_server.login(self.__user, self.__passwd)
            return remote_server, token
        except Exception as e:
            LOGGER.error(e)
            exit('URL:%s no access' % self.__server)

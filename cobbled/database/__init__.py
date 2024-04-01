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


from sqlalchemy import create_engine
from cobbled.conf import configuration


def make_mysql_engine_url(config):
    """
    Create engine url of mysql

    Args:
        config (Config): configuration object of certain module

    Returns:
        str: url of engine
    """
    mysql_host = config.mysql.get("IP")
    mysql_port = config.mysql.get("PORT")
    mysql_url_format = config.mysql.get("ENGINE_FORMAT")
    mysql_database_name = config.mysql.get("DATABASE_NAME")
    url = mysql_url_format % (mysql_host, mysql_port, mysql_database_name)
    return url


def create_database_engine(url, pool_size, pool_recycle):
    """
    Create database connection pool

    Args:
        url(str): engine url
        pool_size(int): size of pool
        pool_recycle(int): time that pool recycle the connection

    Returns:
        engine
    """
    engine = create_engine(url, pool_size=pool_size, pool_recycle=pool_recycle, pool_pre_ping=True)
    return engine


ENGINE = create_database_engine(
    make_mysql_engine_url(configuration),
    configuration.mysql.get("POOL_SIZE"),
    configuration.mysql.get("POOL_RECYCLE"))

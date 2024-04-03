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
Description: mysql tables
"""


from sqlalchemy import Column
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.sqltypes import Integer, String

Base = declarative_base()


class MyBase:
    """
    Class that provide helper function
    """

    def __init__(self):
        self.__table__ = None

    def to_dict(self):
        """
        Transfer query data to dict

        Returns:
            dict
        """
        return {col.name: getattr(self, col.name) for col in self.__table__.columns}  # pylint: disable=E1101


class RawHost(Base, MyBase):  # pylint: disable=R0903
    """
    Host table
    """

    __tablename__ = "raw_host"

    host_id = Column(Integer(), primary_key=True, autoincrement=True)
    host_name = Column(String(50), nullable=False)
    bmc_ip = Column(String(16), nullable=False)
    bmc_user_name = Column(String(128), nullable=False)
    bmc_passwd = Column(String(512), nullable=False)
    host_ip = Column(String(16), nullable=True)
    status = Column(Integer(), default=0)
    host_mac = Column(String(18), nullable=False)
    update_time = Column(String(32), nullable=True)

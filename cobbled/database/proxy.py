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
Description: Database proxy
"""


import sqlalchemy
from sqlalchemy import func, desc
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
from sqlalchemy.orm import sessionmaker
from cobbled.log.log import LOGGER
from cobbled.database import ENGINE


class MysqlProxy:
    """
    Proxy of mysql
    Database linking engine，global initialization before using engin
    """

    engine = ENGINE

    def __init__(self):
        """
        Class instance initialization
        """
        if not MysqlProxy.engine:
            raise Exception("Database error: Engine is not initialized")

        self.session = None
        self._create_session()

    def _create_session(self):
        session = sessionmaker()
        try:
            session.configure(bind=MysqlProxy.engine)
            self.session = session()
        except (DisconnectionError, sqlalchemy.exc.SQLAlchemyError):
            LOGGER.error("Mysql connection failed.")
            raise Exception("Database connection failed to be established: Mysql connection failed.")

    def __del__(self):
        if self.session:
            self.session.close()

    def insert(self, table, data):
        """
        Insert data to table

        Args:
            table(class): table of database
            data(dict): inserted data

        Returns:
            bool: insert succeed or fail
        """
        try:
            self.session.add(table(**data))
            self.session.commit()
            return True
        except sqlalchemy.exc.SQLAlchemyError as error:
            self.session.rollback()
            LOGGER.error(error)
            return False

    def delete(self, table, condition):
        """
        Delete data from table

        Args:
            table(class): table of database
            condition(set): delete condition

        Returns:
            bool: delete succeed or fail
        """
        try:
            self.session.query(table).filter(*condition).delete()
            self.session.commit()
            return True
        except sqlalchemy.exc.SQLAlchemyError as error:
            LOGGER.error(error)
            self.session.rollback()
            return False

    def update(self, table, condition, data) -> bool:
        """
        Update data info to table

        Args:
            table(class): table of database
            condition(set): update condition
            data(dict): update info

        Returns:
            str: True or False
        """
        try:
            self.session.query(table).filter(*condition).update(data)
            self.session.commit()
            return True
        except sqlalchemy.exc.SQLAlchemyError as error:
            LOGGER.error(error)
            self.session.rollback()
            return False

    def select(self, table, condition, page_no=1, page_size=10):
        """
        Query data from table

        Args:
            table(class): table or field list of database
            condition(set): query condition
            page_no: page no
            page_size: page size

        Returns:
            bool: query succeed or fail
        """
        try:
            data = (self.session.query(table)
                    .filter(*condition)
                    .order_by(desc(getattr(table, "host_id")))
                    .offset((page_no - 1) * page_size)
                    .limit(page_size).all())
            return True, data
        except sqlalchemy.exc.SQLAlchemyError as error:
            LOGGER.error(error)
            return False, []

    def count(self, table_column, condition):
        """
        Query count according to filters

        Args:
            table_column(class): table or field list of database
            condition(set): query condition

        Returns:
            int
        """
        try:
            total_count = self.session.query(func.count(table_column)).filter(*condition).scalar()
            return True, total_count
        except sqlalchemy.exc.SQLAlchemyError as error:
            LOGGER.error(error)
            return False, 0

    def add_batch(self, data_list: list) -> bool:
        """
        Batch add data to the table in batches

        Args:
            data_list(list): list of data object

        Returns:
            bool: True or False
        """
        try:
            self.session.bulk_save_objects(data_list)
            self.session.commit()
            return True
        except sqlalchemy.exc.SQLAlchemyError as error:
            LOGGER.error(error)
            self.session.rollback()
            return False

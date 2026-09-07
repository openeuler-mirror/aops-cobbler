#!/usr/bin/python3
# ******************************************************************************
# Copyright (c) iSoftStone Technologies Co., Ltd. 2023-2024. All rights reserved.
# licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of the Mulan PSL v2 at:
#     http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN 'AS IS' BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v2 for more details.
# ******************************************************************************/

import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

from cobbled.database.proxy import MysqlProxy


class TestMysqlProxyLifecycle(unittest.TestCase):
    def setUp(self):
        self.original_engine = MysqlProxy.engine
        self.engine = create_engine(
            "sqlite://",
            poolclass=QueuePool,
            pool_size=1,
            max_overflow=0)
        MysqlProxy.engine = self.engine

    def tearDown(self):
        MysqlProxy.engine = self.original_engine
        self.engine.dispose()

    def test_context_manager_returns_connection_after_success(self):
        with MysqlProxy() as proxy:
            proxy.session.execute(text("select 1")).scalar()
            self.assertEqual(self.engine.pool.checkedout(), 1)

        self.assertEqual(self.engine.pool.checkedout(), 0)

    def test_context_manager_returns_connection_after_exception(self):
        with self.assertRaises(RuntimeError), MysqlProxy() as proxy:
            proxy.session.execute(text("select 1")).scalar()
            raise RuntimeError("database request failed")

        self.assertEqual(self.engine.pool.checkedout(), 0)

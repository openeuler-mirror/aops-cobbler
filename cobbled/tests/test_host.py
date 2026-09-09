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
Description: unit tests for database/host.py
"""
import json
import unittest
from unittest.mock import patch, MagicMock

from cobbled.database.host import HostProxy

HOST_ID = "host-001"
HOST_NAME = "test-host"
BMC_IP = "10.0.0.1"
HOST_IP = "192.168.1.10"
BMC_PASSWD = "secret"


class TestHostProxyAddHost(unittest.TestCase):
    """Tests for HostProxy.add_host method."""

    @patch("cobbled.database.host.AesUtil")
    @patch("cobbled.database.host.MysqlProxy")
    def test_add_host_encrypts_password(self, mock_proxy, mock_aes):
        """Test add_host encrypts bmc_passwd."""
        mock_aes.encrypt.return_value = "encrypted"
        proxy = HostProxy.__new__(HostProxy)
        proxy.session = MagicMock()
        params = {
            "host_id": HOST_ID,
            "host_name": HOST_NAME,
            "bmc_ip": BMC_IP,
            "host_ip": HOST_IP,
            "bmc_passwd": BMC_PASSWD,
            "host_mac": "AA:BB:CC:DD:EE:FF",
        }
        with patch.object(proxy, "insert", return_value=True):
            result = proxy.add_host(params)
            self.assertTrue(result)
            self.assertEqual(params["bmc_passwd"], "encrypted")
            self.assertEqual(params["host_mac"], "aa:bb:cc:dd:ee:ff")


class TestHostProxyQueryHosts(unittest.TestCase):
    """Tests for HostProxy.query_hosts method."""

    @patch("cobbled.database.host.RawHost")
    def test_query_hosts_empty(self, mock_host):
        """Test query_hosts returns empty when no results."""
        proxy = HostProxy.__new__(Proxy)
        proxy.session = MagicMock()
        params = {"host_id": None, "host_name": None, "bmc_ip": None, "page_no": 1, "page_size": 10}
        result = proxy.query_hosts(params)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()

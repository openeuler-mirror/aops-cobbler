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
Description: unit tests for server/remote.py
"""
import unittest
from unittest.mock import patch, MagicMock

from cobbled.server.remote import (
    RemoteServer,
    TimeoutSafeTransport,
    TimeoutTransport,
)

SERVER_URL = "http://192.0.2.10/cobbler_api"
HTTPS_SERVER_URL = "https://192.0.2.10/cobbler_api"
SERVER_USER = "cobbler"
SERVER_PASSWD = "cobbler"


class TestRemoteServerParam(unittest.TestCase):
    """Tests for RemoteServer initialization and check_param."""

    @patch("cobbled.server.remote.configuration")
    def test_check_param_raises_when_credentials_missing(self, mock_config):
        """Test check_param raises ValueError when a credential is empty."""
        mock_config.cobbler_server.get.return_value = None
        server = RemoteServer()
        with self.assertRaises(ValueError):
            server.check_param()

    @patch("cobbled.server.remote.configuration")
    def test_check_param_raises_when_password_empty(self, mock_config):
        """Test check_param raises ValueError when only the password is empty."""
        mock_config.cobbler_server.get.side_effect = [SERVER_URL, SERVER_USER, ""]
        server = RemoteServer()
        with self.assertRaises(ValueError):
            server.check_param()

    @patch("cobbled.server.remote.configuration")
    def test_check_param_passes_when_credentials_set(self, mock_config):
        """Test check_param returns silently for valid credentials."""
        mock_config.cobbler_server.get.side_effect = [SERVER_URL, SERVER_USER, SERVER_PASSWD]
        server = RemoteServer()
        self.assertIsNone(server.check_param())


class TestRemoteServerConnection(unittest.TestCase):
    """Tests for RemoteServer.get_remote_server."""

    @patch("cobbled.server.remote.LOGGER")
    @patch("cobbled.server.remote.xmlrpc")
    @patch("cobbled.server.remote.configuration")
    def test_get_remote_server_returns_server_and_token(
            self, mock_config, mock_xmlrpc, mock_logger):
        """Test get_remote_server returns (remote_server, token) on success."""
        mock_config.cobbler_server.get.side_effect = [SERVER_URL, SERVER_USER, SERVER_PASSWD]
        mock_remote = MagicMock()
        mock_remote.login.return_value = "token-123"
        mock_xmlrpc.client.Server.return_value = mock_remote
        server = RemoteServer()
        result = server.get_remote_server()
        self.assertEqual(result, (mock_remote, "token-123"))
        mock_xmlrpc.client.Server.assert_called_once_with(SERVER_URL)
        mock_remote.login.assert_called_once_with(SERVER_USER, SERVER_PASSWD)

    @patch("cobbled.server.remote.LOGGER")
    @patch("cobbled.server.remote.xmlrpc")
    @patch("cobbled.server.remote.configuration")
    def test_get_remote_server_raises_connection_error_on_failure(
            self, mock_config, mock_xmlrpc, mock_logger):
        """Test get_remote_server wraps connection failures in ConnectionError."""
        mock_config.cobbler_server.get.side_effect = [SERVER_URL, SERVER_USER, SERVER_PASSWD]
        mock_xmlrpc.client.Server.side_effect = OSError("unreachable")
        server = RemoteServer()
        with self.assertRaisesRegex(ConnectionError, "is unreachable"):
            server.get_remote_server()
        mock_logger.error.assert_called_once()

    @patch("cobbled.server.remote.LOGGER")
    @patch("cobbled.server.remote.xmlrpc")
    @patch("cobbled.server.remote.configuration")
    def test_get_remote_server_rejects_empty_credentials(
            self, mock_config, mock_xmlrpc, mock_logger):
        """Test get_remote_server refuses to connect with empty credentials."""
        mock_config.cobbler_server.get.return_value = None
        server = RemoteServer()
        with self.assertRaises(ValueError):
            server.get_remote_server()
        mock_xmlrpc.client.Server.assert_not_called()


class TestRemoteTimeout(unittest.TestCase):
    """Tests for TimeoutTransport, TimeoutSafeTransport, and timeout selection."""

    def test_http_and_https_connections_have_timeout(self):
        """Test HTTP and HTTPS transports pass the configured timeout."""
        for transport, target in ((TimeoutTransport, "HTTPConnection"),
                                  (TimeoutSafeTransport, "HTTPSConnection")):
            with self.subTest(transport=transport), patch(
                    "cobbled.server.remote.http.client." + target) as connection:
                transport(30).make_connection("example.test")
                self.assertEqual(connection.call_args.kwargs["timeout"], 30)

    def test_make_connection_reuses_cached_connection_for_same_host(self):
        """Test consecutive make_connection calls for the same host reuse _connection."""
        for transport_cls, target in ((TimeoutTransport, "HTTPConnection"),
                                      (TimeoutSafeTransport, "HTTPSConnection")):
            with self.subTest(transport=transport_cls), patch(
                    "cobbled.server.remote.http.client." + target) as connection:
                transport = transport_cls(30)
                first_conn = transport.make_connection("example.test")
                second_conn = transport.make_connection("example.test")
                self.assertIs(first_conn, second_conn)
                connection.assert_called_once()

    def test_get_remote_server_selects_timeout_transport_by_scheme(self):
        """Test RemoteServer(timeout=30) picks HTTP or HTTPS timeout transport."""
        cases = (
            (SERVER_URL, TimeoutTransport),
            (HTTPS_SERVER_URL, TimeoutSafeTransport),
        )
        for url, expected_transport in cases:
            with self.subTest(url=url), \
                    patch("cobbled.server.remote.configuration") as mock_config, \
                    patch("cobbled.server.remote.xmlrpc.client.Server") as mock_server:
                mock_config.cobbler_server.get.side_effect = [
                    url, SERVER_USER, SERVER_PASSWD
                ]
                mock_remote = MagicMock()
                mock_remote.login.return_value = "token-123"
                mock_server.return_value = mock_remote

                server = RemoteServer(timeout=30)
                result = server.get_remote_server()

                self.assertEqual(result, (mock_remote, "token-123"))
                mock_server.assert_called_once()
                args, kwargs = mock_server.call_args
                self.assertEqual(args, (url,))
                self.assertIs(type(kwargs["transport"]), expected_transport)
                self.assertEqual(kwargs["transport"].timeout, 30)
                mock_remote.login.assert_called_once_with(SERVER_USER, SERVER_PASSWD)


if __name__ == "__main__":
    unittest.main()

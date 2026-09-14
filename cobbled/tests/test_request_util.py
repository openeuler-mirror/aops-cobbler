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
Description: unit tests for util/request_util.py
"""
import unittest
from unittest.mock import patch, MagicMock

from cobbled.util.request_util import JsonObjectResource


class TestJsonObjectResource(unittest.TestCase):
    """Tests for JsonObjectResource class."""

    @patch("cobbled.util.request_util.request")
    def test_dispatch_request_with_dict(self, mock_request):
        """Test dispatch_request accepts dict JSON body."""
        mock_request.get_json.return_value = {"key": "value"}
        resource = JsonObjectResource()
        mock_dispatch = MagicMock(return_value="ok")
        resource.dispatch_request = mock_dispatch
        result = resource.dispatch_request()
        mock_dispatch.assert_called_once()

    @patch("cobbled.util.request_util.request")
    def test_dispatch_request_with_list(self, mock_request):
        """Test dispatch_request rejects list JSON body."""
        mock_request.get_json.return_value = [1, 2, 3]
        resource = JsonObjectResource()
        result = resource.dispatch_request()
        self.assertEqual(result.status_code, 400)

    @patch("cobbled.util.request_util.request")
    def test_dispatch_request_with_none(self, mock_request):
        """Test dispatch_request rejects None body."""
        mock_request.get_json.return_value = None
        resource = JsonObjectResource()
        result = resource.dispatch_request()
        self.assertEqual(result.status_code, 400)


if __name__ == "__main__":
    unittest.main()

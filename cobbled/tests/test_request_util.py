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

from flask import Flask

from cobbled.util.request_util import JsonObjectResource

# A real Flask app provides the request context; patching the flask `request`
# proxy directly makes the proxy resolve at patch setup time and raise
# "Working outside of request context".
APP = Flask("request-util-test")


class DispatchSpy(JsonObjectResource):
    """JsonObjectResource that records the dispatch reaching a method."""

    def get(self):
        return {"reached": True}


class TestJsonObjectResource(unittest.TestCase):
    """Tests for JsonObjectResource class."""

    def test_dispatch_request_with_dict(self):
        """Test dispatch_request passes a dict JSON body to the method."""
        with APP.test_request_context(json={"key": "value"}):
            resource = DispatchSpy()
            result = resource.dispatch_request()
        self.assertEqual(result, {"reached": True})

    def test_dispatch_request_with_list(self):
        """Test dispatch_request rejects list JSON body."""
        with APP.test_request_context(json=[1, 2, 3]):
            resource = JsonObjectResource()
            result = resource.dispatch_request()
        self.assertEqual(result.status_code, 400)

    def test_dispatch_request_with_none(self):
        """Test dispatch_request rejects a null JSON body."""
        with APP.test_request_context(data="null", content_type="application/json"):
            resource = JsonObjectResource()
            result = resource.dispatch_request()
        self.assertEqual(result.status_code, 400)


if __name__ == "__main__":
    unittest.main()

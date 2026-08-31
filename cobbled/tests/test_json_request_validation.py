"""Regression tests for non-object JSON request bodies."""

import unittest

from flask import Flask
from flask_restful import Api

from cobbled.util.request_util import JsonObjectResource


class ProbeResource(JsonObjectResource):
    calls = 0

    def post(self):
        ProbeResource.calls += 1
        return {"result": "ok"}


class TestJsonRequestValidation(unittest.TestCase):

    def setUp(self):
        ProbeResource.calls = 0
        self.app = Flask(__name__)
        Api(self.app).add_resource(ProbeResource, "/probe")
        self.client = self.app.test_client()

    def test_rejects_valid_json_values_that_are_not_objects(self):
        for payload in ("[]", "null", '"text"', "1"):
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/probe", data=payload, content_type="application/json")

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json, {
                    "code": 400,
                    "msg": "Request body must be a JSON object."
                })

        self.assertEqual(ProbeResource.calls, 0)

    def test_preserves_flask_errors_for_invalid_json_requests(self):
        empty_response = self.client.post(
            "/probe", data="", content_type="application/json")
        content_type_response = self.client.post(
            "/probe", data="{}", content_type="text/plain")

        self.assertEqual(empty_response.status_code, 400)
        self.assertEqual(content_type_response.status_code, 415)
        self.assertEqual(ProbeResource.calls, 0)

    def test_allows_json_objects_to_reach_the_resource(self):
        response = self.client.post("/probe", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"result": "ok"})
        self.assertEqual(ProbeResource.calls, 1)


if __name__ == "__main__":
    unittest.main()

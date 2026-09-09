"""Regression tests for host-list container and element validation."""

import unittest
from unittest.mock import patch

from flask import Flask
from flask_restful import Api

from cobbled.conf.constant import HostCons
from cobbled.host_manager import view as host_view
from cobbled.install_manager import view as install_view


class TestHostListValidation(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        api = Api(self.app)
        api.add_resource(host_view.BatchAddHost, "/hosts/batch")
        api.add_resource(host_view.DeleteHost, "/hosts/delete")
        api.add_resource(install_view.AutoInstall, "/install")
        self.client = self.app.test_client()

    def assert_invalid_host_list(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            "code": 400,
            "msg": HostCons.CHECK_HOST_LIST_TIPS,
        })

    def test_batch_add_rejects_non_list_and_non_object_elements(self):
        for host_list in ({"host": {}}, "host", [None], ["host"]):
            with self.subTest(host_list=host_list), patch.object(
                    host_view, "HostProxy") as host_proxy:
                response = self.client.post(
                    "/hosts/batch", json={"host_list": host_list})

                self.assert_invalid_host_list(response)
                host_proxy.assert_not_called()

    def test_auto_install_rejects_non_list_and_non_object_elements(self):
        payload = {"iso_name": "test", "arch": "x86_64", "ks_name": "test"}
        for host_list in ({"host": {}}, "host", [None], ["host"]):
            with self.subTest(host_list=host_list), \
                    patch.object(install_view.ISOChecker, "check_iso_name", return_value=None), \
                    patch.object(install_view.ISOChecker, "check_iso_arch", return_value=None), \
                    patch.object(install_view.KsChecker, "check_ks_name", return_value=None):
                response = self.client.post(
                    "/install", json={**payload, "host_list": host_list})

                self.assert_invalid_host_list(response)

    def test_delete_rejects_non_list_host_list(self):
        for host_list in ({"host": "id"}, "host"):
            with self.subTest(host_list=host_list), patch.object(
                    host_view, "HostProxy") as host_proxy:
                response = self.client.post(
                    "/hosts/delete", json={"host_list": host_list})

                self.assert_invalid_host_list(response)
                host_proxy.assert_not_called()


if __name__ == "__main__":
    unittest.main()

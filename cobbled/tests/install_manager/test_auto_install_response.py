"""Protect the HTTP contract while the installation workflow returns plain data."""

import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
from flask_restful import Api

from cobbled.conf.constant import InstallCons, KsCons
from cobbled.install_manager import view
from cobbled.install_manager.workflow import InstallationResult


class TestAutoInstallResponse(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        Api(self.app).add_resource(view.AutoInstall, "/install")
        self.client = self.app.test_client()
        self.payload = {
            "host_list": [{"bmc_ip": "192.0.2.1"}],
            "iso_name": "test", "arch": "x86_64", "ks_name": "test",
        }

    def test_preserves_status_message_and_optional_data(self):
        results = [
            InstallationResult(200, InstallCons.AUTO_INSTALL_SUCCESS_TIPS,
                               [{"bmc_ip": "192.0.2.1", "result": "succeed", "reason": ""}]),
            # Partial host failures keep the existing overall success response.
            InstallationResult(200, InstallCons.AUTO_INSTALL_SUCCESS_TIPS,
                               [{"bmc_ip": "192.0.2.1", "result": "failed", "reason": "IPMI failed"}]),
            InstallationResult.failed(KsCons.CHECK_KS_EXITS_TIPS),
            InstallationResult.failed(InstallCons.MODIFY_PXE_LINUX_DEFAULT_TIPS,
                                      [{"bmc_ip": "192.0.2.1", "result": "failed"}]),
            InstallationResult.failed("remote error", []),
        ]
        for result in results:
            with self.subTest(result=result), patch.object(view, "InstallationWorkflow") as factory:
                factory.return_value.run.return_value = result
                response = self.client.post("/install", json=self.payload)
                expected = {"code": result.code, "msg": result.msg}
                if result.data is not None:
                    expected["data"] = result.data
                self.assertEqual(response.status_code, result.code)
                self.assertEqual(response.json, expected)
                factory.return_value.run.assert_called_once_with(
                    **self.payload, script_name=None, install_rpm=None)

    def test_invalid_fields_are_rejected_before_workflow_construction(self):
        invalid_fields = (
            {"iso_name": 123}, {"ks_name": "../test"}, {"arch": "invalid"},
            {"host_list": [None]}, {"host_list": "host"},
            {"host_list": [{"bmc_ip": "invalid"}]}, {"script_name": "../test"},
        )
        for fields in invalid_fields:
            with self.subTest(fields=fields), patch.object(view, "InstallationWorkflow") as factory:
                response = self.client.post("/install", json={**self.payload, **fields})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json["code"], 400)
                factory.assert_not_called()

    def test_missing_kickstart_uses_real_workflow_without_external_connections(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(view, "ks_dir", directory), \
                patch.object(view, "RemoteServer") as remote, \
                patch.object(view, "HostProxy") as hosts:
            response = self.client.post("/install", json=self.payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"code": 400, "msg": KsCons.CHECK_KS_EXITS_TIPS})
        remote.assert_not_called()
        hosts.assert_not_called()


if __name__ == "__main__":
    unittest.main()

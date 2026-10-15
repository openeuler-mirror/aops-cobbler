"""IPMI adapter contracts can be exercised without a Flask context."""

import unittest
from unittest.mock import call, patch

from cobbled.conf.constant import HostCons
from cobbled.install_manager import power
from cobbled.util import validate_util


class TestIPMIPower(unittest.TestCase):
    def setUp(self):
        self.host = {"bmc_ip": "192.0.2.1", "bmc_user_name": "test", "bmc_passwd": "encrypted"}
        self.power = power.IPMIPower()

    def test_connection_failure_returns_plain_message(self):
        with patch.object(validate_util.configuration, "host", {"CHECK_BMC_CONNECTION": 1}), \
                patch.object(power.AesUtil, "decrypt", return_value="password"), \
                patch.object(validate_util, "run_ipmitool", return_value=1) as command:
            self.assertEqual(self.power.check_connection(self.host), HostCons.CHECK_BMC_CONNECTION_TIPS)
        command.assert_called_once_with("192.0.2.1", "test", "password", "power", "status")

    def test_disabled_connection_check_does_not_decrypt_or_execute(self):
        with patch.object(validate_util.configuration, "host", {"CHECK_BMC_CONNECTION": 0}), \
                patch.object(power.AesUtil, "decrypt") as decrypt, \
                patch.object(validate_util, "run_ipmitool") as command:
            self.assertIsNone(self.power.check_connection(self.host))
        decrypt.assert_not_called()
        command.assert_not_called()

    def test_start_preserves_command_order_and_stops_after_bootdev_failure(self):
        for codes, expected in (([0, 0], 0), ([1], 1), ([0, 1], 1)):
            with self.subTest(codes=codes), \
                    patch.object(power.AesUtil, "decrypt", return_value="password"), \
                    patch.object(power, "run_ipmitool", side_effect=codes) as command:
                self.assertEqual(self.power.start(self.host), expected)
                calls = [call("192.0.2.1", "test", "password", "chassis", "bootdev", "pxe")]
                if len(codes) == 2:
                    calls.append(call("192.0.2.1", "test", "password", "power", "reset"))
                self.assertEqual(command.call_args_list, calls)


if __name__ == "__main__":
    unittest.main()

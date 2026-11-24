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
Description: unit tests for util/apscheduler.py
"""
import importlib
import unittest
from unittest.mock import patch

from apscheduler.triggers.cron import CronTrigger
from flask import Flask
from flask_apscheduler import APScheduler

from cobbled.conf import configuration
from cobbled.install_manager.view import host_scheduler
from cobbled.util import apscheduler as apscheduler_module


class TestSchedulerConfig(unittest.TestCase):
    """Tests for SchedulerConfig in cobbled/util/apscheduler.py."""

    def test_scheduler_api_disabled(self):
        """Test SCHEDULER_API_ENABLED is False on both class and instance."""
        self.assertIs(apscheduler_module.SchedulerConfig.SCHEDULER_API_ENABLED, False)
        self.assertIs(apscheduler_module.SchedulerConfig().SCHEDULER_API_ENABLED, False)

    def test_jobs_default_configuration(self):
        """Test JOBS matches the configured scheduler interval and target function."""
        expected_interval = configuration.host.get("SCHEDULER_INTERVAL_TIME")
        self.assertEqual(apscheduler_module.scheduler_interval_time, expected_interval)
        self.assertEqual(
            apscheduler_module.SchedulerConfig.JOBS,
            [
                {
                    "id": "1000",
                    "func": "cobbled.install_manager.view:host_scheduler",
                    "trigger": "cron",
                    "day": "*",
                    "hour": "*",
                    "minute": f"0/{expected_interval}",
                    "second": "0",
                }
            ],
        )

    def test_minute_expression_uses_configured_interval_on_reload(self):
        """Test JOBS minute expression formats the configured interval on module reload."""
        cases = (
            (5, "0/5"),
            (15, "0/15"),
            ("10", "0/10"),
        )
        for interval, expected_minute in cases:
            with self.subTest(interval=interval):
                try:
                    with patch.dict(configuration.host, {"SCHEDULER_INTERVAL_TIME": interval}):
                        reloaded = importlib.reload(apscheduler_module)
                        self.assertEqual(reloaded.scheduler_interval_time, interval)
                        self.assertEqual(len(reloaded.SchedulerConfig.JOBS), 1)
                        self.assertEqual(
                            reloaded.SchedulerConfig.JOBS[0]["minute"],
                            expected_minute,
                        )
                        self.assertIs(reloaded.SchedulerConfig.SCHEDULER_API_ENABLED, False)
                finally:
                    importlib.reload(apscheduler_module)

    def test_flask_apscheduler_loads_config_and_registers_job(self):
        """Test Flask-APScheduler loads SchedulerConfig and registers the cron job."""
        try:
            with patch.dict(configuration.host, {"SCHEDULER_INTERVAL_TIME": 5}):
                reloaded = importlib.reload(apscheduler_module)
                app = Flask("apscheduler-test")
                app.config.from_object(reloaded.SchedulerConfig())

                self.assertEqual(app.config["JOBS"], reloaded.SchedulerConfig.JOBS)
                self.assertIs(app.config["SCHEDULER_API_ENABLED"], False)

                scheduler = APScheduler()
                scheduler.init_app(app)

                self.assertIs(scheduler.api_enabled, False)
                self.assertFalse(
                    any(rule.rule.startswith("/scheduler") for rule in app.url_map.iter_rules())
                )

                job = scheduler.get_job("1000")
                self.assertIsNotNone(job)
                self.assertEqual(job.id, "1000")
                self.assertIs(job.func, host_scheduler)
                self.assertIsInstance(job.trigger, CronTrigger)

                trigger_fields = {field.name: str(field) for field in job.trigger.fields}
                self.assertEqual(trigger_fields["day"], "*")
                self.assertEqual(trigger_fields["hour"], "*")
                self.assertEqual(trigger_fields["minute"], "0/5")
                self.assertEqual(trigger_fields["second"], "0")
        finally:
            importlib.reload(apscheduler_module)


if __name__ == "__main__":
    unittest.main()

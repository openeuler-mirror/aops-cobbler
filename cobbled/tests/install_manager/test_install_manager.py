#!/usr/bin/python3
# ******************************************************************************
# Copyright (c) iSoftStone Technologies Co., Ltd. 2023-2024. All rights reserved.
# licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#     http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN 'AS IS' BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v2 for more details.
# ******************************************************************************
"""
Time:
Author:
Description: test install manager.
"""

import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cobbled.database.host import HostProxy
from cobbled.database.table import Base, RawHost
from cobbled.install_manager import view
from cobbled.install_manager.view import get_default_gateway, render_after_os_installed_script


class TestGetDefaultGateway(unittest.TestCase):

    def test_accepts_integer_mask_from_config(self):
        """Config parses a purely numeric subnet_mask into an int."""
        self.assertEqual(get_default_gateway("10.10.192.213", 24), "10.10.192.254")

    def test_accepts_string_mask(self):
        self.assertEqual(get_default_gateway("10.10.192.213", "24"), "10.10.192.254")

    def test_after_install_script_uses_configured_subnet_mask(self):
        script_path = Path(__file__).parents[3] / "script" / "after_os_installed.sh"
        script = script_path.read_text(encoding="utf-8")

        rendered_script = render_after_os_installed_script(
            script, "10.10.192.1", 8888, 16)

        self.assertIn('echo "PREFIX=16"', rendered_script)
        self.assertNotIn("s_u_b_n_e_t_m_a_s_k", rendered_script)


class TestHostScheduler(unittest.TestCase):

    def test_checks_all_installing_hosts_across_batches(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE TRIGGER raw_host_update_time
                AFTER UPDATE ON raw_host
                FOR EACH ROW
                BEGIN
                    UPDATE raw_host
                       SET update_time = datetime(OLD.update_time, '+1 day')
                     WHERE host_id = NEW.host_id;
                END
            """)
        session = sessionmaker(bind=engine)()
        self.addCleanup(engine.dispose)
        self.addCleanup(session.close)

        update_time = datetime.now() - timedelta(minutes=10)
        for index in range(11):
            session.add(RawHost(
                host_id=str(index),
                host_name=f"host-{index}",
                bmc_ip=f"10.0.0.{index + 1}",
                bmc_user_name="user",
                bmc_passwd="password",
                host_mac=f"00:00:00:00:00:{index:02x}",
                status=3,
                update_time=update_time,
            ))
        session.commit()

        host_proxy = HostProxy.__new__(HostProxy)
        host_proxy.session = session
        remote_server = Mock()
        remote_factory = Mock()
        remote_factory.get_remote_server.return_value = (remote_server, "token")

        with patch.object(view, "HostProxy", return_value=host_proxy), \
                patch.object(view, "RemoteServer", return_value=remote_factory), \
                patch.object(view, "HOST_SCHEDULER_BATCH_SIZE", 10, create=True), \
                patch.object(view.os.path, "exists", return_value=False):
            view.host_scheduler()

        installing_count = session.query(RawHost).filter(RawHost.status == 3).count()
        failed_count = session.query(RawHost).filter(RawHost.status == 4).count()
        self.assertEqual(installing_count, 0)
        self.assertEqual(failed_count, 11)
        self.assertEqual(remote_server.remove_system.call_count, 11)
        remote_server.sync_dhcp.assert_called_once_with("token")


if __name__ == "__main__":
    unittest.main()

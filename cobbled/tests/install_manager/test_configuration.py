"""验证安装配置的远端契约；轮次与事务行为由安装流程测试覆盖。"""

import unittest
from unittest.mock import Mock, call

from cobbled.conf.constant import InstallCons
from cobbled.install_manager.configuration import (
    CobblerInstallationConfiguration,
    InstallationConfigurationError,
)


class TestInstallationConfiguration(unittest.TestCase):
    def setUp(self):
        self.remote = Mock()
        self.remote.get_distro.return_value = {'name': 'image-x86_64'}
        self.remote.get_profile.return_value = {
            'name': 'image-x86_64', 'autoinstall': '/templates/image.ks'}
        self.remote.get_profiles.return_value = [
            {'name': 'other'}, {'name': 'image-x86_64'}]
        self.remote.new_system.return_value = 'system-handle'
        self.connect = Mock(return_value=(self.remote, 'token'))
        self.config = CobblerInstallationConfiguration.for_image(self.connect, 'image-x86_64')
        self.remote.reset_mock()

    def prepare_host(self):
        self.config.prepare_host(system_name='host-1-round', host_name='host-1',
                                 round_id='round', host_mac='aa:bb:cc:dd:ee:ff',
                                 host_ip='192.0.2.10')

    def test_missing_image_has_no_profile_lookup_or_writes(self):
        for missing in (None, {}, False, '~'):
            with self.subTest(missing=missing):
                self.remote.reset_mock()
                self.remote.get_distro.return_value = missing
                self.assertIsNone(CobblerInstallationConfiguration.for_image(
                    self.connect, 'missing'))
                self.assertEqual(self.remote.mock_calls, [call.get_distro('missing')])

    def test_shared_configuration_selects_menu_and_synchronizes_last(self):
        # 旧行为：save_profile 的假值不视为失败，异常仍会传播。
        self.remote.save_profile.return_value = False
        self.config.prepare_shared('kickstart content')
        self.assertEqual(self.remote.mock_calls, [
            call.write_autoinstall_template('/templates/image.ks', 'kickstart content', 'token'),
            call.get_profiles(),
            call.modify_profile('profile::other', 'enable_menu', '0', 'token'),
            call.save_profile('profile::other', 'token'),
            call.modify_profile('profile::image-x86_64', 'enable_menu', '1', 'token'),
            call.save_profile('profile::image-x86_64', 'token'),
            call.sync('token'),
        ])

    def test_shared_failure_stops_before_later_side_effects(self):
        for method, stage, message, forbidden in (
                ('write_autoinstall_template', '写入安装模板',
                 InstallCons.WRITE_AUTOINSTALL_KS_TIPS, 'get_profiles'),
                ('modify_profile', '设置 PXE 菜单',
                 InstallCons.SET_ENABLE_PXE_TIPS, 'save_profile'),
                ('sync', '同步 Cobbler', InstallCons.COBBLER_SYNC_TIPS, 'new_system')):
            with self.subTest(method=method):
                self.remote.reset_mock()
                getattr(self.remote, method).return_value = False
                with self.assertRaises(InstallationConfigurationError) as caught:
                    self.config.prepare_shared('content')
                self.assertEqual(caught.exception.stage, stage)
                self.assertEqual(str(caught.exception), message)
                getattr(self.remote, forbidden).assert_not_called()
                getattr(self.remote, method).return_value = True

    def test_host_configuration_carries_round_and_syncs_after_save(self):
        self.prepare_host()
        self.assertEqual(self.remote.mock_calls, [
            call.new_system('token'),
            call.modify_system('system-handle', 'name', 'host-1-round', 'token'),
            call.modify_system('system-handle', 'hostname', 'host-1', 'token'),
            call.modify_system('system-handle', 'profile', 'image-x86_64', 'token'),
            call.modify_system('system-handle', 'kernel_options',
                               {'aops_installation_round': 'round'}, 'token'),
            call.modify_system('system-handle', 'modify_interface', {
                'macaddress-net0': 'aa:bb:cc:dd:ee:ff',
                'ipaddress-net0': '192.0.2.10', 'dhcptag-net0': 'default'}, 'token'),
            call.save_system('system-handle', 'token'),
            call.sync_dhcp('token'),
        ])

    def test_host_failure_does_not_continue_to_save_or_sync(self):
        for method, forbidden in (('new_system', 'modify_system'),
                                  ('modify_system', 'save_system'),
                                  ('save_system', 'sync_dhcp')):
            with self.subTest(method=method):
                self.remote.reset_mock()
                original = getattr(self.remote, method).return_value
                getattr(self.remote, method).return_value = False
                with self.assertRaises(InstallationConfigurationError) as caught:
                    self.prepare_host()
                self.assertEqual(str(caught.exception), InstallCons.COBBLER_SYSTEM_TIPS)
                getattr(self.remote, forbidden).assert_not_called()
                getattr(self.remote, method).return_value = original

    def test_profile_save_exception_keeps_original_message_and_stops_sync(self):
        self.remote.save_profile.side_effect = OSError('save failed')
        with self.assertRaises(InstallationConfigurationError) as caught:
            self.config.prepare_shared('content')
        self.assertEqual(str(caught.exception), 'save failed')
        self.assertEqual(caught.exception.stage, '设置 PXE 菜单')
        self.remote.sync.assert_not_called()

    def test_host_dhcp_failure_reports_failure_after_saved_configuration(self):
        self.remote.sync_dhcp.return_value = False
        with self.assertRaises(InstallationConfigurationError) as caught:
            self.prepare_host()
        self.assertEqual(str(caught.exception), InstallCons.COBBLER_SYSTEM_TIPS)
        self.assertEqual(caught.exception.stage, '同步 DHCP')
        self.remote.save_system.assert_called_once_with('system-handle', 'token')
        self.remote.sync_dhcp.assert_called_once_with('token')

    def test_missing_system_still_syncs_dhcp(self):
        for missing in (None, {}, False, '~'):
            with self.subTest(missing=missing):
                self.remote.reset_mock()
                self.remote.get_system.return_value = missing
                CobblerInstallationConfiguration.clean_system(self.connect, 'old-round')
                self.assertEqual(self.remote.mock_calls, [
                    call.get_system('old-round'), call.sync_dhcp('token')])

    def test_cleanup_error_preserves_stage_and_type_without_secrets(self):
        cases = (
            (self.connect, '连接 Cobbler'),
            (self.remote.get_system, '查询 Cobbler 配置'),
            (self.remote.remove_system, '删除 Cobbler 配置'),
            (self.remote.sync_dhcp, '同步 DHCP'),
        )
        for method, stage in cases:
            with self.subTest(stage=stage):
                method.side_effect = TimeoutError('password=secret')
                with self.assertRaises(InstallationConfigurationError) as caught:
                    CobblerInstallationConfiguration.clean_system(self.connect, 'old-round')
                self.assertEqual(caught.exception.cleanup_summary,
                                 f'{stage}失败（TimeoutError），等待重试')
                self.assertNotIn('secret', caught.exception.cleanup_summary)
                method.side_effect = None

    def test_cleanup_false_results_fail_without_retrying(self):
        for method, stage in ((self.remote.remove_system, '删除 Cobbler 配置'),
                              (self.remote.sync_dhcp, '同步 DHCP')):
            with self.subTest(stage=stage):
                self.remote.reset_mock()
                self.connect.reset_mock()
                method.return_value = False
                with self.assertRaises(InstallationConfigurationError) as caught:
                    CobblerInstallationConfiguration.clean_system(self.connect, 'old-round')
                self.assertEqual(caught.exception.cleanup_summary,
                                 f'{stage}失败（RuntimeError），等待重试')
                self.connect.assert_called_once()
                method.assert_called_once()
                if stage == '删除 Cobbler 配置':
                    self.remote.sync_dhcp.assert_not_called()
                method.return_value = True

    def test_retry_after_delete_only_needs_dhcp_sync(self):
        systems = {'old-round'}
        self.remote.get_system.side_effect = lambda name: {'name': name} if name in systems else '~'
        self.remote.remove_system.side_effect = lambda name, token: systems.remove(name) or True
        self.remote.sync_dhcp.side_effect = [False, True]
        with self.assertRaises(InstallationConfigurationError):
            CobblerInstallationConfiguration.clean_system(self.connect, 'old-round')
        self.assertEqual(systems, set())
        CobblerInstallationConfiguration.clean_system(self.connect, 'old-round')
        self.remote.remove_system.assert_called_once_with('old-round', 'token')
        self.assertEqual(self.remote.sync_dhcp.call_count, 2)


if __name__ == '__main__':
    unittest.main()

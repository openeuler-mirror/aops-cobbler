"""Exercise the rendered post-install script without changing host networking."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cobbled.install_manager.workflow import render_after_os_installed_script


class TestAfterOsScript(unittest.TestCase):
    def run_script(self, *, gateway="", runtime_gateway="", bmc_ip="192.0.2.20",
                   existing_gateway="192.0.2.254", ifcfg_content=None,
                   keyfile_content=None, packages=None, fail_ifcfg_update=False,
                   fail_packages="", missing_ifcfg=False, missing_ifcfg_dir=False,
                   fail_nmcli=False, legacy_bmc=False, no_keyfile=False,
                   extra_keyfiles=None, without_nmcli=False, without_ipmitool=False,
                   link_mac="aa:bb:cc:dd:ee:ff"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bindir = root / "bin"
            bindir.mkdir()
            ifcfg_dir = root / "network-scripts"
            if not missing_ifcfg_dir:
                ifcfg_dir.mkdir()
            ifcfg = ifcfg_dir / "ifcfg-ens1"
            if not missing_ifcfg and not missing_ifcfg_dir:
                if ifcfg_content is not None:
                    ifcfg.write_text(ifcfg_content, encoding="utf-8")
                else:
                    gateway_line = f"GATEWAY={existing_gateway}\n" if existing_gateway else ""
                    ifcfg.write_text("DEVICE=ens1\nBOOTPROTO=dhcp\nNETMASK=255.255.255.0\n"
                                     f"{gateway_line}ONBOOT=no\n"
                                     " IPADDR1 = '192.0.2.50'\nPREFIX1=24\n"
                                     "GATEWAY1=192.0.2.253\n", encoding="utf-8")
            keyfile_dir = root / "system-connections"
            keyfile_dir.mkdir()
            keyfile = keyfile_dir / "ens1.nmconnection"
            if missing_ifcfg and not no_keyfile:
                if keyfile_content is not None:
                    keyfile.write_text(keyfile_content, encoding="utf-8")
                elif existing_gateway:
                    keyfile.write_text("[connection]\nid=ens1\ninterface-name=ens1\n"
                                       f"[ipv4]\nmethod=auto\ngateway={existing_gateway}\n"
                                       f"address1=192.0.2.50/24,{existing_gateway}\n",
                                       encoding="utf-8")
                else:
                    keyfile.write_text("[connection]\nid=ens1\ninterface-name=ens1\n"
                                       "[ipv4]\nmethod=auto\n"
                                       "address1=192.0.2.50/24\n",
                                       encoding="utf-8")
            for filename, content in (extra_keyfiles or {}).items():
                (keyfile_dir / filename).write_text(content, encoding="utf-8")
            cmdline = root / "cmdline"
            cmdline.write_text("aops_installation_round=12345678-1234-1234-1234-123456789abc"
                               + ("" if legacy_bmc else f" aops_bmc_ip={bmc_ip}") + "\n",
                               encoding="utf-8")
            commands = {
                "yum": ('#!/bin/bash\nprintf "[%s]" "$@" >> "$MOCK_YUM_LOG"\n'
                        'printf "\\n" >> "$MOCK_YUM_LOG"\n'
                        '[[ -n "$MOCK_FAIL_PACKAGES" && "$*" == *"$MOCK_FAIL_PACKAGES"* ]] && exit 1\n'
                        'exit 0\n'),
                "curl": '#!/bin/bash\nprintf "%s\\n" "$*" >> "$MOCK_CURL_LOG"\n',
                "ipmitool": '#!/bin/bash\nprintf "IP Address Source : Static\\nIP Address : %s\\n" "$MOCK_BMC_IP"\n',
                "nmcli": '''#!/bin/bash
printf "%s\\n" "$*" >> "$MOCK_NMCLI_LOG"
[[ -n "$MOCK_FAIL_NMCLI" ]] && exit 1
offline=0
mode=""
con_type=""
con_name=""
ifname=""
autoconnect=""
method=""
addresses=""
has_gw=0
gw=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --offline) offline=1; shift ;;
    --show-secrets) shift ;;
    connection)
      [[ $# -ge 2 && ( "$2" == modify || "$2" == add ) ]] || exit 2
      mode="$2"; shift 2 ;;
    type) [[ $# -ge 2 && -n "$2" ]] || exit 2; con_type="$2"; shift 2 ;;
    con-name) [[ $# -ge 2 && -n "$2" ]] || exit 2; con_name="$2"; shift 2 ;;
    ifname) [[ $# -ge 2 && -n "$2" ]] || exit 2; ifname="$2"; shift 2 ;;
    connection.autoconnect) [[ $# -ge 2 && -n "$2" ]] || exit 2; autoconnect="$2"; shift 2 ;;
    ipv4.method) [[ $# -ge 2 && -n "$2" ]] || exit 2; method="$2"; shift 2 ;;
    ipv4.addresses) [[ $# -ge 2 && -n "$2" ]] || exit 2; addresses="$2"; shift 2 ;;
    ipv4.gateway) [[ $# -ge 2 ]] || exit 2; has_gw=1; gw="$2"; shift 2 ;;
    *) exit 2 ;;
  esac
done
[[ "$offline" == 1 && -n "$mode" && -n "$method" && -n "$addresses" ]] || exit 2
[[ "$has_gw" == 1 && -z "$gw" ]] && exit 2
if [[ "$mode" == add ]]; then
  [[ -n "$con_type" && -n "$con_name" && -n "$ifname" ]] || exit 2
  printf "[connection]\\nid=%s\\ntype=%s\\ninterface-name=%s\\n" "$con_name" "$con_type" "$ifname"
  if [[ -n "$autoconnect" ]]; then
    if [[ "$autoconnect" == yes || "$autoconnect" == true ]]; then
      printf "autoconnect=true\\n"
    else
      printf "autoconnect=false\\n"
    fi
  fi
  printf "\\n[ipv4]\\nmethod=%s\\naddress1=%s\\n" "$method" "$addresses"
  [[ -n "$gw" ]] && printf "gateway=%s\\n" "$gw"
else
  awk -v autoconnect="$autoconnect" -v method="$method" -v addresses="$addresses" \
      -v has_gw="$has_gw" -v gw="$gw" '
    function flush_section() {
      if (section == "connection" && ac_val != "" && !wrote_ac) {
        print "autoconnect=" ac_val
        wrote_ac = 1
      } else if (section == "ipv4" && !wrote_ipv4) {
        print "method=" method
        print "address1=" addresses
        final_gw = (has_gw == 1) ? gw : existing_gw
        if (final_gw != "") print "gateway=" final_gw
        wrote_ipv4 = 1
      }
    }
    BEGIN {
      if (autoconnect == "yes" || autoconnect == "true") ac_val = "true"
      else if (autoconnect != "") ac_val = "false"
    }
    /^[[:space:]]*\\[[^]]+\\][[:space:]]*$/ {
      flush_section()
      section = $0
      gsub(/^[[:space:]]*\\[|\\][[:space:]]*$/, "", section)
      if (section == "ipv4") saw_ipv4 = 1
      print
      next
    }
    section == "connection" && ac_val != "" && /^[[:space:]]*autoconnect[[:space:]]*=/ {
      next
    }
    section == "ipv4" {
      if ($0 ~ /^[[:space:]]*method[[:space:]]*=/) next
      if ($0 ~ /^[[:space:]]*gateway[[:space:]]*=/) {
        val = $0
        sub(/^[[:space:]]*gateway[[:space:]]*=[[:space:]]*/, "", val)
        sub(/[[:space:]]*$/, "", val)
        if (val != "") existing_gw = val
        next
      }
      if ($0 ~ /^[[:space:]]*address[0-9]+(_options)?[[:space:]]*=/) {
        if ($0 !~ /_options[[:space:]]*=/ && index($0, ",") > 0) {
          val = substr($0, index($0, ",") + 1)
          sub(/[;[:space:]].*$/, "", val)
          if (existing_gw == "" && val != "") existing_gw = val
        }
        next
      }
    }
    { print }
    END {
      flush_section()
      if (!saw_ipv4) {
        print "[ipv4]"
        print "method=" method
        print "address1=" addresses
        if (has_gw == 1 && gw != "") print "gateway=" gw
      }
    }
  '
fi
exit 0
''',
                "ip": '''#!/bin/bash
if [[ "$*" == *"route get"* ]]; then
    echo '192.0.2.10 dev ens1 src 192.0.2.11'
elif [[ "$*" == *"addr show dev ens1"* ]]; then
    echo '2: ens1 inet 192.0.2.11/24 brd 192.0.2.255 scope global ens1'
elif [[ "$*" == *"link show dev ens1"* && -n "$MOCK_LINK_MAC" ]]; then
    echo "2: ens1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 link/ether $MOCK_LINK_MAC brd ff:ff:ff:ff:ff:ff"
elif [[ "$*" == *"route show default dev ens1"* && -n "$MOCK_RUNTIME_GATEWAY" ]]; then
    while IFS= read -r candidate; do
        echo "default via $candidate dev ens1"
    done <<< "$MOCK_RUNTIME_GATEWAY"
fi
''',
            }
            if without_ipmitool:
                del commands["ipmitool"]
            if without_nmcli:
                del commands["nmcli"]
            if fail_ifcfg_update:
                commands["sed"] = ("#!/bin/bash\n"
                                   "[[ \"$*\" == *ifcfg-ens1* ]] && exit 1\n"
                                   f"exec {shutil.which('sed')} \"$@\"\n")
            for name, source in commands.items():
                path = bindir / name
                path.write_text(source, encoding="utf-8")
                path.chmod(0o755)
            for name in ("awk", "sed", "mktemp", "cp", "grep", "chmod", "mv", "rm", "wc", "cat"):
                if name not in commands:
                    (bindir / name).symlink_to(shutil.which(name))
            source = Path(__file__).parents[3] / "script" / "after_os_installed.sh"
            script = render_after_os_installed_script(
                source.read_text(encoding="utf-8"), "192.0.2.10", 8888, 24,
                packages, gateway)
            script = script.replace("/proc/cmdline", str(cmdline))
            script = script.replace("/etc/sysconfig/network-scripts/ifcfg-", str(ifcfg_dir / "ifcfg-"))
            script = script.replace("/etc/NetworkManager/system-connections", str(keyfile_dir))
            path = root / "post.sh"
            path.write_text(script, encoding="utf-8")
            env = dict(os.environ, PATH=str(bindir),
                       MOCK_BMC_IP=bmc_ip, MOCK_RUNTIME_GATEWAY=runtime_gateway,
                       MOCK_LINK_MAC=link_mac,
                       MOCK_FAIL_PACKAGES=fail_packages,
                       MOCK_FAIL_NMCLI="1" if fail_nmcli else "",
                       MOCK_NMCLI_LOG=str(root / "nmcli.log"),
                       MOCK_YUM_LOG=str(root / "yum.log"), MOCK_CURL_LOG=str(root / "curl.log"))
            result = subprocess.run([shutil.which("bash"), str(path)], env=env, text=True,
                                    capture_output=True, check=False, timeout=120,
                                    stdin=subprocess.DEVNULL)
            if ifcfg_dir.exists():
                self.assertEqual(list(ifcfg_dir.glob("ifcfg-ens1.*")), [])
            self.assertEqual(list(keyfile_dir.glob("*.nmconnection.*")), [])
            yum_log = root / "yum.log"
            curl_log = root / "curl.log"
            nm_files = sorted(keyfile_dir.glob("*.nmconnection"))
            config_path = ifcfg if ifcfg.exists() else (
                keyfile if keyfile.exists() else (nm_files[0] if len(nm_files) == 1 else keyfile))
            all_keyfiles = {item.name: item.read_text(encoding="utf-8") for item in nm_files}
            self._last_keyfiles = all_keyfiles
            nmcli_log = root / "nmcli.log"
            self._last_nmcli_log = nmcli_log.read_text(encoding="utf-8") if nmcli_log.exists() else ""
            return (result, config_path.read_text(encoding="utf-8") if config_path.exists() else "",
                    curl_log.read_text(encoding="utf-8") if curl_log.exists() else "",
                    yum_log.read_text(encoding="utf-8") if yum_log.exists() else "")

    def test_no_runtime_gateway_preserves_existing_gateway_and_installs_multiple_packages(self):
        result, config, notified, yum_log = self.run_script(packages="vim,git")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(notified)
        self.assertIn("[install][-y][vim][git]", yum_log)
        self.assertEqual(config.count("BOOTPROTO="), 1)
        self.assertIn("BOOTPROTO=none", config)
        self.assertIn("ONBOOT=yes", config)
        self.assertIn("IPADDR=192.0.2.11", config)
        self.assertIn("PREFIX=24", config)
        self.assertNotIn("NETMASK=", config)
        self.assertIn("GATEWAY=192.0.2.254", config)
        self.assertNotIn("IPADDR1", config)
        self.assertNotIn("PREFIX1", config)
        self.assertNotIn("GATEWAY1", config)
        self.assertNotIn("[install][-y][ipmitool]", yum_log)

    def test_ifcfg_without_runtime_or_existing_gateway_stays_gateway_free(self):
        result, config, notified, _ = self.run_script(existing_gateway="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IPADDR=192.0.2.11", config)
        self.assertNotIn("GATEWAY=", config)
        self.assertIn('"result":"success"', notified)

    def test_package_rendering_ignores_blank_entries_and_whitespace(self):
        result, _, notified, yum_log = self.run_script(packages=" vim , git, , ")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[install][-y][vim][git]", yum_log)
        self.assertIn('"result":"success"', notified)

    def test_explicit_gateway_overrides_runtime_gateway(self):
        result, config, notified, _ = self.run_script(
            gateway="192.0.2.1", runtime_gateway="192.0.2.2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(notified)
        self.assertIn("GATEWAY=192.0.2.1", config)

    def test_runtime_gateway_is_used_when_none_is_configured(self):
        result, config, notified, _ = self.run_script(runtime_gateway="192.0.2.2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(notified)
        self.assertIn("GATEWAY=192.0.2.2", config)

    def test_multiple_runtime_gateways_warn_and_use_first(self):
        result, config, notified, _ = self.run_script(
            runtime_gateway="192.0.2.2\n192.0.2.3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(notified)
        self.assertIn("Multiple default gateways", result.stderr)
        self.assertIn("GATEWAY=192.0.2.2", config)
        self.assertNotIn("GATEWAY=192.0.2.3", config)

    def test_invalid_bmc_reports_failure_without_rewriting_network(self):
        for bmc_ip in ("0.0.0.0", "010.0.0.1", "999.0.0.1"):
            with self.subTest(bmc_ip=bmc_ip):
                result, config, notified, _ = self.run_script(bmc_ip=bmc_ip)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('"result":"failed"', notified)
                self.assertNotIn('"bmc_ip"', notified)
                self.assertIn("BOOTPROTO=dhcp", config)

    def test_legacy_boot_arguments_do_not_install_unused_ipmitool(self):
        result, config, notified, yum_log = self.run_script(
            legacy_bmc=True, without_ipmitool=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BOOTPROTO=none", config)
        self.assertIn('"result":"success"', notified)
        self.assertNotIn("ipmitool", yum_log)

    def test_boot_argument_bmc_does_not_install_ipmitool(self):
        result, config, notified, yum_log = self.run_script(without_ipmitool=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BOOTPROTO=none", config)
        self.assertIn('"result":"success"', notified)
        self.assertNotIn("ipmitool", yum_log)

    def test_failed_ifcfg_update_removes_temporary_file(self):
        result, config, notified, _ = self.run_script(fail_ifcfg_update=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"result":"failed"', notified)
        self.assertIn("BOOTPROTO=dhcp", config)

    def test_missing_ifcfg_uses_networkmanager_profile(self):
        result, config, notified, _ = self.run_script(missing_ifcfg=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--show-secrets --offline connection modify", self._last_nmcli_log)
        self.assertIn("method=manual", config)
        self.assertIn("address1=192.0.2.11/24", config)
        self.assertIn("gateway=192.0.2.254", config)
        self.assertNotIn("address1=192.0.2.50", config)
        self.assertIn('"result":"success"', notified)

    def test_networkmanager_profile_without_any_gateway_stays_gateway_free(self):
        result, config, notified, _ = self.run_script(
            missing_ifcfg=True, existing_gateway="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("address1=192.0.2.11/24", config)
        self.assertNotIn("gateway=", config)
        self.assertNotIn("address1=192.0.2.50", config)
        self.assertIn('"result":"success"', notified)

    def test_networkmanager_profile_sets_explicit_gateway(self):
        result, config, notified, _ = self.run_script(
            missing_ifcfg=True, gateway="192.0.2.1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gateway=192.0.2.1", config)
        self.assertNotIn("gateway=192.0.2.254", config)
        self.assertNotIn("address1=192.0.2.50", config)
        self.assertIn('"result":"success"', notified)

    def test_networkmanager_profile_uses_runtime_gateway(self):
        result, config, notified, _ = self.run_script(
            missing_ifcfg=True, runtime_gateway="192.0.2.2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gateway=192.0.2.2", config)
        self.assertNotIn("gateway=192.0.2.254", config)
        self.assertNotIn("address1=192.0.2.50", config)
        self.assertIn('"result":"success"', notified)

    def test_missing_ifcfg_without_editable_profile_reports_failure(self):
        result, config, notified, _ = self.run_script(missing_ifcfg=True, fail_nmcli=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("method=auto", config)
        self.assertIn("Cannot update network profile", result.stderr)
        self.assertIn('"result":"failed"', notified)

    def test_missing_ifcfg_and_keyfile_creates_networkmanager_profile(self):
        result, config, notified, _ = self.run_script(
            missing_ifcfg=True, missing_ifcfg_dir=True, no_keyfile=True,
            gateway="192.0.2.1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("interface-name=ens1", config)
        self.assertIn("address1=192.0.2.11/24", config)
        self.assertIn("gateway=192.0.2.1", config)
        self.assertIn("--offline connection add", self._last_nmcli_log)
        self.assertIn('"result":"success"', notified)

    def test_missing_ifcfg_and_nmcli_creates_ifcfg_when_sysconfig_exists(self):
        result, config, notified, _ = self.run_script(
            missing_ifcfg=True, no_keyfile=True, without_nmcli=True,
            gateway="192.0.2.1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DEVICE=ens1", config)
        self.assertIn("BOOTPROTO=none", config)
        self.assertIn("ONBOOT=yes", config)
        self.assertIn("IPADDR=192.0.2.11", config)
        self.assertIn("PREFIX=24", config)
        self.assertIn("GATEWAY=192.0.2.1", config)
        self.assertIn('"result":"success"', notified)

    def test_networkmanager_profile_matches_by_mac_address(self):
        result, _, notified, _ = self.run_script(
            missing_ifcfg=True, no_keyfile=True,
            extra_keyfiles={
                "wired.nmconnection": (
                    "[connection]\nid=Wired connection 1\ntype=ethernet\n"
                    "[ethernet]\nmac-address=AA:BB:CC:DD:EE:FF\n"
                    "[ipv4]\nmethod=auto\n"
                ),
                "vlan.nmconnection": (
                    "[connection]\nid=vlan100\ntype=vlan\n"
                    "[ethernet]\nmac-address=AA:BB:CC:DD:EE:FF\n"
                    "[ipv4]\nmethod=auto\n"
                ),
                "slave.nmconnection": (
                    "[connection]\nid=bond-slave\ntype=ethernet\nmaster=bond0\n"
                    "[ethernet]\nmac-address=AA:BB:CC:DD:EE:FF\n"
                ),
            })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("method=manual", self._last_keyfiles["wired.nmconnection"])
        self.assertIn("address1=192.0.2.11/24", self._last_keyfiles["wired.nmconnection"])
        self.assertIn("method=auto", self._last_keyfiles["vlan.nmconnection"])
        self.assertNotIn("method=manual", self._last_keyfiles["slave.nmconnection"])
        self.assertIn('"result":"success"', notified)

    def test_networkmanager_profile_prefers_active_and_higher_priority_profile(self):
        result, _, notified, _ = self.run_script(
            missing_ifcfg=True, no_keyfile=True,
            extra_keyfiles={
                "disabled.nmconnection": (
                    "[connection]\nid=disabled\ninterface-name=ens1\nautoconnect=false\n"
                    "[ipv4]\nmethod=auto\n"
                ),
                "initrd.nmconnection": (
                    "[connection]\nid=initrd\ninterface-name=ens1\nautoconnect-priority=-100\n"
                    "[ipv4]\nmethod=auto\n"
                ),
                "active.nmconnection": (
                    "[connection]\nid=active\ntype=ethernet\nautoconnect-priority=0\n"
                    "[802-3-ethernet]\nmac-address=AA:BB:CC:DD:EE:FF\n"
                    "[ipv4]\nmethod=auto\n"
                ),
            })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("method=manual", self._last_keyfiles["active.nmconnection"])
        self.assertIn("method=auto", self._last_keyfiles["disabled.nmconnection"])
        self.assertIn("method=auto", self._last_keyfiles["initrd.nmconnection"])
        self.assertIn('"result":"success"', notified)

    def test_ambiguous_networkmanager_profiles_warn_and_report_success(self):
        result, _, notified, yum_log = self.run_script(
            missing_ifcfg=True, no_keyfile=True, packages="vim",
            extra_keyfiles={
                "first.nmconnection": (
                    "[connection]\nid=first\ninterface-name=ens1\n[ipv4]\nmethod=auto\n"
                ),
                "second.nmconnection": (
                    "[connection]\nid=second\ninterface-name=ens1\n[ipv4]\nmethod=auto\n"
                ),
            })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Multiple editable network profiles", result.stderr)
        self.assertIn("method=auto", self._last_keyfiles["first.nmconnection"])
        self.assertIn("method=auto", self._last_keyfiles["second.nmconnection"])
        self.assertIn("[install][-y][vim]", yum_log)
        self.assertIn('"result":"success"', notified)

    def test_no_editable_backend_warns_and_reports_success(self):
        result, config, notified, _ = self.run_script(
            missing_ifcfg=True, missing_ifcfg_dir=True,
            no_keyfile=True, without_nmcli=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(config, "")
        self.assertIn("No editable network profile", result.stderr)
        self.assertIn('"result":"success"', notified)

    def test_legacy_boot_arguments_use_round_only_notification(self):
        result, config, notified, _ = self.run_script(legacy_bmc=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BOOTPROTO=none", config)
        self.assertIn('"result":"success"', notified)
        self.assertNotIn('"bmc_ip"', notified)

    def test_failed_optional_package_install_still_notifies(self):
        result, config, notified, yum_log = self.run_script(
            packages="vim,git", fail_packages="vim")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(notified)
        self.assertIn("Failed to install requested packages", result.stderr)
        self.assertIn("[install][-y][vim][git]", yum_log)
        self.assertIn("BOOTPROTO=none", config)

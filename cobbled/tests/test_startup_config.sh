#!/bin/bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
# Load the parser without running the startup script's final create_config_file call.
eval "$(sed '$d' "$repo_root/aops-cobbler")"
declare -F get_config >/dev/null

fixture=$(mktemp)
trap 'rm -f "$fixture"' EXIT

printf '\357\273\277[cobbler_client]\n#ip=commented\nip = 127.0.0.1\nport = 8888\n[uwsgi] # settings\ninvalid line\ndaemonize = /tmp/a=b.log\n[mysql]\nip=10.10.192.213\n' > "$fixture"
[[ $(get_config "$fixture" cobbler_client ip) == 127.0.0.1 ]]
[[ $(get_config "$fixture" uwsgi daemonize) == /tmp/a=b.log ]]
[[ -z $(get_config "$fixture" uwsgi ip) ]]

printf '[cobbler_client]\n[broken section\nport=9999\n' > "$fixture"
[[ -z $(get_config "$fixture" cobbler_client port) ]]

echo 'startup INI parser checks passed'

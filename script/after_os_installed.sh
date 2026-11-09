#!/bin/bash
ip_addr=127.0.0.1
port=8888
rpms=(r_p_m_s)
configured_gateway='g_a_t_e_w_a_y'
prefix='s_u_b_n_e_t_m_a_s_k'

notify_result() {
    local payload
    payload="{\"installation_round\":\"${installation_round}\",\"result\":\"$1\""
    if [[ "${bmc_ready:-0}" == 1 ]]; then
        payload+=",\"bmc_ip\":\"${bmc_ip}\""
    fi
    payload+='}'
    curl --fail --retry 5 --retry-connrefused --retry-delay 10 --connect-timeout 10 --max-time 60 \
        -H 'Content-Type: application/json' \
        -d "$payload" \
        "http://${ip_addr}:${port}/cobbler/notify"
}

fail() {
    echo "$*" >&2
    if [[ "${identity_ready:-0}" == 1 ]]; then
        notify_result failed || echo "Failed to report installation failure" >&2
    fi
    exit 1
}

is_valid_ipv4() {
    local ip=$1 octet
    local -a octets
    [[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || return 1
    IFS=. read -r -a octets <<< "$ip"
    for octet in "${octets[@]}"; do
        [[ "$octet" == 0 || "$octet" != 0* ]] || return 1
        (( 10#$octet <= 255 )) || return 1
    done
}

installation_round=$(sed -n 's/.*aops_installation_round=\([^ ]*\).*/\1/p' /proc/cmdline)
[[ "$installation_round" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || fail "Missing or invalid installation round"
identity_ready=1

bmc_ip=$(sed -n 's/.*aops_bmc_ip=\([^ ]*\).*/\1/p' /proc/cmdline)
if [[ -n "$bmc_ip" ]]; then
    is_valid_ipv4 "$bmc_ip" || fail "Invalid BMC IP"
    [[ "$bmc_ip" != 0.0.0.0 ]] || fail "BMC IP is not configured"
    bmc_ready=1
fi

route_info=$(ip -4 -o route get "$ip_addr") || fail "No route to installation server"
network_name=$(awk '{for (i=1;i<NF;i++) if ($i=="dev") {print $(i+1); exit}}' <<< "$route_info")
service_ip=$(awk '{for (i=1;i<NF;i++) if ($i=="src") {print $(i+1); exit}}' <<< "$route_info")
[[ -n "$network_name" && "$network_name" != lo && -n "$service_ip" ]] || fail "Invalid installation interface"
ifcfg_file="/etc/sysconfig/network-scripts/ifcfg-${network_name}"
ip -4 -o addr show dev "$network_name" | awk -v ip="$service_ip" '{split($4, address, "/"); if (address[1] == ip) found=1} END {exit !found}' \
    || fail "Route source IP does not belong to installation interface"

gateway="$configured_gateway"
if [[ -z "$gateway" ]]; then
    default_routes=$(ip -4 -o route show default dev "$network_name") || fail "Cannot read default route"
    gateways=$(awk '{for (i=1;i<NF;i++) if ($i=="via") print $(i+1)}' <<< "$default_routes")
    if [[ $(printf '%s\n' "$gateways" | awk 'NF' | wc -l) -gt 1 ]]; then
        echo "Multiple default gateways on installation interface; using the first" >&2
    fi
    gateway=$(printf '%s\n' "$gateways" | awk 'NF {print; exit}')
fi

temp_files=()
cleanup_temp_files() {
    if [[ ${#temp_files[@]} -gt 0 ]]; then
        rm -f -- "${temp_files[@]}"
    fi
}
trap cleanup_temp_files EXIT

if [[ -f "$ifcfg_file" ]]; then
    gateway_to_write="$gateway"
    if [[ -z "$gateway_to_write" ]]; then
        existing_gateway=$(awk -v sq="'" '
            { sub(/\r$/, "") }
            /^[[:space:]]*[#]/ { next }
            match($0, /^[[:space:]]*GATEWAY0?[[:space:]]*=/) {
                key = substr($0, RSTART, RLENGTH)
                val = substr($0, RSTART + RLENGTH)
                sub(/[[:space:]]*[#].*$/, "", val)
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
                if (length(val) >= 2) {
                    first = substr(val, 1, 1)
                    last = substr(val, length(val), 1)
                    if ((first == "\"" && last == "\"") || (first == sq && last == sq)) {
                        val = substr(val, 2, length(val) - 2)
                    }
                }
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
                if (key ~ /GATEWAY0/) {
                    gw0 = val
                } else {
                    gw = val
                }
            }
            END {
                if (gw != "") print gw
                else if (gw0 != "") print gw0
            }
        ' "$ifcfg_file")
        if [[ -n "$existing_gateway" && "$existing_gateway" != 0.0.0.0 ]] && is_valid_ipv4 "$existing_gateway"; then
            gateway_to_write="$existing_gateway"
        fi
    fi
    temp_ifcfg=$(mktemp "${ifcfg_file}.XXXXXX") || fail "Cannot create temporary network configuration"
    temp_files+=("$temp_ifcfg")
    cp -p "$ifcfg_file" "$temp_ifcfg" || fail "Cannot copy network configuration"
    sed -E '/^[[:space:]]*(BOOTPROTO|ONBOOT|IPADDR[0-9]*|PREFIX[0-9]*|NETMASK[0-9]*|GATEWAY[0-9]*)[[:space:]]*=/d' "$ifcfg_file" > "$temp_ifcfg" \
        || fail "Cannot update network configuration"
    {
        echo 'BOOTPROTO=none'
        echo 'ONBOOT=yes'
        echo "IPADDR=${service_ip}"
        echo "PREFIX=${prefix}"
        [[ -z "$gateway_to_write" ]] || echo "GATEWAY=${gateway_to_write}"
    } >> "$temp_ifcfg" || fail "Cannot write network configuration"
    mv -f "$temp_ifcfg" "$ifcfg_file" || fail "Cannot replace network configuration"
else
    ## %post runs in a chroot, where the NetworkManager daemon is unavailable.
    keyfile_dir=/etc/NetworkManager/system-connections
    link_info=$(ip -o link show dev "$network_name" 2>/dev/null || true)
    network_mac=$(awk '{for (i=1;i<NF;i++) if ($i=="link/ether") {print tolower($(i+1)); exit}}' <<< "$link_info")
    keyfiles=()
    best_active=-1
    best_priority=-2147483648
    best_tier=-1
    for candidate in "$keyfile_dir"/*.nmconnection; do
        [[ -f "$candidate" ]] || continue
        match_info=$(awk -v device="$network_name" -v device_mac="$network_mac" '
            BEGIN {
                active = 1
                priority = 0
                conn_type = ""
                ifname = ""
                mac = ""
                is_port = 0
            }
            { sub(/\r$/, "") }
            /^[[:space:]]*[#;]/ || /^[[:space:]]*$/ { next }
            /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {
                section = $0
                gsub(/^[[:space:]]*\[|\][[:space:]]*$/, "", section)
                next
            }
            {
                eq = index($0, "=")
                if (!eq) next
                key = substr($0, 1, eq - 1)
                val = substr($0, eq + 1)
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
            }
            section == "connection" {
                if (key == "interface-name") {
                    ifname = val
                } else if (key == "type") {
                    conn_type = tolower(val)
                } else if (key == "autoconnect") {
                    lower = tolower(val)
                    active = (lower == "false" || lower == "no" || lower == "0") ? 0 : 1
                } else if (key == "autoconnect-priority" && val ~ /^-?[0-9]{1,9}$/) {
                    priority = val + 0
                } else if ((key == "master" || key == "controller" || key == "slave-type" || key == "port-type") && val != "") {
                    is_port = 1
                }
            }
            section == "ethernet" || section == "802-3-ethernet" {
                if (key == "mac-address") {
                    gsub(/^"|"$/, "", val)
                    mac = tolower(val)
                }
            }
            END {
                if (is_port) exit 1
                if (ifname != "") {
                    if (ifname != device) exit 1
                    tier = 2
                } else if ((conn_type == "" || conn_type == "ethernet" || conn_type == "802-3-ethernet") &&
                           device_mac != "" && mac == device_mac) {
                    tier = 1
                } else {
                    exit 1
                }
                printf "%d %d %d\n", active, priority, tier
            }
        ' "$candidate") || continue
        read -r cand_active cand_priority cand_tier <<< "$match_info"
        if (( cand_active > best_active ||
              (cand_active == best_active && cand_priority > best_priority) ||
              (cand_active == best_active && cand_priority == best_priority && cand_tier > best_tier) )); then
            keyfiles=("$candidate")
            best_active=$cand_active
            best_priority=$cand_priority
            best_tier=$cand_tier
        elif (( cand_active == best_active && cand_priority == best_priority && cand_tier == best_tier )); then
            keyfiles+=("$candidate")
        fi
    done
    gateway_args=()
    if [[ -n "$gateway" ]]; then
        gateway_args=(ipv4.gateway "$gateway")
    fi
    if [[ ${#keyfiles[@]} -eq 1 ]]; then
        if command -v nmcli >/dev/null 2>&1; then
            keyfile=${keyfiles[0]}
            temp_keyfile=$(mktemp "${keyfile}.XXXXXX") || fail "Cannot create temporary network profile"
            temp_files+=("$temp_keyfile")
            if cp -p "$keyfile" "$temp_keyfile" && \
                nmcli --show-secrets --offline connection modify connection.autoconnect yes \
                ipv4.method manual ipv4.addresses "$service_ip/$prefix" "${gateway_args[@]}" \
                < "$keyfile" > "$temp_keyfile" && \
                grep -q '^\[connection\]$' "$temp_keyfile" && \
                grep -q '^\[ipv4\]$' "$temp_keyfile" && \
                chmod 600 "$temp_keyfile" && \
                mv -f "$temp_keyfile" "$keyfile"; then
                :
            else
                fail "Cannot update network profile for $network_name"
            fi
        else
            echo "nmcli is unavailable; skipping network profile update for $network_name" >&2
        fi
    elif [[ ${#keyfiles[@]} -eq 0 ]]; then
        network_configured=0
        if [[ -d "$keyfile_dir" ]] && command -v nmcli >/dev/null 2>&1; then
            keyfile="$keyfile_dir/${network_name}.nmconnection"
            if [[ -e "$keyfile" || -L "$keyfile" ]]; then
                keyfile="$keyfile_dir/aops-${network_name}.nmconnection"
            fi
            if [[ ! -e "$keyfile" && ! -L "$keyfile" ]]; then
                temp_keyfile=$(mktemp "${keyfile}.XXXXXX") || temp_keyfile=""
                if [[ -n "$temp_keyfile" ]]; then
                    temp_files+=("$temp_keyfile")
                    if nmcli --offline connection add type ethernet \
                        con-name "$network_name" ifname "$network_name" \
                        connection.autoconnect yes ipv4.method manual \
                        ipv4.addresses "$service_ip/$prefix" "${gateway_args[@]}" \
                        < /dev/null > "$temp_keyfile" && \
                        grep -q '^\[connection\]$' "$temp_keyfile" && \
                        grep -q '^\[ipv4\]$' "$temp_keyfile" && \
                        chmod 600 "$temp_keyfile" && \
                        mv -f "$temp_keyfile" "$keyfile"; then
                        network_configured=1
                    else
                        rm -f -- "$temp_keyfile"
                    fi
                fi
            fi
        fi
        if [[ "$network_configured" != 1 && -d "${ifcfg_file%/*}" ]]; then
            temp_ifcfg=$(mktemp "${ifcfg_file}.XXXXXX") || temp_ifcfg=""
            if [[ -n "$temp_ifcfg" ]]; then
                temp_files+=("$temp_ifcfg")
                if {
                    echo 'TYPE=Ethernet'
                    echo "DEVICE=${network_name}"
                    echo "NAME=${network_name}"
                    echo 'BOOTPROTO=none'
                    echo 'ONBOOT=yes'
                    echo "IPADDR=${service_ip}"
                    echo "PREFIX=${prefix}"
                    [[ -z "$gateway" ]] || echo "GATEWAY=${gateway}"
                } > "$temp_ifcfg" && chmod 644 "$temp_ifcfg" && mv -f "$temp_ifcfg" "$ifcfg_file"; then
                    network_configured=1
                else
                    rm -f -- "$temp_ifcfg"
                fi
            fi
        fi
        if [[ "$network_configured" != 1 ]]; then
            echo "No editable network profile for $network_name; skipping static network persistence" >&2
        fi
    else
        echo "Multiple editable network profiles for $network_name; skipping static network persistence" >&2
    fi
fi

## 软件包安装是可选步骤，失败不影响装机完成回报。
if [[ "${rpms[0]}" != r_p_m_s ]]; then
    yum install -y "${rpms[@]}" || echo "Failed to install requested packages" >&2
fi

notify_result success || { echo "Installation completion callback failed" >&2; exit 1; }

#!/bin/bash
 ip_addr=127.0.0.1
 gate_way=127.0.0.254
 port=8888
 rpms='r_p_m_s'

 echo 'nameserver 8.8.8.8' > /etc/resolv.conf
 yum install -y ipmitool
 bmc_ip=`ipmitool lan print | grep 'IP Address' | grep -v 'Source' | awk -F ': ' '{print $2}'`
 installation_round=$(sed -n 's/.*aops_installation_round=\([^ ]*\).*/\1/p' /proc/cmdline)
 # 缺少轮次时不得发送会被误认为当前安装的完成通知。
 if ! [[ "$installation_round" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
   echo "Missing or invalid installation round" >&2
   exit 1
 fi
 curl --fail --retry 5 --retry-delay 10 --connect-timeout 10 --max-time 60 -d '{"bmc_ip":"'${bmc_ip}'","installation_round":"'${installation_round}'"}' -H "Content-Type: application/json " http://${ip_addr}:${port}/cobbler/notify

 service_ip=`hostname -I`
 network_name=`ip addr | grep ${service_ip} | awk -F ' ' '{print $NF}'`
 network_config_file_name='ifcfg-'${network_name}
 cd /etc/sysconfig/network-scripts
 echo "BOOTPROTO=static" >> ${network_config_file_name}
 echo "IPADDR=${service_ip}" >> ${network_config_file_name}
 echo "PREFIX=s_u_b_n_e_t_m_a_s_k" >> ${network_config_file_name}
 echo "GATEWAY=${gate_way}" >> ${network_config_file_name}

 if [ "${rpms}" != "r_p_m_s" ]; then
   yum install -y ${rpms}
 fi

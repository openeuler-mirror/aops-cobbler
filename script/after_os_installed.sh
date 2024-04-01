#!/bin/bash
 ip_addr=127.0.0.1
 gate_way=127.0.0.254
 port=8888
 rpms='r_p_m_s'

 echo 'nameserver 8.8.8.8' > /etc/resolv.conf
 yum install -y ipmitool
 bmc_ip=`ipmitool lan print | grep 'IP Address' | grep -v 'Source' | awk -F ': ' '{print $2}'`
 curl -d '{"bmc_ip":"'${bmc_ip}'"}' -H "Content-Type: application/json " http://${ip_addr}:${port}/cobbler/notify

 service_ip=`hostname -I`
 network_name=`ip addr | grep ${service_ip} | awk -F ' ' '{print $NF}'`
 network_config_file_name='ifcfg-'${network_name}
 cd /etc/sysconfig/network-scripts
 echo "BOOTPROTO=static" >> ${network_config_file_name}
 echo "IPADDR=${service_ip}" >> ${network_config_file_name}
 echo "PREFIX=24" >> ${network_config_file_name}
 echo "GATEWAY=${gate_way}" >> ${network_config_file_name}

 if [ "${rpms}" != "r_p_m_s" ]; then
   yum install -y ${rpms}
 fi
 
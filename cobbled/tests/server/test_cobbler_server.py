#!/usr/bin/python3
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
Time:
Author:
Description: cobbler remote server test.
"""


import time
import xmlrpc.client

if __name__ == '__main__':

    time_str = time.time()

    server = 'http://192.168.235.106/cobbler_api'

    user = 'cobbler'

    passwd = 'cobbler'

    try:
        remote_server = xmlrpc.client.Server(server)

        token = remote_server.login(user, passwd)

        # 返回cobbler系统登录账号
        # print(remote_server.get_user_from_token(token))

        # 返回所有distro的已有内容
        print(remote_server.get_distros())

        # 返回distro指定名称的详细信息
        # print(remote_server.get_distro('ISSEOS-V22-x86_64'))

        # 返回profile指定名称的详细信息
        # print(remote_server.get_profile('ISSEOS-V22-x86_64'))

        # cobbler服务器状态监测
        # print(remote_server.ping())

        # 获取指定发布版本的信息
        # print(remote_server.get_item('distro','Centos6.9-x86_64'))

        # 返回所有profiles的已有内容
        # print(remote_server.get_profiles())

        # 以列表返回所有的 system 名称
        # print(remote_server.find_system())

        # 以列表返回所有的distro名称
        # print(remote_server.find_distro())

        # 以列表返回所有profile的名称
        # print(remote_server.find_profile())

        # 检测指定distro中指定的名称是否存在
        # print(remote_server.has_item('distro','Centos6.9-x86_64'))

        # 获取distro handle
        # print(remote_server.get_distro_handle('Centos6.9-x86_64',token))

        # 删除指定的profile
        # print(remote_server.remove_profile('test111',token))

        # 删除指定的system
        # print(remote_server.remove_system('hostname121',token))

        # 创建一个新的profile并保存
        # prof_id = remote_server.new_profile(token)
        # print('profile new id:%s' % prof_id)

        # 修改指定prof_id的profile名称
        # remote_server.modify_profile(prof_id,'name','vm_test1',token)

        # 也是根据prof_id修改信息
        # remote_server.modify_profile(prof_id,'distro','centos6.8-x86_64',token)
        # remote_server.modify_profile(prof_id,'kickstart','/var/lib/cobbler/kickstart/123.ks',token)

        # 保存profile
        # remote_server.save_profile(prof_id,token)

        # 同步cobbler修改后的信息，这个做任何操作后都要必须有
        # remote_server.sync(token)

        # 启动方面操作
        # print(remote_server.generate_gpxe('vm_test1'))
        # print(remote_server.generate_bootcfg('vm_test1'))

        # 获取profile的详细信息
        # print(remote_server.get_blended_data('vm_test1'))

        # 获取Cobbler设置信息
        # print(remote_server.get_settings())

        # 输出签名信息
        # print(remote_server.get_signatures())

        # 获取的是各个操作系统的类型
        # 输出： ['debian', 'redhat', 'suse', 'ubuntu', 'unix', 'vmware', 'windows', 'xen']
        # print(remote_server.get_valid_breeds())

        # 返回cobbler版本
        # print(remote_server.version())

        # 返回cobbler详细版本信息
        # print(remote_server.extended_version())

        # 退出当前cobbler连接
        # print(remote_server.logout(token))

        # 检测当前token状态，是否失效
        # print(remote_server.token_check(token))

        # 同步DHCP
        # print(remote_server.sync_dhcp(token)

        # 以下是不常用API
        # print(remote_server.get_valid_os_versions())
        # print(remote_server.get_repo_config_for_profile('vm_test1'))
        # print(remote_server.get_repo_config_for_system('t1'))
        # print(remote_server.get_config_data('zhao'))
    except Exception as e:
        print(e)
        exit('remote server:%s error occurred' % server)

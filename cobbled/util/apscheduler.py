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
# ******************************************************************************/
"""
Time:
Author:
Description: Manager scheduler config
"""


from cobbled.conf import configuration

# 从配置文件里获取定时任务调度间隔时间
scheduler_interval_time = configuration.host.get("SCHEDULER_INTERVAL_TIME")


class SchedulerConfig:
    JOBS = [
        {
            'id': '1000',
            'func': 'cobbled.install_manager.view:host_scheduler',  # 函数所在python文件名：函数名
            'trigger': 'cron',  # 使用cron触发器
            'day': '*',  # *表示每一天
            'hour': '*',
            'minute': '0/' + str(scheduler_interval_time),
            'second': '0'
        }
    ]

    SCHEDULER_API_ENABLED = False

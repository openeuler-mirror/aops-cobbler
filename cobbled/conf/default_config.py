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
Description: default config of manager
"""


import os

# cobbler client configuration
cobbler_client = {"IP": "127.0.0.1", "PORT": 8888}

# cobbler server configuration
cobbler_server = {
    "SERVER": "http://127.0.0.1/cobbler_api",
    "USER": "cobbler",
    "PASSWD": "cobbler"
}

# uwsgi configuration
uwsgi = {
    "WSGI-FILE": "manage.py",
    "DAEMONIZE": "/var/log/aops/uwsgi/aops-cobbler.log",
    "HTTP-TIMEOUT": 600,
    "HARAKIRI": 600,
    "PROCESSES": 2,
    "GEVENT": 100
}

# log configuration
log = {
    "LOG_DIR": os.path.join("/", "var", "log", "aops", "cobbler"),
    "LOG_LEVEL": "INFO",
    "MAX_BYTES": 31457280,
    "BACKUP_COUNT": 30,
}

# iso configuration
iso = {
    "UPLOAD_DIR": "/opt/aops/cobbler/iso/upload",
    "MAX_CONTENT_LENGTH": 5 * 1024 * 1024 * 1024,
    "ARCH": "x86_64,aarch64"
}

# ks configuration
ks = {
    "HTTP_DIR": "/var/www/html/"
}

mysql = {
    "IP": "10.10.192.213",
    "PORT": 3306,
    "DATABASE_NAME": "aops",
    "ENGINE_FORMAT": "mysql+pymysql://root:@%s:%s/%s",
    "POOL_SIZE": 100,
    "POOL_RECYCLE": 7200,
}

host = {
  "CHECK_BMC_CONNECTION": 1,
  "SCHEDULER_INTERVAL_TIME": 5,
  "OS_INSTALLED_TIME": 30,
  "OS_INSTALL_LOG_DIR": "/var/log/osinstall/",
  "OS_START_IP": "10.10.192.210",
  "OS_END_IP": "10.10.192.211"
}

script = {
  "SCRIPT_DIR": "/opt/aops/cobbler/script/upload",
  "MAX_CONTENT_LENGTH": 10240
}

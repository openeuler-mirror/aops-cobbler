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
Description: setup up the A-ops cobbler service.
"""


from setuptools import setup, find_packages


setup(
    name='aops-cobbler',
    version='1.0.0',
    packages=find_packages(),
    install_requires=[
        'Flask',
        'Flask-RESTful',
        'requests',
        'Werkzeug',
        'gevent',
        'cryptography',
        'uWSGI',
        'PyMySQL',
        'sqlalchemy'
        'concurrent-log-handler'
    ],
    author='cmd-lsw-yyy-zyc',
    data_files=[
        ('/etc/aops', ['conf/aops-cobbler.ini']),
        ('/usr/lib/systemd/system', ['aops-cobbler.service'])
    ],
    scripts=['aops-cobbler'],
    zip_safe=False,
)

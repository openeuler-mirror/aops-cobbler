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
Description: url set
"""


from cobbled.ks_manager import view as ks_view
from cobbled.install_manager import view as auto_install_view
from cobbled.iso_manager import view as iso_view
from cobbled.host_manager import view as host_view
from cobbled.script_manager import view as script_view
from cobbled.conf.constant import RouteCons

URLS = []

SPECIFIC_URLS = {
    "ISO_URLS": [
        (iso_view.UploadISO, RouteCons.UPLOAD_ISO),
        (iso_view.QueryISO, RouteCons.QUERY_ISO),
        (iso_view.DeleteISO, RouteCons.DELETE_ISO),
    ],
    "KS_URLS": [
        (ks_view.AddKickstart, RouteCons.ADD_KICKSTART),
        (ks_view.QueryKickstart, RouteCons.QUERY_KICKSTART),
        (ks_view.DeleteKickstart, RouteCons.DELETE_KICKSTART),
        (ks_view.UpdateKickstart, RouteCons.UPDATE_KICKSTART),
    ],
    "AUTO_INSTALL_URLS": [
        (auto_install_view.AutoInstall, RouteCons.AUTO_INSTALL),
        (auto_install_view.Notify, RouteCons.NOTIFY),
        (auto_install_view.GetInstallLogFile, RouteCons.DOWNLOAD_LOG_FILE),
    ],
    "HOST_URLS": [
        (host_view.AddHost, RouteCons.ADD_HOST),
        (host_view.BatchAddHost, RouteCons.BATCH_ADD_HOST),
        (host_view.UpdateHost, RouteCons.UPDATE_HOST),
        (host_view.DeleteHost, RouteCons.DELETE_HOST),
        (host_view.QueryHosts, RouteCons.QUERY_HOSTS),
        (host_view.GetHostTemplateFile, RouteCons.GET_HOST_TEMPLATE_FILE),
    ],
    "SCRIPT_URLS": [
            (script_view.UploadScript, RouteCons.UPLOAD_SCRIPT),
            (script_view.QueryScript, RouteCons.QUERY_SCRIPT),
            (script_view.DeleteScript, RouteCons.DELETE_SCRIPT),
        ],
}

for _, value in SPECIFIC_URLS.items():
    URLS.extend(value)

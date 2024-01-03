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
Description: manager constant
"""


class ConfigCons:
    import os

    BASE_CONFIG_PATH = "/etc/aops/"

    # path of manager configuration
    MANAGER_CONFIG_PATH = os.path.join(BASE_CONFIG_PATH, 'aops-cobbler.ini')

    AES_KEY = "Pvopc-H5pspQVa0kRNzXEo3LntLpICjnRDbGIiHC59g="


class RouteCons:
    # cobbler route
    UPLOAD_ISO = "/cobbler/uploadISO"
    QUERY_ISO = "/cobbler/queryISO"
    DELETE_ISO = "/cobbler/deleteISO"

    ADD_KICKSTART = "/cobbler/addKickstart"
    QUERY_KICKSTART = "/cobbler/queryKickstart"
    UPDATE_KICKSTART = "/cobbler/updateKickstart"
    DELETE_KICKSTART = "/cobbler/deleteKickstart"

    AUTO_INSTALL = "/cobbler/autoInstall"
    NOTIFY = "/cobbler/notify"
    DOWNLOAD_LOG_FILE = "/cobbler/downloadLogFile"

    ADD_HOST = "/cobbler/addHost"
    BATCH_ADD_HOST = "/cobbler/batchAddHost"
    UPDATE_HOST = "/cobbler/updateHost"
    DELETE_HOST = "/cobbler/deleteHost"
    QUERY_HOSTS = "/cobbler/queryHosts"
    GET_HOST_TEMPLATE_FILE = "/cobbler/getHostTemplateFile"

    UPLOAD_SCRIPT = "/cobbler/uploadScript"
    QUERY_SCRIPT = "/cobbler/queryScript"
    DELETE_SCRIPT = "/cobbler/deleteScript"


class HostCons:
    # host template file content
    HOST_TEMPLATE_FILE_CONTENT = """host_name,host_mac,bmc_ip,bmc_user_name,bmc_passwd
    test-host1,18:56:44:21:db:ef,10.10.10.1,admin,123456
    test-host2,18:56:44:21:db:ed,10.10.10.2,admin,123456,
    """

    ADD_HOST_FAILED_TIPS = "The host add failed."
    ADD_HOST_SUCCESS_TIPS = "The host add successfully."

    BATCH_ADD_HOST_FAILED_TIPS = "Batch add hosts failed."
    BATCH_ADD_HOST_SUCCESS_TIPS = "Batch add hosts successfully."

    UPDATE_HOST_FAILED_TIPS = "The host update failed."
    UPDATE_HOST_SUCCESS_TIPS = "The host update successfully."

    DELETE_HOST_FAILED_TIPS = "The host delete failed."
    DELETE_HOST_SUCCESS_TIPS = "The host delete successfully."

    QUERY_HOST_FAILED_TIPS = "Query host failed."
    QUERY_HOST_SUCCESS_TIPS = "Query host successfully."

    BMC_IP_DUPLICATED_TIPS = "The bmc ip is duplicated."
    HOST_MAC_DUPLICATED_TIPS = "The host mac is duplicated."

    CHECK_HOST_EXITS_TIPS = "The host not exists."
    CHECK_HOST_NAME_TIPS = "The host_name can not be none and must comply with hostname rules."
    CHECK_HOST_MAC_TIPS = "The host_mac can not be none and must comply with mac rules."
    CHECK_HOST_ID_TIPS = "The host_id can not be none and must be an integer greater than 0."
    CHECK_HOST_LIST_TIPS = "The host list can not be none and length must be less than 100."
    CHECK_BMC_IP_TIPS = "The bmc ip can not be none and must comply with IP rules."
    CHECK_BMC_USER_NAME_TIPS = "The bmc user name can not be none and length must be less than 128."
    CHECK_BMC_PASSWD_TIPS = "The bmc passwd can not be none and length must be less than 128."
    CHECK_HOST_STATUS_TIPS = "The host status must be 0,1,2,3 or 4"
    CHECK_BMC_CONNECTION_TIPS = "Check bmc connection failed."
    CHECK_PAGE_NO_TIPS = "The page_no must be an integer greater than 0."
    CHECK_PAGE_SIZE_TIPS = "The page_size must be an integer greater than 0 and less than 100."


class ISOCons:
    CHECK_ISO_NAME_TIPS = "The iso name can not be none and must be [A-Za-z0-9_-] and must not include arch and " \
                          "length less than 128. "
    CHECK_ISO_ARCH_TIPS = "The iso arch can not be none and must be x86_64 or aarch64."
    CHECK_ISO_SUFFIX_TIPS = "The iso file suffix must be .iso."
    CHECK_ISO_EXITS_TIPS = "The iso file already exists in remote cobbler server."

    UPLOAD_ISO_SUCCESS_TIPS = "The iso background import in progress, please refresh the query list later."
    DELETE_ISO_SUCCESS_TIPS = "The iso delete successfully."


class KsCons:
    CHECK_KS_NAME_TIPS = "The ks name can not be none and must be [A-Za-z0-9_-] and length less than 128."
    CHECK_KS_CONTENT_TIPS = "The ks content can not be none"
    CHECK_KS_EXITS_TIPS = "The kickstart file not exist."

    ADD_KS_SUCCESS_TIPS = "The kickstart add successfully."
    UPDATE_KS_SUCCESS_TIPS = "The kickstart update successfully."
    DELETE_KS_SUCCESS_TIPS = "The kickstart delete successfully."


class InstallCons:
    CHECK_LOG_FILE_EXITS_TIPS = "The os install log file not exists."
    CHECK_LOG_FILE_NAME_TIPS = "The log file name can not be none."
    CHECK_RPM_EXITS_TIPS = "The rpm not exists: "
    CHECK_ISO_EXITS_TIPS = "The iso file not exists in remote cobbler server."
    WRITE_AUTOINSTALL_KS_TIPS = "Write autoinstall ks template to cobbler server error."
    SET_ENABLE_PXE_TIPS = "Modify cobbler server profile to set enable pxe menu error."
    COBBLER_SYNC_TIPS = "Cobbler sync error."
    IPMI_COMMAND_EXECUTE_TIPS = "execute ipmi command to chassis bootdev pxe failed or power reset failed"
    COBBLER_SYSTEM_TIPS = "cobbler remote server save system or sync dhcp failed"

    AUTO_INSTALL_SUCCESS_TIPS = "The os installation command have been successfully announced."
    AUTO_INSTALL_NOTIFY_TIPS = "Notify aops-cobbler to update host info successfully."
    MODIFY_PXE_LINUX_DEFAULT_TIPS = "Modify pxe linux default file to add inst error."
    NO_AVAILABLE_IP_LEFT_TIPS = "There are no available IP resources left"

    MODIFY_PXE_LINUX_DEFAULT_CMD = "cd /var/lib/tftpboot/pxelinux.cfg/ && sed -i 's/ks=/inst.ks=/g' * && sed -i " \
                                   "'s/repo=/inst.repo=/g' * && sed -i 's/kssendmac/inst.kssendmac/g' *"
    INSTALL_LOG_FORWARD_CMD = "\nlogging --host=ip_addr\n"


class ScriptCons:
    CHECK_SCRIPT_NAME_TIPS = "The script name can not be none and must be [A-Za-z0-9_-] and length less than 128."
    CHECK_SCRIPT_SUFFIX_TIPS = "The script file suffix must be .sh."
    CHECK_SCRIPT_SIZE_TIPS = "The script file is too large and must be less than "
    CHECK_SCRIPT_EXITS_TIPS = "The script file not exist."
    CHECK_SCRIPT_FILE_TIPS = "The script file can not be none."
    UPLOAD_SCRIPT_SUCCESS_TIPS = "The script file upload successfully."
    DELETE_SCRIPT_SUCCESS_TIPS = "The script file delete successfully."

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
Description: manager configuration
"""


import os
import configparser
from cobbled.conf import default_config
from cobbled.conf.constant import ConfigCons


class Config:
    """
    Merge system default configuration with configuration file.
    """

    def __init__(self, config_file, default=None):
        """
        Class instance initialization.

        Args:
            config_file(str): configuration file
            default(module): module of default configuration
        """
        # read default configuration

        if default is not None:
            for config in dir(default):
                setattr(self, config, getattr(default, config))

        self.read_config(config_file)

    def _load_conf(self, config_file):
        if not os.path.exists(config_file):
            raise RuntimeError(f"Configuration file does not exist: {config_file}")

        conf = configparser.RawConfigParser()
        try:
            conf.read(config_file)
        except configparser.ParsingError:
            raise RuntimeError(f"Failed to load the configuration file: {config_file}")

        return conf

    def _set_section_value(self, conf, section):
        temp_config = dict()
        for option in conf.items(section):
            try:
                (key, value) = option
            except IndexError:
                continue
            if not value:
                continue
            if value.isdigit():
                value = int(value)
            elif value.lower() in ("true", "false"):
                value = True if value.lower() == "true" else False
            temp_config[key.upper()] = value

        if not temp_config:
            return
        # let default configuration be merged with configuration from config file
        if hasattr(self, section):
            getattr(self, section).update(temp_config)
        else:
            setattr(self, section, temp_config)

    def read_config(self, config_file):
        """
        read configuration from file.

        Args:
            config_file(str): configuration file
        """

        conf = self._load_conf(config_file)

        for section in conf.sections():
            self._set_section_value(conf, section)


# read manager configuration
configuration = Config(ConfigCons.MANAGER_CONFIG_PATH, default_config)

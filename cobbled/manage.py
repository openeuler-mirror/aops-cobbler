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
Description: Manager that start aops-cobbler
"""


from flask_apscheduler import APScheduler

from cobbled.util.apscheduler import SchedulerConfig
from flask import Flask
from flask.blueprints import Blueprint
from flask_restful import Api
from cobbled.conf import configuration
from cobbled.url import URLS
from cobbled.log.log import LOGGER

try:
    from gevent import monkey, pywsgi

    monkey.patch_all(ssl=False)
except:
    pass


def init_application(name: str, settings, register_urls: list = None, config: dict = None):
    """
    Init application
    Returns:
        app: flask application
    """
    service_module = __import__(name, fromlist=[name])
    app = Flask(service_module.__name__)

    # Unique configuration for flask service initialization
    if config:
        for config_item, config_content in config.items():
            app.config[config_item] = config_content

    # url routing address of the api service
    # register the routing address into the blueprint
    if register_urls:
        api = _register_blue_point(register_urls)
        api.init_app(app)
        app.register_blueprint(Blueprint('manager', __name__))

    # sync service config
    for config in [config for config in dir(settings) if not config.startswith("_")]:
        setattr(configuration, config, getattr(settings, config))

    return app


def _register_blue_point(urls):
    api = Api()
    for view, url in urls:
        api.add_resource(view, url)
    return api


app = init_application(name="cobbled", settings=configuration, register_urls=URLS)
app.config.from_object(SchedulerConfig())
scheduler = APScheduler()
# 将调度器对象与Flask应用程序实例(app)相关联
scheduler.init_app(app)
scheduler.start()

if __name__ == "__main__":
    server = pywsgi.WSGIServer((configuration.cobbler_client.get('IP'), configuration.cobbler_client.get('PORT')),
                               app, log=app.logger)
    LOGGER.info("aops-cobbler server Successfully started")
    server.serve_forever()

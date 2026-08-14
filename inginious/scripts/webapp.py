#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#

""" Starts the webapp """

import argparse
import logging
import os
import signal
import sys
from werkzeug.serving import run_simple
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.middleware.shared_data import SharedDataMiddleware

# If INGInious files are not installed in Python path
sys.path.append(os.path.dirname(__file__))

from inginious.common.log import init_logging
from inginious.common.base import load_json_or_yaml
import inginious.frontend.app


def get_app(configfile=None):
    if not configfile:
        if os.path.isfile("./configuration.yaml"):
            configfile = "./configuration.yaml"
        elif os.path.isfile("./configuration.json"):
            configfile = "./configuration.json"
        else:
            raise Exception("No configuration file found")

    # Load configuration and application (!!! For mod_wsgi, application identifier must be present)
    config = load_json_or_yaml(configfile)

    # Init logging
    init_logging(config.get('log_level', 'INFO'))

    application, close_app_func = inginious.frontend.app.get_app(config)

    # Add static redirection and request log
    root_path = inginious.get_root_path()
    application = SharedDataMiddleware(application, [
        ('/static/', os.path.join(root_path, 'frontend', 'static'))
    ])

    # Close the client when interrupting the app
    def close_app_signal():
        close_app_func()
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, lambda _, _2: close_app_signal())
    signal.signal(signal.SIGTERM, lambda _, _2: close_app_signal())

    return config, application

def main():
    # Parse the paramaters from command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",
                        help="Path to configuration file. By default: configuration.yaml or configuration.json", default=os.environ.get("INGINIOUS_WEBAPP_CONFIG", ""))
    parser.add_argument("--host", help="Host to bind to. Default is localhost.", default=os.environ.get("INGINIOUS_WEBAPP_HOST", "localhost"))
    parser.add_argument("--port", help="Port to listen to. Default is 8080.", type=int, default=os.environ.get("INGINIOUS_WEBAPP_PORT", "8080"))
    args = parser.parse_args()

    host = args.host
    port = args.port
    configfile = args.config

    config, application = get_app(configfile)
    logging.getLogger("inginious.webapp").info("http://%s:%d/" % (host, int(port)))

    # Fix Reverse Proxy
    reverse_proxy_config = config.get('reverse-proxy-config', {})
    reverse_proxy_enable = reverse_proxy_config.get('enable', False)
    x_for = reverse_proxy_config.get('x-for', 1)
    x_host = reverse_proxy_config.get('x-host', 1)

    if reverse_proxy_enable:
        application = ProxyFix(application, x_for=x_for, x_host=x_host)

    # Launch the app
    run_simple(host, port, application, use_debugger=config.get("web_debug", False), threaded=True)


if __name__ == "__main__":
    main()
else:
    config, application = get_app(os.environ.get("INGINIOUS_WEBAPP_CONFIG"))

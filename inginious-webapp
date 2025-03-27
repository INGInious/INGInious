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

from inginious.common.log import init_logging, CustomLogMiddleware
from inginious.common.base import load_json_or_yaml
import inginious.frontend.app


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
    logging.getLogger("inginious.webapp").info("http://%s:%d/" % (host, int(port)))

    application, close_app_func = inginious.frontend.app.get_app(config)

    if 'SERVER_SOFTWARE' in os.environ:  # cgi
        os.environ['FCGI_FORCE_CGI'] = 'Y'

    if 'PHP_FCGI_CHILDREN' in os.environ or 'SERVER_SOFTWARE' in os.environ:  # lighttpd fastcgi
        import flup.server.fcgi as flups
        flups.WSGIServer(application, multiplexed=True, bindAddress=None, debug=False).run()

    # Fix Reverse Proxy
    reverse_proxy_config = config.get('reverse-proxy-config', {})
    reverse_proxy_enable = reverse_proxy_config.get('enable', False)
    x_for = reverse_proxy_config.get('x-for', 1)
    x_host = reverse_proxy_config.get('x-host', 1)

    if reverse_proxy_enable:
        application = ProxyFix(application, x_for=x_for, x_host=x_host)

    # Close the client when interrupting the app
    def close_app_signal():
        close_app_func()
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, lambda _, _2: close_app_signal())
    signal.signal(signal.SIGTERM, lambda _, _2: close_app_signal())

    # Add static redirection and request log
    root_path = inginious.get_root_path()
    application = SharedDataMiddleware(application, [
        ('/static/', os.path.join(root_path, 'frontend', 'static'))
    ])
    application = CustomLogMiddleware(application, logging.getLogger("inginious.webapp.requests"))

    # Launch the app
    run_simple(host, port, application, use_debugger=config.get("web_debug", False), threaded=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#

""" Starts the webdav """

import argparse
import logging
import os
import sys
from werkzeug.serving import run_simple
from werkzeug.wsgi import get_input_stream

# If INGInious files are not installed in Python path
sys.path.append(os.path.dirname(__file__))

from inginious.common.log import init_logging
from inginious.common.base import load_json_or_yaml
import inginious.frontend.webdav


def limited_input_middleware(app):
    # Ensure wsgi.input is a bounded stream
    def new_app(environ, start_response):
        environ['wsgi.input'] = get_input_stream(environ)
        return app(environ, start_response)
    return new_app

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

    application = inginious.frontend.webdav.get_app(config)

    if 'SERVER_SOFTWARE' in os.environ:  # cgi
        os.environ['FCGI_FORCE_CGI'] = 'Y'

    # Ensure WsgiDAV receive limited streams for PUT requests
    return config, limited_input_middleware(application)

def main():
    # Parse the paramaters from command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",
                        help="Path to configuration file. By default: configuration.yaml or configuration.json", default=os.environ.get("INGINIOUS_WEBAPP_CONFIG", ""))
    parser.add_argument("--host", help="Host to bind to. Default is localhost.", default=os.environ.get("INGINIOUS_WEBDAV_HOST", "localhost"))
    parser.add_argument("--port", help="Port to listen to. Default is 8080.", type=int, default=os.environ.get("INGINIOUS_WEBDAV_PORT", "8080"))
    args = parser.parse_args()

    host = args.host
    port = args.port
    configfile = args.config

    config, application = get_app(configfile)
    logging.getLogger("inginious.webdav").info("http://%s:%d/" % (host, int(port)))

    # Launch the app
    run_simple(host, port, application, use_debugger=config.get("web_debug", False), threaded=True)


if __name__ == "__main__":
    main()
else:
    config, application = get_app(os.environ.get("INGINIOUS_WEBAPP_CONFIG"))

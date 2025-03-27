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

# If INGInious files are not installed in Python path
sys.path.append(os.path.dirname(__file__))

from inginious.common.log import init_logging, CustomLogMiddleware
from inginious.common.base import load_json_or_yaml
import inginious.frontend.webdav


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
    logging.getLogger("inginious.webdav").info("http://%s:%d/" % (host, int(port)))
    application = inginious.frontend.webdav.get_app(config)

    if 'SERVER_SOFTWARE' in os.environ:  # cgi
        os.environ['FCGI_FORCE_CGI'] = 'Y'

    if 'PHP_FCGI_CHILDREN' in os.environ or 'SERVER_SOFTWARE' in os.environ:  # lighttpd fastcgi
        import flup.server.fcgi as flups
        flups.WSGIServer(application, multiplexed=True, bindAddress=None, debug=False).run()

    # Add static redirection and request log
    application = CustomLogMiddleware(application, logging.getLogger("inginious.webdav.requests"))

    # Launch the app
    run_simple(host, port, application, use_debugger=config.get("web_debug", False), threaded=True)


if __name__ == "__main__":
    main()

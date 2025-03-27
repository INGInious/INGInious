# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#

import os
from inginious.common.base import load_json_or_yaml


def get_config():
    #Parse the parameters from environment variables
    configfile = os.environ.get("INGINIOUS_WEBAPP_CONFIG", "")

    if not configfile:
        if os.path.isfile("./configuration.yaml"):
            configfile = "./configuration.yaml"
        elif os.path.isfile("./configuration.json"):
            configfile = "./configuration.json"
        else:
            raise Exception("No configuration file found")

    # Load configuration and application (!!! For mod_wsgi, application identifier must be present)
    return load_json_or_yaml(configfile)
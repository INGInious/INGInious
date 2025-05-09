# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#

from inginious.common.log import init_logging
from inginious.frontend.wsgi.common import get_config
import inginious.frontend.app

config = get_config()

# Init logging
init_logging(config.get('log_level', 'INFO'))

# Load application (!!! For mod_wsgi, application identifier must be present)
application, close_app_func = inginious.frontend.app.get_app(config)

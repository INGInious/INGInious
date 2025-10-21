# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" A demo plugin that adds a page """
from inginious.frontend.pages.utils import INGIniousPage


class DemoPage(INGIniousPage):
    """ A simple demo page showing how to add a new page """

    def GET(self):
        """ GET request """
        return "This is a simple demo plugin"


def init(plugin_manager, client, config):
    """ Init the plugin """
    plugin_manager.add_page("/plugindemo", DemoPage.as_view('demopage'))

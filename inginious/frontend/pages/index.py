# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Index page """
from flask import current_app, redirect, url_for
from inginious.frontend.pages.utils import INGIniousStaticPage


class IndexPage(INGIniousStaticPage):
    """ Index page """

    def GET(self):  # pylint: disable=arguments-differ
        """ Display main course list page """
        if "WELCOME_PAGE" in current_app.config:
            return self.show_page(current_app.config["WELCOME_PAGE"])
        return redirect(self.app.get_path("courselist"))


    def POST(self):  # pylint: disable=arguments-differ
        """ Display main course list page """
        return self.GET()
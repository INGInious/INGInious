# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" API token page """
from flask import session, request, redirect, render_template, url_for

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.models import User


class APITokenPage(INGIniousAuthPage):
    """ Page to view or generate an API token for the user """

    def GET_AUTH(self):
        """ GET request """

        api_token = User.objects(username=session["username"]).first().apitoken

        return self.show_page(api_token=api_token)

    def POST_AUTH(self):
        """ POST request """
        # Change to teacher privilege when created

        return self.show_page()

    def show_page(self, errors=None, api_token=None):
        """ Prepares and shows the course marketplace """
        if errors is None:
            errors = []
        token = "my_token" # TODO : get from DB, Is it safe to simply get from DB or should we never show and generate a new one if the user forgot it ?
        return render_template("apitoken.html", api_token=api_token)
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Maintenance page """

from flask import render_template
from flask.views import MethodView


class MaintenancePage(MethodView):
    """ Maintenance page """

    def get(self, path=None):
        """ GET request """
        return render_template("maintenance.html")

    def post(self, path=None):
        """ POST request """
        return render_template("maintenance.html")

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Profile page """
from flask import request, redirect, render_template
from werkzeug.exceptions import Forbidden

from inginious.frontend.pages.utils import INGIniousAuthPage


class DeletePage(INGIniousAuthPage):
    """ Delete account page for DB-authenticated users"""

    def delete_account(self, data):
        """ Delete account from DB """
        error = False
        msg = ""

        username = self.user_manager.session_username()
        result = self.user_manager.delete_user(username, data.get("delete_email", ""))

        if not result:
            error = True
            msg = _("The specified email is incorrect.")
        else:
            self.user_manager.disconnect_user()
        return msg, error

    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ GET request """
        userdata = self.database.users.find_one({"username": self.user_manager.session_username()})

        if not userdata or not self.app.allow_deletion:
            raise Forbidden(description=_("User unavailable or deletion is forbidden."))

        return render_template("preferences/delete.html", msg="", error=False)

    def POST_AUTH(self):  # pylint: disable=arguments-differ
        """ POST request """
        userdata = self.database.users.find_one({"username": self.user_manager.session_username()})

        if not userdata or not self.app.allow_deletion:
            raise Forbidden(description=_("User unavailable or deletion forbidden."))

        msg = ""
        error = False
        data = request.form
        if "delete" in data:
            msg, error = self.delete_account(data)
            if not error:
                return redirect("/index")

        return render_template("preferences/delete.html", msg=msg, error=error)

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Profile page """
from flask import current_app, session, request, redirect, render_template, url_for
from werkzeug.exceptions import Forbidden

from inginious.frontend.pages.utils import INGIniousAuthPage

class DeletePage(INGIniousAuthPage):
    """ Delete account page for DB-authenticated users"""

    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ GET request """
        if not current_app.config.get("ALLOW_DELETION"):
            raise Forbidden(description=_("User unavailable or deletion is forbidden."))

        return render_template("preferences/delete.html", msg="", error=False)

    def POST_AUTH(self):  # pylint: disable=arguments-differ
        """ POST request """
        if not current_app.config.get("ALLOW_DELETION"):
            raise Forbidden(description=_("User unavailable or deletion forbidden."))

        msg = ""
        error = False
        data = request.form
        if "delete" in data:
            if not session.email == data.get("delete_email", "").strip():
                msg = _("The specified email is incorrect.")
                error = True
            else:
                error, msg = self.user_manager.delete_user(session.username)
                if not error:
                    self.user_manager.disconnect_user()
                    return redirect(url_for("indexpage"))

        return render_template("preferences/delete.html", msg=msg, error=error)

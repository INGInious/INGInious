# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Auth bindings page """
from flask import request, redirect, render_template

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend import database
from inginious.frontend.user_manager import user_manager

class BindingsPage(INGIniousAuthPage):
    """ Bindings page for DB-authenticated users"""

    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ GET request """
        auth_methods = user_manager.get_auth_methods()
        user_data = user_manager.get_user_info(user_manager.session_username())
        bindings = user_data.bindings
        return render_template("preferences/bindings.html", bindings=bindings,
                                           auth_methods=auth_methods, msg="", error=False)

    def POST_AUTH(self):  # pylint: disable=arguments-differ
        """ POST request """
        msg = ""
        error = False

        user_data = database.users.find_one({"username": user_manager.session_username()})

        if not user_data:
            raise self.app.notfound(message=_("User doesn't exist."))

        user_input = request.form
        auth_methods = user_manager.get_auth_methods()

        if "auth_binding" in user_input:
            auth_binding = user_input["auth_binding"]

            if auth_binding not in auth_methods.keys():
                error = True
                msg = _("Incorrect authentication binding.")
            elif auth_binding not in user_data.get("bindings", {}):
                return redirect("/auth/signin/" + auth_binding)
        elif "revoke_auth_binding" in user_input:
            auth_id = user_input["revoke_auth_binding"]
            error, msg = user_manager.revoke_binding(user_manager.session_username(), auth_id)

        bindings = user_data.get("bindings", {})

        return render_template("preferences/bindings.html", bindings=bindings,
                                           auth_methods=auth_methods, msg=msg, error=error)

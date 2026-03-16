# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Auth page """
from flask import current_app, redirect, session, request, url_for

from inginious.frontend.pages.utils import INGIniousPage


class AuthenticationPage(INGIniousPage):
    def process_signin(self,auth_id):
        auth_method = self.user_manager.get_auth_method(auth_id)
        if not auth_method:
            raise current_app.notfound(message=_("Auth method doesn't exist"))

        auth_storage = session.auth_storage.setdefault(auth_id, {})
        auth_storage["redir_url"] = request.referrer or '/'
        auth_link = auth_method.get_auth_link(auth_storage)
        return redirect(auth_link)

    def GET(self, auth_id):
        if session.is_lti:
            return redirect(url_for("authenticationpage",auth_id=auth_id))
        return self.process_signin(auth_id)

    def POST(self, auth_id):
        return self.process_signin(auth_id)


class CallbackPage(INGIniousPage):
    def process_callback(self, auth_id):
        auth_method = self.user_manager.get_auth_method(auth_id)
        if not auth_method:
            raise current_app.notfound(message=_("Auth method doesn't exist."))

        auth_storage = session.auth_storage.setdefault(auth_id, {})
        user = auth_method.callback(auth_storage)
        if not user:
            return redirect(url_for("signinpage", callbackerror=""))
        if not self.user_manager.bind_user(auth_id, user):
            return redirect(url_for("signinpage", binderror=""))

        return redirect(auth_storage.get("redir_url", "/"))

    def GET(self, auth_id):
        if session.is_lti:
            return redirect(url_for("authenticationpage", auth_id=auth_id))
        return self.process_callback(auth_id)

    def POST(self, auth_id):
        return self.process_callback(auth_id)

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LTI """

import secrets

from flask import redirect, render_template, session, request
from werkzeug.exceptions import Forbidden

from inginious.frontend.pages.utils import INGIniousPage, INGIniousAuthPage
from inginious.frontend.models import LaunchData
from inginious.frontend.controllers import auth


def login_or_bind(launch):
    """
    Connects the INGInious user bound to the LTI user of the launch and redirects to the launched page.
    Otherwise, returns the login template that invites to bind an account, holding the launch token.
    """
    if auth.lti_login(launch):
        return redirect(launch.lti.redir_url)

    token = launch.token or secrets.token_urlsafe(32)
    launch.update(set__token=token)
    return render_template("lti/login.html", lti_version=launch.lti.version, token=token)


class LTIBindPage(INGIniousAuthPage):
    """
    Opened in a new window by the LTI login page. With partitioned cookies, this window does not share the session
    of the LMS frame, which hands it the launch token via postMessage (same origin only).
    """
    _lti_version = ""

    def _render(self, **kwargs):
        return render_template("lti/bind.html", lti_version=self._lti_version, **kwargs)

    def GET_AUTH(self):
        return self._render()  # the page then waits for the bind token from the LMS frame

    def POST_AUTH(self):
        token = request.form.get("token")
        launch = LaunchData.objects(token=token, lti__version=self._lti_version).first() if token else None
        if launch is None:
            return self._render(error=_("Invalid or expired LTI launch, please refresh the LMS page."))

        if "confirm" not in request.form:
            return self._render(data=launch.lti, token=token)

        if not auth.bind_lti(session.username, launch.lti):
            return self._render(error=_("Your account is already bound with this context."))

        return self._render(success=True)  # the LMS frame then logs in with the launch token


class LTILoginPage(INGIniousPage):
    """
    Posted by the LTI login page with its launch token, once an account is bound. The launch is not looked up through
    the session: LMS frames opened simultaneously without cookies each get their own one, only one surviving.
    """
    _lti_version = ""

    def POST(self):
        token = request.form.get("token")
        launch = LaunchData.objects(token=token, lti__version=self._lti_version).first() if token else None
        if launch is None:
            raise Forbidden(description=_("No LTI data available."))
        return login_or_bind(launch)

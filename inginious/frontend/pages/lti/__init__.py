# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LTI """

import secrets

from flask import redirect, render_template, session, request
from werkzeug.exceptions import Forbidden

from inginious.frontend.pages.utils import INGIniousPage, INGIniousAuthPage
from inginious.frontend.models import User, LaunchData


class LTIBindPage(INGIniousAuthPage):
    """
    Opened in a new window by the LTI login page. With partitioned cookies, this window does not share the session
    of the LMS frame, which hands it the bind token of the launch via postMessage (same origin only).
    """
    _lti_version = ""

    def _render(self, **kwargs):
        return render_template("lti/bind.html", lti_version=self._lti_version, **kwargs)

    def GET_AUTH(self):
        return self._render()  # the page then waits for the bind token from the LMS frame

    def POST_AUTH(self):
        token = request.form.get("token")
        launch = LaunchData.objects(bind_token=token, lti__version=self._lti_version).first() if token else None
        if launch is None:
            return self._render(error=_("Invalid or expired LTI launch, please refresh the LMS page."))

        data = launch.lti
        if "confirm" not in request.form:
            return self._render(data=data, token=token)

        binding_key = data.binding_key
        user_profile = User.objects.get(username=session.username)
        lti_user_profile = User.objects(**{"ltibindings__" + binding_key: data["username"]}).first()
        if not user_profile.ltibindings.get(binding_key, "") and not lti_user_profile:
            # There is no binding yet, so bind LTI to this account
            user_profile.ltibindings[binding_key] = data["username"]
            user_profile.save()
        elif not (lti_user_profile and user_profile["username"] == lti_user_profile["username"]):
            # There exists an LTI binding for another account, refuse auth!
            self.logger.info("User %s tried to bind LTI user %s in for %s, but %s is already bound.",
                             user_profile["username"],
                             data["username"],
                             binding_key,
                             user_profile.ltibindings.get(binding_key, ""))
            return self._render(error=_("Your account is already bound with this context."))

        launch.update(unset__bind_token=True)  # single use
        return self._render(success=True)


class LTILoginPage(INGIniousPage):
    _lti_version = ""

    def GET(self, launch_id):
        """
            Checks if user is authenticated and valides the pending LTI launch.
            Otherwise, returns the login templates that invites to bind account.
        """
        launch = LaunchData.objects(session_id=session.id, launch_id=launch_id, lti__version=self._lti_version).first()
        if launch is None:
            raise Forbidden(description=_("No LTI data available."))

        search = {"ltibindings__" + launch.lti.binding_key: launch.lti.username}
        user_profile = User.objects(**search).first()

        if user_profile:
            if not session.loggedin or session.username != user_profile.username:
                self.user_manager.connect_user(user_profile)
            launch.update(set__lti__valid=True)
            return redirect(launch.lti.redir_url)

        bind_token = secrets.token_urlsafe(32)
        launch.update(set__bind_token=bind_token)
        return render_template("lti/login.html", lti_version=self._lti_version, bind_token=bind_token)

    def POST(self, launch_id):
        return self.GET(launch_id)


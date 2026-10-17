# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LTI """

from flask import  redirect, render_template, session
from werkzeug.exceptions import Forbidden

from inginious.frontend.pages.utils import INGIniousPage, INGIniousAuthPage
from inginious.frontend.models import User, LISLaunch


class LTIBindPage(INGIniousAuthPage):
    _lti_version = ""
    _launch_model = LISLaunch

    def _get_lti_data(self, launch_id):
        launch = self._launch_model.objects(session_id=session.id, launch_id=launch_id, lti__exists=True).first()
        if launch is None:
            return None, render_template("lti/bind.html", success=False,
                                                     data=None, error=_("Invalid LTI launch id"))
        return launch.lti, None

    def GET_AUTH(self, launch_id):
        data, error = self._get_lti_data(launch_id)
        if error:
            return error
        return render_template("lti/bind.html", success=False, data=data, error="")

    def POST_AUTH(self, launch_id):
        data, error = self._get_lti_data(launch_id)
        if error:
            return error

        if data:
            field = data.platform_instance_id.replace(".", "").replace("$", "")
            user_profile = User.objects.get(username=session.username)
            lti_user_profile = User.objects(**{"ltibindings__" + field: data["username"]}).first()
            if not user_profile.ltibindings.get(field, "") and not lti_user_profile:
                # There is no binding yet, so bind LTI to this account
                user_profile.ltibindings[field] = data["username"]
                user_profile.save()
            elif not (lti_user_profile and user_profile["username"] == lti_user_profile["username"]):
                # There exists an LTI binding for another account, refuse auth!
                self.logger.info("User %s tried to bind LTI user %s in for %s, but %s is already bound.",
                                 user_profile["username"],
                                 data["username"],
                                 field,
                                 user_profile.ltibindings.get(field, ""))
                return render_template("lti/bind.html", lti_version=self._lti_version, success=False,
                                                   data=data, error=_("Your account is already bound with this context."))

        return render_template("lti/bind.html", lti_version=self._lti_version, success=True, data=data, error="")


class LTILoginPage(INGIniousPage):
    _lti_version = ""
    _launch_model = LISLaunch

    def GET(self, launch_id):
        """
            Checks if user is authenticated and valides the pending LTI launch.
            Otherwise, returns the login templates that invites to bind account.
        """
        launch = self._launch_model.objects(session_id=session.id, launch_id=launch_id, lti__exists=True).first()
        if launch is None:
            raise Forbidden(description=_("No LTI data available."))

        search = {"ltibindings__" + launch.lti.platform_instance_id.replace(".", "").replace("$", ""): launch.lti.username}
        user_profile = User.objects(**search).first()

        if user_profile:
            if not session.loggedin or session.username != user_profile.username:
                self.user_manager.connect_user(user_profile)
            launch.update(set__lti__valid=True)
            return redirect(launch.lti.redir_url)

        return render_template("lti/login.html", lti_version=self._lti_version, launch_id=launch_id)

    def POST(self, launch_id):
        return self.GET(launch_id)

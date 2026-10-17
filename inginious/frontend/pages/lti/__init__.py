# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LTI """

from flask import  redirect, render_template, session
from werkzeug.exceptions import Forbidden

from inginious.frontend.pages.utils import INGIniousPage, INGIniousAuthPage
from inginious.frontend.models import User, LISLaunch, LaunchData

_launch_models = {"1.1": LISLaunch, "1.3": LaunchData}


def lti_binding_field(platform_instance_id):
    """ Returns the User.ltibindings key for a given platform instance """
    return platform_instance_id.replace(".", "").replace("$", "")


def get_launch(version, launch_id):
    """ Returns the launch message identified by launch_id, None otherwise. """
    model = _launch_models.get(version)
    return model.get_launch(launch_id) if model is not None and launch_id is not None else None


def get_launch_user(launch, username=None):
    """ Returns the INGInious user bound to the LTI user of the launch message, optionally filtered by username """
    search = {"ltibindings__" + lti_binding_field(launch.lti.platform_instance_id): launch.lti.username}
    if username is not None:
        search["username"] = username
    return User.objects(**search).first()


def get_session_launch(version, launch_id, courseid=None, taskid=None):
    """
    Returns the launch message identified by launch_id if its LTI user is bound to the user of the current LTI
    session and, if courseid is given, if it was issued for the given task. Returns None otherwise.
    """
    if not session.is_lti or not session.loggedin:
        return None

    launch = get_launch(version, launch_id)
    if launch is None or (courseid is not None and list(launch.lti.task) != [courseid, taskid]):
        return None
    return launch if get_launch_user(launch, session.username) is not None else None


class LTIBindPage(INGIniousAuthPage):
    _lti_version = ""

    def is_lti_page(self):
        return False

    def _get_lti_data(self, launch_id):
        launch = get_launch(self._lti_version, launch_id)
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
            field = lti_binding_field(data.platform_instance_id)
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

    def is_lti_page(self):
        return True

    def GET(self, launch_id):
        """
            Checks if user is authenticated and calls POST_AUTH or performs login and calls GET_AUTH.
            Otherwise, returns the login template.
        """
        launch = get_launch(self._lti_version, launch_id) if session.is_lti else None
        if launch is None:
            raise Forbidden(description=_("No LTI data available."))

        user_profile = get_launch_user(launch)
        if user_profile:
            self.user_manager.connect_user(user_profile)

        if session.loggedin:
            return redirect(launch.lti.redir_url)

        return render_template("lti/login.html", lti_version=self._lti_version)

    def POST(self, launch_id):
        """
        Checks if user is authenticated and calls POST_AUTH or performs login and calls GET_AUTH.
        Otherwise, returns the login template.
        """
        return self.GET(launch_id)

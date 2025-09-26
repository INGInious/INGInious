# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LTI """

from flask import redirect, request, render_template
from werkzeug.exceptions import Forbidden

from inginious.frontend.pages.utils import INGIniousPage, INGIniousAuthPage
from inginious.frontend.pages.tasks import BaseTaskPage

from inginious.frontend import database
from inginious.frontend.user_manager import user_manager
from inginious.frontend.course_factory import course_factory

class LTITaskPage(INGIniousAuthPage):
    def is_lti_page(self):
        return True

    def GET_AUTH(self):
        data = user_manager.session_lti_info()
        if data is None:
            raise Forbidden(description=_("No LTI data available."))
        (courseid, taskid) = data['task']

        return BaseTaskPage(self).GET(courseid, taskid, True)

    def POST_AUTH(self):
        data = user_manager.session_lti_info()
        if data is None:
            raise Forbidden(description=_("No LTI data available."))
        (courseid, taskid) = data['task']

        return BaseTaskPage(self).POST(courseid, taskid, True)


class LTIAssetPage(INGIniousAuthPage):
    def is_lti_page(self):
        return True

    def GET_AUTH(self, asset_url):
        data = user_manager.session_lti_info()
        if data is None:
            raise Forbidden(description=_("No LTI data available."))
        (courseid, _) = data['task']
        return redirect(self.app.get_path("course", courseid, asset_url))


class LTIBindPage(INGIniousAuthPage):
    _field = "consumer_key"
    _ids_fct = lambda cls, course: course.lti_keys().keys()
    _lti_version = ""

    def is_lti_page(self):
        return False

    def _get_lti_session_data(self):
        data = database.lti_sessions.find_one({'session_id': request.args['lti_session_id']}) if 'lti_session_id' in request.args else None
        if data is None or data.get("lti", None) is None:
            return None, render_template("lti/bind.html", success=False,
                                                     data=None, error=_("Invalid LTI session id"))
        return data.get("lti"), None

    def GET_AUTH(self):
        data, error = self._get_lti_session_data()
        if error:
            return error
        return render_template("lti/bind.html", success=False, data=data, error="")

    def POST_AUTH(self):
        data, error = self._get_lti_session_data()
        if error:
            return error

        try:
            course = course_factory.get_course(data["task"][0])
            if data[self._field] not in self._ids_fct(course):
                raise Exception()
        except:
            return render_template("lti/bind.html", success=False, data=None, error=_("Invalid LTI data"))

        if data:
            user_profile = database.users.find_one({"username": user_manager.session_username()})
            lti_user_profile = database.users.find_one(
                {"ltibindings." + data["task"][0] + "." + data[self._field]: data["username"]})
            if not user_profile.get("ltibindings", {}).get(data["task"][0], {}).get(data[self._field],
                                                                                    "") and not lti_user_profile:
                # There is no binding yet, so bind LTI to this account
                database.users.find_one_and_update({"username": user_manager.session_username()}, {"$set": {
                    "ltibindings." + data["task"][0] + "." + data[self._field]: data["username"]}})
            elif not (lti_user_profile and user_profile["username"] == lti_user_profile["username"]):
                # There exists an LTI binding for another account, refuse auth!
                self.logger.info("User %s tried to bind LTI user %s in for %s:%s, but %s is already bound.",
                                 user_profile["username"],
                                 data["username"],
                                 data["task"][0],
                                 data[self._field],
                                 user_profile.get("ltibindings", {}).get(data["task"][0], {}).get(data[self._field], ""))
                return render_template("lti/bind.html", lti_version=self._lti_version, success=False,
                                                   data=data, error=_("Your account is already bound with this context."))

        return render_template("lti/bind.html", lti_version=self._lti_version, success=True, data=data, error="")


class LTILoginPage(INGIniousPage):
    _field = "consumer_key"
    _ids_fct = lambda cls, course: course.lti_keys().keys()
    _lti_version = ""

    def is_lti_page(self):
        return True

    def GET(self):
        """
            Checks if user is authenticated and calls POST_AUTH or performs login and calls GET_AUTH.
            Otherwise, returns the login template.
        """
        data = user_manager.session_lti_info()
        if data is None:
            raise Forbidden(description=_("No LTI data available."))

        try:
            course = course_factory.get_course(data["task"][0])
            if data[self._field] not in self._ids_fct(course):
                raise Exception()
        except:
            return render_template("lti/bind.html", lti_version=self._lti_version, success=False,
                                               session_id="", data=None, error="Invalid LTI data")

        user_profile = database.users.find_one({"ltibindings." + data["task"][0] + "." + data[self._field]: data["username"]})
        if user_profile:
            user_manager.connect_user(user_profile)

        if user_manager.session_logged_in():
            return redirect(self.app.get_path("lti", "task"))

        return render_template("lti/login.html", lti_version=self._lti_version)

    def POST(self):
        """
        Checks if user is authenticated and calls POST_AUTH or performs login and calls GET_AUTH.
        Otherwise, returns the login template.
        """
        return self.GET()

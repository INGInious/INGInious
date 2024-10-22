# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import hashlib
import flask
from flask import jsonify, redirect
from werkzeug.exceptions import Forbidden, NotFound
from inginious.frontend.pages.utils import INGIniousPage, INGIniousAuthPage
from itsdangerous import want_bytes

from inginious.common import exceptions
from inginious.frontend.pages.tasks import BaseTaskPage
from inginious.frontend.lti_grade_manager import MongoLTILaunchDataStorage

from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch, FlaskRequest


class LTITaskPage(INGIniousAuthPage):
    def is_lti_page(self):
        return True

    def GET_AUTH(self):
        data = self.user_manager.session_lti_info()
        if data is None:
            raise Forbidden(description=_("No LTI data available."))
        (courseid, taskid) = data['task']

        return BaseTaskPage(self).GET(courseid, taskid, True)

    def POST_AUTH(self):
        data = self.user_manager.session_lti_info()
        if data is None:
            raise Forbidden(description=_("No LTI data available."))
        (courseid, taskid) = data['task']

        return BaseTaskPage(self).POST(courseid, taskid, True)


class LTIAssetPage(INGIniousAuthPage):
    def is_lti_page(self):
        return True

    def GET_AUTH(self, asset_url):
        data = self.user_manager.session_lti_info()
        if data is None:
            raise Forbidden(description=_("No LTI data available."))
        (courseid, _) = data['task']
        return redirect(self.app.get_path("course", courseid, asset_url))


class LTIBindPage(INGIniousAuthPage):
    def is_lti_page(self):
        return False

    def _get_lti_session_data(self):
        if not self.user_manager.session_is_lti():
            return self.template_helper.render("lti_bind.html", success=False, data=None, error=_("Missing LTI session id"))

        data = self.user_manager.session_lti_info()
        if data is None:
            return None, self.template_helper.render("lti_bind.html", success=False, data=None, error=_("Invalid LTI session id"))
        return data, None

    def GET_AUTH(self):
        data, error = self._get_lti_session_data()
        if error:
            return error
        return self.template_helper.render("lti_bind.html", success=False, data=data, error="")

    def POST_AUTH(self):
        data, error = self._get_lti_session_data_or_error()
        if error:
            return error

        try:
            course = self.course_factory.get_course(data["task"][0])
            if data["platform_instance_id"] not in course.lti_platform_instances_ids():
                raise Exception()
        except:
            return self.template_helper.render("lti_bind.html", success=False, data=None, error=_("Invalid LTI data"))

        if data:
            user_profile = self.database.users.find_one({"username": self.user_manager.session_username()})
            lti_user_profile = self.database.users.find_one(
                {"ltibindings." + data["task"][0] + "." + data["platform_instance_id"]: data["username"]})
            if not user_profile.get("ltibindings", {}).get(data["task"][0], {}).get(data["platform_instance_id"],
                                                                                    "") and not lti_user_profile:
                # There is no binding yet, so bind LTI to this account
                self.database.users.find_one_and_update({"username": self.user_manager.session_username()}, {"$set": {
                    "ltibindings." + data["task"][0] + "." + data["platform_instance_id"]: data["username"]}})
            elif not (lti_user_profile and user_profile["username"] == lti_user_profile["username"]):
                # There exists an LTI binding for another account, refuse auth!
                self.logger.info("User %s tried to bind LTI user %s in for %s:%s, but %s is already bound.",
                                 user_profile["username"],
                                 data["username"],
                                 data["task"][0],
                                 data["platform_instance_id"],
                                 user_profile.get("ltibindings", {}).get(data["task"][0], {}).get(data["platform_instance_id"], ""))
                return self.template_helper.render("lti_bind.html", success=False, data=data,
                                                   error=_("Your account is already bound with this context."))

        return self.template_helper.render("lti_bind.html", success=True, data=data, error="")


class LTIJWKSPage(INGIniousPage):
    endpoint = 'ltijwkspage'

    def GET(self, courseid, keyset_hash):
        try:
            course = self.course_factory.get_course(courseid)
        except exceptions.CourseNotFoundException as ex:
            raise NotFound(description=_(str(ex)))

        lti_config = course.lti_config()
        for issuer in lti_config:
            for client_config in lti_config[issuer]:
                if keyset_hash == course.lti_keyset_hash(issuer, client_config['client_id']):
                    tool_conf = course.lti_tool()
                    return jsonify(tool_conf.get_jwks(iss=issuer, client_id=client_config['client_id']))

        raise NotFound(description=_("Keyset not found"))


class LTIOIDCLoginPage(INGIniousPage):
    endpoint = 'ltioidcloginpage'

    def _handle_oidc_login_request(self, courseid):
        """ Initiates the LTI 1.3 OIDC login. """
        try:
            course = self.course_factory.get_course(courseid)
        except exceptions.CourseNotFoundException as ex:
            raise NotFound(description=_(str(ex)))

        flask_request = FlaskRequest()
        target_link_uri = flask_request.get_param('target_link_uri')
        if not target_link_uri:
            raise Exception('Missing "target_link_uri" param')
        taskid = target_link_uri.split('/')[-1]

        launch_data_storage = MongoLTILaunchDataStorage(self.database, courseid, taskid)
        oidc_login = FlaskOIDCLogin(flask_request, course.lti_tool(), launch_data_storage=launch_data_storage)
        return oidc_login.enable_check_cookies().redirect(target_link_uri)

    def GET(self, courseid):
        return self._handle_oidc_login_request(courseid)

    def POST(self, courseid):
        return self._handle_oidc_login_request(courseid)


class LTILaunchPage(INGIniousPage):
    endpoint = 'ltilaunchpage'

    def _handle_message_launch(self, courseid, taskid):
        """ Decrypt and process the LTI Launch message. """
        try:
            course = self.course_factory.get_course(courseid)
        except exceptions.CourseNotFoundException as ex:
            raise NotFound(description=_(str(ex)))

        tool_conf = course.lti_tool()
        launch_data_storage = MongoLTILaunchDataStorage(self.database, courseid, taskid)
        flask_request = FlaskRequest()
        message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)

        launch_id = message_launch.get_launch_id()  # TODO(mp): With a good use of the cache, this could be used as a non-session id
        launch_data = message_launch.get_launch_data()

        user_id = launch_data['sub']
        roles = launch_data['https://purl.imsglobal.org/spec/lti/claim/roles']
        realname = self._find_realname(launch_data)
        email = launch_data.get('email', '')
        platform_instance_id = '/'.join([launch_data['iss'], message_launch.get_client_id(), launch_data['https://purl.imsglobal.org/spec/lti/claim/deployment_id']])
        tool = launch_data.get('https://purl.imsglobal.org/spec/lti/claim/tool_platform', {})
        tool_name = tool.get('name', 'N/A')
        tool_desc = tool.get('description', 'N/A')
        tool_url = tool.get('url', 'N/A')
        context = launch_data['https://purl.imsglobal.org/spec/lti/claim/context']
        context_title = context.get('context_title', 'N/A')
        context_label = context.get('context_label', 'N/A')

        can_report_grades = message_launch.has_ags() and tool_conf.get_iss_config(iss=message_launch.get_iss(),
                                                                                  client_id=message_launch.get_client_id()).get('auth_token_url')

        session_id = hashlib.sha256(launch_id.encode('utf-8')).digest().hex()  # TODO(mp): Make this more secure
        self.user_manager.create_lti_session(session_id, user_id, roles, realname, email, courseid, taskid, platform_instance_id,
                                             launch_id if can_report_grades else None, tool_name, tool_desc, tool_url, context_title, context_label)

        loggedin = self.user_manager.attempt_lti_login()
        if loggedin:
            return redirect(self.app.get_path("lti", "task"))
        else:
            return redirect(self.app.get_path("lti", "login"))

    def GET(self, courseid, taskid):
        return self._handle_message_launch(courseid, taskid)

    def POST(self, courseid, taskid):
        return self._handle_message_launch(courseid, taskid)

    def _find_realname(self, launch_data):
        """ Returns the most appropriate name to identify the user """

        # First, try the full name
        if "name" in launch_data:
            return launch_data["name"]
        if "given" in launch_data and "family_name" in launch_data:
            return launch_data["given"] + launch_data["family_name"]

        # Then the email
        if "email" in launch_data:
            return launch_data["email"]

        # Then only part of the full name
        if "family_name" in launch_data:
            return launch_data["family_name"]
        if "given" in launch_data:
            return launch_data["given"]

        return launch_data["sub"]

class LTILoginPage(INGIniousPage):
    def is_lti_page(self):
        return True

    def GET(self):
        """
            Checks if user is authenticated and calls POST_AUTH or performs login and calls GET_AUTH.
            Otherwise, returns the login template.
        """
        data = self.user_manager.session_lti_info()
        if data is None:
            raise Forbidden(description=_("No LTI data available."))

        try:
            course = self.course_factory.get_course(data["task"][0])
            if data["platform_instance_id"] not in course.lti_platform_instances_ids():
                raise Exception()
        except:
            return self.template_helper.render("lti_bind.html", success=False,
                                               data=None, error=_("Invalid LTI data"))

        user_profile = self.database.users.find_one({"ltibindings." + data["task"][0] + "." + data["platform_instance_id"]: data["username"]})
        if user_profile:
            self.user_manager.connect_user(user_profile["username"], user_profile["realname"], user_profile["email"],
                                           user_profile["language"], user_profile.get("tos_accepted", False))

        if self.user_manager.session_logged_in():
            return redirect(self.app.get_path("lti", "task"))

        return self.template_helper.render("lti_login.html")

    def POST(self):
        """
        Checks if user is authenticated and calls POST_AUTH or performs login and calls GET_AUTH.
        Otherwise, returns the login template.
        """
        return self.GET()


# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LTI v1.3 """

from flask import jsonify, redirect, session, url_for, current_app
from werkzeug.exceptions import NotFound
from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch, FlaskRequest

from inginious.common import exceptions
from inginious.frontend.pages.utils import INGIniousPage
from inginious.frontend.pages.lti import LTIBindPage, LTILoginPage
from inginious.frontend.lti.v1_3 import MongoLTILaunchDataStorage, lti_tool, lti_keyset_hash
from inginious.frontend.courses import Course

from inginious.frontend.models import LTIData

class LTI13JWKSPage(INGIniousPage):
    endpoint = 'ltijwkspage'

    def GET(self, courseid, keyset_hash):
        try:
            lti_config = Course.get(courseid).lti_config() if courseid else {}
        except exceptions.CourseNotFoundException as ex:
            raise NotFound(description=_(str(ex)))

        global_config = current_app.config.get("LTI_CONFIG")

        # Merge with global config
        for iss, cfgs in global_config.items():
            lti_config.setdefault(iss, [])
            lti_config[iss] += cfgs

        for issuer in lti_config:
            for client_config in lti_config[issuer]:
                if keyset_hash == lti_keyset_hash(issuer, client_config['client_id']):
                    tool_conf = lti_tool(lti_config, {})
                    return jsonify(tool_conf.get_jwks(iss=issuer, client_id=client_config['client_id']))

        raise NotFound(description=_("Keyset not found"))


class LTI13OIDCLoginPage(INGIniousPage):
    endpoint = 'lti13oidcloginpage'

    def _handle_oidc_login_request(self, courseid):
        """ Initiates the LTI 1.3 OIDC login. """
        try:
            lti_config = Course.get(courseid).lti_config() if courseid else {}
        except exceptions.CourseNotFoundException as ex:
            raise NotFound(description=_(str(ex)))

        flask_request = FlaskRequest()
        target_link_uri = flask_request.get_param('target_link_uri')
        if not target_link_uri:
            raise Exception('Missing "target_link_uri" param')

        launch_data_storage = MongoLTILaunchDataStorage()
        oidc_login = FlaskOIDCLogin(flask_request, lti_tool(lti_config, current_app.config.get("LTI_CONFIG")), launch_data_storage=launch_data_storage)
        return oidc_login.enable_check_cookies().redirect(target_link_uri)

    def GET(self, courseid):
        return self._handle_oidc_login_request(courseid)

    def POST(self, courseid):
        return self._handle_oidc_login_request(courseid)


class LTI13LaunchPage(INGIniousPage):
    endpoint = 'lti1.3launchpage'

    def _handle_message_launch(self, courseid, taskid):
        """ Decrypt and process the LTI Launch message. """
        try:
            lti_config = Course.get(courseid).lti_config() if courseid else {}
        except exceptions.CourseNotFoundException as ex:
            raise NotFound(description=_(str(ex)))

        tool_conf = lti_tool(lti_config, current_app.config.get("LTI_CONFIG"))
        launch_data_storage = MongoLTILaunchDataStorage()
        flask_request = FlaskRequest()
        message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)

        launch_id = message_launch.get_launch_id()
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

        auth_token_url = tool_conf.get_iss_config(iss=message_launch.get_iss(), client_id=message_launch.get_client_id()).get('auth_token_url')
        can_report_grades = message_launch.has_ags() and auth_token_url

        # Fetch courseid and taskid
        custom_data = launch_data["https://purl.imsglobal.org/spec/lti/claim/custom"]
        courseid = courseid or custom_data.get('courseid')
        taskid = taskid or custom_data.get('taskid')

        if not session.is_lti:
            raise Exception("Not an LTI session")

        session.loggedin = False
        session.lti = LTIData(
            version = "1.3",
            email =email,
            username = user_id,
            realname = realname,
            roles = roles,
            task = (courseid, taskid),
            platform_instance_id = platform_instance_id,
            message_launch_id = launch_id if can_report_grades else None,
            context_title = context_title,
            context_label = context_label,
            tool_description = tool_desc,
            tool_name = tool_name,
            tool_url = tool_url,
        )

        return redirect(url_for("lti1.3loginpage"))

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


class LTI13BindPage(LTIBindPage):
    _field = "platform_instance_id"
    _ids_fct = lambda cls, course: course.lti_platform_instances_ids(current_app.config["LTI_CONFIG"])
    _lti_version = "1.3"


class LTI13LoginPage(LTILoginPage):
    _field = "platform_instance_id"
    _ids_fct = lambda cls, course: course.lti_platform_instances_ids(current_app.config["LTI_CONFIG"])
    _lti_version = "1.3"

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LTI v1.3 """

import secrets

from flask import jsonify, redirect, session, url_for, current_app, render_template, request
from werkzeug.exceptions import NotFound, Forbidden
from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch, FlaskRequest
from pylti1p3.deep_link_resource import DeepLinkResource

from inginious.common.exceptions import CourseNotFoundException
from inginious.frontend.pages.utils import INGIniousPage, INGIniousAuthPage
from inginious.frontend.pages.tasks import BaseTaskPage
from inginious.frontend.pages.lti import LTIBindPage, LTILoginPage
from inginious.frontend.lti.v1_3 import MongoLTILaunchDataStorage, lti_tool, lti_keyset_hash
from inginious.frontend.courses import Course

from inginious.frontend.models import LTIData

class LTI13TaskPage(INGIniousAuthPage):
    def is_lti_page(self):
        return True

    def check_access(self):
        data = session.lti
        if data is None:
            raise Forbidden(description=_("No LTI data available."))

        courseid, taskid = data['task']

        try:
            course = Course.get(courseid)
        except CourseNotFoundException as ex:
            raise NotFound(description=str(ex))

        if not course.lti_secrets().get(data["platform_instance_id"]) == data["course_secret"]:
            raise Forbidden(description=_("Invalid LTI secret"))

        return courseid, taskid

    def GET_AUTH(self):
        courseid, taskid= self.check_access()
        return BaseTaskPage(self).GET(courseid, taskid, True)

    def POST_AUTH(self):
        courseid, taskid = self.check_access()
        return BaseTaskPage(self).POST(courseid, taskid, True)

class LTI13JWKSPage(INGIniousPage):
    endpoint = 'ltijwkspage'

    def GET(self, courseid, keyset_hash):
        try:
            lti_config = Course.get(courseid).lti_config() if courseid else {}
        except CourseNotFoundException as ex:
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
        except CourseNotFoundException as ex:
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
        except CourseNotFoundException as ex:
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
        context = launch_data.get('https://purl.imsglobal.org/spec/lti/claim/context', {})
        context_title = context.get('context_title', 'N/A')
        context_label = context.get('context_label', 'N/A')

        if message_launch.is_resource_launch():
            # Fetch courseid and taskid
            custom_data = launch_data["https://purl.imsglobal.org/spec/lti/claim/custom"]
            courseid = courseid or custom_data.get('courseid')
            taskid = taskid or custom_data.get('taskid')
            secret = custom_data.get('secret', '')
            redir_url = url_for("lti1.3taskpage")
        elif message_launch.is_deep_link_launch():
            courseid = ""
            taskid = ""
            secret = ""
            redir_url = url_for("lti1.3deeplinkpage")

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
            course_secret=secret,
            message_launch_id = launch_id,
            context_title = context_title,
            context_label = context_label,
            tool_description = tool_desc,
            tool_name = tool_name,
            tool_url = tool_url,
            redir_url=redir_url
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
    _lti_version = "1.3"
    _mongo_field = lambda cls, data: data["platform_instance_id"].replace(".", "").replace("$", "")


class LTI13LoginPage(LTILoginPage):
    _lti_version = "1.3"
    _mongo_field = lambda cls, data: data["platform_instance_id"].replace(".", "").replace("$", "")


class LTI13DeepLinkPage(INGIniousPage):

    def GET(self):
        if not session.is_lti:
            raise Exception("Not an LTI session")

        lti_courses = {
            courseid: course for courseid, course in Course.get_all().items()
            if self.user_manager.has_admin_rights_on_course(course) and course.is_lti()
        }

        if (courseid := request.args.get("courseid")) is not None:
            if courseid not in lti_courses:
                raise Forbidden("Course not found")

            course = lti_courses[courseid]
            return {taskid: task.get_name(session.language) for taskid, task in course.get_tasks().items()}

        return render_template("lti/deeplink.html", courses=lti_courses)

    def POST(self):
        if not session.is_lti:
            raise Exception("Not an LTI session")

        courseid = request.form.get("courseid")
        taskid = request.form.get("taskid")

        try:
            course =  Course.get(courseid)
            task = course.get_task(taskid)
        except CourseNotFoundException as ex:
            raise NotFound(description=_(str(ex)))

        # Ftech LTI session info
        message_launch_id = session.lti["message_launch_id"]
        platform_instance_id = session.lti["platform_instance_id"]

        # Fetch or generate the LTI1.3 course secret
        lti_secrets = course.lti_secrets()
        if platform_instance_id not in lti_secrets:
            lti_secrets[platform_instance_id] = secrets.token_hex(16)
            course.set_descriptor_element("lti_secrets", lti_secrets)
            course.save()

        # Ftech launch message from database
        tool_config = lti_tool(course.lti_config(), current_app.config.get("LTI_CONFIG"))
        message_launch = FlaskMessageLaunch.from_cache(message_launch_id, request=None, tool_config=tool_config,
                                                       launch_data_storage=MongoLTILaunchDataStorage())

        # Generate deep link response
        deep_link = message_launch.get_deep_link()
        resource = DeepLinkResource()
        resource.set_url(url_for("lti1.3launchpage", _external=True).split("?")[0]) \
            .set_custom_params({'courseid': courseid, "taskid": taskid, "secret": lti_secrets[platform_instance_id]}) \
            .set_title(task.get_name(session.language))

        return deep_link.output_response_form([resource])

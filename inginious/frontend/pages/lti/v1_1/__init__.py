# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LTI v1.1 """

import flask
from flask import redirect
import datetime
from oauthlib.oauth1 import RequestValidator
from pymongo.errors import DuplicateKeyError
from werkzeug.exceptions import Forbidden, NotFound, MethodNotAllowed
from bson import ObjectId
from lti import ToolProvider

from inginious.common import exceptions
from inginious.frontend.pages.utils import INGIniousPage
from inginious.frontend.pages.lti import LTIBindPage, LTILoginPage
from inginious.frontend.courses import Course


class LTIFlaskToolProvider(ToolProvider):
    '''
    ToolProvider that works with Web.py requests
    '''

    @classmethod
    def from_flask_request(cls, secret=None):
        params = flask.request.form.copy()
        headers = flask.request.headers.environ.copy()

        headers = dict([(k, headers[k])
                        for k in headers if
                        k.upper().startswith('HTTP_') or
                        k.upper().startswith('CONTENT_')])

        url = flask.request.url
        return cls.from_unpacked_request(secret, params, url, headers)


class LTIValidator(RequestValidator):  # pylint: disable=abstract-method
    enforce_ssl = True
    client_key_length = (1, 30)
    nonce_length = (20, 64)
    realms = [""]

    @property
    def dummy_client(self):
        return ""  # Not used: validation works for all

    @property
    def dummy_request_token(self):
        return ""  # Not used: validation works for all

    @property
    def dummy_access_token(self):
        return ""  # Not used: validation works for all

    def __init__(self, collection, keys, nonce_validity=datetime.timedelta(minutes=10), debug=False):
        """
        :param collection: Pymongo collection. The collection must have a unique index on ("timestamp","nonce") and a TTL expiration on ("expiration")
        :param keys: dictionnary of allowed client keys, and their associated secret
        :param nonce_validity: timedelta representing the time during which a nonce is considered as valid
        :param debug:
        """
        super().__init__()

        self.enforce_ssl = debug
        self._collection = collection
        self._nonce_validity = nonce_validity
        self._keys = keys

    def validate_client_key(self, client_key, request):
        return client_key in self._keys

    def validate_timestamp_and_nonce(self, client_key, timestamp, nonce, request, request_token=None, access_token=None):
        try:
            date = datetime.datetime.utcfromtimestamp(int(timestamp))
            self._collection.insert_one({"timestamp": date,
                                         "nonce": nonce,
                                         "expiration": date + self._nonce_validity})
            return True
        except ValueError: # invalid timestamp
            return False
        except DuplicateKeyError:
            return False

    def get_client_secret(self, client_key, request):
        return self._keys[client_key] if client_key in self._keys else None


class LTI11LaunchPage(INGIniousPage):
    """
    Page called by the TC to start an LTI session on a given task
    """
    endpoint = 'ltilaunchpage'

    def GET(self, courseid, taskid):
        raise MethodNotAllowed()

    def POST(self, courseid, taskid):
        (session_id, loggedin) = self._parse_lti_data(courseid, taskid)
        if loggedin:
            return redirect(self.app.get_path("lti", "task"))
        else:
            return redirect(self.app.get_path("lti", "login"))

    def _parse_lti_data(self, courseid, taskid):
        """ Verify and parse the data for the LTI basic launch """
        post_input = flask.request.form
        self.logger.debug('_parse_lti_data:' + str(post_input))

        try:
            course = Course.get(courseid)
        except exceptions.CourseNotFoundException as ex:
            raise NotFound(description=_(str(ex)))

        try:
            test = LTIFlaskToolProvider.from_flask_request()
            validator = LTIValidator(self.database.nonce, course.lti_keys())
            verified = test.is_valid_request(validator)
        except Exception as ex:
            self.logger.error("Error while parsing the LTI request : {}".format(str(post_input)))
            self.logger.error("The exception caught was :  {}".format(str(ex)))
            raise Forbidden(description=_("Error while parsing the LTI request"))

        if verified:
            self.logger.debug('parse_lit_data for %s', str(post_input))
            user_id = post_input["user_id"]
            roles = post_input.get("roles", "Student").split(",")
            realname = self._find_realname(post_input)
            email = post_input.get("lis_person_contact_email_primary", "")
            lis_outcome_service_url = post_input.get("lis_outcome_service_url", None)
            outcome_result_id = post_input.get("lis_result_sourcedid", None)
            consumer_key = post_input["oauth_consumer_key"]

            if course.lti_send_back_grade():
                if lis_outcome_service_url is None or outcome_result_id is None:
                    self.logger.info('Error: lis_outcome_service_url is None but lti_send_back_grade is True')
                    raise Forbidden(description=_("In order to send grade back to the TC, INGInious needs the parameters lis_outcome_service_url and "
                                        "lis_outcome_result_id in the LTI basic-launch-request. Please contact your administrator."))
            else:
                lis_outcome_service_url = None
                outcome_result_id = None

            tool_name = post_input.get('tool_consumer_instance_name', 'N/A')
            tool_desc = post_input.get('tool_consumer_instance_description', 'N/A')
            tool_url = post_input.get('tool_consumer_instance_url', 'N/A')
            context_title = post_input.get('context_title', 'N/A')
            context_label = post_input.get('context_label', 'N/A')

            session_id = str(ObjectId())
            session_dict = {
                "version": "1.1",
                "email": email,
                "username": user_id,
                "realname": realname,
                "roles": roles,
                "task": (courseid, taskid),
                "outcome_service_url": lis_outcome_service_url,
                "outcome_result_id": outcome_result_id,
                "consumer_key": consumer_key,
                "context_title": context_title,
                "context_label": context_label,
                "tool_description": tool_desc,
                "tool_name": tool_name,
                "tool_url": tool_url
            }

            self.user_manager.create_lti_session(session_id, session_dict)
            loggedin = self.user_manager.attempt_lti_login()

            return session_id, loggedin
        else:
            self.logger.info("Couldn't validate LTI request")
            raise Forbidden(description=_("Couldn't validate LTI request"))

    def _find_realname(self, post_input):
        """ Returns the most appropriate name to identify the user """

        # First, try the full name
        if "lis_person_name_full" in post_input:
            return post_input["lis_person_name_full"]
        if "lis_person_name_given" in post_input and "lis_person_name_family" in post_input:
            return post_input["lis_person_name_given"] + post_input["lis_person_name_family"]

        # Then the email
        if "lis_person_contact_email_primary" in post_input:
            return post_input["lis_person_contact_email_primary"]

        # Then only part of the full name
        if "lis_person_name_family" in post_input:
            return post_input["lis_person_name_family"]
        if "lis_person_name_given" in post_input:
            return post_input["lis_person_name_given"]

        return post_input["user_id"]


class LTI11BindPage(LTIBindPage):
    pass


class LTI11LoginPage(LTILoginPage):
    pass

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Helper classes and methods for the REST API """

import json
import flask
from flask import Response

import inginious.common.custom_yaml as yaml
from inginious.frontend.pages.utils import INGIniousPage
from inginious.frontend.user_manager import user_manager


class APIPage(INGIniousPage):
    """ Generic handler for all API pages """

    def GET(self, *args, **kwargs):
        """ GET request """
        return self._handle_api(self.API_GET, args, kwargs)

    def PUT(self, *args, **kwargs):
        """ PUT request """
        return self._handle_api(self.API_PUT, args, kwargs)

    def POST(self, *args, **kwargs):
        """ POST request """
        return self._handle_api(self.API_POST, args, kwargs)

    def DELETE(self, *args, **kwargs):
        """ DELETE request """
        return self._handle_api(self.API_DELETE, args, kwargs)

    def PATCH(self, *args, **kwargs):
        """ PATCH request """
        return self._handle_api(self.API_PATCH, args, kwargs)

    def HEAD(self, *args, **kwargs):
        """ HEAD request """
        return self._handle_api(self.API_HEAD, args, kwargs)

    def OPTIONS(self, *args, **kwargs):
        """ OPTIONS request """
        return self._handle_api(self.API_OPTIONS, args, kwargs)

    def _handle_api(self, handler, handler_args, handler_kwargs):
        """ Handle call to subclasses and convert the output to an appropriate value """
        try:
            status_code, return_value = handler(*handler_args, **handler_kwargs)
        except APIError as error:
            return error.send()

        return _api_convert_output(status_code, return_value)

    def _guess_available_methods(self):
        """ Guess the method implemented by the subclass"""
        available_methods = []
        for m in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
            self_method = getattr(type(self), "API_{}".format(m))
            super_method = getattr(APIPage, "API_{}".format(m))
            if self_method != super_method:
                available_methods.append(m)
        return available_methods

    def invalid_method(self):
        """ Returns 405 Invalid Method to the client """
        raise APIInvalidMethod(self._guess_available_methods())

    def API_GET(self, *args, **kwargs):  # pylint: disable=unused-argument
        """ API GET request. Should be overridden by subclasses """
        self.invalid_method()

    def API_PUT(self, *args, **kwargs):  # pylint: disable=unused-argument
        """ API PUT request. Should be overridden by subclasses """
        self.invalid_method()

    def API_POST(self, *args, **kwargs):  # pylint: disable=unused-argument
        """ API POST request. Should be overridden by subclasses """
        self.invalid_method()

    def API_DELETE(self, *args, **kwargs):  # pylint: disable=unused-argument
        """ API DELETE request. Should be overridden by subclasses """
        self.invalid_method()

    def API_PATCH(self, *args, **kwargs):  # pylint: disable=unused-argument
        """ API PATCH request. Should be overridden by subclasses """
        self.invalid_method()

    def API_HEAD(self, *args, **kwargs):  # pylint: disable=unused-argument
        """ API HEAD request. Should be overridden by subclasses """
        self.invalid_method()

    def API_OPTIONS(self, *args, **kwargs):  # pylint: disable=unused-argument
        """ API OPTIONS request. Should be overridden by subclasses """
        self.invalid_method()


class APIAuthenticatedPage(APIPage):
    """
        A wrapper for pages that needs authentication. Automatically checks that the client is authenticated and returns "403 Forbidden" if it's
        not the case.
    """

    def _handle_api(self, handler, handler_args, handler_kwargs):
        return APIPage._handle_api(self, (lambda *args, **kwargs: self._verify_authentication(handler, args, kwargs)), handler_args, handler_kwargs)

    def _verify_authentication(self, handler, args, kwargs):
        """ Verify that the user is authenticated """
        if not user_manager.session_logged_in():
            raise APIForbidden()
        return handler(*args, **kwargs)


class APIError(Exception):
    """ Standard API Error """

    def __init__(self, status_code, return_value):
        super(APIError, self).__init__()
        self.status_code = status_code
        self.return_value = return_value

    def send(self, response=None):
        """ Send the API Exception to the client """
        return _api_convert_output(self.status_code, self.return_value, response)


class APIInvalidMethod(APIError):
    """ Invalid method error """

    def __init__(self, methods):
        APIError.__init__(self, 405, {"error": "This endpoint has no such method"})
        self.methods = methods

    def send(self):
        response = Response()
        response.headers['Allow'] = ",".join(self.methods)
        return APIError.send(self, response)


class APIInvalidArguments(APIError):
    """ Invalid arguments error """

    def __init__(self):
        APIError.__init__(self, 400, {"error": "Invalid arguments for this method"})


class APIForbidden(APIError):
    """ Forbidden error """

    def __init__(self, message="You are not authenticated"):
        APIError.__init__(self, 403, {"error": message})


class APINotFound(APIError):
    """ Not found error """

    def __init__(self, message="Not found"):
        APIError.__init__(self, 404, {"error": message})


def _api_convert_output(status_code, return_value, response=None):
    if not response:
        response = Response()
        response.status_code = status_code
    """ Convert the output to what the client asks """
    content_type = flask.request.environ.get('CONTENT_TYPE', 'text/json')

    if "text/json" in content_type:
        response.content_type = 'text/json; charset=utf-8'
        response.response = [json.dumps(return_value)]
        return response
    if "text/html" in content_type:
        response.content_type = 'text/html; charset=utf-8'
        dump = yaml.dump(return_value)
        response.response = ["<pre>" + dump + "</pre>"]
        return response
    if "text/yaml" in content_type or \
                    "text/x-yaml" in content_type or \
                    "application/yaml" in content_type or \
                    "application/x-yaml" in content_type:
        response.content_type = 'text/yaml; charset=utf-8'
        response.response = [yaml.dump(return_value)]
        return response
    response.content_type = 'text/json; charset=utf-8'
    response.response = [json.dumps(return_value)]
    return response

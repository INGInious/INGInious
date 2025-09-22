# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Authentication """

import flask

from inginious.frontend.pages.api._api_page import APIPage, APIInvalidArguments
from inginious.frontend.user_manager import user_manager

class APIAuthentication(APIPage):
    """
        Endpoint /api/v0/authentication
    """

    def API_GET(self):  # pylint: disable=arguments-differ
        """
            Returns {"authenticated": false} or {"authenticated": true, "username": "your_username"} (always 200 OK)
        """
        if user_manager.session_logged_in():
            return 200, {"authenticated": True, "username": user_manager.session_username()}
        else:
            return 200, {"authenticated": False}

    def API_POST(self):  # pylint: disable=arguments-differ
        """
            Authenticates the remote client. Takes as input:

            login
                the INGInious account login

            password
                the associated password

            Response: a dict in the form {"status": "success"} (200 OK) or {"status": "error"} (403 Forbidden)
        """

        user_input = flask.request.form
        if "login" not in user_input or "password" not in user_input:
            raise APIInvalidArguments()

        try:
            if user_manager.auth_user(user_input["login"].strip(), user_input["password"]) is not None:
                    return 200, {"status": "success", "username": user_manager.session_username()}
        except:
            pass
        return 403, {"status": "error"}

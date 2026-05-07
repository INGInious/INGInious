# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

"""Auth methods"""

from inginious.frontend.pages.api._api_page import APIPage


class APIAuthMethods(APIPage):
    """
    Endpoint /api/v0/auth_methods
    """

    def API_GET(self):
        """
        Returns all the auth methods available. (200 OK)

        Response: list of auth methods. The values in the last are auth methods, represented by:

        id
            id of the auth method

        name
            the name of the authentication method, typically displayed by the webapp

        input
            a list containing the inputs to this method.
            Each input is represented as a dictionary containing three fields:

            id
                the id of the input, to be returned as id in the POST request of /api/v0/authentication

            name
                the placeholder for the input

            type
                text or password
        """
        # this is an old API, not used anymore. This ensures retrocompatibility.
        return 200, [
            {
                "id": 0,
                "name": "INGInious account",
                "input": [
                    {"id": "login", "name": "Login", "type": "text"},
                    {"id": "password", "name": "Password", "type": "password"},
                ],
            }
        ]

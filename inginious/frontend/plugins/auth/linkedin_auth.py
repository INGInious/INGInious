# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" linkedin auth plugin """

import json
import os
import flask

from requests_oauthlib import OAuth2Session

from inginious.frontend.user_manager import AuthMethod

authorization_base_url = 'https://www.linkedin.com/oauth/v2/authorization'
token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
scope = ["r_liteprofile", "r_emailaddress"]


class LinkedInAuthMethod(AuthMethod):
    """
    LinkedIn auth method
    """
    def get_auth_link(self, auth_storage):
        linkedin = OAuth2Session(self._client_id, scope=scope, redirect_uri=flask.request.url_root + self._callback_page)
        authorization_url, state = linkedin.authorization_url(authorization_base_url)
        auth_storage["oauth_state"] = state
        return authorization_url

    def callback(self, auth_storage):
        linkedin = OAuth2Session(self._client_id, state=auth_storage["oauth_state"], redirect_uri=flask.request.url_root + self._callback_page)
        try:
            linkedin.fetch_token(token_url, include_client_id=True, client_secret=self._client_secret,
                                 authorization_response=flask.request.url)
            r = linkedin.get('https://api.linkedin.com/v2/me?projection=(id,localizedFirstName,localizedLastName)')
            profile = json.loads(r.content.decode('utf-8'))
            r = linkedin.get('https://api.linkedin.com/v2/clientAwareMemberHandles?q=members&projection=(elements*(primary,type,handle~))')
            result = json.loads(r.content.decode('utf-8'))
            for contact in result["elements"]:
                if contact["type"] == "EMAIL":
                    profile["emailAddress"] = contact["handle~"]["emailAddress"]
                    break
            return str(profile["id"]), profile["localizedFirstName"] + " " + profile["localizedLastName"], profile["emailAddress"], {}
        except Exception as e:
            return None

    def get_id(self):
        return self._id

    def __init__(self, id, name, client_id, client_secret):
        self._id = id
        self._name = name
        self._client_id = client_id
        self._client_secret = client_secret
        self._callback_page = 'auth/callback/' + self._id

    def get_name(self):
        return self._name

    def get_imlink(self):
        return '<i class="fa fa-linkedin-square" style="font-size:50px; color:#008CC9;"></i>'


def init(plugin_manager, fs_provider, client, conf):

    if conf.get("debug", False):
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    client_id = conf.get("client_id", "")
    client_secret = conf.get("client_secret", "")

    plugin_manager.register_auth_method(LinkedInAuthMethod(conf.get("id"), conf.get('name', 'LinkedIn'), client_id, client_secret))

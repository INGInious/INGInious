# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Facebook auth plugin """

import json
import os
import flask

from requests_oauthlib import OAuth2Session
from requests_oauthlib.compliance_fixes import facebook_compliance_fix

from inginious.frontend.user_manager import AuthMethod

authorization_base_url = 'https://www.facebook.com/dialog/oauth'
token_url = 'https://graph.facebook.com/oauth/access_token'
scope = ["public_profile", "email"]


class FacebookAuthMethod(AuthMethod):
    """
    Facebook auth method
    """
    def get_auth_link(self, auth_storage):
        facebook = OAuth2Session(self._client_id, scope=scope, redirect_uri=flask.request.url_root + self._callback_page)
        facebook = facebook_compliance_fix(facebook)
        authorization_url, state = facebook.authorization_url(authorization_base_url)
        auth_storage["oauth_state"] = state
        return authorization_url

    def callback(self, auth_storage):
        facebook = OAuth2Session(self._client_id, state=auth_storage["oauth_state"], redirect_uri=flask.request.url_root + self._callback_page)
        try:
            facebook.fetch_token(token_url, client_secret=self._client_secret,
                                 authorization_response=flask.request.url)
            r = facebook.get('https://graph.facebook.com/me?fields=id,name,email')
            profile = json.loads(r.content.decode('utf-8'))
            auth_storage["oauth_state"] = facebook.state
            return str(profile["id"]), profile["name"], profile["email"], {}
        except:
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
        return '<i class="fa fa-facebook-square" style="font-size:50px; color:#4267b2;"></i>'


def init(plugin_manager, conf):

    if conf.get("debug", False):
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    client_id = conf.get("client_id", "")
    client_secret = conf.get("client_secret", "")

    plugin_manager.register_auth_method(FacebookAuthMethod(conf.get("id"), conf.get('name', 'Facebook'), client_id, client_secret))

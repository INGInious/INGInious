# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Google auth plugin """

import json
import os

import flask
from flask import redirect
from requests_oauthlib import OAuth2Session

from inginious.frontend.user_manager import AuthMethod

authorization_base_url = 'https://accounts.google.com/o/oauth2/v2/auth'
token_url = 'https://www.googleapis.com/oauth2/v4/token'
scope = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

class GoogleAuthMethod(AuthMethod):
    """
    Google auth method
    """

    def get_auth_link(self, auth_storage):
        google = OAuth2Session(self._client_id, scope=scope, redirect_uri=flask.request.url_root + self._callback_page)
        authorization_url, state = google.authorization_url(authorization_base_url, hd=self._domain)
        auth_storage["oauth_state"] = state
        return authorization_url

    def callback(self, auth_storage):
        google = OAuth2Session(self._client_id, state=auth_storage["oauth_state"],
            redirect_uri=flask.request.url_root + self._callback_page, scope=scope)

        try:
            google.fetch_token(token_url, client_secret=self._client_secret,
                authorization_response=flask.request.url)

            response = google.get('https://www.googleapis.com/oauth2/v3/userinfo')
            profile = json.loads(response.content.decode('utf-8'))
            return str(profile["sub"]), profile["name"], profile["email"], {}
        except Exception as e:
            return None

    def get_id(self):
        return self._id

    def __init__(self, id, name, client_id, client_secret, domain):
        self._id = id
        self._name = name
        self._client_id = client_id
        self._client_secret = client_secret
        self._callback_page = 'auth/callback/' + self._id
        self._domain = domain

    def get_name(self):
        return self._name

    def get_imlink(self):
        return '<img src="/static/icons/google-icon.svg" ' \
               'style="-moz-user-select: none; -webkit-user-select: none;' \
               'user-select: none; width: 50px; height:50px;" >'


def init(plugin_manager, fs_provider, client, conf):
    if conf.get("debug", False):
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    client_id = conf.get("client_id", "")
    client_secret = conf.get("client_secret", "")
    domain = conf.get("domain", "")

    plugin_manager.register_auth_method(GoogleAuthMethod(conf.get("id"),
        conf.get('name', 'Google'), client_id, client_secret, domain))

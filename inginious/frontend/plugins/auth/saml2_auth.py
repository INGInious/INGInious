# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" SAML SSO plugin """

import copy
import html
import json
import logging
import flask

from urllib.parse import urlparse
from flask import Response
from werkzeug.exceptions import abort, InternalServerError
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.utils import OneLogin_Saml2_Utils

from inginious.frontend.pages.utils import INGIniousPage
from inginious.frontend.user_manager import AuthMethod, user_manager

settings = None


class SAMLAuthMethod(AuthMethod):
    """
    SAML SSO auth method
    """

    def __init__(self, id, name, imlink, settings):
        self._id = id
        self._name = name
        self._imlink = imlink
        self._settings = settings

    def get_id(self):
        return self._id

    def get_name(self):
        return self._name

    def get_imlink(self):
        if self._imlink:
            return '<img src="' + self._imlink + \
                   '" style="-moz-user-select: none; -webkit-user-select: none; ' \
                   'user-select: none; max-height:50px;" />'
        else:
            return '<i class="fa fa-id-card" style="font-size:50px; color:#000000;"></i>'

    def get_auth_link(self, auth_storage):
        auth = OneLogin_Saml2_Auth(prepare_request(self._settings), self._settings)
        return auth.login(json.dumps(auth_storage))

    def callback(self, auth_storage):
        req = prepare_request(self._settings)
        input_data = flask.request.form

        if "alreadyRedirected" not in input_data:
            raise abort(Response(status=200, response="""
                <!DOCTYPE html>
                <html>
                    <head>
                        <meta charset="utf-8" />
                    </head>
                    <body onload="document.forms[0].submit()">
                        <noscript>
                            <p>
                                <strong>Note:</strong> Since your browser does not support JavaScript,
                                you must press the Continue button once to proceed.
                            </p>
                        </noscript>
                        <form method="post">
                            <div>
                                <input type="hidden" name="RelayState" value="{RelayState}"/>
                                <input type="hidden" name="SAMLResponse" value="{SAMLResponse}"/>
                                <input type="hidden" name="alreadyRedirected" value="yes"/>
                            </div>
                            <noscript>
                                <div>
                                    <input type="submit" value="Continue"/>
                                </div>
                            </noscript>
                        </form>
                    </body>
                </html>
            """.format(RelayState=html.escape(input_data["RelayState"]), SAMLResponse=html.escape(input_data["SAMLResponse"]))))

        auth = OneLogin_Saml2_Auth(req, self._settings)
        auth.process_response()
        errors = auth.get_errors()

        # Try and check if IdP is using several signature certificates
        # This is a limitation of python3-saml
        for cert in self._settings["idp"].get("additionalX509certs", []):
            if auth.get_last_error_reason() == "Signature validation failed. SAML Response rejected":
                # Change used IdP certificate
                logging.getLogger('inginious.webapp.plugin.auth.saml').debug("Trying another certificate...")
                new_settings = copy.deepcopy(self._settings)
                new_settings["idp"]["x509cert"] = cert
                # Retry processing response
                auth = OneLogin_Saml2_Auth(req, new_settings)
                auth.process_response()
                errors = auth.get_errors()

        if len(errors) == 0 and "attributes" in self._settings:
            attrs = auth.get_attributes()
            username = attrs[self._settings["attributes"]["uid"]][0]
            realname = attrs[self._settings["attributes"]["cn"]][0]
            email = attrs[self._settings["attributes"]["email"]][0]

            additional = {}
            for field, urn in self._settings.get("additional", {}).items():
                additional[field] = attrs[urn][0] if urn in attrs else ""

            # Redirect to desired url
            self_url = OneLogin_Saml2_Utils.get_self_url(req)
            if 'RelayState' in input_data and self_url != input_data['RelayState']:
                auth_storage.update(json.loads(input_data['RelayState']))
                # Initialize session in user manager and update cache
                return str(username), realname, email, additional
        else:
            logging.getLogger('inginious.webapp.plugin.auth.saml').error("Errors while processing response : " +
                                                                         ", ".join(errors))
            return None

    def get_settings(self):
        return self._settings


def prepare_request(settings):
    """ Prepare SAML request """

    # Set the ACS url and binding method
    settings["sp"]["assertionConsumerService"] = {
        "url": flask.request.url_root + "auth/callback/" + settings["id"],
        "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
    }

    # If server is behind proxys or balancers use the HTTP_X_FORWARDED fields
    url_data = urlparse(flask.request.url)
    return {
        'https': 'on' if flask.request.scheme == 'https' else 'off',
        'http_host': flask.request.host,
        'server_port': url_data.port,
        'script_name': flask.request.path,
        'get_data': flask.request.args.copy(),
        'post_data': flask.request.form.copy(),
        # Uncomment if using ADFS as IdP, https://github.com/onelogin/python-saml/pull/144
        # 'lowercase_urlencoding': True,
        'query_string': flask.request.query_string
    }


class MetadataPage(INGIniousPage):
    def GET(self, id):
        settings = user_manager.get_auth_method(id).get_settings()
        auth = OneLogin_Saml2_Auth(prepare_request(settings), settings)
        metadata = auth.get_settings().get_sp_metadata()
        errors = auth.get_settings().validate_metadata(metadata)

        if len(errors) == 0:
            return Response(response=metadata, status=200, mimetype="text/xml")
        else:
            raise InternalServerError(description=', '.join(errors))


def init(plugin_manager, course_factory, client, conf):
    plugin_manager.add_page('/auth/<id>/metadata', MetadataPage.as_view('metadatapage_' + conf.get("id")))
    plugin_manager.register_auth_method(SAMLAuthMethod(conf.get("id"), conf.get('name', 'SAML'), conf.get('imlink', ''), conf))


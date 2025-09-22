# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LDAP plugin """
import os
import logging
import ldap3

from flask import redirect, render_template, request
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from inginious.frontend.pages.social import AuthenticationPage
from inginious.frontend.user_manager import AuthMethod, user_manager

PATH_TO_PLUGIN = os.path.abspath(os.path.dirname(__file__))

logger = logging.getLogger('inginious.webapp.plugin.auth.ldap')

class LdapAuthMethod(AuthMethod):
    """
    LDAP auth method
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
            return '<i class="fa fa-address-book" style="font-size:50px; color:#000000;"></i>'

    def get_auth_link(self, auth_storage):
        return "/auth/page/" + self._id

    def callback(self, auth_storage):
        return None

    def get_settings(self):
        return self._settings


class LDAPAuthenticationPage(AuthenticationPage):
    def GET(self, id):
        settings = user_manager.get_auth_method(id).get_settings()
        return render_template("ldap_auth/custom_auth_form.html", settings=settings, error=False)

    def POST(self, id):
        # Get configuration
        settings = user_manager.get_auth_method(id).get_settings()
        login_data = request.form
        login = login_data["login"].strip().lower()
        password = login_data["password"]

        # do not send empty password to the LDAP
        if password.rstrip() == "":
            return render_template("ldap_auth/custom_auth_form.html", settings=settings, error= _("Empty password"))

        try:
            # Connect to the ldap
            logger.debug('Connecting to ' + settings['host'] + ", port " + str(settings['port']))
            if "bind_dn" in settings:
                bind_dn = {"user": settings["bind_dn"].format(login), "password": password}
            else:
                bind_dn = {}

            auto_bind = settings.get("auto_bind", True)
            conn = ldap3.Connection(
                ldap3.Server(settings['host'], port=settings['port'], use_ssl=settings["encryption"] == 'ssl',
                             get_info=ldap3.ALL), auto_bind=auto_bind, **bind_dn)
            logger.debug('Connected to ' + settings['host'] + ", port " + str(settings['port']))
        except LDAPException as e:
            logger.exception("Can't initialze connection to " + settings['host'] + ': ' + str(e))
            return render_template("ldap_auth/custom_auth_form.html", settings=settings, error=_("Cannot contact host"))

        attr_cn = settings.get("cn", "cn")
        attr_mail = settings.get("mail", "mail")
        try:
            ldap_request = settings["request"].format(escape_filter_chars(login))
            conn.search(settings["base_dn"], ldap_request, attributes=[attr_cn, attr_mail])
            user_data = conn.response[0]
        except (LDAPException, IndexError) as ex:
            logger.exception("Can't get user data : " + str(ex))
            conn.unbind()
            return render_template("ldap_auth/custom_auth_form.html", settings=settings, error=_("Unknown user"))

        if conn.rebind(user_data['dn'], password=password):
            try:
                email = user_data['attributes'][attr_mail]
                if isinstance(email, list):
                    email = email[0]
                username = login
                realname = user_data["attributes"][attr_cn]
                if isinstance(realname, list):
                    realname = realname[0]

            except KeyError as e:
                logger.exception("Can't get field " + str(e) + " from your LDAP server")
                return render_template("ldap_auth/custom_auth_form.html", settings=settings,
                                                   error=_("Can't get field {} from your LDAP server").format(str(e)))
            except LDAPException as e:
                logger.exception("Can't get some user fields")
                return render_template("ldap_auth/custom_auth_form.html", settings=settings, error=_("Can't get some user fields"))
            finally:
                conn.unbind()

            if not user_manager.bind_user(id, (username, realname, email, {})):
                return redirect("/signin?binderror")
            
            auth_storage = user_manager.session_auth_storage().setdefault(id, {})
            return redirect(auth_storage.get("redir_url", "/"))
        else:
            logger.debug('Auth Failed')
            conn.unbind()
            return render_template("ldap_auth/custom_auth_form.html", settings=settings, error=_("Incorrect password"))


def init(plugin_manager, _, _2, conf):
    """
        Allow to connect through a LDAP service

        Available configuration:
        ::

            plugins:
                - plugin_module": "inginious.frontend.plugins.auth.ldap_auth",

                  host: "ldap.test.be",
                  port: 0,
                  encryption: "ssl",
                  base_dn: "o=test,c=be",
                  request: "(uid={})",
                  name: "LDAP Login"

        *host*
            The host of the ldap server
        *encryption*
            Encryption method used to connect to the LDAP server
            Can be either "none", "ssl" or "tls"
        *request*
            Request made to the server in order to find the dn of the user. The characters "{}" will be replaced by the login name.

    """

    encryption = conf.get("encryption", "none")
    if encryption not in ["none", "ssl", "tls"]:
        raise Exception("Unknown encryption method {}".format(encryption))
    if encryption == "none":
        conf["encryption"] = None

    if conf.get("port", 0) == 0:
        conf["port"] = None

    the_method = LdapAuthMethod(conf.get("id"), conf.get('name', 'LDAP'), conf.get("imlink", ""), conf)
    plugin_manager.add_page('/auth/page/<id>', LDAPAuthenticationPage.as_view('ldapauthenticationpage'))
    plugin_manager.register_auth_method(the_method)
    plugin_manager.add_template_prefix("ldap_auth", PATH_TO_PLUGIN)

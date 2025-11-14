# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Some utils for all the pages """
import logging
import os
from typing import List, Dict

import flask
from gridfs import GridFS
from flask import redirect, render_template
from flask.views import MethodView
from werkzeug.exceptions import NotFound, NotAcceptable, MethodNotAllowed

from inginious.common.filesystems import FileSystemProvider
from inginious.client.client import Client
from inginious.common import custom_yaml
from inginious.frontend.environment_types import get_all_env_types
from inginious.frontend.environment_types.env_type import FrontendEnvType
from inginious.frontend.submission_manager import WebAppSubmissionManager
from inginious.frontend.user_manager import UserManager
from inginious.frontend.parsable_text import ParsableText
from inginious.frontend.i18n import available_languages
from pymongo.database import Database


class INGIniousPage(MethodView):
    """
    A base for all the pages of the INGInious webapp.
    Contains references to the PluginManager, the CourseFactory, and the SubmissionManager
    """

    @property
    def is_lti_page(self):
        """ True if the current page allows LTI sessions. False else. """
        return False

    @property
    def app(self):
        """ Returns the web application singleton """
        return flask.current_app

    def _pre_check(self):
        """ Checks for language. """
        if "lang" in flask.request.args and flask.request.args["lang"] in available_languages:
            self.user_manager.set_session_language(flask.request.args["lang"])
        elif not self.user_manager.session_language(default=None):
            best_lang = flask.request.accept_languages.best_match(available_languages,default="en")
            self.user_manager.set_session_language(best_lang)

    def GET(self, *args, **kwargs):
        """ Handles GET requests. It should be redefined by subclasses. """
        raise MethodNotAllowed()

    def POST(self, *args, **kwargs):
        """ Handles POST requests. It should be redefined by subclasses. """
        raise MethodNotAllowed()

    def get(self, *args, **kwargs):
        """ Interfaces INGInious pages with Flask views for GET requests. """
        self._pre_check()
        return self.GET(*args, **kwargs)

    def post(self, *args, **kwargs):
        """ Interfaces INGInious pages with Flask views for POST requests. """
        self._pre_check()
        return self.POST(*args, **kwargs)

    @property
    def submission_manager(self) -> WebAppSubmissionManager:
        """ Returns the submission manager singleton"""
        return self.app.submission_manager

    @property
    def user_manager(self) -> UserManager:
        """ Returns the user manager singleton """
        return self.app.user_manager

    @property
    def database(self) -> Database:
        """ Returns the database singleton """
        return self.app.database

    @property
    def gridfs(self) -> GridFS:
        """ Returns the GridFS singleton """
        return self.app.gridfs

    @property
    def client(self) -> Client:
        """ Returns the INGInious client """
        return self.app.client

    @property
    def default_allowed_file_extensions(self) -> List[str]:  # pylint: disable=invalid-sequence-index
        """ List of allowed file extensions """
        return self.app.default_allowed_file_extensions

    @property
    def default_max_file_size(self) -> int:
        """ Default maximum file size for upload """
        return self.app.default_max_file_size

    @property
    def environments(self) -> Dict[str, List[str]]:  # pylint: disable=invalid-sequence-index
        """ Available environments """
        return self.app.submission_manager.get_available_environments()

    @property
    def environment_types(self) -> Dict[str, FrontendEnvType]:
        """ Available environment types """
        return get_all_env_types()

    @property
    def webterm_link(self) -> str:
        """ Returns the link to the web terminal """
        return self.app.webterm_link

    @property
    def webdav_host(self) -> str:
        """ True if webdav is available """
        return self.app.webdav_host

    @property
    def logger(self) -> logging.Logger:
        """ Logger """
        return logging.getLogger('inginious.webapp.pages')


class INGIniousAuthPage(INGIniousPage):
    """
    Augmented version of INGIniousPage that checks if user is authenticated.
    """

    def POST_AUTH(self, *args, **kwargs):  # pylint: disable=unused-argument
        raise NotAcceptable()

    def GET_AUTH(self, *args, **kwargs):  # pylint: disable=unused-argument
        raise NotAcceptable()

    def GET(self, *args, **kwargs):
        """
        Checks if user is authenticated and calls GET_AUTH or performs logout.
        Otherwise, returns the login template.
        """
        if self.user_manager.session_logged_in():
            if (not self.user_manager.session_username() or (self.app.terms_page is not None and
                                                             self.app.privacy_page is not None and
                                                             not self.user_manager.session_tos_signed())) \
                    and not self.__class__.__name__ == "ProfilePage":
                return redirect("/preferences/profile")

            if not self.is_lti_page and self.user_manager.session_lti_info() is not None:  # lti session
                self.user_manager.disconnect_user()
                return render_template("auth.html", auth_methods=self.user_manager.get_auth_methods())

            return self.GET_AUTH(*args, **kwargs)
        elif self.preview_allowed(*args, **kwargs):
            return self.GET_AUTH(*args, **kwargs)
        else:
            error = ''
            if "binderror" in flask.request.args:
                error = _("An account using this email already exists and is not bound with this service. "
                          "For security reasons, please log in via another method and bind your account in your profile.")
            if "callbackerror" in flask.request.args:
                error = _("Couldn't fetch the required information from the service. Please check the provided "
                          "permissions (name, email) and contact your INGInious administrator if the error persists.")
            return render_template("auth.html", auth_methods=self.user_manager.get_auth_methods(),
                                               error=error)

    def POST(self, *args, **kwargs):
        """
        Checks if user is authenticated and calls POST_AUTH or performs login and calls GET_AUTH.
        Otherwise, returns the login template.
        """
        if self.user_manager.session_logged_in():
            if not self.user_manager.session_username() and not self.__class__.__name__ == "ProfilePage":
                return redirect("/preferences/profile")

            if not self.is_lti_page and self.user_manager.session_lti_info() is not None:  # lti session
                self.user_manager.disconnect_user()
                return render_template("auth.html", auth_methods=self.user_manager.get_auth_methods())

            return self.POST_AUTH(*args, **kwargs)
        else:
            user_input = flask.request.form
            if "login" in user_input and "password" in user_input:
                if self.user_manager.auth_user(user_input["login"].strip(), user_input["password"]) is not None:
                    return self.GET_AUTH(*args, **kwargs)
                else:
                    return render_template("auth.html", auth_methods=self.user_manager.get_auth_methods(),
                                                       error=_("Invalid login/password"))
            elif self.preview_allowed(*args, **kwargs):
                return self.POST_AUTH(*args, **kwargs)
            else:
                return render_template("auth.html", auth_methods=self.user_manager.get_auth_methods())

    def preview_allowed(self, *args, **kwargs):
        """
            If this function returns True, the auth check is disabled.
            Override this function with a custom check if needed.
        """
        return False


class INGIniousAdministratorPage(INGIniousAuthPage):
    """
       Augmented version of INGIniousAuthPage that checks if user is administrator (superadmin).
    """

    def GET(self, *args, **kwargs):
        """
        Checks if user is superadmin and calls GET_AUTH or performs logout.
        Otherwise, returns the login template.
        """
        username = self.user_manager.session_username()
        if self.user_manager.session_logged_in():
            if not self.user_manager.user_is_superadmin(username):
                return render_template("forbidden.html",
                                                   message=_("Forbidden"))
            return self.GET_AUTH(*args, **kwargs)
        return INGIniousAuthPage.GET(self, *args, **kwargs)

    def POST(self, *args, **kwargs):
        """
        Checks if user is superadmin and calls POST_AUTH.
        Otherwise, returns the forbidden template.
        """

        username = self.user_manager.session_username()
        if self.user_manager.session_logged_in() and self.user_manager.user_is_superadmin(username):
            return self.POST_AUTH()
        return render_template("forbidden.html",
                                           message=_("You have not sufficient right to see this part."))


class SignInPage(INGIniousAuthPage):
    def GET_AUTH(self, *args, **kwargs):
        return redirect("/mycourses")

    def POST_AUTH(self, *args, **kwargs):
        return redirect("/mycourses")

    def GET(self):
        return INGIniousAuthPage.GET(self)


class LogOutPage(INGIniousAuthPage):
    def GET_AUTH(self, *args, **kwargs):
        self.user_manager.disconnect_user()
        return redirect("/courselist")

    def POST_AUTH(self, *args, **kwargs):
        self.user_manager.disconnect_user()
        return redirect("/courselist")


class INGIniousStaticPage(INGIniousPage):
    cache = {}

    def GET(self, pageid):
        return self.show_page(pageid)

    def POST(self, pageid):
        return self.show_page(pageid)

    def show_page(self, page):
        static_directory = self.app.static_directory
        language = self.user_manager.session_language()

        # Check for the file
        filename = None
        mtime = None
        filepaths = [os.path.join(static_directory, page + ".yaml"),
                     os.path.join(static_directory, page + "." + language + ".yaml")]

        for filepath in filepaths:
            if os.path.exists(filepath):
                filename = filepath
                mtime = os.stat(filepath).st_mtime

        if not filename:
            raise NotFound(description=_("File doesn't exist."))

        # Check and update cache
        if INGIniousStaticPage.cache.get(filename, (0, None))[0] < mtime:
            with open(filename, "r") as f:
                INGIniousStaticPage.cache[filename] = mtime, custom_yaml.load(f)

        filecontent = INGIniousStaticPage.cache[filename][1]
        title = filecontent["title"]
        content = ParsableText.rst(filecontent["content"], initial_header_level=2)

        return render_template("static.html", pagetitle=title, content=content)


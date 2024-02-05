# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Profile page """
import re

import flask
from pymongo import ReturnDocument
from werkzeug.exceptions import NotFound
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.user_manager import UserManager


class ProfilePage(INGIniousAuthPage):
    """ Profile page for DB-authenticated users"""

    def save_profile(self, userdata, data):
        """ Save user profile modifications """
        result = userdata
        error = False

        # Check if updating username.
        if not userdata["username"] and "username" in data:
            if re.match(r"^[-_|~0-9A-Z]{4,}$", data["username"], re.IGNORECASE) is None:
                error = True
                msg = _("Invalid username format.")
                return result, msg, error
            elif self.database.users.find_one({"username": data["username"]}):
                error = True
                msg = _("Username already taken")
                return result, msg, error
            else:
                result = self.database.users.find_one_and_update({"email": userdata["email"]},
                                                                 {"$set": {"username": data["username"]}},
                                                                 return_document=ReturnDocument.AFTER)
                if not result:
                    error = True
                    msg = _("Incorrect email.")
                    return result, msg, error
                else:
                    self.user_manager.connect_user(result["username"], result["realname"], result["email"],
                                                   result["language"], result.get("tos_accepted", False))

        # Check if updating the password.
        if self.app.allow_registration and len(data["passwd"]) in range(1, 6):
            error = True
            msg = _("Password too short.")
            return result, msg, error
        elif self.app.allow_registration and len(data["passwd"]) > 0 and data["passwd"] != data["passwd2"]:
            error = True
            msg = _("Passwords don't match !")
            return result, msg, error
        elif self.app.allow_registration and len(data["passwd"]) >= 6:

            if "password" in userdata:
                user = self.user_manager.auth_user(self.user_manager.session_username(), data["oldpasswd"], False)
            else:
                user = self.database.users.find_one({"username": userdata["username"]})

            if user is None:
                error = True
                msg = _("Incorrect old password.")
                return result, msg, error
            else:
                passwd_hash = UserManager.hash_password(data["passwd"])
                result = self.database.users.find_one_and_update({"username": self.user_manager.session_username()},
                                                                 {"$set": {"password": passwd_hash}},
                                                                 return_document=ReturnDocument.AFTER)

        # Check if updating language
        if data["language"] != userdata["language"]:
            language = data["language"] if data["language"] in self.app.available_languages else "en"
            result = self.database.users.find_one_and_update({"username": self.user_manager.session_username()},
                                                             {"$set": {"language": language}},
                                                             return_document=ReturnDocument.AFTER)
            if not result:
                error = True
                msg = _("Incorrect username.")
                return result, msg, error
            else:
                self.user_manager.set_session_language(language)

        # Checks if updating name
        if len(data["realname"]) > 0:
            result = self.database.users.find_one_and_update({"username": self.user_manager.session_username()},
                                                             {"$set": {"realname": data["realname"]}},
                                                             return_document=ReturnDocument.AFTER)
            if not result:
                error = True
                msg = _("Incorrect username.")
                return result, msg, error
            else:
                self.user_manager.set_session_realname(data["realname"])
        else:
            error = True
            msg = _("Name is too short.")
            return result, msg, error

        msg = _("Profile updated.")

        #updating tos
        if self.app.terms_page is not None and self.app.privacy_page is not None:
            self.database.users.find_one_and_update({"username": self.user_manager.session_username()},
                                                {"$set": {"tos_accepted": "term_policy_check" in data}})
            self.user_manager.set_session_tos_signed()
        return result, msg, error

    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ GET request """
        userdata = self.database.users.find_one({"email": self.user_manager.session_email()})

        if not userdata:
            raise NotFound(description=_("User unavailable."))

        return self.template_helper.render("preferences/profile.html", terms_page=self.app.terms_page,
                                           privacy_page=self.app.privacy_page, msg="", error=False)

    def POST_AUTH(self):  # pylint: disable=arguments-differ
        """ POST request """
        userdata = self.database.users.find_one({"email": self.user_manager.session_email()})

        if not userdata:
            raise NotFound(description=_("User unavailable."))


        msg = ""
        error = False
        data = flask.request.form
        if "save" in data:
            userdata, msg, error = self.save_profile(userdata, data)

        return self.template_helper.render("preferences/profile.html", terms_page=self.app.terms_page,
                                           privacy_page=self.app.privacy_page, msg=msg, error=error)

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Registration page"""

import hashlib
import random
import re
import flask
import logging

from smtplib import SMTPException
from flask_mail import Message
from werkzeug.exceptions import Forbidden
from inginious.frontend.pages.utils import INGIniousPage
from inginious.frontend.flask.mail import mail
from inginious.frontend.user_manager import UserManager


class RegistrationPage(INGIniousPage):
    """ Registration page for DB authentication """

    _logger = logging.getLogger("inginious.register")

    def GET(self):
        """ Handles GET request """
        if self.user_manager.session_logged_in() or not self.app.allow_registration:
            raise Forbidden(description=_("You're not allow to register."))

        error = False
        reset = None
        msg = ""
        data = flask.request.args

        if "activate" in data:
            error = self.user_manager.activate_user(data["activate"])
            msg = _("Invalid activation hash.") if error else _("User successfully activated.")
        elif "reset" in data:
            msg, error, reset = self.get_reset_data(data)

        return self.template_helper.render("register.html", terms_page=self.app.terms_page,
                                           privacy_page=self.app.privacy_page, reset=reset, msg=msg, error=error)

    def get_reset_data(self, data):
        """ Returns the user info to reset """
        error = False
        reset = None
        msg = ""
        user = self.database.users.find_one({"reset": data.get("reset", "")})
        if user is None:
            error = True
            msg = "Invalid reset hash."
        else:
            reset = {"hash": data["reset"], "username": user["username"], "realname": user["realname"]}

        return msg, error, reset

    def register_user(self, data):
        """ Parses input and register user """
        error = False
        msg = ""

        email = UserManager.sanitize_email(data["email"])

        # Check input format
        if re.match(r"^[-_|~0-9A-Z]{4,}$", data["username"], re.IGNORECASE) is None:
            error = True
            msg = _("Invalid username format.")
        elif email is None:
            error = True
            msg = _("Invalid email format.")
        elif len(data["passwd"]) < 6:
            error = True
            msg = _("Password too short.")
        elif data["passwd"] != data["passwd2"]:
            error = True
            msg = _("Passwords don't match !")
        elif self.app.terms_page is not None and self.app.privacy_page is not None and "term_policy_check" not in data:
            error = True
            msg = _("Please accept the Terms of Service and Data Privacy")

        if not error:
            existing_user = self.database.users.find_one(
                {"$or": [{"username": data["username"]}, {"email": email}]})
            if existing_user is not None:
                error = True
                if existing_user["username"] == data["username"]:
                    msg = _("This username is already taken !")
                else:
                    msg = _("This email address is already in use !")
            else:
                passwd_hash = UserManager.hash_password(data["passwd"])
                activate_hash = UserManager.hash_password_sha512(str(random.getrandbits(256)))
                self.database.users.insert_one({"username": data["username"],
                                                "realname": data["realname"],
                                                "email": email,
                                                "password": passwd_hash,
                                                "activate": activate_hash,
                                                "bindings": {},
                                                "language": self.user_manager._session.get("language", "en"),
                                                "tos_accepted": True
                                                })
                try:
                    subject = _("Welcome on INGInious")
                    body = _("""Welcome on INGInious !

To activate your account, please click on the following link :
""") + flask.request.url_root + "register?activate=" + activate_hash

                    message = Message(recipients=[(data["realname"], email)],
                                      subject=subject,
                                      body=body)
                    mail.send(message)
                    msg = _("You are succesfully registered. An email has been sent to you for activation.")
                except Exception as ex:
                    # Remove newly inserted user (do not add after to prevent email sending in case of failure)
                    self.database.users.delete_one({"username": data["username"]})
                    error = True
                    msg = _("Something went wrong while sending you activation email. Please contact the administrator.")
                    self._logger.error("Couldn't send email : {}".format(str(ex)))

        return msg, error

    def lost_passwd(self, data):
        """ Send a reset link to user to recover its password """
        error = False
        msg = ""

        # Check input format
        email_re = re.compile(
            r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
            r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"'  # quoted-string
            r')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$', re.IGNORECASE)  # domain
        if email_re.match(data["recovery_email"]) is None:
            error = True
            msg = _("Invalid email format.")

        if not error:
            reset_hash = UserManager.hash_password_sha512(str(random.getrandbits(256)))
            user = self.database.users.find_one_and_update({"email": data["recovery_email"]},
                                                           {"$set": {"reset": reset_hash}})
            if user is None:
                error = True
                msg = _("This email address was not found in database.")
            else:
                try:
                    subject = _("INGInious password recovery")

                    body = _("""Dear {realname},

Someone (probably you) asked to reset your INGInious password. If this was you, please click on the following link :
""").format(realname=user["realname"]) + flask.request.url_root + "register?reset=" + reset_hash

                    message = Message(recipients=[(user["realname"], data["recovery_email"])],
                                      subject=subject,
                                      body=body)
                    mail.send(message)

                    msg = _("An email has been sent to you to reset your password.")
                except Exception as ex:
                    error = True
                    msg = _("Something went wrong while sending you reset email. Please contact the administrator.")
                    self._logger.error("Couldn't send email : {}".format(str(ex)))

        return msg, error

    def reset_passwd(self, data):
        """ Reset the user password """
        error = False
        msg = ""

        # Check input format
        if len(data["passwd"]) < 6:
            error = True
            msg = _("Password too short.")
        elif data["passwd"] != data["passwd2"]:
            error = True
            msg = _("Passwords don't match !")

        if not error:
            passwd_hash = UserManager.hash_password(data["passwd"])
            user = self.database.users.find_one_and_update({"reset": data["reset"]},
                                                           {"$set": {"password": passwd_hash},
                                                            "$unset": {"reset": True, "activate": True}})
            if user is None:
                error = True
                msg = _("Invalid reset hash.")
            else:
                msg = _("Your password has been successfully changed.")

        return msg, error

    def POST(self):
        """ Handles POST request """
        if self.user_manager.session_logged_in() or not self.app.allow_registration:
            raise Forbidden(description=_("You're not allow to register."))

        reset = None
        msg = ""
        error = False
        data = flask.request.form
        if "register" in data:
            msg, error = self.register_user(data)
        elif "lostpasswd" in data:
            msg, error = self.lost_passwd(data)
        elif "resetpasswd" in data:
            msg, error, reset = self.get_reset_data(data)
            if reset:
                msg, error = self.reset_passwd(data)
            if not error:
                reset = None

        return self.template_helper.render("register.html", terms_page=self.app.terms_page,
                                           privacy_page=self.app.privacy_page, reset=reset, msg=msg, error=error)

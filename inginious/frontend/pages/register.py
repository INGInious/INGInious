# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Registration page"""

import re
import flask
import logging

from flask import current_app, session, render_template
from flask_mail import Message
from werkzeug.exceptions import Forbidden

from inginious.frontend.pages.utils import INGIniousPage
from inginious.frontend.flask.mail import mail
from inginious.frontend.controllers import auth


class RegistrationPage(INGIniousPage):
    """ Registration page for DB authentication """

    _logger = logging.getLogger("inginious.register")

    def GET(self):
        """ Handles GET request """
        if session.loggedin or not current_app.config.get("ALLOW_REGISTRATION"):
            raise Forbidden(description=_("You're not allow to register."))

        error = False
        reset = None
        msg = ""
        data = flask.request.args

        if "activate" in data:
            error = not auth.activate_user(data["activate"])
            msg = _("Invalid activation hash.") if error else _("User successfully activated.")
        elif "reset" in data:
            msg, error, reset = self.get_reset_data(data)

        return render_template("register.html", reset=reset, msg=msg, error=error)

    def get_reset_data(self, data):
        """ Returns the user info to reset """
        error = False
        reset = None
        msg = ""
        user = auth.get_reset_user(data.get("reset", ""))
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

        email = auth.sanitize_email(data["email"])

        # Check input format
        if re.match(r"^[-_|~0-9A-Z]{4,}$", data["username"], re.IGNORECASE) is None:
            error = True
            msg = _("Invalid username format.")
        elif not data["realname"]:
            error = True
            msg = _("Complete name is required.")
        elif email is None:
            error = True
            msg = _("Invalid email format.")
        elif password_error := auth.check_new_password(data["passwd"], data["passwd2"]):
            error = True
            msg = password_error
        elif current_app.config["IS_TOS_DEFINED"] and "term_policy_check" not in data:
            error = True
            msg = _("Please accept the Terms of Service and Data Privacy")

        if not error:
            user, msg = auth.register_user(data["username"], data["realname"], email, data["passwd"], session.language)
            if user is None:
                error = True
            else:
                try:
                    subject = _("Welcome on INGInious")
                    body = _("""Welcome on INGInious !

To activate your account, please click on the following link :
""") + flask.request.url_root + "register?activate=" + user.activate

                    message = Message(recipients=[(data["realname"], email)],
                                      subject=subject,
                                      body=body)
                    mail.send(message)
                    msg = _("You are succesfully registered. An email has been sent to you for activation.")
                except Exception as ex:
                    # Remove newly inserted user (do not add after to prevent email sending in case of failure)
                    user.delete()
                    error = True
                    msg = _("Something went wrong while sending you activation email. Please contact the administrator.")
                    self._logger.error("Couldn't send email : {}".format(str(ex)))

        return msg, error

    def lost_passwd(self, data):
        """ Send a reset link to user to recover its password """
        error = False
        msg = ""

        email = auth.sanitize_email(data["recovery_email"])
        if email is None:
            error = True
            msg = _("Invalid email format.")

        if not error:
            user = auth.create_reset_token(email)
            if user is None:
                error = True
                msg = _("This email address was not found in database.")
            else:
                try:
                    subject = _("INGInious password recovery")

                    body = _("""Dear {realname},

Someone (probably you) asked to reset your INGInious password. If this was you, please click on the following link :
""").format(realname=user["realname"]) + flask.request.url_root + "register?reset=" + user.reset

                    message = Message(recipients=[(user["realname"], user.email)],
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

        password_error = auth.check_new_password(data["passwd"], data["passwd2"])
        if password_error:
            error = True
            msg = password_error

        if not error:
            user = auth.reset_password(data["reset"], data["passwd"])
            if user is None:
                error = True
                msg = _("Invalid reset hash.")
            else:
                msg = _("Your password has been successfully changed.")

        return msg, error

    def POST(self):
        """ Handles POST request """
        if session.loggedin or not current_app.config.get("ALLOW_REGISTRATION"):
            raise Forbidden(description=_("You're not allow to register."))

        reset = None
        msg = ""
        error = False
        data = flask.request.form
        fields_to_strip = {"username", "realname", "email", "recovery_email"}
        data = {k: v.strip() if k in fields_to_strip else v for k, v in data.items()}
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

        return render_template("register.html", reset=reset, msg=msg, error=error)

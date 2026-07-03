# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" API token page """
from flask import session, request, redirect, render_template, url_for
import jwt
import datetime
from datetime import timezone

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.models import User


# test values to move to config file or configure in api token page (lifetime)
# one secret key per user ? If the secret key is found out, every user is at risk.
JWT_SECRET = "your-secret-key"
JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME = datetime.timedelta(days=365)  # Token lifetime of 1 year


class APITokenPage(INGIniousAuthPage):
    """ Page to view or generate an API token for the user """

    def GET_AUTH(self):
        """ GET request """

        user = User.objects(username=session["username"]).first()

        try:
            payload = jwt.decode(user.apitoken, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return self.show_page(errors=["Your token has expired, please generate a new one."])
        except jwt.InvalidTokenError:
            return self.show_page(errors=["Invalid token, please generate a new one."])

        expiration = datetime.datetime.fromtimestamp(payload["exp"], tz=timezone.utc).astimezone()

        return self.show_page(api_token=user.apitoken, expiration=expiration)

    def POST_AUTH(self):
        """ POST request, generates a new token for the user """

        user = User.objects(username=session["username"]).first()

        now = datetime.datetime.now(timezone.utc)
        payload = {
            "username": user.username,
            "exp": now + TOKEN_LIFETIME,
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        user.apitoken = token
        user.save()

        expiration = payload["exp"].astimezone()

        return self.show_page(api_token=token, expiration=expiration)

    def show_page(self, errors=None, api_token=None, expiration=None):
        """ Prepares and shows the course marketplace """
        if errors is None:
            errors = []
        return render_template("apitoken.html", errors=errors, api_token=api_token, expiration=expiration)
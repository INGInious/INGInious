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
from inginious.frontend.models import User, APIToken


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
        token_dict = {}

        for token in user.apitokens:
            token_dict[token.token] = token

        return self.show_page()

    def POST_AUTH(self):
        """ POST request, generates a new token for the user """

        user = User.objects(username=session["username"]).first()

        # generate a new token
        if "generate" in request.form:
            expiration = datetime.datetime.now(tz=timezone.utc) + TOKEN_LIFETIME
            payload = {
                "username": user.username,
                "exp": expiration.timestamp(),
            }
            token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM) # TODO : hash token

            return self.show_page(generated_token=token)

        # save the token and description in the database
        if "save" in request.form:
            generated_token = request.form.get("generated_token")
            description = request.form.get("description")

            if description == "" :
                return self.show_page(errors=["Description is required to save the token."])

            expiration = jwt.decode(generated_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])["exp"]
            expiration  = datetime.datetime.fromtimestamp(expiration, tz=timezone.utc)
            user.apitokens.append(APIToken(token=generated_token, expires=expiration, description=description))
            user.save()

            return self.show_page()

        # invalidates a token
        if "delete" in request.form:
            token_to_delete = request.form.get('token')
            user.apitokens = [token for token in user.apitokens if token.token != token_to_delete]
            user.save()


        return self.show_page()

    def show_page(self, generated_token=None, errors=None):
        """ Prepares and shows the course marketplace """
        if errors is None:
            errors = []

        user = User.objects(username=session["username"]).first()
        token_list = []

        for token in user.apitokens:
            token_list.append(token)

        return render_template("apitoken.html", errors=errors, generated_token=generated_token, token_list=token_list)
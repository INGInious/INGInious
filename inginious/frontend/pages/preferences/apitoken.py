# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" API token page """
from flask import session, request, render_template, current_app
import datetime
import zoneinfo
from datetime import timezone
import uuid
import jwt

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.models import User, APIToken
from inginious.frontend.user_manager import UserManager
from mongoengine import ValidationError


class APITokenPage(INGIniousAuthPage):
    """ Page to view or generate an API token for the user """

    def GET_AUTH(self):
        """ GET request """
        return self.show_page()

    def POST_AUTH(self):
        """ POST request, generates a new token for the user """

        user = User.objects(username=session["username"]).first()
        description = request.form.get("description")

        expires_in = request.form.get("expires_in", 10)
        if expires_in == "custom":
            expires_in = int(request.form.get("custom_expiration"))

        try:
            days = int(expires_in)
        except (TypeError, ValueError):
            return self.show_page(errors=["Please select a valid expiration duration."])

        if days < 10 or days > 365:
            return self.show_page(errors=["Expiration duration must be between 10 and 365 days."])

        expiration = datetime.datetime.now(tz=timezone.utc) + datetime.timedelta(days=days)

        token_id = uuid.uuid4().hex
        payload = {
            "id": token_id,
            "username": user.username,
            "exp": expiration.timestamp(),
        }

        current_secret = current_app.config["API_JWT_SECRET"]
        token = jwt.encode(payload, current_secret, algorithm=current_app.config["API_JWT_ALGORITHM"])

        try:
            new_token = APIToken(token=UserManager.hash_password(token), expires=expiration, description=description)
            user.apitokens[token_id] = new_token
            user.save()
        except ValidationError as e:
            return self.show_page(errors=[list(e.to_dict().values())[0]])
        return self.show_page(generated_token=token)


    def show_page(self, generated_token=None, errors=None):
        """ Prepares and shows the course marketplace """
        if errors is None:
            errors = []

        user = User.objects(username=session["username"]).first()
        # Exclude the token hash from the data sent to the template
        token_list = [
            {"token_id": token_id, "description": token.description, "expires": token.expires}
            for token_id, token in user.apitokens.items()
        ]

        return render_template("apitoken.html", errors=errors, generated_token=generated_token, token_list=token_list)
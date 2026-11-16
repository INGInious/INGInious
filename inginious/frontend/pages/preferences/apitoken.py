# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" API token page """
from flask import session, request, render_template
from mongoengine import ValidationError

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.models import User
from inginious.frontend.controllers import auth


class APITokenPage(INGIniousAuthPage):
    """ Page to view or generate an API token for the user """

    def GET_AUTH(self):
        """ GET request """
        return self.show_page()

    def POST_AUTH(self):
        """ POST request, generates a new token for the user """

        user = User.objects(username=session.username).first()
        if "save" in request.form:
            description = request.form.get("description")
            expires_in = request.form.get("expires_in", 10)

            if expires_in == "custom":
                expires_in = request.form.get("custom_days")

            try:
                days = int(expires_in)
            except (TypeError, ValueError):
                return self.show_page(errors=[_("Please select a valid expiration duration.")])

            if not 10 <= days <= 365:
                return self.show_page(errors=[_("Expiration duration must be between 10 and 365 days.")])

            try:
                token = auth.create_api_token(user, days, description)
            except ValidationError as e:
                return self.show_page(errors=[list(e.to_dict().values())[0]])
            return self.show_page(generated_token=token)

        elif "delete" in request.form:
            token_id = request.form.get("token_id")

            if not auth.revoke_api_token(user, token_id):
                return self.show_page(errors=["Token not found."])
            return self.show_page()

    def show_page(self, generated_token=None, errors=None):
        """ Prepares and shows the API token page with the list of tokens or errors. """
        if errors is None:
            errors = []

        user = User.objects(username=session.username).get()
        # Exclude the token hash from the data sent to the template
        token_list = [
            {"token_id": token_id, "description": token.description, "expires": token.expires}
            for token_id, token in user.apitokens.items()
        ]

        return render_template("apitoken.html", errors=errors, generated_token=generated_token, token_list=token_list)

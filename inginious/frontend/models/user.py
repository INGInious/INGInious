# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import tzlocal

from mongoengine import Document,  StringField, ListField, MapField, BooleanField, EmbeddedDocument, EmbeddedDocumentField, DateTimeField, ValidationError


class APIToken(EmbeddedDocument):
    """ Embedded document for API tokens. Contains the token hash, expiration date,description and hash algorithm used. """
    token = StringField(required=True)
    expires = DateTimeField(required=True)
    description = StringField(required=True)

class User(Document):
    username = StringField(required=True)
    realname = StringField(required=True)
    email = StringField(required=True)
    password = StringField()
    language = StringField(required=True, default="en")
    code_indentation = StringField(choices=["2", "3", "4", "tabs"], default="4")
    bindings = MapField(ListField()) # TODO: use custom validation or refactor
    ltibindings = MapField(StringField())
    tos_accepted = BooleanField(default=False)
    apikey = StringField(default=None)
    apitokens = MapField(EmbeddedDocumentField(APIToken), default={})
    timezone = StringField(default=lambda: tzlocal.get_localzone_name())
    pinned_courses = ListField(StringField(), default=list)
    activate = StringField()
    reset = StringField()

    meta = {"collection": "users", "indexes": ["username", "email"]}

    def clean(self):
        """
        Custom validation for the User model.
        """
        if len(self.apitokens) > 20:
            raise ValidationError("A user can have at most 20 API tokens.")
        if len(self.apitokens):
            for token in self.apitokens.values():
                if len(token.description) > 40:
                    raise ValidationError("Description must be at most 40 characters long.")
                if len(token.description) == 0:
                    raise ValidationError("Description cannot be empty.")

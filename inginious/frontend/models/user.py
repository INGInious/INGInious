# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import tzlocal

from mongoengine import Document,  StringField
from mongoengine.fields import ListField, MapField, BooleanField, DynamicField


class User(Document):
    username = StringField(required=True)
    realname = StringField(required=True)
    email = StringField(required=True)
    password = StringField()
    language = StringField(required=True, default="en")
    code_indentation = StringField(choices=["2", "3", "4", "tabs"], default="4")
    bindings = MapField(ListField()) # TODO: use custom validation or refactor
    ltibindings = MapField(MapField(DynamicField())) # TODO: use custom validation or refactor
    tos_accepted = BooleanField(default=False)
    apikey = StringField(default=None)
    timezone = StringField(default=lambda: tzlocal.get_localzone_name())
    activate = StringField()
    reset = StringField()

    meta = {"collection": "users", "indexes": ["username"]}
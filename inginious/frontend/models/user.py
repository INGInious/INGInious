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
    code_indentation = StringField(default="4")
    bindings = MapField(ListField())
    ltibindings = MapField(MapField(DynamicField())) # This should be refactored
    tos_accepted = BooleanField(default=False)
    apikey = StringField(default=None)
    timezone = StringField(default=lambda: tzlocal.get_localzone_name())
    activate = StringField()
    reset = StringField()

    meta = {"collection": "users"}
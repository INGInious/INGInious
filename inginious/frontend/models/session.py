# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import tzlocal
from bson.objectid import ObjectId
from mongoengine import Document, StringField, BooleanField
from mongoengine import DateTimeField, DynamicField, MapField, ObjectIdField


class Session(Document):
    id = ObjectIdField(primary_key=True, default=lambda: ObjectId()) # id should be available at creation time
    permanent = BooleanField(required=True)
    loggedin = BooleanField(required=True, default=False)
    auth_storage = MapField(DynamicField(), default=dict)
    expiration = DateTimeField()
    code_indentation = StringField(choices=["2", "3", "4", "tabs"], default="4")
    email = StringField()
    language = StringField(default="") # will be autodetected
    realname = StringField()
    token = StringField(default=None)
    tos_signed = BooleanField()
    username = StringField(default=None)
    timezone = StringField(default=lambda: tzlocal.get_localzone_name())

    meta = {
        "collection": "sessions",
        "indexes": [
            {
                'fields': ['expiration'],
                'expireAfterSeconds': 0 # use field value
            }
        ]
    }

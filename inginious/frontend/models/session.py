# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import tzlocal
from bson.objectid import ObjectId
from mongoengine import Document, StringField, ListField, EmbeddedDocument, EmbeddedDocumentField, BooleanField
from mongoengine import DateTimeField, DynamicField, MapField, ObjectIdField


class LTIData(EmbeddedDocument):
    version = StringField(required=True, default="")
    email = StringField(required=True, default="")
    username = StringField(required=True, default="")
    realname = StringField(required=True, default="")
    roles = ListField(StringField())
    task = ListField(StringField(), required=True, default=['', ''])

    context_title = StringField()
    context_label = StringField()
    tool_description = StringField()
    tool_name = StringField()
    tool_url = StringField()

    # LTI1.1
    consumer_key = StringField()
    outcome_service_url = StringField()
    outcome_result_id = StringField()

    # LTI1.3
    message_launch_id = StringField()
    platform_instance_id = StringField()


class Session(Document):
    id = ObjectIdField(primary_key=True, default=lambda: ObjectId()) # id should be available at creation time
    permanent = BooleanField(required=True)
    is_lti = BooleanField(required=True, default=False)
    loggedin = BooleanField(required=True, default=False)
    auth_storage = MapField(DynamicField(), default={})
    expiration = DateTimeField()
    lti = EmbeddedDocumentField(LTIData, default=lambda: LTIData())
    code_indentation = StringField(choices=["2", "3", "4", "tabs"], default="4")
    email = StringField()
    language = StringField(default="en")
    realname = StringField()
    token = StringField()
    tos_signed = BooleanField()
    username = StringField()
    timezone = StringField(default=lambda: tzlocal.get_localzone_name())

    meta = {"collection": "sessions", "indexes": ["expiration"]}

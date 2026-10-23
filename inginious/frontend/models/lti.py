# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from mongoengine import Document, StringField, ListField, BooleanField, EmbeddedDocument, EmbeddedDocumentField, \
    DynamicField, DateTimeField, ObjectIdField


class LTIData(EmbeddedDocument):
    """ User and context information extracted from a LTI launch message """
    version = StringField(required=True, default="")
    email = StringField(required=True, default="")
    username = StringField(required=True, default="")
    realname = StringField(required=True, default="")
    roles = ListField(StringField())
    task = ListField(StringField(), required=True, default=lambda: ['', ''])
    redir_url = StringField(required=True, default="")

    # Set once the user has been connected via the LTI login page
    valid = BooleanField(required=True, default=False)

    # LTI1.1: courseid/consumer key, LTI1.3: issuer/client_id/deployment_id
    platform_instance_id = StringField(required=True)

    context_title = StringField()
    context_label = StringField()
    tool_description = StringField()
    tool_name = StringField()
    tool_url = StringField()


class LaunchData(Document):
    """ LTI launch messages and nonces, launch ids being prefixed by the LTI version (lti1p1- or lti1p3-) """
    session_id = ObjectIdField()
    launch_id = StringField(required=True)  # pylti1p3 key
    value = DynamicField(required=True)
    expiration = DateTimeField(required=True)

    # Set by INGInious once the launch message is validated
    lti = EmbeddedDocumentField(LTIData)

    meta = {
        'collection': 'lti_launch',
        'indexes': [
            {'fields': ['session_id', 'launch_id'], 'unique': True},
            {
                'fields': ['expiration'],
                'expireAfterSeconds': 0  # use field value
            }
        ]
    }
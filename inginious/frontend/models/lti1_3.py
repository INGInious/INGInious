# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from mongoengine import Document, StringField, ListField, DynamicField, IntField, DateTimeField, EmbeddedDocumentField

from inginious.frontend.models.lti import LTIData


class LTIGrade(Document):
    courseid = StringField()
    taskid = StringField()
    username = StringField()
    nb_attempt = IntField()

    message_launch_id = StringField()

    meta = { 'collection': 'lti_grade_queue' }

class LaunchData(Document):
    key = StringField(required=True)
    value = DynamicField(required=True)
    expiration = DateTimeField(required=True)

    # Set by INGInious once the launch message is validated
    lti = EmbeddedDocumentField(LTIData)

    meta = {
        'collection': 'lti_launch',
        'indexes': [
            {
                'fields': ['expiration'],
                'expireAfterSeconds': 0  # use field value
            }
        ]
    }

    @classmethod
    def get_launch(cls, launch_id):
        """ Returns the validated launch message identified by launch_id, or None """
        return cls.objects(key=launch_id, lti__exists=True).first()
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import secrets

from mongoengine import Document, StringField, DateTimeField, IntField, EmbeddedDocumentField

from inginious.frontend.models.lti import LTIData


class Nonce(Document):
    timestamp = DateTimeField()
    nonce = StringField()
    expiration = DateTimeField()

    meta = {
        'collection': 'nonce',
        'indexes': [
            ('timestamp', 'nonce'),
            {
                'fields': ['expiration'],
                'expireAfterSeconds': 0 # use field value
            }
        ]
    }

class LISLaunch(Document):
    """ LTI 1.1 launch message information, outcome fields are needed to send grades back to the TC """
    key = StringField(required=True, unique=True, sparse=True, default=lambda: secrets.token_urlsafe(32))  # unguessable launch id
    consumer_key = StringField(required=True)
    outcome_service_url = StringField()
    outcome_result_id = StringField()
    lti = EmbeddedDocumentField(LTIData, required=True)
    expiration = DateTimeField(required=True)

    meta = {
        'collection': 'lis_launch',
        'indexes': [
            {
                'fields': ['expiration'],
                'expireAfterSeconds': 0  # use field value
            }
        ]
    }

    @classmethod
    def get_launch(cls, launch_id):
        """ Returns the launch identified by launch_id, or None """
        return cls.objects(key=launch_id).first()

class LISOutcome(Document):
    courseid = StringField()
    taskid = StringField()
    username = StringField()
    nb_attempt = IntField()

    message_launch_id = StringField()

    meta = {'collection': 'lis_outcome_queue'}
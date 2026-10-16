# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from mongoengine import Document, StringField, DateTimeField, IntField


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
    """ LTI 1.1 launch message information needed to send grades back to the TC """
    consumer_key = StringField(required=True)
    outcome_service_url = StringField(required=True)
    outcome_result_id = StringField(required=True)

    meta = {
        'collection': 'lis_launch',
        'indexes': [('consumer_key', 'outcome_service_url', 'outcome_result_id')]
    }

class LISOutcome(Document):
    courseid = StringField()
    taskid = StringField()
    username = StringField()
    nb_attempt = IntField()

    message_launch_id = StringField()

    meta = {'collection': 'lis_outcome_queue'}
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

class LISOutcome(Document):
    courseid = StringField()
    taskid = StringField()
    username = StringField()
    nb_attempt = IntField()

    outcome_consumer_key = StringField()
    outcome_result_id = StringField()
    outcome_service_url = StringField()

    meta = {'collection': 'lis_outcome_queue'}
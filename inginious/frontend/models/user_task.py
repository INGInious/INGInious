# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from datetime import datetime, timedelta

from mongoengine import Document, EmbeddedDocument, StringField, FloatField, ObjectIdField
from mongoengine import IntField, ListField, DateTimeField, BooleanField, EmbeddedDocumentField


class Tokens(EmbeddedDocument):
    amount = IntField(required=True, default=0)
    date = DateTimeField(default=datetime.fromtimestamp(0).astimezone())

class UserTask(Document):
    courseid = StringField(required=True)
    taskid = StringField(required=True)
    username = StringField(required=True)
    grade = FloatField(required=True, default=0)
    submissionid = ObjectIdField(null=True, default=None)
    succeeded = BooleanField(required=True, default=False)
    tried = IntField(required=True, default=0)
    random = ListField(FloatField(), default=[])
    tokens = EmbeddedDocumentField(Tokens, default=lambda : Tokens())
    state = StringField(required=True, default="")

    def reset_state(self):
        self.state = ""
        self.save()

    def reset_tokens(self):
        self.tokens.amount = 0
        self.tokens.date = datetime.now().astimezone()
        self.save()

    def check_tokens(self, submission_limit : dict):
        tokens_ok = self.tokens.amount < submission_limit["amount"]
        need_reset = self.tokens.date < datetime.now().astimezone() - timedelta(hours=submission_limit["period"])

        if submission_limit["period"] > 0 and need_reset:
            self.reset_tokens()
            tokens_ok = True

        return tokens_ok

    meta = {
        "collection": "user_tasks",
        "indexes": [
            {
                "fields": ["username", "courseid", "taskid"],
                "unique": True
             },
            ("username", "courseid"),
            ("courseid", "taskid"),
            "courseid",
            "username"
        ]
    }
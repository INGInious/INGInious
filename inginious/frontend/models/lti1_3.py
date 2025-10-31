# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from mongoengine import Document, StringField, ListField, DynamicField, IntField


class LTIGrade(Document):
    courseid = StringField()
    taskid = StringField()
    username = StringField()
    nb_attempt = IntField()

    message_launch_id = StringField()

    meta = { 'collection': 'lti_grade_queue' }

class LaunchData(Document):
    key = StringField(required=True)
    context = ListField(required=True)
    value = DynamicField(required=True)

    meta = {'collection': 'lti_launch'}
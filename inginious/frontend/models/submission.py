# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import bson

from mongoengine import Document, StringField, ListField, MapField, FileField, DateTimeField, FloatField, IntField


class Submission(Document):
    courseid = StringField(required=True)
    taskid = StringField(required=True)
    username = ListField(StringField(), required=True)
    input = FileField(required=True)
    archive = FileField()
    status = StringField(choices=["done", "error", "waiting"], required=True)
    submitted_on = DateTimeField(required=True)
    response_type = StringField(default='rst') # Deprecated
    grade = FloatField(default=0.0) # TODO: use min_value and max_value and change container API
    custom = MapField(StringField())
    problems = MapField(StringField())
    result = StringField(default="crash") # TODO: restrict possible values and change container API
    stderr  = StringField()
    stdout  = StringField()
    tests = MapField(StringField())
    text = StringField(default="")
    user_ip = StringField()
    state = StringField()
    jobid = StringField() # Following fields are used during job processing
    ssh_host = StringField()
    ssh_port = IntField()
    ssh_user = StringField()
    ssh_password = StringField()
    last_replay = DateTimeField()
    lti_version = StringField() # This should be refactored in the future to avoid storing data from modules
    message_launch_id = StringField() # LTI1.3 field
    outcome_service_url = StringField() # LTI1.1 field
    outcome_result_id = StringField() # LTI 1.1 field
    outcome_consumer_key = StringField() #LTI1.1 field

    def get_input(self):
        value = bson.BSON.decode(self.input.read())
        self.input.seek(0)
        return value

    def set_input(self, value):
        self.input.put(bson.BSON.encode(value))

    meta = {"collection": "submissions"}
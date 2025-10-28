# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from mongoengine import Document, StringField, ListField


class Audience(Document):
    description = StringField(required=True)
    courseid = StringField(required=True)
    students = ListField(StringField())
    tutors = ListField(StringField())

    meta = {"collection": "audiences", "indexes": ["courseid"]}
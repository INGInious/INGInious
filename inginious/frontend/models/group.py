# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from mongoengine import Document, StringField, ListField, IntField, ObjectIdField


class Group(Document):
    description = StringField(required=True)
    courseid = StringField(required=True)
    size = IntField(required=True)
    students = ListField(StringField())
    audiences = ListField(ObjectIdField())

    meta = {"collection": "groups", "indexes": ["courseid"]}
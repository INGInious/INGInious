# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from mongoengine import Document, StringField, ListField

class CourseClass(Document):
    id = StringField(primary_key=True)
    students = ListField(StringField())

    meta = {"collection": "courses"}
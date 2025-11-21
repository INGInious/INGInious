# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from mongoengine import Document, IntField

from inginious import DB_VERSION
from inginious.frontend.models.audience import Audience
from inginious.frontend.models.course_class import CourseClass
from inginious.frontend.models.group import Group
from inginious.frontend.models.lti1_1 import LISOutcome, Nonce
from inginious.frontend.models.lti1_3 import LTIGrade, LaunchData
from inginious.frontend.models.session import Session
from inginious.frontend.models.submission import Submission
from inginious.frontend.models.user import User
from inginious.frontend.models.user_task import UserTask


class DBVersion(Document):
    db_version = IntField(default=DB_VERSION)
    meta = {"collection": "db_version"}
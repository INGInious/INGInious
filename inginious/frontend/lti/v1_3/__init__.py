# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from datetime import datetime
import logging

from pylti1p3.contrib.flask import FlaskMessageLaunch
from pylti1p3.grade import Grade
from pylti1p3.lineitem import LineItem
from pylti1p3.launch_data_storage.base import LaunchDataStorage

from inginious.frontend.lti import LTIScorePublisher
from inginious.frontend import database


class MongoLTILaunchDataStorage(LaunchDataStorage):
    """
    Stores LTI Launch messages in database during the handshake process and
    to submit grades later using the LTIGradeManager.
    """
    def __init__(self, courseid, taskid, *args, **kwargs) -> None:
        self.query_context = (courseid, taskid)
        self._session_cookie_name = ""  # Disables session scope mechanism in favor of query_context
        super().__init__(*args, **kwargs)

    def can_set_keys_expiration(self) -> bool:
        return False  # TODO(mp): I think it's reasonable to clean LTI Launch messages further than a week away tho

    def get_value(self, key: str):
        entry = database.lti_launch.find_one({'key': key, 'context': self.query_context})
        return entry.get('value') if entry else None

    def set_value(self, key: str, value, exp) -> None:
        database.lti_launch.find_one_and_update({'key': key, 'context': self.query_context},
                                                     {'$set': {'key': key, 'value': value}}, upsert=True)

    def check_value(self, key: str) -> bool:
        return bool(database.lti_launch.find_one({'key': key, 'context': self.query_context}))


class LTIGradeManager(LTIScorePublisher):
    _submission_tags = {"message_launch_id": "message_launch_id"}

    def __init__(self, course_factory):
        self._logger = logging.getLogger("inginious.webapp.lti1_3.grade_manager")
        super(LTIGradeManager, self).__init__(database.lti_grade_queue, course_factory)

    def process(self, mongo_entry, grade):
        courseid, taskid, message_launch_id = (mongo_entry["courseid"], mongo_entry["taskid"], mongo_entry["message_launch_id"])

        try:
            course = self._course_factory.get_course(courseid)
            message_launch = FlaskMessageLaunch.from_cache(message_launch_id, request=None, tool_config=course.lti_tool(), launch_data_storage=MongoLTILaunchDataStorage(courseid, taskid))
            launch_data = message_launch.get_launch_data()
            ags = message_launch.get_ags()

            if ags.can_put_grade():
                sc = Grade()
                sc.set_score_given(grade) \
                    .set_score_maximum(100.0) \
                    .set_timestamp(datetime.now().astimezone().isoformat()) \
                    .set_activity_progress('Completed') \
                    .set_grading_progress('FullyGraded') \
                    .set_user_id(launch_data['sub'])

                ags.put_grade(sc)
                return True
        except Exception:
            self._logger.error("An exception occurred while sending a grade to the LTI Platform.", exc_info=True)

        return False

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


class MongoLTILaunchDataStorage(LaunchDataStorage):
    """
    Stores LTI Launch messages in database during the handshake process and
    to submit grades later using the LTIGradeManager.
    """
    def __init__(self, database, courseid, taskid, *args, **kwargs) -> None:
        self.database = database
        self.query_context = (courseid, taskid)
        self._session_cookie_name = ""  # Disables session scope mechanism in favor of query_context
        super().__init__(*args, **kwargs)

    def can_set_keys_expiration(self) -> bool:
        return False  # TODO(mp): I think it's reasonable to clean LTI Launch messages further than a week away tho

    def get_value(self, key: str):
        entry = self.database.lti_launch.find_one({'key': key, 'context': self.query_context})
        return entry.get('value') if entry else None

    def set_value(self, key: str, value, exp) -> None:
        self.database.lti_launch.find_one_and_update({'key': key, 'context': self.query_context},
                                                     {'$set': {'key': key, 'value': value}}, upsert=True)

    def check_value(self, key: str) -> bool:
        return bool(self.database.lti_launch.find_one({'key': key, 'context': self.query_context}))


class LTIGradeManager(LTIScorePublisher):
    _submission_tags = {"message_launch_id"}

    def __init__(self, database, user_manager, course_factory):
        self._logger = logging.getLogger("inginious.webapp.lti1_3.grade_manager")
        self._database = database
        super(LTIGradeManager, self).__init__(database.lti_grade_queue, user_manager, course_factory)

    def process(self, data):
        mongo_id, username, courseid, taskid, message_launch_id, nb_attempt = data

        try:
            course = self._course_factory.get_course(courseid)
            task = course.get_task(taskid)
            grade = self._user_manager.get_task_cache(username, courseid, task.get_id())["grade"]
        except Exception:
            self._logger.error("An exception occurred while getting a course/LTI secret/grade.", exc_info=True)
            return False, mongo_id,  nb_attempt

        try:
            message_launch = FlaskMessageLaunch.from_cache(message_launch_id, request=None, tool_config=course.lti_tool(), launch_data_storage=MongoLTILaunchDataStorage(self._database, courseid, taskid))
            launch_data = message_launch.get_launch_data()
            ags = message_launch.get_ags()

            if ags.can_put_grade():
                sc = Grade()
                # TODO(mp): Is there a better timestamp to set with the score? Submission time? Grading time?
                sc.set_score_given(grade) \
                    .set_score_maximum(100.0) \
                    .set_timestamp(datetime.now().isoformat() + 'Z') \
                    .set_activity_progress('Completed') \
                    .set_grading_progress('FullyGraded') \
                    .set_user_id(launch_data['sub'])

                sc_line_item = LineItem()
                sc_line_item.set_tag('score') \
                    .set_score_maximum(100) \
                    .set_label('Score')
                if launch_data:
                    sc_line_item.set_resource_id(launch_data['https://purl.imsglobal.org/spec/lti/claim/resource_link']['id'])

                ags.put_grade(sc, sc_line_item)
                self._delete_in_db(mongo_id)
                self._logger.debug("Successfully sent grade to LTI Platform: %s", str(data))
                return True, mongo_id,  nb_attempt
        except Exception:
            self._logger.error("An exception occurred while sending a grade to the LTI Platform.", exc_info=True)

        return False, mongo_id, nb_attempt

    def _add_to_queue(self, mongo_entry):
        self._queue.put((mongo_entry["_id"], mongo_entry["username"], mongo_entry["courseid"],
                         mongo_entry["taskid"], mongo_entry["message_launch_id"], mongo_entry["nb_attempt"]))

    def _get_search_dict(self, username, submission):
        return  {"username": username, "courseid": submission["courseid"],
                      "taskid": submission["taskid"], "message_launch_id": submission["message_launch_id"]}

    def tag_submission(self, submission, lti_info):
        if lti_info["message_launch_id"] is None:
            self._logger.error("message_launch_id is None, but grade needs to be sent back to LTI platform! Ignoring.")
            return

        submission.update({"message_launch_id": lti_info["message_launch_id"]})

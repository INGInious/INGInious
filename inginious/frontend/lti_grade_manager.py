# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Implements LTI AGS. """
from datetime import datetime
import logging
import threading
import queue
import time

from pymongo import ReturnDocument

from pylti1p3.contrib.flask import FlaskMessageLaunch
from pylti1p3.grade import Grade
from pylti1p3.lineitem import LineItem
from pylti1p3.launch_data_storage.base import LaunchDataStorage


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


class LTIGradeManager(threading.Thread):
    """ Waits for grading to complete and submit grade to the LTI Platform. """
    def __init__(self, database, app):
        super(LTIGradeManager, self).__init__()
        self.daemon = True
        self._database = database
        self._app = app
        self._queue = queue.Queue()
        self._stopped = False
        self._logger = logging.getLogger("inginious.webapp.lti_grade_manager")
        self.start()

    def stop(self):
        self._stopped = True

    def run(self):
        # Load old tasks from the database
        for todo in self._database.lti_grade_queue.find({}):
            self._add_to_queue(todo)

        try:
            while not self._stopped:
                time.sleep(0.5)
                data = self._queue.get()
                mongo_id, username, courseid, taskid, message_launch_id, nb_attempt = data

                try:
                    course = self._app.course_factory.get_course(courseid)
                    task = course.get_task(taskid)
                    grade = self._app.user_manager.get_task_cache(username, courseid, task.get_id())["grade"]
                except Exception:
                    self._logger.error("An exception occurred while getting a course/LTI secret/grade in LTIGradeManager.", exc_info=True)
                    continue

                try:
                    message_launch = FlaskMessageLaunch.from_cache(message_launch_id, request=None, tool_config=course.lti_tool(), launch_data_storage=MongoLTILaunchDataStorage(self._app.database, courseid, taskid))
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
                        continue
                except Exception:
                    self._logger.error("An exception occurred while sending a grade to the LTI Platform.", exc_info=True)

                if nb_attempt < 5:
                    self._logger.debug("An error occurred while sending a grade to the LTI Platform. Retrying...")
                    self._increment_attempt(mongo_id)
                else:
                    self._logger.error("An error occurred while sending a grade to the LTI Platform. Maximum number of retries reached.")
                    self._delete_in_db(mongo_id)
        except KeyboardInterrupt:
            pass

    def _add_to_queue(self, mongo_entry):
        self._queue.put((mongo_entry["_id"], mongo_entry["username"], mongo_entry["courseid"],
                         mongo_entry["taskid"], mongo_entry["message_launch_id"], mongo_entry["nb_attempt"]))

    def add(self, username, courseid, taskid, message_launch_id):
        """ Add a job in the queue
        :param username:
        :param courseid:
        :param taskid:
        :param message_launch_id:
        """
        search = {"username": username, "courseid": courseid,
                  "taskid": taskid, "message_launch_id": message_launch_id}

        entry = self._database.lti_grade_queue.find_one_and_update(search, {"$set": {"nb_attempt": 0}},
                                                                     return_document=ReturnDocument.BEFORE, upsert=True)
        if entry is None:  # and it should be
            self._add_to_queue(self._database.lti_grade_queue.find_one(search))

    def _delete_in_db(self, mongo_id):
        """
        Delete an element from the queue in the database
        :param mongo_id:
        :return:
        """
        self._database.lti_grade_queue.delete_one({"_id": mongo_id})

    def _increment_attempt(self, mongo_id):
        """
        Increment the number of attempt for an entry and
        :param mongo_id:
        :return:
        """
        entry = self._database.lti_grade_queue.find_one_and_update({"_id": mongo_id}, {"$inc": {"nb_attempt": 1}})
        self._add_to_queue(entry)

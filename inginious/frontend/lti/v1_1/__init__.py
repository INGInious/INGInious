# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Manages the calls to the TC """
import logging
import threading
import queue
import time

from lti import OutcomeRequest
from pymongo import ReturnDocument


class LTIOutcomeManager(threading.Thread):
    def __init__(self, database, user_manager, course_factory):
        super(LTIOutcomeManager, self).__init__()
        self.daemon = True
        self._database = database
        self._user_manager = user_manager
        self._course_factory = course_factory
        self._queue = queue.Queue()
        self._stopped = False
        self._logger = logging.getLogger("inginious.webapp.lti1_1.outcome_manager")
        self.start()

    def stop(self):
        self._stopped = True

    def run(self):
        # Load old tasks from the database
        for todo in self._database.lis_outcome_queue.find({}):
            self._add_to_queue(todo)

        try:
            while not self._stopped:
                time.sleep(0.5)
                data = self._queue.get()

                mongo_id, username, courseid, taskid, consumer_key, service_url, result_id, nb_attempt = data

                try:
                    course = self._course_factory.get_course(courseid)
                    task = course.get_task(taskid)

                    consumer_secret = course.lti_keys()[consumer_key]

                    grade = self._user_manager.get_task_cache(username, task.get_course_id(), task.get_id())["grade"]
                    grade = grade / 100.0
                    if grade > 1:
                        grade = 1
                    if grade < 0:
                        grade = 0
                except Exception:
                    self._logger.error("An exception occurred while getting a course/LTI secret/grade in LTIOutcomeManager.", exc_info=True)
                    continue

                try:
                    outcome_response = OutcomeRequest({"consumer_key": consumer_key,
                                                       "consumer_secret": consumer_secret,
                                                       "lis_outcome_service_url": service_url,
                                                       "lis_result_sourcedid": result_id}).post_replace_result(grade)

                    if outcome_response.code_major == "success":
                        self._delete_in_db(mongo_id)
                        self._logger.debug("Successfully sent grade to TC: %s", str(data))
                        continue
                except Exception:
                    self._logger.error("An exception occurred while sending a grade to the TC.", exc_info=True)

                if nb_attempt < 5:
                    self._logger.debug("An error occurred while sending a grade to the TC. Retrying...")
                    self._increment_attempt(mongo_id)
                else:
                    self._logger.error("An error occurred while sending a grade to the TC. Maximum number of retries reached.")
                    self._delete_in_db(mongo_id)
        except KeyboardInterrupt:
            pass

    def _add_to_queue(self, mongo_entry):
        self._queue.put((mongo_entry["_id"], mongo_entry["username"], mongo_entry["courseid"],
                         mongo_entry["taskid"], mongo_entry["consumer_key"], mongo_entry["service_url"],
                         mongo_entry["result_id"], mongo_entry["nb_attempt"]))

    def add(self, submission):
        """ Add a job in the queue
        :param submission: the submission dict
        """
        if "outcome_service_url" not in submission or "outcome_result_id" not in submission or "outcome_consumer_key" not in submission:
            return

        for username in submission["username"]:
            search = {"username": username, "courseid": submission["courseid"],
                      "taskid": submission["taskid"], "service_url": submission["outcome_service_url"],
                      "consumer_key": submission["outcome_consumer_key"], "result_id": submission["outcome_result_id"]}

            entry = self._database.lis_outcome_queue.find_one_and_update(search, {"$set": {"nb_attempt": 0}},
                                                                         return_document=ReturnDocument.BEFORE, upsert=True)
            if entry is None:  # and it should be
                self._add_to_queue(self._database.lis_outcome_queue.find_one(search))

    def _delete_in_db(self, mongo_id):
        """
        Delete an element from the queue in the database
        :param mongo_id:
        :return:
        """
        self._database.lis_outcome_queue.delete_one({"_id": mongo_id})

    def _increment_attempt(self, mongo_id):
        """
        Increment the number of attempt for an entry and
        :param mongo_id:
        :return:
        """
        entry = self._database.lis_outcome_queue.find_one_and_update({"_id": mongo_id}, {"$inc": {"nb_attempt": 1}})

        self._add_to_queue(entry)

    def tag_submission(self, submission, lti_info):
        """
        Tags the submission with the information needed for score publishing
        :param submission: the submission dictionary
        :param lti_info: the lti session information
        """
        outcome_service_url = lti_info["outcome_service_url"]
        outcome_result_id = lti_info["outcome_result_id"]
        outcome_consumer_key = lti_info["consumer_key"]

        # safety check
        if outcome_result_id is None or outcome_service_url is None:
            self._logger.error("outcome_result_id or outcome_service_url is None, but grade needs to be sent back to TC! Ignoring.")
            return

        submission.update({
            "outcome_service_url": outcome_service_url,
            "outcome_result_id": outcome_result_id,
            "outcome_consumer_key": outcome_consumer_key
        })
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LTI """

import threading
import queue
import time

from abc import ABCMeta, abstractmethod
from pymongo import ReturnDocument


class LTIScorePublisher(threading.Thread, metaclass=ABCMeta):
    _submission_tags = {}

    def __init__(self, mongo_collection, user_manager):
        super(LTIScorePublisher, self).__init__()
        self.daemon = True
        self._queue = queue.Queue()
        self._stopped = False

        self._mongo_collection = mongo_collection
        self._user_manager = user_manager
        self.start()

    def stop(self):
        self._stopped = True

    def run(self):
        # Load old tasks from the database
        for todo in self._mongo_collection.find({}):
            self._queue.put(todo)

        try:
            while not self._stopped:
                time.sleep(0.5)
                data = self._queue.get()

                try:
                    grade = self._user_manager.get_task_cache(data["username"], data["courseid"], data["taskid"])["grade"]
                except Exception:
                    self._logger.error("An exception occurred while getting a course/LTI secret/grade.", exc_info=True)
                    return False

                if self.process(data, grade):
                    self._delete_in_db(data["_id"])
                    self._logger.debug("Successfully sent grade to TC: %s", str(data))
                    continue

                if data["nb_attempt"] < 5:
                    self._logger.debug("An error occurred while sending a grade to the TC. Retrying...")
                    self._increment_attempt(data["_id"])
                else:
                    self._logger.error("An error occurred while sending a grade to the TC. Maximum number of retries reached.")
                    self._delete_in_db(data["_id"])
        except KeyboardInterrupt:
            pass

    @abstractmethod
    def process(self, data):
        pass

    def add(self, submission):
        """ Add a job in the queue
        :param submission: the submission dict
        """
        for tag in self._submission_tags.keys():
            if tag not in submission:
                return

        for username in submission["username"]:
            search = {"username": username, "courseid": submission["courseid"], "taskid": submission["taskid"]}
            search.update({key: submission[key] for key in self._submission_tags.keys()})
            entry = self._mongo_collection.find_one_and_update(search, {"$set": {"nb_attempt": 0}}, return_document=ReturnDocument.BEFORE, upsert=True)
            if entry is None:  # and it should be
                self._queue.put(self._mongo_collection.find_one(search))

    def _delete_in_db(self, mongo_id):
        """
        Delete an element from the queue in the database
        :param mongo_id:
        :return:
        """
        self._mongo_collection.delete_one({"_id": mongo_id})

    def _increment_attempt(self, mongo_id):
        """
        Increment the number of attempt for an entry and
        :param mongo_id:
        :return:
        """
        entry = self._mongo_collection.find_one_and_update({"_id": mongo_id}, {"$inc": {"nb_attempt": 1}})
        self._queue.put(entry)

    def tag_submission(self, submission, lti_info):
        """
        Tags the submission with the information needed for score publishing
        :param submission: the submission dictionary
        :param lti_info: the lti session information
        """
        for submission_key, lti_info_key in self._submission_tags.items():
            if lti_info[lti_info_key] is None:
                self._logger.error(lti_info_key + " is None, but grade needs to be sent back to LTI platform! Ignoring.")
                return
            submission[submission_key] = lti_info[lti_info_key]

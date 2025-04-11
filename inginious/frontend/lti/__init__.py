# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" LTI """

import threading
import queue
import time

from pymongo import ReturnDocument


class LTIScorePublisher(threading.Thread):

    def __init__(self, mongo_collection, user_manager, course_factory):
        super(LTIScorePublisher, self).__init__()
        self.daemon = True
        self._queue = queue.Queue()
        self._stopped = False

        self._mongo_collection = mongo_collection
        self._user_manager = user_manager
        self._course_factory = course_factory

        self.start()

    def stop(self):
        self._stopped = True

    def run(self):
        # Load old tasks from the database
        for todo in self._mongo_collection.find({}):
            self._add_to_queue(todo)

        try:
            while not self._stopped:
                time.sleep(0.5)
                data = self._queue.get()

                success, mongo_id, nb_attempt = self.process(data)

                if success:
                    continue

                if nb_attempt < 5:
                    self._logger.debug("An error occurred while sending a grade to the TC. Retrying...")
                    self._increment_attempt(mongo_id)
                else:
                    self._logger.error("An error occurred while sending a grade to the TC. Maximum number of retries reached.")
                    self._delete_in_db(mongo_id)
        except KeyboardInterrupt:
            pass

    def process(self, data):
        pass

    def _add_to_queue(self, mongo_entry):
        self._queue.put((mongo_entry["_id"], mongo_entry["username"], mongo_entry["courseid"],
                         mongo_entry["taskid"], mongo_entry["consumer_key"], mongo_entry["service_url"],
                         mongo_entry["result_id"], mongo_entry["nb_attempt"]))

    def _get_search_dict(self, username, submission):
        return {}

    def add(self, submission):
        """ Add a job in the queue
        :param submission: the submission dict
        """
        for tag in self._submission_tags:
            if tag not in submission:
                return

        for username in submission["username"]:
            search = self._get_search_dict(username, submission)
            entry = self._mongo_collection.find_one_and_update(search, {"$set": {"nb_attempt": 0}}, return_document=ReturnDocument.BEFORE, upsert=True)
            if entry is None:  # and it should be
                self._add_to_queue(self._mongo_collection.find_one(search))

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
        self._add_to_queue(entry)

    def tag_submission(self, submission, lti_info):
        pass

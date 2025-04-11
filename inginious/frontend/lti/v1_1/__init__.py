# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Manages the calls to the TC """
import logging

from lti import OutcomeRequest
from inginious.frontend.lti import LTIScorePublisher


class LTIOutcomeManager(LTIScorePublisher):
    _submission_tags = {"outcome_service_url", "outcome_result_id",   "outcome_consumer_key"}

    def __init__(self, database, user_manager, course_factory):
        self._logger = logging.getLogger("inginious.webapp.lti1_1.outcome_manager")
        super(LTIOutcomeManager, self).__init__(database.lis_outcome_queue, user_manager, course_factory)

    def process(self, data):
        mongo_id, username, courseid, taskid, consumer_key, service_url, result_id, nb_attempt = data

        try:
            course = self._course_factory.get_course(courseid)
            task = course.get_task(taskid)
            grade = self._user_manager.get_task_cache(username, task.get_course_id(), task.get_id())["grade"]
        except Exception:
            self._logger.error("An exception occurred while getting a course/LTI secret/grade.", exc_info=True)
            return False, mongo_id,  nb_attempt

        try:
            grade = grade / 100.0
            if grade > 1:
                grade = 1
            if grade < 0:
                grade = 0

            consumer_secret = course.lti_keys()[consumer_key]
            outcome_response = OutcomeRequest({"consumer_key": consumer_key,
                                               "consumer_secret": consumer_secret,
                                               "lis_outcome_service_url": service_url,
                                               "lis_result_sourcedid": result_id}).post_replace_result(grade)

            if outcome_response.code_major == "success":
                self._delete_in_db(mongo_id)
                self._logger.debug("Successfully sent grade to TC: %s", str(data))
                return True, mongo_id, nb_attempt
        except Exception:
            self._logger.error("An exception occurred while sending a grade to the TC.", exc_info=True)

        return False, mongo_id, nb_attempt

    def _add_to_queue(self, mongo_entry):
        self._queue.put((mongo_entry["_id"], mongo_entry["username"], mongo_entry["courseid"],
                         mongo_entry["taskid"], mongo_entry["consumer_key"], mongo_entry["service_url"],
                         mongo_entry["result_id"], mongo_entry["nb_attempt"]))

    def _get_search_dict(self, username, submission):
        return {"username": username, "courseid": submission["courseid"],
                "taskid": submission["taskid"], "service_url": submission["outcome_service_url"],
                "consumer_key": submission["outcome_consumer_key"], "result_id": submission["outcome_result_id"]}

    def tag_submission(self, submission, lti_info):
        """
        Tags the submission with the information needed for score publishing
        :param submission: the submission dictionary
        :param lti_info: the lti session information
        """

        if lti_info["outcome_result_id"] is None or lti_info["outcome_service_url"] is None:
            self._logger.error("outcome_result_id or outcome_service_url is None, but grade needs to be sent back to TC! Ignoring.")
            return

        submission.update({
            "outcome_service_url": lti_info["outcome_service_url"],
            "outcome_result_id": lti_info["outcome_result_id"],
            "outcome_consumer_key": lti_info["consumer_key"]
        })
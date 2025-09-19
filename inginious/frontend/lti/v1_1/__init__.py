# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Manages the calls to the TC """
import logging

from lti import OutcomeRequest
from inginious.frontend.lti import LTIScorePublisher

from inginious.frontend import database


class LTIOutcomeManager(LTIScorePublisher):
    _submission_tags = {"outcome_service_url": "outcome_service_url", "outcome_result_id": "outcome_result_id",
                        "outcome_consumer_key": "consumer_key"}

    def __init__(self, user_manager, course_factory):
        self._logger = logging.getLogger("inginious.webapp.lti1_1.outcome_manager")
        super(LTIOutcomeManager, self).__init__(database.lis_outcome_queue, user_manager, course_factory)

    def process(self, mongo_entry, grade):
        courseid, consumer_key, service_url, result_id = (mongo_entry["courseid"], mongo_entry["outcome_consumer_key"], mongo_entry["outcome_service_url"], mongo_entry["outcome_result_id"])

        try:
            clip = lambda n, minn, maxn: min(max(n, minn), maxn)
            grade = clip(grade / 100.0, 0.0, 1.0)

            course = self._course_factory.get_course(courseid)
            consumer_secret = course.lti_keys()[consumer_key]
            outcome_response = OutcomeRequest({"consumer_key": consumer_key,
                                               "consumer_secret": consumer_secret,
                                               "lis_outcome_service_url": service_url,
                                               "lis_result_sourcedid": result_id}).post_replace_result(grade)

            if outcome_response.code_major == "success":
                return True
        except Exception:
            self._logger.error("An exception occurred while sending a grade to the TC.", exc_info=True)

        return False

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Manages the calls to the TC """
import logging

from lti import OutcomeRequest
from inginious.frontend.lti import LTIScorePublisher
from inginious.frontend.courses import Course

from inginious.frontend.models.lti1_1 import LISOutcome

class LTIOutcomeManager(LTIScorePublisher):
    _submission_tags = {"outcome_service_url": "outcome_service_url", "outcome_result_id": "outcome_result_id",
                        "outcome_consumer_key": "consumer_key"}

    def __init__(self, user_manager):
        self._logger = logging.getLogger("inginious.webapp.lti1_1.outcome_manager")
        super(LTIOutcomeManager, self).__init__(LISOutcome, user_manager)

    def process(self, outcome : LISOutcome, grade):
        try:
            clip = lambda n, minn, maxn: min(max(n, minn), maxn)
            grade = clip(grade / 100.0, 0.0, 1.0)

            course = Course.get(outcome.courseid)
            consumer_secret = course.lti_keys()[outcome.outcome_consumer_key]
            outcome_response = OutcomeRequest({
                "consumer_key": outcome.outcome_consumer_key,
                "consumer_secret": consumer_secret,
                "lis_outcome_service_url": outcome.outcome_service_url,
                "lis_result_sourcedid": outcome.outcome_result_id
            }).post_replace_result(grade)

            if outcome_response.code_major == "success":
                return True
        except Exception:
            self._logger.error("An exception occurred while sending a grade to the TC.", exc_info=True)

        return False

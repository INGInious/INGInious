# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Manages the calls to the TC """
import logging
from datetime import datetime, timedelta, timezone

from lti import OutcomeRequest
from mongoengine.errors import NotUniqueError

from inginious.frontend.lti import LTIScorePublisher
from inginious.frontend.courses import Course

from inginious.frontend.models import LTIGrade, LaunchData


class MongoLTI11LaunchDataStorage:
    """
    Stores LTI1.1 launch messages and nonces in the same collection as LTI1.3.
    Keys must be prefixed by lti1p1-, as pylti1p3 does with lti1p3- for LTI1.3.
    """

    def __init__(self, session_id=None):
        """ Keys are bound to session_id if given """
        self._session_id = str(session_id) if session_id else None

    def set_value(self, key: str, value, exp) -> None:
        exp_date = datetime.now(timezone.utc) + timedelta(seconds=exp)
        LaunchData.objects(session_id=self._session_id, launch_id=key).update(value=value, expiration=exp_date,
                                                                              upsert=True)

    def add_value(self, key: str, value, exp) -> bool:
        """ Atomically stores the value if the key does not exist yet. Returns False if it already exists. """
        exp_date = datetime.now(timezone.utc) + timedelta(seconds=exp)
        try:
            result = LaunchData.objects(session_id=self._session_id, launch_id=key).update_one(
                set_on_insert__value=value, set_on_insert__expiration=exp_date, upsert=True, full_result=True)
            return result.upserted_id is not None
        except NotUniqueError:  # concurrent insertion of the same key
            return False


class LTIOutcomeManager(LTIScorePublisher):

    def __init__(self, user_manager):
        self._logger = logging.getLogger("inginious.webapp.lti1_1.outcome_manager")
        super(LTIOutcomeManager, self).__init__("1.1", user_manager)

    def process(self, outcome : LTIGrade, grade):
        try:
            clip = lambda n, minn, maxn: min(max(n, minn), maxn)
            grade = clip(grade / 100.0, 0.0, 1.0)

            course = Course.get(outcome.courseid)
            launch = LaunchData.objects.get(id=outcome.message_launch_id).value
            consumer_secret = course.lti_keys()[launch["consumer_key"]]
            outcome_response = OutcomeRequest({
                "consumer_key": launch["consumer_key"],
                "consumer_secret": consumer_secret,
                "lis_outcome_service_url": launch["outcome_service_url"],
                "lis_result_sourcedid": launch["outcome_result_id"]
            }).post_replace_result(grade)

            if outcome_response.code_major == "success":
                return True
        except Exception:
            self._logger.error("An exception occurred while sending a grade to the TC.", exc_info=True)

        return False

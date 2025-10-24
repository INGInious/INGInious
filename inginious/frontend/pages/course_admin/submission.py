# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import logging

from flask import request, redirect, render_template
from werkzeug.exceptions import NotFound, Forbidden
from bson.errors import InvalidId

from inginious.frontend.pages.course_admin.utils import INGIniousAdminPage


class SubmissionPage(INGIniousAdminPage):
    """ List information about a task done by a student """
    _logger = logging.getLogger("inginious.frontend.submissions")

    def fetch_submission(self, submissionid):
        try:
            submission = self.submission_manager.get_submission(submissionid, False)
            if not submission:
                raise NotFound(description=_("This submission doesn't exist."))
        except InvalidId as ex:
            self._logger.info("Invalid ObjectId : %s", submissionid)
            raise Forbidden(description=_("Invalid ObjectId."))

        courseid = submission["courseid"]
        taskid = submission["taskid"]
        course, task = self.get_course_and_check_rights(courseid, taskid)
        return course, task, submission

    def GET_AUTH(self, submissionid):  # pylint: disable=arguments-differ
        """ GET request """
        course, task, submission = self.fetch_submission(submissionid)
        return self.page(course, task, submission)

    def POST_AUTH(self, submissionid):  # pylint: disable=arguments-differ
        course, task, submission = self.fetch_submission(submissionid)
        is_admin = self.user_manager.has_admin_rights_on_course(course)

        webinput = request.form
        if "replay" in webinput and is_admin:
            self.submission_manager.replay_job(course, task, submission, course.get_task_dispenser())
        elif "replay-copy" in webinput:  # Authorized for tutors
            self.submission_manager.replay_job(course, task, submission, course.get_task_dispenser(), True)
            return redirect(self.app.get_path("course", course.get_id(), task.get_id()))
        elif "replay-debug" in webinput and is_admin:
            self.submission_manager.replay_job(course, task, submission, course.get_task_dispenser(), True, "ssh")
            return redirect(self.app.get_path("course", course.get_id(), task.get_id()))

        return self.page(course, task, submission)

    def page(self, course, task, submission):
        """ Get all data and display the page """
        submission = self.submission_manager.get_feedback_from_submission(submission, show_everything=True)

        to_display = {
            problem.get_id(): {
                "id": problem.get_id(),
                "name": problem.get_name(self.user_manager.session_language()),
                "defined": True
            } for problem in task.get_problems()
        }

        to_display.update({
            pid: {
                "id": pid,
                "name": pid,
                "defined": False
            } for pid in (set(submission.get_input()) - set(to_display))
        })

        return render_template("course_admin/submission.html", course=course, task=task,
                                           submission=submission, to_display=to_display.values(),
                                           pdict={problem.get_id(): problem.get_type() for problem in task.get_problems()})

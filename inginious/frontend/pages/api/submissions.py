# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Submissions """

import base64
import gettext
import flask

from inginious.frontend.pages.api._api_page import APIAuthenticatedPage, APINotFound, APIForbidden, APIInvalidArguments, APIError
from inginious.frontend.user_manager import user_manager
from inginious.frontend.course_factory import course_factory


def _get_submissions(submission_manager, courseid, taskid, with_input, submissionid=None):
    """
        Helper for the GET methods of the two following classes
    """

    try:
        course = course_factory.get_course(courseid)
    except:
        raise APINotFound("Course not found")

    if not user_manager.course_is_open_to_user(course, lti=False):
        raise APIForbidden("You are not registered to this course")

    try:
        task = course.get_task(taskid)
    except:
        raise APINotFound("Task not found")

    if submissionid is None:
        submissions = submission_manager.get_user_submissions(task)
    else:
        try:
            submissions = [submission_manager.get_submission(submissionid)]
        except:
            raise APINotFound("Submission not found")
        if submissions[0]["taskid"] != task.get_id() or submissions[0]["courseid"] != course.get_id():
            raise APINotFound("Submission not found")

    output = []

    for submission in submissions:
        submission = submission_manager.get_feedback_from_submission(
            submission,
            show_everything=user_manager.has_staff_rights_on_course(course, user_manager.session_username())
        )
        data = {
            "id": str(submission["_id"]),
            "submitted_on": submission["submitted_on"].isoformat(),
            "status": submission["status"]
        }

        if with_input:
            data["input"] = submission_manager.get_input_from_submission(submission, True)

            # base64 encode file to allow JSON encoding
            for d in data["input"]:
                if isinstance(d, dict) and d.keys() == {"filename", "value"}:
                    d["value"] = base64.b64encode(d["value"]).decode("utf8")

        if submission["status"] == "done":
            data["grade"] = submission.get("grade", 0)
            data["result"] = submission.get("result", "crash")
            data["feedback"] = submission.get("text", "")
            data["problems_feedback"] = submission.get("problems", {})

        output.append(data)

    return 200, output


class APISubmissionSingle(APIAuthenticatedPage):
    r"""
        Endpoint
          ::

            /api/v0/courses/[a-zA-Z_\-\.0-9]+/tasks/[a-zA-Z_\-\.0-9]+/submissions/[a-zA-Z_\-\.0-9]+

    """

    def API_GET(self, courseid, taskid, submissionid):  # pylint: disable=arguments-differ
        """
            List all the submissions that the connected user made. Returns list of the form

            ::

                [
                    {
                        "id": "submission_id1",
                        "submitted_on": "date",
                        "status" : "done",          #can be "done", "waiting", "error" (execution status of the task).
                        "grade": 0.0,
                        "input": {},                #the input data. File are base64 encoded.
                        "result" : "success"        #only if status=done. Result of the execution.
                        "feedback": ""              #only if status=done. the HTML global feedback for the task
                        "problems_feedback":        #only if status=done. HTML feedback per problem. Some pid may be absent.
                        {
                            "pid1": "feedback1",
                            #...
                        }
                    }
                    #...
                ]

            If you use the endpoint /api/v0/courses/the_course_id/tasks/the_task_id/submissions/submissionid,
            this dict will contain one entry or the page will return 404 Not Found.
        """
        with_input = "input" in flask.request.args

        return _get_submissions(self.submission_manager, courseid, taskid, with_input, submissionid)


class APISubmissions(APIAuthenticatedPage):
    r"""
        Endpoint
          ::

            /api/v0/courses/[a-zA-Z_\-\.0-9]+/tasks/[a-zA-Z_\-\.0-9]+/submissions

    """

    def API_GET(self, courseid, taskid):  # pylint: disable=arguments-differ
        """
            List all the submissions that the connected user made. Returns dicts in the form

            ::

                [
                    {
                        "id": "submission_id1",
                        "submitted_on": "date",
                        "status" : "done",          #can be "done", "waiting", "error" (execution status of the task).
                        "grade": 0.0,
                        "input": {},                #the input data. File are base64 encoded.
                        "result" : "success"        #only if status=done. Result of the execution.
                        "feedback": ""              #only if status=done. the HTML global feedback for the task
                        "problems_feedback":        #only if status=done. HTML feedback per problem. Some pid may be absent.
                        {
                            "pid1": "feedback1",
                            #...
                        }
                    }
                    #...
                ]

            If you use the endpoint /api/v0/courses/the_course_id/tasks/the_task_id/submissions/submissionid,
            this dict will contain one entry or the page will return 404 Not Found.
        """
        with_input = "input" in flask.request.args

        return _get_submissions(self.submission_manager, courseid, taskid, with_input)

    def API_POST(self, courseid, taskid):  # pylint: disable=arguments-differ
        """
            Creates a new submissions. Takes as (POST) input the key of the subproblems, with the value assigned each time.

            Returns

            - an error 400 Bad Request if all the input is not (correctly) given,
            - an error 403 Forbidden if you are not allowed to create a new submission for this task
            - an error 404 Not found if the course/task id not found
            - an error 500 Internal server error if the grader is not available,
            - 200 Ok, with {"submissionid": "the submission id"} as output.
        """

        try:
            course = course_factory.get_course(courseid)
        except:
            raise APINotFound("Course not found")

        username = user_manager.session_username()

        if not user_manager.course_is_open_to_user(course, username, False):
            raise APIForbidden("You are not registered to this course")

        try:
            task = course.get_task(taskid)
        except:
            raise APINotFound("Task not found")

        user_manager.user_saw_task(username, courseid, taskid)

        # Verify rights
        if not user_manager.task_can_user_submit(task, username, False):
            raise APIForbidden("You are not allowed to submit for this task")

        user_input = flask.request.form.copy()
        for problem in task.get_problems():
            pid = problem.get_id()
            if problem.input_type() == list:
                user_input[pid] = flask.request.form.getlist(pid)
            elif problem.input_type() == dict:
                user_input[pid] = flask.request.files.get(pid)
            else:
                user_input[pid] = flask.request.form.get(pid)

        user_input = task.adapt_input_for_backend(user_input)

        if not task.input_is_consistent(user_input, self.default_allowed_file_extensions, self.default_max_file_size):
            raise APIInvalidArguments()

        # Get debug info if the current user is an admin
        debug = user_manager.has_admin_rights_on_course(course, username)


        # Start the submission
        try:
            submissionid, _ = self.submission_manager.add_job(task, user_input, course.get_task_dispenser(), debug)
            return 200, {"submissionid": str(submissionid)}
        except Exception as ex:
            raise APIError(500, str(ex))

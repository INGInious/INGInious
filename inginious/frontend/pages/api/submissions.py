# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Submissions """

import base64
import flask
import json

from flask import current_app, session, request
from inginious.frontend.courses import Course
from inginious.frontend.pages.api._api_page import APIAuthenticatedPage, APITokenAuthPage, APINotFound, APIForbidden, APIInvalidArguments, APIError
from inginious.frontend.models.submission import Submission


def _get_submissions(submission_manager, user_manager, courseid, taskid, with_input, submissionid=None):
    """
        Helper for the GET methods of the two following classes
    """

    try:
        course = Course.get(courseid)
    except:
        raise APINotFound("Course not found")

    if not user_manager.course_is_open_to_user(course, lti=False):
        raise APIForbidden("You are not registered to this course")

    try:
        task = course.get_task(taskid)
    except:
        raise APINotFound("Task not found")

    if submissionid is None:
        submissions = submission_manager.get_user_submissions(course, task)
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
            show_everything=user_manager.has_staff_rights_on_course(course, session.username)
        )
        data = {
            "id": str(submission["id"]),
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

        return _get_submissions(self.submission_manager, self.user_manager, courseid, taskid, with_input, submissionid)


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

        return _get_submissions(self.submission_manager, self.user_manager, courseid, taskid, with_input)

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
            course = Course.get(courseid)
        except:
            raise APINotFound("Course not found")

        username = session.username

        if not self.user_manager.course_is_open_to_user(course, username, False):
            raise APIForbidden("You are not registered to this course")

        try:
            task = course.get_task(taskid)
        except:
            raise APINotFound("Task not found")

        self.user_manager.user_saw_task(username, courseid, taskid)

        # Verify rights
        if not self.user_manager.task_can_user_submit(course, task, username, False):
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

        if not task.input_is_consistent(user_input, current_app.config('ALLOWED_FILE_EXTENSIONS'),
                                        current_app.config.get('MAX_FILE_SIZE')):
            raise APIInvalidArguments()

        # Get debug info if the current user is an admin
        debug = self.user_manager.has_admin_rights_on_course(course, username)


        # Start the submission
        try:
            submissionid, _ = self.submission_manager.add_job(course, task, user_input, course.get_task_dispenser(), debug)
            return 200, {"submissionid": str(submissionid)}
        except Exception as ex:
            raise APIError(500, str(ex))



class APISubmissionsTest(APITokenAuthPage):

    def API_GET(self):
        """
            Test endpoint.
            Returns a 200 OK if the endpoint is reachable and the user has access to it.
            Returns 403 Forbidden if the user does not have access to the course/task.
            Returns 404 Not Found if the course/task does not exist.
        """


        # Does APITokenAuthPage automatically checks for APIForbidden? -> normally yes,

        # TODO : get user from token, for now we use a hardcoded username

        return 200, {"message": "Submissions endpoint is reachable and user has access."}


class APISubmissionsCourse(APITokenAuthPage):

    def API_POST(self, courseid):
        """
            Endpoint sending back all submissions of a course. Only accessible to staff members of the course.
            Returns a 200 OK if the endpoint is reachable and the user has access to it.
            Returns 403 Forbidden if the user does not have access to the course/task.
            Returns 404 Not Found if the course does not exist.
        """

        username = self.user.username

        try:
            course = Course.get(courseid)
        except:
            raise APINotFound("Course not found")

        if not self.user_manager.has_staff_rights_on_course(course, username, include_superadmins=True):
            raise APIForbidden("You cannot access this course")

        data = request.get_json(silent=True) or {}

        select = data.get("select", "all")
        usernames = data.get("username", None)
        response_format = data.get("format", "json")

        if select not in ("all", "best", "last"):
            raise APIInvalidArguments()
        if response_format not in ("json", "csv"):
            raise APIInvalidArguments()
        if usernames is not None and not isinstance(usernames, list):
            raise APIInvalidArguments()

        query = {"courseid": courseid, "status": "done"}
        if usernames:
            query["username__in"] = usernames

        submissions = Submission.objects(**query) \
            .only("courseid", "taskid", "username", "submitted_on", "result", "grade", "stderr", "stdout", "input") \
            .order_by("-submitted_on")

        if select == "last":
            seen = set()
            result = []
            for s in submissions:
                key = tuple(sorted(s.username))
                if key not in seen:
                    seen.add(key)
                    result.append(s)
            submissions = result

        elif select == "best":
            best = {}
            for s in submissions:
                key = tuple(sorted(s.username))
                if key not in best or s.grade > best[key].grade:
                    best[key] = s
            submissions = list(best.values())

        # TODO : implement CSV format functionality

        if select in ("best", "last"):
            submissions_list = [json.loads(s.to_json()) for s in submissions]
        else:
            submissions_list = json.loads(submissions.to_json())

        return 200, submissions_list


    # warning
    # format submitted_on correctly
    # format input correctly (base64 encode files) -> use .get_input ?
    # send back archive ?
    # send back text feedback ? -> text sent back to the student after submitting its work, not the feedback sent back by the grader

    # filter on date range ?


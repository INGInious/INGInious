# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Submissions """

import base64
import flask
import binascii
from werkzeug.datastructures import FileStorage
from io import BytesIO
import logging

from flask import current_app
from inginious.frontend.courses import Course
from inginious.frontend.submission_manager import SubmissionAlreadyPendingError
from inginious.frontend.pages.api._api_page import APIAuthenticatedPageV0, APIAuthenticatedPageV1, APINotFound, APIInvalidArguments, APIError


_logger = logging.getLogger("inginious.frontend.api")

def _get_submissions(submission_manager, user_manager, courseid, taskid, username, with_input, submissionid=None):
    """
        Helper for the GET methods of the two following classes
    """
    try:
        course = Course.get(courseid)
    except:
        _logger.info("Course %r not found", courseid)
        raise APINotFound()

    if not user_manager.course_is_open_to_user(course, username, lti=False):
        _logger.warning("Course %r not open to user %r", courseid, username)
        raise APINotFound()

    try:
        task = course.get_task(taskid)
    except:
        _logger.info("Task %r not found in course %r", taskid, courseid)
        raise APINotFound()

    if not user_manager.task_is_visible_by_user(course, task, username, lti=False):
        _logger.warning("Task %r not visible to user %r in course %r", taskid, username, courseid)
        raise APINotFound()

    if submissionid is None:
        submissions = submission_manager.get_user_submissions(course, task, username)
    else:
        try:
            submission = submission_manager.get_submission(submissionid, as_username=username)
        except:
            _logger.warning("User %r tried accessing a non existing submission : %r", username, submissionid)
            raise APINotFound()

        if submission is None:
            _logger.warning("User %r tried to access submission %r which does not belong to them", username, submissionid)
            raise APINotFound()
        if submission.taskid != task.get_id() or submission.courseid != course.get_id():
            _logger.warning("Submission %r not found for user %r, for task %r in course %r", submissionid, username, taskid, courseid)
            raise APINotFound()
        submissions = [submission]

    output = []

    for submission in submissions:
        submission = submission_manager.get_feedback_from_submission(
            submission,
            show_everything=user_manager.has_staff_rights_on_course(course, username)
        )
        data = {
            "id": str(submission.id),
            "submitted_on": submission.submitted_on.isoformat(),
            "status": submission.status
        }

        if with_input:
            data["input"] = submission_manager.get_input_from_submission(submission, True)

            # base64 encode file to allow JSON encoding
            for d in data["input"]:
                if isinstance(d, dict) and d.keys() == {"filename", "value"}:
                    d["value"] = base64.b64encode(d["value"]).decode("utf8")

        if submission["status"] == "done":
            data["grade"] = submission.grade
            data["result"] = submission.result
            data["feedback"] = submission.text
            data["problems_feedback"] = submission.problems

        output.append(data)

    return 200, output


class APISubmissionSingle(APIAuthenticatedPageV0):
    r"""
        Endpoint
          ::

            /api/v0/courses/[a-zA-Z_\-\.0-9]+/tasks/[a-zA-Z_\-\.0-9]+/submissions/[a-zA-Z_\-\.0-9]+

    """

    def API_GET(self, courseid, taskid, submissionid):  # pylint: disable=arguments-differ
        """
            List a submission that the connected user made. Returns a one element list of the form

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
                ]

            Returns 404 Not Found if the course, task or submission does not exist, if the client is not allowed to
            access the submission or if he is not registered to the course.
        """
        with_input = "input" in flask.request.args

        return _get_submissions(self.submission_manager, self.user_manager, courseid, taskid, flask.g.user.username, with_input, submissionid)


class APISubmissions(APIAuthenticatedPageV0):
    r"""
        Endpoint
          ::

            /api/v0/courses/[a-zA-Z_\-\.0-9]+/tasks/[a-zA-Z_\-\.0-9]+/submissions

    """

    def API_GET(self, courseid, taskid):  # pylint: disable=arguments-differ
        """
            List all the submissions that the connected user made. Returns dicts of the form

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

            Returns 404 Not Found if the course or task does not exist or if the client is not registered to the course.
        """
        with_input = "input" in flask.request.args

        return _get_submissions(self.submission_manager, self.user_manager, courseid, taskid, flask.g.user.username, with_input)

    def API_POST(self, courseid, taskid):  # pylint: disable=arguments-differ
        """
            Creates a new submissions. Takes as (POST) input the key of the subproblems, with the value assigned each time.

            Returns

            - an error 400 Bad Request if all the input is not (correctly) given,
            - an error 404 Not found if the course/task id not found, or if you are not allowed to access/submit to it,
            - an error 500 Internal server error if the grader is not available,
            - 200 Ok, with {"submissionid": "the submission id"} as output.
        """

        try:
            course = Course.get(courseid)
        except:
            self._logger.info("Course %r not found", courseid)
            raise APINotFound()

        username = flask.g.user.username

        if not self.user_manager.course_is_open_to_user(course, username, False):
            self._logger.warning("Course %r not open to user %r", courseid, username)
            raise APINotFound()

        try:
            task = course.get_task(taskid)
        except:
            self._logger.info("Task %r not found in course %r", taskid, courseid)
            raise APINotFound()

        self.user_manager.user_saw_task(username, courseid, taskid)

        # Verify rights
        if not self.user_manager.task_can_user_submit(course, task, username, False):
            self._logger.warning("User %r cannot submit to task %r in course %r", username, taskid, courseid)
            raise APINotFound()

        if flask.request.is_json:
            user_input = flask.request.get_json()
            for problem in task.get_problems():
                pid = problem.get_id()
                if problem.input_type() == list:
                    value = user_input.get(pid, [])
                    user_input[pid] = value if isinstance(value, list) else [value]
                elif problem.input_type() == dict:
                    # File inputs are not supported in JSON requests. Needs to be sent in base64 encoded format
                    value = user_input.get(pid)
                    if isinstance(value, dict) and "filename" in value and "value" in value:
                        try:
                            user_input[pid] = FileStorage(BytesIO(base64.b64decode(value["value"])),value["filename"])
                        except (binascii.Error, TypeError, ValueError):
                            raise APIInvalidArguments()
        else:
            user_input = flask.request.form.copy().to_dict()
            for problem in task.get_problems():
                pid = problem.get_id()
                if problem.input_type() == list:
                    user_input[pid] = flask.request.form.getlist(pid)
                elif problem.input_type() == dict:
                    user_input[pid] = flask.request.files.get(pid)

        user_input = task.adapt_input_for_backend(user_input)

        if not task.input_is_consistent(user_input, current_app.config['ALLOWED_FILE_EXTENSIONS'],
                                        current_app.config['MAX_FILE_SIZE']):
            raise APIInvalidArguments()

        # Get debug info if the current user is an admin
        debug = self.user_manager.has_admin_rights_on_course(course, username)


        # Start the submission
        try:
            submissionid, _ = self.submission_manager.add_job(course, task, user_input, course.get_task_dispenser(), username, debug)
            return 200, {"submissionid": str(submissionid)}
        except SubmissionAlreadyPendingError as ex:
            self._logger.info("User %r already has a pending submission on task %r in course %r.", username, taskid, courseid)
            raise APIError(409, {"error": str(ex)})
        except Exception as ex:
            self._logger.exception("Error while adding a submission for user %r on task %r in course %r: %r", username, taskid, courseid, ex)
            raise APIError(500, {"error": str(ex) if debug else "Internal server error"})


class APISubmissionsCourseV1(APIAuthenticatedPageV1):
    """
        Endpoints
            ::

                /api/v1/courses/[a-zA-Z_\-\.0-9]+/submissions

                /api/v1/courses/[a-zA-Z_\-\.0-9]+/[a-zA-Z_\-\.0-9]+/submissions
    """

    def POST(self, courseid, taskid=None):
        """
            List all the submissions from a course (or particular task if a taskid is given) that are evaluation submissions.
            That is, the ones that will be used for the final grade. Depending on the task those can be the last or best submissions.
            Only accessible to staff members of the course.
            Returns 200 OK if the endpoint is reachable and the user has access to it.
            Returns 400 Bad Request if the request body is not valid JSON or does not respect the expected format.
            Returns 404 Not Found if the client does not have access to the course/task or if they try to access other user's submissions while not being an admin of the course.

            Returns submissions containing all values except the ip of the user for security reasons and the status because it will always be "done".
            Example :
            ::

                {
                  "_id": {
                    "$oid": "6ab3df2a8d9eb36e888ba709"
                  },
                  "courseid": "tutorial",
                  "taskid": "01_getting_started",
                  "username": [
                    "test"
                  ],
                  "input": {
                    "$oid": "6ab3df2a8d9eb36e888ba707"
                  },
                  "archive": {
                    "$oid": "6ab3df2a8d9eb36e888ba70a"
                  },
                  "submitted_on": {
                    "$date": 1790172970090
                  },
                  "response_type": "rst",
                  "grade": 100.0,
                  "custom": {},
                  "problems": {},
                  "result": "success",
                  "stderr": "",
                  "stdout": "",
                  "tests": {},
                  "text": "",
                  "state": ""
                }

            The response is streamed as newline-delimited JSON (NDJSON). Allowing the client to process the submissions
            one by one as they arrive.

            The raw input submitted by the student (file contents, code, QCM answers, etc.) is not included in this
            list. Use the dedicated endpoint for retrieving inputs (accessible to staff members or to the authors) to
            download the raw input of one particular submission.

            This endpoint takes a JSON body with the mandatory field "username", a list of usernames to filter the submissions.
            Only submissions from those users will be returned.
        """

        username = flask.g.user.username

        try:
            course = Course.get(courseid)
        except:
            self._logger.warning("Course %r not found", courseid)
            raise APINotFound()

        data = flask.request.get_json(silent=True)
        if data is None:
            raise APIInvalidArguments()

        usernames = data.get("usernames")
        if not isinstance(usernames, list):
            raise APIInvalidArguments()

        if not self.user_manager.has_staff_rights_on_course(course, username, include_superadmins=True) and not set(usernames) == {username}:
            self._logger.warning("User %r tried accessing submissions of other users in course %r", username, courseid)
            raise APINotFound()

        try:
            _ = course.get_task(taskid) if taskid else None
        except:
            self._logger.warning("Task %r not found", taskid)
            raise APINotFound()

        tasks = [taskid] if taskid else None

        submissions, _ = self.submission_manager.get_selected_submissions_queryset(
            course, only_tasks=tasks, only_users=usernames,
            keep_only_evaluation_submissions=True
        )

        def generate():
            for s in submissions.exclude("user_ip", "status"):
                yield s.to_json() + "\n"

        return flask.Response(
            generate(),
            mimetype="application/x-ndjson",
            headers={
                "X-Total-Count": str(submissions.count()),
            },
        )


class APISubmissionInputV1(APIAuthenticatedPageV1):
    """
        Endpoint
          ::

            /api/v1/submissions/<submissionid>/input

    """

    def GET(self, submissionid):
        """
            Returns the raw input of a submission, formatted as a BSON binary.
            Accessible to any author of the submission, or to a staff member of the course.

            The input is formatted as follows, with additional metadata and the different problems' input :
            {
                "@username" : "user1",
                "@email" : "user1@email.com",
                "@lang" : "en",
                "@time": "2026-06-23 15:01:44.706579+00:00",
                "@attempts": "5",
                "@random": [],
                "@state": "",

                "code_problem": "print(\"Hello world!\")",
                "file_problem": {
                    "filename": "file1.zip",
                    "value": "sDBBQAVcbcAWpn2wFoAQAAYi9maXp6YnV6e......DQAH4NsBagbcAWrg2wFqdXgLAAEE6AMAAAToAwAAUEsFBgAAAAAEAAQAVgEAAEACAAAAAA=="
                    },
                "qcm_problem": {
                    # number of the selected answer for each question, starting from 0.
                    "qcm1": "0",
                    "qcm2": "2",
                    "qcm3": "1",
                    ...
            }

            Returns 200 OK with the raw input as a BSON binary if the submission exists and the user is allowed to access it.
            Returns 404 Not Found if the submission does not exist or if the user is not allowed to access it.

        """

        username = flask.g.user.username

        try:
            submission = self.submission_manager.get_submission(submissionid)
        except:
            self.logger.info("Submission %r not found", submissionid)
            raise APINotFound()

        course = Course.get(submission.courseid)
        is_staff = self.user_manager.has_staff_rights_on_course(course, username, include_superadmins=True)
        is_owner = username in submission.username
        if not (is_staff or is_owner):
            self.logger.warning("User %r is nor the owner, nor a staff member for submission %r", username, submissionid)
            raise APINotFound()

        grid_file = submission.input

        def generate(chunk_size):
            grid_file.seek(0)
            while chunk := grid_file.read(chunk_size):
                yield chunk

        response = flask.Response(generate(chunk_size= 2 * 1024 * 1024), content_type="application/octet-stream")
        response.headers["Content-Length"] = str(grid_file.length)

        return response

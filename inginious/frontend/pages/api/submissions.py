# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Submissions """

import base64
import flask
import json
import csv
import io
from bson import json_util

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


class APISubmissionsCourse(APITokenAuthPage):

    @staticmethod
    def _to_csv_response(submissions_list):
        """
            Flattens a list of serialized submissions (as produced by `serialize`) into a CSV file.
            Since the "input" field's structure varies per task (and even per problem type within
            a task), the set of CSV columns is computed dynamically as the union of all input keys
            found across the submissions, prefixed with "input.".
        """

        base_fields = ["courseid", "taskid", "username", "submitted_on", "result", "grade", "stderr", "stdout"]

        # Collect the union of all "input" keys across submissions, to build stable CSV columns.
        input_fields = []
        seen_input_fields = set()
        for s in submissions_list:
            for key in s.get("input", {}).keys():
                if key not in seen_input_fields:
                    seen_input_fields.add(key)
                    input_fields.append(key)

        fieldnames = base_fields + ["input." + f for f in input_fields]

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        def stringify(value):
            # Lists, dicts, and nested structures (e.g. file_problem, qcm_problem, @random)
            # are serialized as JSON strings so they fit into a single CSV cell.
            if isinstance(value, (list, dict)):
                return json.dumps(value)
            if value is None:
                return ""
            return value

        for s in submissions_list:
            row = {field: stringify(s.get(field)) for field in base_fields}
            row["username"] = ",".join(s.get("username", []))

            input_data = s.get("input", {})
            for key in input_fields:
                row["input." + key] = stringify(input_data.get(key))

            writer.writerow(row)

        csv_data = buffer.getvalue()
        buffer.close()

        return csv_data


    def API_POST(self, courseid, taskid
    =None):
        """
            List all the submissions from a course that were evaluated (done). Or all submissions for a particular task in case a task id is given.
            # TODO : have two different docs ?How to display them separately in the documentation ?
            Only accessible to staff members of the course.
            Returns a 200 OK if the endpoint is reachable and the user has access to it.
            Returns 403 Forbidden if the user does not have access to the course/task.
            Returns 404 Not Found if the course does not exist.

            Returns list of the form :
            ::

                [
                    {
                        "courseid": "submission_id1",
                        "taskid": "date",
                        "username" : ["user1", "user2", ...],          #list of users related to that submissions (multiple users in case of a group submission)
                        "submitted_on": "2026-06-23T15:01:44Z",     #date in the ISO 8601 format
                        "result" : "success"        #can be success, failure, crash (execution status of the task).
                        "grade": 0.0,
                        "stderr": "stderr output of the submission",
                        "stdout": "stdout output of the submission",
                        "input": {  #input data from the submission, additional info and input submitted by the student.
                            "@username" : "user1",
                            "@email" : "user1@email.com",
                            "@lang" : "en",
                            "@time": "2026-06-23 15:01:44.706579+00:00",
                            "@attempts": "5",
                            "@random": [],
                            "@state": "",
                            ...
                        },
                    }
                ]

            The input field also contains the inputs of the student for all problems of the task. File contents are encoded in base64.
             The structure depends on the type of the problem :


                {
                    "code_problem": ""print(\"Hello world!\")"",
                    "file_problem": {
                        "filename": "file1.zip",
                        "value": "sDBBQAVcbcAWpn2wFoAQAAYi9maXp6YnV6e......DQAH4NsBagbcAWrg2wFqdXgLAAEE6AMAAAToAwAAUEsFBgAAAAAEAAQAVgEAAEACAAAAAA=="
                        },
                    "qcm_problem": {
                    ... # TODO
                    }

            This endpoint takes a token in the header (accessible from your account settings) and a JSON body with the following fields :
            - select: "all" (default), "best", "last" : select all submissions, the best submission per student, or the last submission per student
            - username: a list of usernames to filter the submissions. If none is provided (or it is empty), the submissions for all users are returned
            - format: "json" (default), "csv" : format of the response.

            example of a call to this endpoint using curl: :
                curl -X POST "http://localhost:8080/api/v0/token/courses/tutorial/submissions"
                -H "Authorization: Bearer <token>"
                -H "Content-Type: application/json"  -d '{ "select": "last", "format": "json", "username" : ["user1"] }'

        """

        username = self.user.username

        try:
            course = Course.get(courseid)
        except:
            raise APINotFound("Course not found")
        try:
            _ = course.get_task(taskid) if taskid else None
        except:
            raise APINotFound("Task not found")

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

        query = {"courseid": courseid, "status": "done"} if taskid is None else {"courseid": courseid, "taskid": taskid, "status": "done"}
        if usernames:
            query["username__in"] = usernames

        if select == "best":
            submissions = Submission.objects(**query) \
                .only("courseid", "taskid", "username", "submitted_on", "result", "grade", "stderr", "stdout", "input") \
                .order_by("-grade", "-submitted_on")
        else:  # select == "last" or select == "all"
            submissions = Submission.objects(**query) \
                .only("courseid", "taskid", "username", "submitted_on", "result", "grade", "stderr", "stdout", "input") \
                .order_by("-submitted_on")

        if select in ("best", "last"):
            seen = set()
            result = []
            for s in submissions:
                key = (tuple(sorted(s.username)), s.taskid)
                if key not in seen:
                    seen.add(key)
                    result.append(s)
            submissions = result

        def serialize(s):
            return {
                "courseid": s.courseid,
                "taskid": s.taskid,
                "username": s.username,
                "submitted_on": s.submitted_on.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "result": s.result,
                "grade": s.grade,
                "stderr": s.stderr,
                "stdout": s.stdout,
                "input": json.loads(json_util.dumps(s.get_input())),
            }

        submissions_list = [serialize(s) for s in submissions]

        if response_format == "csv":
            return 200, self._to_csv_response(submissions_list)

        return 200, submissions_list


    # send back text feedback ? -> text sent back to the student after submitting its work, not the feedback sent back by the grader
    # send back submission id ?

    # filter on date range ?


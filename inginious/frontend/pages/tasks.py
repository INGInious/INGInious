# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Task page """
import json
import mimetypes
import posixpath
import urllib.error
import urllib.parse
import urllib.request
import random
import time
import flask

from flask import redirect, Response
from werkzeug.exceptions import NotFound, HTTPException
from bson.objectid import ObjectId
from pymongo import ReturnDocument

from inginious.common.exceptions import TaskNotFoundException, CourseNotFoundException
from inginious.frontend.pages.course import handle_course_unavailable
from inginious.frontend.pages.utils import INGIniousPage, INGIniousAuthPage


class BaseTaskPage(object):
    """ Display a task (and allow to reload old submission/file uploaded during a submission) """

    def __init__(self, calling_page):
        self.cp = calling_page
        self.submission_manager = self.cp.submission_manager
        self.user_manager = self.cp.user_manager
        self.database = self.cp.database
        self.course_factory = self.cp.course_factory
        self.template_helper = self.cp.template_helper
        self.default_allowed_file_extensions = self.cp.default_allowed_file_extensions
        self.default_max_file_size = self.cp.default_max_file_size
        self.webterm_link = self.cp.webterm_link
        self.plugin_manager = self.cp.plugin_manager

    def preview_allowed(self, courseid, taskid):
        try:
            course = self.course_factory.get_course(courseid)
        except CourseNotFoundException as ex:
            raise NotFound(description=str(ex))
        return course.get_accessibility().is_open() and course.allow_preview()

    def GET(self, courseid, taskid, is_LTI):
        """ GET request """
        username = self.user_manager.session_username()

        # Fetch the course
        try:
            course = self.course_factory.get_course(courseid)
        except CourseNotFoundException as ex:
            raise NotFound(description=str(ex))

        if is_LTI and not self.user_manager.course_is_user_registered(course):
            self.user_manager.course_register_user(course, force=True)

        if not self.user_manager.course_is_open_to_user(course, username, is_LTI):
            return handle_course_unavailable(self.cp.app.get_homepath(), self.template_helper, self.user_manager, course)

        is_staff = self.user_manager.has_staff_rights_on_course(course, username)

        try:
            task = course.get_task(taskid)
            if not self.user_manager.task_is_visible_by_user(task, username, is_LTI):
                return self.template_helper.render("task_unavailable.html")
        except TaskNotFoundException:
            raise NotFound()

        task_dispenser = course.get_task_dispenser()
        user_task_list = task_dispenser.get_user_task_list([username])[username]
        ordered_task_list = [taskid for taskid in task_dispenser.get_ordered_tasks() if taskid in user_task_list]

        if taskid not in user_task_list:
            previous_taskid = None
            next_taskid = None
        else:
            # Compute previous and next taskid
            index = ordered_task_list.index(taskid)
            previous_taskid = ordered_task_list[index - 1] if index > 0 else None
            next_taskid = ordered_task_list[index + 1] if index < len(ordered_task_list) - 1 else None

        self.user_manager.user_saw_task(username, courseid, taskid)

        is_staff = self.user_manager.has_staff_rights_on_course(course, username)

        userinput = flask.request.args
        if "submissionid" in userinput and "questionid" in userinput:
            # Download a previously submitted file
            submission = self.submission_manager.get_submission(userinput["submissionid"], user_check=not is_staff)
            if submission is None:
                raise self.cp.app.notfound(message=_("Submission doesn't exist."))
            sinput = self.submission_manager.get_input_from_submission(submission, True)
            if userinput["questionid"] not in sinput:
                raise NotFound()

            if isinstance(sinput[userinput["questionid"]], dict):
                # File uploaded previously
                mimetypes.init()
                mime_type = mimetypes.guess_type(urllib.request.pathname2url(sinput[userinput["questionid"]]['filename']))
                return Response(response=sinput[userinput["questionid"]]['value'], content_type=mime_type[0])
            else:
                # Other file, download it as text
                return Response(response=sinput[userinput["questionid"]], content_type='text/plain')
        else:
            # Generate random inputs and save it into db
            random.seed(str(username if username is not None else "") + taskid + courseid + str(
                time.time() if task.regenerate_input_random() else ""))
            random_input_list = [random.random() for i in range(task.get_number_input_random())]

            user_task = self.database.user_tasks.find_one_and_update(
                {
                    "courseid": task.get_course_id(),
                    "taskid": task.get_id(),
                    "username": self.user_manager.session_username()
                },
                {
                    "$set": {"random": random_input_list}
                },
                return_document=ReturnDocument.AFTER
            )

            submissionid = user_task.get('submissionid', None)
            eval_submission = self.database.submissions.find_one({'_id': ObjectId(submissionid)}) if submissionid else None

            students = [self.user_manager.session_username()]
            if course.get_task_dispenser().get_group_submission(taskid) and not self.user_manager.has_admin_rights_on_course(course, username):
                group = self.database.groups.find_one({"courseid": task.get_course_id(),
                                                     "students": self.user_manager.session_username()})
                if group is not None:
                    students = group["students"]
                # we don't care for the other case, as the student won't be able to submit.

            submissions = self.submission_manager.get_user_submissions(task) if self.user_manager.session_logged_in() else []
            user_info = self.user_manager.get_user_info(username)

            # Visible tags
            course_tags = course.get_tags()
            visible_tags = [tags for _,tags in course_tags.items() if
                tags.is_visible_for_student() or self.user_manager.has_staff_rights_on_course(course)]

            # Problem dict
            pdict = {problem.get_id(): problem.get_type() for problem in task.get_problems()}
            is_input_list = {problem.get_id():  1 if problem.input_type() == list else 0 for problem in task.get_problems()}

            # Display the task itself
            return self.template_helper.render("task.html", user_info=user_info, course=course, task=task,
                                               submissions=submissions, students=students,
                                               eval_submission=eval_submission, user_task=user_task,
                                               previous_taskid=previous_taskid, next_taskid=next_taskid,
                                               webterm_link=self.webterm_link, input_random_list=random_input_list,
                                               visible_tags=visible_tags, pdict=pdict, is_input_list=is_input_list)

    def POST(self, courseid, taskid, isLTI):
        """ POST a new submission """
        username = self.user_manager.session_username()

        course = self.course_factory.get_course(courseid)
        if not self.user_manager.course_is_open_to_user(course, username, isLTI):
            return handle_course_unavailable(self.cp.app.get_homepath(), self.template_helper, self.user_manager, course)

        is_staff = self.user_manager.has_staff_rights_on_course(course, username)
        is_admin = self.user_manager.has_admin_rights_on_course(course, username)

        task = course.get_task(taskid)
        if not self.user_manager.task_is_visible_by_user(task, username, isLTI):
            return self.template_helper.render("task_unavailable.html")

        self.user_manager.user_saw_task(username, courseid, taskid)

        userinput = flask.request.form
        if "@action" in userinput and userinput["@action"] == "submit":
            # Verify rights
            if not self.user_manager.task_can_user_submit(task, username, lti=isLTI):
                return json.dumps({"status": "error", "title": _("Error"), "text": _("You are not allowed to submit for this task.")})

            # Retrieve input random and check still valid
            random_input = self.database.user_tasks.find_one({"courseid": task.get_course_id(), "taskid": task.get_id(), "username": username}, { "random": 1 })
            random_input = random_input["random"] if "random" in random_input else []
            for i in range(0, len(random_input)):
                s = "@random_" + str(i)
                if s not in userinput or float(userinput[s]) != random_input[i]:
                    return json.dumps({"status": "error", "title": _("Error"), "text": _("Your task has been regenerated. This current task is outdated.")})

            # Reparse user input with array for multiple choices and files
            task_input = {}
            for problem in task.get_problems():
                pid = problem.get_id()
                if problem.input_type() == list:
                    task_input[pid] = flask.request.form.getlist(pid)
                elif problem.input_type() == dict:
                    task_input[pid] = flask.request.files.get(pid)
                else:
                    task_input[pid] = flask.request.form.get(pid)

            task_input = task.adapt_input_for_backend(task_input)

            if not task.input_is_consistent(task_input, self.default_allowed_file_extensions, self.default_max_file_size):
                return Response(content_type='application/json',
                                response=json.dumps({
                                    "status": "error",  "title": _("Error"),
                                    "text": _("Please answer to all the questions and verify the extensions of the files "
                                              "you want to upload. Your responses were not tested.")
                                }))

            # Get debug info if the current user is an admin
            debug = is_admin
            if "@debug-mode" in userinput:
                if userinput["@debug-mode"] == "ssh" and debug:
                    debug = "ssh"

            # Start the submission
            try:
                submissionid, oldsubids = self.submission_manager.add_job(task, task_input, course.get_task_dispenser(), debug)
                return Response(content_type='application/json', response=json.dumps({
                    "status": "ok", "submissionid": str(submissionid), "remove": oldsubids,
                    "text": _("<b>Your submission has been sent...</b>")
                }))
            except Exception as ex:
                return Response(content_type='application/json', response=json.dumps({
                    "status": "error", "title": _("Error"), "text": str(ex)
                }))

        elif "@action" in userinput and userinput["@action"] == "check" and "submissionid" in userinput:
            result = self.submission_manager.get_submission(userinput['submissionid'], user_check=not is_staff)
            if result is None:
                return Response(content_type='application/json', response=json.dumps({
                    'status': "error",  "title": _("Error"), "text": _("Internal error")
                }))
            elif self.submission_manager.is_done(result, user_check=not is_staff):
                result = self.submission_manager.get_input_from_submission(result)
                result = self.submission_manager.get_feedback_from_submission(result, show_everything=is_staff)

                # user_task always exists as we called user_saw_task before
                user_task = self.database.user_tasks.find_one({
                    "courseid":task.get_course_id(),
                    "taskid": task.get_id(),
                    "username": {"$in": result["username"]}
                })

                default_submissionid = user_task.get('submissionid', None)
                if default_submissionid is None:
                    # This should never happen, as user_manager.update_user_stats is called whenever a submission is done.
                    return Response(content_type='application/json', response=json.dumps({
                        'status': "error",  "title": _("Error"), "text": _("Internal error")
                    }))

                return Response(content_type='application/json', response=self.submission_to_json(
                    task, result, is_admin, False, default_submissionid == result['_id'], tags=course.get_tags()
                ))
            else:
                return Response(content_type='application/json', response=self.submission_to_json(
                    task, result, is_admin, False, tags=course.get_tags()
                ))

        elif "@action" in userinput and userinput["@action"] == "load_submission_input" and "submissionid" in userinput:
            submission = self.submission_manager.get_submission(userinput["submissionid"], user_check=not is_staff)
            submission = self.submission_manager.get_input_from_submission(submission)
            submission = self.submission_manager.get_feedback_from_submission(submission, show_everything=is_staff)
            if not submission:
                raise NotFound(description=_("Submission doesn't exist."))

            return Response(content_type='application/json', response=self.submission_to_json(
                task, submission, is_admin, True, tags=course.get_tags()
            ))

        elif "@action" in userinput and userinput["@action"] == "kill" and "submissionid" in userinput:
            self.submission_manager.kill_running_submission(userinput["submissionid"])  # ignore return value
            return Response(content_type='application/json', response=json.dumps({'status': 'done'}))
        else:
            raise NotFound()

    def submission_to_json(self, task, data, debug, reloading=False, replace=False, tags=None):
        """ Converts a submission to json (keeps only needed fields) """

        if tags is None:
            tags = []

        if "ssh_host" in data:
            return json.dumps({
                'status': "waiting",
                'text': "<b>SSH server active</b>",
                'ssh_host': data["ssh_host"],
                'ssh_port': data["ssh_port"],
                'ssh_user': data["ssh_user"],
                'ssh_password': data["ssh_password"]
            })

        # Here we are waiting. Let's send some useful information.
        waiting_data = self.submission_manager.get_job_queue_info(data["jobid"]) if "jobid" in data else None
        if waiting_data is not None and not reloading:
            nb_tasks_before, approx_wait_time = waiting_data
            wait_time = round(approx_wait_time)
            if nb_tasks_before == -1 and wait_time <= 0:
                text = _("<b>INGInious is currently grading your answers.</b> (almost done)")
            elif nb_tasks_before == -1:
                text = _("<b>INGInious is currently grading your answers.</b> (Approx. wait time: {} seconds)").format(
                    wait_time)
            elif nb_tasks_before == 0:
                text = _("<b>You are next in the waiting queue!</b>")
            elif nb_tasks_before == 1:
                text = _("<b>There is one task in front of you in the waiting queue.</b>")
            else:
                text = _("<b>There are {} tasks in front of you in the waiting queue.</b>").format(nb_tasks_before)

            return json.dumps({'status': "waiting", 'text': text})

        tojson = {
            'status': data['status'],
            'result': data.get('result', 'crash'),
            'id': str(data["_id"]),
            'submitted_on': str(data['submitted_on']),
            'grade': str(data.get("grade", 0.0)),
            'replace': replace and not reloading  # Replace the evaluated submission
        }

        if "text" in data:
            tojson["text"] = data["text"]
        if "problems" in data:
            tojson["problems"] = data["problems"]

        if debug:
            tojson["debug"] = self._cut_long_chains(data)

        if tojson['status'] == 'waiting':
            tojson["title"] = _("<b>Your submission has been sent...</b>")
        elif tojson["result"] == "failed":
            tojson["title"] = _("There are some errors in your answer. Your score is {score}%.").format(score=data["grade"])
        elif tojson["result"] == "success":
            tojson["title"] = _("Your answer passed the tests! Your score is {score}%.").format(score=data["grade"])
        elif tojson["result"] == "timeout":
            tojson["title"] = _("Your submission timed out. Your score is {score}%.").format(score=data["grade"])
        elif tojson["result"] == "overflow":
            tojson["title"] = _("Your submission made an overflow. Your score is {score}%.").format(score=data["grade"])
        elif tojson["result"] == "killed":
            tojson["title"] = _("Your submission was killed.")
        else:
            tojson["title"] = _("An internal error occurred. Please retry later. "
                                "If the error persists, send an email to the course administrator.")

        tojson["title"] += " " + _("[Submission #{submissionid} (<b>{submissionDate}</b>)]").format(submissionid=data["_id"], submissionDate=data["submitted_on"].strftime("%Y-%m-%d %H:%M:%S"))
        tojson["title"] = self.plugin_manager.call_hook_recursive("feedback_title", task=task, submission=data, title=tojson["title"])["title"]
        
        tojson["text"] = data.get("text", "")
        tojson["text"] = self.plugin_manager.call_hook_recursive("feedback_text", task=task, submission=data, text=tojson["text"])["text"]

        if reloading:
            # Set status='ok' because we are reloading an old submission.
            tojson["status"] = 'ok'
            # And also include input
            tojson["input"] = data.get('input', {})

        if "tests" in data:
            tojson["tests"] = {}
            for key, tag in tags.items():  # Tags only visible for admins should not appear in the json for students.
                if tag.get_type() in [0, 1] and (tag.is_visible_for_student() or debug) and key in data["tests"]:
                    tojson["tests"][key] = data["tests"][key]
            if debug: #We add also auto tags when we are admin
                for tag in data["tests"]:
                    if tag.startswith("*auto-tag-"):
                        tojson["tests"][tag] = data["tests"][tag]

        # allow plugins to insert javascript to be run in the browser after the submission is loaded
        tojson["feedback_script"] = "".join(self.plugin_manager.call_hook("feedback_script", task=task, submission=data))

        return json.dumps(tojson, default=str)

    def _cut_long_chains(self, data, limit=1000):
        """ Cut all strings and byte chains in a dictionary
            if they exceed a limit in characters or bytes """

        if isinstance(data, dict):
            new_data = {}
            for key, value in data.items():
                if isinstance(value, bytes) and len(value) > limit:
                    new_data[key] = value[:limit] + _(" <truncated>").encode("utf-8")
                elif isinstance(value, str) and len(value) > limit:
                    new_data[key] = value[:limit] + _(" <truncated>")
                elif isinstance(value, dict):
                    new_data[key] = self._cut_long_chains(value)
                else:
                    new_data[key] = value
            return new_data
        return data


class TaskPageStaticDownload(INGIniousPage):
    """ Allow to download files stored in the task folder """

    def is_lti_page(self):
        # authorize LTI sessions to download static files
        return True

    def GET(self, courseid, taskid, path):  # pylint: disable=arguments-differ
        """ GET request """
        try:
            course = self.course_factory.get_course(courseid)
            if not self.user_manager.course_is_open_to_user(course):
                return handle_course_unavailable(self.app.get_homepath(), self.template_helper, self.user_manager, course)

            path_norm = posixpath.normpath(urllib.parse.unquote(path))

            if taskid == "$common":
                public_folder = course.get_fs().from_subfolder("$common").from_subfolder("public")
            else:

                task = course.get_task(taskid)
                if not self.user_manager.task_is_visible_by_user(task):  # ignore LTI check here
                    return self.template_helper.render("task_unavailable.html")

                public_folder = task.get_fs().from_subfolder("public")
            (method, mimetype_or_none, file_or_url) = public_folder.distribute(path_norm, False)

            if method == "local":
                return Response(response=file_or_url, content_type=mimetype_or_none)
            elif method == "url":
                return redirect(file_or_url)
            else:
                raise NotFound()
        except TaskNotFoundException:
            raise NotFound()
        except HTTPException as error_or_redirect:
            raise error_or_redirect


class TaskPage(INGIniousAuthPage):
    def GET_AUTH(self, courseid, taskid):
        return BaseTaskPage(self).GET(courseid, taskid, False)

    def POST_AUTH(self, courseid, taskid):
        return BaseTaskPage(self).POST(courseid, taskid, False)

    def preview_allowed(self, courseid, taskid):
        return BaseTaskPage(self).preview_allowed(courseid, taskid)

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import json
import logging
from flask import request, Response, render_template
from werkzeug.exceptions import NotFound, Forbidden

from inginious.frontend.pages.course_admin.utils import make_csv, INGIniousSubmissionsAdminPage
from inginious.frontend.models import Submission

class CourseSubmissionsPage(INGIniousSubmissionsAdminPage):
    """ Page that allow search, view, replay an download of submisssions done by students """
    _logger = logging.getLogger("inginious.webapp.submissions")

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course, __ = self.get_course_and_check_rights(courseid)
        msgs = []

        user_input = request.form.copy()
        user_input["users"] = request.form.getlist("users")
        user_input["audiences"] = request.form.getlist("audiences")
        user_input["tasks"] = request.form.getlist("tasks")
        user_input["org_categories"] = request.form.getlist("org_categories")

        if "replay_submission" in user_input:
            # Replay a unique submission
            submission = Submission.objects(id=user_input["replay_submission"]).first()
            if submission is None:
                raise NotFound(description=_("This submission doesn't exist."))

            self.submission_manager.replay_job(course, course.get_task(submission["taskid"]), submission, course.get_task_dispenser())
            return Response(response=json.dumps({"status": "waiting"}), content_type='application/json')

        elif "csv" in user_input or "download" in user_input or "replay" in user_input:
            best_only = "eval_dl" in user_input and "download" in user_input
            params = self.get_input_params(json.loads(user_input.get("displayed_selection", "")), course)
            data = self.submissions_from_user_input(course, params, msgs, best_only=best_only)

            if "csv" in user_input:
                return make_csv(data)

            elif "download" in user_input:
                download_type = user_input.get("download_type", "")
                if download_type not in ["taskid/username", "taskid/audience", "username/taskid", "audience/taskid"]:
                    download_type = "taskid/username"
                if (best_only or "eval" in params) and "simplify" in user_input:
                    sub_folders = list(download_type.split('/'))
                else:
                    sub_folders = list(download_type.split('/')) + ["submissiondateid"]
                archive, error = self.submission_manager.get_submission_archive(course, data, sub_folders, simplify="simplify" in user_input)
                if not error:
                    response = Response(response=archive, content_type='application/x-gzip')
                    response.headers['Content-Disposition'] = 'attachment; filename="submissions.tgz"'
                    return response
                else:
                    msgs.append(_("The following submission could not be prepared for download: {}").format(error))
                    return self.page(course, params, msgs=msgs)

            elif "replay" in user_input:
                if not self.user_manager.has_admin_rights_on_course(course):
                    raise Forbidden(description=_("You don't have admin rights on this course."))

                tasks = course.get_tasks()
                for submission in data:
                    self.submission_manager.replay_job(course, tasks[submission["taskid"]], submission, course.get_task_dispenser())
                msgs.append(_("{0} selected submissions were set for replay.").format(str(len(data))))
                return self.page(course, params, msgs=msgs)

        elif "page" in user_input:
            params = self.get_input_params(json.loads(user_input["displayed_selection"]), course)
            try:
                page = int(user_input["page"])
            except TypeError:
                page = 1
            return self.page(course, params, page=page, msgs=msgs)
        else:
            params = self.get_input_params(user_input, course)
            return self.page(course, params, msgs=msgs)

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course, __ = self.get_course_and_check_rights(courseid)

        user_input = request.args.copy()
        user_input["users"] = request.args.getlist("users")
        user_input["audiences"] = request.args.getlist("audiences")
        user_input["tasks"] = request.args.getlist("tasks")
        user_input["org_categories"] = request.args.getlist("org_categories")

        if "download_submission" in user_input:
            submission = Submission.objects(
                id=user_input["download_submission"],courseid=course.get_id(), status__in=["done", "error"]
            ).first()

            if submission is None:
                raise NotFound(description=_("The submission doesn't exist."))

            self._logger.info("Downloading submission %s - %s - %s - %s", submission.id, submission['courseid'],
                              submission['taskid'], submission['username'])
            archive, error = self.submission_manager.get_submission_archive(course, [submission], [])
            if not error:
                response = Response(response=archive, content_type='application/x-gzip')
                response.headers['Content-Disposition'] = 'attachment; filename="submissions.tgz"'
                return response

        params = self.get_input_params(user_input, course)
        return self.page(course, params)

    def page(self, course, params, page=1, msgs=None):
        """ Get all data and display the page """
        msgs = msgs if msgs else []

        users, tutored_users, audiences, tutored_audiences, tasks, limit = self.get_course_params(course, params)

        data, sub_count, pages = self.submissions_from_user_input(course, params, msgs, page, limit)

        return render_template("course_admin/submissions.html", course=course, users=users,
                                           tutored_users=tutored_users, audiences=audiences,
                                           tutored_audiences=tutored_audiences, tasks=tasks, old_params=params,
                                           data=data, displayed_selection=json.dumps(params),
                                           number_of_pages=pages, page_number=page, msgs=msgs, sub_count = sub_count)

    def submissions_from_user_input(self, course, user_input, msgs, page=None, limit=None, best_only=False):
        """ Returns the list of submissions and corresponding aggragations based on inputs """

        submit_time_between = [None, None]
        try:
            if user_input.get('date_before', ''):
                submit_time_between[1] = user_input["date_before"]
            if user_input.get('date_after', ''):
                submit_time_between[0] = user_input["date_after"]
        except ValueError:  # If match of datetime.strptime() fails
            msgs.append(_("Invalid dates"))

        must_keep_best_submissions_only = "eval" in user_input or best_only

        skip = None
        if page and limit:
            skip = (page-1) * limit

        return self.submission_manager.get_selected_submissions(course, only_tasks=user_input["tasks"],
                                             only_tasks_with_categories=user_input["org_categories"],
                                             only_users=user_input["users"],
                                             only_audiences=user_input["audiences"],
                                             grade_between=[
                                                 float(user_input["grade_min"]) if user_input.get('grade_min', '') else None,
                                                 float(user_input["grade_max"]) if user_input.get('grade_max', '') else None
                                             ],
                                             submit_time_between=submit_time_between,
                                             keep_only_evaluation_submissions=must_keep_best_submissions_only,
                                             keep_only_crashes="crashes_only" in user_input,
                                             sort_by=(user_input.get('sort_by', 'submitted_on'), user_input.get('order', 0) == 1),
                                             limit=limit,
                                             skip=skip)

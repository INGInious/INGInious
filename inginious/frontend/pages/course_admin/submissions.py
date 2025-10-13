# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import json
import logging
import pymongo
import flask
from bson import ObjectId
from flask import Response
from werkzeug.exceptions import NotFound, Forbidden

from inginious.frontend.pages.course_admin.utils import make_csv, INGIniousSubmissionsAdminPage


class CourseSubmissionsPage(INGIniousSubmissionsAdminPage):
    """ Page that allow search, view, replay an download of submisssions done by students """
    _logger = logging.getLogger("inginious.webapp.submissions")

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course, __ = self.get_course_and_check_rights(courseid)
        msgs = []

        user_input = flask.request.form.copy()
        user_input["users"] = flask.request.form.getlist("users")
        user_input["audiences"] = flask.request.form.getlist("audiences")
        user_input["tasks"] = flask.request.form.getlist("tasks")
        user_input["org_categories"] = flask.request.form.getlist("org_categories")

        if "replay_submission" in user_input:
            # Replay a unique submission
            submission = self.database.submissions.find_one({"_id": ObjectId(user_input["replay_submission"])})
            if submission is None:
                raise NotFound(description=_("This submission doesn't exist."))

            self.submission_manager.replay_job(course.get_task(submission["taskid"]), submission, course.get_task_dispenser())
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
                    self.submission_manager.replay_job(tasks[submission["taskid"]], submission, course.get_task_dispenser())
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

        user_input = flask.request.args.copy()
        user_input["users"] = flask.request.args.getlist("users")
        user_input["audiences"] = flask.request.args.getlist("audiences")
        user_input["tasks"] = flask.request.args.getlist("tasks")
        user_input["org_categories"] = flask.request.args.getlist("org_categories")

        if "download_submission" in user_input:
            submission = self.database.submissions.find_one({"_id": ObjectId(user_input["download_submission"]),
                                                             "courseid": course.get_id(),
                                                             "status": {"$in": ["done", "error"]}})
            if submission is None:
                raise NotFound(description=_("The submission doesn't exist."))

            self._logger.info("Downloading submission %s - %s - %s - %s", submission['_id'], submission['courseid'],
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

        return self.template_helper.render("course_admin/submissions.html", course=course, users=users,
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

        return self.get_selected_submissions(course, only_tasks=user_input["tasks"],
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

    def get_selected_submissions(self, course,
                                 only_tasks=None, only_tasks_with_categories=None,
                                 only_users=None, only_audiences=None,
                                 with_tags=None,
                                 grade_between=None, submit_time_between=None,
                                 keep_only_evaluation_submissions=False,
                                 keep_only_crashes=False,
                                 sort_by=("submitted_on", True),
                                 limit=None, skip=None):
        """
        All the parameters (excluding course, sort_by and keep_only_evaluation_submissions) can be None.
        If that is the case, they are ignored.

        :param course: the course
        :param only_tasks: a list of task ids. Only submissions on these tasks will be loaded.
        :param only_tasks_with_categories: keep only tasks that have a least one category in common with this list
        :param only_users: a list of usernames. Only submissions from these users will be loaded.
        :param only_audiences: a list of audience ids. Only submissions from users in these will be loaded
        :param with_tags: a list of tags in the form [(tagid, present)], where present is a boolean indicating
               whether the tag MUST be present or MUST NOT be present. If you don't mind if a tag is present or not,
               just do not put it in the list.
        :param grade_between: a tuple of two floating point number or None ([0.0, None], [None, 0.0] or [None, None])
               that indicates bounds on the grade of the retrieved submissions
        :param submit_time_between: a tuple of two dates or None ([datetime, None], [None, datetime] or [None, None])
               that indicates bounds on the submission time of the submission. Format: "%Y-%m-%d %H:%M:%S"
        :param keep_only_evaluation_submissions: True to keep only submissions that are counting for the evaluation
        :param keep_only_crashes: True to keep only submissions that timed out or crashed
        :param sort_by: a tuple (sort_column, ascending) where sort_column is in ["submitted_on", "username", "grade", "taskid"]
               and ascending is either True or False.
        :param limit: an integer representing the maximum number of submission to list.
        :return: a list of submission filling the criterias above.
        """

        filter, best_submissions_list = self.get_submissions_filter(course, only_tasks=only_tasks,
                                                                    only_tasks_with_categories=only_tasks_with_categories,
                                                                    only_users=only_users,
                                                                    only_audiences=only_audiences, with_tags=with_tags,
                                                                    grade_between=grade_between,
                                                                    submit_time_between=submit_time_between,
                                                                    keep_only_evaluation_submissions=keep_only_evaluation_submissions,
                                                                    keep_only_crashes=keep_only_crashes)

        submissions = self.database.submissions.find(filter)
        submissions_count = self.database.submissions.count_documents(filter)

        if sort_by[0] not in ["submitted_on", "username", "grade", "taskid"]:
            sort_by[0] = "submitted_on"
        submissions = submissions.sort(sort_by[0], pymongo.ASCENDING if sort_by[1] else pymongo.DESCENDING)

        if skip is not None and skip < submissions_count:
            submissions.skip(skip)

        if limit is not None:
            submissions.limit(limit)

        out = list(submissions)

        for d in out:
            d["best"] = d["_id"] in best_submissions_list  # mark best submissions

        if limit is not None:
            number_of_pages = max(submissions_count // limit + (submissions_count % limit > 0), 1)
            return out, submissions_count, number_of_pages
        else:
            return out

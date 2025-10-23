# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Utilities for administration pages """

import codecs
import csv
import io
from collections import OrderedDict
from datetime import datetime

from flask import redirect, Response
from werkzeug.exceptions import Forbidden
from bson.objectid import ObjectId

from inginious.common.base import id_checker
from inginious.frontend.courses import Course
from inginious.frontend.pages.utils import INGIniousAuthPage


class INGIniousAdminPage(INGIniousAuthPage):
    """
    An improved version of INGIniousAuthPage that checks rights for the administration
    """

    def get_course_and_check_rights(self, courseid, taskid=None, allow_all_staff=True):
        """ Returns the course with id ``courseid`` and the task with id ``taskid``, and verify the rights of the user.
            Raise app.forbidden() when there is no such course of if the users has not enough rights.
            :param courseid: the course on which to check rights
            :param taskid: If not None, returns also the task with id ``taskid``
            :param allow_all_staff: allow admins AND tutors to see the page. If false, all only admins.
            :returns (Course, Task)
        """

        try:
            course = Course.get(courseid)
            if allow_all_staff:
                if not self.user_manager.has_staff_rights_on_course(course):
                    raise Forbidden(description=_("You don't have staff rights on this course."))
            else:
                if not self.user_manager.has_admin_rights_on_course(course):
                    raise Forbidden(description=_("You don't have admin rights on this course."))

            if taskid is None:
                return course, None
            else:
                return course, course.get_task(taskid)
        except:
            raise Forbidden(description=_("This course is unreachable"))


class INGIniousSubmissionsAdminPage(INGIniousAdminPage):
    """
    An INGIniousAdminPage containing some common methods for querying submissions
    """

    def get_course_params(self, course, params):
        users = self.get_users(course)
        audiences = self.user_manager.get_course_audiences(course)
        tasks = course.get_task_dispenser().get_ordered_tasks()

        tutored_audiences = [str(audience["_id"]) for audience in audiences if
                             self.user_manager.session_username() in audience["tutors"]]
        tutored_users = []
        for audience in audiences:
            if self.user_manager.session_username() in audience["tutors"]:
                tutored_users += audience["students"]

        limit = params.get("limit", 50) if params.get("limit", 50) > 0 else 50

        return users, tutored_users, audiences, tutored_audiences, tasks, limit

    def get_users(self, course):
        user_ids = self.user_manager.get_course_registered_users(course)
        users_info = self.user_manager.get_users_info(user_ids)
        users = {user: users_info[user].realname if users_info[user] else '' for user in user_ids}
        return OrderedDict(sorted(users.items(), key=lambda x: x[1]))

    def get_input_params(self, user_input, course, limit=50):
        users = self.get_users(course)
        audiences = self.user_manager.get_course_audiences(course)
        tasks = course.get_tasks()

        # Sanitise user
        if not user_input.get("users", []) and not user_input.get("audiences", []):
            user_input["users"] = list(users.keys())
        if len(user_input.get("users", [])) == 1 and "," in user_input["users"][0]:
            user_input["users"] = user_input["users"][0].split(',')
        user_input["users"] = [user for user in user_input["users"] if user in users]

        # Sanitise audiences
        if len(user_input.get("audiences", [])) == 1 and "," in user_input["audiences"][0]:
            user_input["audiences"] = user_input["audiences"][0].split(',')
        user_input["audiences"] = [audience for audience in user_input["audiences"] if any(str(a["_id"]) == audience for a in audiences)]

        # Sanitise tasks
        if not user_input.get("tasks", []):
            user_input["tasks"] = list(tasks.keys())
        if len(user_input.get("tasks", [])) == 1 and "," in user_input["tasks"][0]:
            user_input["tasks"] = user_input["tasks"][0].split(',')
        user_input["tasks"] = [task for task in user_input["tasks"] if task in tasks]

        # Sanitise tags
        if not user_input.get("tasks", []):
            user_input["tasks"] = []
        if len(user_input.get("org_categories", [])) == 1 and "," in user_input["org_categories"][0]:
            user_input["org_categories"] = user_input["org_categories"][0].split(',')

        # Sanitise grade
        if "grade_min" in user_input:
            try:
                user_input["grade_min"] = int(user_input["grade_min"])
            except:
                user_input["grade_min"] = ''
        if "grade_max" in user_input:
            try:
                user_input["grade_max"] = int(user_input["grade_max"])
            except:
                user_input["grade_max"] = ''

        # Sanitise order
        if "sort_by" in user_input and user_input["sort_by"] not in ["submitted_on", "username", "grade", "taskid"]:
            user_input["sort_by"] = "submitted_on"
        if "order" in user_input:
            try:
                user_input["order"] = 1 if int(user_input["order"]) == 1 else 0
            except:
                user_input["order"] = 0

        # Sanitise limit
        if "limit" in user_input:
            try:
                user_input["limit"] = int(user_input["limit"])
            except:
                user_input["limit"] = limit

        return user_input

    def _validate_list(self, list_of_ids):
        """ Prevent MongoDB injections by verifying arrays sent to it """
        for i in list_of_ids:
            if not id_checker(i):
                raise Forbidden(description=_("List not valid."))

    def get_submissions_filter(self, course,
                               only_tasks=None, only_tasks_with_categories=None,
                               only_users=None, only_audiences=None,
                               with_tags=None,
                               grade_between=None, submit_time_between=None,
                               keep_only_evaluation_submissions=False,
                               keep_only_crashes=False):
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
        :return: the filter for the mongoDB search.
        """

        # Create the filter for the query. base_filter is used to also filter the collection user_tasks.
        base_filter = {"courseid": course.get_id()}
        filter = {}

        # Tasks (with categories)
        if only_tasks and not only_tasks_with_categories:
            self._validate_list(only_tasks)
            base_filter["taskid"] = {"$in": only_tasks}
        elif only_tasks_with_categories:
            only_tasks_with_categories = set(only_tasks_with_categories)
            more_tasks = {taskid for taskid, task in course.get_tasks().items() if
                          only_tasks_with_categories.intersection(course.get_task_dispenser().get_categories(taskid))}
            if only_tasks:
                self._validate_list(only_tasks)
                more_tasks.intersection_update(only_tasks)
            base_filter["taskid"] = {"$in": list(more_tasks)}

        # Users/audiences
        if only_users and not only_audiences:
            self._validate_list(only_users)
            base_filter["username"] = {"$in": only_users}
        elif only_audiences:
            list_audience_id = [ObjectId(o) for o in only_audiences]
            students = set()
            for audience in self.database.audiences.find({"_id": {"$in": list_audience_id}}):
                students.update(audience["students"])
            if only_users:  # do the intersection
                self._validate_list(only_users)
                students.intersection_update(only_users)
            base_filter["username"] = {"$in": list(students)}

        # Tags
        for tag_id, should_be_present in with_tags or []:
            if id_checker(tag_id):
                filter["tests." + tag_id] = {"$in": [None, False]} if not should_be_present else True

        # Grades
        if grade_between and grade_between[0] is not None:
            filter.setdefault("grade", {})["$gte"] = float(grade_between[0])
        if grade_between and grade_between[1] is not None:
            filter.setdefault("grade", {})["$lte"] = float(grade_between[1])

        # Submit time
        if submit_time_between and submit_time_between[0] is not None:
            filter.setdefault("submitted_on", {})["$gte"] = datetime.fromisoformat(submit_time_between[0])
        if submit_time_between and submit_time_between[1] is not None:
            filter.setdefault("submitted_on", {})["$lte"] = datetime.fromisoformat(submit_time_between[1])

        # Only crashed or timed-out submissions
        if keep_only_crashes:
            filter["result"] = {"$in": ["crash", "timeout"]}

        # Only evaluation submissions
        user_tasks = self.database.user_tasks.find(base_filter)
        best_submissions_list = {user_task['submissionid'] for user_task in user_tasks if
                                 user_task['submissionid'] is not None}

        if keep_only_evaluation_submissions is True:
            filter["_id"] = {"$in": list(best_submissions_list)}

        filter.update(base_filter)

        return filter, best_submissions_list


class UnicodeWriter(object):
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = io.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        """ Writes a row to the CSV file """
        self.writer.writerow(row)
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)
        self.queue.seek(0)

    def writerows(self, rows):
        """ Writes multiple rows to the CSV file """
        for row in rows:
            self.writerow(row)


def make_csv(data):
    """ Returns the content of a CSV file with the data of the dict/list data """
    # Convert sub-dicts to news cols
    for entry in data:
        rval = entry
        if isinstance(data, dict):
            rval = data[entry]
        todel = []
        toadd = {}
        for key, val in rval.items():
            if isinstance(val, dict):
                for key2, val2 in val.items():
                    toadd[str(key) + "[" + str(key2) + "]"] = val2
                todel.append(key)
        for k in todel:
            del rval[k]
        for k, v in toadd.items():
            rval[k] = v

    # Convert everything to CSV
    columns = set()
    output = [[]]
    if isinstance(data, dict):
        output[0].append("id")
        for entry in data:
            for col in data[entry]:
                columns.add(col)
    else:
        for entry in data:
            for col in entry:
                columns.add(col)

    columns = sorted(columns)

    for col in columns:
        output[0].append(col)

    if isinstance(data, dict):
        for entry in data:
            new_output = [str(entry)]
            for col in columns:
                new_output.append(str(data[entry][col]) if col in data[entry] else "")
            output.append(new_output)
    else:
        for entry in data:
            new_output = []
            for col in columns:
                new_output.append(str(entry[col]) if col in entry else "")
            output.append(new_output)

    csv_string = io.StringIO()
    csv_writer = UnicodeWriter(csv_string)
    for row in output:
        csv_writer.writerow(row)
    csv_string.seek(0)
    response = Response(response=csv_string.read(), content_type='text/csv; charset=utf-8')
    response.headers['Content-disposition'] = 'attachment; filename=export.csv'
    return response


class CourseRedirectPage(INGIniousAdminPage):
    """ Redirect admins to /settings and tutors to /task """

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course, __ = self.get_course_and_check_rights(courseid)
        if self.user_manager.session_username() in course.get_tutors():
            return redirect(self.app.get_path("admin", courseid, "tasks"))
        else:
            return redirect(self.app.get_path("admin", courseid, "settings"))

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        return self.GET_AUTH(courseid)

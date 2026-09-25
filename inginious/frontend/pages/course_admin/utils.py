# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Utilities for administration pages """

import codecs
import csv
import io
from collections import OrderedDict

from flask import  session, redirect, Response, url_for
from werkzeug.exceptions import Forbidden

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

        tutored_audiences = [str(audience["id"]) for audience in audiences if
                             session.username in audience["tutors"]]
        tutored_users = []
        for audience in audiences:
            if session.username in audience["tutors"]:
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
        user_input["audiences"] = [audience for audience in user_input["audiences"] if any(str(a["id"]) == audience for a in audiences)]

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
        if session.username in course.get_tutors():
            return redirect(url_for("coursetasklistpage", courseid=courseid))
        else:
            return redirect(url_for("coursesettingspage", courseid=courseid))

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        return self.GET_AUTH(courseid)

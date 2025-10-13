# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import io
import csv
import json

import yaml

import flask
from collections import OrderedDict
from bson import ObjectId
from pymongo import ReturnDocument
from flask import Response
from io import StringIO
from inginious.common import custom_yaml
from inginious.frontend.pages.course_admin.utils import make_csv, INGIniousAdminPage


class CourseStudentListPage(INGIniousAdminPage):
    """ Course administration page: list of registered students """

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course, __ = self.get_course_and_check_rights(courseid)
        if "preferred_field" in flask.request.args and flask.request.args["preferred_field"] in \
                ['username', 'email']:
            preferred_field = flask.request.args["preferred_field"]
            audiences = []
            si = StringIO()
            cw = csv.writer(si)
            for audience in self.user_manager.get_course_audiences(course):
                for student in audience["students"]:
                    field_value = self.get_requested_field_user_info(student, preferred_field)
                    audiences.append([field_value, preferred_field, "student", audience["description"]])
                for tutor in audience["tutors"]:
                    field_value = self.get_requested_field_user_info(tutor, preferred_field)
                    audiences.append([field_value, preferred_field, "tutor", audience["description"]])
            cw.writerows(audiences)

            response = Response(response=si.getvalue(), content_type='text/csv')
            response.headers['Content-Disposition'] = 'attachment; filename="audiences.csv"'
            return response

        if "download_groups" in flask.request.args:
            groups = [{"description": group["description"],
                       "students": group["students"],
                       "size": group["size"],
                       "audiences": [str(c) for c in group["audiences"]]} for group in
                      self.user_manager.get_course_groups(course)]
            response = Response(response=yaml.dump(groups), content_type='text/x-yaml')
            response.headers['Content-Disposition'] = 'attachment; filename="groups.yaml"'
            return response

        return self.page(course, active_tab="tab_audiences" if "audiences" in flask.request.args else "tab_students")

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course, __ = self.get_course_and_check_rights(courseid, None, True)
        data = flask.request.form.copy()
        data["delete"] = flask.request.form.getlist("delete")
        data["groupfile"] = flask.request.files.get("groupfile")
        data["audiencefile"] = flask.request.files.get("audiencefile")
        error = {}
        msg = {}
        active_tab = "tab_students"

        self.post_student_list(course, data)
        active_tab = self.post_audiences(course, data, active_tab, msg, error)
        active_tab = self.post_groups(course, data, active_tab, msg, error)

        return self.page(course, active_tab, msg, error)

    def submission_url_generator_user(self, username):
        """ Generates a submission url """
        return "?format=taskid%2Fusername&users=" + username

    def submission_url_generator_audience(self, audienceid):
        """ Generates a submission url """
        return "?audiences=" + str(audienceid)

    def page(self, course, active_tab="tab_students", msg=None, error=None):
        """ Get all data and display the page """
        if error is None:
            error = {}
        if msg is None:
            msg = {}

        split_audiences, audiences = self.get_audiences_params(course)
        user_data = self.get_student_list_params(course)
        groups = self.user_manager.get_course_groups(course)
        student_list, audience_list, other_students, users_info = self.get_user_lists(course)

        if "csv_audiences" in flask.request.args:
            return make_csv(audiences)
        if "csv_student" in flask.request.args:
            return make_csv(user_data)

        return self.template_helper.render("course_admin/student_list.html", course=course,
                                           user_data=list(user_data.values()), audiences=split_audiences,
                                           active_tab=active_tab, student_list=student_list,
                                           audience_list=audience_list,
                                           other_students=other_students, users_info=users_info, groups=groups,
                                           error=error, msg=msg)

    def get_student_list_params(self, course):
        users = sorted(list(
            self.user_manager.get_users_info(self.user_manager.get_course_registered_users(course, False)).items()),
            key=lambda k: k[1].realname if k[1] is not None else "")

        users = OrderedDict(sorted(list(self.user_manager.get_users_info(course.get_staff()).items()),
                                   key=lambda k: k[1].realname if k[1] is not None else "") + users)

        user_data = OrderedDict([(username, {
            "username": username, "realname": user.realname if user is not None else "",
            "email": user.email if user is not None else "", "total_tasks": 0,
            "task_grades": {"answer": 0, "match": 0}, "task_succeeded": 0, "task_tried": 0, "total_tries": 0,
            "grade": 0, "url": self.submission_url_generator_user(username)}) for username, user in users.items()])

        for username, data in self.user_manager.get_course_caches(list(users.keys()), course).items():
            user_data[username].update(data if data is not None else {})

        return user_data

    def get_audiences_params(self, course):
        audiences = OrderedDict()
        taskids = list(course.get_tasks().keys())

        for audience in self.user_manager.get_course_audiences(course):
            audiences[audience['_id']] = dict(list(audience.items()) +
                                              [("tried", 0),
                                               ("done", 0),
                                               ("url", self.submission_url_generator_audience(audience['_id']))
                                               ])

            data = list(self.database.submissions.aggregate(
                [
                    {
                        "$match":
                            {
                                "courseid": course.get_id(),
                                "taskid": {"$in": taskids},
                                "username": {"$in": audience["students"]}
                            }
                    },
                    {
                        "$group":
                            {
                                "_id": "$taskid",
                                "tried": {"$sum": 1},
                                "done": {"$sum": {"$cond": [{"$eq": ["$result", "success"]}, 1, 0]}}
                            }
                    },

                ]))

            for c in data:
                audiences[audience['_id']]["tried"] += 1 if c["tried"] else 0
                audiences[audience['_id']]["done"] += 1 if c["done"] else 0

        my_audiences, other_audiences = [], []
        for audience in audiences.values():
            if self.user_manager.session_username() in audience["tutors"]:
                my_audiences.append(audience)
            else:
                other_audiences.append(audience)

        return [my_audiences, other_audiences], audiences

    def post_student_list(self, course, data):
        if "remove_student" in data:
            try:
                if data["type"] == "all":
                    audiences = list(self.database.audiences.find({"courseid": course.get_id()}))
                    for audience in audiences:
                        audience["students"] = []
                        self.database.audiences.replace_one({"_id": audience["_id"]}, audience)
                    groups = list(self.database.groups.find({"courseid": course.get_id()}))
                    for group in groups:
                        group["students"] = []
                        self.database.groups.replace_one({"_id": group["_id"]}, group)
                    self.database.courses.find_one_and_update({"_id": course.get_id()}, {"$set": {"students": []}})
                else:
                    self.user_manager.course_unregister_user(course.get_id(), data["username"])
            except:
                pass
        elif "register_student" in data:
            try:
                self.user_manager.course_register_user(course, data["username"].strip(), '', True)
            except:
                pass

    def post_audiences(self, course, data, active_tab, msg, error):
        try:
            if 'audience' in data:
                self.database.audiences.insert_one({"courseid": course.get_id(), "students": [],
                                                    "tutors": [],
                                                    "description": data['audience']})
                msg["audiences"] = _("New audience created.")
                active_tab = "tab_audiences"

        except:
            msg["audiences"] = _('User returned an invalid form.')
            error["audiences"] = True
            active_tab = "tab_audiences"

        try:
            if "audiencefile" in data and 'upload_audiences_creation' in data:
                # get the Werkzeug datastructures.FileStorage object.
                # The stream of this object is the stream body of the uploaded file.
                # Furthermore, FileStorage.stream seems to inherit ʻio.BufferedIOBase`, so this stream should be boiled.
                # As reader return an iterator and that we iterate twice, it is faster to cast into a list.
                csv_data = list(csv.reader(io.TextIOWrapper(data["audiencefile"], encoding='utf-8')))
                # Define used variables.
                students_per_audience = {}
                tutors_per_audience = {}
                course_students = []
                course_tutors = []
                audiences = []
                # Check correctness of CSV structure.
                for line in csv_data:
                    if len(line) != 4:
                        msg["audiences"] = _("File wrongly formatted.")
                        error["audiences"] = True
                if "audiences" not in error or not error["audiences"]:
                    stud_list, aud_li, oth_stu, u_info = self.get_user_lists(course)
                    courseid = course.get_id()
                    # Fully remove previous audiences.
                    self.database.audiences.delete_many({"courseid": courseid})
                    # read datas from CSV.
                    for user_id, field, role, description in csv_data:
                        user_id = user_id.strip()
                        field = field.strip()
                        role = role.strip()
                        if description != "":
                            description = description.strip()
                        if field not in ["username", "email"]:
                            msg["audiences"] = _("Field was not recognized: ") + field
                            error["audiences"] = True
                            continue
                        if role not in ["student", "tutor"]:
                            msg["audiences"] = _("Unknown role: ") + role
                            error["audiences"] = True
                            continue
                        user = self.database.users.find_one({field: user_id})
                        if user is not None:
                            user_id = user["username"]
                        else:
                            msg["audiences"] = _("User was not found: ") + user_id
                            error["audiences"] = True
                            continue
                        # prepare datas to avoid multiple request to database.
                        if role == "student":
                            students_per_audience.setdefault(description, []).append(user_id)
                            course_students.append(user_id)
                        else:
                            tutors_per_audience.setdefault(description, []).append(user_id)
                            course_tutors.append(user_id)
                    # Creation of audiences.
                    if len(students_per_audience) > 0:
                        for key, value in students_per_audience.items():
                            audiences.append({"description": key, "courseid": courseid,
                                              "students": value,
                                              "tutors": tutors_per_audience[key] if key in tutors_per_audience else []})
                    else:
                        for key, value in tutors_per_audience.items():
                            audiences.append({"description": key, "courseid": courseid,
                                              "students": [],
                                              "tutors": value})

                    # update list of students and tutors of the course.
                    new_students = list(set(stud_list).union(set(course_students)))
                    new_tutors = list(set(course.get_tutors()).union(set(course_tutors)))

                    self.database.courses.update_one({"_id": courseid}, {"$set": {"students": new_students,
                                                                                  "tutors": new_tutors}})

                    # this is done to avoid removing the audience id and impact the group audience filter.
                    for audience in audiences:
                        existing_audience = self.database.audiences.find_one(
                            {"courseid": courseid, "description": audience["description"]})
                        if not existing_audience:
                            self.database.audiences.insert_one(audience)
                        else:
                            self.database.audiences.update_one({"courseid": courseid,
                                                                "description": audience["description"]},
                                                               {"$set": {"students": audience["students"],
                                                                         "tutors": audience["tutors"]}})

            active_tab = "tab_audiences"
        except Exception as e:
            msg["audiences"] = _('An error occurred while parsing the data.')
            error["audiences"] = True
            active_tab = "tab_audiences"
        return active_tab

    def get_requested_field_user_info(self, username, preferred_field):
        if preferred_field != "username":
            # query user
            username = self.database.users.find_one({"username": username})[preferred_field]

        return username

    def post_groups(self, course, data, active_tab, msg, error):
        if course.is_lti():
            return active_tab

        audience_list = self.user_manager.get_course_audiences(course)
        audience_students = {}
        for audience in audience_list:
            for stud in audience["students"]:
                audience_students.setdefault(stud, []).append(audience["_id"])

        errored_students = []
        if len(data["delete"]):

            for classid in data["delete"]:
                # Get the group
                group = self.database.groups.find_one(
                    {"_id": ObjectId(classid), "courseid": course.get_id()}) if ObjectId.is_valid(classid) else None

                if group is None:
                    msg["groups"] = ("group with id {} not found.").format(classid)
                    error["groups"] = True
                else:
                    self.database.groups.find_one_and_update({"courseid": course.get_id()},
                                                             {"$push": {
                                                                 "students": {"$each": group["students"]}
                                                             }})

                    self.database.groups.delete_one({"_id": ObjectId(classid)})
                    msg["groups"] = _("Audience updated.")
            active_tab = "tab_groups"

        if "upload_groups" in data or "groups" in data:
            try:
                if "upload_groups" in data:
                    self.database.groups.delete_many({"courseid": course.get_id()})
                    groups = custom_yaml.load(data["groupfile"].read())
                else:
                    groups = json.loads(data["groups"])

                for index, new_group in enumerate(groups):
                    # In case of file upload, no id specified
                    new_group['_id'] = new_group['_id'] if '_id' in new_group else 'None'

                    # Update the group
                    group, errors = self.update_group(course, new_group['_id'], new_group, audience_students)
                    errored_students += errors

                if len(errored_students) > 0:
                    msg["groups"] = _("Changes couldn't be applied for following students :") + "<ul>"
                    for student in errored_students:
                        msg["groups"] += "<li>" + student + "</li>"

                    msg["groups"] += "</ul>"
                    error["groups"] = True
                elif not error:
                    msg["groups"] = _("Groups updated.")
            except:
                msg["groups"] = _('An error occurred while parsing the data.')
                error["groups"] = True
            active_tab = "tab_groups"
        return active_tab

    def get_user_lists(self, course):
        """ Get the available student list for group edition"""
        audience_list = self.user_manager.get_course_audiences(course)
        audience_list = {audience["_id"]: audience for audience in audience_list}

        student_list = self.user_manager.get_course_registered_users(course, False)
        users_info = self.user_manager.get_users_info(student_list)

        groups_list = list(self.database.groups.aggregate([
            {"$match": {"courseid": course.get_id()}},
            {"$unwind": "$students"},
            {"$project": {
                "group": "$_id",
                "students": 1
            }}
        ]))
        groups_list = {d["students"]: d["group"] for d in groups_list}

        other_students = [entry for entry in student_list if entry not in groups_list]
        other_students = sorted(other_students,
                                key=lambda val: (("0" + users_info[val].realname) if users_info[val] else ("1" + val)))

        return student_list, audience_list, other_students, users_info

    def update_group(self, course, groupid, new_data, audience_students):
        """ Update group and returns a list of errored students"""

        student_list = self.user_manager.get_course_registered_users(course, False)

        # If group is new
        if groupid == 'None':
            # Remove _id for correct insertion
            del new_data['_id']
            new_data["courseid"] = course.get_id()

            # Insert the new group
            result = self.database.groups.insert_one(new_data)

            # Retrieve new group id
            groupid = result.inserted_id
            new_data['_id'] = result.inserted_id
            group = new_data
        else:
            group = self.database.groups.find_one({"_id": ObjectId(groupid), "courseid": course.get_id()})

        # Convert audience ids to ObjectId
        new_data["audiences"] = [ObjectId(s) for s in new_data["audiences"]]

        students, errored_students = [], []

        if len(new_data["students"]) <= new_data["size"]:
            # Check the students
            for student in new_data["students"]:
                student_allowed_in_group = any(
                    set(audience_students.get(student, [])).intersection(new_data["audiences"]))
                if student in student_list and (student_allowed_in_group or not new_data["audiences"]):
                    # Remove user from the other group
                    self.database.groups.find_one_and_update({"courseid": course.get_id(), "students": student},
                                                             {"$pull": {"students": student}})
                    students.append(student)
                else:
                    errored_students.append(student)

        new_data["students"] = students

        group = self.database.groups.find_one_and_update(
            {"_id": ObjectId(groupid)},
            {"$set": {"description": new_data["description"], "audiences": new_data["audiences"],
                      "size": new_data["size"],
                      "students": students}}, return_document=ReturnDocument.AFTER)

        return group, errored_students

    def update_audience(self, course, audienceid, new_data):
        """ Update audience and returns a list of errored students"""

        student_list = self.user_manager.get_course_registered_users(course, False)

        # If audience is new
        if audienceid == 'None':
            # Remove _id for correct insertion
            del new_data['_id']
            new_data["courseid"] = course.get_id()

            # Insert the new audience
            result = self.database.audiences.insert_one(new_data)

            # Retrieve new audience id
            audienceid = result.inserted_id
            new_data['_id'] = result.inserted_id
            audience = new_data
        else:
            audience = self.database.audiences.find_one({"_id": ObjectId(audienceid), "courseid": course.get_id()})

        # Check tutors
        new_data["tutors"] = [tutor for tutor in new_data["tutors"] if tutor in course.get_staff()]

        students, errored_students = [], []

        # Check the students
        for student in new_data["students"]:
            if student in student_list:
                students.append(student)
            else:
                # Check if user can be registered
                user_info = self.user_manager.get_user_info(student)
                if user_info is None or student in audience["tutors"]:
                    errored_students.append(student)
                else:
                    self.user_manager.course_register_user(course, student, force=True)
                    students.append(student)

        removed_students = [student for student in audience["students"] if student not in new_data["students"]]
        self.database.audiences.find_one_and_update({"courseid": course.get_id()},
                                                    {"$push": {"students": {"$each": removed_students}}})

        new_data["students"] = students

        audience = self.database.audiences.find_one_and_update(
            {"_id": ObjectId(audienceid)},
            {"$set": {"description": new_data["description"],
                      "students": students, "tutors": new_data["tutors"]}}, return_document=ReturnDocument.AFTER)

        return audience, errored_students

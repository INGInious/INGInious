# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import io
import csv
import json
import yaml

from bson import ObjectId
from flask import Response, request, render_template
from io import StringIO

from natsort import natsorted
from inginious.frontend.models import Audience, User, Group, CourseClass
from inginious.common import custom_yaml
from inginious.frontend.pages.course_admin.utils import make_csv, INGIniousAdminPage


class CourseStudentListPage(INGIniousAdminPage):
    """ Course administration page: list of registered students """

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course, __ = self.get_course_and_check_rights(courseid)
        if "preferred_field" in request.args and request.args["preferred_field"] in ['username', 'email']:
            preferred_field = request.args["preferred_field"]
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

        if "download_groups" in request.args:
            groups = [{"description": group["description"],
                       "students": list(group["students"]),
                       "size": group["size"],
                       "audiences": [str(c) for c in group["audiences"]]} for group in
                      self.user_manager.get_course_groups(course)]
            response = Response(response=yaml.dump(groups), content_type='text/x-yaml')
            response.headers['Content-Disposition'] = 'attachment; filename="groups.yaml"'
            return response

        return self.page(course, active_tab="tab_audiences" if "audiences" in request.args else "tab_students")

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course, __ = self.get_course_and_check_rights(courseid, None, True)
        data = request.form.copy()
        data["delete"] = request.form.getlist("delete")
        data["groupfile"] = request.files.get("groupfile")
        data["audiencefile"] = request.files.get("audiencefile")
        error = {}
        msg = {}
        active_tab = "tab_students"

        self.post_student_list(course, data)
        active_tab = self.post_audiences(course, data, active_tab, msg, error)
        active_tab = self.post_groups(course, data, active_tab, msg, error)

        return self.page(course, active_tab, msg, error)

    def page(self, course, active_tab="tab_students", msg=None, error=None):
        """ Get all data and display the page """
        if error is None:
            error = {}
        if msg is None:
            msg = {}

        # Course user infos
        student_list = self.user_manager.get_course_registered_users(course, False)
        staff_list = course.get_staff()
        users_info = self.user_manager.get_users_info(student_list + staff_list)

        # User progress
        user_progress = self.user_manager.get_course_caches(student_list + staff_list, course)

        # Audiences and audience progress
        audiences = self.user_manager.get_course_audiences(course)
        audience_progress = self.user_manager.get_audience_progress(audiences, course)

        # Groups and student groups
        groups = self.user_manager.get_course_groups(course)
        ungrouped_students = self.user_manager.get_course_ungrouped_students(course)

        if "csv_audiences" in request.args:
            retval = {audience.id: audience.to_mongo() for audience in audiences}
            for audience_id in retval:
                retval[audience_id].update(audience_progress[audience_id])
            return make_csv(retval)

        if "csv_student" in request.args:
            for username in user_progress:
                user_progress[username]["username"] = username
                user_progress[username]["realname"] = users_info[username].realname
                user_progress[username]["email"] = users_info[username].email
            return make_csv(user_progress)

        sorted_staff_list = natsorted(staff_list, lambda x: users_info[x].realname)
        sorted_student_list = natsorted(student_list, lambda x: users_info[x].realname)

        return render_template("course_admin/student_list.html", course=course,
                               student_list=sorted_student_list, staff_list=sorted_staff_list, users_info=users_info,
                               user_progress=user_progress,
                               audiences={audience.id: audience for audience in audiences},
                               audience_progress=audience_progress,
                               groups=groups, ungrouped_students=ungrouped_students,
                               active_tab=active_tab, error=error, msg=msg)



    def post_student_list(self, course, data):
        if "remove_student" in data:
            try:
                if data["type"] == "all":
                    Audience.objects(courseid=course.get_id()).update(students=[])
                    Group.objects(courseid=course.get_id()).update(students=[])
                    CourseClass.objects(id=course.get_id()).update(students=[])
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
                Audience(courseid=course.get_id(), students=[], tutors=[], description=data['audience']).save()
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
                    stud_list = self.user_manager.get_course_registered_users(course, False)
                    courseid = course.get_id()
                    # Fully remove previous audiences.
                    Audience.objects(courseid=courseid).delete()
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
                        user = User.objects(**{field: user_id}).first()
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
                    CourseClass.objects(id=courseid).update(students=new_students)

                    # this is done to avoid removing the audience id and impact the group audience filter.
                    for audience in audiences:
                        existing_audience = Audience.objects(
                            courseid=courseid, description=audience["description"]
                        ).first()
                        if not existing_audience:
                            Audience(**audience).save()
                        else:
                            existing_audience.students = audience["students"]
                            existing_audience.tutors = audience["tutors"]
                            existing_audience.save()

                active_tab = "tab_audiences"
        except Exception as e:
            msg["audiences"] = _('An error occurred while parsing the data.')
            error["audiences"] = True
            active_tab = "tab_audiences"
        return active_tab

    def get_requested_field_user_info(self, username, preferred_field):
        if preferred_field != "username":
            # query user
            username = User.objects.get(username=username)[preferred_field]

        return username

    def post_groups(self, course, data, active_tab, msg, error):
        if course.is_lti():
            return active_tab

        audience_list = self.user_manager.get_course_audiences(course)
        audience_students = {}
        for audience in audience_list:
            for stud in audience["students"]:
                audience_students.setdefault(stud, []).append(audience.id)

        errored_students = []
        if len(data["delete"]):

            for classid in data["delete"]:
                # Get the group
                group = Group.objects(id=classid, courseid=course.get_id()).first()

                if group is None:
                    msg["groups"] = ("group with id {} not found.").format(classid)
                    error["groups"] = True
                else:
                    Group.objects(id=classid).delete()
                    msg["groups"] = _("Groups updated.")
            active_tab = "tab_groups"

        if "upload_groups" in data or "groups" in data:
            try:
                if "upload_groups" in data:
                    Group.objects(courseid=course.get_id()).delete()
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

    def update_group(self, course, groupid, new_data, audience_students):
        """ Update group and returns a list of errored students"""

        student_list = self.user_manager.get_course_registered_users(course, False)

        # If group is new
        if groupid == 'None':
            # Remove _id for correct insertion
            del new_data['_id']
            new_data["courseid"] = course.get_id()

            # Insert the new group and retrieve its id
            groupid = Group(**new_data).save().id

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
                    Group.objects(courseid=course.get_id(), students=student).update(pull__students=student)
                    students.append(student)
                else:
                    errored_students.append(student)

        new_data["students"] = students

        group = Group.objects.get(id=groupid).modify(
            description=new_data["description"], audiences=new_data["audiences"], size=new_data["size"],
            students=students)

        return group, errored_students

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Pages that allow editing of tasks """

import json

import web
from bson.objectid import ObjectId
from pymongo import ReturnDocument

from inginious.common import custom_yaml
from inginious.frontend.pages.course_admin.utils import INGIniousAdminPage


class CourseEditTeam(INGIniousAdminPage):
    """ Edit a task """

    def get_user_lists(self, course, teamid=''):
        """ Get the available student and tutor lists for team edition"""
        tutor_list = course.get_staff()

        # Determine student list and if they are grouped
        course_obj = self.database.courses.find_one({"_id": course.get_id()})
        students = course_obj["students"] if course_obj else []
        student_list = list(self.database.teams.aggregate([
            {"$match": {"courseid": course.get_id()}},
            {"$unwind": "$students"},
            {"$project": {
                "classroom": "$_id",
                "students": 1,
                "grouped": {
                    "$anyElementTrue": {
                        "$map": {
                            "input": "$groups.students",
                            "as": "group",
                            "in": {
                                "$anyElementTrue": {
                                    "$map": {
                                        "input": "$$group",
                                        "as": "groupmember",
                                        "in": {"$eq": ["$$groupmember", "$students"]}
                                    }
                                }
                            }
                        }
                    }
                }
            }}
        ]))

        student_list = dict([(student["students"], student) for student in student_list])
        student_list = {student: student_list[student] if student in student_list else {"students": student, "classroom": None, "grouped": False} for student in students}
        users_info = self.user_manager.get_users_info(list(student_list.keys()) + tutor_list)

        if teamid:
            # Order the non-registered students
            other_students = [student_list[entry]['students'] for entry in student_list.keys() if
                              not student_list[entry]['classroom'] == ObjectId(teamid)]
            other_students = sorted(other_students, key=lambda val: (("0"+users_info[val][0]) if users_info[val] else ("1"+val)))

            return student_list, tutor_list, other_students, users_info
        else:
            return student_list, tutor_list, users_info

    def update_team(self, course, teamid, new_data):
        """ Update team and returns a list of errored students"""

        student_list = self.user_manager.get_course_registered_users(course, False)

        # If team is new
        if teamid == 'None':
            # Remove _id for correct insertion
            del new_data['_id']
            new_data["courseid"] = course.get_id()

            # Insert the new team
            result = self.database.teams.insert_one(new_data)

            # Retrieve new team id
            teamid = result.inserted_id
            new_data['_id'] = result.inserted_id
            team = new_data
        else:
            team = self.database.teams.find_one({"_id": ObjectId(teamid), "courseid": course.get_id()})

        # Check tutors
        new_data["tutors"] = [tutor for tutor in new_data["tutors"] if tutor in course.get_staff()]

        students, groups, errored_students = [], [], []

        # Check the students
        for student in new_data["students"]:
            if student in student_list:
                # Remove user from the other team
                self.database.teams.find_one_and_update({"courseid": course.get_id(), "groups.students": student},
                                                             {"$pull": {"groups.$.students": student, "students": student}})
                self.database.teams.find_one_and_update({"courseid": course.get_id(), "students": student}, {"$pull": {"students": student}})
                students.append(student)
            else:
                # Check if user can be registered
                user_info = self.user_manager.get_user_info(student)
                if user_info is None or student in team["tutors"]:
                    errored_students.append(student)
                else:
                    self.user_manager.course_register_user(course, student, force=True)
                    students.append(student)

        removed_students = [student for student in team["students"] if student not in new_data["students"]]
        self.database.teams.find_one_and_update({"courseid": course.get_id()},
                                                     {"$push": {"students": {"$each": removed_students}}})

        new_data["students"] = students

        # Check the groups
        for group in new_data["groups"]:
            group["students"] = [student for student in group["students"] if student in new_data["students"]]
            if len(group["students"]) <= group["size"]:
                groups.append(group)

        new_data["groups"] = groups

        team = self.database.teams.find_one_and_update(
            {"_id": ObjectId(teamid)},
            {"$set": {"description": new_data["description"],
                      "students": students, "tutors": new_data["tutors"],
                      "groups": groups}}, return_document=ReturnDocument.AFTER)

        return team, errored_students

    def display_page(self, course, msg='', error=False):
        # If no team id specified, use the groups only template
        student_list, tutor_list, users_info = self.get_user_lists(course)
        teams = self.user_manager.get_course_teams(course)
        return self.template_helper.get_renderer().course_admin.teams_edit(course, student_list,
                                                                                    tutor_list,
                                                                                    users_info, teams, msg,
                                                                                    error)

    def GET_AUTH(self, courseid, teamid=''):  # pylint: disable=arguments-differ
        """ Edit a team """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=True)

        if course.is_lti():
            raise web.notfound()

        return self.display_page(course)

    def POST_AUTH(self, courseid, teamid=''):  # pylint: disable=arguments-differ
        """ Edit a team """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=True)

        if course.is_lti():
            raise web.notfound()

        msg=''
        error = False
        errored_students = []
        data = web.input(delete=[], tutors=[], groups=[], teamfile={})
        if len(data["delete"]):

            for classid in data["delete"]:
                # Get the team
                team = self.database.teams.find_one({"_id": ObjectId(classid), "courseid": courseid}) if ObjectId.is_valid(classid) else None

                if team is None:
                    msg = ("Team with id {} not found.").format(classid)
                    error = True
                elif team['default'] and teamid:
                    msg = _("You can't remove your default classroom.")
                    error = True
                else:
                    self.database.teams.find_one_and_update({"courseid": courseid},
                                                                 {"$push": {
                                                                     "students": {"$each": team["students"]}
                                                                 }})

                    self.database.teams.delete_one({"_id": ObjectId(classid)})
                    msg = _("Classroom updated.")

            if teamid and teamid in data["delete"]:
                raise web.seeother(self.app.get_homepath() + "/admin/" + courseid + "/teams")

        try:
            if "upload" in data:
                self.database.teams.delete_many({"courseid": course.get_id()})
                teams = custom_yaml.load(data["teamfile"].file)
            else:
                teams = json.loads(data["aggregations"])

            for index, new_team in enumerate(teams):
                # In case of file upload, no id specified
                new_team['_id'] = new_team['_id'] if '_id' in new_team else 'None'

                # If no groups field set, create group from class students if in groups only mode
                if "groups" not in new_team:
                    new_team["groups"] = [] if teamid else [{'size': len(new_team['students']),
                                                                       'students': new_team['students']}]

                # Update the team
                team, errors = self.update_team(course, new_team['_id'], new_team)

                errored_students += errors

            if len(errored_students) > 0:
                msg = _("Changes couldn't be applied for following students :") + "<ul>"
                for student in errored_students:
                    msg += "<li>" + student + "</li>"
                msg += "</ul>"
                error = True
            elif not error:
                msg = _("Teams updated.")
        except:
            raise
            msg = _('An error occurred while parsing the data.')
            error = True

        # Display the page
        return self.display_page(course, msg, error)

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Index page """

import logging

from flask import request, render_template
from werkzeug.exceptions import Forbidden
from bson.objectid import ObjectId

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend import database
from inginious.frontend.user_manager import user_manager
from inginious.frontend.course_factory import course_factory

class GroupPage(INGIniousAuthPage):
    """ Group page """

    _logger = logging.getLogger("inginious.webapp.groups")

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """

        course = course_factory.get_course(courseid)
        username = user_manager.session_username()

        error = False
        msg = ""
        data = request.args
        if user_manager.has_staff_rights_on_course(course):
            raise Forbidden(description=_("You can't access this page as a member of the staff."))
        elif not (user_manager.course_is_open_to_user(course, lti=False)
                  and user_manager.course_is_user_registered(course, username)):
            return render_template("course_unavailable.html")
        elif "register_group" in data:
            if course.can_students_choose_group():

                group = database.groups.find_one(
                    {"courseid": course.get_id(), "students": username})
                if group is not None:
                    group["students"].remove(username)
                    database.groups.replace_one({"courseid": course.get_id(), "students": username}, group)

                # Add student in the audience and unique group if group is not full
                new_group = database.groups.find_one_and_update(
                    {"_id": ObjectId(data["register_group"]),
                     "$where": "this.students.length<this.size"},
                    {"$push": {"students": username}})

                if new_group is None:
                    error = True
                    msg = _("Couldn't register to the specified group.")
                else:
                    self._logger.info("User %s registered to group %s/%s", username, courseid, new_group["description"])
            else:
                error = True
                msg = _("You are not allowed to change group.")
        elif "unregister_group" in data:
            if course.can_students_choose_group():
                group = database.groups.find_one({"courseid": course.get_id(), "students": username})
                if group is not None:
                    database.groups.find_one_and_update({"_id": group["_id"]}, {"$pull": {"students": username}})
                    self._logger.info("User %s unregistered from group %s/%s", username, courseid, group["description"])
                else:
                    error = True
                    msg = _("You're not registered in a group.")
            else:
                error = True
                msg = _("You are not allowed to change group.")

        tasks = course.get_tasks()
        last_submissions = self.submission_manager.get_user_last_submissions(5, {"courseid": courseid, "taskid": {"$in": list(tasks.keys())}})
        for submission in last_submissions:
            submission["taskname"] = tasks[submission['taskid']].get_name(user_manager.session_language())

        user_group = user_manager.get_course_user_group(course)
        user_audiences = [audience["_id"] for audience in database.audiences.find({"courseid": courseid, "students": username})]
        groups = user_manager.get_course_groups(course)

        student_allowed_in_group = lambda group: any(set(user_audiences).intersection(group["audiences"])) or not group["audiences"]
        allowed_groups = [group for group in groups if student_allowed_in_group(group)]

        users = user_manager.get_users_info(user_manager.get_course_registered_users(course))

        return render_template("group.html",
                                           course=course,
                                           submissions=last_submissions,
                                           allowed_groups=allowed_groups,
                                           groups=groups,
                                           users=users,
                                           mygroup=user_group,
                                           msg=msg,
                                           error=error)

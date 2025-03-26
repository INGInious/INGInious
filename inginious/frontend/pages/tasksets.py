# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Index page """
from datetime import datetime
import flask
from collections import OrderedDict

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.exceptions import CourseAlreadyExistsException


class TasksetsPage(INGIniousAuthPage):
    """ Index page """

    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ Display main course list page """
        return self.show_page(False, [])

    def POST_AUTH(self):  # pylint: disable=arguments-differ
        """ Parse taskset creation or course instantiation and display the tasksets list page """

        user_input = flask.request.form
        success = None

        messages = []

        if "instantiate" in user_input:
            tasksetid = user_input["tasksetid"]
            courseid = user_input["courseid"]

            try:
                taskset = self.taskset_factory.get_taskset(tasksetid)
                if self.user_manager.session_username() in taskset.get_admins() or taskset.is_public() or self.user_manager.user_is_superadmin():
                    task_dispenser = taskset.get_task_dispenser()
                    self.course_factory.create_course(courseid, {
                        "name": courseid, "accessible":  {"start": datetime.max.replace(microsecond=0), "end": datetime.max.replace(microsecond=0)},
                        "registration": {"start": datetime.max.replace(microsecond=0), "end": datetime.max.replace(microsecond=0)}, "tasksetid": taskset.get_id(),
                        "admins": [self.user_manager.session_username()], "students": [],
                        "task_dispenser": task_dispenser.get_id(), "dispenser_data": task_dispenser.get_dispenser_data()
                    })
                    success = True
                    messages.append(_("Course with id {} successfully instantiated from taskset {}").format(courseid, tasksetid))
                else:
                    success = False
                    messages.append(_("You are not allowed to instantiate a course from this taskset."))
            except CourseAlreadyExistsException as e:
                success = False
                messages.append(_("A course with id {} already exists.").format(courseid))
            except Exception as e:
                success = False
                messages.append(_("Couldn't instantiate course with id {} : ").format(courseid) + str(e))

        elif "new_tasksetid" in user_input and self.user_manager.user_is_superadmin():
            try:
                tasksetid = user_input["new_tasksetid"]
                self.taskset_factory.create_taskset(tasksetid, {"name": tasksetid, "admins": [], "description": ""})
                success = True
                messages.append(_("Taskset created."))
            except:
                success = False
                messages.append( _("Failed to create the taskset."))

        return self.show_page(success, messages)

    def show_page(self, success, messages):
        """  Display main course list page """
        all_tasksets = self.taskset_factory.get_all_tasksets()
        all_tasksets = {tasksetid: taskset for tasksetid, taskset in all_tasksets.items() if
                        self.user_manager.user_is_superadmin() or self.user_manager.session_username() in taskset.get_admins() or taskset.is_public()}

        tasksets = OrderedDict(sorted(iter(all_tasksets.items()), key=lambda x: x[1].get_name(self.user_manager.session_language())))

        return self.template_helper.render("tasksets.html", tasksets=tasksets, success=success, messages=messages)

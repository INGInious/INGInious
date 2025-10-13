# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import bson
import json
import logging
import flask
from collections import OrderedDict
from natsort import natsorted

from inginious.frontend.pages.course_admin.utils import INGIniousAdminPage


class CourseTaskListPage(INGIniousAdminPage):
    """ List informations about all tasks """

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=True)
        return self.page(course)

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)

        errors = []
        user_input = flask.request.form
        if "task_dispenser" in user_input:
            selected_task_dispenser = user_input.get("task_dispenser", "toc")
            task_dispenser_class = self.course_factory.get_task_dispensers().get(selected_task_dispenser, None)
            if task_dispenser_class:
                self.course_factory.update_course_descriptor_element(courseid, 'task_dispenser', task_dispenser_class.get_id())
                self.course_factory.update_course_descriptor_element(courseid, 'dispenser_data', {})
            else:
                errors.append(_("Invalid task dispenser"))
        elif "migrate_tasks" in user_input:
            task_dispenser = course.get_task_dispenser()
            try:
                data = task_dispenser.import_legacy_tasks()
                self.update_dispenser(course, data)
                self.clean_task_files(course)
            except Exception as e:
                errors.append(_("Something wrong happened: ") + str(e))
        else:
            try:
                self.update_dispenser(course, json.loads(user_input["course_structure"]))
            except Exception as e:
                errors.append(_("Something wrong happened: ") + str(e))

            for taskid in json.loads(user_input.get("new_tasks", "[]")):
                try:
                    self.task_factory.create_task(course, taskid, {
                        "name": taskid, "problems": {}, "environment_type": "mcq"})
                except Exception as ex:
                    errors.append(_("Couldn't create task {} : ").format(taskid) + str(ex))
            for taskid in json.loads(user_input.get("deleted_tasks", "[]")):
                try:
                    self.task_factory.delete_task(courseid, taskid)
                except Exception as ex:
                    errors.append(_("Couldn't delete task {} : ").format(taskid) + str(ex))
            for taskid in json.loads(user_input.get("wiped_tasks", "[]")):
                try:
                    self.wipe_task(courseid, taskid)
                except Exception as ex:
                    errors.append(_("Couldn't wipe task {} : ").format(taskid) + str(ex))

        # don't forget to reload the modified course
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)
        return self.page(course, errors, not errors)

    def update_dispenser(self, course, dispenser_data):
        """ Update the task dispenser based on dispenser_data """
        task_dispenser = course.get_task_dispenser()
        data, msg = task_dispenser.check_dispenser_data(dispenser_data)
        if data:
            self.course_factory.update_course_descriptor_element(course.get_id(), 'task_dispenser',
                                                                 task_dispenser.get_id())
            self.course_factory.update_course_descriptor_element(course.get_id(), 'dispenser_data', data)
        else:
            raise Exception(_("Invalid course structure: ") + msg)

    def clean_task_files(self, course):
        task_dispenser = course.get_task_dispenser()
        legacy_fields = task_dispenser.legacy_fields.keys()
        for taskid in course.get_tasks():
            descriptor = self.task_factory.get_task_descriptor_content(course.get_id(), taskid)
            for field in legacy_fields:
                descriptor.pop(field, None)
            self.task_factory.update_task_descriptor_content(course.get_id(), taskid, descriptor)

    def submission_url_generator(self, taskid):
        """ Generates a submission url """
        return "?format=taskid%2Fusername&tasks=" + taskid

    def wipe_task(self, courseid, taskid):
        """ Wipe the data associated to the taskid from DB"""
        submissions = self.database.submissions.find({"courseid": courseid, "taskid": taskid})
        for submission in submissions:
            for key in ["input", "archive"]:
                if key in submission and type(submission[key]) == bson.objectid.ObjectId:
                    self.submission_manager.get_gridfs().delete(submission[key])

        self.database.user_tasks.delete_many({"courseid": courseid, "taskid": taskid})
        self.database.submissions.delete_many({"courseid": courseid, "taskid": taskid})

        logging.getLogger("inginious.webapp.task_edit").info("Task %s/%s wiped.", courseid, taskid)

    def page(self, course, errors=None, validated=False):
        """ Get all data and display the page """

        # Load tasks and verify exceptions
        files = self.task_factory.get_readable_tasks(course)

        tasks = {}
        if errors is None:
            errors = []

        tasks_errors = {}
        for taskid in files:
            try:
                tasks[taskid] = course.get_task(taskid)
            except Exception as ex:
                tasks_errors[taskid] = str(ex)

        tasks_data = natsorted([(taskid, {"name": tasks[taskid].get_name(self.user_manager.session_language()),
                                       "url": self.submission_url_generator(taskid)}) for taskid in tasks],
                            key=lambda x: x[1]["name"])
        tasks_data = OrderedDict(tasks_data)

        task_dispensers = self.course_factory.get_task_dispensers()

        return self.template_helper.render("course_admin/task_list.html", course=course,
                                           task_dispensers=task_dispensers, tasks=tasks_data, errors=errors,
                                           tasks_errors=tasks_errors, validated=validated, webdav_host=self.webdav_host)


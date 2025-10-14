# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Pages that allow editing of tasks """
import json
import logging
import tempfile
import bson

import flask
from collections import OrderedDict
from zipfile import ZipFile
from flask import render_template
from werkzeug.exceptions import NotFound

from inginious.frontend.tasks import _migrate_from_v_0_6
from inginious.frontend.pages.course_admin.utils import INGIniousAdminPage

from inginious.common.base import dict_from_prefix, id_checker
from inginious.common.exceptions import TaskNotFoundException
from inginious.common.tasks_problems import get_problem_types
from inginious.frontend.pages.course_admin.task_edit_file import CourseTaskFiles
from inginious.frontend.tasks import Task
from inginious.frontend.plugins import plugin_manager


class CourseEditTask(INGIniousAdminPage):
    """ Edit a task """
    _logger = logging.getLogger("inginious.webapp.task_edit")

    def GET_AUTH(self, courseid, taskid):  # pylint: disable=arguments-differ
        """ Edit a task """
        if not id_checker(taskid):
            raise NotFound(description=_("Invalid task id"))

        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)

        try:
            task_data = self.task_factory.get_task_descriptor_content(courseid, taskid)
        except TaskNotFoundException:
            raise NotFound()

        # Ensure retrocompatibility
        task_data = _migrate_from_v_0_6(task_data)

        environment_types = self.environment_types
        environments = self.environments

        additional_tabs = plugin_manager.call_hook('task_editor_tab', course=course, taskid=taskid,
                                                        task_data=task_data)

        return render_template("course_admin/task_edit.html", course=course, taskid=taskid,
                                           problem_types=get_problem_types(), task_data=task_data,
                                           environment_types=environment_types, environments=environments,
                                           problemdata=json.dumps(task_data.get('problems', {})),
                                           contains_is_html=self.contains_is_html(task_data),
                                           file_list=CourseTaskFiles.get_task_filelist(self.task_factory, courseid, taskid),
                                           additional_tabs=additional_tabs)

    @classmethod
    def contains_is_html(cls, data):
        """ Detect if the problem has at least one "xyzIsHTML" key """
        for key, val in data.items():
            if isinstance(key, str) and key.endswith("IsHTML"):
                return True
            if isinstance(val, (OrderedDict, dict)) and cls.contains_is_html(val):
                return True
        return False

    def parse_problem(self, problem_content):
        """ Parses a problem, modifying some data """
        del problem_content["@order"]
        return get_problem_types().get(problem_content["type"]).parse_problem(problem_content)

    def POST_AUTH(self, courseid, taskid):  # pylint: disable=arguments-differ
        """ Edit a task """
        if not id_checker(taskid) or not id_checker(courseid):
            raise NotFound(description=_("Invalid course/task id"))

        __, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)
        data = flask.request.form.copy()
        data["task_file"] = flask.request.files.get("task_file")

        # Else, parse content
        try:
            try:
                task_zip = data.get("task_file").read()
            except:
                task_zip = None
            del data["task_file"]

            problems = dict_from_prefix("problem", data)
            environment_type = data.get("environment_type", "")
            environment_parameters = dict_from_prefix("envparams", data).get(environment_type, {})
            environment_id = dict_from_prefix("environment_id", data).get(environment_type, "")

            data = {key: val for key, val in data.items() if
                    not key.startswith("problem")
                    and not key.startswith("envparams")
                    and not key.startswith("environment_id")
                    and not key.startswith("/")
                    and not key == "@action"}

            data["environment_id"] = environment_id # we do this after having removed all the environment_id[something] entries

            # Parse and order the problems (also deletes @order from the result)
            if problems is None:
                data["problems"] = OrderedDict([])
            else:
                data["problems"] = OrderedDict([(key, self.parse_problem(val))
                                                for key, val in sorted(iter(problems.items()), key=lambda x: int(x[1]['@order']))])

            # Task environment parameters
            data["environment_parameters"] = environment_parameters

            # Random inputs
            try:
                data['input_random'] = int(data['input_random'])
            except:
                return json.dumps({"status": "error", "message": _("The number of random inputs must be an integer!")})
            if data['input_random'] < 0:
                return json.dumps({"status": "error", "message": _("The number of random inputs must be positive!")})

            # Checkboxes
            if data.get("responseIsHTML"):
                data["responseIsHTML"] = True

            # Network grading
            data["network_grading"] = "network_grading" in data


        except Exception as message:
            return json.dumps({"status": "error", "message": _("Your browser returned an invalid form ({})").format(message)})

        # Get the course
        try:
            course = self.course_factory.get_course(courseid)
        except:
            return json.dumps({"status": "error", "message": _("Error while reading course's informations")})

        # Get original data
        try:
            orig_data = self.task_factory.get_task_descriptor_content(courseid, taskid)
            data["order"] = orig_data["order"]
        except:
            pass

        task_fs = self.task_factory.get_task_fs(courseid, taskid)
        task_fs.ensure_exists()

        # Call plugins and return the first error
        plugin_results = plugin_manager.call_hook('task_editor_submit', course=course, taskid=taskid,
                                                       task_data=data, task_fs=task_fs)

        # Retrieve the first non-null element
        error = next(filter(None, plugin_results), None)
        if error is not None:
            return error

        try:
            Task(taskid, data, self.course_factory.get_course_fs(courseid))
        except Exception as message:
            return json.dumps({"status": "error", "message": _("Invalid data: {}").format(str(message))})

        if task_zip:
            try:
                zipfile = ZipFile(task_zip)
            except Exception:
                return json.dumps({"status": "error", "message": _("Cannot read zip file. Files were not modified")})

            with tempfile.TemporaryDirectory() as tmpdirname:
                try:
                    zipfile.extractall(tmpdirname)
                except Exception:
                    return json.dumps(
                        {"status": "error", "message": _("There was a problem while extracting the zip archive. Some files may have been modified")})
                task_fs.copy_to(tmpdirname)

        self.task_factory.update_task_descriptor_content(courseid, taskid, data)

        return json.dumps({"status": "ok"})

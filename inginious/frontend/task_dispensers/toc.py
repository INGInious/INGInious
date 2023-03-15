# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import json
from collections import OrderedDict

from functools import reduce
from operator import concat
from inginious.frontend.task_dispensers.util import check_toc, parse_tasks_config, check_task_config,\
    SectionsList, SectionConfigItem, GroupSubmission, Weight, SubmissionStorage, EvaluationMode, Categories, \
    SubmissionLimit, Accessibility
from inginious.frontend.task_dispensers import TaskDispenser
from inginious.frontend.accessible_time import AccessibleTime


class TableOfContents(TaskDispenser):
    config_items = [Weight, SubmissionStorage, EvaluationMode, GroupSubmission, Categories, SubmissionLimit, Accessibility]

    def __init__(self, task_list_func, dispenser_data, database, course_id):
        # Check dispenser data structure
        dispenser_data = dispenser_data or {"toc": {}, "config": {}}
        if not isinstance(dispenser_data, dict) or "toc" not in dispenser_data or "config" not in dispenser_data:
            raise Exception("Invalid dispenser data structure")

        TaskDispenser.__init__(self, task_list_func, dispenser_data, database, course_id)
        self._toc = SectionsList(dispenser_data.get("toc", {}))
        self._task_config = dispenser_data.get("config", {})
        parse_tasks_config(self.config_items, self._task_config)

    @classmethod
    def get_id(cls):
        """ Returns the task dispenser id """
        return "toc"

    @classmethod
    def get_name(cls, language):
        """ Returns the localized task dispenser name """
        return _("Table of contents")

    def get_weight(self, taskid):
        """ Returns the weight of taskid """
        return Weight.get_value(self._task_config.get(taskid, {}))

    def get_no_stored_submissions(self,taskid):
        """Returns the maximum stored submission specified by the administrator"""
        return SubmissionStorage.get_value(self._task_config.get(taskid, {}))

    def get_evaluation_mode(self,taskid):
        """Returns the evaluation mode specified by the administrator"""
        return EvaluationMode.get_value(self._task_config.get(taskid, {}))

    def get_submission_limit(self, taskid):
        """ Returns the submission limits et for the task"""
        return SubmissionLimit.get_value(self._task_config.get(taskid, {}))

    def get_group_submission(self, taskid):
        """ Indicates if the task submission mode is per groups """
        return GroupSubmission.get_value(self._task_config.get(taskid, {}))

    def get_accessibilities(self, taskids, usernames):
        """  Get the accessible time of this task """
        return {username: {taskid: AccessibleTime(Accessibility.get_value(self._task_config.get(taskid, {})))
                           for taskid in taskids } for username in usernames}

    def get_categories(self, taskid):
        """Returns the categories specified for the taskid by the administrator"""
        return Categories.get_value(self._task_config.get(taskid, {}))

    def get_all_categories(self):
        """Returns the categories specified by the administrator"""
        taskids = self._toc.get_tasks()
        return set(reduce(concat, [self.get_categories(taskid) for taskid in taskids])) if len(taskids) else []

    def get_course_grades(self, usernames):
        """ Returns the grade of a user for the current course"""
        taskids = list(self._task_list_func().keys())
        task_list = self.get_accessibilities(taskids, usernames)
        user_tasks = self._database.user_tasks.find(
            {"username": {"$in": usernames}, "courseid": self._course_id, "taskid": {"$in": taskids}})

        tasks_weight = {taskid: self.get_weight(taskid) for taskid in taskids}
        tasks_scores = {username: [0.0, 0.0] for username in usernames}

        for user_task in user_tasks:
            username = user_task["username"]
            if task_list[username][user_task["taskid"]].after_start():
                weighted_score = user_task["grade"] * tasks_weight[user_task["taskid"]]
                tasks_scores[username][0] += weighted_score
                tasks_scores[username][1] += tasks_weight[user_task["taskid"]]

        return {username: round(tasks_scores[username][0]/tasks_scores[username][1])
                if tasks_scores[username][1] > 0 else 0 for username in usernames}

    def get_dispenser_data(self):
        """ Returns the task dispenser data structure """
        return self._toc

    def render_edit(self, template_helper, course, task_data):
        """ Returns the formatted task list edition form """
        config_fields = {
            "closed": SectionConfigItem(_("Closed by default"), "checkbox", False),
            "hidden_if_empty": SectionConfigItem(_("Hidden if empty"),"checkbox",False)
        }
        return template_helper.render("course_admin/task_dispensers/toc.html", course=course,
                                      course_structure=self._toc, tasks=task_data, config_fields=config_fields,
                                      config_items_funcs=["dispenser_util_get_" + config_item.get_id() for config_item in self.config_items])

    def render(self, template_helper, course, tasks_data, tag_list):
        """ Returns the formatted task list"""
        return template_helper.render("task_dispensers/toc.html", course=course, tasks=self._task_list_func(),
                                      tasks_data=tasks_data, tag_filter_list=tag_list, sections=self._toc)

    def check_dispenser_data(self, dispenser_data):
        """ Checks the dispenser data as formatted by the form from render_edit function """
        new_toc = json.loads(dispenser_data)
        valid, errors = check_toc(new_toc.get("toc", {}))
        if valid:
            valid, errors = check_task_config(self.config_items, new_toc.get("config", {}))
        return new_toc if valid else None, errors

    def get_ordered_tasks(self):
        """ Returns a serialized version of the tasks structure as an OrderedDict"""
        tasks = self._task_list_func()
        return OrderedDict([(taskid, tasks[taskid]) for taskid in self._toc.get_tasks() if taskid in tasks])

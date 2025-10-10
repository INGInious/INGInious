# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from random import Random

from flask import render_template
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.frontend.task_dispensers.util import SectionConfigItem, Weight, SubmissionStorage, EvaluationMode, \
    Categories, SubmissionLimit, Accessibility
from inginious.frontend.accessible_time import AccessibleTime


class CombinatoryTest(TableOfContents):
    config_items = [Weight, SubmissionStorage, EvaluationMode, Categories, SubmissionLimit, Accessibility]
    legacy_fields = {"weight": Weight, "submission_limit": SubmissionLimit, "stored_submissions": SubmissionStorage,
                     "evaluate": EvaluationMode, "accessible": Accessibility, "categories": Categories}
    @classmethod
    def get_id(cls):
        return "combinatory_test"

    @classmethod
    def get_name(cls, language):
        return _("Combinatory test")

    def get_group_submission(self, taskid):
        return False

    def get_accessibilities(self, taskids, usernames):
        result = {username: {taskid: AccessibleTime(False) for taskid in taskids} for username in usernames}
        for index, section in enumerate(self._toc):
            task_list = [taskid for taskid in section.get_tasks()
                         if Accessibility.get_value(self._task_config.get(taskid, {})).after_start()]
            amount_questions = int(section.get_config().get("amount", 0))
            for username in usernames:
                rand = Random("{}#{}#{}".format(username, index, section.get_title()))
                random_order_choices = task_list.copy()
                rand.shuffle(random_order_choices)
                for taskid in random_order_choices[0:amount_questions]:
                    result[username][taskid] = Accessibility.get_value(self._task_config.get(taskid, {}))

        return result

    def render_edit(self, course, task_data, task_errors):
        """ Returns the formatted task list edition form """
        config_fields = {
            "amount": SectionConfigItem(_("Amount of tasks to be displayed"), "number", 0)
        }
        return render_template("course_admin/task_dispensers/combinatory_test.html", course=course,
                                      course_structure=self._toc, tasks=task_data, task_errors=task_errors, config_fields=config_fields,
                                      dispenser_config=self._task_config)

    def render(self, course, tasks_data, tag_list, username):
        """ Returns the formatted task list"""
        accessibilities = course.get_task_dispenser().get_accessibilities(self._task_list_func(), [username])
        return render_template("task_dispensers/toc.html", course=course, tasks=self._task_list_func(),
                                      tasks_data=tasks_data, tag_filter_list=tag_list, sections=self._toc,
                                      accessibilities=accessibilities)

    def check_dispenser_data(self, dispenser_data):
        """ Checks the dispenser data as formatted by the form from render_edit function """
        new_toc, errors = TableOfContents.check_dispenser_data(self, dispenser_data)
        if not new_toc:
            return None, errors

        try:
            for section in new_toc.get("toc", {}):
                config = section.setdefault("config", {})
                config["amount"] = int(config.get("amount", 0))
        except Exception as ex:
            return None, str(ex)

        return new_toc, errors

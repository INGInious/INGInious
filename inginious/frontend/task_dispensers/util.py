# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from inginious.common.base import id_checker
from inginious.frontend.accessible_time import AccessibleTime

SectionConfigItem = namedtuple('SectionConfigItem', ['label', 'type', 'default'])


class TaskConfigItem(metaclass=ABCMeta):

    @classmethod
    @abstractmethod
    def get_template(cls):
        pass

    @classmethod
    @abstractmethod
    def get_id(cls):
        pass

    @classmethod
    @abstractmethod
    def get_name(cls):
        pass

    @classmethod
    @abstractmethod
    def get_value(cls, task_config):
        pass


class GroupSubmission(TaskConfigItem):
    default = False

    @classmethod
    def get_template(cls):
        return "course_admin/task_dispensers/config_items/groups.html"

    @classmethod
    def get_id(cls):
        return "group_submission"

    @classmethod
    def get_name(cls):
        return _("Submission mode")

    @classmethod
    def get_value(cls, task_config):
        group_submission = task_config.get(cls.get_id(), cls.default)
        if not type(group_submission) == bool:
            raise InvalidTocException("Invalid submission mode")
        return group_submission


class Weight(TaskConfigItem):
    default = 1

    @classmethod
    def get_template(cls):
        return "course_admin/task_dispensers/config_items/weight.html"

    @classmethod
    def get_id(cls):
        return "weight"

    @classmethod
    def get_name(cls):
        return _("Weight")

    @classmethod
    def get_value(cls, task_config):
        weight = task_config.get(cls.get_id(), cls.default)
        if not (type(weight) == float or type(weight) == int):
            raise InvalidTocException("The weight value must be a numeric >= 0 ")
        elif weight < 0:
            raise InvalidTocException("The weight value must be a numeric >= 0")
        return weight


class SubmissionStorage(TaskConfigItem):
    default = 0

    @classmethod
    def get_template(cls):
        return "course_admin/task_dispensers/config_items/submission_storage.html"

    @classmethod
    def get_id(cls):
        return "no_stored_submissions"

    @classmethod
    def get_name(cls):
        return _("Submission storage")

    @classmethod
    def get_value(cls, task_config):
        no_stored_submissions = task_config.get(cls.get_id(), cls.default)
        if not type(no_stored_submissions) == int:
            raise InvalidTocException("The store submission must be an integer > 1 ")
        elif no_stored_submissions < 0:
            raise InvalidTocException("The store submission must be an integer > 1")
        return no_stored_submissions


class EvaluationMode(TaskConfigItem):
    default = "best"

    @classmethod
    def get_template(cls):
        return "course_admin/task_dispensers/config_items/evaluation_mode.html"

    @classmethod
    def get_id(cls):
        return "evaluation_mode"

    @classmethod
    def get_name(cls):
        return _("Evaluation mode")

    @classmethod
    def get_value(cls, task_config):
        evaluation_mode = task_config.get(cls.get_id(), cls.default)
        if evaluation_mode != "best" and evaluation_mode != "last":
            raise InvalidTocException("The evaluation mode must be either best or last but is " + str(evaluation_mode))
        return evaluation_mode


class Categories(TaskConfigItem):
    default = []

    @classmethod
    def get_template(cls):
        return "course_admin/task_dispensers/config_items/categories.html"

    @classmethod
    def get_id(cls):
        return "categories"

    @classmethod
    def get_name(cls):
        return _("Categories")

    @classmethod
    def get_value(cls, task_config):
        categories = task_config.get(cls.get_id(), cls.default)
        if "" in categories:
            raise InvalidTocException("All categories must have a name but are :" + str(categories))
        return categories


class SubmissionLimit(TaskConfigItem):
    default = {"amount": -1, "period": -1}

    @classmethod
    def get_template(cls):
        return "course_admin/task_dispensers/config_items/submission_limit.html"

    @classmethod
    def get_id(cls):
        return "submission_limit"

    @classmethod
    def get_name(cls):
        return _("Submission limit")

    @classmethod
    def get_value(cls, task_config):
        submission_limit = task_config.get(cls.get_id(), cls.default)
        if not type(submission_limit["amount"]) == int or not type(submission_limit["period"]) == int:
            raise InvalidTocException("Invalid submission limit")
        elif submission_limit["amount"] < -1 or submission_limit["period"] < -1:
            raise InvalidTocException("Submission limit values must be higher than or equal to -1")
        return submission_limit


class Accessibility(TaskConfigItem):
    default = False

    @classmethod
    def get_template(cls):
        return "course_admin/task_dispensers/config_items/accessibility.html"

    @classmethod
    def get_id(cls):
        return "accessibility"

    @classmethod
    def get_name(cls):
        return _("Accessibility")

    @classmethod
    def get_value(cls, task_config):
        accessibility = task_config.get(cls.get_id(), cls.default)
        try:
            AccessibleTime(accessibility)
        except Exception as message:
            raise InvalidTocException("Invalid task accessibility : {}".format(message))
        return accessibility


class InvalidTocException(Exception):
    pass

class SectionsList(object):
    """ A list of section for a course structure """

    def __init__(self, structure):
        self._sections = []
        for section in structure:
            if "sections_list" in section:
                self._sections.append(NonTerminalSection(section))
            elif "tasks_list" in section:
                self._sections.append(TerminalSection(section))
            else:
                raise InvalidTocException(_("One section don't contain a sections list nor a tasks list"))

    def __iter__(self):
        return iter(self._sections)

    def is_empty(self):
        """
        :return: True if the list is empty false otherwise
        """
        return len(self._sections) == 0

    def get_tasks(self):
        """
        :return: The ordered list of all the tasks in the subsections
        """
        tasks = []
        for section in self._sections:
            tasks += section.get_tasks()
        return tasks

    def to_structure(self):
        """
        :return: The structure in YAML format
        """
        return [section.to_structure() for section in self._sections]


class Section(object):
    def __init__(self, structure):
        if "title" in structure and structure["title"] != "":
            self._title = structure["title"]
        else:
            raise InvalidTocException(_("No title for one section"))
        self._config = structure["config"] if "config" in structure else {}

    def get_title(self):
        """
        :return: the title of this section
        """
        return self._title

    def get_config(self):
        """
        :return: the config dict of this section
        """
        return self._config


class NonTerminalSection(Section):
    def __init__(self, structure):
        Section.__init__(self, structure)
        self._sections_list = SectionsList(structure["sections_list"])

    def is_terminal(self):
        return False

    def get_sections_list(self):
        """
        :return: the list of sub-sections of this section
        """
        return self._sections_list

    def is_empty(self):
        """
        :return: True if the section is empty false otherwise
        """
        return self._sections_list.is_empty()

    def get_tasks(self):
        """
        :return: The ordered list of all the tasks in the subsections
        """
        return self._sections_list.get_tasks()

    def to_structure(self):
        """
        :return: The structure in YAML format
        """
        return {"title": self._title, "sections_list": self._sections_list.to_structure()}


class TerminalSection(Section):
    def __init__(self, structure):
        Section.__init__(self, structure)
        if not all(id_checker(id) for id in structure["tasks_list"]):
            raise InvalidTocException(_("One task id contains non alphanumerical characters"))
        self._task_list = structure["tasks_list"]

    def is_terminal(self):
        return True

    def get_tasks(self):
        """
        :return: The ordered list of all the tasks in the section
        """
        return self._task_list

    def is_empty(self):
        """
        :return: True if the section is empty false otherwise
        """
        return len(self._task_list) == 0

    def to_structure(self):
        """
        :return: The structure in YAML format
        """
        return {
            "title": self._title,
            "tasks_list": self._task_list
        }


def check_toc(toc):
    """
    :param toc: the raw content of the table of content
    :return: (True, "Valid TOC") if the toc has a valid format and (False, The error message) otherwise
    """
    try:
        result = SectionsList(toc)
    except Exception as ex:
        return False, str(ex)
    return True, "Valid TOC"


def parse_tasks_config(task_list, config_items, data):
    """
    Parse the task settings and modify data to set default values if needed
    :param data: the raw content of the task settings
    """

    # Clean the config dict from unexpected tasks
    unexpected = [taskid for taskid in data if taskid not in task_list]
    for taskid in unexpected:
        del data[taskid]

    # Set default empty dict for missing tasks
    for taskid in task_list:
        data.setdefault(taskid, {})

    # Check each config validity
    for taskid, structure in data.items():
        try:
            for config_item in config_items:
                id = config_item.get_id()
                structure[id] = config_item.get_value(structure)
        except Exception as ex:
            raise InvalidTocException("In taskid {} : {}".format(taskid, str(ex)))


def check_task_config(task_list, config_items, data):
    """

    :param data: the raw content of the task settings
    :return:  (True, '') if the settings are valid or (False, The error message) otherwise
    """
    try:
        parse_tasks_config(task_list, config_items, data)
        return True, ''
    except Exception as ex:
        return False, str(ex)
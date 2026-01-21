from abc import ABCMeta, abstractmethod
from typing import Type

class TaskDispenser(metaclass=ABCMeta):
    legacy_fields = {}

    def __init__(self, task_list_func, dispenser_data, course_id):
        """
        Instantiate a new TaskDispenser
        :param task_list_func: A function returning the list of available course tasks from the task factory
        :param dispenser_data: The dispenser data structure/configuration
        :param course_id: A String that is the id of the course
        """
        self._task_list_func = task_list_func
        self._course_id = course_id
        self._dispenser_data = dispenser_data

    @abstractmethod
    def get_no_stored_submissions(self, taskid):
        """Returns the maximum stored submission specified by the administrator"""
        pass

    @abstractmethod
    def get_evaluation_mode(self, taskid):
        """Returns the evaluation mode specified by the administrator"""
        pass

    @abstractmethod
    def get_group_submission(self):
        """ Indicates if the task submission mode is per groups """
        pass

    @abstractmethod
    def get_categories(self,taskid):
        """Returns the categories specified for the taskid by the administrator"""
        pass

    @abstractmethod
    def get_all_categories(self):
        """Returns the categories specified by the administrator"""
        pass

    @abstractmethod
    def get_course_grades(self, user_tasks, usernames):
        """Returns the current grade of the course for a set of users"""

    def get_course_grade(self, user_tasks, username):
        """Returns the current grade of the course for a specific user"""
        return self.get_course_grades(user_tasks, [username])[username]

    @abstractmethod
    def get_submission_limit(self, taskid):
        """ Returns the submission limits et for the task"""
        pass

    @classmethod
    @abstractmethod
    def get_id(cls):
        """ Returns the task dispenser id """
        pass

    @classmethod
    @abstractmethod
    def get_name(cls, language):

        """ Returns the localized task dispenser name """
        pass

    @abstractmethod
    def get_dispenser_data(self):
        """ Returns the task dispenser data structure """
        pass

    @abstractmethod
    def render_edit(self, course, task_data, task_errors):
        """ Returns the formatted task list edition form """
        pass

    @abstractmethod
    def render(self, course, tasks_data, tag_list,username):
        """ Returns the formatted task list"""
        pass

    def handle_settings(self, course, dispenser_settings):
        """ Handles the setting of the dispenser data from the possible task list edition form """
        pass

    @abstractmethod
    def check_dispenser_data(self, dispenser_data):
        """ Checks the dispenser data as formatted by the form from render_edit function """
        pass

    @abstractmethod
    def get_accessibilities(self, taskids, usernames):
        """ Returns the AccessibleTime instance for a set of taskids and usernames """
        pass

    def get_accessibility(self, taskid, username):
        """ Returns the AccessibleTime instance for a taskid and username """
        result = self.get_accessibilities([taskid], [username])
        return result[username][taskid]

    def get_user_task_list(self, usernames):
        """
        Returns the user task list that are eligible for grade computation
        :param usernames: List of usernames for which get the user task list
        :return: Returns a dictionary with username as key and the user task list as value
        """
        taskids = self._task_list_func()
        result = self.get_accessibilities(taskids, usernames)

        return {username: [taskid for taskid in result[username].keys() if result[username][taskid].after_start()] for username in result}

    @abstractmethod
    def get_ordered_tasks(self):
        """ Returns a serialized version of the tasks structure as an OrderedDict"""
        pass

    def has_legacy_tasks(self):
        """ Checks if the task files contains dispenser settings """
        return False

    def import_legacy_tasks(self):
        """ Imports the task dispenser settings from a task file dict """
        pass

_task_dispensers = {}

def get_task_dispensers() -> dict[str, TaskDispenser]:
    """Returns a mapping between registered task dispensers ids and classes"""
    return _task_dispensers


def register_task_dispenser(task_dispenser : Type[TaskDispenser]):
    """ Register a task dispenser using its class """
    _task_dispensers[task_dispenser.get_id()] = task_dispenser

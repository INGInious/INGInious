# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Factory for loading courses from disk """
import logging

from inginious.common.filesystems import FileSystemProvider
from inginious.common.log import get_course_logger
from inginious.common.base import id_checker, get_json_or_yaml, loads_json_or_yaml
from inginious.frontend.plugin_manager import PluginManager
from inginious.common.exceptions import InvalidNameException, CourseNotFoundException, CourseUnreadableException, CourseAlreadyExistsException

from inginious.frontend.courses import Course
from inginious.frontend.task_factory import TaskFactory


class CourseFactory(object):
    """ Load courses from disk """
    _logger = logging.getLogger("inginious.course_factory")

    def __init__(self, filesystem: FileSystemProvider, task_factory, plugin_manager, task_dispensers):
        self._filesystem = filesystem
        self._task_factory = task_factory
        self._plugin_manager = plugin_manager
        self._task_dispensers = task_dispensers
        self._cache = {}

    def add_task_dispenser(self, task_dispenser):
        """
        :param task_dispenser: TaskDispenser class
        """
        self._task_dispensers.update({task_dispenser.get_id(): task_dispenser})

    def get_task_dispensers(self):
        """
        Returns the supported task dispensers by this course factory
        """
        return self._task_dispensers

    def get_course(self, courseid):
        """
        :param courseid: the course id of the course
        :raise: InvalidNameException, CourseNotFoundException, CourseUnreadableException
        :return: an object representing the course, of the type given in the constructor
        """
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)
        if self._cache_update_needed(courseid):
            self._update_cache(courseid)

        return self._cache[courseid][0]

    def get_task(self, courseid, taskid):
        """
        Shorthand for CourseFactory.get_course(courseid).get_task(taskid)
        :param courseid: the course id of the course
        :param taskid: the task id of the task
        :raise InvalidNameException, CourseNotFoundException, CourseUnreadableException, TaskNotFoundException, TaskUnreadableException
        :return: an object representing the task, of the type given in the constructor
        """
        return self.get_course(courseid).get_task(taskid)

    def get_task_factory(self):
        """
        :return: the associated task factory
        """
        return self._task_factory

    def get_course_descriptor_content(self, courseid):
        """
        :param courseid: the course id of the course
        :raise: InvalidNameException, CourseNotFoundException, CourseUnreadableException
        :return: the content of the dict that describes the course
        """
        path = self._get_course_descriptor_path(courseid)
        return loads_json_or_yaml(path, self._filesystem.get(path).decode("utf-8"))

    def update_course_descriptor_content(self, courseid, content):
        """
        Updates the content of the dict that describes the course
        :param courseid: the course id of the course
        :param content: the new dict that replaces the old content
        :raise InvalidNameException, CourseNotFoundException
        """
        path = self._get_course_descriptor_path(courseid)
        self._filesystem.put(path, get_json_or_yaml(path, content))

    def update_course_descriptor_element(self, courseid, key, value):
        """
        Updates the value for the key in the dict that describes the course
        :param courseid: the course id of the course
        :param key: the element to change in the dict
        :param value: the new value that replaces the old one
        :raise InvalidNameException, CourseNotFoundException
        """
        course_structure = self.get_course_descriptor_content(courseid)
        course_structure[key] = value
        self.update_course_descriptor_content(courseid, course_structure)

    def get_fs(self):
        """
        :return: a FileSystemProvider pointing to the task directory
        """
        return self._filesystem

    def get_course_fs(self, courseid):
        """
        :param courseid: the course id of the course
        :return: a FileSystemProvider pointing to the directory of the course 
        """
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)
        return self._filesystem.from_subfolder(courseid)

    def get_all_courses(self):
        """
        :return: a table containing courseid=>Course pairs
        """
        course_ids = [f[0:len(f)-1] for f in self._filesystem.list(folders=True, files=False, recursive=False)]  # remove trailing "/"
        output = {}
        for courseid in course_ids:
            try:
                output[courseid] = self.get_course(courseid)
            except Exception:
                get_course_logger(courseid).warning("Cannot open course", exc_info=True)
        return output

    def _get_course_descriptor_path(self, courseid):
        """
        :param courseid: the course id of the course
        :raise InvalidNameException, CourseNotFoundException
        :return: the path to the descriptor of the course
        """
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)
        course_fs = self.get_course_fs(courseid)
        if course_fs.exists("course.yaml"):
            return courseid+"/course.yaml"
        if course_fs.exists("course.json"):
            return courseid+"/course.json"
        raise CourseNotFoundException()

    def create_course(self, courseid, init_content):
        """
        Create a new course folder and set initial descriptor content, folder can already exist
        :param courseid: the course id of the course
        :param init_content: initial descriptor content
        :raise: InvalidNameException or CourseAlreadyExistsException
        """
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)

        course_fs = self.get_course_fs(courseid)
        course_fs.ensure_exists()

        if course_fs.exists("course.yaml") or course_fs.exists("course.json"):
            raise CourseAlreadyExistsException("Course with id " + courseid + " already exists.")
        else:
            course_fs.put("course.yaml", get_json_or_yaml("course.yaml", init_content))

        get_course_logger(courseid).info("Course %s created in the factory.", courseid)

    def delete_course(self, courseid):
        """
        Erase the content of the course folder
        :param courseid: the course id of the course
        :raise: InvalidNameException or CourseNotFoundException
        """
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)

        course_fs = self.get_course_fs(courseid)

        if not course_fs.exists():
            raise CourseNotFoundException()

        course_fs.delete()

        get_course_logger(courseid).info("Course %s erased from the factory.", courseid)

    def _cache_update_needed(self, courseid):
        """
        :param courseid: the (valid) course id of the course
        :raise InvalidNameException, CourseNotFoundException
        :return: True if an update of the cache is needed, False else
        """
        if courseid not in self._cache:
            return True

        try:
            descriptor_name = self._get_course_descriptor_path(courseid)
            last_update = {descriptor_name: self._filesystem.get_last_modification_time(descriptor_name)}
            translations_fs = self._filesystem.from_subfolder("$i18n")
            if translations_fs.exists():
                for f in translations_fs.list(folders=False, files=True, recursive=False):
                    lang = f[0:len(f) - 3]
                    if translations_fs.exists(lang + ".mo"):
                        last_update["$i18n/" + lang + ".mo"] = translations_fs.get_last_modification_time(lang + ".mo")
        except:
            raise CourseNotFoundException()

        last_modif = self._cache[courseid][1]
        for filename, mftime in last_update.items():
            if filename not in last_modif or last_modif[filename] < mftime:
                return True

        return False

    def _update_cache(self, courseid):
        """
        Updates the cache
        :param courseid: the (valid) course id of the course
        :raise InvalidNameException, CourseNotFoundException, CourseUnreadableException
        """
        self._logger.info("Caching course {}".format(courseid))
        path_to_descriptor = self._get_course_descriptor_path(courseid)
        try:
            course_descriptor = loads_json_or_yaml(path_to_descriptor, self._filesystem.get(path_to_descriptor).decode("utf8"))
        except Exception as e:
            raise CourseUnreadableException(str(e))

        last_modif = {path_to_descriptor: self._filesystem.get_last_modification_time(path_to_descriptor)}
        translations_fs = self._filesystem.from_subfolder("$i18n")
        if translations_fs.exists():
            for f in translations_fs.list(folders=False, files=True, recursive=False):
                lang = f[0:len(f) - 3]
                if translations_fs.exists(lang + ".mo"):
                    last_modif["$i18n/" + lang + ".mo"] = translations_fs.get_last_modification_time(lang + ".mo")

        self._cache[courseid] = (
            Course(courseid, course_descriptor, self.get_course_fs(courseid), self._task_factory, self._plugin_manager, self._task_dispensers),
            last_modif
        )

        self._task_factory.update_cache_for_course(courseid)


def create_factories(fs_provider, task_dispensers, task_problem_types, plugin_manager=None):
    """
    Shorthand for creating Factories
    :param fs_provider: A FileSystemProvider leading to the courses
    :param plugin_manager: a Plugin Manager instance. If None, a new Hook Manager is created
    :param task_class:
    :return: a tuple with two objects: the first being of type CourseFactory, the second of type TaskFactory
    """
    if plugin_manager is None:
        plugin_manager = PluginManager()

    task_factory = TaskFactory(fs_provider, plugin_manager, task_problem_types)
    return CourseFactory(fs_provider, task_factory, plugin_manager, task_dispensers), task_factory

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Factory for loading tasks from disk """

from os.path import splitext
from inginious.common.filesystems import FileSystemProvider
from inginious.common.log import get_course_logger
from inginious.common.base import id_checker, get_json_or_yaml, loads_json_or_yaml
from inginious.common.exceptions import InvalidNameException

from inginious.frontend.tasks import Task

class TaskFactory(object):
    """ Load courses from disk """

    def __init__(self, filesystem: FileSystemProvider):
        self._filesystem = filesystem
        self._cache = {}

    def get_task(self, course, taskid):
        """
        :param course: a Course object
        :param taskid: the task id of the task
        :raise: InvalidNameException, TaskNotFoundException, TaskUnreadableException
        :return: an object representing the task, of the type given in the constructor
        """
        return Task.get(taskid, course.get_fs())

    def get_task_fs(self, courseid, taskid):
        """
        :param courseid: the course id of the course
        :param taskid: the task id of the task
        :raise: InvalidNameException
        :return: A FileSystemProvider to the folder containing the task files
        """
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)
        if not id_checker(taskid):
            raise InvalidNameException("Task with invalid name: " + taskid)
        return self._filesystem.from_subfolder(courseid).from_subfolder(taskid)

    def get_readable_tasks(self, course):
        """ Returns the list of all available tasks in a course """
        course_fs = self._filesystem.from_subfolder(course.get_id())
        tasks = [
            task[0:len(task)-1]  # remove trailing /
            for task in course_fs.list(folders=True, files=False, recursive=False)
            if course_fs.from_subfolder(task).exists("task.yaml")
        ]
        return tasks

    def get_all_tasks(self, course):
        """
        :return: a table containing taskid=>Task pairs
        """
        tasks = self.get_readable_tasks(course)
        output = {}
        for task in tasks:
            try:
                output[task] = self.get_task(course, task)
            except:
                pass
        return output

    def update_cache_for_course(self, courseid):
        """
        Clean/update the cache of all the tasks for a given course (id)
        :param courseid:
        """
        to_drop = []
        for (cid, tid) in self._cache:
            if cid == courseid:
                to_drop.append(tid)
        for tid in to_drop:
            del self._cache[(courseid, tid)]

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Factory for loading tasks from disk """

from inginious.common.filesystems import FileSystemProvider

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
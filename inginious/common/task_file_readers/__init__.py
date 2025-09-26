# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Managers for handling the different format of task files """

from inginious.common.task_file_readers.yaml_reader import TaskYAMLFileReader

_task_readers = {TaskYAMLFileReader.get_ext(): TaskYAMLFileReader()}

def add_custom_task_file_manager(self, task_file_manager):
    """ Add a custom task file manager """
    global _task_readers
    _task_readers[task_file_manager.get_ext()] = task_file_manager

def get_task_file_managers():
    """ Get a list of all the extensions possible for task descriptors """
    return _task_readers
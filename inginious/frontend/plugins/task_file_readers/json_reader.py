# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" JSON task file manager. """
import collections
import json

from inginious.common.task_file_readers.abstract_reader import AbstractTaskFileReader


class TaskJSONFileReader(AbstractTaskFileReader):
    """ Read and write task descriptions in JSON """

    def load(self, content):
        return json.loads(content, object_pairs_hook=collections.OrderedDict)

    @classmethod
    def get_ext(cls):
        return "json"

    def dump(self, data):
        return json.dumps(data, sort_keys=False, indent=4, separators=(',', ': '))


def init(plugin_manager, _3):
    """
        Init the plugin. Configuration:
        ::

            plugins:
                - plugin_module: inginious.frontend.plugins.task_file_readers.json_reader
    """

    plugin_manager.add_task_file_manager(TaskJSONFileReader())

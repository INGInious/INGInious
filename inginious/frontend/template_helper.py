# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" TemplateManager """
import os
from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, select_autoescape
import inginious

class TemplateHelper(object):
    """ Class accessible from templates that calls function defined in the Python part of the code. """

    def __init__(self, plugin_manager, use_minified=True):
        """
        Init the Template Helper
        :param plugin_manager: an instance of a PluginManager
        :param use_minified: weither to use minified js/css or not. Use True in production, False in dev envs.
        """
        self._base_helpers = {"task_list_item": (lambda **kwargs: self._generic_hook('task_list_item', **kwargs)),
                              "task_menu": (lambda **kwargs: self._generic_hook('task_menu', **kwargs))}
        self._plugin_manager = plugin_manager
        self._template_dir = 'frontend/templates'
        self._template_globals = {}

        self.add_to_template_globals("template_helper", self)
        self.add_to_template_globals("plugin_manager", plugin_manager)
        self.add_to_template_globals("use_minified", use_minified)

    def add_to_template_globals(self, name, value):
        """ Add a variable to will be accessible in the templates """
        self._template_globals[name] = value

    def render(self, path, template_folder="", **tpl_kwargs):
        """
        Parse the Jinja template named "path" and render it with args ``*tpl_args`` and ``**tpl_kwargs``
        :param path: Path of the template, relative to the base folder
        :param template_folder: add the specified folder to the templates PATH.
        :param tpl_kwargs: named args sent to the template
        :return: the rendered template, as a str
        """
        env = self._get_jinja_renderer(template_folder)
        env.globals.update(dict(self._plugin_manager.call_hook("template_helper")))
        return self._get_jinja_renderer(template_folder).get_template(path).render(**tpl_kwargs)

    @lru_cache(None)
    def _get_jinja_renderer(self, template_folder=""):
        # Always include the main template folder
        template_folders = [os.path.join(inginious.get_root_path(), self._template_dir)]

        # Include the additional template folder if specified
        if template_folder:
            template_folders += [os.path.join(inginious.get_root_path(), template_folder)]

        env = Environment(loader=FileSystemLoader(template_folders),
                          autoescape=select_autoescape(['html', 'htm', 'xml']))
        env.globals.update(self._template_globals)

        return env

    def call(self, name, **kwargs):
        helpers = dict(list(self._base_helpers.items()))
        if helpers.get(name, None) is None:
            return ""
        else:
            return helpers[name](**kwargs)

    def add_other(self, name, func):
        """ Add another callback to the template helper """
        self._base_helpers[name] = func

    def _generic_hook(self, name, **kwargs):
        """ A generic hook that links the TemplateHelper with PluginManager """
        entries = [entry for entry in self._plugin_manager.call_hook(name, **kwargs) if entry is not None]
        return "\n".join(entries)

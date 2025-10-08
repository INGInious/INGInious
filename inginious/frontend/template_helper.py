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
        self._base_helpers = {"header_hook": (lambda **kwargs: self._generic_hook('header_html', **kwargs)),
                              "main_menu": (lambda **kwargs: self._generic_hook('main_menu', **kwargs)),
                              "course_menu": (lambda **kwargs: self._generic_hook('course_menu', **kwargs)),
                              "submission_admin_menu": (lambda **kwargs: self._generic_hook('submission_admin_menu', **kwargs)),
                              "task_list_item": (lambda **kwargs: self._generic_hook('task_list_item', **kwargs)),
                              "task_menu": (lambda **kwargs: self._generic_hook('task_menu', **kwargs)),
                              "welcome_text": (lambda **kwargs: self._generic_hook('welcome_text', **kwargs)),
                              "javascript_header": (lambda **_: self._javascript_helper("header")),
                              "javascript_footer": (lambda **_: self._javascript_helper("footer")),
                              "css": (lambda **_: self._css_helper())}
        self._plugin_manager = plugin_manager
        self._template_dir = 'frontend/templates'
        self._template_globals = {}
        self._ctx = {"javascript": {"footer": [], "header": []}, "css": []}

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
        helpers = dict(list(self._base_helpers.items()) + self._plugin_manager.call_hook("template_helper"))
        if helpers.get(name, None) is None:
            return ""
        else:
            return helpers[name](**kwargs)

    def add_javascript(self, link, position="footer"):
        """ Add a javascript file to load. Position can either be "header" or "footer" """
        self._ctx["javascript"][position].append(link)

    def add_css(self, link):
        """ Add a css file to load """
        self._ctx["css"].append(link)

    def add_other(self, name, func):
        """ Add another callback to the template helper """
        self._base_helpers[name] = func

    def _javascript_helper(self, position):
        """ Add javascript links for the current page and for the plugins """
        if position not in ["header", "footer"]:
            position = "footer"

        # Load javascript files from plugins
        if position == "header":
            entries = [entry for entry in self._plugin_manager.call_hook("javascript_header") if entry is not None]
        else:
            entries = [entry for entry in self._plugin_manager.call_hook("javascript_footer") if entry is not None]
        # Load javascript for the current page
        entries += self._ctx["javascript"][position]
        entries = ["<script src='" + entry + "' type='text/javascript' charset='utf-8'></script>" for entry in entries]
        return "\n".join(entries)

    def _css_helper(self):
        """ Add CSS links for the current page and for the plugins """
        entries = [entry for entry in self._plugin_manager.call_hook("css") if entry is not None]
        # Load javascript for the current page
        entries += self._ctx["css"]
        entries = ["<link href='" + entry + "' rel='stylesheet'>" for entry in entries]
        return "\n".join(entries)

    def _generic_hook(self, name, **kwargs):
        """ A generic hook that links the TemplateHelper with PluginManager """
        entries = [entry for entry in self._plugin_manager.call_hook(name, **kwargs) if entry is not None]
        return "\n".join(entries)

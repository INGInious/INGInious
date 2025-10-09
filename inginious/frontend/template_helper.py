# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" TemplateManager """
from jinja2 import  FileSystemLoader
from flask import current_app, render_template
from inginious import get_root_path

class TemplateHelper(object):
    """ Class accessible from templates that calls function defined in the Python part of the code. """

    def __init__(self, plugin_manager):
        """
        Init the Template Helper
        :param plugin_manager: an instance of a PluginManager
        """
        self._plugin_manager = plugin_manager

    def render(self, path, template_folder="", **tpl_kwargs):
        """
        Parse the Jinja template named "path" and render it with args ``*tpl_args`` and ``**tpl_kwargs``
        :param path: Path of the template, relative to the base folder
        :param template_folder: add the specified folder to the templates PATH.
        :param tpl_kwargs: named args sent to the template
        :return: the rendered template, as a str
        """
        # Include the additional template folder if specified
        if template_folder:
            current_app.jinja_loader = FileSystemLoader([get_root_path() + '/frontend/templates', template_folder])

        current_app.jinja_env.globals.update(dict(self._plugin_manager.call_hook("template_helper")))
        return render_template(path, **tpl_kwargs)

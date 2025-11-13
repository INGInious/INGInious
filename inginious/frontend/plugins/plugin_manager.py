# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Plugin Manager """
import importlib
import logging
import bisect

from jinja2 import  FileSystemLoader

from inginious.frontend.user_manager import AuthMethod
from inginious.frontend.task_problems import inspect_displayable_problem_types
from inginious.common.tasks_problems import register_problem_types


class PluginManagerNotLoadedException(Exception):
    pass


class PluginManager(object):
    """ Registers an manage plugins. The init method inits only the Hook Manager; you have to call the method load() to start the plugins """

    def __init__(self):
        self._logger = logging.getLogger("inginious.frontend.plugin_manager")
        self._hooks = {}
        self._loaded = False
        self._webpy_app = None
        self._flask_app = None
        self._database = None
        self._user_manager = None
        self._submission_manager = None

    def _exception_free_callback(self, callback, *args, **kwargs):
        """ A wrapper that remove all exceptions raised from hooks """
        try:
            return callback(*args, **kwargs)
        except Exception:
            self._logger.exception("An exception occurred while calling a hook! ",exc_info=True)
            return None

    def add_hook(self, name, callback, prio=0):
        """ Add a new hook that can be called with the call_hook function.
            `prio` is the priority. Higher priority hooks are called before lower priority ones.
            This function does not enforce a particular order between hooks with the same priorities.
        """
        hook_list = self._hooks.get(name, [])

        add = (lambda *args, **kwargs: self._exception_free_callback(callback, *args, **kwargs)), -prio
        pos = bisect.bisect_right(list(x[1] for x in hook_list), -prio)
        hook_list[pos:pos] = [add]

        self._hooks[name] = hook_list

    def call_hook(self, name, **kwargs):
        """ Call all hooks registered with this name. Returns a list of the returns values of the hooks (in the order the hooks were added)"""
        return [y for y in [x(**kwargs) for x, _ in self._hooks.get(name, [])] if y is not None]

    def call_hook_recursive(self, name, **kwargs):
        """ Call all hooks registered with this name. Each hook receives as arguments the return value of the
            previous hook call, or the initial params for the first hook. As such, each hook must return a dictionary
            with the received (eventually modified) args. Returns the modified args."""
        for x, _ in self._hooks.get(name, []):
            out = x(**kwargs)
            if out is not None: #ignore already reported failure
                kwargs = out
        return kwargs

    def load(self, client, flask_app, course_factory, database, user_manager, submission_manager, config):
        """ Loads the plugin manager. Must be done after the initialisation of the client """
        self._flask_app = flask_app
        self._database = database
        self._user_manager = user_manager
        self._submission_manager = submission_manager
        self._loaded = True
        for entry in config:
            module_name = entry["plugin_module"]
            module = importlib.import_module(module_name)

            """ Load DisplayableProblem sub-classes """
            displayable_pbl_types = inspect_displayable_problem_types(module_name)
            register_problem_types(displayable_pbl_types)

            """ Initialize the module """
            module.init(self, course_factory, client, entry)

    def add_page(self, pattern, classname_or_viewfunc):
        """ Add a new page to the web application. Only available after that the Plugin Manager is loaded """
        if not self._loaded:
            raise PluginManagerNotLoadedException()

        self._flask_app.add_url_rule("/" + pattern[1:], view_func=classname_or_viewfunc)

    def register_auth_method(self, auth_method: AuthMethod):
        """
        Registers a new authentication method
        :param auth_method: a AuthMethod-based class
        """
        if not self._loaded:
            raise PluginManagerNotLoadedException()
        self._user_manager.register_auth_method(auth_method)

    def get_database(self):
        """ Returns the frontend database"""
        return self._database

    def get_submission_manager(self):
        """ Returns the submission manager"""
        return self._submission_manager

    def get_user_manager(self):
        """ Returns the user manager"""
        return self._user_manager

    def add_template_prefix(self, prefix : str, folder : str):
        """
        Adds a template folder served for all templates prefixed by indicated prefix
        :param prefix: prefix the template folder is served from.
        :param folder: abolute path to the template folder.
        """
        mapping = self._flask_app.jinja_loader.loaders[1].mapping
        if prefix in mapping:
            raise Exception("Template prefix already registered")

        mapping[prefix] = FileSystemLoader(folder)

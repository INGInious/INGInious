# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Starts the webapp """
import builtins
import os
import sys
import flask
import pymongo
import oauthlib
import gettext

from gridfs import GridFS
from binascii import hexlify
from pymongo import MongoClient
from werkzeug.exceptions import InternalServerError

import inginious.frontend.pages.course_admin.utils as course_admin_utils
import inginious.frontend.pages.preferences.utils as preferences_utils
from inginious.frontend.environment_types import register_base_env_types
from inginious.frontend.arch_helper import create_arch, start_asyncio_and_zmq
from inginious.frontend.pages.utils import register_utils
from inginious.frontend.plugin_manager import PluginManager
from inginious.frontend.submission_manager import WebAppSubmissionManager
from inginious.frontend.submission_manager import update_pending_jobs
from inginious.frontend.template_helper import TemplateHelper
from inginious.frontend.user_manager import UserManager
from inginious.frontend.l10n_manager import L10nManager
from inginious import get_root_path, __version__, DB_VERSION
from inginious.frontend.course_factory import create_factories
from inginious.common.entrypoints import filesystem_from_config_dict
from inginious.common.filesystems.local import LocalFSProvider
from inginious.frontend.lti_outcome_manager import LTIOutcomeManager
from inginious.frontend.task_problems import get_default_displayable_problem_types
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.frontend.task_dispensers.combinatory_test import CombinatoryTest
from inginious.frontend.flask.mapping import init_flask_mapping, init_flask_maintenance_mapping
from inginious.frontend.flask.mongo_sessions import MongoDBSessionInterface
from inginious.frontend.flask.mail import mail

def _put_configuration_defaults(config):
    """
    :param config: the basic configuration as a dict
    :return: the same dict, but with defaults for some unfilled parameters
    """
    if 'allowed_file_extensions' not in config:
        config['allowed_file_extensions'] = [".c", ".cpp", ".java", ".oz", ".zip", ".tar.gz", ".tar.bz2", ".txt"]
    if 'max_file_size' not in config:
        config['max_file_size'] = 1024 * 1024

    if 'session_parameters' not in config or 'secret_key' not in config['session_parameters']:
        print("Please define a secret_key in the session_parameters part of the configuration.", file=sys.stderr)
        print("You can simply add the following (the text between the lines, without the lines) "
              "to your INGInious configuration file. We generated a random key for you.", file=sys.stderr)
        print("-------------", file=sys.stderr)
        print("session_parameters:", file=sys.stderr)
        print('\ttimeout: 86400  # 24 * 60 * 60, # 24 hours in seconds', file=sys.stderr)
        print('\tignore_change_ip: False # change this to True if you want user to keep their session if they change their IP', file=sys.stderr)
        print('\tsecure: False # change this to True if you only use https', file=sys.stderr)
        print('\tsecret_key: "{}"'.format(hexlify(os.urandom(32)).decode('utf-8')), file=sys.stderr)
        print("-------------", file=sys.stderr)
        exit(1)

    if 'session_parameters' not in config:
        config['session_parameters'] = {}
    default_session_parameters = {
        "cookie_name": "inginious_session_id",
        "cookie_domain": None,
        "cookie_path": None,
        "samesite": "Lax",
        "timeout": 86400,  # 24 * 60 * 60, # 24 hours in seconds
        "ignore_change_ip": False,
        "httponly": True,
        "secret_key": "fLjUfxqXtfNoIldA0A0G",
        "secure": False
    }
    for k, v in default_session_parameters.items():
        if k not in config['session_parameters']:
            config['session_parameters'][k] = v

    # flask migration
    config["DEBUG"] = config.get("web_debug", False)
    config["SESSION_COOKIE_NAME"] = "inginious_session_id"
    config["SESSION_USE_SIGNER"] = True
    config["PERMANENT_SESSION_LIFETIME"] = config['session_parameters']["timeout"]
    config["SECRET_KEY"] = config['session_parameters']["secret_key"]

    smtp_conf = config.get('smtp', None)
    if smtp_conf is not None:
        config["MAIL_SERVER"] = smtp_conf["host"]
        config["MAIL_PORT"] = int(smtp_conf["port"])
        config["MAIL_USE_TLS"] = bool(smtp_conf.get("starttls", False))
        config["MAIL_USE_SSL"] = bool(smtp_conf.get("usessl", False))
        config["MAIL_USERNAME"] = smtp_conf.get("username", None)
        config["MAIL_PASSWORD"] = smtp_conf.get("password", None)
        config["MAIL_DEFAULT_SENDER"] = smtp_conf.get("sendername", "no-reply@ingnious.org")

    return config

def get_homepath():
    """ Returns the URL root. """
    return flask.request.url_root[:-1]

def get_path(*path_parts, force_cookieless=False):
    """
    :param path_parts: List of elements in the path to be separated by slashes
    :param force_cookieless: Force the cookieless session; the link will include the session_creator if needed.
    """
    session = flask.session
    request = flask.request
    query_delimiter = '&' if path_parts and '?' in path_parts[-1] else '?'
    path_parts = (get_homepath(), ) + path_parts
    if session.sid is not None and session.cookieless:
        return "/".join(path_parts) + f"{query_delimiter}session_id={session.sid}"
    if force_cookieless:
        return "/".join(path_parts) + f"{query_delimiter}session_id="
    return "/".join(path_parts)


def _close_app(mongo_client, client):
    """ Ensures that the app is properly closed """
    client.close()
    mongo_client.close()


def get_app(config):
    """
    :param config: the configuration dict
    :return: A new app
    """
    # First, disable debug. It will be enabled in the configuration, later.

    config = _put_configuration_defaults(config)
    mongo_client = MongoClient(host=config.get('mongo_opt', {}).get('host', 'localhost'))
    database = mongo_client[config.get('mongo_opt', {}).get('database', 'INGInious')]
    gridfs = GridFS(database)

    # Init database if needed
    db_version = database.db_version.find_one({})
    if db_version is None:
        database.submissions.create_index([("username", pymongo.ASCENDING)])
        database.submissions.create_index([("courseid", pymongo.ASCENDING)])
        database.submissions.create_index([("courseid", pymongo.ASCENDING), ("taskid", pymongo.ASCENDING)])
        database.submissions.create_index([("submitted_on", pymongo.DESCENDING)])  # sort speed
        database.submissions.create_index([("status", pymongo.ASCENDING)]) # update_pending_jobs speedup
        database.user_tasks.create_index(
            [("username", pymongo.ASCENDING), ("courseid", pymongo.ASCENDING), ("taskid", pymongo.ASCENDING)],
            unique=True)
        database.user_tasks.create_index([("username", pymongo.ASCENDING), ("courseid", pymongo.ASCENDING)])
        database.user_tasks.create_index([("courseid", pymongo.ASCENDING), ("taskid", pymongo.ASCENDING)])
        database.user_tasks.create_index([("courseid", pymongo.ASCENDING)])
        database.user_tasks.create_index([("username", pymongo.ASCENDING)])
        database.db_version.insert_one({"db_version": DB_VERSION})
    elif db_version.get("db_version", 0) != DB_VERSION:
        raise Exception("Please update the database before running INGInious")

    flask_app = flask.Flask(__name__)

    flask_app.config.from_mapping(**config)
    flask_app.session_interface = MongoDBSessionInterface(
        mongo_client, config.get('mongo_opt', {}).get('database', 'INGInious'),
        "sessions", config.get('SESSION_USE_SIGNER', False), True  # config.get('SESSION_PERMANENT', True)
    )

    # Init gettext
    available_translations = {
        "de": "Deutsch",
        "el": "ελληνικά",
        "es": "Español",
        "fr": "Français",
        "he": "עִבְרִית",
        "nl": "Nederlands",
        "nb_NO": "Norsk (bokmål)",
        "pt": "Português",
        "vi": "Tiếng Việt"
    }

    available_languages = {"en": "English"}
    available_languages.update(available_translations)

    # available indentation types
    available_indentation_types = {
        "2": {"text": "2 spaces", "indent": 2, "indentWithTabs": False},
        "3": {"text": "3 spaces", "indent": 3, "indentWithTabs": False},
        "4": {"text": "4 spaces", "indent": 4, "indentWithTabs": False},
        "tabs": {"text": "tabs", "indent": 4, "indentWithTabs": True},
    }

    l10n_manager = L10nManager()

    l10n_manager.translations["en"] = gettext.NullTranslations()  # English does not need translation ;-)
    for lang in available_translations.keys():
        l10n_manager.translations[lang] = gettext.translation('messages', get_root_path() + '/frontend/i18n', [lang])

    builtins.__dict__['_'] = l10n_manager.gettext

    if config.get("maintenance", False):
        template_helper = TemplateHelper(PluginManager(), None, config.get('use_minified_js', True))
        template_helper.add_to_template_globals("get_homepath", get_homepath)
        template_helper.add_to_template_globals("get_path", get_path)
        template_helper.add_to_template_globals("pkg_version", __version__)
        template_helper.add_to_template_globals("available_languages", available_languages)
        template_helper.add_to_template_globals("_", _)
        flask_app.template_helper = template_helper
        init_flask_maintenance_mapping(flask_app)
        return flask_app.wsgi_app, lambda: None

    default_allowed_file_extensions = config['allowed_file_extensions']
    default_max_file_size = config['max_file_size']

    zmq_context, __ = start_asyncio_and_zmq(config.get('debug_asyncio', False))

    # Init the different parts of the app
    plugin_manager = PluginManager()

    # Add the "agent types" inside the frontend, to allow loading tasks and managing envs
    register_base_env_types()

    # Create the FS provider
    if "fs" in config:
        fs_provider = filesystem_from_config_dict(config["fs"])
    else:
        task_directory = config["tasks_directory"]
        fs_provider = LocalFSProvider(task_directory)

    default_task_dispensers = {
        task_dispenser.get_id(): task_dispenser for task_dispenser in [TableOfContents, CombinatoryTest]
    }

    default_problem_types = get_default_displayable_problem_types()

    course_factory, task_factory = create_factories(fs_provider, default_task_dispensers, default_problem_types, plugin_manager, database)

    user_manager = UserManager(database, config.get('superadmins', []))

    update_pending_jobs(database)

    client = create_arch(config, fs_provider, zmq_context, course_factory)

    lti_outcome_manager = LTIOutcomeManager(database, user_manager, course_factory)

    submission_manager = WebAppSubmissionManager(client, user_manager, database, gridfs, plugin_manager, lti_outcome_manager)
    template_helper = TemplateHelper(plugin_manager, user_manager, config.get('use_minified_js', True))

    register_utils(database, user_manager, template_helper)

    is_tos_defined = config.get("privacy_page", "") and config.get("terms_page", "")

    # Init web mail
    mail.init_app(flask_app)

    # Add some helpers for the templates
    template_helper.add_to_template_globals("_", _)
    template_helper.add_to_template_globals("str", str)
    template_helper.add_to_template_globals("available_languages", available_languages)
    template_helper.add_to_template_globals("available_indentation_types", available_indentation_types)
    template_helper.add_to_template_globals("get_homepath", get_homepath)
    template_helper.add_to_template_globals("get_path", get_path)
    template_helper.add_to_template_globals("pkg_version", __version__)
    template_helper.add_to_template_globals("allow_registration", config.get("allow_registration", True))
    template_helper.add_to_template_globals("sentry_io_url", config.get("sentry_io_url"))
    template_helper.add_to_template_globals("user_manager", user_manager)
    template_helper.add_to_template_globals("default_allowed_file_extensions", default_allowed_file_extensions)
    template_helper.add_to_template_globals("default_max_file_size", default_max_file_size)
    template_helper.add_to_template_globals("is_tos_defined", is_tos_defined)
    template_helper.add_to_template_globals("privacy_page", config.get("privacy_page", None))
    template_helper.add_other("course_admin_menu",
                              lambda course, current: course_admin_utils.get_menu(course, current, template_helper.render,
                                                                                  plugin_manager, user_manager))
    template_helper.add_other("preferences_menu",
                              lambda current: preferences_utils.get_menu(config.get("allow_deletion", True),
                                                                         current, template_helper.render,
                                                                         plugin_manager, user_manager))

    # Not found page
    def flask_not_found(e):
        return template_helper.render("notfound.html", message=e.description), 404
    flask_app.register_error_handler(404, flask_not_found)

    # Forbidden page
    def flask_forbidden(e):
        return template_helper.render("forbidden.html", message=e.description), 403
    flask_app.register_error_handler(403, flask_forbidden)

    # Enable debug mode if needed
    web_debug = config.get('web_debug', False)
    flask_app.debug = web_debug
    oauthlib.set_debug(web_debug)

    def flask_internalerror(e):
        return template_helper.render("internalerror.html", message=e.description), 500
    flask_app.register_error_handler(InternalServerError, flask_internalerror)

    # Insert the needed singletons into the application, to allow pages to call them
    flask_app.get_path = get_path
    flask_app.plugin_manager = plugin_manager
    flask_app.course_factory = course_factory
    flask_app.task_factory = task_factory
    flask_app.submission_manager = submission_manager
    flask_app.user_manager = user_manager
    flask_app.l10n_manager = l10n_manager
    flask_app.template_helper = template_helper
    flask_app.database = database
    flask_app.gridfs = gridfs
    flask_app.client = client
    flask_app.default_allowed_file_extensions = default_allowed_file_extensions
    flask_app.default_max_file_size = default_max_file_size
    flask_app.backup_dir = config.get("backup_directory", './backup')
    flask_app.webterm_link = config.get("webterm", None)
    flask_app.lti_outcome_manager = lti_outcome_manager
    flask_app.allow_registration = config.get("allow_registration", True)
    flask_app.allow_deletion = config.get("allow_deletion", True)
    flask_app.available_languages = available_languages
    flask_app.available_indentation_types = available_indentation_types
    flask_app.welcome_page = config.get("welcome_page", None)
    flask_app.terms_page = config.get("terms_page", None)
    flask_app.privacy_page = config.get("privacy_page", None)
    flask_app.static_directory = config.get("static_directory", "./static")
    flask_app.webdav_host = config.get("webdav_host", None)

    # Init the mapping of the app
    init_flask_mapping(flask_app)

    # Loads plugins
    plugin_manager.load(client, flask_app, course_factory, task_factory, database, user_manager, submission_manager, config.get("plugins", []))

    # Start the inginious.backend
    client.start()

    return flask_app.wsgi_app, lambda: _close_app(mongo_client, client)

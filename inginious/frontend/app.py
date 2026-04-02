# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Starts the webapp """
import os
import sys
import flask
import jinja2
import oauthlib

from binascii import hexlify
from werkzeug.exceptions import InternalServerError
from mongoengine import connect, disconnect

from inginious.frontend.environment_types import register_base_env_types
from inginious.frontend.arch_helper import create_arch, start_asyncio_and_zmq
from inginious.frontend.plugins import plugin_manager
from inginious.frontend.submission_manager import WebAppSubmissionManager
from inginious.frontend.user_manager import UserManager
from inginious.frontend.i18n import available_languages, gettext
from inginious import __version__, DB_VERSION
from inginious.common.entrypoints import filesystem_from_config_dict
from inginious.common.filesystems import init_fs_provider
from inginious.common.filesystems.local import LocalFSProvider
from inginious.frontend.lti.v1_1 import LTIOutcomeManager
from inginious.frontend.lti.v1_3 import LTIGradeManager
from inginious.common.tasks_problems import register_problem_types
from inginious.frontend.task_problems import get_default_displayable_problem_types
from inginious.frontend.task_dispensers import register_task_dispenser
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.frontend.task_dispensers.combinatory_test import CombinatoryTest
from inginious.frontend.flask.mapping import init_flask_mapping, init_flask_maintenance_mapping
from inginious.frontend.flask.mongo_sessions import MongoDBSessionInterface
from inginious.frontend.flask.mail import mail
from inginious.frontend.models import DBVersion

def _put_configuration_defaults(config):
    """
    :param config: the basic configuration as a dict
    :return: the same dict, but with defaults for some unfilled parameters
    """
    session_parameters = config.get('session_parameters', None)
    if not session_parameters or 'secret_key' not in config['session_parameters']:
        print("Please define a secret_key in the session_parameters part of the configuration.", file=sys.stderr)
        print("You can simply add the following (the text between the lines, without the lines) "
              "to your INGInious configuration file. We generated a random key for you.", file=sys.stderr)
        print("-------------", file=sys.stderr)
        print("session_parameters:", file=sys.stderr)
        print('\ttimeout: 86400  # 24 * 60 * 60, # 24 hours in seconds', file=sys.stderr)
        print('\tsecure: False # change this to True if you only use https', file=sys.stderr)
        print('\tsecret_key: "{}"'.format(hexlify(os.urandom(32)).decode('utf-8')), file=sys.stderr)
        print("-------------", file=sys.stderr)
        exit(1)

    # Populate a sanitized new dict with upper chars for Flask
    new_config = {
        "ALLOWED_FILE_EXTENSIONS": config.get('allowed_file_extensions',
                                              [".c", ".cpp", ".java", ".oz", ".zip", ".tar.gz", ".tar.bz2", ".txt"]),
        "ALLOW_DELETION": config.get("allow_deletion", True),
        "ALLOW_REGISTRATION": config.get("allow_registration", True),
        "BACKEND": config.get("backend", "local"),
        "DEBUG": config.get("web_debug", False),
        "DEBUG_ASYNCIO": config.get('debug_asyncio', False),
        "LOCAL-CONFIG": config.get("local-config", {}),
        "MAINTENANCE": config.get("maintenance", False),
        "MAX_FILE_SIZE": config.get('max_file_size', 1024 * 1024),
        "MONGO_OPT": config.get("mongo_opt", {}),
        "PLUGINS": config.get("plugins", []),
        "STATIC_DIRECTORY": config.get("static_directory", "./static"),
        "SUPERADMINS": config.get("superadmins", []),
        "TASKS_DIRECTORY": config.get("tasks_directory", "./tasks"),
        "USE_MINIFIED_JS": config.get("use_minified_js", False),

        # Session config
        "PERMANENT_SESSION_LIFETIME": session_parameters.get("timeout", 86400),  # 24 hours
        "SECRET_KEY": session_parameters["secret_key"],
        "SESSION_USE_SIGNER": True,
        "SESSION_COOKIE_NAME": session_parameters.get("cookie_name", "inginious_session_id"),
        "SESSION_COOKIE_DOMAIN": session_parameters.get("cookie_domain", None),
        "SESSION_COOKIE_PATH": session_parameters.get("cookie_path", None),
        "SESSION_COOKIE_SAMESITE": session_parameters.get("samesite", "Lax"),
        "SESSION_COOKIE_HTTPONLY": session_parameters.get("httponly", True),
        "SESSION_COOKIE_SECURE": session_parameters.get("secure", False)
    }

    # SMTP config
    smtp_conf = config.get('smtp', None)
    if smtp_conf is not None:
        new_config.update({
            "MAIL_SERVER": smtp_conf["host"],
            "MAIL_PORT": int(smtp_conf["port"]),
            "MAIL_USE_TLS": bool(smtp_conf.get("starttls", False)),
            "MAIL_USE_SSL": bool(smtp_conf.get("usessl", False)),
            "MAIL_USERNAME": smtp_conf.get("username", None),
            "MAIL_PASSWORD": smtp_conf.get("password", None),
            "MAIL_DEFAULT_SENDER": smtp_conf.get("sendername", "no-reply@ingnious.org")
        })

    # Optional keys
    for key in ["fs", "privacy_page", "sentry_io_url", "terms_page", "webdav_host", "webterm"]:
        if key in config:
            new_config[key.upper()] = config[key]

    # indentation types and languages
    new_config["INDENTATION_TYPES"] = {
        "2": {"text": "2 spaces", "indent": 2, "indentWithTabs": False},
        "3": {"text": "3 spaces", "indent": 3, "indentWithTabs": False},
        "4": {"text": "4 spaces", "indent": 4, "indentWithTabs": False},
        "tabs": {"text": "tabs", "indent": 4, "indentWithTabs": True},
    }
    new_config["LANGUAGES"] = available_languages
    new_config["IS_TOS_DEFINED"] = "PRIVACY_PAGE" in new_config and "TERMS_PAGE" in new_config

    return new_config

def _close_app(client):
    """ Ensures that the app is properly closed """
    client.close()
    disconnect()

def get_app(config):
    """
    :param config: the configuration dict
    :return: A new app
    """
    config = _put_configuration_defaults(config)

    # Init database
    connect(config['MONGO_OPT'].get('database', 'INGInious'), host=config['MONGO_OPT'].get('host', 'localhost'), tz_aware=True)

    # Fetch or init DB version
    db_version = DBVersion.objects(db_version__exists=True).first() or DBVersion().save()
    if db_version.db_version != DB_VERSION:
        raise Exception("Please update the database before running INGInious")

    flask_app = flask.Flask(__name__)

    flask_app.config.from_mapping(**config)

    # config.get('SESSION_PERMANENT', True)
    flask_app.session_interface = MongoDBSessionInterface(config['SESSION_USE_SIGNER'], True)

    zmq_context, __ = start_asyncio_and_zmq(config['DEBUG_ASYNCIO'])

    # Add the "agent types" inside the frontend, to allow loading tasks and managing envs
    register_base_env_types()

    # Create the FS provider
    if "FS" in config:
        fs_provider = filesystem_from_config_dict(config["FS"])
    else:
        task_directory = config["TASKS_DIRECTORY"]
        fs_provider = LocalFSProvider(task_directory)

    init_fs_provider(fs_provider)

    register_task_dispenser(TableOfContents)
    register_task_dispenser(CombinatoryTest)

    register_problem_types(get_default_displayable_problem_types())

    user_manager = UserManager(config['SUPERADMINS'])

    client = create_arch(config, zmq_context)

    lti_score_publishers = {"1.1": LTIOutcomeManager(user_manager),
                            "1.3": LTIGradeManager(user_manager)}

    submission_manager = WebAppSubmissionManager(client, user_manager, lti_score_publishers)

    # Init web mail
    mail.init_app(flask_app)

    # Add some helpers for the templates
    flask_app.jinja_loader = jinja2.ChoiceLoader([flask_app.jinja_loader, jinja2.PrefixLoader({})])
    flask_app.jinja_env.globals["_"] = gettext
    flask_app.jinja_env.globals["str"] = str
    flask_app.jinja_env.globals["plugin_manager"] = plugin_manager
    flask_app.jinja_env.globals["pkg_version"] = __version__
    flask_app.jinja_env.globals["user_manager"] = user_manager

    @flask_app.context_processor
    def context_processor():
        return dict(plugin_manager.call_hook("template_helper"))

    @flask_app.url_defaults
    def add_lti_session_id(endpoint, values):
        if flask.session.is_lti:
            key = "lti_session_id" if endpoint in ["ltibindpage", "lti1.3bindpage"] else "session_id"
            values.setdefault(key, flask.session.id)

    # Not found page
    def flask_not_found(e):
        return flask.render_template("notfound.html", message=e.description), 404
    flask_app.register_error_handler(404, flask_not_found)

    # Forbidden page
    def flask_forbidden(e):
        return flask.render_template("forbidden.html", message=e.description), 403
    flask_app.register_error_handler(403, flask_forbidden)

    # Enable debug mode if needed
    flask_app.debug = config['DEBUG']
    oauthlib.set_debug(config['DEBUG'])

    def flask_internalerror(e):
        return flask.render_template("internalerror.html", message=e.description), 500
    flask_app.register_error_handler(InternalServerError, flask_internalerror)

    # Insert the needed singletons into the application, to allow pages to call them
    flask_app.submission_manager = submission_manager
    flask_app.user_manager = user_manager
    flask_app.client = client

    # Init the mapping of the app
    if config["MAINTENANCE"]:
        init_flask_maintenance_mapping(flask_app)
        return flask_app.wsgi_app, lambda: None
    else:
        init_flask_mapping(flask_app)

    # Loads plugins
    plugin_manager.load(client, flask_app, user_manager, submission_manager, config["PLUGINS"])

    # Start the inginious.backend
    client.start()

    return flask_app.wsgi_app, lambda: _close_app(client)

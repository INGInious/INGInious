# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Custom installer for the web app """

import hashlib
import os
import tarfile
import tempfile
import re
import urllib.request
from binascii import hexlify
import docker
from docker.errors import BuildError
from gridfs import GridFS
from pymongo import MongoClient
from inginious import __version__
import inginious.common.custom_yaml as yaml
from inginious.frontend.user_manager import UserManager

HEADER = '\033[95m'
INFO = '\033[94m'
OKGREEN = '\033[92m'
WARNING = '\033[33m'
WHITE = '\033[97m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'
DOC = '\033[39m'
BACKGROUND_RED = '\033[101m'


class Installer:
    """ Custom installer for the WebApp frontend """

    def __init__(self, config_path=None, default=False):
        self._config_path = config_path
        self._default = default

    #######################################
    #          Display functions          #
    #######################################

    def _display_header(self, title):
        """ Displays an header in the console """
        print("")
        print(BOLD + HEADER + "--- " + title + " ---" + ENDC)

    def _display_warning(self, content):
        """ Displays a warning in the console """
        print(WARNING + "(WARN) " + content + ENDC)

    def _display_info(self, content):
        """ Displays an info message in the console """
        print(INFO + "(INFO) " + content + ENDC)

    def _display_question(self, content):
        """ Displays a preamble to a question """
        print(DOC + content + ENDC)

    def _display_error(self, content):
        """ Displays an error """
        print(WHITE + BACKGROUND_RED + "(ERROR) " + content + ENDC)

    def _display_big_warning(self, content):
        """ Displays a BIG warning """
        print("")
        print(BOLD + WARNING + "--- WARNING ---" + ENDC)
        print(WARNING + content + ENDC)
        print("")

    def _ask_with_default(self, question, default=""):
        default = str(default)
        if self._default:
            answer = default
        else:
            answer = input(DOC + UNDERLINE + question + " [" + default + "]:" + ENDC + " ")
            if answer == "":
                answer = default
        return answer

    def _ask_boolean(self, question, default):
        while True:
            val = self._ask_with_default(question, ("yes" if default else "no")).lower()
            if val in ["yes", "y", "1", "true", "t"]:
                return True
            elif val in ["no", "n", "0", "false", "f"]:
                return False
            self._display_question("Please answer 'yes' or 'no'.")

    def _ask_integer(self, question, default):
        while True:
            try:
                return int(self._ask_with_default(question, default))
            except:
                pass

    def _configure_directory(self, dirtype: str):
        """Configure user specified directory and create it if required"""
        self._display_question("Please choose a directory in which to store the %s files." % dirtype)
        directory = None
        while directory is None:
            directory = self._ask_with_default("%s directory" % (dirtype[0].upper()+dirtype[1:]), "./%s" % dirtype)
            if not os.path.exists(directory):
                if self._ask_boolean("Path does not exist. Create directory?", True):
                    try:
                        os.makedirs(directory)
                    except FileExistsError:
                        pass # We should never reach this part since the path is verified above
                    except PermissionError:
                        self._display_error("Permission denied. Are you sure of your path?\nIf yes, contact your system administrator"
                                            " or create manually the directory with the correct user permissions.\nOtherwise, you may"
                                            " enter a new path now.")
                        directory = None
                else:
                    directory = None

        return os.path.abspath(directory)

    #######################################
    #            Main function            #
    #######################################

    def run(self):
        """ Run the installator """
        self._display_header("BACKEND CONFIGURATION")
        options = {}
        while True:
            options = {}
            backend = self.ask_backend()
            if backend == "local":
                self._display_info("Backend chosen: local. Testing the configuration.")
                options = self._ask_local_config()
                if not self.test_local_docker_conf():
                    self._display_error(
                        "An error occurred while testing the configuration. Please make sure you are able do run `docker info` in "
                        "your command line, and environment parameters like DOCKER_HOST are correctly set.")
                    if self._ask_boolean("Would you like to continue anyway?", False):
                        break
                else:
                    break
            else:
                self._display_warning(
                    "Backend chosen: manual. As it is a really advanced feature, you will have to configure it yourself in "
                    "the configuration file, at the end of the setup process.")
                options = {"backend": backend}
                break

        self._display_header("MONGODB CONFIGURATION")
        mongo_opt = self.configure_mongodb()
        options.update(mongo_opt)

        self._display_header("TASK DIRECTORY")
        task_directory_opt = self.configure_task_directory()
        options.update(task_directory_opt)

        self._display_header("CONTAINERS")
        self.select_containers_to_build()

        self._display_header("MISC")
        misc_opt = self.configure_misc()
        options.update(misc_opt)

        database = self.try_mongodb_opts(options["mongo_opt"]["host"], options["mongo_opt"]["database"])

        self._display_header("BACKUP DIRECTORY")
        backup_directory_opt = self.configure_backup_directory()
        options.update(backup_directory_opt)

        self._display_header("AUTHENTIFICATION")
        auth_opts = self.configure_authentication(database)
        options.update(auth_opts)

        self._display_info("You may want to add additional plugins to the configuration file.")

        self._display_header("REMOTE DEBUGGING - IN BROWSER")
        self._display_info(
            "If you want to activate the remote debugging of task in the users' browser, you have to install separately "
            "INGInious-xterm, which is available on Github, according to the parameters you have given for the hostname and the "
            "port range given in the configuration of the remote debugging.")
        self._display_info(
            "You can leave the following question empty to disable this feature; remote debugging will still be available, "
            "but not in the browser.")
        webterm = self._ask_with_default(
            "Please indicate the link to your installation of INGInious-xterm (for example: "
            "https://your-hostname.com:8080).", "")
        if webterm != "":
            options["webterm"] = webterm

        self._display_header("END")
        file_dir = self._config_path or os.path.join(os.getcwd(), self.configuration_filename())
        try:
            yaml.dump(options, open(file_dir, "w"))
            self._display_info("Successfully written the configuration file")
        except:
            self._display_error("Cannot write the configuration file on disk. Here is the content of the file")
            print(yaml.dump(options))

    #######################################
    #       Docker configuration          #
    #######################################

    def _ask_local_config(self):
        """ Ask some parameters about the local configuration """
        options = {"backend": "local", "local-config": {}}

        # Concurrency
        while True:
            concurrency = self._ask_with_default(
                "Maximum concurrency (number of tasks running simultaneously). Leave it empty to use the number of "
                "CPU of your host.", "")
            if concurrency == "":
                break

            try:
                concurrency = int(concurrency)
            except:
                self._display_error("Invalid number")
                continue

            if concurrency <= 0:
                self._display_error("Invalid number")
                continue

            options["local-config"]["concurrency"] = concurrency
            break

        # Debug hostname
        hostname = self._ask_with_default(
            "What is the external hostname/address of your machine? You can leave this empty and let INGInious "
            "autodetect it.", "")
        if hostname != "":
            options["local-config"]["debug_host"] = hostname
        self._display_info(
            "You can now enter the port range for the remote debugging feature of INGInious. Please verify that these "
            "ports are open in your firewall. You can leave this parameters empty, the default is 64100-64200")

        # Debug port range
        port_range = None
        while True:
            start_port = self._ask_with_default("Beginning of the range", "")
            if start_port != "":
                try:
                    start_port = int(start_port)
                except:
                    self._display_error("Invalid number")
                    continue
                end_port = self._ask_with_default("End of the range", str(start_port + 100))
                try:
                    end_port = int(end_port)
                except:
                    self._display_error("Invalid number")
                    continue
                if start_port > end_port:
                    self._display_error("Invalid range")
                    continue
                port_range = str(start_port) + "-" + str(end_port)
            else:
                break
        if port_range != None:
            options["local-config"]["debug_ports"] = port_range

        return options

    def test_local_docker_conf(self):
        """ Test to connect to a local Docker daemon """
        try:
            docker_connection = docker.from_env()
        except Exception as e:
            self._display_error("- Unable to connect to Docker. Error was %s" % str(e))
            return False

        try:
            self._display_info("- Asking Docker some info")
            if docker.utils.compare_version('1.24', docker_connection.version()['ApiVersion']) < 0:
                self._display_error("- Docker version >= 1.12.0 is required.")
                return False
        except Exception as e:
            self._display_error("- Unable to contact Docker. Error was %s" % str(e))
            return False
        self._display_info("- Successfully got info from Docker. Docker connection works.")

        return True

    def ask_backend(self):
        """ Ask the user to choose the backend """
        response = self._ask_boolean(
            "Do you have a local docker daemon (on Linux), do you use docker-machine via a local machine, or do you use "
            "Docker for macOS?", True)
        if (response):
            self._display_info("If you use docker-machine on macOS, please see "
                               "http://inginious.readthedocs.io/en/latest/install_doc/troubleshooting.html")
            return "local"
        else:
            self._display_info(
                "You will have to run inginious-backend and inginious-agent yourself. Please run the commands without argument "
                "and/or read the documentation for more info")
            return self._display_question("Please enter the address of your backend")

    #######################################
    #       MONGODB CONFIGURATION         #
    #######################################

    def try_mongodb_opts(self, host="localhost", database_name='INGInious'):
        """ Try MongoDB configuration """
        try:
            mongo_client = MongoClient(host=host)
            # Effective access only occurs when we call a method on the connexion
            mongo_version = str(mongo_client.server_info()['version'])
            self._display_info("Found mongodb server running version %s on %s." % (mongo_version, host))
        except Exception as e:
            self._display_warning("Cannot connect to MongoDB on host %s: %s" % (host, str(e)))
            return None

        try:
            database = mongo_client[database_name]
            # Effective access only occurs when we call a method on the database.
            database.list_collection_names()
        except Exception as e:
            self._display_warning("Cannot access database %s: %s" % (database_name, str(e)))
            return None

        try:
            # Effective access only occurs when we call a method on the gridfs object.
            GridFS(database).find_one()
        except Exception as e:
            self._display_warning("Cannot access gridfs %s: %s" % (database_name, str(e)))
            return None

        return database

    def configure_mongodb(self):
        """ Configure MongoDB """
        self._display_info("Trying default configuration")

        host = "localhost"
        database_name = "INGInious"

        should_ask = True
        if self.try_mongodb_opts(host, database_name) is not None:
            should_ask = self._ask_boolean(
                "Successfully connected to MongoDB. Do you want to edit the configuration anyway?", False)
        else:
            self._display_info("Cannot guess configuration for MongoDB.")

        while should_ask:
            self._display_question(
                "Please enter the MongoDB host. If you need to enter a password, here is the syntax:")
            self._display_question("mongodb://USERNAME:PASSWORD@HOST:PORT/AUTHENTIFICATION_DATABASE")
            host = self._ask_with_default("MongoDB host", host)
            database_name = self._ask_with_default("Database name", database_name)
            if not self.try_mongodb_opts(host, database_name):
                if self._ask_boolean("Cannot connect to MongoDB. Would you like to continue anyway?", False):
                    break
            else:
                self._display_info("Successfully connected to MongoDB")
                break

        return {"mongo_opt": {"host": host, "database": database_name}}

    #######################################
    #           TASK DIRECTORY            #
    #######################################

    def configure_task_directory(self):
        """ Configure task directory """
        task_directory = self._configure_directory("tasks")

        if os.path.exists(task_directory):
            self._display_question("Demonstration tasks can be downloaded to let you discover INGInious.")
            if self._ask_boolean("Would you like to download them ?", True):
                try:
                    self._retrieve_and_extract_tarball("https://api.github.com/repos/INGInious/demo-tasks/tarball", task_directory)
                    self._display_info("Successfully downloaded and copied demonstration tasks.")
                except Exception as e:
                    self._display_error("An error occurred while copying the directory: %s" % str(e))
        else:
            self._display_warning("Skipping copying the 'test' course because the task dir does not exists")

        return {"tasks_directory": task_directory}

    #######################################
    #             CONTAINERS              #
    #######################################

    def _build_container(self, name, folder):
        self._display_info("Building container {}...".format(name))
        docker_connection = docker.from_env()
        docker_connection.images.build(path=folder, tag=name)
        self._display_info("done.".format(name))

    def select_containers_to_build(self):
        # If on a dev branch, download from github master branch (then manually rebuild if needed)
        # If on an pip installed version, download with the correct tag
        if not self._ask_boolean("Build the default containers? This is highly recommended, and is required to build other containers.", True):
            self._display_info("Skipping container building.")
            return

        # Mandatory images:
        stock_images = []
        try:
            docker_connection = docker.from_env()
            for image in docker_connection.images.list():
                for tag in image.attrs["RepoTags"]:
                    if re.match(r"^ghcr.io/inginious/env-(base|default):v" + __version__, tag):
                        stock_images.append(tag)
        except:
            self._display_info(FAIL + "Cannot connect to Docker!" + ENDC)
            self._display_info(FAIL + "Restart this command after making sure the command `docker info` works" + ENDC)
            return

        # If there are already available images, ask to rebuild or not
        if len(stock_images) >= 2:
            self._display_info("You already have the minimum required images for version " + __version__)
            if not self._ask_boolean("Do you want to re-build them ?", "yes"):
                self._display_info("Continuing with previous images. If you face issues, run inginious-container-update")
                return
        try:
            with tempfile.TemporaryDirectory() as tmpdirname:
                self._display_info("Downloading the base container source directory...")
                if "dev" in __version__:
                    tarball_url = "https://api.github.com/repos/INGInious/INGInious/tarball"
                    containers_version = "dev (github branch master)"
                    dev = True
                else:
                    tarball_url = "https://api.github.com/repos/INGInious/INGInious/tarball/v" + __version__
                    containers_version = __version__
                    dev = False
                self._display_info("Downloading containers for version:" + containers_version)
                self._retrieve_and_extract_tarball(tarball_url, tmpdirname)
                self._build_container("ghcr.io/inginious/env-base",
                                      os.path.join(tmpdirname, "base-containers", "base"))
                self._build_container("ghcr.io/inginious/env-default",
                                      os.path.join(tmpdirname, "base-containers", "default"))
                if dev:
                    self._display_info("If you modified files in base-containers folder, don't forget to rebuild manually to make these changes effective !")

            # Other non-mandatory containers:
            with tempfile.TemporaryDirectory() as tmpdirname:
                self._display_info("Downloading the other containers source directory...")
                self._retrieve_and_extract_tarball(
                    "https://api.github.com/repos/INGInious/containers/tarball", tmpdirname)
                # As the add_container function recursively calls itself before adding the entry,
                # the wanted build order.
                todo = ["ghcr.io/inginious/env-base", "ghcr.io/inginious/env-default"]
                available_containers = set(os.listdir(os.path.join(tmpdirname, 'grading')))
                self._display_info("Done.")

                def __add_container(container):
                    """
                        Add container to the dict of container to build.
                        :param: container : The prefixed name of the container.
                    """
                    if not container.startswith("ghcr.io/inginious/env-"):
                        container = "ghcr.io/inginious/env-" + container

                    if container in todo:
                        return
                    # getting name of supercontainer to see if need to build
                    line_from = \
                        [l for l in
                         open(os.path.join(tmpdirname, 'grading', container[22:], 'Dockerfile')).read().split("\n")
                         if
                         l.startswith("FROM")][0]
                    supercontainer = line_from.strip()[4:].strip().split(":")[0]
                    if supercontainer.startswith("ingi/") and supercontainer not in todo:
                        self._display_info(
                            "Container {} requires container {}, I'll build it too.".format(container,
                                                                                            supercontainer))
                        __add_container(supercontainer)
                    todo.append(container)

                self._display_info("The following containers can be built:")
                for container in available_containers:
                    self._display_info("\t" + container)
                while True:
                    answer = self._ask_with_default(
                        "Indicate the name of a container to build, or press enter to continue")
                    if answer == "":
                        break
                    if answer not in available_containers:
                        self._display_warning("Unknown container. Please retry")
                    else:
                        self._display_info("Ok, I'll build container {}".format(answer))
                        __add_container(answer)

                todo.remove("ghcr.io/inginious/env-base")
                todo.remove("ghcr.io/inginious/env-default")
                for container in todo:
                    try:
                        self._build_container(container,
                                              os.path.join(tmpdirname, 'grading', container[22:]))
                    except BuildError:
                        self._display_error(
                            "An error occured while building the container. Please retry manually.")
        except Exception as e:
            self._display_error("An error occurred while copying the directory: {}".format(e))

    #######################################
    #                MISC                 #
    #######################################

    def configure_misc(self):
        """ Configure various things """
        options = {}
        options["use_minified_js"] = self._ask_boolean(
            "Use minified javascript? (Useful in production, but should be disabled in dev environment)",
            True)

        return options

    def configure_backup_directory(self):
        """ Configure backup directory """
        return {"backup_directory": self._configure_directory("backups")}

    def ldap_plugin(self):
        """ Configures the LDAP plugin """
        name = self._ask_with_default("Authentication method name (will be displayed on the login page)", "LDAP")
        prefix = self._ask_with_default("Prefix to append to the username before db storage. Usefull when you have more than one auth method with "
                                        "common usernames.", "")
        ldap_host = self._ask_with_default("LDAP Host", "ldap.your.domain.com")

        encryption = 'none'
        while True:
            encryption = self._ask_with_default("Encryption (either 'ssl', 'tls', or 'none')", 'none')
            if encryption not in ['none', 'ssl', 'tls']:
                self._display_error("Invalid value")
            else:
                break

        base_dn = self._ask_with_default("Base DN", "ou=people,c=com")
        request = self._ask_with_default("Request to find a user. '{}' will be replaced by the username", "uid={}")
        require_cert = self._ask_boolean("Require certificate validation?", encryption is not None)

        return {
            "plugin_module": "inginious.frontend.plugins.auth.ldap_auth",
            "host": ldap_host,
            "encryption": encryption,
            "base_dn": base_dn,
            "request": request,
            "prefix": prefix,
            "name": name,
            "require_cert": require_cert
        }

    def configure_authentication(self, database):
        """ Configure the authentication """
        options = {"plugins": [], "superadmins": []}

        self._display_info("We will now create the first user.")

        username = self._ask_with_default("Enter the login of the superadmin", "superadmin")
        realname = self._ask_with_default("Enter the name of the superadmin", "INGInious SuperAdmin")
        email = None
        while not email:
            email = self._ask_with_default("Enter the email address of the superadmin", "superadmin@inginious.org")
            email = UserManager.sanitize_email(email)
            if email is None:
                self._display_error("Invalid email format.")

        password = self._ask_with_default("Enter the password of the superadmin", "superadmin")

        database.users.insert_one({"username": username,
                                   "realname": realname,
                                   "email": email,
                                   "password": UserManager.hash_password(password),
                                   "bindings": {},
                                   "code_indentation": "4",
                                   "language": "en"})

        options["superadmins"].append(username)

        while True:
            if not self._ask_boolean("Would you like to add another auth method?", False):
                break

            self._display_info("You can choose an authentication plugin between:")
            self._display_info("- 1. LDAP auth plugin. This plugin allows to connect to a distant LDAP host.")
            self._display_info("There are other plugins available that are not configurable directly by inginious-install.")
            self._display_info("Please consult the online documentation to install them yourself.")

            plugin = self._ask_with_default("Enter the corresponding number to your choice", 'skip')
            if plugin == '1':
                options["plugins"].append(self.ldap_plugin())
            else:
                continue

        options["session_parameters"] = {}
        options["session_parameters"]['timeout'] = self._ask_integer("How much time should a user stay connected, "
                                                                     "in seconds? The default is 86400, one day.", 86400)
        options["session_parameters"]['ignore_change_ip'] = not self._ask_boolean("Should user be disconnected when "
                                                                                  "their IP changes? It may prevent "
                                                                                  "cookie stealing.",
                                                                                  True)
        options["session_parameters"]['secure'] = self._ask_boolean("Do you plan to serve your INGInious instance only"
                                                                    " in HTTPS?", False)
        options["session_parameters"]['secret_key'] = hexlify(os.urandom(32)).decode('utf-8')

        return options

    def configuration_filename(self):
        """ Returns the name of the configuration file """
        return "configuration.yaml"

    def support_remote_debugging(self):
        """ Returns True if the frontend supports remote debugging, False else"""
        return True

    def _retrieve_and_extract_tarball(self, link, folder):
        filename, _ = urllib.request.urlretrieve(link)
        with tarfile.open(filename, mode="r:gz") as thetarfile:
            members = thetarfile.getmembers()
            commonpath = os.path.commonpath([tarinfo.name for tarinfo in members])

            for member in members:
                member.name = member.name[len(commonpath) + 1:]
                if member.name:
                    thetarfile.extract(member, folder, filter="data")

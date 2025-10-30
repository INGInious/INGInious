# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Manages users data and session """
import logging
import hashlib
import flask
import tzlocal
from typing import Dict, Optional

from bson import ObjectId
from werkzeug.exceptions import NotFound
from abc import ABCMeta, abstractmethod
from functools import reduce
from natsort import natsorted
from collections import OrderedDict, namedtuple
from binascii import hexlify
import os
import re
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask.sessions import NullSession
from mongoengine import Q

from inginious.frontend.models.submission import Submission
from inginious.frontend.models.user_task import UserTask
from inginious.frontend.models.user import User
from inginious.frontend.models.group import Group
from inginious.frontend.models.audience import Audience
from inginious.frontend.models.course_class import CourseClass
from inginious.frontend.models.session import Session

class AuthInvalidInputException(Exception):
    pass


class AuthInvalidMethodException(Exception):
    pass


class AuthMethod(object, metaclass=ABCMeta):

    @abstractmethod
    def get_id(self):
        """
        :return: The auth method id
        """
        return ""

    @abstractmethod
    def get_auth_link(self, auth_storage):
        """
        :param auth_storage: The session auth method storage dict
        :return: The authentication link
        """
        return ""

    @abstractmethod
    def callback(self, auth_storage):
        """
        :param auth_storage: The session auth method storage dict
        :return: User tuple and , or None, if failed
        """
        return None

    @abstractmethod
    def get_name(self):
        """
        :return: The name of the auth method, to be displayed publicly
        """
        return ""

    @abstractmethod
    def get_imlink(self):
        """
        :return: The image link
        """
        return ""


UserInfo = namedtuple("UserInfo", ["realname", "email", "username", "bindings", "language", "code_indentation", "activated"])


class UserManager:
    def __init__(self, database, superadmins):
        """
        :type database: pymongo.database.Database
        :type superadmins: list(str)
        :param superadmins: list of the super-administrators' usernames
        """
        self._session = flask.session
        self._database = database
        self._superadmins = superadmins
        self._auth_methods = OrderedDict()
        self._logger = logging.getLogger("inginious.webapp.users")

    @classmethod
    def sanitize_email(cls, email: str) -> str:
        """
        Sanitize an email address and put the bar part of an address foo@bar in lower case.
        """
        email_re = re.compile(
            r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
            r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"'  # quoted-string
            r')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$', re.IGNORECASE)  # domain

        if email_re.match(email) is None:
            return None

        email = email.split('@')
        return "%s@%s" % (email[0], email[1].lower())

    ##############################################
    #           User session management          #
    ##############################################

    def session_is_lti(self) -> bool:
        """ Returns whether the current request comes from an LTI session. """
        return self._session.is_lti

    def session_logged_in(self):
        """ Returns True if a user is currently connected in this session, False else """
        return self._session.loggedin

    def session_username(self):
        """ Returns the username from the session, if one is open. Else, returns None"""
        if not self.session_logged_in():
            return None
        return self._session["username"]

    def session_email(self):
        """ Returns the email of the current user in the session, if one is open. Else, returns None"""
        if not self.session_logged_in():
            return None
        return self._session["email"]

    def session_realname(self):
        """ Returns the real name of the current user in the session, if one is open. Else, returns None"""
        if not self.session_logged_in():
            return None
        return self._session["realname"]

    def session_tos_signed(self):
        """ Returns True if the current user has signed the tos"""
        if not self.session_logged_in():
            return None
        return self._session["tos_signed"]

    def session_token(self):
        """ Returns the token of the current user in the session, if one is open. Else, returns None"""
        if not self.session_logged_in():
            return None
        return self._session["token"]

    def session_lti_info(self):
        """ If the current session is an LTI one, returns a dict in the form
            ::

                {
                    "email": email,
                    "username": username
                    "realname": realname,
                    "roles": roles,
                    "task": (course_id, task_id),
                    <lti version dependent fields>
                }

            where all these data where provided by the LTI consumer, and MAY NOT be equivalent to the data
            contained in database for the currently connected user.

            If the current session is not an LTI one, returns None.
        """
        if self.session_is_lti() and "lti" in self._session:
            return self._session["lti"]
        return None

    def session_id(self):
        """ Returns the current session id"""
        return self._session.sid

    def session_auth_storage(self):
        """ Returns the oauth state for login """
        return self._session.auth_storage

    def session_language(self, default="en"):
        """ Returns the current session language """
        return self._session.language

    def session_timezone(self):
        """ Returns the current session timezone """
        return self._session.timezone

    def session_code_indentation(self):
        """ Returns the current session code indentation """
        return self._session.code_indentation

    def session_api_key(self):
        """ Returns the API key for the current user. Created on first demand. """
        return self.get_user_api_key(self.session_username())

    def set_session_token(self, token):
        """ Sets the token of the current user in the session, if one is open."""
        if self.session_logged_in():
            self._session["token"] = token

    def set_session_username(self, username):
        """ Sets the username of the current user in the session, if one is open."""
        if self.session_logged_in():
            self._session["username"] = username

    def set_session_realname(self, realname):
        """ Sets the real name of the current user in the session, if one is open."""
        if self.session_logged_in():
            self._session["realname"] = realname

    def set_session_tos_signed(self):
        """ Sets the real name of the current user in the session, if one is open."""
        if self.session_logged_in():
            self._session["tos_signed"] = True

    def set_session_language(self, language):
        self._session["language"] = language

    def set_session_timezone(self, timezone):
        self._session["timezone"] = timezone

    def set_session_code_indentation(self, code_indentation):
        """ Sets the code indentation of the current user in the session, if one is open."""
        if self.session_logged_in():
            self._session["code_indentation"] = code_indentation

    def _set_session(self, user):
        """ Init the session. Preserves potential LTI information. """
        self._session["loggedin"] = True
        self._session["email"] = user.email
        self._session["username"] = user.username
        self._session["realname"] = user.realname
        self._session["language"] = user.language
        self._session["timezone"] = user.timezone
        self._session["code_indentation"] = user.code_indentation
        self._session["tos_signed"] = user.tos_accepted
        self._session["token"] = None


    def create_lti_session(self, session_id, session_dict):
        """ Creates an LTI session. Returns the new session id"""
        self._session.loggedin = False
        for key, item in session_dict.items():
            self._session.lti[key] = item
        return session_id

    def attempt_lti_login(self):
        """ Given that the current session is an LTI one (session_lti_info does not return None), attempt to find an INGInious user
            linked to this lti username/consumer_key. If such user exists, logs in using it.
             
            Returns True (resp. False) if the login was successful
        """
        if not self.session_is_lti():
            raise Exception("Not an LTI session")

        # TODO allow user to be automagically connected if the TC uses the same user id
        return False

    ##############################################
    #      User searching and authentication     #
    ##############################################

    def register_auth_method(self, auth_method):
        """
        Registers an authentication method
        :param auth_method: an AuthMethod object
        """
        self._auth_methods[auth_method.get_id()] = auth_method

    def get_auth_method(self, auth_method_id):
        """
        :param the auth method id, as provided by get_auth_methods_inputs()
        :return: AuthMethod if it exists, otherwise None
        """
        return self._auth_methods.get(auth_method_id, None)

    def get_auth_methods(self):
        """
        :return: The auth methods dict
        """
        return self._auth_methods

    def auth_user(self, username, password, do_connect=True):
        """
        Authenticate the user in database
        :param username: Username/Login
        :param password: User password
        :param do_connect: indicates if the user must be connected after authentification, True by default
        :return: Returns a dict representing the user, or None if the authentication was not successful
        """
        user = User.objects(username=username, activate__exists=False).first()

        if user is None:
            return None

        method, db_hash = user["password"].split("-", 1) if "-" in user["password"] else ("sha512", user["password"])

        if self.verify_hash(db_hash, password, method):
            if do_connect:
                self.connect_user(user)
            return user

    def verify_hash(cls, db_hash, password, method="sha512"):
        """
        Verify a hash
        :param db_hash: The hash to verify
        :param password: The password to verify
        :param method: The hash method
        :return: A boolean if the hash is correct
        """
        available_methods = {"sha512": cls.verify_hash_sha512, "argon2id": cls.verify_hash_argon2id}

        if method in available_methods:
            return available_methods[method](db_hash, password)
        else:
            raise AuthInvalidMethodException()


    def verify_hash_sha512(cls, db_hash, password):
        return cls.hash_password_sha512(password) == db_hash


    def verify_hash_argon2id(cls, db_hash, password):
        try:
            ph = PasswordHasher()
            return ph.verify(db_hash, password)
        except VerifyMismatchError:
            return False

    def connect_user(self, user):
        """ Opens a session for the user

        :param user : a dict representing the user, it contains the data of the user.
            It must at least contain the following fields:
            - realname
            - email
            - username
        """

        if not all(key in user for key in ["realname", "email", "username"]):
            raise AuthInvalidInputException()

        User.objects(email=user["email"]).update(realname=user["realname"], username=user["username"],
                                                 language=user.language)

        ip = flask.request.remote_addr
        self._logger.info("User %s connected - %s - %s - %s", user["username"], user["realname"], user["email"], ip)
        self._set_session(user)
        return True

    def disconnect_user(self):
        """
        Disconnects the user currently logged-in
        """
        if self.session_logged_in():
            ip = flask.request.remote_addr
            self._logger.info("User %s disconnected - %s - %s - %s", self.session_username(), self.session_realname(),
                              self.session_email(), ip)

        self._session.loggedin = False

    def get_users_info(self, usernames, limit=0, skip=0) -> Dict[str, Optional[UserInfo]]:
        """
        :param usernames: a list of usernames
        :param limit A limit of users requested
        :param skip A quantity of users to skip
        :return: a dict, in the form {username: val}, where val is either None if the user cannot be found,
        or a UserInfo. If the list of usernames is empty, return an empty dict.
        """
        query = {"username__in": usernames} if usernames is not None else {}
        infos = User.objects(**query).skip(skip).limit(limit)

        retval = {info["username"]: UserInfo(info["realname"], info["email"], info["username"], info["bindings"],
                                             info["language"], info["code_indentation"], "activate" not in info)
                  for info in infos}
        return retval

    def get_user_info(self, username) -> Optional[UserInfo]:
        """
        :param username:
        :return: a tuple (realname, email) if the user can be found, None else
        """
        info = self.get_users_info([username])
        return info[username] if username in info else ""

    def get_user_realname(self, username):
        """
        :param username:
        :return: the real name of the user if it can be found, None else
        """
        info = self.get_user_info(username)
        if info is not None:
            return info.realname
        return None

    def get_user_email(self, username):
        """
        :param username:
        :return: the email of the user if it can be found, None else
        """
        info = self.get_user_info(username)
        if info is not None:
            return info.email
        return None

    def get_user_api_key(self, username, create=True):
        """
        Get the API key of a given user.
        API keys are generated on demand.
        :param username:
        :param create: Create the API key if none exists yet
        :return: the API key assigned to the user, or None if none exists and create is False.
        """
        retval = User.objects.get(username=username)
        if not retval:
            return None
        elif "apikey" not in retval and create:
            retval.apikey = self.generate_api_key()
            retval.save()
        return retval.apikey

    def activate_user(self, activate_hash):
        """Active a user based on his/her activation hash
        :param activate_hash: The activation hash of a user
        :return A boolean if the user was found and updated
        """
        user = User.objects(activate=activate_hash).modify(unset__activate=True)
        return user is not None

    def bind_user(self, auth_id, user):
        """
        Add a binding method to a user
        :param auth_id: The binding method id
        :param user: User object
        :return: Boolean if method has been add
        """
        username, realname, email, additional = user
        email = UserManager.sanitize_email(email)
        if email is None:
            self._logger.exception("Invalid email format.")
            return False

        auth_method = self.get_auth_method(auth_id)
        if not auth_method:
            raise NotFound(description=_("Auth method not found."))

        # Look for already bound auth method username
        user_profile = User.objects(**{"bindings__" + auth_id: username}).first()

        if user_profile and not self.session_logged_in():
            # Sign in
            self.connect_user(user_profile)
        elif user_profile and self.session_username() == user_profile["username"]:
            # Logged in, refresh fields if found profile username matches session username
            User.objects(username=self.session_username()).update(**{"bindings__" + auth_id: [username, additional]})
        elif user_profile:
            # Logged in, but already linked to another account
            self._logger.exception("Tried to bind an already bound account !")
        elif self.session_logged_in():
            # No binding, but logged: add new binding
            # !!! Use email as it may happen that a user is logged with empty username
            # !!! if the binding link is used as is
            User.objects(email=self.session_email()).update(**{"bindings__" + auth_id: [username, additional]})
        else:
            # No binding, check for email
            if User.objects(email=email).first():
                # Found an email, existing user account, abort without binding
                self._logger.exception("The binding email is already used by another account!")
                return False
            else:
                # New user, create an account using email address
                user_profile = User(username="", realname=realname, email=email,
                                bindings={auth_id: [username, additional]}, language=self.session_language())

                user_profile.save()
                self.connect_user(user_profile)

        return True

    def revoke_binding(self, username, binding_id):
        """
        Revoke a binding method for a user
        :param binding_id: The binding method id
        :param username: username of the user
        :return: Boolean if error occurred and message if necessary
        """
        user_data = User.objects(username=username).first()
        if binding_id not in self.get_auth_methods().keys():
            error = True
            msg = _("Incorrect authentication binding.")
        elif user_data is not None and (len(user_data.bindings.keys()) > 1 or "password" in user_data):
            User.objects(username=username).update(**{"unset__bindings__" + binding_id: 1})
            msg = ""
            error = False
        else:
            error = True
            msg = _("You must set a password before removing all bindings.")
        return error, msg

    def delete_user(self, username, confirmation_email=None):
        """
        Delete a user based on username
        :param username: the username of the user
        :param confirmation_email: An email to confirm suppression. May be None
        :return a boolean if a user was deleted
        """
        query = {"username": username, "email": confirmation_email} \
            if confirmation_email is not None else {"username": username}
        result = User.objects(**query).modify(remove=True)
        if not result:
            return False
        else:
            Submission.objects(username=username).delete()
            UserTask.objects(username=username).delete()
            user_courses = CourseClass.objects(students=username)
            for elem in user_courses: self.course_unregister_user(elem.id, username)
        return True

    def create_user(self, values):
        """
        Create a new user
        :param values: Dictionary of fields
        :return: An error message if something went wrong else None
        """
        query = Q(username=values["username"]) | Q(email=values["email"])
        if User.objects(query).first() is not None:
            return _("User could not be created.")

        User(username=values["username"], realname=values["realname"], email=values["email"],
             password=self.hash_password(values["password"])).save()

        return None

    ##############################################
    #      User task/course info management      #
    ##############################################

    def get_course_cache(self, username, course):
        """
        :param username: The username
        :param course: A Course object
        :return: a dict containing info about the course, in the form:

            ::

                {"task_tried": 0, "total_tries": 0, "task_succeeded": 0, "task_grades":{"task_1": 100.0, "task_2": 0.0, ...}}

            Note that only the task already seen at least one time will be present in the dict task_grades.
        """
        return self.get_course_caches([username], course)[username]

    def get_course_caches(self, usernames : list[str], course):
        """
        :param usernames: List of username for which we want info. If usernames is None, data from all users will be returned.
        :param course: A Course object
        :return:
            Returns data of the specified users for a specific course. users is a list of username.

            The returned value is a dict:

            ::

                {"username": {"task_tried": 0, "total_tries": 0, "task_succeeded": 0, "task_grades":{"task_1": 100.0, "task_2": 0.0, ...}}}

            Note that only the task already seen at least one time will be present in the dict task_grades.
        """

        match = {"courseid": course.get_id()}
        if usernames is not None:
            match["username"] = {"$in": usernames}

        taskids = course.get_readable_tasks()
        match["taskid"] = {"$in": list(taskids)}

        user_tasks = UserTask.objects(**match)
        data = user_tasks.aggregate([{
            "$group":
                {
                    "_id": "$username",
                    "task_tried": {"$sum": {"$cond": [{"$ne": ["$tried", 0]}, 1, 0]}},
                    "total_tries": {"$sum": "$tried"},
                    "task_succeeded": {"$addToSet": {"$cond": ["$succeeded", "$taskid", False]}},
                    "task_grades": {"$addToSet": {"taskid": "$taskid", "grade": "$grade"}}
                }
        }])

        if usernames is None:
            usernames = self.get_course_registered_users(course=course, with_admins=False)

        retval = {username: {"task_succeeded": 0, "task_grades": [], "grade": 0} for username in usernames}

        users_tasks_list = course.get_task_dispenser().get_user_task_list(usernames)
        users_grade = course.get_task_dispenser().get_course_grades(user_tasks, usernames)

        for result in data:
            username = result["_id"]
            visible_tasks = users_tasks_list.get(username, [])
            result["task_succeeded"] = len(set(result["task_succeeded"]).intersection(visible_tasks))
            result["task_grades"] = {dg["taskid"]: dg["grade"] for dg in result["task_grades"] if
                                     dg["taskid"] in visible_tasks}

            result["grade"] = users_grade[username]
            retval[username] = result

        return retval

    def get_task_cache(self, username, courseid, taskid):
        """
        Shorthand for get_task_caches([username], courseid, taskid)[username]
        """
        return self.get_task_caches([username], courseid, taskid)[username]

    def get_task_caches(self, usernames, courseid, taskid):
        """
        :param usernames: List of username for which we want info. If usernames is None, data from all users will be returned.
        :param courseid: the course id
        :param taskid: the task id
        :return: A dict in the form:

            ::

                {
                    "username": {
                        "courseid": courseid,
                        "taskid": taskid,
                        "tried": 0,
                        "succeeded": False,
                        "grade": 0.0
                    }
                }
        """
        match = {"courseid": courseid, "taskid": taskid}
        if usernames is not None:
            match["username"] = {"$in": usernames}

        data = UserTask.objects(**match)
        retval = {username: None for username in usernames}
        for result in data:
            username = result["username"]
            retval[username] = result

        return retval

    def user_saw_task(self, username, courseid, taskid):
        """ Set in the database that the user has viewed this task """
        UserTask.objects(username=username, courseid=courseid, taskid=taskid).update_one(
            set_on_insert__username=username,
            set_on_insert__courseid=courseid,
            set_on_insert__taskid=taskid,
            set_on_insert__tried=0,
            set_on_insert__succeeded=False,
            set_on_insert__grade=0.0,
            set_on_insert__submissionid=None,
            set_on_insert__state="",
            upsert=True
        )

    def update_user_stats(self, username, course, task, submission, result_str, grade, state, newsub, task_dispenser):
        """ Update stats with a new submission """
        self.user_saw_task(username, submission["courseid"], submission["taskid"])

        eval_mode = task_dispenser.get_evaluation_mode(task.get_id())
        match_filter = {"username": username, "courseid": submission["courseid"], "taskid": submission["taskid"]}
        if newsub:
            old_submission = UserTask.objects(**match_filter).modify(inc__tried=1, inc__tokens__amount=1, new=True)

            # Update if the submission should be the default one
            if eval_mode == 'last' or (eval_mode == 'best' and old_submission.grade <= grade):
                old_submission.succeeded = result_str == "success"
                old_submission.grade = grade
                old_submission.state = state
                old_submission.submissionid = submission.id
                old_submission.save()
        else:
            old_submission = UserTask.objects.get(**match_filter)
            sort_filter = ["-grade"] if eval_mode == 'best' else []
            sort_filter.append("-submitted_on")
            def_sub = Submission.objects(**match_filter).order_by(*sort_filter).first()

            if def_sub:
                old_submission.succeeded = def_sub["result"] == "success"
                old_submission.grade = def_sub["grade"]
                old_submission.state = def_sub["state"]
                old_submission.submissionid = def_sub.id
                old_submission.save()
            elif old_submission.submissionid == submission["_id"]: # otherwise, update cache if needed
                old_submission.succeeded = submission["result"] == "success"
                old_submission.grade = submission["grade"]
                old_submission.state = submission["state"]
                old_submission.save()

    def task_is_visible_by_user(self, course, task, username=None, lti=None):
        """ Returns true if the task is visible and can be accessed by the user

        :param lti: indicates if the user is currently in a LTI session or not.

            - None to ignore the check
            - True to indicate the user is in a LTI session
            - False to indicate the user is not in a LTI session
            - "auto" to enable the check and take the information from the current session
        """
        if username is None:
            username = self.session_username()

        dispenser_filter = course.get_task_dispenser().get_accessibility(task.get_id(), username).after_start()
        return (self.course_is_open_to_user(course, username, lti) and dispenser_filter) \
               or self.has_staff_rights_on_course(course, username)

    def task_can_user_submit(self, course, task, username=None, only_check=None, lti=None):
        """ returns true if the user can submit his work for this task
            :param only_check : only checks for 'groups', 'tokens', or None if all checks
            :param lti: indicates if the user is currently in a LTI session or not.
            - None to ignore the check
            - True to indicate the user is in a LTI session
            - False to indicate the user is not in a LTI session
            - "auto" to enable the check and take the information from the current session
        """
        checks = [only_check] if only_check is not None else ["groups", "tokens"]

        if username is None:
            username = self.session_username()

        if self.has_staff_rights_on_course(course, username):
            return True

        # Check if course access is ok
        course_filter = self.course_is_open_to_user(course, username, lti)

        # Check if task accessible to user
        task_filter = course.get_task_dispenser().get_accessibility(task.get_id(), username).is_open()

        # Check for group
        is_group_task = course.get_task_dispenser().get_group_submission(task.get_id())
        group = Group.objects(courseid=course.get_id(), students=self.session_username()).first()
        group_filter = 'groups' in checks and group if is_group_task else True

        # Check for tokens
        students = group["students"] if (group is not None and is_group_task) else [self.session_username()]
        token_filter = True
        submission_limit = course.get_task_dispenser().get_submission_limit(task.get_id())
        if 'tokens' in checks and submission_limit != {"amount": -1, "period": -1}:
            user_tasks = UserTask.objects(courseid=course.get_id(), taskid=task.get_id(), username__in=students)
            token_filter = reduce(lambda last, cur: last and cur.check_tokens(submission_limit), user_tasks, True)

        return course_filter and task_filter and group_filter and token_filter


    def get_course_audiences(self, course):
        """ Returns a list of the course audiences"""
        return natsorted(list(Audience.objects(courseid=course.get_id())), key=lambda x: x["description"])

    def get_course_audiences_per_student(self, course):
        """ Returns a dictionnary mapping student -> list of audiences it belongs to, for a given course """
        course_audiences = self.get_course_audiences(course)
        student_audiences = {}
        for audience in course_audiences:
            for student in audience["students"]:
                if student not in student_audiences:
                    student_audiences[student] = []
                student_audiences[student].append(audience)
        return student_audiences

    def get_course_groups(self, course):
        """ Returns a list of the course groups"""
        return natsorted(list(Group.objects(courseid=course.get_id())), key=lambda x: x.description)

    def get_course_user_group(self, course, username=None):
        """ Returns the audience whose username belongs to
        :param course: a Course object
        :param username: The username of the user that we want to register. If None, uses self.session_username()
        :return: the audience description
        """
        if username is None:
            username = self.session_username()

        return Group.objects(courseid=course.get_id(), students=username).first()

    def course_register_user(self, course, username=None, password=None, force=False):
        """ Register a user to the course

        :param course: a Course object
        :param username: The username of the user that we want to register. If None, uses self.session_username()
        :param password: Password for the course. Needed if course.is_password_needed_for_registration() and force != True
        :param force: Force registration
        :return: True if the registration succeeded, False else
        """
        if username is None:
            username = self.session_username()

        # Do not continue registering the user in the course if username is empty
        # or if the user is not in DB (should never happen, anyway).
        if not username:
            return False
        user_info = self.get_user_info(username)
        if not user_info:
            return False

        if not force:
            if not course.is_registration_possible(user_info):
                return False
            if course.is_password_needed_for_registration() and course.get_registration_password() != password:
                return False
        if self.course_is_user_registered(course, username):
            return False  # already registered?

        CourseClass.objects(id=course.get_id()).update(push__students=username, upsert=True)

        self._logger.info("User %s registered to course %s", username, course.get_id())
        return True

    def course_unregister_user(self, course_id, username=None):
        """
        Unregister a user to the course
        :param course_id: a course id
        :param username: The username of the user that we want to unregister. If None, uses self.session_username()
        """
        if username is None:
            username = self.session_username()

        # If user doesn't belong to a group, will ensure correct deletion
        Audience.objects(courseid=course_id, students=username).update(pull__students=username)

        # If user doesn't belong to a group, will ensure correct deletion
        Group.objects(courseid=course_id, students=username).update(pull_students=username)

        CourseClass.objects(id=course_id).update(pull__students=username)

        self._logger.info("User %s unregistered from course %s", username, course_id)

    def course_is_open_to_user(self, course, username=None, lti=None, return_reason=False):
        """ Checks if a user is can access a course

        :param course: a Course object
        :param username: The username of the user that we want to check. If None, uses self.session_username()
        :param lti: indicates if the user is currently in a LTI session or not.

            - None to ignore the check
            - True to indicate the user is in a LTI session
            - False to indicate the user is not in a LTI session
            - "auto" to enable the check and take the information from the current session

        :param return_reason: instead of False, returns a string indicating for which reason the course is not
            open to the user. Reasons may be :

            - "closed" if the course is not open
            - "unregistered_not_previewable" user is not registered and course is not previewable
            - "lti_only" the current session is not a LTI session and this course requires at LTI session
            - "lti_not_registered" this LTI course can be accessed outside an LTI session only if the user register
              first via the LTI interface

        :return: True if the user can access the course, False (or the reason if return_reason is True) otherwise
        """
        if username is None:
            username = self.session_username()
        if lti == "auto":
            lti = self.session_lti_info() is not None

        if self.has_staff_rights_on_course(course, username):
            return True

        if not course.get_accessibility().is_open():
            return False if not return_reason else "closed"

        if not self.course_is_user_registered(course, username) and not course.allow_preview():
            return False if not return_reason else "unregistered_not_previewable"

        # LTI courses can only be accessed from a LTI session
        if lti and course.is_lti() != lti:
            return False if not return_reason else "lti_only"

        # If we are not in a LTI session, an LTI course can be accessed if we do not need to send grades back
        # to the LMS
        if lti is False and course.is_lti():
            if not course.lti_send_back_grade():
                return True
            else:
                return False if not return_reason else "lti_not_registered"

        return True

    def course_is_user_registered(self, course, username=None):
        """ Checks if a user is registered

        :param course: a Course object
        :param username: The username of the user that we want to check. If None, uses self.session_username()
        :return: True if the user is registered, False else
        """
        if username is None:
            username = self.session_username()

        if self.has_staff_rights_on_course(course, username):
            return True

        return CourseClass.objects(id=course.get_id(), students=username).first() is not None

    def get_course_registered_users(self, course, with_admins=True):
        """
        Get all the users registered to a course
        :param course: a Course object
        :param with_admins: include admins?
        :return: a list of usernames that are registered to the course
        """

        course_class = CourseClass.objects(id=course.get_id()).first()
        students = course_class.students if course_class else []
        if with_admins:
            return list(set(students + course.get_staff()))
        else:
            return students

    ##############################################
    #             Rights management              #
    ##############################################

    def user_is_superadmin(self, username=None):
        """
        :param username: the username. If None, the username of the currently logged in user is taken
        :return: True if the user is superadmin, False else
        """
        if username is None:
            username = self.session_username()

        return username in self._superadmins

    def has_admin_rights_on_course(self, course, username=None, include_superadmins=True):
        """
        Check if a user can be considered as having admin rights for a course
        :type course: inginious.frontend.courses.Course
        :param username: the username. If None, the username of the currently logged in user is taken
        :param include_superadmins: Boolean indicating if superadmins should be taken into account
        :return: True if the user has admin rights, False else
        """
        if username is None:
            username = self.session_username()

        return (username in course.get_admins()) or (include_superadmins and self.user_is_superadmin(username))

    def has_staff_rights_on_course(self, course, username=None, include_superadmins=True):
        """
        Check if a user can be considered as having staff rights for a course
        :type course: inginious.frontend.courses.Course
        :param username: the username. If None, the username of the currently logged in user is taken
        :param include_superadmins: Boolean indicating if superadmins should be taken into account
        :return: True if the user has staff rights, False else
        """
        if username is None:
            username = self.session_username()

        return (username in course.get_staff()) or (include_superadmins and self.user_is_superadmin(username))

    @classmethod
    def generate_api_key(cls):
        return hexlify(os.urandom(40)).decode('utf-8')

    @classmethod
    def hash_password_sha512(cls, content):
        """
        :param content: a str input
        :return a hash of str input
        """
        return hashlib.sha512(content.encode("utf-8")).hexdigest()

    @classmethod
    def hash_password_argon2id(cls, content):
        """
        :param content: a str input
        :return a hash of str input
        """
        ph = PasswordHasher()
        return ph.hash(content)

    @classmethod
    def hash_password(cls, content):
        """
        Encapsulates the other password hashing functions
        :param content: a str input
        :return a hash of str input
        """

        methods = {"argon2id": cls.hash_password_argon2id, "sha512": cls.hash_password_sha512}
        latest_method = "argon2id"

        return latest_method + "-" + methods[latest_method](content)

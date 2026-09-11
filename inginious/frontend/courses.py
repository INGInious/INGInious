# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" A course class with some modification for users """
from __future__ import annotations

import copy
import gettext
import re
import os
import logging
from typing import List, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError, ConfigDict
from pydantic_core import InitErrorDetails
from typing import Optional, Literal

from inginious.common.filesystems import FileSystemProvider, fetch_or_cache, invalidate_cache, get_fs_provider
from inginious.common.tags import Tag
from inginious.common.base import id_checker, get_json_or_yaml, loads_json_or_yaml
from inginious.frontend.accessible_time import AccessibleTime
from inginious.frontend.parsable_text import ParsableText
from inginious.frontend.user_manager import UserInfo
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.frontend.plugins import plugin_manager
from inginious.frontend.task_dispensers import get_task_dispensers
from inginious.frontend.tasks import Task
from inginious.common.exceptions import InvalidNameException, CourseNotFoundException, CourseUnreadableException


def _load_course(course_fs : FileSystemProvider, courseid : str):
    # Try to open the course file
    try:
        logging.getLogger("inginious.course").info("Caching course %s", courseid)
        task_content = loads_json_or_yaml("course.yaml", course_fs.get("course.yaml"))
    except Exception as e:
        raise CourseUnreadableException(str(e))

    return Course(courseid, task_content)


class CourseDescriptor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True) # to allow AccessibleTime() objects in the model

    name: str
    admins: list[str] = []
    tutors: list[str] = []
    description: str = ""
    accessible: Optional[str | bool | AccessibleTime] = None
    registration: Optional[str | bool | AccessibleTime] = None
    registration_password: Optional[str] = None
    registration_ac: Optional[Literal["username", "binding", "email"]] = None
    registration_ac_accept: bool = True
    registration_ac_list: list[str] = []
    groups_student_choice: bool = False
    allow_unregister: bool = True
    allow_preview: bool = False
    is_lti: bool = False
    archived: bool = False
    archive_date: Optional[datetime] = Field( # using datetime type to allow automatic parsing of ISO-8601 strings + accept parsed value by validator
        default=None,
        description="ISO-8601 date/time string",
    )
    lti_url: str = ""
    lti_keys: dict = {}
    lti_config: dict = {}
    lti_secrets: dict = {}
    lti_send_back_grade: bool = False
    tags: dict = {}
    task_dispenser: str = "toc"
    dispenser_data: dict = {}
    nofrontend: bool = False

    # Force some parameters if LTI is active
    @model_validator(mode="after")
    def apply_lti_overrides(self):
        if self.is_lti:
            self.accessible = True
            self.registration = False
            self.registration_password = None
            self.registration_ac = None
            self.registration_ac_list = []
            self.groups_student_choice = False
            self.allow_unregister = False
        else:
            self.lti_keys, self.lti_secrets, self.lti_config = {}, {}, {}
            self.lti_url = ""
            self.lti_send_back_grade = False
        return self

    # check task dispenser is valid
    @field_validator("task_dispenser", mode="after")
    @classmethod
    def check_task_dispenser_registered(cls, task_dispenser: str) -> str:
        available_task_dispensers = get_task_dispensers()
        if task_dispenser not in available_task_dispensers:
            raise ValueError(
                f"Unknown task dispenser '{task_dispenser}'. Registered dispensers: {sorted(available_task_dispensers.keys())}"
            )
        return task_dispenser

    # check given accessible and registration values are valid
    @field_validator("accessible", mode="after")
    @classmethod
    def verify_accessible(cls, v):
        try:
            return AccessibleTime(v)
        except Exception as e:
            raise ValueError(f"Invalid time format.")

    @field_validator("registration", mode="after")
    @classmethod
    def verify_registration(cls, v):
        try:
            return AccessibleTime(v)
        except Exception as e:
            raise ValueError(f"Invalid time format.")

    # validator on archived VS archive_date
    @model_validator(mode="after")
    def check_archive_fields(self):
        if self.archived and not self.archive_date:
            raise ValidationError.from_exception_data(
                self.__class__.__name__,
                [
                    InitErrorDetails(
                        type="value_error",
                        loc=("archive_date",),
                        input=self.archive_date,
                        ctx={"error": ValueError("Archive_date must be set if archived is True.")},
                    )
                ],
            )
        if not self.archived and self.archive_date:
            raise ValidationError.from_exception_data(
                self.__class__.__name__,
                [
                    InitErrorDetails(
                        type="value_error",
                        loc=("archived",),
                        input=self.archived,
                        ctx={"error": ValueError("Archive_date is given but archived is False.")},
                    )
                ],
            )
        return self


class Course(object):
    """ A course with some modification for users """

    def __init__(self, courseid, content):
        self._id = courseid
        self._pre_validated_content = content
        try:
            self._content = CourseDescriptor(**content)
        except ValidationError as e:
            if bool(set(e.errors()[0]['loc']) & {"admins", "tutors", "registration_password", "registration_ac_list", "lti_secrets", }):  # if the error is related to a sensitive field, do not print the message
                raise CourseUnreadableException(f"Course '{courseid}' has an invalid '{e.errors()[0]['loc'][0]}' YAML spec.")
            else:
                raise CourseUnreadableException(f"Course '{courseid}' has an invalid '{e.errors()[0]['loc'][0]}' YAML spec: {e.errors()[0]['msg']}")

        self._fs = get_fs_provider().from_subfolder(courseid)
        self._new_doc = not self._fs.exists()

        self._translations = {}

        self._name = self._content.name

        if self._content.nofrontend:
            raise Exception("That course is not allowed to be displayed directly in the webapp")

        self._tags = {key: Tag(key, tag_dict, self.gettext) for key, tag_dict in self._content.tags.items()}

        try:
            task_dispenser_class = get_task_dispensers().get(self._content.task_dispenser, TableOfContents)
            # Here we use a lambda to ensure we do not pass a fixed list of tasks to the task dispenser
            self._task_dispenser = task_dispenser_class(lambda: self.get_tasks(), self._content.dispenser_data, self.get_id())
        except Exception as e:
            raise CourseUnreadableException(f"Course {self.get_id()} has an invalid task dispenser : {str(e)}")

        # Build the regex for the ACL, allowing for fast matching. Only used internally.
        self._registration_ac_regex = self._build_ac_regex(self._content.registration_ac_list)

    def set_translations(self, translations : dict[str, gettext.GNUTranslations]):
        self._translations = translations

    def get_translation_obj(self, language):
        return self._translations.get(language, gettext.NullTranslations())

    def gettext(self, language, text):
        return self.get_translation_obj(language).gettext(text) if text else ""

    def get_id(self):
        """ Return the _id of this course """
        return self._id

    def get_fs(self):
        """ Returns a FileSystemProvider which points to the folder of this course """
        return self._fs

    def get_task(self, taskid):
        """ Returns a Task object """
        return Task.get(self._id, taskid)

    def get_descriptor(self):
        """ Get the description of the course as a python dict. """
        return copy.deepcopy(self._pre_validated_content)


    def get_staff(self):
        """ Returns a list containing the usernames of all the staff users """
        return list(set(self.get_tutors() + self.get_admins()))

    def get_admins(self):
        """ Returns a list containing the usernames of the administrators of this course """
        return self._content.admins

    def get_tutors(self):
        """ Returns a list containing the usernames of the tutors assigned to this course """
        return self._content.tutors

    def is_open_to_non_staff(self):
        """ Returns true if the course is accessible by users that are not administrator of this course """
        return self.get_accessibility().is_open()

    def is_registration_possible(self, user_info: UserInfo):
        """ Returns true if users can register for this course """
        return self.get_accessibility().is_open() and self._content.registration.is_open() and self.is_user_accepted_by_access_control(user_info)

    def is_password_needed_for_registration(self):
        """ Returns true if a password is needed for registration """
        return self._content.registration_password is not None

    def get_registration_password(self):
        """ Returns the password needed for registration (None if there is no password) """
        return self._content.registration_password

    def get_accessibility(self, plugin_override=True):
        """ Return the AccessibleTime object associated with the accessibility of this course """
        if self.is_archive():
            return AccessibleTime(False)

        vals = plugin_manager.call_hook('course_accessibility', course=self, default=self._content.accessible)
        return vals[0] if len(vals) and plugin_override else self._content.accessible

    def get_registration_accessibility(self):
        """ Return the AccessibleTime object associated with the registration """
        return self._content.registration

    def get_readable_tasks(self):
        """ Returns the list of all available tasks in a course """
        return [
            task[0:len(task)-1]  # remove trailing /
            for task in self._fs.list(folders=True, files=False, recursive=False)
            if self._fs.from_subfolder(task).exists("task.yaml")
        ] if self._fs.exists() else []

    def get_tasks(self) -> dict[str, Task]:
        """ Returns """
        tasks = self.get_readable_tasks()
        output = {}
        for task in tasks:
            try:
                output[task] = self.get_task(task)
            except Exception as e:
                logging.getLogger("inginious.course." + self._id).info("Couldn't load task %s : %s", task, str(e))
        return output

    def get_access_control_method(self):
        """ Returns either None, "username", "binding", or "email", depending on the method used to verify that users can register to the course """
        return self._content.registration_ac

    def get_access_control_accept(self):
        """ Returns either True (accept) or False (deny), depending on the control type used to verify that users can register to the course """
        return self._content.registration_ac_accept

    def get_access_control_list(self) -> List[str]:
        """ Returns the list of all users/emails/binding methods/... (see get_access_control_method) allowed by the AC list """
        return self._content.registration_ac_list

    def can_students_choose_group(self):
        """ Returns True if the students can choose their groups """
        return self._content.groups_student_choice

    def is_lti(self):
        """ True if the current course is in LTI mode """
        return self._content.is_lti

    def lti_keys(self):
        """ {name: key} for the LTI customers """
        return self._content.lti_keys if self._content.is_lti else {}

    def lti_config(self):
        """ LTI Tool config dictionary. Specs are at https://github.com/dmitry-viskov/pylti1.3/blob/master/README.rst?plain=1#L70-L98 """
        return self._content.lti_config if self._content.is_lti else {}

    def lti_secrets(self):
        """ {deployment: secret} for the LTI 1.3 consumers """
        return self._content.lti_secrets if self._content.is_lti else {}

    def lti_url(self):
        """ Returns the URL to the external platform the course is hosted on """
        return self._content.lti_url

    def lti_send_back_grade(self):
        """ True if the current course should send back grade to the LTI Tool Consumer """
        return self._content.is_lti and self._content.lti_send_back_grade

    def is_user_accepted_by_access_control(self, user_info: UserInfo):
        """ Returns True if the user is allowed by the ACL """
        if self.get_access_control_method() is None:
            return True

        keys_per_access_control_method = {
            "username": (lambda: [user_info.username]),
            "email": (lambda: [user_info.email]),
            "binding": (lambda: user_info.bindings.keys())
        }

        if not user_info or self.get_access_control_method() not in keys_per_access_control_method:
            return False

        # check that at least one key matches in the list
        keys = keys_per_access_control_method[self.get_access_control_method()]()
        at_least_one = any(self._registration_ac_regex.fullmatch(key) for key in keys)
        return at_least_one if self.get_access_control_accept() else not at_least_one

    def allow_preview(self):
        return self._content.allow_preview

    def allow_unregister(self, plugin_override=True):
        """ Returns True if students can unregister from course """
        vals = plugin_manager.call_hook('course_allow_unregister', course=self, default=self._content.allow_unregister)
        return vals[0] if len(vals) and plugin_override else self._content.allow_unregister

    def get_name(self, language):
        """ Return the name of this course """
        return self.gettext(language, self._name) if self._name else ""

    def get_description(self, language):
        """Returns the course description """
        description = self.gettext(language, self._content.description) if self._content.description else ''
        return ParsableText(description, "rst")

    def get_tags(self):
        return self._tags

    def get_task_dispenser(self):
        """
       :return: the structure of the course
       """
        return self._task_dispenser

    def _build_ac_regex(self, list_ac):
        """ Build a regex for the AC list, allowing for fast matching. The regex is only used internally """
        return re.compile('|'.join(re.escape(x).replace("\\*", ".*") for x in list_ac))

    def is_archive(self):
        """ Returns true if the course is an archive"""
        return self._content.archived

    def get_archiving_date(self):
        """ Returns the date at which the course was archived as a string (None if not archived)"""
        return self._content.archive_date

    def set_descriptor_element(self, key: str, value: Any):
        self._pre_validated_content[key] = value

    def save(self):
        """ Saves the Course into the filesystem """
        self._fs.put("course.yaml", get_json_or_yaml("course.yaml", self._pre_validated_content))
        if self._new_doc:
            logging.getLogger("inginious.course").info("Course %s created in the factory.", self._fs.prefix)

    @classmethod
    def get(cls, courseid : str) -> Course:
        """ Fetch a course with id courseid from the specified course filesystem"""
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)

        course_fs = get_fs_provider().from_subfolder(courseid)
        if not course_fs.exists("course.yaml"):
            raise CourseNotFoundException()

        course = fetch_or_cache(course_fs, "course.yaml", lambda: _load_course(course_fs, courseid))

        translations = {}
        i18n_fs = course_fs.from_subfolder("$i18n")
        if i18n_fs.exists():
            for f in i18n_fs.list(folders=False, files=True, recursive=False):
                lang, ext = os.path.splitext(f)
                if ext == ".mo":
                    translations[lang] = fetch_or_cache(i18n_fs, f, lambda: gettext.GNUTranslations(i18n_fs.get_fd(f)))

        course.set_translations(translations)
        return course

    def delete(self):
        """ Erase the content of the course folder """
        invalidate_cache(self._fs)
        self._fs.delete()
        logging.getLogger("inginious.course").info("Course %s erased from the factory.", self._fs.prefix)

    @classmethod
    def get_all(cls) -> dict[str, Course]:
        """ Returns a dictionnary with courseid=>Course mapping """
        output = {}
        for courseid in [f[0:len(f) - 1] for f in get_fs_provider().list(folders=True, files=False, recursive=False)]:
            try:
                output[courseid] = Course.get(courseid)
            except Exception as e:
                logging.getLogger("inginious.course").warning("Cannot open course : %s", courseid)
        return output
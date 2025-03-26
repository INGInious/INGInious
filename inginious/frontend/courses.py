# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" A course class with some modification for users """

import copy
import gettext
import re
from typing import List
from datetime import datetime

from inginious.frontend.user_settings.course_user_setting import CourseUserSetting
from inginious.common.tags import Tag
from inginious.frontend.accessible_time import AccessibleTime
from inginious.frontend.parsable_text import ParsableText
from inginious.frontend.user_manager import UserInfo
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.frontend.tasksets import _migrate_from_v_0_6


class Course(object):
    """ A course with some modification for users """

    def __init__(self, courseid, content, taskset_factory, task_factory, plugin_manager, database):
        self._id = courseid
        self._content = content
        self._taskset_factory = taskset_factory
        self._task_factory = task_factory
        self._plugin_manager = plugin_manager
        self._translations = {}

        try:
            self._name = self._content['name']
            self._tasksetid = self._content['tasksetid']
            self._taskset = taskset_factory.get_taskset(self._tasksetid)
        except:
            raise Exception("Course has an invalid name or tasksetid: " + self.get_id())

        _migrate_from_v_0_6(content, self._task_factory.get_all_tasks(self._taskset))

        self._admins = self._content.get('admins', [])
        self._description = self._content.get('description', '')
        self._accessible = AccessibleTime(self._content.get('accessible'))
        self._registration = AccessibleTime(self._content.get('registration'))
        self._registration_password = self._content.get('registration_password')
        self._registration_ac = self._content.get('registration_ac')
        if self._registration_ac not in [None, "username", "binding", "email"]:
            raise Exception("Course has an invalid value for registration_ac: " + self.get_id())
        self._registration_ac_accept = self._content.get('registration_ac_accept', True)
        self._registration_ac_list = self._content.get('registration_ac_list', [])
        self._groups_student_choice = self._content.get("groups_student_choice", False)
        self._allow_unregister = self._content.get('allow_unregister', True)
        self._allow_preview = self._content.get('allow_preview', False)
        self._is_lti = self._content.get('is_lti', False)
        self._lti_url = self._content.get('lti_url', '')
        self._lti_keys = self._content.get('lti_keys', {})
        self._lti_send_back_grade = self._content.get('lti_send_back_grade', False)
        self._tags = {key: Tag(key, tag_dict, self.gettext) for key, tag_dict in self._content.get("tags", {}).items()}
        self._course_user_setting = {key: CourseUserSetting(key,
                                                            field_dict["description"],
                                                            field_dict["type"])
                                     for key, field_dict in self._content.get("fields", {}).items()}
        task_dispensers = self._taskset_factory.get_task_dispensers()
        task_dispenser_class = task_dispensers.get(self._content.get('task_dispenser', 'toc'), TableOfContents)
        # Here we use a lambda to encourage the task dispenser to pass by the task_factory to fetch course tasks
        # to avoid them to be cached along with the course object. Passing the task factory as argument
        # would require to pass the course too, and have a useless reference back.
        try:
            self._task_dispenser = task_dispenser_class(lambda: self._task_factory.get_all_tasks(self._taskset),
                                                        self._content.get("dispenser_data", ''), database, self.get_id())
        except Exception as e:
            raise

        # Force some parameters if LTI is active
        if self.is_lti():
            self._accessible = AccessibleTime({"start": datetime.min, "end": datetime.max.replace(microsecond=0)})
            self._registration = AccessibleTime({"start": datetime.max.replace(microsecond=0), "end": datetime.max.replace(microsecond=0)})
            self._registration_password = None
            self._registration_ac = None
            self._registration_ac_list = []
            self._groups_student_choice = False
            self._allow_unregister = False
        else:
            self._lti_keys = {}
            self._lti_url = ''
            self._lti_send_back_grade = False

        # Build the regex for the ACL, allowing for fast matching. Only used internally.
        self._registration_ac_regex = self._build_ac_regex(self._registration_ac_list)

    def get_translation_obj(self, language):
        return self._translations.get(language, gettext.NullTranslations())

    def gettext(self, language, text):
        return self.get_translation_obj(language).gettext(text) if text else ""

    def get_id(self):
        """ Return the _id of this course """
        return self._id

    def get_taskset(self):
        return self._taskset

    def get_task(self, taskid):
        """ Returns a Task object """
        return self._task_factory.get_task(self._taskset, taskid)

    def get_descriptor(self):
        """ Get (a copy) the description of the course """
        return copy.deepcopy(self._content)

    def get_admins(self):
        """ Returns a list containing the usernames of the administrators of this course """
        return self._admins

    def is_open_to_non_staff(self):
        """ Returns true if the course is accessible by users that are not administrator of this course """
        return self.get_accessibility().is_open()

    def is_registration_possible(self, user_info: UserInfo):
        """ Returns true if users can register for this course """
        return self.get_accessibility().is_open() and self._registration.is_open() and self.is_user_accepted_by_access_control(user_info)

    def is_password_needed_for_registration(self):
        """ Returns true if a password is needed for registration """
        return self._registration_password is not None

    def get_registration_password(self):
        """ Returns the password needed for registration (None if there is no password) """
        return self._registration_password

    def get_accessibility(self, plugin_override=True):
        """ Return the AccessibleTime object associated with the accessibility of this course """
        vals = self._plugin_manager.call_hook('course_accessibility', course=self, default=self._accessible)
        return vals[0] if len(vals) and plugin_override else self._accessible

    def get_registration_accessibility(self):
        """ Return the AccessibleTime object associated with the registration """
        return self._registration

    def get_tasks(self, ordered=False):
        return self._task_dispenser.get_ordered_tasks() if ordered else self._task_factory.get_all_tasks(self._taskset)

    def get_access_control_method(self):
        """ Returns either None, "username", "binding", or "email", depending on the method used to verify that users can register to the course """
        return self._registration_ac

    def get_access_control_accept(self):
        """ Returns either True (accept) or False (deny), depending on the control type used to verify that users can register to the course """
        return self._registration_ac_accept

    def get_access_control_list(self) -> List[str]:
        """ Returns the list of all users/emails/binding methods/... (see get_access_control_method) allowed by the AC list """
        return self._registration_ac_list

    def can_students_choose_group(self):
        """ Returns True if the students can choose their groups """
        return self._groups_student_choice

    def is_lti(self):
        """ True if the current course is in LTI mode """
        return self._is_lti

    def lti_keys(self):
        """ {name: key} for the LTI customers """
        return self._lti_keys if self._is_lti else {}

    def lti_url(self):
        """ Returns the URL to the external platform the course is hosted on """
        return self._lti_url

    def lti_send_back_grade(self):
        """ True if the current course should send back grade to the LTI Tool Consumer """
        return self._is_lti and self._lti_send_back_grade

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
        return self._allow_preview

    def allow_unregister(self, plugin_override=True):
        """ Returns True if students can unregister from course """
        vals = self._plugin_manager.call_hook('course_allow_unregister', course=self, default=self._allow_unregister)
        return vals[0] if len(vals) and plugin_override else self._allow_unregister

    def get_name(self, language):
        """ Return the name of this course """
        return self.gettext(language, self._name) if self._name else ""

    def get_description(self, language):
        """Returns the course description """
        description = self.gettext(language, self._description) if self._description else ''
        return ParsableText(description, "rst", translation=self.get_translation_obj(language))

    def get_tags(self):
        return self._tags

    def get_course_user_settings(self):
        """
        :return: The course user settings dictionary for a course.
        """
        return self._course_user_setting

    def get_task_dispenser(self):
        """
       :return: the structure of the course
       """
        return self._task_dispenser

    def _build_ac_regex(self, list_ac):
        """ Build a regex for the AC list, allowing for fast matching. The regex is only used internally """
        return re.compile('|'.join(re.escape(x).replace("\\*", ".*") for x in list_ac))

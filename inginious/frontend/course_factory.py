# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Factory for loading courses from disk """
import logging

from inginious.common.filesystems import FileSystemProvider
from inginious.common.log import get_course_logger
from inginious.common.base import id_checker, get_json_or_yaml, loads_json_or_yaml
from inginious.common.exceptions import InvalidNameException, CourseNotFoundException, CourseUnreadableException, CourseAlreadyExistsException

from inginious.frontend.courses import Course


class CourseFactory(object):
    """ Load courses from disk """
    _logger = logging.getLogger("inginious.course_factory")

    def __init__(self, filesystem: FileSystemProvider):
        self._filesystem = filesystem
        self._cache = {}

    def get_course(self, courseid):
        """
        :param courseid: the course id of the course
        :raise: InvalidNameException, CourseNotFoundException, CourseUnreadableException
        :return: an object representing the course, of the type given in the constructor
        """
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)
        if self._cache_update_needed(courseid):
            self._update_cache(courseid)

        return self._cache[courseid][0]

    def get_task(self, courseid, taskid):
        """
        Shorthand for CourseFactory.get_course(courseid).get_task(taskid)
        :param courseid: the course id of the course
        :param taskid: the task id of the task
        :raise InvalidNameException, CourseNotFoundException, CourseUnreadableException, TaskNotFoundException, TaskUnreadableException
        :return: an object representing the task, of the type given in the constructor
        """
        return self.get_course(courseid).get_task(taskid)

    def get_fs(self):
        """
        :return: a FileSystemProvider pointing to the task directory
        """
        return self._filesystem

    def get_course_fs(self, courseid):
        """
        :param courseid: the course id of the course
        :return: a FileSystemProvider pointing to the directory of the course 
        """
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)
        return self._filesystem.from_subfolder(courseid)

    def get_all_courses(self):
        """
        :return: a table containing courseid=>Course pairs
        """
        course_ids = [f[0:len(f)-1] for f in self._filesystem.list(folders=True, files=False, recursive=False)]  # remove trailing "/"
        output = {}
        for courseid in course_ids:
            try:
                output[courseid] = self.get_course(courseid)
            except Exception as e:
                get_course_logger(courseid).warning("Cannot open course : %s", str(e))
        return output

    def create_course(self, courseid, init_content):
        """
        Create a new course folder and set initial descriptor content, folder can already exist
        :param courseid: the course id of the course
        :param init_content: initial descriptor content
        :raise: InvalidNameException or CourseAlreadyExistsException
        """
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)

        course_fs = self.get_course_fs(courseid)
        course_fs.ensure_exists()

        if course_fs.exists("course.yaml") or course_fs.exists("course.json"):
            raise CourseAlreadyExistsException("Course with id " + courseid + " already exists.")
        else:
            course_fs.put("course.yaml", get_json_or_yaml("course.yaml", init_content))

        get_course_logger(courseid).info("Course %s created in the factory.", courseid)

    def delete_course(self, courseid):
        """
        Erase the content of the course folder
        :param courseid: the course id of the course
        :raise: InvalidNameException or CourseNotFoundException
        """
        if not id_checker(courseid):
            raise InvalidNameException("Course with invalid name: " + courseid)

        course_fs = self.get_course_fs(courseid)

        if not course_fs.exists():
            raise CourseNotFoundException()

        course_fs.delete()

        get_course_logger(courseid).info("Course %s erased from the factory.", courseid)

    def _cache_update_needed(self, courseid):
        """
        :param courseid: the (valid) course id of the course
        :raise InvalidNameException, CourseNotFoundException
        :return: True if an update of the cache is needed, False else
        """
        if courseid not in self._cache:
            return True

        try:
            last_update = {"course.yaml": self.get_course_fs(courseid).get_last_modification_time("course.yaml")}
            translations_fs = self.get_course_fs(courseid).from_subfolder("$i18n")
            if translations_fs.exists():
                for f in translations_fs.list(folders=False, files=True, recursive=False):
                    lang = f[0:len(f) - 3]
                    if translations_fs.exists(lang + ".mo"):
                        last_update["$i18n/" + lang + ".mo"] = translations_fs.get_last_modification_time(lang + ".mo")
        except:
            raise CourseNotFoundException()

        last_modif = self._cache[courseid][1]
        for filename, mftime in last_update.items():
            if filename not in last_modif or last_modif[filename] < mftime:
                return True

        return False

    def _update_cache(self, courseid):
        """
        Updates the cache
        :param courseid: the (valid) course id of the course
        :raise InvalidNameException, CourseNotFoundException, CourseUnreadableException
        """
        self._logger.info("Caching course {}".format(courseid))
        try:
            course_descriptor = loads_json_or_yaml("course.yaml", self.get_course_fs(courseid).get("course.yaml").decode("utf8"))
        except Exception as e:
            raise CourseUnreadableException(str(e))

        last_modif = {"course.yaml": self.get_course_fs(courseid).get_last_modification_time("course.yaml")}
        translations_fs = self.get_course_fs(courseid).from_subfolder("$i18n")
        if translations_fs.exists():
            for f in translations_fs.list(folders=False, files=True, recursive=False):
                lang = f[0:len(f) - 3]
                if translations_fs.exists(lang + ".mo"):
                    last_modif["$i18n/" + lang + ".mo"] = translations_fs.get_last_modification_time(lang + ".mo")

        self._cache[courseid] = (
            Course(courseid, course_descriptor, self.get_course_fs(courseid)),
            last_modif
        )

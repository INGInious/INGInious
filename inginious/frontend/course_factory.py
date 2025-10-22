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

    def get_course(self, courseid):
        """
        :param courseid: the course id of the course
        :raise: InvalidNameException, CourseNotFoundException, CourseUnreadableException
        :return: an object representing the course, of the type given in the constructor
        """
        return Course.get(courseid, self._filesystem)

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

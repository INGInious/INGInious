# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Some type of exceptions used by parts of INGInious """

class NotLoadedException(Exception):
    pass


class InvalidNameException(Exception):
    pass


class CourseNotFoundException(Exception):
    pass

class CourseNotArchivable(Exception):
    pass


class TaskNotFoundException(Exception):
    pass


class CourseUnreadableException(Exception):
    """ Raised when a course's descriptor is not readable (e.g. invalid YAML) '"""

    def __init__(self, message=None):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return self.message if self.message else "Course descriptor is not readable"


class CourseAlreadyExistsException(Exception):
    pass

class TaskAlreadyExistsException(Exception):
    pass

class TaskUnreadableException(Exception):
    pass


class TaskReaderNotFoundException(Exception):
    pass


class ImportCourseException(Exception):
    pass


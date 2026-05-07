# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

"""A class for the course from the marketplace"""

import logging
import requests

from inginious import MARKETPLACE_URL
from inginious.common.base import loads_json_or_yaml
from inginious.common.exceptions import CourseNotFoundException
from inginious.frontend.parsable_text import ParsableText


class MarketplaceCourse(object):
    """A class for the course from the marketplace"""

    def __init__(self, structure):
        self._id = structure["id"]
        self._languages = structure["languages"]
        self._license = structure["license"]
        self._maintainers = structure["maintainers"]
        self._authors = structure["authors"]
        self._name = structure["name"]
        self._short_desc = structure["short_desc"]
        self._description = structure["description"]
        self._default_language = structure["default_language"]
        self._link = structure["link"]

    def get_id(self):
        """Return the id of this course"""
        return self._id

    def get_languages(self):
        """Return the languages of this course"""
        return self._languages

    def get_license(self):
        """Return the license of this course"""
        return self._license

    def get_maintainers(self):
        """Return the maintainers of this course"""
        return self._maintainers

    def get_authors(self):
        """Return the authors of this course"""
        return self._authors

    def get_name(self, language):
        """Return the name of this course"""
        if language in self._name:
            return self._name[language]
        elif self._default_language in self._name:
            return self._name[self._default_language]
        else:
            return list(self._name.keys())[0]

    def get_short_desc(self, language):
        """Returns the short course description"""
        if language in self._short_desc:
            return self._short_desc[language]
        elif self._default_language in self._short_desc:
            return self._short_desc[self._default_language]
        else:
            return list(self._short_desc.keys())[0]

    def get_description(self, language):
        """Returns the course description"""
        if language in self._description:
            return ParsableText(self._description[language], "rst")
        elif self._default_language in self._description:
            return ParsableText(self._description[self._default_language], "rst")
        else:
            return ParsableText(list(self._short_desc.keys())[0], "rst")

    def get_link(self):
        """Return the name of this course"""
        return self._link


def get_all_marketplace_courses():
    r = requests.get(MARKETPLACE_URL)
    marketplace_file = loads_json_or_yaml("marketplace.json", r.content)
    try:
        return {course["id"]: MarketplaceCourse(course) for course in marketplace_file}
    except:
        logging.getLogger("inginious.webapp.marketplace").info(
            "Could not load marketplace"
        )
        return {}


def get_marketplace_course(courseid):
    courses = get_all_marketplace_courses()
    if courseid not in courses:
        raise CourseNotFoundException("Marketplace course not found")
    return courses[courseid]

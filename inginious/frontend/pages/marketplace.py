# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Course page """
import sys
from flask import request, redirect, render_template
from werkzeug.exceptions import Forbidden

from inginious.common.base import id_checker
from inginious.common.exceptions import ImportCourseException
from inginious.common.log import get_course_logger

from inginious.frontend.courses import Course
from inginious.frontend.marketplace_courses import get_all_marketplace_courses, get_marketplace_course
from inginious.frontend.pages.utils import INGIniousAuthPage

if sys.platform == 'win32':
    import pbs
    git = pbs.Command('git')
else:
    from sh import git  # pylint: disable=no-name-in-module


class MarketplacePage(INGIniousAuthPage):
    """ Course marketplace """

    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ GET request """
        # Change to teacher privilege when created
        if not self.user_manager.user_is_superadmin():
            raise Forbidden(description=_("You don't have superadmin rights on this course."))
        return self.show_page()

    def POST_AUTH(self):  # pylint: disable=arguments-differ
        """ POST request """
        # Change to teacher privilege when created
        if not self.user_manager.user_is_superadmin():
            raise Forbidden(description=_("You're not allowed to do that"))

        user_input = request.form
        errors = []
        if "new_courseid" in user_input:
            new_courseid = user_input["new_courseid"]
            try:
                course = get_marketplace_course(user_input["courseid"])
                import_course(course, new_courseid, self.user_manager.session_username(), self.course_factory)
            except ImportCourseException as e:
                errors.append(str(e))
            except:
                errors.append(_("User returned an invalid form."))
            if not errors:
                return redirect(self.app.get_path("admin", new_courseid))
        return self.show_page(errors)

    def show_page(self, errors=None):
        """ Prepares and shows the course marketplace """
        if errors is None:
            errors = []
        courses = get_all_marketplace_courses()
        return render_template("marketplace.html", courses=courses, errors=errors)


def import_course(course, new_courseid, username, course_factory):
    if not id_checker(new_courseid):
        raise ImportCourseException("Course with invalid name: " + new_courseid)
    course_fs = course_factory.get_course_fs(new_courseid)

    if course_fs.exists("course.yaml") or course_fs.exists("course.json"):
        raise ImportCourseException("Course with id " + new_courseid + " already exists.")

    try:
        git.clone(course.get_link(), course_fs.prefix)
    except:
        raise ImportCourseException(_("Couldn't clone course into your instance"))

    try:
        old_descriptor = course_factory.get_course(new_courseid).get_descriptor()
    except:
        old_descriptor ={}

    try:
        new_descriptor = {"description": old_descriptor.get("description", ""),
                          'admins': [username],
                          "accessible": False,
                          "tags": old_descriptor.get("tags", {})}
        if "name" in old_descriptor:
            new_descriptor["name"] = old_descriptor["name"] + " - " + new_courseid
        else:
            new_descriptor["name"] = new_courseid
        if "toc" in old_descriptor:
            new_descriptor["task_dispenser"] = "toc"
            new_descriptor["dispenser_data"] = {"config": {}, "toc": old_descriptor["toc"]}

        c = Course(new_courseid, new_descriptor, course_fs)
        c.save()
    except:
        course_factory.delete_course(new_courseid)
        raise ImportCourseException(_("An error occur while editing the course description"))

    get_course_logger(new_courseid).info("Course %s cloned from the marketplace.", new_courseid)


# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Course page """
from flask import request, redirect, render_template
from werkzeug.exceptions import Forbidden

from inginious.common.exceptions import ImportCourseException
from inginious.frontend.marketplace_courses import get_marketplace_course
from inginious.frontend.pages.marketplace import import_course
from inginious.frontend.pages.utils import INGIniousAuthPage


class MarketplaceCoursePage(INGIniousAuthPage):
    """ Course marketplace """

    def get_course(self, courseid):
        """ Return the course """
        try:
            course = get_marketplace_course(courseid)
        except:
            raise Forbidden(description=_("Course unavailable."))

        return course

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        # Change to teacher privilege when created
        if not self.user_manager.user_is_superadmin():
            raise Forbidden(description=_("You're not allowed to do that"))

        course = self.get_course(courseid)
        return self.show_page(course)

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        # Change to teacher privilege when created
        if not self.user_manager.user_is_superadmin():
            raise Forbidden(description=_("You're not allowed to do that"))

        course = self.get_course(courseid)
        user_input = request.form
        errors = []
        if "new_courseid" in user_input:
            new_courseid = user_input["new_courseid"]
            try:
                import_course(course, new_courseid, self.user_manager.session_username(), self.course_factory)
            except ImportCourseException as e:
                errors.append(str(e))
            if not errors:
                return redirect(self.app.get_path("course", new_courseid))
        return self.show_page(course, errors)

    def show_page(self, course, errors=None):
        """ Prepares and shows the course marketplace """
        if errors is None:
            errors = []

        return render_template("marketplace_course.html", course=course, errors=errors)

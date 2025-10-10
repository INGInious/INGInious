# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Course page """
from flask import redirect, request, render_template
from werkzeug.exceptions import NotFound

from inginious.common.exceptions import InvalidNameException, CourseNotFoundException, CourseUnreadableException

from inginious.frontend.pages.utils import INGIniousAuthPage


class CourseRegisterPage(INGIniousAuthPage):
    """ Registers a user to a course """

    def basic_checks(self, courseid):
        try:
            course = self.course_factory.get_course(courseid)
        except (InvalidNameException, CourseNotFoundException, CourseUnreadableException) as e:
            raise NotFound(description=_("This course doesn't exist."))

        username = self.user_manager.session_username()
        user_info = self.user_manager.get_user_info(username)

        if self.user_manager.course_is_user_registered(course, username) or not course.is_registration_possible(user_info):
            return course, None

        return course, username

    def GET_AUTH(self, courseid):
        course, username = self.basic_checks(courseid)
        if not username:
            return redirect(self.app.get_path("course", course.get_id()))
        return render_template("course_register.html", course=course, error=False)

    def POST_AUTH(self, courseid):
        course, username = self.basic_checks(courseid)
        user_input = request.form
        success = self.user_manager.course_register_user(course, username, user_input.get("register_password", None))

        if success:
            return redirect(self.app.get_path("course", course.get_id()))
        else:
            return render_template("course_register.html", course=course, error=True)

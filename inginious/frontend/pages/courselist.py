# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Index page """
from collections import OrderedDict
from flask import render_template

from inginious.frontend.pages.utils import INGIniousPage

from inginious.frontend.user_manager import user_manager

from inginious.frontend.course_factory import course_factory

class CourseListPage(INGIniousPage):
    """ Index page """

    def GET(self):  # pylint: disable=arguments-differ
        """ Display main course list page """
        return self.show_page()

    def POST(self):  # pylint: disable=arguments-differ
        """ Display main course list page """
        return self.show_page()

    def show_page(self):
        """  Display main course list page """
        username = user_manager.session_username()
        user_info = user_manager.get_user_info(username)
        all_courses = course_factory.get_all_courses()

        # Display
        open_courses = {courseid: course for courseid, course in all_courses.items() if course.is_open_to_non_staff()}
        open_courses = OrderedDict(sorted(iter(open_courses.items()), key=lambda x: x[1].get_name(user_manager.session_language())))

        return render_template("courselist.html", open_courses=open_courses, user_info=user_info)

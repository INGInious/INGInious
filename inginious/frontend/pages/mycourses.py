# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Index page """
from collections import OrderedDict
from flask import request, render_template
from inginious.frontend.courses import Course
from inginious.frontend.pages.utils import INGIniousAuthPage


class MyCoursesPage(INGIniousAuthPage):
    """ Index page """

    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ Display main course list page """
        return self.show_page(None)

    def POST_AUTH(self):  # pylint: disable=arguments-differ
        """ Parse course registration or course creation and display the course list page """

        user_input = request.form
        success = None

        if "new_courseid" in user_input and self.user_manager.user_is_superadmin():
            try:
                courseid = user_input["new_courseid"]
                Course(courseid, {"name": courseid, "accessible": False}).save()
                success = True
            except:
                success = False
        elif "pinning_courseid" in user_input:
            pinned_courses = self.user_manager.get_user_pinned_courses_ids(self.user_manager.session_username())
            pinned_courses = [course for course in pinned_courses if course in self.course_factory.get_all_courses()]

            courseid = user_input["pinning_courseid"]
            if courseid not in pinned_courses:
                if len(pinned_courses) == 6:
                    return {"error": "Maximum number of pins"}

                self.user_manager.pin_course(self.user_manager.session_username(), courseid)
                # return data for html
                pin_html_data = {
                    "courseid": courseid,
                    "is_lti" : self.course_factory.get_course(courseid).is_lti(),
                    "lti_url" : self.course_factory.get_course(courseid).lti_url(),
                    "name": self.course_factory.get_course(courseid).get_name(self.user_manager.session_language()),
                    "path": self.app.get_path("course", courseid),
                    "description": str(self.course_factory.get_course(courseid).get_description(self.user_manager.session_language()))
                }
                return pin_html_data
            else:
                self.user_manager.unpin_course(self.user_manager.session_username(), courseid)
                return {"courseid": courseid}

        return self.show_page(success)

    def show_page(self, success):
        """  Display main course list page """
        username = self.user_manager.session_username()
        user_info = self.user_manager.get_user_info(username)

        all_courses = Course.get_all()

        # Display
        open_courses = {courseid: course for courseid, course in all_courses.items()
                        if self.user_manager.course_is_open_to_user(course, username, False) and
                        self.user_manager.course_is_user_registered(course, username)}
        open_courses = OrderedDict(sorted(iter(open_courses.items()), key=lambda x: x[1].get_name(self.user_manager.session_language())))
        pinned_courses_ids = [course for course in self.user_manager.get_user_pinned_courses_ids(username) if course in open_courses]
        pinned_courses = {courseid: self.course_factory.get_course(courseid) for courseid in pinned_courses_ids if courseid in open_courses}

        last_submissions = self.submission_manager.get_user_last_submissions(5, {"courseid__in": list(open_courses.keys())})
        except_free_last_submissions = []
        for submission in last_submissions:
            try:
                submission["task"] = open_courses[submission['courseid']].get_task(submission['taskid'])
                except_free_last_submissions.append(submission)
            except:
                pass

        registerable_courses = {courseid: course for courseid, course in all_courses.items() if
                                not self.user_manager.course_is_user_registered(course, username) and
                                course.is_registration_possible(user_info)}

        registerable_courses = OrderedDict(sorted(iter(registerable_courses.items()), key=lambda x: x[1].get_name(self.user_manager.session_language())))

        return render_template("mycourses.html",
                                           open_courses=open_courses,
                                           pinned_courses=pinned_courses,
                                           registrable_courses=registerable_courses,
                                           submissions=except_free_last_submissions,
                                           success=success)

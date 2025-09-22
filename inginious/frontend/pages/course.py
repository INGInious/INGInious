# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Course page """
import flask
from flask import redirect, render_template
from werkzeug.exceptions import NotFound

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend import database
from inginious.frontend.user_manager import user_manager

def handle_course_unavailable(get_path, user_manager, course):
    """ Displays the course_unavailable page or the course registration page """
    reason = user_manager.course_is_open_to_user(course, lti=False, return_reason=True)
    if reason == "unregistered_not_previewable":
        username = user_manager.session_username()
        user_info = user_manager.get_user_info(username)
        if course.is_registration_possible(user_info):
            return redirect(get_path("register", course.get_id()))
    return render_template("course_unavailable.html", reason=reason)


class CoursePage(INGIniousAuthPage):
    """ Course page """

    def preview_allowed(self, courseid):
        course = self.get_course(courseid)
        return course.get_accessibility().is_open() and course.allow_preview()

    def get_course(self, courseid):
        """ Return the course """
        try:
            course = self.course_factory.get_course(courseid)
        except:
            raise NotFound(description=_("Course not found."))

        return course

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course = self.get_course(courseid)

        user_input = flask.request.form
        if "unregister" in user_input and course.allow_unregister():
            user_manager.course_unregister_user(courseid, user_manager.session_username())
            return redirect(self.app.get_path('mycourses'))

        return self.show_page(course)

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course = self.get_course(courseid)
        return self.show_page(course)

    def show_page(self, course):
        """ Prepares and shows the course page """
        username = user_manager.session_username()
        if not user_manager.course_is_open_to_user(course, lti=False):
            return handle_course_unavailable(self.app.get_path, user_manager, course)
        else:
            tasks = course.get_tasks()

            user_task_list = course.get_task_dispenser().get_user_task_list([username])[username]

            # Get 5 last submissions
            last_submissions = []
            for submission in self.submission_manager.get_user_last_submissions(5, {"courseid": course.get_id(), "taskid": {"$in": user_task_list}}):
                submission["taskname"] = tasks[submission['taskid']].get_name(user_manager.session_language())
                last_submissions.append(submission)

            # Compute course/tasks scores
            tasks_data = {taskid: {"succeeded": False, "grade": 0.0} for taskid in user_task_list}
            user_tasks = database.user_tasks.find({"username": username, "courseid": course.get_id(), "taskid": {"$in": user_task_list}})

            for user_task in user_tasks:
                tasks_data[user_task["taskid"]]["succeeded"] = user_task["succeeded"]
                tasks_data[user_task["taskid"]]["grade"] = user_task["grade"]

            course_grade = course.get_task_dispenser().get_course_grade(username)

            # Get tag list
            categories = course.get_task_dispenser().get_all_categories()

            # Get user info
            user_info = user_manager.get_user_info(username)

            return render_template("course.html", user_info=user_info,
                                               course=course,
                                               submissions=last_submissions,
                                               tasks_data=tasks_data,
                                               grade=course_grade,
                                               category_filter_list=categories)

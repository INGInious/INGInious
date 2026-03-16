# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Course page """
import flask
from flask import current_app, session, redirect, render_template, url_for
from werkzeug.exceptions import NotFound

from inginious.frontend.courses import Course
from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.models import UserTask


def handle_course_unavailable(user_manager, course):
    """ Displays the course_unavailable page or the course registration page """
    reason = user_manager.course_is_open_to_user(course, lti=False, return_reason=True)
    if reason == "unregistered_not_previewable":
        user_info = user_manager.get_user_info(session.username)
        if course.is_registration_possible(user_info):
            return redirect(url_for("courseregisterpage", courseid=course.get_id()))
    return render_template("course_unavailable.html", reason=reason)


class CoursePage(INGIniousAuthPage):
    """ Course page """

    def preview_allowed(self, courseid):
        course = self.get_course(courseid)
        return course.get_accessibility().is_open() and course.allow_preview()

    def get_course(self, courseid):
        """ Return the course """
        try:
            course = Course.get(courseid)
        except:
            raise NotFound(description=_("Course not found."))

        return course

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course = self.get_course(courseid)

        user_input = flask.request.form
        if "unregister" in user_input and course.allow_unregister():
            self.user_manager.course_unregister_user(courseid, session.username)
            return redirect(url_for('mycoursespage'))

        return self.show_page(course)

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course = self.get_course(courseid)
        return self.show_page(course)

    def show_page(self, course):
        """ Prepares and shows the course page """
        username = session.username
        if not self.user_manager.course_is_open_to_user(course, lti=False):
            return handle_course_unavailable(self.user_manager, course)
        else:
            tasks = course.get_tasks()

            user_task_list = course.get_task_dispenser().get_user_task_list([username])[username]

            # Get 5 last submissions
            last_submissions = []
            for submission in self.submission_manager.get_user_last_submissions(5, {"courseid": course.get_id(), "taskid__in": user_task_list}):
                submission["taskname"] = tasks[submission['taskid']].get_name(session.language)
                last_submissions.append(submission)

            # Compute course/tasks scores
            tasks_data = {taskid: {"succeeded": False, "grade": 0.0} for taskid in user_task_list}
            user_tasks = UserTask.objects(username=username, courseid=course.get_id(), taskid__in=user_task_list)

            for user_task in user_tasks:
                tasks_data[user_task["taskid"]]["succeeded"] = user_task["succeeded"]
                tasks_data[user_task["taskid"]]["grade"] = user_task["grade"]

            course_grade = course.get_task_dispenser().get_course_grade(user_tasks, username)

            # Get tag list
            categories = course.get_task_dispenser().get_all_categories()

            # Get user info
            user_info = self.user_manager.get_user_info(username)

            return render_template("course.html", user_info=user_info,
                                               course=course,
                                               submissions=last_submissions,
                                               tasks_data=tasks_data,
                                               grade=course_grade,
                                               category_filter_list=categories)

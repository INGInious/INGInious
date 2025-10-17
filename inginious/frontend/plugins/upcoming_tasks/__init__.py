# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#

""" A plugin that allow students to see their futur work in a single place for all their courses """
import os
from collections import OrderedDict
from datetime import datetime, timedelta
from flask import request, send_from_directory, render_template

from inginious.frontend.courses import Course
from inginious.frontend.pages.utils import INGIniousPage, INGIniousAuthPage

PATH_TO_PLUGIN = os.path.abspath(os.path.dirname(__file__))


def menu():
    """ Displays the link to the board on the main page, if the plugin is activated """
    return render_template("upcoming_tasks/main_menu.html")


class StaticMockPage(INGIniousPage):
    """ MockPage based on auto-evaluation plugin structure """

    def GET(self, path):
        return send_from_directory(os.path.join(PATH_TO_PLUGIN, "static"), path)

    def POST(self, path):
        return self.GET(path)


class UpComingTasksBoard(INGIniousAuthPage):

    def GET_AUTH(self):
        """ Called when reaching the page """
        time_planner = "unlimited"
        return self.page(time_planner)

    def POST_AUTH(self):
        """ Called when modifying time planner """
        user_input = request.form
        time_planner = user_input.get("time_planner", default="unlimited")
        return self.page(time_planner)

    def time_planner_conversion(self, string_time_planner):
        """ Used to convert the time_planner options into int value """
        if string_time_planner in ["7", "14", "30"]:
            return int(string_time_planner)
        return 100000

    def page(self, time_planner):
        """ General main method called for GET and POST """
        username = self.user_manager.session_username()
        all_courses = Course.get_all(self.fs_provider)
        time_planner = self.time_planner_conversion(time_planner)

        # Get the courses id
        open_courses = {courseid: course for courseid, course in all_courses.items()
                        if self.user_manager.course_is_open_to_user(course, username, False) and
                        self.user_manager.course_is_user_registered(course, username)}

        # Get last submissions for left panel
        last_submissions = self.submission_manager.get_user_last_submissions(5, {"courseid": {"$in": list(open_courses.keys())}})
        except_free_last_submissions = []
        for submission in last_submissions:
            try:
                submission["task"] = open_courses[submission['courseid']].get_task(submission['taskid'])
                except_free_last_submissions.append(submission)
            except:
                pass

        # Get the courses tasks, remove finished ones and courses that have no available unfinished tasks with upcoming deadline in range
        tasks_data = {}
        succeeded_courses = []
        all_accessibilities = {}
        all_tasks = {courseid: course.get_tasks() for courseid, course in open_courses.items()}

        for courseid, course in open_courses.items():
            tasks = all_tasks[courseid]
            accessibilities = course.get_task_dispenser().get_accessibilities(tasks.keys(), [username])[username]
            accessibilities = OrderedDict(sorted(accessibilities.items(), key=lambda x: x[1].get_soft_end_date()))
            all_accessibilities[courseid] = accessibilities

            outdated_tasks = [taskid for taskid, accessibility in accessibilities.items() if (not accessibility.is_open()) or ((accessibility.get_soft_end_date()) > (datetime.now()+timedelta(days=time_planner)))]
            new_user_task_list = [taskid for taskid, accessibility in accessibilities.items() if accessibility.after_start() and taskid not in outdated_tasks]

            tasks_data[courseid] = {taskid: {"succeeded": False, "grade": 0.0} for taskid in new_user_task_list}
            user_tasks = self.database.user_tasks.find({"username": username, "courseid": course.get_id(), "taskid": {"$in": new_user_task_list}})
            for user_task in user_tasks:
                if not user_task["succeeded"]:
                    tasks_data[courseid][user_task["taskid"]]["succeeded"] = user_task["succeeded"]
                    tasks_data[courseid][user_task["taskid"]]["grade"] = user_task["grade"]

                else:
                    del tasks_data[courseid][user_task["taskid"]]
            # Remove courses with no unfinished available tasks with deadline and lti courses
            if (len(tasks_data[courseid]) == 0) or course.is_lti():
                succeeded_courses.append(courseid)

        # Remove succeeded courses (including lti courses)
        for succeeded_course in succeeded_courses:
            del open_courses[succeeded_course]

        sorted_tasks = {courseid: OrderedDict(
            [(taskid, all_tasks[courseid][taskid]) for taskid, accessibility in all_accessibilities[courseid].items() if
             taskid in tasks_data[courseid]]) for courseid in open_courses}

        # Sort the courses based on the most urgent task for each course
        open_courses = OrderedDict(sorted(list(open_courses.items()), key=lambda x: all_accessibilities[x[0]][list(sorted_tasks[x[0]].keys())[0]].get_soft_end_date()))

        return render_template("upcoming_tasks/coming_tasks.html",
                                           open_courses=open_courses,
                                           tasks_data=tasks_data,
                                           sorted_tasks=sorted_tasks,
                                           time_planner=["7", "14", "30", "unlimited"],
                                           submissions=except_free_last_submissions)


def init(plugin_manager, _, _2, config):
    """ Init the plugin """
    plugin_manager.add_page('/coming_tasks', UpComingTasksBoard.as_view("upcomingtasksboardpage"))
    plugin_manager.add_page('/plugins/coming_tasks/static/<path:path>', StaticMockPage.as_view("upcomingtasksstaticmockpage"))
    plugin_manager.add_hook('main_menu', menu)
    plugin_manager.add_template_prefix('upcoming_tasks', PATH_TO_PLUGIN + "/templates")

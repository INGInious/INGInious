# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from collections import OrderedDict

from flask import request, render_template

from inginious.frontend.pages.course_admin.utils import make_csv, INGIniousAdminPage


class CourseStudentInfoPage(INGIniousAdminPage):
    """ List information about a student """

    def GET_AUTH(self, courseid, username):  # pylint: disable=arguments-differ
        """ GET request """
        course, __ = self.get_course_and_check_rights(courseid)
        return self.page(course, username)

    def POST_AUTH(self, courseid, username):
        data = request.form
        taskid = data["taskid"]
        course, __ = self.get_course_and_check_rights(courseid)

        self.user_manager.reset_user_task_state(courseid, taskid, username)

        return self.page(course, username)

    def submission_url_generator(self, username, taskid):
        """ Generates a submission url """
        return "?tasks=" + taskid + "&users=" + username

    def page(self, course, username):
        """ Get all data and display the page """
        data = list(self.database.user_tasks.find({"username": username, "courseid": course.get_id()}))

        tasks = course.get_tasks(True)
        user_task_list = course.get_task_dispenser().get_user_task_list([username])[username]
        result = OrderedDict([(taskid, {"taskid": taskid, "name": tasks[taskid].get_name(self.user_manager.session_language()),
                                 "tried": 0, "status": "notviewed", "grade": 0, "visible": False,
                                 "url": self.submission_url_generator(username, taskid)}) for taskid in tasks])

        for taskdata in data:
            if taskdata["taskid"] in result:
                result[taskdata["taskid"]]["tried"] = taskdata["tried"]
                if taskdata["tried"] == 0:
                    result[taskdata["taskid"]]["status"] = "notattempted"
                elif taskdata["succeeded"]:
                    result[taskdata["taskid"]]["status"] = "succeeded"
                else:
                    result[taskdata["taskid"]]["status"] = "failed"
                result[taskdata["taskid"]]["grade"] = taskdata["grade"]
                result[taskdata["taskid"]]["submissionid"] = str(taskdata["submissionid"])

        for taskid in user_task_list:
            result[taskid]["visible"] = True

        if "csv" in request.args:
            return make_csv(result)

        return render_template("course_admin/student_info.html", course=course,
                                           username=username, data=result)

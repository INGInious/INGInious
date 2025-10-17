# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" An algorithm contest plugin for INGInious. Based on the same principles than contests like ACM-ICPC. """

import os
import copy
from collections import OrderedDict
from datetime import datetime, timedelta

import pymongo
from flask import request, render_template

from werkzeug.exceptions import NotFound
from inginious.frontend.courses import Course
from inginious.frontend.accessible_time import AccessibleTime
from inginious.frontend.pages.course_admin.utils import INGIniousAdminPage
from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.task_dispensers.toc import TableOfContents

PATH_TO_PLUGIN = os.path.abspath(os.path.dirname(__file__))

def add_admin_menu(course): # pylint: disable=unused-argument
    """ Add a menu for the contest settings in the administration """
    task_dispenser = course.get_task_dispenser()
    if task_dispenser.get_id() == Contest.get_id():
        return ('contest', '<i class="fa fa-trophy fa-fw"></i>&nbsp; Contest')
    else:
        return None


class Contest(TableOfContents):

    def __init__(self, task_list_func, dispenser_data, database, course_id):
        TableOfContents.__init__(self, task_list_func, dispenser_data.get("toc_data", {}), database, course_id)
        self._contest_settings = dispenser_data.get(
            'contest_settings',
            {"enabled": False,
             "start": datetime.now().astimezone().isoformat(),
             "end": (datetime.now().astimezone() + timedelta(hours=1)).isoformat(),
             "blackout": 0,
             "penalty": 20}
        )

    @classmethod
    def get_id(cls):
        return "contest"

    @classmethod
    def get_name(cls, language):
        return "Contest"

    def check_dispenser_data(self, dispenser_data):
        """ Checks the dispenser data as formatted by the form from render_edit function """
        data, errors = TableOfContents.check_dispenser_data(self, dispenser_data)
        return {"toc_data": data, "contest_settings": self._contest_settings} if data else None, errors

    def get_accessibilities(self, taskids, usernames): # pylint: disable=unused-argument
        tasks_in_toc = self._toc.get_tasks()
        contest_data = self.get_contest_data()
        if contest_data['enabled']:
            return {
                username: {
                    taskid: AccessibleTime(contest_data['start'] + '/')
                    if taskid in tasks_in_toc else AccessibleTime(False)
                    for taskid in taskids
                }
                for username in usernames
            }
        else:
            return TableOfContents.get_accessibilities(self, taskids, usernames)

    def get_contest_data(self):
        """ Returns the settings of the contest for this course """
        return self._contest_settings


def course_menu(course):
    """ Displays some informations about the contest on the course page"""
    task_dispenser = course.get_task_dispenser()
    if not task_dispenser.get_id() == Contest.get_id():
        return None

    contest_data = task_dispenser.get_contest_data()
    if contest_data['enabled']:
        start = datetime.fromisoformat(contest_data['start']).astimezone()
        end = datetime.fromisoformat(contest_data['end']).astimezone()
        blackout = end - timedelta(hours=contest_data['blackout'])
        return render_template("contests/course_menu.html", course=course, start=start, end=end, blackout=blackout)
    else:
        return None


class ContestScoreboard(INGIniousAuthPage):
    """ Displays the scoreboard of the contest """

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        course = self.course_factory.get_course(courseid)
        task_dispenser = course.get_task_dispenser()
        if not task_dispenser.get_id() == Contest.get_id():
            raise NotFound()
        contest_data = task_dispenser.get_contest_data()
        if not contest_data['enabled']:
            raise NotFound()
        start = datetime.fromisoformat(contest_data['start']).astimezone()
        end = datetime.fromisoformat(contest_data['end']).astimezone()
        blackout = end - timedelta(hours=contest_data['blackout'])

        users = self.user_manager.get_course_registered_users(course)
        tasks = list(course.get_tasks().keys())

        db_results = self.database.submissions.find({
            "username": {"$in": users},
            "courseid": courseid,
            "submitted_on": {"$gte": start, "$lt": blackout},
            "status": "done"},
            {"username": True, "_id": False, "taskid": True, "result": True, "submitted_on": True}).sort([("submitted_on", pymongo.ASCENDING)])

        task_status = {taskid: {"status": "NA", "tries": 0} for taskid in tasks}
        results = {username: {"name": self.user_manager.get_user_realname(username), "tasks": copy.deepcopy(task_status)} for username in users}
        activity = []

        # Compute stats for each submission
        task_succeeded = {taskid: False for taskid in tasks}
        for submission in db_results:
            for username in submission["username"]:
                if submission['taskid'] not in tasks:
                    continue
                if username not in users:
                    continue
                status = results[username]["tasks"][submission['taskid']]
                if status["status"] == "AC" or status["status"] == "ACF":
                    continue
                else:
                    if submission['result'] == "success":
                        if not task_succeeded[submission['taskid']]:
                            status["status"] = "ACF"
                            task_succeeded[submission['taskid']] = True
                        else:
                            status["status"] = "AC"
                        status["tries"] += 1
                        status["time"] = submission['submitted_on']
                        status["score"] = (submission['submitted_on']
                                           + timedelta(minutes=contest_data["penalty"]*(status["tries"] - 1))
                                           - start).total_seconds() / 60
                    elif submission['result'] == "failed" or submission['result'] == "killed":
                        status["status"] = "WA"
                        status["tries"] += 1
                    elif submission['result'] == "timeout":
                        status["status"] = "TLE"
                        status["tries"] += 1
                    else:  # other internal error
                        continue
                    activity.append({"user": results[username]["name"],
                                     "when": submission['submitted_on'],
                                     "result": (status["status"] == 'AC' or status["status"] == 'ACF'),
                                     "taskid": submission['taskid']})
        activity.reverse()
        # Compute current score
        for user in results:
            score = [0, 0]
            for data in list(results[user]["tasks"].values()):
                if "score" in data:
                    score[0] += 1
                    score[1] += data["score"]
            results[user]["score"] = tuple(score)

        # Sort everybody
        results = OrderedDict(sorted(list(results.items()), key=lambda t: (-t[1]["score"][0], t[1]["score"][1])))

        # Compute ranking
        old = None
        current_rank = 0
        for cid, user in enumerate(results.keys()):
            if results[user]["score"] != old:
                old = results[user]["score"]
                current_rank = cid + 1
                results[user]["rank"] = current_rank
                results[user]["displayed_rank"] = str(current_rank)
            else:
                results[user]["rank"] = current_rank
                results[user]["displayed_rank"] = ""

        return render_template("contests/scoreboard.html",
                                           course=course, start=start, end=end, blackout=blackout, tasks=tasks,
                                           results=results, activity=activity)


class ContestAdmin(INGIniousAdminPage):
    """ Contest settings for a course """

    def save_contest_data(self, course, contest_data):
        """ Saves updated contest data for the course """
        course_content = course.get_descriptor()
        course_content["dispenser_data"]["contest_settings"] = contest_data

        Course(course.get_id(), course_content, course.get_fs()).save()

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request: simply display the form """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)
        task_dispenser = course.get_task_dispenser()
        if not task_dispenser.get_id() == Contest.get_id():
            raise NotFound()
        contest_data = task_dispenser.get_contest_data()
        return render_template("contests/admin.html", course=course, data=contest_data, errors=None, saved=False)

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request: update the settings """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)
        task_dispenser = course.get_task_dispenser()
        if not task_dispenser.get_id() == Contest.get_id():
            raise NotFound()
        contest_data = task_dispenser.get_contest_data()

        new_data = request.form
        errors = []
        try:
            contest_data['enabled'] = new_data.get('enabled', '0') == '1'
            contest_data['start'] = new_data["start"]
            contest_data['end'] = new_data["end"]

            try:
                start = datetime.fromisoformat(contest_data['start'])
            except:
                errors.append('Invalid start date')

            try:
                end = datetime.fromisoformat(contest_data['end'])
            except:
                errors.append('Invalid end date')

            if len(errors) == 0:
                if start >= end:
                    errors.append('Start date should be before end date')

            try:
                contest_data['blackout'] = int(new_data["blackout"])
                if contest_data['blackout'] < 0:
                    errors.append('Invalid number of hours for the blackout: should be greater than 0')
            except:
                errors.append('Invalid number of hours for the blackout')

            try:
                contest_data['penalty'] = int(new_data["penalty"])
                if contest_data['penalty'] < 0:
                    errors.append('Invalid number of minutes for the penalty: should be greater than 0')
            except:
                errors.append('Invalid number of minutes for the penalty')
        except:
            errors.append('User returned an invalid form')

        if len(errors) == 0:
            self.save_contest_data(course, contest_data)
            return render_template("contests/admin.html", course=course, data=contest_data, errors=None, saved=True)
        else:
            return render_template("contests/admin.html", course=course, data=contest_data, errors=errors, saved=False)


def init(plugin_manager, course_factory, client, config):  # pylint: disable=unused-argument
    """
        Init the contest plugin.
        Available configuration:
        ::

            {
                "plugin_module": "inginious.frontend.plugins.contests"
            }
    """

    plugin_manager.add_page('/contest/<courseid>', ContestScoreboard.as_view('contestscoreboard'))
    plugin_manager.add_page('/admin/<courseid>/contest', ContestAdmin.as_view('contestadmin'))
    plugin_manager.add_hook('course_admin_menu', add_admin_menu)
    plugin_manager.add_hook('css', lambda: '/static/plugins/contests/scoreboard.css')
    plugin_manager.add_hook('javascript_header', lambda : '/static/plugins/contests/jquery.countdown.min.js')
    plugin_manager.add_hook('javascript_header', lambda : '/static/plugins/contests/contests.js')
    plugin_manager.add_hook('course_menu', course_menu)
    plugin_manager.add_template_prefix("contests", PATH_TO_PLUGIN)
    course_factory.add_task_dispenser(Contest)

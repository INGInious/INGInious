# -*- coding: utf-8 -*-
#
# Copyright (c) 2014 Université Catholique de Louvain.
#
# This file is part of INGInious.
#
# INGInious is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# INGInious is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with INGInious.  If not, see <http://www.gnu.org/licenses/>.
""" Contains the UserData class that helps to manage saved statistical data of a user """
from inginious.frontend.base import get_database, add_to_template_globals


class UserData(object):

    """ Allow to get and to modify _data stored in database for a particular user.
        These data are only used as statistics.
            userdata
            {
                "_id":             "gderval",
                "realname":        "Guillaume Derval",
                "email":           "guillaume.derval@student.uclouvain.be"
            }

            user_task
            {
                "username":        "gderval",
                "courseid":        "idCourse1",
                "taskid":          "idTask1",
                "tried":           0,
                "succeeded":       False,
                "grade":        0.0
            }
    """

    def __init__(self, username):
        self.username = username
        self._data = None
        self._update_cache()

    def _update_cache(self):
        """ Update internal cache of this object """
        self._data = get_database().users.find_and_modify({"_id": self.username}, {
            "$setOnInsert": {"realname": "", "email": ""}}, upsert=True, new=True)

    def update_basic_informations(self, realname, email):
        """ Update basic informations in the database """
        get_database().users.update(
            {"_id": self.username}, {"$set": {"realname": realname, "email": email}})
        self._update_cache()

    def get_data(self):
        """ Returns data of this user """
        return self._data

    def get_course_data(self, courseid):
        """ Returns data of this user for a specific course."""
        return self.get_course_data_for_users(
            courseid, [
                self.username]).get(
            self.username, None)

    @classmethod
    def get_course_data_for_users(cls, courseid, users=None):
        """
            Returns data of users for a specific course. users is a list of username. If users is none, data from all users will be returned.

            The returned value is a dict:

            {"username": {"task_tried": 0, "total_tries": 0, "task_succeeded": 0, "task_grades":{"task_1": 100.0, "task_2": 0.0, ...}}}

            Please note that only the task already seen at least one time will be present in the dict task_grades.
        """
        from inginious.frontend.custom.courses import FrontendCourse
        course = FrontendCourse(courseid)
        match = {"courseid": courseid}
        if users is not None:
            match["username"] = {"$in": users}

        tasks = course.get_tasks()
        taskids = tasks.keys()
        match["taskid"] = {"$in": taskids}

        data = get_database().user_tasks.aggregate(
            [
                {"$match": match},
                {"$group": {
                    "_id": "$username",
                    "task_tried": {"$sum": {"$cond": [{"$ne": ["$tried", 0]}, 1, 0]}},
                    "total_tries":{"$sum": "$tried"},
                    "task_succeeded": {"$addToSet": {"$cond": ["$succeeded", "$taskid", False]}},
                    "task_grades": {"$addToSet": {"taskid": "$taskid", "grade": "$grade"}}
                }}
            ])
        if data.get('ok', False):
            return_data = {}
            for result in data["result"]:
                username = result["_id"]
                user_tasks = set([taskid for taskid, task in tasks.iteritems() if task.is_visible_by_user(username)])
                result["total_tasks"] = len(user_tasks)
                result["task_succeeded"] = len(set(result["task_succeeded"]).intersection(user_tasks))
                result["task_grades"] = {dg["taskid"]: dg["grade"] for dg in result["task_grades"] if dg["taskid"] in user_tasks}
                del result["_id"]
                return_data[username] = result
            return return_data
        else:
            return {}

    def get_task_data(self, courseid, taskid):
        """ Returns data of this user for a specific task """
        return get_database().user_tasks.find_one(
            {"username": self.username, "courseid": courseid, "taskid": taskid})

    def view_task(self, courseid, taskid):
        """ Set in the database that the user has viewed this task """
        # Insert a new entry if no one exists
        get_database().user_tasks.update({"username": self.username,
                                          "courseid": courseid,
                                          "taskid": taskid},
                                         {"$setOnInsert": {"username": self.username,
                                                           "courseid": courseid,
                                                           "taskid": taskid,
                                                           "tried": 0,
                                                           "succeeded": False,
                                                           "grade": 0.0}},
                                         upsert=True)

    def update_stats(self, submission, job):
        """ Update stats with a new submission """
        # Insert a new entry if no one exists
        get_database().user_tasks.find_and_modify(
            {
                "username": self.username,
                "courseid": submission["courseid"],
                "taskid": submission["taskid"]},
            {
                "$setOnInsert": {
                    "username": self.username,
                    "courseid": submission["courseid"],
                    "taskid": submission["taskid"],
                    "tried": 0,
                    "succeeded": False,
                    "grade": 0.0}},
            upsert=True)

        # Update inc counter
        get_database().user_tasks.update({"username": self.username, "courseid": submission[
            "courseid"], "taskid": submission["taskid"]}, {"$inc": {"tried": 1}})

        # Set to succeeded if not succeeded yet
        if job["result"] == "success":
            get_database().user_tasks.find_and_modify({"username": self.username,
                                                       "courseid": submission["courseid"],
                                                       "taskid": submission["taskid"],
                                                       "succeeded": False},
                                                      {"$set": {"succeeded": True}})

        # Update the grade if needed
        get_database().user_tasks.find_and_modify({"username": self.username,
                                                   "courseid": submission["courseid"],
                                                   "taskid": submission["taskid"],
                                                   "grade": {"$lt": job["grade"]}},
                                                  {"$set": {"grade": job["grade"]}})

        self._update_cache()

add_to_template_globals("UserData", UserData)

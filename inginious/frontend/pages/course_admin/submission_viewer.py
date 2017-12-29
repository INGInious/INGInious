# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import pymongo
import web
import re
import itertools
from bson.objectid import ObjectId
from collections import OrderedDict

from inginious.frontend.pages.course_admin.utils import make_csv, INGIniousAdminPage
from inginious.frontend.pages.course_admin.statistics import compute_statistics
from inginious.common.base import id_checker

class CourseSubmissionViewerTaskPage(INGIniousAdminPage):
    """ List information about a task done by a student """

    def GET_AUTH(self, courseid, filter=""):  # pylint: disable=arguments-differ
        """ GET request """
        course, __ = self.get_course_and_check_rights(courseid)
        
        self._allowed_sort = ["submitted_on", "username", "grade", "taskid"]
        self._allowed_sort_name = [_("Submitted on"), _("User"), _("Grade"), _("Task id")]
        
        if course.is_lti():
            raise web.notfound()

        return self.page(course)

    def submission_url_generator(self, submissionid):
        """ Generates a submission url """
        return "?submission=" + submissionid

    def page(self, course):
        """ Get all data and display the page """

        input = web.input(
            username=[],
            task=[],
            classroom=[],
            org_tags=[],
            grade_min='',
            grade_max='',
            sort_by="submitted_on",
            order='0',  #"0" for pymongo.DESCENDING, anything else for pymongo.ASCENDING
            limit='',
            filter_tags=[],
            filter_tags_presence=[],
            )
        
        print(input)
        self.sanitise_input(input)

        #Build lists of wanted users based on classrooms and specific users
        list_classroom_ObjectId = [ObjectId(o) for o in input.classroom]
        classroom = list(self.database.aggregations.find({"_id": {"$in" : list_classroom_ObjectId}}))
        more_username = [s["students"] for s in classroom] #Extract usernames of students
        more_username = [y for x in more_username for y in x] #Flatten lists
        
        #Get tasks based on organisational tags
        more_tasks = []
        for org_tag in input.org_tags:
            if org_tag in course.get_organisational_tags_to_task():
                more_tasks += course.get_organisational_tags_to_task()[org_tag]

        #Base query
        query_base = {
                "username": {"$in": input.username + more_username},
                "courseid": course.get_id(),
                "taskid": {"$in": input.task + more_tasks}
                }

        #Additional query field
        query_advanced = {}
        if (input.grade_min != '' and input.grade_max == ''):
            query_advanced["grade"] = {"$gte" : float(input.grade_min)}
        elif (input.grade_min == '' and input.grade_max != ''):
            query_advanced["grade"] = {"$lte" : float(input.grade_max)}
        elif (input.grade_min != '' and input.grade_max != ''):
            query_advanced["grade"] = {"$gte" : float(input.grade_min), "$lte" : float(input.grade_max)}
        
        #Query with tags
        if len(input.filter_tags) == len(input.filter_tags_presence):
            for i in range(0, len(input.filter_tags)):
                if id_checker(input.filter_tags[i]):
                    state = (input.filter_tags_presence[i] == "True" or input.filter_tags_presence[i] == "true")
                    query_advanced["tests." + input.filter_tags[i]] = {"$in": [None, False]} if not state else True
            
        #Mongo operations
        data = list(self.database.submissions.find({**query_base, **query_advanced}).sort([(input.sort_by, 
            pymongo.DESCENDING if input.order == "0" else pymongo.ASCENDING)]))
        data = [dict(list(f.items()) + [("url", self.submission_url_generator(str(f["_id"])))]) for f in data]

        # Get best submissions from database
        user_tasks = list(self.database.user_tasks.find(query_base, {"submissionid": 1, "_id": 0}))
        best_submissions_list = [u["submissionid"] for u in user_tasks] # list containing ids of best submissions
        for d in data:
            d["best"] = d["_id"] in best_submissions_list # mark best submissions

        #Keep best submissions
        if("eval" in input):
            data = [d for d in data if d["best"]]
            
        users = self.get_users(course) # All users of the course
        tasks = course.get_tasks();  # All tasks of the course
        classrooms = self.user_manager.get_course_aggregations(course) # All classrooms of the course
        
        statistics = compute_statistics(tasks, data, True if "ponderate" in input else False)

        if input.limit != '':
            data = data[:int(input.limit)]
            
        if "csv" in web.input():
            return make_csv(data)
            
        if "download" in web.input():
            #self._logger.info("Downloading %d submissions from course %s", len(data), course.get_id())
            web.header('Content-Type', 'application/x-gzip', unique=True)
            web.header('Content-Disposition', 'attachment; filename="submissions.tgz"', unique=True)

            # Tweak if not using classrooms : classroom['students'] may content ungrouped users
            aggregations = dict([(username,
                                  aggregation if course.use_classrooms() or (
                                  username in aggregation['groups'][0]["students"]) else None
                                  ) for aggregation in classroom for username in aggregation["students"]])

            return self.submission_manager.get_submission_archive(data, list(reversed(web.input().download.split('/'))), aggregations)

        return self.template_helper.get_renderer().course_admin.submission_viewer(course, tasks, users, classrooms, data, statistics, input, self._allowed_sort, self._allowed_sort_name, self.valid_formats)

    def get_users(self, course):
        """ """
        users = sorted(list(self.user_manager.get_users_info(self.user_manager.get_course_registered_users(course, False)).items()),
            key=lambda k: k[1][0] if k[1] is not None else "")

        users = OrderedDict(sorted(list(self.user_manager.get_users_info(course.get_staff()).items()),
            key=lambda k: k[1][0] if k[1] is not None else "") + users)

        return users

        
    def sanitise_input(self, input):
        for item in itertools.chain(input.username, input.task, input.classroom):
            if not id_checker(item):
                raise web.notfound() 
        
    def valid_formats(self):
        dict = {
            "taskid/username": _("taskid/username"),
            "taskid/aggregation": _("taskid/aggregation"),
            "username/taskid": _("username/taskid"),
            "aggregation/taskid": _("aggregation/taskid")
        }
        return list(dict.keys())
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from datetime import datetime, timezone
import glob
import logging
import os
import random
import zipfile

import bson.json_util
import flask
from flask import redirect, Response
from werkzeug.exceptions import NotFound


from inginious.frontend.pages.course_admin.utils import INGIniousAdminPage
from inginious.frontend.user_manager import UserManager
from inginious.common.exceptions import CourseNotFoundException, CourseNotArchivable


class CourseDangerZonePage(INGIniousAdminPage):
    """ Course administration page: list of audiences """
    _logger = logging.getLogger("inginious.webapp.danger_zone")

    def wipe_course(self, courseid):
        submissions = self.database.aware_submissions.find({"courseid": courseid})
        for submission in submissions:
            for key in ["input", "archive"]:
                gridfs = self.submission_manager.get_gridfs()
                if key in submission and type(submission[key]) == bson.objectid.ObjectId and gridfs.exists(submission[key]):
                    gridfs.delete(submission[key])

        self.database.courses.update_one({"_id": courseid}, {"$set": {"students": []}})
        self.database.audiences.delete_many({"courseid": courseid})
        self.database.groups.delete_many({"courseid": courseid})
        self.database.user_tasks.delete_many({"courseid": courseid})
        self.database.aware_submissions.delete_many({"courseid": courseid})

        self._logger.info("Course %s wiped.", courseid)

    def dump_course(self, courseid):
        """
            Creates a new course (Archive course), gives it a course id resulting of the concatenation of the original id
            and the archiving date. This archive course is marked as archived and given an archive date in its YAML descriptor.
            The original course keeps their course id and all related submissions, user_tasks, audiences, courses and
            groups are updated to point to the archive course.
        """

        course = self.course_factory.get_course(courseid)
        course_fs = course.get_fs()
        if course.is_archive():
            raise CourseNotArchivable()
        if not course_fs.exists():
            raise CourseNotFoundException()

        # Create archive course by duplicating it's folder in the FS
        archive_course_id = courseid + "_archive_" + datetime.now(tz=timezone.utc).strftime("%Y_%m_%d.%H_%M_%S")
        self.course_factory.get_fs().copy_to(course_fs.prefix, archive_course_id)

        # Create archive course entry in DB
        old_course_students = self.database.courses.find_one({"_id": courseid})
        self.database.courses.insert_one({"_id": archive_course_id,
                                          "archived_from": courseid,
                                          "archive_date": datetime.now(tz=timezone.utc),
                                          "students": old_course_students.get("students", []) if old_course_students else []})

        # Update course id in DB
        self.database.aware_submissions.update_many({"courseid": courseid}, {"$set": {"courseid": archive_course_id}})
        self.database.user_tasks.update_many({"courseid": courseid}, {"$set": {"courseid": archive_course_id}})
        self.database.groups.update_many({"courseid": courseid}, {"$set": {"courseid": archive_course_id}})
        self.database.audiences.update_many({"courseid": courseid}, {"$set": {"courseid": archive_course_id}})

        self._logger.info("Course %s backed up.", courseid)


    def delete_course(self, courseid):
        """ Erase all course data """
        # Wipes the course (delete database)
        self.wipe_course(courseid)

        # Deletes the course from the factory (entire folder)
        self.course_factory.delete_course(courseid)

        self._logger.info("Course %s files erased.", courseid)

    def remove_old_archive_links(self, course):
        """ Remove all archive links in DB for a course that has been deleted manually """
        archive_list_id = [archive["_id"] for archive in self.database.courses.find({"archived_from": course.get_id()})] \
            if not course.is_archive() else []
        courses_in_fs = self.course_factory.get_all_courses()
        for archive_id in archive_list_id:
            if archive_id not in courses_in_fs :
                self.database.courses.delete_many({"_id": archive_id})
                self._logger.info("Archive link for course %s removed from database.", archive_id)


    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)

        return self.page(course)

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)

        msg = ""
        error = False

        data = flask.request.form
        if not data.get("token", "") == self.user_manager.session_token():
            msg = _("Operation aborted due to invalid token.")
            error = True
        elif "wipeall" in data:
            if not data.get("courseid", "") == courseid:
                msg = _("Wrong course id.")
                error = True
            else:
                try:
                    self.dump_course(courseid)
                    msg = _("All course data have been deleted.")
                except Exception as ex:
                    msg = _("An error occurred while dumping course from database: {}").format(repr(ex))
                    error = True
        elif "deleteall" in data:
            if not data.get("courseid", "") == courseid:
                msg = _("Wrong course id.")
                error = True
            else:
                try:
                    self.delete_course(courseid)
                    return redirect(self.app.get_path("index"))
                except Exception as ex:
                    msg = _("An error occurred while deleting the course data: {}").format(repr(ex))
                    error = True

        return self.page(course, msg, error)


    def page(self, course, msg="", error=False):
        """ Get all data and display the page """
        thehash = UserManager.hash_password_sha512(str(random.getrandbits(256)))
        self.user_manager.set_session_token(thehash)

        self.remove_old_archive_links(course)

        archive_list_id = [archive["_id"] for archive in self.database.courses.find({"archived_from": course.get_id()})] \
            if not course.is_archive() else []
        archives = [self.course_factory.get_course(archive_id) for archive_id in archive_list_id]

        original_course_id = self.database.courses.find_one({"_id": course.get_id()}) if course.is_archive() else None
        original_course = self.course_factory.get_course(original_course_id["archived_from"]) if  original_course_id else None

        return self.template_helper.render("course_admin/danger_zone.html", course=course, thehash=thehash,
                                           archives=archives, original_course=original_course, msg=msg, error=error)

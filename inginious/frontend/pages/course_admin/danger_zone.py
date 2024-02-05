# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import datetime
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


class CourseDangerZonePage(INGIniousAdminPage):
    """ Course administration page: list of audiences """
    _logger = logging.getLogger("inginious.webapp.danger_zone")

    def wipe_course(self, courseid):
        submissions = self.database.submissions.find({"courseid": courseid})
        for submission in submissions:
            for key in ["input", "archive"]:
                gridfs = self.submission_manager.get_gridfs()
                if key in submission and type(submission[key]) == bson.objectid.ObjectId and gridfs.exists(submission[key]):
                    gridfs.delete(submission[key])

        self.database.courses.update_one({"_id": courseid}, {"$set": {"students": []}})
        self.database.audiences.delete_many({"courseid": courseid})
        self.database.groups.delete_many({"courseid": courseid})
        self.database.user_tasks.delete_many({"courseid": courseid})
        self.database.submissions.delete_many({"courseid": courseid})

        self._logger.info("Course %s wiped.", courseid)

    def dump_course(self, courseid):
        """ Create a zip file containing all information about a given course in database and then remove it from db"""
        filepath = os.path.join(self.backup_dir, courseid, datetime.datetime.now().strftime("%Y%m%d.%H%M%S") + ".zip")

        if not os.path.exists(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath))

        with zipfile.ZipFile(filepath, "w", allowZip64=True) as zipf:
            course_obj = self.database.courses.find_one({"_id": courseid})
            students = course_obj.get("students", []) if course_obj else []
            zipf.writestr("students.json", bson.json_util.dumps(students), zipfile.ZIP_DEFLATED)

            audiences = self.database.audiences.find({"courseid": courseid})
            zipf.writestr("audiences.json", bson.json_util.dumps(audiences), zipfile.ZIP_DEFLATED)

            groups = self.database.groups.find({"courseid": courseid})
            zipf.writestr("groups.json", bson.json_util.dumps(groups), zipfile.ZIP_DEFLATED)

            user_tasks = self.database.user_tasks.find({"courseid": courseid})
            zipf.writestr("user_tasks.json", bson.json_util.dumps(user_tasks), zipfile.ZIP_DEFLATED)

            # Fetching input data  while looping on submissions can trigger a mongo cursor timeout
            submissions = self.database.submissions.find({"courseid": courseid}, no_cursor_timeout=True)
            erroneous_subs = set()

            for submission in submissions:
                for key in ["input", "archive"]:
                    gridfs = self.submission_manager.get_gridfs()
                    if key in submission and type(submission[key]) == bson.objectid.ObjectId:
                        if gridfs.exists(submission[key]):
                            infile = gridfs.get(submission[key])
                            zipf.writestr(key + "/" + str(submission[key]) + ".data", infile.read(), zipfile.ZIP_DEFLATED)
                        else:
                            self._logger.error("Missing {} in grifs, skipping submission {}".format(str(submission[key]), str(submission["_id"])))
                            erroneous_subs.add(submission["_id"])

            submissions.rewind()
            submissions = [submission for submission in submissions if submission["_id"] not in erroneous_subs]
            zipf.writestr("submissions.json", bson.json_util.dumps(submissions), zipfile.ZIP_DEFLATED)

        self._logger.info("Course %s dumped to backup directory.", courseid)
        self.wipe_course(courseid)

    def restore_course(self, courseid, backup):
        """ Restores a course of given courseid to a date specified in backup (format : YYYYMMDD.HHMMSS) """
        self.wipe_course(courseid)

        filepath = os.path.join(self.backup_dir, courseid, backup + ".zip")
        with zipfile.ZipFile(filepath, "r") as zipf:

            students = bson.json_util.loads(zipf.read("students.json").decode("utf-8"))
            if len(students) > 0:
                self.database.courses.update_one({"_id": courseid}, {"$set": {"students": students}}, upsert=True)

            audiences = bson.json_util.loads(zipf.read("audiences.json").decode("utf-8"))
            if len(audiences) > 0:
                self.database.audiences.insert_many(audiences)

            groups = bson.json_util.loads(zipf.read("groups.json").decode("utf-8"))
            if len(groups) > 0:
                self.database.groups.insert_many(groups)

            user_tasks = bson.json_util.loads(zipf.read("user_tasks.json").decode("utf-8"))
            if len(user_tasks) > 0:
                self.database.user_tasks.insert_many(user_tasks)

            submissions = bson.json_util.loads(zipf.read("submissions.json").decode("utf-8"))
            for submission in submissions:
                for key in ["input", "archive"]:
                    if key in submission and type(submission[key]) == bson.objectid.ObjectId:
                        submission[key] = self.submission_manager.get_gridfs().put(zipf.read(key + "/" + str(submission[key]) + ".data"))

            if len(submissions) > 0:
                self.database.submissions.insert_many(submissions)

        self._logger.info("Course %s restored from backup directory.", courseid)

    def delete_course(self, courseid):
        """ Erase all course data """
        # Wipes the course (delete database)
        self.wipe_course(courseid)

        # Deletes the course from the factory (entire folder)
        self.course_factory.delete_course(courseid)

        # Removes backup
        filepath = os.path.join(self.backup_dir, courseid)
        if os.path.exists(os.path.dirname(filepath)):
            for backup in glob.glob(os.path.join(filepath, '*.zip')):
                os.remove(backup)

        self._logger.info("Course %s files erased.", courseid)

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)

        data = flask.request.args

        if "download" in data:
            filepath = os.path.join(self.backup_dir, courseid, data["download"] + '.zip')

            if not os.path.exists(os.path.dirname(filepath)):
                raise NotFound(description=_("This file doesn't exist."))

            response = Response(response=open(filepath, 'rb'), content_type='application/zip')
            response.headers['Content-Disposition'] = 'attachment; filename="{}.zip"'.format(data["download"])
            return response

        else:
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
        elif "restore" in data:
            if "backupdate" not in data:
                msg = "No backup date selected."
                error = True
            else:
                try:
                    dt = datetime.datetime.strptime(data["backupdate"], "%Y%m%d.%H%M%S")
                    self.restore_course(courseid, data["backupdate"])
                    msg = _("Course restored to date : {}.").format(dt.strftime("%Y-%m-%d %H:%M:%S"))
                except Exception as ex:
                    msg = _("An error occurred while restoring backup: {}").format(repr(ex))
                    error = True
        elif "deleteall" in data:
            if not data.get("courseid", "") == courseid:
                msg = _("Wrong course id.")
                error = True
            else:
                try:
                    self.delete_course(courseid)
                    return redirect(self.app.get_homepath() + '/index')
                except Exception as ex:
                    msg = _("An error occurred while deleting the course data: {}").format(repr(ex))
                    error = True

        return self.page(course, msg, error)

    def get_backup_list(self, course):
        backups = []

        filepath = os.path.join(self.backup_dir, course.get_id())
        if os.path.exists(os.path.dirname(filepath)):
            for backup in glob.glob(os.path.join(filepath, '*.zip')):
                try:
                    basename = os.path.basename(backup)[0:-4]
                    dt = datetime.datetime.strptime(basename, "%Y%m%d.%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
                    backups.append({"file": basename, "date": dt})
                except:  # Wrong format
                    pass

        return backups

    def page(self, course, msg="", error=False):
        """ Get all data and display the page """
        thehash = UserManager.hash_password_sha512(str(random.getrandbits(256)))
        self.user_manager.set_session_token(thehash)

        backups = self.get_backup_list(course)

        return self.template_helper.render("course_admin/danger_zone.html", course=course, thehash=thehash,
                                           backups=backups, msg=msg, error=error)

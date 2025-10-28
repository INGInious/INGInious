# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from datetime import datetime, timezone
import logging
import random

from flask import request, redirect, Response, render_template
from werkzeug.exceptions import NotFound

from inginious.frontend.models.submission import Submission
from inginious.frontend.models.audience import Audience
from inginious.frontend.courses import Course
from inginious.frontend.pages.course_admin.utils import INGIniousAdminPage
from inginious.frontend.user_manager import UserManager
from inginious.common.exceptions import CourseNotFoundException, CourseNotArchivable
from inginious.frontend.models.user_task import UserTask
from inginious.frontend.models.group import Group
from inginious.frontend.models.course_class import CourseClass


class CourseDangerZonePage(INGIniousAdminPage):
    """ Course administration page: list of audiences """
    _logger = logging.getLogger("inginious.webapp.danger_zone")

    def wipe_course(self, courseid):
        for submission in Submission.objects(courseid=courseid):
            submission.input.delete()
            submission.archive.delete()

        CourseClass.objects(id=courseid).update(students=[])
        Audience.objects(courseid=courseid).delete()
        Group.objects(courseid=courseid).delete()
        UserTask.objects(courseid=courseid).delete()
        Submission.objects(courseid=courseid).delete()

        self._logger.info("Course %s wiped.", courseid)

    def dump_course(self, course):
        """
            Creates a new course (Archive course), gives it a course id resulting of the concatenation of the original id
            and the archiving date. This archive course is marked as archived and given an archive date in its YAML descriptor.
            The original course keeps their course id and all related submissions, user_tasks, audiences, courses and
            groups are updated to point to the archive course.
        """

        courseid = course.get_id()
        course_fs = course.get_fs()
        if course.is_archive():
            raise CourseNotArchivable()

        # Copy archive course
        archive_course_id = courseid + "_archive_" + datetime.now(tz=timezone.utc).strftime("%Y_%m_%d_%H_%M_%S")
        archive_course_fs = Course(archive_course_id, {"name": archive_course_id}).get_fs()
        archive_course_fs.copy_to(course_fs.prefix)

        # Update archive YAML file
        archive_course_content = course.get_descriptor()
        archive_course_content["archived"] = True
        archive_course_content["archive_date"] = datetime.now(tz=timezone.utc).isoformat()

        # Save archived course
        Course(archive_course_id, archive_course_content).save()

        # Update course id in DB
        Submission.objects(courseid=courseid).update(set__courseid=archive_course_id)
        UserTask.objects(courseid=courseid).update(set__courseid=archive_course_id)
        Group.objects(courseid=courseid).update(set__courseid=archive_course_id)
        Audience.objects(courseid=courseid).update(set__courseid=archive_course_id)
        old_course_class = CourseClass.objects(id=courseid).modify(remove=True)

        if old_course_class:
            CourseClass(id=archive_course_id, students=old_course_class.students).save()

        self._logger.info("Course %s archived as %s.", courseid, archive_course_id)
        return courseid, archive_course_id

    def delete_course(self, course):
        """ Erase all course data """
        # Wipes the course (delete database)
        self.wipe_course(course.get_id())

        # Deletes the course from the factory (entire folder)
        course.delete()

        self._logger.info("Course %s files erased.", course.get_id())

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)
        return self.page(course)

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course, __ = self.get_course_and_check_rights(courseid, allow_all_staff=False)

        msg = ""
        error = False

        data = request.form
        if not data.get("token", "") == self.user_manager.session_token():
            msg = _("Operation aborted due to invalid token.")
            error = True
        elif "wipeall" in data:
            if not data.get("courseid", "") == courseid:
                msg = _("Wrong course id.")
                error = True
            else:
                try:
                    courseid, archive_course_id = self.dump_course(course)
                    msg = _("Course archived as : ") + archive_course_id
                except Exception as ex:
                    msg = _("An error occurred while dumping course from database: {}").format(repr(ex))
                    error = True
        elif "deleteall" in data:
            if not data.get("courseid", "") == courseid:
                msg = _("Wrong course id.")
                error = True
            else:
                try:
                    self.delete_course(course)
                    return redirect(self.app.get_path("index"))
                except Exception as ex:
                    msg = _("An error occurred while deleting the course data: {}").format(repr(ex))
                    error = True

        return self.page(course, msg, error)


    def page(self, course, msg="", error=False):
        """ Get all data and display the page """
        thehash = UserManager.hash_password_sha512(str(random.getrandbits(256)))
        self.user_manager.set_session_token(thehash)


        return render_template("course_admin/danger_zone.html", course=course, thehash=thehash,
                               msg=msg, error=error)

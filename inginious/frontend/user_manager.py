# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Manages users data """
import logging

from flask import session, request
from typing import Dict, Optional
from functools import reduce
from natsort import natsorted
from mongoengine import Q

from inginious.frontend.controllers import auth
from inginious.frontend.models import User, Group, Audience, CourseClass, UserTask, Submission

class UserManager:
    def __init__(self, superadmins):
        """
        :type superadmins: list(str)
        :param superadmins: list of the super-administrators' usernames
        """
        self._superadmins = superadmins
        self._logger = logging.getLogger("inginious.webapp.users")

    ##############################################
    #              User information              #
    ##############################################

    def get_users_info(self, usernames) -> Dict[str, Optional[User]]:
        """
        :param usernames: a list of usernames
        :return: a dict, in the form {username: val}, where val is either None if the user cannot be found, or a User.
        If the list of usernames is empty, return an empty dict.
        """
        retval = {username: None for username in usernames}
        for info in User.objects(username__in=usernames):
            retval[info.username] = info
        return retval

    def get_user_info(self, username) -> Optional[User]:
        """
        :param username:
        :return: a User object if the user can be found, None else
        """
        return User.objects(username=username).first()

    def get_user_realname(self, username):
        """
        :param username:
        :return: the real name of the user if it can be found, None else
        """
        info = self.get_user_info(username)
        if info is not None:
            return info.realname
        return None

    def get_user_email(self, username):
        """
        :param username:
        :return: the email of the user if it can be found, None else
        """
        info = self.get_user_info(username)
        if info is not None:
            return info.email
        return None

    def delete_user(self, username, confirmation_email=None):
        """
        Delete a user based on username
        :param username: the username of the user
        :param confirmation_email: An email to confirm suppression. May be None
        :return a boolean if a user was deleted
        """
        query = {"username": username, "email": confirmation_email} \
            if confirmation_email is not None else {"username": username}
        result = User.objects(**query).modify(remove=True)
        if not result:
            return False
        else:
            Submission.objects(username=username).delete()
            UserTask.objects(username=username).delete()
            user_courses = CourseClass.objects(students=username)
            for elem in user_courses: self.course_unregister_user(elem.id, username)
        return True

    def create_user(self, values):
        """
        Create a new user
        :param values: Dictionary of fields
        :return: An error message if something went wrong else None
        """
        query = Q(username=values["username"]) | Q(email=values["email"])
        if User.objects(query).first() is not None:
            return _("User could not be created.")

        User(username=values["username"], realname=values["realname"], email=values["email"],
             password=auth.hash_password(values["password"])).save()

        return None

    ##############################################
    #      User task/course info management      #
    ##############################################

    def get_course_cache(self, username, course):
        """
        :param username: The username
        :param course: A Course object
        :return: a dict containing info about the course, in the form:

            ::

                {"task_tried": 0, "total_tries": 0, "task_succeeded": 0, "grade": 0}
        """
        return self.get_course_caches([username], course)[username]

    def get_course_caches(self, usernames : list[str], course):
        """
        :param usernames: List of username for which we want info.
        :param course: A Course object
        :return:
            Returns data of the specified users for a specific course. users is a list of username.

            The returned value is a dict:

            ::

                {"username": {"task_tried": 0, "total_tries": 0, "task_succeeded": 0, "grade": 0}}
        """

        user_tasks = UserTask.objects(
            courseid=course.get_id(),
            username__in=usernames,
            taskid__in=course.get_readable_tasks()
        )

        retval = {
            username: {"task_tried": 0, "total_tries": 0, "task_succeeded": 0, "grade": 0}
            for username in usernames
        }

        data = user_tasks.aggregate([{
            "$group":
                {
                    "_id": "$username",
                    "task_tried": {"$sum": {"$cond": [{"$ne": ["$tried", 0]}, 1, 0]}},
                    "total_tries": {"$sum": "$tried"},
                    "task_succeeded": {"$sum": {"$cond": ["$succeeded", 1, 0]}},
                }
        }])

        users_grade = course.get_task_dispenser().get_course_grades(user_tasks, usernames)

        for result in data:
            username = result["_id"]
            result["grade"] = users_grade[username]
            retval[username] = result

        return retval

    def get_task_cache(self, username, courseid, taskid) -> UserTask:
        """
        :param username: username for which we want info.
        :param courseid: the course id
        :param taskid: the task id
        """
        return UserTask.objects(courseid=courseid, taskid=taskid, username=username).first()

    def get_audience_progress(self, audiences, course) -> dict[str, dict]:
        """
        :param audiences: List of audiences for which we want info.
        :return: A dict mapping audience id to a dict {"tried": 0, "succeeded": 0}
        """
        retval = {}
        taskids = course.get_readable_tasks()
        for audience in audiences:
            data = UserTask.objects(
                courseid=course.get_id(),
                username__in=audience.students,
                taskid__in=taskids
            ).aggregate([
                {
                    "$group": {
                        "_id": "$taskid",
                        "task_tried": { "$max": { "$gt": ["$tried", 0] } },
                        "task_succeeded": {"$max": "$succeeded" }
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "tried": {
                            "$sum": {"$cond": ["$task_tried", 1, 0]}
                        },
                        "succeeded": {
                            "$sum": {"$cond": ["$task_succeeded", 1, 0]}
                        }
                    }
                }
            ])
            retval[audience.id] = next(data, {"tried": 0, "succeeded": 0})
        return retval

    def user_saw_task(self, username, courseid, taskid):
        """ Set in the database that the user has viewed this task """
        if not username:
            return
        UserTask.objects(username=username, courseid=courseid, taskid=taskid).update_one(
            set_on_insert__username=username,
            set_on_insert__courseid=courseid,
            set_on_insert__taskid=taskid,
            set_on_insert__tried=0,
            set_on_insert__succeeded=False,
            set_on_insert__grade=0.0,
            set_on_insert__submissionid=None,
            set_on_insert__state="",
            upsert=True
        )

    def get_user_pinned_courses(self, username):
        data = User.objects(username=username).first()
        return data.pinned_courses if data else []

    def pin_course(self, username, courseid):
        data = User.objects(username=username).first()
        modified = User.objects(username=username).update(add_to_set__pinned_courses=courseid)
        return modified is not None


    def unpin_course(self, username, courseid):
        modified = User.objects(username=username, pinned_courses=courseid).update(pull__pinned_courses=courseid)
        return modified is not None


    def update_user_stats(self, username, task, submission, result_str, grade, state, newsub, task_dispenser):
        """ Update stats with a new submission """
        self.user_saw_task(username, submission["courseid"], submission["taskid"])

        eval_mode = task_dispenser.get_evaluation_mode(task.get_id())
        match_filter = {"username": username, "courseid": submission["courseid"], "taskid": submission["taskid"]}
        if newsub:
            old_submission = UserTask.objects(**match_filter).modify(inc__tried=1, inc__tokens__amount=1, new=True)

            # Update if the submission should be the default one
            if eval_mode == 'last' or (eval_mode == 'best' and old_submission.grade <= grade):
                old_submission.succeeded = result_str == "success"
                old_submission.grade = grade
                old_submission.state = state
                old_submission.submissionid = submission.id
                old_submission.save()
        else:
            old_submission = UserTask.objects.get(**match_filter)
            sort_filter = ["-grade"] if eval_mode == 'best' else []
            sort_filter.append("-submitted_on")
            def_sub = Submission.objects(**match_filter).order_by(*sort_filter).first()

            if def_sub:
                old_submission.succeeded = def_sub["result"] == "success"
                old_submission.grade = def_sub["grade"]
                old_submission.state = def_sub["state"]
                old_submission.submissionid = def_sub.id
                old_submission.save()
            elif old_submission.submissionid == submission["id"]: # otherwise, update cache if needed
                old_submission.succeeded = submission["result"] == "success"
                old_submission.grade = submission["grade"]
                old_submission.state = submission["state"]
                old_submission.save()

    def task_is_visible_by_user(self, course, task, username=None, lti=None):
        """ Returns true if the task is visible and can be accessed by the user

        :param lti: indicates if the user is currently in a LTI session or not.

            - None to ignore the check
            - True to indicate the user is in a LTI session
            - False to indicate the user is not in a LTI session
            - "auto" to enable the check and take the information from the current session
        """
        if username is None:
            username = session.username

        dispenser_filter = course.get_task_dispenser().get_accessibility(task.get_id(), username).after_start()
        return (self.course_is_open_to_user(course, username, lti) and dispenser_filter) \
               or self.has_staff_rights_on_course(course, username)

    def task_can_user_submit(self, course, task, username=None, only_check=None, lti=None):
        """ returns true if the user can submit his work for this task
            :param only_check : only checks for 'groups', 'tokens', or None if all checks
            :param lti: indicates if the user is currently in a LTI session or not.
            - None to ignore the check
            - True to indicate the user is in a LTI session
            - False to indicate the user is not in a LTI session
            - "auto" to enable the check and take the information from the current session
        """
        checks = [only_check] if only_check is not None else ["groups", "tokens"]

        if username is None:
            username = session.username

        if not username:
            return False

        if self.has_staff_rights_on_course(course, username):
            return True

        # Check if course access is ok
        course_filter = self.course_is_open_to_user(course, username, lti)

        # Check if task accessible to user
        task_filter = course.get_task_dispenser().get_accessibility(task.get_id(), username).is_open()

        # Check for group
        is_group_task = course.get_task_dispenser().get_group_submission(task.get_id())
        group = Group.objects(courseid=course.get_id(), students=username).first()
        group_filter = group is not None if 'groups' in checks and is_group_task else True

        # Check for tokens
        students = group["students"] if (group is not None and is_group_task) else [username]
        token_filter = True
        submission_limit = course.get_task_dispenser().get_submission_limit(task.get_id())
        if 'tokens' in checks and submission_limit != {"amount": -1, "period": -1}:
            user_tasks = UserTask.objects(courseid=course.get_id(), taskid=task.get_id(), username__in=students)
            token_filter = reduce(lambda last, cur: last and cur.check_tokens(submission_limit), user_tasks, True)

        return course_filter and task_filter and group_filter and token_filter


    def get_course_audiences(self, course):
        """ Returns a list of the course audiences"""
        return natsorted(list(Audience.objects(courseid=course.get_id())), key=lambda x: x["description"])

    def get_course_audiences_per_student(self, course):
        """ Returns a dictionnary mapping student -> list of audiences it belongs to, for a given course """
        course_audiences = self.get_course_audiences(course)
        student_audiences = {}
        for audience in course_audiences:
            for student in audience["students"]:
                if student not in student_audiences:
                    student_audiences[student] = []
                student_audiences[student].append(audience)
        return student_audiences

    def get_course_groups(self, course):
        """ Returns a list of the course groups"""
        return natsorted(list(Group.objects(courseid=course.get_id())), key=lambda x: x.description)

    def get_course_user_group(self, course, username=None):
        """ Returns the audience whose username belongs to
        :param course: a Course object
        :param username: The username of the user that we want to register. If None, uses session.username
        :return: the audience description
        """
        if username is None:
            username = session.username

        return Group.objects(courseid=course.get_id(), students=username).first()

    def course_register_user(self, course, username=None, password=None, force=False):
        """ Register a user to the course

        :param course: a Course object
        :param username: The username of the user that we want to register. If None, uses session.username
        :param password: Password for the course. Needed if course.is_password_needed_for_registration() and force != True
        :param force: Force registration
        :return: True if the registration succeeded, False else
        """
        if username is None:
            username = session.username

        # Do not continue registering the user in the course if username is empty
        # or if the user is not in DB (should never happen, anyway).
        if not username:
            return False
        user_info = self.get_user_info(username)
        if not user_info:
            return False

        if not force:
            if not course.is_registration_possible(user_info):
                return False
            if course.is_password_needed_for_registration() and course.get_registration_password() != password:
                return False
        if self.course_is_user_registered(course, username):
            return False  # already registered?

        CourseClass.objects(id=course.get_id()).update(push__students=username, upsert=True)

        self._logger.info("User %s registered to course %s", username, course.get_id())
        return True

    def course_unregister_user(self, course_id, username=None):
        """
        Unregister a user to the course
        :param course_id: a course id
        :param username: The username of the user that we want to unregister. If None, uses session.username
        """
        if username is None:
            username = session.username

        # If user doesn't belong to a group, will ensure correct deletion
        Audience.objects(courseid=course_id, students=username).update(pull__students=username)

        # If user doesn't belong to a group, will ensure correct deletion
        Group.objects(courseid=course_id, students=username).update(pull__students=username)

        CourseClass.objects(id=course_id).update(pull__students=username)

        self._logger.info("User %s unregistered from course %s", username, course_id)

    def course_is_open_to_user(self, course, username, lti=None, return_reason=False):
        """ Checks if a user is can access a course

        :param course: a Course object
        :param username: The username of the user that we want to check. If None, uses session.username
        :param lti: indicates if the user is currently in a LTI session or not.

            - None to ignore the check
            - True to indicate the user is in a LTI session
            - False to indicate the user is not in a LTI session
            - "auto" to enable the check and take the information from the current session

        :param return_reason: instead of False, returns a string indicating for which reason the course is not
            open to the user. Reasons may be :

            - "closed" if the course is not open
            - "unregistered_not_previewable" user is not registered and course is not previewable
            - "lti_only" the current session is not a LTI session and this course requires at LTI session
            - "lti_not_registered" this LTI course can be accessed outside an LTI session only if the user register
              first via the LTI interface

        :return: True if the user can access the course, False (or the reason if return_reason is True) otherwise
        """
        if lti == "auto":
            #FIXME: will be removed when flask dependency is removed from the module
            lti = request.blueprint in ["lti", "lti13"]

        if self.has_staff_rights_on_course(course, username):
            return True

        if not course.get_accessibility().is_open():
            return False if not return_reason else "closed"

        if not self.course_is_user_registered(course, username) and not course.allow_preview():
            return False if not return_reason else "unregistered_not_previewable"

        # LTI courses can only be accessed from a LTI session
        if lti and course.is_lti() != lti:
            return False if not return_reason else "lti_only"

        # If we are not in a LTI session, an LTI course can be accessed if we do not need to send grades back
        # to the LMS
        if lti is False and course.is_lti():
            if not course.lti_send_back_grade():
                return True
            else:
                return False if not return_reason else "lti_not_registered"

        return True

    def course_is_user_registered(self, course, username=None):
        """ Checks if a user is registered

        :param course: a Course object
        :param username: The username of the user that we want to check. If None, uses session.username
        :return: True if the user is registered, False else
        """
        if username is None:
            username = session.username

        if self.has_staff_rights_on_course(course, username):
            return True

        return CourseClass.objects(id=course.get_id(), students=username).first() is not None

    def get_course_registered_users(self, course, with_admins=True):
        """
        Get all the users registered to a course
        :param course: a Course object
        :param with_admins: include admins?
        :return: a list of usernames that are registered to the course
        """

        course_class = CourseClass.objects(id=course.get_id()).first()
        students = course_class.students if course_class else []
        if with_admins:
            return list(set(students + course.get_staff()))
        else:
            return students

    ##############################################
    #             Rights management              #
    ##############################################

    def user_is_superadmin(self, username=None):
        """
        :param username: the username. If None, the username of the currently logged in user is taken
        :return: True if the user is superadmin, False else
        """
        if username is None:
            username = session.username

        return username in self._superadmins

    def has_admin_rights_on_course(self, course, username=None, include_superadmins=True):
        """
        Check if a user can be considered as having admin rights for a course
        :type course: inginious.frontend.courses.Course
        :param username: the username. If None, the username of the currently logged in user is taken
        :param include_superadmins: Boolean indicating if superadmins should be taken into account
        :return: True if the user has admin rights, False else
        """
        if username is None:
            username = session.username

        return (username in course.get_admins()) or (include_superadmins and self.user_is_superadmin(username))

    def has_staff_rights_on_course(self, course, username=None, include_superadmins=True):
        """
        Check if a user can be considered as having staff rights for a course
        :type course: inginious.frontend.courses.Course
        :param username: the username. If None, the username of the currently logged in user is taken
        :param include_superadmins: Boolean indicating if superadmins should be taken into account
        :return: True if the user has staff rights, False else
        """
        if username is None:
            username = session.username

        return (username in course.get_staff()) or (include_superadmins and self.user_is_superadmin(username))

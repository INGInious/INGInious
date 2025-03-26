# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Factory for loading courses from disk """

from pymongo import ReturnDocument

from inginious.frontend.log import get_course_logger

from inginious.frontend.exceptions import CourseNotFoundException, CourseAlreadyExistsException, TasksetNotFoundException
from inginious.frontend.courses import Course


class CourseFactory(object):
    """ Load courses from disk """

    def __init__(self, taskset_factory, task_factory, plugin_manager, database):
        self._taskset_factory = taskset_factory
        self._task_factory = task_factory
        self._plugin_manager = plugin_manager
        self._database = database

        self._migrate_legacy_courses()

    def add_task_dispenser(self, task_dispenser):
        """
        :param task_dispenser: TaskDispenser class
        """
        self._taskset_factory.add_task_dispenser(task_dispenser)

    def get_task_dispensers(self):
        """
        Returns the supported task dispensers by this taskset factory
        """
        return self._taskset_factory.get_task_dispensers()

    def get_task_factory(self):
        """
        :return: the associated task factory
        """
        return self._task_factory

    def get_course_descriptor_content(self, courseid):
        return self._database.courses.find_one({"_id": courseid})

    def update_course_descriptor_content(self, courseid, course_content):
        self._database.courses.find_one_and_update({"_id": courseid}, {"$set": course_content})

    def update_course_descriptor_element(self, courseid, key, value):
        self._database.courses.find_one_and_update({"_id": courseid}, {"$set": {key: value}})

    def import_legacy_course(self, database, courseid):
        course_desc = self.get_course_descriptor_content(courseid)
        database.courses.find_one_and_update({"_id": courseid}, {"$set": course_desc}, upsert=True,
                                                      return_document=ReturnDocument.AFTER)

    def create_course(self, courseid, descriptor):
        existing_course = self._database.courses.find_one({"_id": courseid})
        if existing_course:
            raise CourseAlreadyExistsException()

        descriptor["_id"] = courseid
        self._database.courses.insert_one(descriptor)

    def get_course(self, courseid):
        course_desc = self.get_course_descriptor_content(courseid)
        try:
            return Course(courseid, course_desc, self._taskset_factory, self._task_factory, self._plugin_manager, self._database)
        except Exception as e:
            raise CourseNotFoundException()

    def get_all_courses(self):
        course_descriptors = self._database.courses.find({})
        result = {}
        for course_desc in course_descriptors:
            courseid = course_desc["_id"]
            try:
                result[courseid] = Course(courseid, course_desc, self._taskset_factory, self._task_factory, self._plugin_manager, self._database)
            except Exception:
                get_course_logger(courseid).warning("Cannot open course", exc_info=True)

        return result

    def delete_course(self, courseid):
        self._database.courses.delete_one({"_id": courseid})

    def _migrate_legacy_courses(self):
        courseids = []

        existing_courses = self._database.courses.find({})
        for course_descriptor in existing_courses:
            if "tasksetid" not in course_descriptor:
                courseids.append(course_descriptor["_id"])

        for tasksetid, taskset in self._taskset_factory.get_all_tasksets().items():
            if taskset.is_legacy() and not self._database.courses.find_one({"_id": tasksetid}):
                courseids.append(tasksetid)

        for courseid in courseids:
            get_course_logger(courseid).warning("Trying to migrate legacy course {}.".format(courseid))

            try:
                taskset_descriptor = self._taskset_factory.get_taskset_descriptor_content(courseid)
                cleaned_taskset_descriptor = {
                    "name": taskset_descriptor["name"],
                    "admins": taskset_descriptor.get("admins", []),
                    "description": taskset_descriptor.get( "description", ""),
                }
                if "task_dispenser" in taskset_descriptor:
                    cleaned_taskset_descriptor["task_dispenser"] = taskset_descriptor["task_dispenser"]
                    cleaned_taskset_descriptor["dispenser_data"] = taskset_descriptor.get("dispenser_data", {})
                taskset_descriptor["tasksetid"] = courseid
                taskset_descriptor["admins"] = taskset_descriptor.get("admins", []) + taskset_descriptor.get("tutors", [])

                self._database.courses.update_one({"_id": courseid}, {"$set": taskset_descriptor}, upsert=True)
                self._taskset_factory.update_taskset_descriptor_content(courseid, cleaned_taskset_descriptor)
            except TasksetNotFoundException as e:
                get_course_logger(courseid).warning("No migration from taskset possible for courseid {}.".format(courseid))


# pylint: disable=redefined-outer-name
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from collections import OrderedDict

import pytest
import os
import tempfile
import shutil

from inginious.common.filesystems.local import LocalFSProvider
from inginious.frontend.course_factory import CourseFactory
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.frontend.environment_types import register_base_env_types
from inginious.common.tasks_problems import register_problem_types
from inginious.frontend.task_problems import get_default_displayable_problem_types
from inginious.frontend.task_dispensers.combinatory_test import CombinatoryTest

task_dispensers = {TableOfContents.get_id(): TableOfContents, CombinatoryTest.get_id(): CombinatoryTest}


@pytest.fixture()
def ressource(request):
    register_base_env_types()
    dir_path = tempfile.mkdtemp()
    fs = LocalFSProvider(os.path.join(os.path.dirname(__file__), 'tasks'))
    register_problem_types(get_default_displayable_problem_types())
    course_factory = CourseFactory(fs, task_dispensers, None)
    yield (course_factory, dir_path)
    course_factory.update_course_descriptor_content("test", {"name": "Unit test 1", "admins": ["testadmin1","testadmin2"],
                                                             "accessible": True})
    shutil.rmtree(dir_path)


class TestCourse(object):

    def test_course_loading(self, ressource):
        """Tests if a course file loads correctly"""
        course_factory, temp_dir = ressource
        print("\033[1m-> common-courses: course loading\033[0m")
        c = course_factory.get_course('test')
        assert c.get_id() == 'test'
        assert c._content['accessible'] == True
        assert c._content['admins'] == ['testadmin1', 'testadmin2']
        assert c._content['name'] == 'Unit test 1'

        c = course_factory.get_course('test2')
        assert c.get_id() == 'test2'
        assert c._content['accessible'] == '1970-01-01/2033-01-01'
        assert c._content['admins'] == ['testadmin1']
        assert c._content['name'] == 'Unit test 2'

        # This one is in JSON
        c = course_factory.get_course('test3')
        assert c.get_id() == 'test3'
        assert c._content['accessible'] == '1970-01-01/1970-12-31'
        assert c._content['admins'] == ['testadmin1', 'testadmin2']
        assert c._content['name'] == 'Unit test 3'

    def test_invalid_coursename(self, ressource):
        try:
            course_factory, temp_dir = ressource
            course_factory.get_course('invalid/name')
        except:
            return
        assert False

    def test_unreadable_course(self, ressource):
        try:
            course_factory, temp_dir = ressource
            course_factory.get_course('invalid_course')
        except:
            return
        assert False

    def test_all_courses_loading(self, ressource):
        '''Tests if all courses are loaded by Course.get_all_courses()'''
        print("\033[1m-> common-courses: all courses loading\033[0m")
        course_factory, temp_dir = ressource
        c = course_factory.get_all_courses()
        assert 'test' in c
        assert 'test2' in c
        assert 'test3' in c

    def test_tasks_loading(self, ressource):
        '''Tests loading tasks from the get_tasks method'''
        print("\033[1m-> common-courses: course tasks loading\033[0m")
        course_factory, temp_dir = ressource
        c = course_factory.get_course('test')
        t = c.get_tasks()
        assert 'task1' in t
        assert 'task2' in t
        assert 'task3' in t
        assert 'task4' in t

    def test_tasks_loading_invalid(self, ressource):
        course_factory, temp_dir = ressource
        c = course_factory.get_course('test3')
        t = c.get_tasks()
        assert t == {}


class TestCourseWrite(object):
    """ Test the course update function """

    def test_course_update(self, ressource):
        course_factory, temp_dir = ressource
        os.mkdir(os.path.join(temp_dir, "test"))
        with open(os.path.join(temp_dir, "test", "course.yaml"), "w") as f:
            f.write("""
                name: "a"
                admins: ["a"]
                accessible: "1970-01-01/2033-01-01"
                        """)
        assert dict(course_factory.get_course_descriptor_content("test")) != {"name": "a", "admins": ["a"],
                                                                                    "accessible": "1970-01-01/2033-01-01"}
        course_factory.update_course_descriptor_content("test", {"name": "b", "admins": ["b"],
                                                                 "accessible": "1970-01-01/2030-01-01"})
        assert dict(course_factory.get_course_descriptor_content("test")) == {"name": "b", "admins": ["b"],
                                                                              "accessible": "1970-01-01/2030-01-01"}

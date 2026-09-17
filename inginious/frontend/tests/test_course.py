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
import datetime

from inginious.common.filesystems import init_fs_provider
from inginious.common.filesystems.local import LocalFSProvider
from inginious.frontend.courses import Course
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.frontend.environment_types import register_base_env_types
from inginious.common.tasks_problems import register_problem_types
from inginious.frontend.task_problems import get_default_displayable_problem_types
from inginious.frontend.task_dispensers import register_task_dispenser
from inginious.frontend.task_dispensers.combinatory_test import CombinatoryTest
from inginious.frontend.accessible_time import AccessibleTime

task_dispensers = {TableOfContents.get_id(): TableOfContents, CombinatoryTest.get_id(): CombinatoryTest}


@pytest.fixture()
def ressource(request):
    register_base_env_types()
    dir_path = tempfile.mkdtemp()
    init_fs_provider(LocalFSProvider(os.path.join(os.path.dirname(__file__), 'tasks')))
    register_problem_types(get_default_displayable_problem_types())
    register_task_dispenser(TableOfContents)
    register_task_dispenser(CombinatoryTest)
    yield dir_path
    c = Course("test",
               {
                   "name": "Unit test 1", "admins": ["testadmin1","testadmin2"],
                   "accessible": True
               })
    c.save()
    shutil.rmtree(dir_path)


class TestCourse(object):

    def test_course_loading(self, ressource):
        """Tests if a course file loads correctly"""
        print("\033[1m-> common-courses: course loading\033[0m")
        c = Course.get('test')
        assert c.get_id() == 'test'
        assert c._pre_validated_content['accessible'] == True
        assert c._pre_validated_content['admins'] == ['testadmin1', 'testadmin2']
        assert c._pre_validated_content['name'] == 'Unit test 1'

        c = Course.get('test2')
        assert c.get_id() == 'test2'
        assert c._pre_validated_content['accessible'] == '1970-01-01/2033-01-01'
        assert c._pre_validated_content['admins'] == ['testadmin1']
        assert c._pre_validated_content['name'] == 'Unit test 2'

        c = Course.get('test3')
        assert c.get_id() == 'test3'
        assert c._pre_validated_content['accessible'] == '1970-01-01/1970-12-31'
        assert c._pre_validated_content['admins'] == ['testadmin1', 'testadmin2']
        assert c._pre_validated_content['name'] == 'Unit test 3'

    def test_course_defaults(self, ressource):
        """Tests if a course file loads correctly with default values from the """
        print("\033[1m-> common-courses: course defaults\033[0m")
        c = Course.get('test4')
        assert c.get_id() == 'test4'
        assert c._content.admins == []
        assert c._content.tutors == []
        assert c._content.description == ""
        assert c._content.accessible is None
        assert c._content.registration is None
        assert c._content.registration_password is None
        assert c._content.registration_ac is None
        assert c._content.registration_ac_accept is True
        assert c._content.registration_ac_list == []
        assert c._content.groups_student_choice is False
        assert c._content.allow_unregister is True
        assert c._content.allow_preview is False
        assert c._content.is_lti is False
        assert c._content.archived is False
        assert c._content.archive_date is None
        assert c._content.lti_url == ""
        assert c._content.lti_keys == {}
        assert c._content.lti_config == {}
        assert c._content.lti_secrets == {}
        assert c._content.lti_send_back_grade is False
        assert c._content.tags == {}
        assert c._content.task_dispenser == "toc"
        assert c._content.dispenser_data == {}
        assert c._content.nofrontend is False

    def test_course_missing_fields(self, ressource):
        """Tests if a ValidationError is raised when a course file is missing required fields"""
        print("\033[1m-> common-courses: course missing fields\033[0m")
        try:
            Course("test5", {"description": "Test course without name"}) # missing required fields
        except:
            return
        assert False

    def test_course_invalid_accessible_time(self, ressource):
        """Tests validation on AccessibleTime fields (accessible and registration)"""
        print("\033[1m-> common-courses: course invalid accessible/registration time\033[0m")
        descriptor = {
            "name": "Unit test 6",
            "accessible": "/2026-08-24 16:52:33+02:00",
            "registration": "/202-08-24 16:52:33+02:00", # invalid date
        }
        try:
            Course("test6", descriptor)
        except:
            return

        descriptor = {
            "name": "Unit test 6",
            "accessible": "Monday", # invalid date
            "registration": False,
        }
        try:
            Course("test6", descriptor)
        except:
            return
        assert False

    def test_course_valid_accessible_time(self, ressource):
        """Tests validation on AccessibleTime fields (accessible and registration)"""
        print("\033[1m-> common-courses: course invalid accessible/registration time\033[0m")
        descriptor = {
            "name": "Unit test 6",
            "accessible": "/2026-08-24 16:52:33+02:00",
            "registration": True,
        }
        try:
            Course("test6", descriptor)
        except:
            assert False
        assert True

    def test_course_invalid_task_dispenser(self, ressource):
        """Tests validation on task_dispenser field"""
        print("\033[1m-> common-courses: course invalid task_dispenser\033[0m")
        descriptor = {
            "name": "Unit test 7",
            "task_dispenser": "invalid_dispenser", # unavailable task dispenser
        }
        try:
            Course("test7", descriptor)
        except:
            return
        assert False

    def test_course_valid_task_dispenser(self, ressource):
        """Tests validation on task_dispenser field"""
        print("\033[1m-> common-courses: course valid task_dispenser\033[0m")
        descriptor = {
            "name": "Unit test 8",
            "task_dispenser": "combinatory_test", # available task dispenser
        }
        try:
            Course("test8", descriptor)
        except:
            assert False
        assert True

    def test_course_lti_update(self, ressource):
        """Tests if lti fields are updated correctly  """
        print("\033[1m-> common-courses: course lti update\033[0m")
        descriptor = {
            "name": "Unit test 9",
            "is_lti": True,
        }
        c = Course("test9", descriptor)
        assert c._content.accessible == True
        assert c._content.registration == False
        assert c._content.registration_password is None
        assert c._content.registration_ac is None
        assert c._content.registration_ac_list == []
        assert c._content.groups_student_choice == False
        assert c._content.allow_unregister == False

        descriptor = {
            "name": "Unit test 9",
            "is_lti": False,
        }
        c = Course("test9", descriptor)
        assert c._content.lti_keys == {}
        assert c._content.lti_secrets == {}
        assert c._content.lti_config == {}
        assert c._content.lti_url == ""
        assert c._content.lti_send_back_grade == False

    def test_course_archive_date_validation(self, ressource):
        """Tests validation on archive_date field, """
        print("\033[1m-> common-courses: course archive_date validation.\033[0m")
        descriptor = {
            "name": "Unit test 10",
            "archived": True,
            "archive_date": "2026-08-24 16:52:33+02:00", # valid date
        }

        c = Course("test10", descriptor)
        assert c._content.archive_date == datetime.datetime(2026, 8, 24, 16, 52, 33, tzinfo=datetime.timezone(datetime.timedelta(hours=2)))

        descriptor = {
            "name": "Unit test 11",
            "archived": True,
            "archive_date": "invalid-date", # invalid date
        }

        try:
            Course("test11", descriptor)
        except:
            return
        assert False

    def test_course_archive_date_none(self,  ressource):
        """Tests validation on archive_date field not present when archived. """
        print("\033[1m-> common-courses: course archived/archive_date validation, archived with no date. \033[0m")
        descriptor = {
            "name": "Unit test 12",
            "archived": True,
            "archive_date": None, # valid date
        }

        try:
            Course("test12", descriptor)
        except:
            return
        assert False

    def test_course_archive_date_not_archived(self,  ressource):
        """Tests validation on archive_date field present when not archived. """
        print("\033[1m-> common-courses: course archived/archive_date validation, not archived with date.\033[0m")
        descriptor = {
            "name": "Unit test 13",
            "archived": False,
            "archive_date": "2026-08-24 16:52:33+02:00", # valid date
        }

        try:
            Course("test13", descriptor)
        except:
            return
        assert False

    def test_invalid_coursename(self, ressource):
        try:
            Course.get('invalid/name')
        except:
            return
        assert False

    def test_unreadable_course(self, ressource):
        try:
            Course.get('invalid_course')
        except:
            return
        assert False

    def test_all_courses_loading(self, ressource):
        '''Tests if all courses are loaded by Course.get_all_courses()'''
        print("\033[1m-> common-courses: all courses loading\033[0m")
        c = Course.get_all()
        assert 'test' in c
        assert 'test2' in c
        assert 'test3' in c

    def test_tasks_loading(self, ressource):
        '''Tests loading tasks from the get_tasks method'''
        print("\033[1m-> common-courses: course tasks loading\033[0m")
        c = Course.get('test')
        t = c.get_tasks()
        assert 'task1' in t
        assert 'task2' in t
        assert 'task3' in t
        assert 'task4' in t

    def test_tasks_loading_invalid(self, ressource):
        c = Course.get('test3')
        t = c.get_tasks()
        assert t == {}


class TestCourseWrite(object):
    """ Test the course update function """

    def test_course_update(self, ressource):
        temp_dir = ressource
        os.mkdir(os.path.join(temp_dir, "test"))
        with open(os.path.join(temp_dir, "test", "course.yaml"), "w") as f:
            f.write("""
                name: "a"
                admins: ["a"]
                accessible: "1970-01-01/2033-01-01"
                        """)
        assert dict(Course.get("test").get_descriptor()) != {"name": "a", "admins": ["a"],
                                                                                    "accessible": "1970-01-01/2033-01-01"}

        Course("test", {"name": "b", "admins": ["b"],"accessible": "1970-01-01/2030-01-01"}).save()

        assert dict(Course.get("test").get_descriptor()) == {"name": "b", "admins": ["b"],
                                                                              "accessible": "1970-01-01/2030-01-01"}

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

import inginious.common.filesystems as filesystems
from inginious.common.filesystems import init_fs_provider, invalidate_cache
from inginious.common.filesystems.local import LocalFSProvider
from inginious.common.exceptions import CourseAlreadyExistsException, InvalidNameException
from inginious.frontend.courses import Course
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.frontend.environment_types import register_base_env_types
from inginious.common.tasks_problems import register_problem_types
from inginious.frontend.task_problems import get_default_displayable_problem_types
from inginious.frontend.task_dispensers import register_task_dispenser
from inginious.frontend.task_dispensers.combinatory_test import CombinatoryTest

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

@pytest.fixture
def temp_fs(monkeypatch):
    """
    Create a temporary filesystem for testing purposes Allowing to test course creation and modification without
    affecting the real filesystem. This fixture sets up a temporary directory as the filesystem provider for the duration
    of the test. After the test is completed, the temporary directory is cleaned up.
    """
    register_base_env_types()
    register_problem_types(get_default_displayable_problem_types())
    register_task_dispenser(TableOfContents)
    register_task_dispenser(CombinatoryTest)

    with tempfile.TemporaryDirectory() as directory:
        test_provider = LocalFSProvider(directory)
        with monkeypatch.context() as patch:
            patch.setattr(filesystems, "_fs_provider", test_provider)
            yield directory
            invalidate_cache(test_provider)


@pytest.fixture
def temp_git_course(git_repo):
    """Create a local Git repository containing a committed course."""
    (git_repo.workspace / "course.yaml").write_text(
        """
        name: "Git Course"
        admins: ["admin"]
        accessible: true
        """
    )
    git_repo.api.index.add(["course.yaml"])
    git_repo.api.index.commit("Add course")
    return git_repo.uri


class TestCourse(object):

    @pytest.mark.parametrize("course_id", ["", "invalid/id", "invalid@id", "./..", "abc\n", ".", "..", "invalid{id}", "invalid id"])
    def test_invalid_course_id(self, ressource, course_id):
        assert Course("test", {"name": "Test"}).is_valid_id(course_id) is False

    @pytest.mark.parametrize("course_id", ["validid", "valide_id", "valid.id", "valid-id"])
    def test_valid_course_id(self, ressource, course_id):
        assert Course("test", {"name": "Test"}).is_valid_id(course_id) is True

    def test_course_id_load_char_limit(self, ressource):
        """ Tests that a course with a long id cannot be loaded, raising an InvalidNameException"""
        with pytest.raises(InvalidNameException):
            Course.get("invalid/id")

    def test_course_id_load_course_length_limit(self, ressource):
        """ Tests that a course with a long id can be loaded (e.g. the course was created before size limit was set or it is an archive) """
        Course.get("course_with_overly_long_course_id_that_exceeds_the_length_limit")

    def test_course_id_load_all_courses(self, ressource):
        """Test to see if a course with an invalid id does not raise an error when loading all courses"""
        course = Course("invalid/id", {"name": "Test"})
        # check no error is raised when loading all the courses
        Course.get_all()

    def test_course_id_length_boundaries(self, ressource):
        course = Course("test", {"name": "Test"})
        assert course.is_valid_id("a" * 50) is True
        assert course.is_valid_id("a" * 51) is False

    def test_get_archive_with_long_id(self, temp_fs):
        """Tests that an archive with an id longer than the limit can be created and loaded"""
        archive_id = "a" * 42 + "_archive_2026_11_16_10_09_59"
        c = Course(archive_id, {"name": "Test", "archived": True})
        c.create()
        Course.get(archive_id)

    def test_course_loading(self, ressource):
        """Tests if a course file loads correctly"""
        print("\033[1m-> common-courses: course loading\033[0m")
        c = Course.get('test')
        assert c.get_id() == 'test'
        assert c._content['accessible'] == True
        assert c._content['admins'] == ['testadmin1', 'testadmin2']
        assert c._content['name'] == 'Unit test 1'

        c = Course.get('test2')
        assert c.get_id() == 'test2'
        assert c._content['accessible'] == '1970-01-01/2033-01-01'
        assert c._content['admins'] == ['testadmin1']
        assert c._content['name'] == 'Unit test 2'

        c = Course.get('test3')
        assert c.get_id() == 'test3'
        assert c._content['accessible'] == '1970-01-01/1970-12-31'
        assert c._content['admins'] == ['testadmin1', 'testadmin2']
        assert c._content['name'] == 'Unit test 3'

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

    def test_create_existing_course_id(self, ressource):
        with pytest.raises(CourseAlreadyExistsException):
            Course("test", {"name": "Duplicate"}).create()

    def test_create_invalid_course_id(self, ressource):
        with pytest.raises(InvalidNameException):
            Course("invalid/id", {"name": "Invalid"}).create()

    def test_create_valid_course_id(self, temp_fs):
        c = Course("validid", {"name": "Valid"})
        c.create()
        assert c.get_id() == "validid"
        assert c.get_descriptor()["name"] == "Valid"

    def test_git_import_invalid_course_id(self, temp_fs, temp_git_course):
        with pytest.raises(InvalidNameException):
            Course("invalid/id", {"name": "Invalid"}).git_import(temp_git_course)

    def test_git_import_existing_course_id(self, temp_fs, temp_git_course):
        Course("test", {"name": "Existing"}).create()
        with pytest.raises(CourseAlreadyExistsException):
            Course("test", {"name": "Exists"}).git_import(temp_git_course)

    def test_git_import_valid_course_id(self, temp_fs, temp_git_course):
        Course("validid", {"name": "Valid"}).git_import(temp_git_course)
        course = Course.get("validid")
        assert course.get_id() == "validid"
        assert course.get_descriptor()["name"] == "Git Course"

    def test_git_import_non_existing_repo(self, temp_fs):
        with pytest.raises(Exception, match="Course import failed:"):
            Course("nonexistant", {"name": "Non-existant"}).git_import(temp_fs + "/missing-repo")

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

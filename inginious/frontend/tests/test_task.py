# pylint: disable=redefined-outer-name
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from collections import OrderedDict

import pytest
import os

from inginious.common.filesystems.local import LocalFSProvider
from inginious.common.exceptions import InvalidNameException, TaskUnreadableException
from inginious.common.tasks_problems import *

from inginious.frontend.tasks import Task
from inginious.frontend.course_factory import CourseFactory
from inginious.frontend.environment_types import register_base_env_types
from inginious.common.tasks_problems import register_problem_types
from inginious.frontend.task_problems import get_default_displayable_problem_types
from inginious.frontend.task_dispensers import register_task_dispenser
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.frontend.task_dispensers.combinatory_test import CombinatoryTest

problem_types = {"code": CodeProblem, "code_single_line": CodeSingleLineProblem, "file": FileProblem,
                 "multiple_choice": MultipleChoiceProblem, "match": MatchProblem}


@pytest.fixture()
def ressource(request):
    register_base_env_types()
    fs = LocalFSProvider(os.path.join(os.path.dirname(__file__), 'tasks'))
    course_factory = CourseFactory(fs, None)
    register_problem_types(get_default_displayable_problem_types())
    register_task_dispenser(TableOfContents)
    register_task_dispenser(CombinatoryTest)
    yield course_factory


class TestTaskBasic(object):

    def test_task_loading(self, ressource):
        '''Tests if a course file loads correctly'''
        course_factory = ressource
        print("\033[1m-> common-tasks: task loading\033[0m")
        t = course_factory.get_task('test', 'task1')
        assert t.get_environment_id() == 'default'
        assert t.get_id() == 'task1'

        env_param = t.get_environment_parameters()
        lim = env_param['limits']
        assert lim['disk'] == 100
        assert lim['memory'] == 32
        assert lim['time'] == 60

        assert t.get_problems()[0].get_type() == 'multiple_choice'

    def test_task_invalid_name(self, ressource):
        course_factory = ressource
        try:
            course_factory.get_task('test', 'invalid/name')
        except InvalidNameException:
            return
        assert False

    def test_task_invalid(self, ressource):
        course_factory = ressource
        try:
            course_factory.get_task('test3', 'invalid_task')
        except TaskUnreadableException:
            return
        assert False

    def test_no_problems(self, ressource):
        course_factory = ressource
        try:
            Task('invalid_task',
                 {"environment_id": "default",
                  "environment_type": "docker",
                  "environment_parameters": {
                      "run_cmd": '',
                      "limits": '0',
                      "time": '30',
                      "memory": '100',
                      "hard_time": '',
                  }
                  }, 'fake_path')
        except Exception as e:
            assert str(e) == "Tasks must have some problems descriptions"
            return
        assert False

    def test_input_consistent_valid(self, ressource):
        course_factory = ressource
        c = course_factory.get_course("test")
        t = c.get_task("task3")
        assert t.input_is_consistent({"unittest": "10"}, [], 0) is True

    def test_input_consistent_invalid(self, ressource):
        course_factory = ressource
        c = course_factory.get_course("test")
        t = c.get_task("task3")
        assert t.input_is_consistent({"unittest": 10}, [], 0) is False


class TestTaskProblem(object):
    def test_problem_types(self, ressource):
        '''Tests if problem types are correctly recognized'''
        course_factory = ressource
        print("\033[1m-> common-tasks: problem types parsing\033[0m")
        t = course_factory.get_task('test2', 'task1')
        assert t.get_problems()[0].get_type() == 'match'

        t = course_factory.get_task('test2', 'task2')
        assert t.get_problems()[0].get_type() == 'match'

        t = course_factory.get_task('test2', 'task3')
        assert t.get_problems()[0].get_type() == 'multiple_choice'

    def test_multiple_choice(self, ressource):
        '''Tests multiple choice problems methods'''
        course_factory = ressource
        print("\033[1m-> common-tasks: multiple_choice parsing\033[0m")
        p = course_factory.get_task('test2', 'task3').get_problems()[0]
        assert p.allow_multiple()

        # Check correct and incorrect answer
        assert p.check_answer({'unittest': [0, 1]}, "")[0]
        assert not p.check_answer({'unittest': [0, 1, 2]}, "")[0]

        # Check random form input
        assert p.input_is_consistent({'unittest': [0, 1]}, [], 0)
        assert not p.input_is_consistent('test', [], 0)
        assert not p.input_is_consistent((10, 42), [], 0)

    def test_match(self, ressource):
        '''Tests match problems methods'''
        course_factory = ressource
        print("\033[1m-> common-tasks: match-problem loading\033[0m")
        p = course_factory.get_task('test2', 'task1').get_problems()[0]

        # Check correct and incorrect answer
        assert p.check_answer({'unittest': 'Answer 1'}, "")[0]
        assert not p.check_answer({'unittest': 'Wrong answer'}, "")[0]

        # Check random form input
        assert p.input_is_consistent({'unittest': 'Answer'}, [], 0)
        assert not p.input_is_consistent('test', [], 0)
        assert not p.input_is_consistent((10, 42), [], 0)

    def test_code(self, ressource):
        '''Tests code problems methods'''
        course_factory = ressource
        print("\033[1m-> common-tasks: code problem parsing\033[0m")
        p = course_factory.get_task('test', 'task3').get_problems()[0]

        # Check random form input
        assert p.input_is_consistent({'unittest': '10'}, [], 0)
        assert not p.input_is_consistent({'unittest/decimal': '10'}, [], 0)
        assert not p.input_is_consistent('test', [], 0)
        assert not p.input_is_consistent("ddd", [], 0)
        assert not p.input_is_consistent(42, [], 0)

    def test_file(self, ressource):
        """Tests file problems methods"""
        course_factory = ressource
        print("\033[1m-> common-tasks: file problem type\033[0m")
        p = course_factory.get_task('test2', 'task4').get_problems()[0]
        assert p.get_type() == 'file'

        # Check random form input
        assert p.input_is_consistent({"unittest": {"filename": "test.txt", "value": "test"}}, [".txt"], 100)
        assert not p.input_is_consistent({"unittest": {"filename": "test.txt", "value": "test"}}, [".nottxt"],
                                         100)
        assert not p.input_is_consistent({"unittest": {"filename": "test.txt", "value": "test"}}, [".txt"], 1)
        assert not p.input_is_consistent({"unittest": {"filename": "test.txt", "content": "test"}}, [".txt"],
                                         100)
        assert not p.input_is_consistent({"unittest": "text"}, [".txt"], 100)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#

"""Test the output of a given input from a yaml inginious output file and compare with the old one"""

import argparse
import os
import time
import json
import sys

from yaml import SafeLoader, load

from inginious.common.tags import Tag
from inginious.frontend.tasks import Task
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.common.log import init_logging
from inginious.frontend.course_factory import create_factories
from inginious.client.client_sync import ClientSync
from inginious.frontend.arch_helper import start_asyncio_and_zmq, create_arch
from inginious.common.filesystems.local import LocalFSProvider
from inginious.frontend.task_problems import get_default_displayable_problem_types
from inginious.frontend.parsable_text import ParsableText


def import_class(name):
    m = name.split('.')
    mod = __import__(m[0])

    for comp in m[1:]:
        mod = getattr(mod, comp)
    return mod


def create_client(config, course_factory, fs_provider):
    """
    Create a new client and return it
    :param config: dict for configuration
    :return: a Client object
    """
    zmq_context, t = start_asyncio_and_zmq(config.get("debug_asyncio", False))
    return create_arch(config, fs_provider, zmq_context, course_factory)


def compare_all_outputs(output1, output2, keys):
    """
    Compare both the output according to each key strategy
    :param output1: output from the yaml
    :param output2: output from the new job
    :param keys: list of string, representing the keys for each value in the output
    :return: a dict, whose the form is
        {k: t,...} where k is a key whose the associated values in the outputs are different and t is a tuple containing
        the values from both the outputs
    """
    return {
            keys[i]: (output1[i], output2[i]) for i in range(len(keys))
            if compare_output(output1[i], output2[i], keys[i]) and output1[i] is not None and output2[i] is not None
        }


def compare_output(output1, output2, key):
    """
    Compare atomic elements from the outputs
    :param output1: atomic data structure from the yaml
    :param output2: atomic data structure from the new job
    :param key: key associated
    :return: True if output1 and output2 are different, False otherwise
    """

    def result_compare(output1, output2):
        """
        Compare for the result key
        :param output1: string
        :param output2: tuple (string 1, string 2)
        :return: True if output1 is different from the string 1 for output2
        """
        return output1 != output2[0]

    def problems_compare(output1, output2):
        """
        Compare for the problems key
        :param output1: dict whose each value is a list
        :param output2: dict whose each value is a tuple
        :return: True if output1 != output2, False otherwise
        """
        try:
            for k in output1:  # same keys in output1 and output2
                l = output1[k]  # in output1, values are lists of size 2
                t = output2[k]  # in output2, values are tuples of size 2
                if l[0] != t[0] or l[1] != t[1]:
                    raise BaseException("")
            return False
        except:  # KeyError or BaseException => different outputs
            return True

    def archive_compare(output1, output2):
        """
        Return False because archives are always different
        """
        return False

    def generic_compare(output1, output2):
        """
        Generic compare for keys
        :param output1: string or different object (dict, list, ...)
        :param output2: string or different object (dict, list, ...)
        :return: see code
        """
        return output1 != output2

    func = {
        "result": result_compare,
        "problems": problems_compare,
        "archive": archive_compare
    }
    return func.get(key, generic_compare)(output1, output2)


def test_task(yaml_data, task, client, client_sync):
    """
    Test the task by comparing the new outputs with the old ones
    :param yaml_data: dict corresponding to the yaml output file for the task
    :param task: Task object corresponding to the yaml data
    :param client: backend client of type Client
    :param client_sync: ClientSync object
    :return: dict whose the format is specified in compare_all_outputs function doc
    """
    if task.get_environment() not in client.get_available_containers():
        time.sleep(1)
    if task.get_environment() not in client.get_available_containers():
        raise Exception('Environment not available')
    new_output = client_sync.new_job(0, task, yaml_data['input'])  # request the client with input from yaml and given task
    keys = ["result", "grade", "problems", "tests", "custom", "state", "archive", "stdout", "stderr"]
    old_output = [yaml_data.get(x, None) for x in keys]
    return compare_all_outputs(old_output, new_output, keys)


def test_web_task(yaml_data, task, config, yaml_path):
    """
    Test the correctness of the data and task input, i.e. the content does not raise any exception and the rst contents
    are compiling
    :param yaml_data: dict, content of a task.yaml
    :param task: Task object linked to this task.yaml
    :param config: dict, configuration values
    :param yaml_path: String, path of the file
    :return: yaml_data if any error, {} otherwise
    """
    try:
        web_task = Task(
            task.get_course_id(),
            task.get_id(),
            yaml_data,
            task.get_fs(),
            task.get_hook(),
            config["default_problem_types"]
        )  # Test of init a web task with the yaml_data. if the values are incorrect, exception will be raised
        web_task.get_context('English').parse(debug=True)  # Test of compiling the context
        if not Tag.check_format(web_task.get_tags()):
            raise BaseException("Tag type not correct")
        if web_task.get_evaluate() not in ["best", "last", "student"]:
            raise BaseException("Not correct evaluation type")
        for sub_prob in yaml_data["problems"]:
            p = ParsableText(yaml_data["problems"][sub_prob]["header"])  # parse the rst of the subproblem
            p.parse(debug=True)
        return {}
    except BaseException as e:  # Rendering of Task failing
        print('{}: WEB TASK ERROR: {}'.format(yaml_path, e), file=sys.stderr)
        return yaml_data


def test_submission_yaml(client, course_factory, path, output, client_sync):
    """
    Test the content of a submission.test yaml by comparing it to the output of the client for this task and the same
    input.
    :param client: Client object
    :param course_factory: CourseFactory object
    :param path: String, path to the submission.test
    :param output: dict, output variable
    :param client_sync: ClientSync object, client_sync = ClientSync(client)
    :return: None
    """
    # print(os.path.join(test_path, yaml_file.name))
    with open(path, 'r') as yaml:
        yaml_data = load(yaml, Loader=SafeLoader)
        res = test_task(yaml_data, course_factory.get_task(yaml_data["courseid"], yaml_data["taskid"]), client, client_sync)
        if res != {}:
            output[path] = res


def test_task_yaml(path, output, course_factory, task_name, course_name, config):
    """
    Test the format and content of a task.yaml file and, if incorrect, the data is stored in the output dict
    :param path: path to the task.yaml
    :param output: output dictionary
    :param course_factory: CourseFactory object
    :param task_name: String, name of the task
    :param course_name: String, name of the course
    :param config: dict, contains configuration variable
    :return: None
    """
    with open(path, 'r') as yaml_file:
        yaml_data = load(yaml_file, Loader=SafeLoader)
    res = test_web_task(yaml_data, course_factory.get_task(course_name, task_name), config, path)
    if res != {}:
        output[path] = res


def test_all_files(config, client, course_factory):
    """
    Test each yaml file contained in the dir_path directory, with dir_path specified in the config var, as specified in
    the test_task function
    :param config: dict for configuration
    :param client: backend client of type Client
    :param course_factory: CourseFactory object
    :return: None
    """
    test_output = {}
    client_sync = ClientSync(client)
    dir_path = config["course_directory"]
    tasks = os.scandir(dir_path)
    for task in tasks:
        if task.is_dir():
            task_dir = os.scandir(task.path)
            names = [item.name for item in task_dir]
            if "task.yaml" in names:  # task directory
                if "test" in names:  # test only if the test sub directory is present
                    test_path = os.path.join(task.path, "test")
                    test_files = os.scandir(test_path)
                    for yaml_file in test_files:
                        if not yaml_file.name.startswith('.') and yaml_file.is_file():  # Exclude possible failures
                            test_submission_yaml(client, course_factory, yaml_file.path, test_output, client_sync)
                task_yaml_path = os.path.join(task.path, "task.yaml")
                test_task_yaml(task_yaml_path, test_output, course_factory, task.name, os.path.split(dir_path)[1], config)
    if test_output != {}:  # errors in task.yaml ou submission.test
        output = json.dumps(test_output)
        if "file" in config:
            with open(config["file"], "w+") as json_file:
                json_file.write(output)
        else:
            print("\n{}\n".format(output))
        raise BaseException("Testing of course failed")
        # exit(-1)  # or 255 if exit code is on 8 bits


def main():
    # Arguments parsing
    parser = argparse.ArgumentParser(description="Test the correctness of results contained in yaml files")
    parser.add_argument("--logging", '-l', help="enables logging", action="store_true")
    parser.add_argument("task_dir", help="Courses directory")
    parser.add_argument("course_dir", help="Repository for the course to test")
    parser.add_argument("-f", "--file", help="Store in the specified file in a json format")
    parser.add_argument("--tdisp", nargs="+", help="Python class import path for additionnal task dispensers")
    parser.add_argument("--ptype", nargs="+", help="Python class import path for additionnal subproblem types")

    args = parser.parse_args()

    if args.logging:
        # Init logging
        init_logging()

    task_dispensers = {
        task_dispenser.get_id(): task_dispenser for task_dispenser in [TableOfContents]
    }

    problem_types = get_default_displayable_problem_types()

    if args.tdisp:
        for tdisp_loc in args.tdisp:
            try:
                tdisp = import_class(tdisp_loc)
                task_dispensers[tdisp.get_id()] = tdisp
            except:
                print("Cannot load {}, exiting".format(tdisp_loc), file=sys.stderr)
                exit(1)

    if args.ptype:
        for ptype_loc in args.ptype:
            try:
                ptype = import_class(ptype_loc)
                problem_types[ptype.get_type()] = ptype
            except:
                print("Cannot load {}, exiting".format(ptype_loc), file=sys.stderr)
                exit(1)

    config = {
        "task_directory": args.task_dir,
        "course_directory": args.course_dir,
        "backend": "local",
        "default_problem_types": problem_types
    }  # yaml in tests directories in each task directory

    if args.file:
        config["file"] = args.file

    fs_provider = LocalFSProvider(config["task_directory"])

    try:
        course_factory, _ = create_factories(fs_provider, task_dispensers, problem_types)  # used for getting tasks

        client = create_client(config, course_factory, fs_provider)

        client.start()

        test_all_files(config, client, course_factory)

    except BaseException as e:
        print("\nAn error has occured: {}\n".format(e), file=sys.stderr)
        exit(66)

    print("\nAll yaml files in {} directory are consistent with the tests\n".format(args.course_dir))


if __name__ == "__main__":
    main()
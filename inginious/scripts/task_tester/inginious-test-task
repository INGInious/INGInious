#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#
# Original version at https://github.com/UCL-INGI/INGInious/blob/v0.4/utils/task_tester/inginious-test-task

import importlib
import argparse
import difflib
import logging
import inspect
import glob
import time
import sys
import abc
import os

# If INGInious files are not installed in Python path
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))),'..'))

from inginious.common.tasks_problems import get_default_problem_types, get_problem_types
from inginious.frontend.task_dispensers.combinatory_test import CombinatoryTest
from inginious.frontend.arch_helper import create_arch, start_asyncio_and_zmq
from inginious.frontend.task_dispensers.toc import TableOfContents
from inginious.common.filesystems.local import LocalFSProvider
from inginious.frontend.course_factory import create_factories
from inginious.common.filesystems import FileSystemProvider
from inginious.frontend.parsable_text import ParsableText
from inginious.client.client_sync import ClientSync
from inginious.common.base import load_json_or_yaml
import inginious.frontend.tasks


class TaskTesterLogger(logging.Logger):
    """ A simple logger providing colored output according to the logging level. """

    class _MyFormat(logging.Formatter):
        fmt = '\033[%i;1m{msg}\033[0m'
        def format(self, record):
            if record.levelno <= logging.INFO:
                s = self.fmt % record.color
            elif record.levelno <= logging.WARNING:
                s = self.fmt % 33
            elif record.levelno <= logging.ERROR:
                s = self.fmt % 31
            else:
                s = '{msg}'
            return s.format(msg=record.msg)

    def __init__(self):
        name = 'inginious.utils.task-tester'
        super().__init__(name)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(self._MyFormat())
        self.setLevel(logging.INFO)
        self.addHandler(handler)

    def info(self, msg, extra:dict = {}):
        default_extra = {'color': 34}
        default_extra.update(extra)
        super().info(msg, extra=default_extra)

    def success(self, msg):
        self.info(msg, {'color': 32})

logger = TaskTesterLogger()

def job_done_callback(result, filename, inputfiles, data, verbose):
    """ Compare a given submission with the result of its replay.
    """
    logger.info('-- [%i/%i] Testing input file <%s>' % (
        (job_done_callback.jobs_done + 1), len(inputfiles), filename
    ))

    """ Print stdout if verbose """
    if verbose:
        print('\x1b[1m-> Complete standard output : \033[0m')
        for line in result['stdout'].splitlines(1):
            print('\t' + line.strip('\n'))

    """ Start the comparison """
    noprob = True

    """ Step 1. Compare the submission results. """
    if 'result' in data and data['result']:
        if data['result'] != result['result'][0]:
            noprob = False
            logger.error('-> Result doesn\'t match.')
            logger.error("\tExpected <%s>\n\tGot <%s>" % (data['result'], result['result'][0]))


    """ Step 2. Compare the tags values. """
    if 'tests' in data and data['tests']:

        if not 'tests' in result:
            """ We expect some tags in the re-run result. """
            noprob = False
            logger.error('-> No tags found in the re-run.')

        else:
            """ Compare each tag of the submission """
            for tag in data['tests']:
                if not tag in result['tests']:
                    noprob = False
                    logger.error('-> No test result with tag <%s> given' % tag)
                    logger.error('\tExpected <%s>' % str(data['tests'][tag]))
                elif data['tests'][tag] != result['tests'][tag]:
                    noprob = False
                    logger.error('-> Tag values doesn\'t match.')
                    logger.error('\t Expected <%s>\n\tGot <%s>' % 
                                 (str(data['tests'][tag]), str(result['tests'][tag])))


    # TODO : This will be reworked with the new tagging system
    # See https://github.com/UCL-INGI/INGInious/issues/874

    """
    if 'stderr' in result and result['stderr']:
        noprob = False
        print('\x1b[31;1m-> There was some error(s) during execution : \033[0m')
        logger.error('-> There was some error(s) during execution :')
        for line in result['stderr'].splitlines(1):
            print('\x1b[31;1m\t' + line.strip('\n') + '\033[0m')

    if 'stdout' in data and data['stdout']:
        if data['stdout'] != result['stdout']:
            noprob = False
            logger.warning('-> Standard output doesn\'t match.')
            for line in difflib.unified_diff(data['stdout'].splitlines(1), result['stdout'].splitlines(1), fromfile='Expected', tofile='Actual'):
                print('\t' + line.strip('\n'))

    if 'text' in data and data['text']:
        if not result['result'][1]:
            noprob = False
            print("\033[1m-> No global feedback given \033[0m")
            print("\t Expected result : " + data['text'])
        elif data['text'].strip() != result['result'][1].strip():
            noprob = False
            print("\033[1m-> Global feedback doesn't match :\033[0m")
            print("\t Expected result : " + repr(data['text']))
            print("\t Actual result : " + repr(result['result'][1]))

    if 'problems' in data and data['problems']:
        if not 'problems' in result:
            noprob = False
            print("\033[1m-> No specific problem feedback given as expected \033[0m")
        else:
            for problem in data['problems']:
                if not problem in result['problems']:
                    noprob = False
                    print("\033[1m-> No feedback for problem id " + problem + " given \033[0m")
                    print("\t Expected result : " + data['problems'][problem][0] + "\n\t" + data['problems'][problem][1])
                elif data['problems'][problem][0].strip() != result['problems'][problem][0].strip():
                    noprob = False
                    print("\033[1m-> Result for problem id " + problem + " doesn't match :\033[0m")
                    print("\t Expected result : " + data['problems'][problem][0])
                    print("\t Actual result : " + result['problems'][problem][0])
                #elif repr(data['problems'][problem][1].strip()) != repr(result['problems'][problem][1].strip()):
                #    noprob = False
                #    print("\033[1m-> Feedback for problem id <" + problem + "> doesn't match :\033[0m")
                #    print("\t Expected result : " + repr(data['problems'][problem][1].strip()))
                #    print("\t Actual result : " + repr(result['problems'][problem][1].strip()))
    """

    if noprob:
        logger.success('--> All tests passed')
    else:
        job_done_callback.failed.append(filename)

    job_done_callback.jobs_done += 1


job_done_callback.jobs_done = 0
job_done_callback.failed = []


# TODO : Move this in the __init__.py of utils since it is also used in inginious-database-update util
def get_config(configfile):
    if not configfile:
        if os.path.isfile("./configuration.yaml"):
            configfile = "./configuration.yaml"
        elif os.path.isfile("./configuration.json"):
            configfile = "./configuration.json"
        else:
            raise Exception("No configuration file found")

    return load_json_or_yaml(configfile)

def launch_job(filename, data, inputfiles, task, job_manager, verbose):
    """ Re-run a submission and compare the results.
        :param filename:    The path towards the submission.
        :param data:        The submission content.
        :param inputfiles:  All the submissions to re-execute for a given task.
        :param task:        The task to test.
        :post:              The list of failed submission test and the number of re-runned 
                            submission have been updated.
    """
    result, grade, problems, tests, custom, state, archive, stdout, stderr = job_manager.new_job(0, task, data["input"], "Task tester", True)
    job_done_callback({"result":result, "grade": grade, "problems": problems, "tests": tests, "custom": custom, "archive": archive, "stdout": stdout, "stderr": stderr}, filename, inputfiles, data, verbose)

def test_task(course, taskid, job_manager, verbose) -> tuple[list, int]:
    """ Re-run submissions for a specific task.
        :param course:  The course containing the task to test.
        :param taskid:  The ID of the task to test.
        :return:        The list of failed submissions and the number of submissions re-executed.
        :post:          The containers for the list of failed submissions and the number of 
                        re-executed submissions have been reset.
    """

    logger.info('-> Re-running submissions for task <%s>' % taskid)

    """ Get task from its id """
    task = course.get_task(taskid)

    """ Build test directory path for current task """
    test_dir = os.path.join(course.get_fs().prefix, taskid, 'test/')

    """ List sample submissions for the current task """
    inputfiles = glob.glob(test_dir + '*.test')

    """ For each submission in the test directory, test the task with the specified input """
    # TODO : create thread pool to parallelize the testing
    for filename in inputfiles:
        """ Open the input file and merge with limits """
        if not os.path.exists(filename):
            logger.warning('Submission file <%s> skipped because it does not seem to be reachable.')
            continue
            
        with open(filename, 'r') as fd:
            submission = inginious.common.custom_yaml.load(fd)
        launch_job(filename, submission, inputfiles, task, job_manager, verbose)
    
    result = (job_done_callback.failed, job_done_callback.jobs_done)

    """ Simple reporting """
    failed = len(job_done_callback.failed)
    if  failed > 0:
        logger.error('%i/%i tests failed\n%s' % (
            failed,
            job_done_callback.jobs_done,
            '\n'.join(['- %s' % i for i in job_done_callback.failed])
        ))
    else:
        if job_done_callback.jobs_done == 0:
            logger.warning('No test submission found.')
        else:
            logger.success('-> All the previous submissions passed.')

    """ Reset results containers """
    job_done_callback.failed = []
    job_done_callback.jobs_done = 0

    return result


def main():
    parser = argparse.ArgumentParser(
        'Replay submissions of a given course to ensure that its task\'s grading processes are '
        'consistent over time.'

    )
    parser.add_argument("courseid", help="Course ID of the course to test.")
    parser.add_argument("taskids", nargs='*', help="Task ID(s) of the task to test.")
    parser.add_argument("-c", "--config", help="Path towards the INGInious instance configuration"
                                                "file.", default="")
    parser.add_argument("-v", "--verbose", help="Display more output", action='store_true')
    parser.add_argument("-p", "--plugins", nargs="*", help="Additional plugins required to replay"
                                                            "the course's tasks.")
    args = parser.parse_args()

    """ Read input argument """
    verbose = args.verbose
    courseid = args.courseid
    taskids = args.taskids
    plugins = args.plugins

    logger.info('Hello from the task tester utility!')

    """ Parse course configuration """
    config = get_config(args.config)

    """ Initialize course/task factory """
    task_directory = config["tasks_directory"]
    task_dispensers = {TableOfContents.get_id(): TableOfContents, CombinatoryTest.get_id(): CombinatoryTest}

    """ Set basic problem types available """
    task_problem_types = get_default_problem_types()

    """ Load additional problem types from plugins if any """
    if plugins:
        for plugin in plugins:
            pbl_types = get_problem_types(plugin)
            task_problem_types.update(pbl_types)

    """ Intialize the LocalFileSystemProvider of the instance """
    local_fsp = LocalFSProvider(task_directory)
    course_factory, task_factory = create_factories(local_fsp, task_dispensers, task_problem_types)

    """ Initialize client """
    zmq_context, asyncio_thread = start_asyncio_and_zmq()
    client = create_arch(config, local_fsp, zmq_context, course_factory)
    client.start()

    """ Get the client synchronous """
    job_manager = ClientSync(client)

    """ Open the taskfile """
    from inginious.frontend.environment_types import register_base_env_types
    register_base_env_types()

    """ Wait for the agent to load containers """
    # TODO: ugly quick fix but no better solution currently
    print('\x1b[1mWaiting for containers loading \033[0m', end='', flush=True)
    for i in range(15):
        time.sleep(1)
        print('\x1b[1m.\033[0m', end='', flush=True)
    print()

    course = course_factory.get_course(courseid)
    course_fs = course.get_fs()

    banned = ['.git/', '$common/', '.github/']
    total_ignored = []
    total_failed = []
    total_done = 0
    taskn = 0

    """ Test each specified task """
    for taskid in taskids if len(taskids) > 0 else [task_dir[:-1] for task_dir in course_fs.list(files=False)]:
        if taskid in banned or not course_fs.exists(os.path.join(taskid, 'task.yaml')):
            continue
        elif course_fs.exists(os.path.join(taskid, '.testignore')):
            logger.warning('-> Task <%s> explicitely ignored' % taskid)
            total_ignored.append(taskid)
        else:
            failed, done = test_task(course, taskid, job_manager, verbose)
            total_failed += failed
            total_done += done
        print()
        taskn += 1

    client.close()

    """ Output simple report """
    logger.warning('### Tests Summary ###')
    logger.warning('> %i tasks considered' % taskn)

    if (ignored := len(total_ignored)) > 0:
        logger.warning('> %i tasks ignored\n%s' %
            (ignored, '\n'.join(['- %s' % i for i in total_ignored]))
        )

    if len(total_failed) > 0:
        logger.error('> %i tests failed in %i tasks' % (len(total_failed), taskn))
        sys.exit(1)
    else:
        if total_done == 0:
            logger.warning('--> No test submission found for course <%s>' % courseid)
            sys.exit(0)
        else:
            logger.success('--> All the previous submissions of the tested tasks passed')
            sys.exit(0)


if __name__ == "__main__":
    main()

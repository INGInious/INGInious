# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import asyncio
import logging
import os
import time
from abc import abstractproperty, ABCMeta, abstractmethod
from typing import Dict, Any, Optional

import zmq

from inginious.common.messages import AgentHello, BackendJobId, SPResult, AgentJobDone, BackendNewJob, BackendKillJob, \
    AgentJobStarted, AgentJobSSHDebug, Ping, Pong, ZMQUtils

from inginious.common.filesystems import get_fs_provider

"""
Various utils to implements new kind of agents easily.
"""


class CannotCreateJobException(Exception):
    """
    Exception that should be raised when a (batch or std) job cannot be created in Agent.new_job or Agent.new_batch_job
    """
    def __init__(self, message):
        self.message = message
        super(CannotCreateJobException, self).__init__()


class TooManyCallsException(Exception):
    """
    Exception raised by the Agent when the function send_ssh_job_info has been called more than once
    """
    pass


class JobNotRunningException(Exception):
    """
    Exception raised by the Agent when the functions send_job_result/send_ssh_job_info are called but the job is not running anymore
    """
    pass


class Agent(object, metaclass=ABCMeta):
    """
    An INGInious agent, that grades specific kinds of jobs, and interacts with a Backend.
    """

    def __init__(self, context, backend_addr, friendly_name, concurrency):
        """
        :param context: a ZMQ context to which the agent will be linked
        :param backend_addr: address of the backend to which the agent should connect. The format is the same as ZMQ
        :param concurrency: number of simultaneous jobs that can be run by this agent
        """
        # These fields can be read/modified/overridden in subclasses
        self._logger = logging.getLogger("inginious.agent")
        self._loop = asyncio.get_event_loop()
        self._fs = get_fs_provider()

        # These fields should not be read/modified/overridden in subclasses
        self.__concurrency = concurrency

        self.__backend_addr = backend_addr
        self.__context = context
        self.__friendly_name = friendly_name
        self.__backend_socket = self.__context.socket(zmq.DEALER)
        self.__backend_socket.ipv6 = True

        self.__running_job = {}
        self.__running_batch_job = set()

        self.__backend_last_seen_time = None

        self.__asyncio_tasks_running = set()

    @property
    @abstractmethod
    def environments(self):
        """
        :return: a dict of available environments (containers most of the time) in the form

            ::

                {
                    "type": {
                        "name": {                 #  for example, "default"
                            "id": "env img id",   # "sha256:715...dd3"
                            "created": 12345678,  # create date
                            "ports": [22, 434],   # list of ports needed
                        }
                    }
                }

            If the environments are not environments, fills `created` with a fixed date (that will be shared by all agents of the same version),
            that could be 0. `id` can be anything, but should also be the same for the same versions of environments.

            Only the `type` and `name` field are shared with the Clients.
        """
        return {}

    async def run(self):
        """
        Runs the agent. Answer to the requests made by the Backend.
        May raise an asyncio.CancelledError, in which case the agent should clean itself and restart completely.
        """
        self._logger.info("Agent started")
        self.__backend_socket.connect(self.__backend_addr)

        # Tell the backend we are up and have `concurrency` threads available
        self._logger.info("Saying hello to the backend")
        await ZMQUtils.send(self.__backend_socket, AgentHello(self.__friendly_name, self.__concurrency, self.environments))
        self.__backend_last_seen_time = time.time()

        run_listen = self._loop.create_task(self.__run_listen())

        self._loop.call_later(1, self._create_safe_task, self.__check_last_ping(run_listen))

        await run_listen

    async def __check_last_ping(self, run_listen):
        """ Check if the last timeout is too old. If it is, kills the run_listen task """
        if self.__backend_last_seen_time < time.time()-10:
            self._logger.warning("Last ping too old. Restarting the agent.")
            run_listen.cancel()
            self.__cancel_remaining_safe_tasks()
        else:
            self._loop.call_later(1, self._create_safe_task, self.__check_last_ping(run_listen))

    async def __run_listen(self):
        """ Listen to the backend """
        while True:
            message = await ZMQUtils.recv(self.__backend_socket)
            await self.__handle_backend_message(message)

    async def __handle_backend_message(self, message):
        """ Dispatch messages received from clients to the right handlers """
        self.__backend_last_seen_time = time.time()
        message_handlers = {
            BackendNewJob: self.__handle_new_job,
            BackendKillJob: self.kill_job,
            Ping: self.__handle_ping
        }
        try:
            func = message_handlers[message.__class__]
        except:
            raise TypeError("Unknown message type %s" % message.__class__)
        self._create_safe_task(func(message))

    async def __handle_ping(self, _ : Ping):
        """ Handle a Ping message. Pong the backend """
        await ZMQUtils.send(self.__backend_socket, Pong())

    async def __handle_new_job(self, message: BackendNewJob):
        self._logger.info("Received request for jobid %s", message.job_id)

        # For send_job_result internal checks
        self.__running_job[message.job_id] = False  # no ssh info sent

        # Fetch previous state if exists.
        previous_state = message.inputdata.get("@state", "")

        # Tell the backend we started running the job
        await ZMQUtils.send(self.__backend_socket, AgentJobStarted(message.job_id))

        try:
            if message.environment_type not in self.environments or message.environment not in self.environments[message.environment_type]:
                self._logger.warning("Task %s/%s ask for an unknown environment %s/%s", message.course_id, message.task_id,
                                     message.environment_type, message.environment)
                raise CannotCreateJobException('This environment is not available in this agent. Please contact your course administrator.')

            task_fs = self._fs.from_subfolder(message.course_id).from_subfolder(message.task_id)
            if not task_fs.exists():
                self._logger.warning("Task %s/%s unavailable on this agent", message.course_id, message.task_id)
                raise CannotCreateJobException('Task unavailable on agent. Please retry later, the agents should synchronize soon. If the error '
                                               'persists, please contact your course administrator.')

            # Let the subclass run the job
            await self.new_job(message)
        except CannotCreateJobException as e:
            await self.send_job_result(job_id=message.job_id, result="crash", text=e.message, state=previous_state)
        except TooManyCallsException:
            self._logger.exception("TooManyCallsException in new_job")
            await self.send_job_result(job_id=message.job_id, result="crash",
                                       text="An unknown error occurred in the agent. Please contact your course administrator.",
                                       state=previous_state)
        except JobNotRunningException:
            self._logger.exception("JobNotRunningException in new_job")
        except:
            self._logger.exception("Unknown exception in new_job")
            await self.send_job_result(job_id=message.job_id, result="crash",
                                       text="An unknown error occurred in the agent. Please contact your course administrator.",
                                       state=previous_state)

    async def send_ssh_job_info(self, job_id: BackendJobId, host: str, port: int, username: str, key: str):
        """
        Send info about the SSH debug connection to the backend/client. Must be called *at most once* for each job.

        :exception JobNotRunningException: is raised when the job is not running anymore (send_job_result already called)
        :exception TooManyCallsException: is raised when this function has been called more than once
        """
        if job_id not in self.__running_job:
            raise JobNotRunningException()
        if self.__running_job[job_id]:
            raise TooManyCallsException()
        self.__running_job[job_id] = True  # now we have sent ssh info
        await ZMQUtils.send(self.__backend_socket, AgentJobSSHDebug(job_id, host, port, username, key))

    async def send_job_result(self, job_id: BackendJobId, result: str, text: str = "", grade: float = None, problems: Dict[str, SPResult] = None,
                              tests: Dict[str, Any] = None, custom: Dict[str, Any] = None, state: str = "", archive: Optional[bytes] = None,
                              stdout: Optional[str] = None, stderr: Optional[str] = None):
        """
        Send the result of a job back to the backend. Must be called *once and only once* for each job

        :exception JobNotRunningException: is raised when send_job_result is called more than once for a given job_id
        """

        if job_id not in self.__running_job:
            raise JobNotRunningException()
        del self.__running_job[job_id]

        if grade is None:
            if result == "success":
                grade = 100.0
            else:
                grade = 0.0
        if problems is None:
            problems = {}
        if custom is None:
            custom = {}
        if tests is None:
            tests = {}

        await ZMQUtils.send(self.__backend_socket, AgentJobDone(job_id, (result, text), round(grade, 2), problems, tests, custom, state, archive, stdout, stderr))

    @abstractmethod
    async def new_job(self, message: BackendNewJob):
        """
        Starts a new job. Most of the time, this function should not call send_job_result directly (as job are intended to be asynchronous). When
        there is a problem starting the job, raise CannotCreateJobException.
        If the job ends immediately, you are free to call send_job_result.

        :param message: message containing all the data needed to start the job
        :return: nothing. If any problems occurs, this method should raise a CannotCreateJobException,
                 which will result in the cancellation of the job.
        """
        pass

    @abstractmethod
    async def kill_job(self, message: BackendKillJob):
        pass

    def _create_safe_task(self, coroutine):
        """ Calls self._loop.create_task with a safe (== with logged exception) coroutine. When run() ends, these tasks
            are automatically cancelled"""
        task = self._loop.create_task(coroutine)
        self.__asyncio_tasks_running.add(task)
        task.add_done_callback(self.__remove_safe_task)

    def __remove_safe_task(self, task):
        exception = task.exception()
        if exception is not None:
            self._logger.exception("An exception occurred while running a Task", exc_info=exception)

        try:
            self.__asyncio_tasks_running.remove(task)
        except:
            pass

    def __cancel_remaining_safe_tasks(self):
        """ Cancel existing safe tasks, to allow the agent to restart properly """
        for x in self.__asyncio_tasks_running:
            x.cancel()
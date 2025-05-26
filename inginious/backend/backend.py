# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import asyncio
import logging
import queue
import time
from collections import namedtuple

import zmq
from typing import Dict
from zmq.asyncio import Poller

from inginious.backend.topic_priority_queue import TopicPriorityQueue
from inginious.common.asyncio_utils import create_safe_task
from inginious.common.messages import BackendNewJob, AgentJobStarted, AgentJobDone, AgentJobSSHDebug, \
    BackendJobDone, BackendJobStarted, BackendJobSSHDebug, ClientNewJob, ClientKillJob, BackendKillJob, AgentHello, \
    ClientHello, BackendUpdateEnvironments, Unknown, Ping, Pong, ClientGetQueue, BackendGetQueue, ZMQUtils

# This will be pushed inside a TopicPriorityQueue that uses natural ordering (smallest element has the highest priority)
# priority and time_received must thus be the two first element of the tuples.
# a tuple with a small priority value will actually be processed first.
WaitingJob = namedtuple('WaitingJob', ['priority', 'time_received', 'client_addr', 'job_id', 'msg'])

RunningJob = namedtuple('RunningJob', ['agent_addr', 'client_addr', 'msg', 'time_started'])
EnvironmentInfo = namedtuple('EnvironmentInfo', ['last_id', 'created_last', 'agents', 'type', 'variables'])
AgentInfo = namedtuple('AgentInfo', ['name', 'environments'])  # environments is a list of tuple (type, environment)

class Backend(object):
    """
        Backend. Central point of the architecture, manages communication between clients (frontends) and agents.
        Schedule jobs on agents.
    """

    def __init__(self, context, agent_addr, client_addr):
        self._content = context
        self._loop = asyncio.get_event_loop()
        self._agent_addr = agent_addr
        self._client_addr = client_addr

        self._agent_socket = context.socket(zmq.ROUTER)
        self._client_socket = context.socket(zmq.ROUTER)
        self._logger = logging.getLogger("inginious.backend")

        # Enable support for ipv6
        self._agent_socket.ipv6 = True
        self._client_socket.ipv6 = True

        self._poller = Poller()
        self._poller.register(self._agent_socket, zmq.POLLIN)
        self._poller.register(self._client_socket, zmq.POLLIN)

        # dict of available environments. Keys are first the type of environement (docker, mcq, kata...) then the
        # name of the environment.
        self._environments: Dict[str, Dict[str, EnvironmentInfo]] = {}
        self._registered_clients = set()  # addr of registered clients

        self._registered_agents: Dict[bytes, AgentInfo] = {}  # all registered agents
        self._ping_count = {}  # ping count per addr of agents

        # addr of available agents. May contain multiple times the same agent, because some agent can
        # manage multiple jobs at once!
        self._available_agents = []

        # These two share the same objects! Tuples should never be recreated.
        self._waiting_jobs_pq = TopicPriorityQueue()  # priority queue for waiting jobs
        self._waiting_jobs: Dict[str, WaitingJob] = {}  # all jobs waiting in queue

        self._job_running: Dict[str, RunningJob] = {}  # all running jobs

    async def handle_agent_message(self, agent_addr, message):
        """Dispatch messages received from agents to the right handlers"""
        message_handlers = {
            AgentHello: self.handle_agent_hello,
            AgentJobStarted: self.handle_agent_job_started,
            AgentJobDone: self.handle_agent_job_done,
            AgentJobSSHDebug: self.handle_agent_job_ssh_debug,
            Pong: self._handle_pong
        }
        try:
            func = message_handlers[message.__class__]
        except:
            raise TypeError("Unknown message type %s" % message.__class__)
        create_safe_task(self._loop, self._logger, func(agent_addr, message))

    async def handle_client_message(self, client_addr, message):
        """Dispatch messages received from clients to the right handlers"""

        # Verify that the client is registered
        if message.__class__ != ClientHello and client_addr not in self._registered_clients:
            await ZMQUtils.send_with_addr(self._client_socket, client_addr, Unknown())
            return

        message_handlers = {
            ClientHello: self.handle_client_hello,
            ClientNewJob: self.handle_client_new_job,
            ClientKillJob: self.handle_client_kill_job,
            ClientGetQueue: self.handle_client_get_queue,
            Ping: self.handle_client_ping
        }
        try:
            func = message_handlers[message.__class__]
        except:
            raise TypeError("Unknown message type %s" % message.__class__)
        create_safe_task(self._loop, self._logger, func(client_addr, message))

    async def send_environment_update_to_client(self, client_addrs):
        """ :param client_addrs: list of clients to which we should send the update """
        self._logger.debug("Sending environments updates...")
        available_environments = {type: [(env, env_info.variables) for env, env_info in environments.items()] for type, environments in self._environments.items()}
        self._logger.info(available_environments)
        msg = BackendUpdateEnvironments(available_environments)
        for client in client_addrs:
            await ZMQUtils.send_with_addr(self._client_socket, client, msg)

    async def handle_client_hello(self, client_addr, _: ClientHello):
        """ Handle an ClientHello message. Send available environments to the client """
        self._logger.info("New client connected %s", client_addr)
        self._registered_clients.add(client_addr)
        await self.send_environment_update_to_client([client_addr])

    async def handle_client_ping(self, client_addr, _: Ping):
        """ Handle an Ping message. Pong the client """
        await ZMQUtils.send_with_addr(self._client_socket, client_addr, Pong())

    async def handle_client_new_job(self, client_addr, message: ClientNewJob):
        """ Handle an ClientNewJob message. Add a job to the queue and triggers an update """

        if message.job_id in self._waiting_jobs or message.job_id in self._job_running:
            self._logger.info("Client %s asked to add a job with id %s to the queue, but it's already inside. "
                              "Duplicate random id, message repeat are possible causes, "
                              "and both should be inprobable at best.", client_addr, message.job_id)
            await ZMQUtils.send_with_addr(self._client_socket, client_addr,
                                          BackendJobDone(message.job_id, ("crash", "Duplicate job id"),
                                                         0.0, {}, {}, {}, "", None, "", ""))
            return

        self._logger.info("Adding a new job %s %s to the queue", client_addr, message.job_id)
        job = WaitingJob(message.priority, time.time(), client_addr, message.job_id, message)
        self._waiting_jobs[message.job_id] = job
        self._waiting_jobs_pq.put((message.environment_type, message.environment), job)

        await self.update_queue()

    async def handle_client_kill_job(self, client_addr, message: ClientKillJob):
        """ Handle an ClientKillJob message. Remove a job from the waiting list or send the kill message to the right agent. """
        # Check if the job is not in the waiting list
        if message.job_id in self._waiting_jobs:
            # Erase the job in waiting list
            waiting_job = self._waiting_jobs.pop(message.job_id)
            previous_state = waiting_job.msg.inputdata.get("@state", "")

            # Do not forget to send a JobDone to the initiating client
            await ZMQUtils.send_with_addr(self._client_socket, waiting_job.client_addr, BackendJobDone(
                message.job_id, ("killed", "You killed the job"), 0.0, {}, {}, {}, previous_state, None, "", ""))
        # If the job is running, transmit the info to the agent
        elif message.job_id in self._job_running:
            running_job = self._job_running[message.job_id]
            agent_addr = running_job.agent_addr
            previous_state = running_job.msg.inputdata.get("@state", "")
            await ZMQUtils.send_with_addr(self._agent_socket, agent_addr, BackendKillJob(message.job_id, previous_state))
        else:
            self._logger.warning("Client %s attempted to kill unknown job %s", str(client_addr), str(message.job_id))

    async def handle_client_get_queue(self, client_addr, _: ClientGetQueue):
        """ Handles a ClientGetQueue message. Send back info about the job queue"""
        #jobs_running: a list of tuples in the form
        #(job_id, is_current_client_job, agent_name, info, launcher, started_at, max_time)
        jobs_running = list()

        for job_id, content in self._job_running.items():
            agent_friendly_name = self._registered_agents[content.agent_addr].name
            jobs_running.append((content.msg.job_id, content.client_addr == client_addr, agent_friendly_name,
                                 content.msg.course_id+"/"+content.msg.task_id,
                                 content.msg.launcher, int(content.time_started), self._get_time_limit_estimate(content.msg)))

        #jobs_waiting: a list of tuples in the form
        #(job_id, is_current_client_job, info, launcher, max_time)
        jobs_waiting = [(job.job_id, job.client_addr == client_addr, job.msg.course_id+"/"+job.msg.task_id, job.msg.launcher,
                                     self._get_time_limit_estimate(job.msg)) for job in self._waiting_jobs.values()]

        await ZMQUtils.send_with_addr(self._client_socket, client_addr, BackendGetQueue(jobs_running, jobs_waiting))

    async def update_queue(self):
        """
        Send waiting jobs to available agents
        """
        available_agents = list(self._available_agents) # do a copy to avoid bad things

        # Loop on available agents to maximize running jobs, and break if priority queue empty
        for agent_addr in available_agents:
            if self._waiting_jobs_pq.empty():
                break  # nothing to do

            try:
                job = None
                while job is None:
                    # keep the object, do not unzip it directly! It's sometimes modified when a job is killed.
                    topics = self._registered_agents[agent_addr].environments

                    job = self._waiting_jobs_pq.get(topics)
                    priority, insert_time, client_addr, job_id, job_msg = job

                    # Ensure the job has not been removed (killed)
                    if job_id not in self._waiting_jobs:
                        job = None  # repeat the while loop. we need a job
            except queue.Empty:
                continue  # skip agent, nothing to do!

            # We have found a job, let's remove the agent from the available list
            self._available_agents.remove(agent_addr)

            # Remove the job from the queue
            del self._waiting_jobs[job_id]

            # Send the job to agent
            self._job_running[job_id] = RunningJob(agent_addr, client_addr, job_msg, time.time())
            self._logger.info("Sending job %s %s to agent %s", client_addr, job_id, agent_addr)
            await ZMQUtils.send_with_addr(self._agent_socket, agent_addr, BackendNewJob(job_id, job_msg.course_id, job_msg.task_id,
                                                                                        job_msg.task_problems, job_msg.inputdata,
                                                                                        job_msg.environment_type,
                                                                                        job_msg.environment,
                                                                                        job_msg.environment_parameters,
                                                                                        job_msg.debug))

    async def handle_agent_hello(self, agent_addr, message: AgentHello):
        """
        Handle an AgentAvailable message. Add agent_addr to the list of available agents
        """
        self._logger.info("Agent %s (%s) said hello", agent_addr, message.friendly_name)

        if agent_addr in self._registered_agents:
            # Delete previous instance of this agent, if any
            await self._delete_agent(agent_addr)

        self._registered_agents[agent_addr] = AgentInfo(message.friendly_name,
                                                        [(etype, env) for etype, envs in
                                                         message.available_environments.items() for env in envs])
        self._available_agents.extend([agent_addr for _ in range(0, message.available_job_slots)])
        self._ping_count[agent_addr] = 0

        # update information about available environments
        for environment_type, environments in message.available_environments.items():
            if environment_type not in self._environments:
                self._environments[environment_type] = {}
            env_dict = self._environments[environment_type]
            for name, environment_info in environments.items():
                self._logger.info("Anatole Backend env info")
                self._logger.info(environment_info)
                if name in env_dict:
                    # check if the id is the same
                    if env_dict[name].last_id == environment_info["id"]:
                        # ok, just add the agent to the list of agents that have the environment
                        self._logger.debug("Registering environment %s/%s for agent %s", environment_type, name, str(agent_addr))
                        env_dict[name].agents.append(agent_addr)
                    elif env_dict[name].created_last > environment_info["created"]:
                        # environments stored have been created after the new one
                        # add the agent, but emit a warning
                        self._logger.warning("Environment %s has multiple version: \n"
                                             "\t Currently registered agents have version %s (%i)\n"
                                             "\t New agent %s has version %s (%i)",
                                             name,
                                             env_dict[name].last_id, env_dict[name].created_last,
                                             str(agent_addr), environment_info["id"], environment_info["created"])
                        env_dict[name].agents.append(agent_addr)
                    else:
                        # environments stored have been created before the new one
                        # add the agent, update the infos, and emit a warning
                        self._logger.warning("Environment %s has multiple version: \n"
                                             "\t Currently registered agents have version %s (%i)\n"
                                             "\t New agent %s has version %s (%i)",
                                             name,
                                             env_dict[name].last_id, env_dict[name].created_last,
                                             str(agent_addr), environment_info["id"], environment_info["created"])
                        env_dict[name] = EnvironmentInfo(environment_info["id"], environment_info["created"],
                                                         env_dict[name].agents + [agent_addr], environment_type, environment_info.get("variables", []))
                else:
                    # just add it
                    self._logger.debug("Registering environment %s/%s for agent %s", environment_type, name, str(agent_addr))
                    env_dict[name] = EnvironmentInfo(environment_info["id"], environment_info["created"], [agent_addr], environment_type, environment_info.get("variables", []))

        # update the queue
        await self.update_queue()

        # update clients
        await self.send_environment_update_to_client(self._registered_clients)

    async def handle_agent_job_started(self, agent_addr, message: AgentJobStarted):
        """Handle an AgentJobStarted message. Send the data back to the client"""
        self._logger.debug("Job %s started on agent %s", message.job_id, agent_addr)
        if message.job_id not in self._job_running:
            self._logger.warning("Agent %s said job %s was running, but it is not in the list of running jobs", agent_addr, message.job_id)

        await ZMQUtils.send_with_addr(self._client_socket, self._job_running[message.job_id].client_addr, BackendJobStarted(message.job_id))

    async def handle_agent_job_done(self, agent_addr, message: AgentJobDone):
        """Handle an AgentJobDone message. Send the data back to the client, and start new job if needed"""

        if agent_addr in self._registered_agents:
            if message.job_id not in self._job_running:
                self._logger.warning("Job result %s from agent %s was not running", message.job_id, agent_addr)
            else:
                self._logger.info("Job %s finished on agent %s", message.job_id, agent_addr)
                # Remove the job from the list of running jobs
                running_job = self._job_running.pop(message.job_id)
                # The agent is available now
                self._available_agents.append(agent_addr)

                await ZMQUtils.send_with_addr(self._client_socket, running_job.client_addr,
                                              BackendJobDone(message.job_id, message.result, message.grade,
                                                             message.problems, message.tests, message.custom,
                                                             message.state, message.archive, message.stdout,
                                                             message.stderr))
        else:
            self._logger.warning("Job result %s from non-registered agent %s", message.job_id, agent_addr)

        # update the queue
        await self.update_queue()

    async def handle_agent_job_ssh_debug(self, agent_addr, message: AgentJobSSHDebug):
        """Handle an AgentJobSSHDebug message. Send the data back to the client"""
        if message.job_id not in self._job_running:
            self._logger.warning("Agent %s sent ssh debug info for job %s, but it is not in the list of running jobs", agent_addr, message.job_id)
        await ZMQUtils.send_with_addr(self._client_socket, self._job_running[message.job_id].client_addr,
                                      BackendJobSSHDebug(message.job_id, message.host, message.port, message.user, message.password))

    async def run(self):
        self._logger.info("Backend started")
        self._agent_socket.bind(self._agent_addr)
        self._client_socket.bind(self._client_addr)
        self._loop.call_later(1, create_safe_task, self._loop, self._logger, self._do_ping())

        try:
            while True:
                socks = await self._poller.poll()
                socks = dict(socks)

                # New message from agent
                if self._agent_socket in socks:
                    agent_addr, message = await ZMQUtils.recv_with_addr(self._agent_socket)
                    await self.handle_agent_message(agent_addr, message)

                # New message from client
                if self._client_socket in socks:
                    client_addr, message = await ZMQUtils.recv_with_addr(self._client_socket)
                    await self.handle_client_message(client_addr, message)

        except (asyncio.CancelledError, KeyboardInterrupt):
            return

    async def _handle_pong(self, agent_addr, _ : Pong):
        """ Handle a pong """
        self._ping_count[agent_addr] = 0

    async def _do_ping(self):
        """ Ping the agents """

        # the list() call here is needed, as we remove entries from _registered_agents!
        for agent_addr, agent_data in list(self._registered_agents.items()):
            friendly_name = agent_data.name

            try:
                ping_count = self._ping_count.get(agent_addr, 0)
                if ping_count > 5:
                    self._logger.warning("Agent %s (%s) does not respond: removing from list.", agent_addr, friendly_name)
                    delete_agent = True
                else:
                    self._ping_count[agent_addr] = ping_count + 1
                    await ZMQUtils.send_with_addr(self._agent_socket, agent_addr, Ping())
                    delete_agent = False
            except:
                # This should not happen, but it's better to check anyway.
                self._logger.exception("Failed to send ping to agent %s (%s). Removing it from list.", agent_addr, friendly_name)
                delete_agent = True

            if delete_agent:
                try:
                    await self._delete_agent(agent_addr)
                except:
                    self._logger.exception("Failed to delete agent %s (%s)!", agent_addr, friendly_name)

        self._loop.call_later(1, create_safe_task, self._loop, self._logger, self._do_ping())

    async def _delete_agent(self, agent_addr):
        """ Deletes an agent """
        self._available_agents = [agent for agent in self._available_agents if agent != agent_addr]
        del self._registered_agents[agent_addr]
        await self._recover_jobs()

    async def _recover_jobs(self):
        """ Recover the jobs sent to a crashed agent """
        for job_id, running_job in reversed(list(self._job_running.items())):
            if running_job.agent_addr not in self._registered_agents:
                await ZMQUtils.send_with_addr(self._client_socket, running_job.client_addr,
                                              BackendJobDone(job_id, ("crash", "Agent restarted"),
                                                             0.0, {}, {}, {}, "", None, None, None))
                del self._job_running[job_id]

        await self.update_queue()

    def _get_time_limit_estimate(self, job_info: ClientNewJob):
        """
            Returns an estimate of the time taken by a given job, if available in the environment_parameters.
            For this to work, ["limits"]["time"] must be a parameter of the environment.
        """
        try:
            return int(job_info.environment_parameters["limits"]["time"])
        except:
            return -1 # unknown
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import asyncio
import base64
import logging
import os
import resource
import shutil
import struct
import tempfile
from dataclasses import dataclass
from os.path import join as path_join
from typing import Dict, Any, Union, List, Set
import msgpack
import psutil
from inginious.agent.docker_agent._docker_interface import DockerInterface

from inginious.agent import Agent, CannotCreateJobException
from inginious.agent.docker_agent._docker_runtime import DockerRuntime
from inginious.agent.docker_agent._timeout_watcher import TimeoutWatcher
from inginious.common.asyncio_utils import AsyncIteratorWrapper, AsyncProxy
from inginious.common.base import id_checker, id_checker_tests
from inginious.common.messages import BackendNewJob, BackendKillJob


@dataclass
class DockerRunningJob:
    message: BackendNewJob
    container_path: str
    future_results: asyncio.Future
    job_id: str
    container_id: str
    inputdata: Dict[str, Any]
    debug: Union[bool, str]  # True, False or "ssh"
    ports: Dict[int, int]  # internal port -> external port mapping
    environment_type: str
    environment_name: str
    mem_limit: int
    time_limit: int
    hard_time_limit: int
    sockets_path: str
    student_path: str
    systemfiles_path: str
    course_common_student_path: str
    run_cmd: str
    assigned_external_ports: List[int]
    student_containers: Set[str]  # container ids of student containers
    enable_network: bool


@dataclass
class DockerRunningStudentContainer:
    container_id: str
    parent_info: DockerRunningJob
    socket_id: str
    write_stream: Any
    ssh: bool
    ports: Dict[int, int]  # internal port -> external port mapping
    assigned_external_ports: List[int]


class DockerAgent(Agent):
    def __init__(self, context, backend_addr, friendly_name, concurrency,
                 address_host=None, external_ports=None, tmp_dir="./agent_tmp", runtimes=None, ssh_allowed=False):
        """
        :param context: ZeroMQ context for this process
        :param backend_addr: address of the backend (for example, "tcp://127.0.0.1:2222")
        :param friendly_name: a string containing a friendly name to identify agent
        :param concurrency: number of simultaneous jobs that can be run by this agent
        :param address_host: hostname/ip/... to which external client should connect to access to the docker
        :param external_ports: iterable containing ports to which the docker instance can bind internal ports
        :param tmp_dir: temp dir that is used by the agent to start new containers
        :param type: type of the container ("docker" or "kata")
        :param runtime: runtime used by docker (the defaults are "runc" with docker or "kata-runtime" with kata)
        :param ssh_allowed: boolean to make this agent accept tasks with ssh or not
        """
        super(DockerAgent, self).__init__(context, backend_addr, friendly_name, concurrency)

        self._runtimes = {x.envtype: x for x in runtimes} if runtimes is not None else None

        self._logger = logging.getLogger("inginious.agent.docker")

        self._concurrency = concurrency

        self._max_memory_per_slot = int(psutil.virtual_memory().total / concurrency / 1024 / 1024)

        # Temp dir
        self._tmp_dir = tmp_dir

        # SSH remote debug
        self._address_host = address_host
        self._external_ports = set(external_ports) if external_ports is not None else set()

        # Async proxy to os
        self._aos = AsyncProxy(os)
        self._ashutil = AsyncProxy(shutil)

        # Does this agent allow ssh_student ?
        self._ssh_allowed = ssh_allowed

    async def _init_clean(self):
        """ Must be called when the agent is starting """
        # Data about running containers
        self._containers_running: Dict[str, DockerRunningJob] = {}  # container_id -> info
        self._container_for_job: Dict[str, str] = {}  # job id -> container_id

        self._student_containers_running: Dict[str, DockerRunningStudentContainer] = {}

        self._containers_killed = dict()

        # Delete tmp_dir, and recreate-it again
        try:
            await self._ashutil.rmtree(self._tmp_dir)
        except OSError:
            pass

        try:
            await self._aos.mkdir(self._tmp_dir)
        except OSError:
            pass

        # Docker
        self._docker = AsyncProxy(DockerInterface())

        if self._runtimes is None:
            self._runtimes = self._detect_runtimes()

        # Auto discover containers
        self._logger.info("Discovering containers")
        self._containers = await self._docker.get_containers(self._runtimes.values())

        if self._address_host is None and len(self._containers) != 0:
            self._logger.info("Guessing external host IP")
            available_bare_container_images = [image for envtype_containers in self._containers.values() for image in
                                               envtype_containers.values()]
            if len(available_bare_container_images) != 0:
                self._address_host = await self._docker.get_host_ip(available_bare_container_images[0]["id"])
            else:
                self._logger.error("Cannot find the external IP without at least an installed container.")

        if self._address_host is None:
            self._logger.warning("Cannot find external host IP. Please indicate it in the configuration. "
                                 "Remote SSH debug has been deactivated.")
            self._external_ports = None
        else:
            self._logger.info("External address for SSH remote debug is %s", self._address_host)

        # Watchers
        self._timeout_watcher = TimeoutWatcher(self._docker)

    async def _end_clean(self):
        """ Must be called when the agent is closing """
        await self._timeout_watcher.clean()

        async def close_and_delete(container_id):
            try:
                await self._docker.remove_container(container_id)
            except:
                pass

        for container_id in self._containers_running:
            await close_and_delete(container_id)
        for container_id in self._student_containers_running:
            await close_and_delete(container_id)

    @property
    def environments(self):
        return self._containers

    async def _check_docker_state(self):
        """
            Periodically checks that Docker is in a consistent state, and attempts to fix it if needed.

            Current checks:
            - If the event stream shuts down because of a bug in Docker, it will restart but we may have
              lost some "death" of containers, that must be propagated.
        """

        # If a container is not running anymore but still present in the running dictionary of the agent,
        # it may actually not be a problem as the docker watcher may not have read the event yet.
        # so we wait some time to ensure that it has the time to process the event normally.
        async def ensure_job_closing_in_one_minute(container_id, is_student):
            await asyncio.sleep(60)

            # dict in which to check if the container is still present or has been processed in the meantime
            d = self._containers_running if not is_student else self._student_containers_running
            # function to handle the processing
            f = self.handle_job_closing if not is_student else self.handle_student_job_closing

            if container_id in d:
                self._logger.warning("Container %s has an inconsistent state after 60 secs.", container_id)
                self._create_safe_task(f(container_id, -1))

        shutdown = False
        while not shutdown:
            try:
                running_container_ids = await self._docker.list_running_containers()

                incoherent_containers = set(self._containers_running).difference(running_container_ids)
                incoherent_student_containers = set(self._student_containers_running).difference(running_container_ids)

                for container_id in incoherent_containers:
                    self._create_safe_task(ensure_job_closing_in_one_minute(container_id, False))

                for container_id in incoherent_student_containers:
                    self._create_safe_task(ensure_job_closing_in_one_minute(container_id, True))

                await asyncio.sleep(90)
            except asyncio.CancelledError:
                shutdown = True
            except:
                self._logger.exception("Exception in _check_docker_state")

    async def _watch_docker_events(self):
        """
            Get raw docker events and convert them to more readable objects, and then give them to self._docker_events_subscriber.
            This function should always be active while the agent is itself active, hence the while True.
        """
        shutdown = False
        since = None  # last time we saw something. Useful if a restart happens...
        while not shutdown:
            try:
                source = AsyncIteratorWrapper(
                    self._docker.sync.event_stream(filters={"event": ["die", "oom"]}, since=since))
                self._logger.info("Docker event stream started")
                async for event in source:
                    try:
                        since = event.get('time', since)  # update time if available.

                        if event["Type"] == "container" and event["Action"] == "die":
                            container_id = event["Actor"]["ID"]
                            try:
                                retval = int(event["Actor"]["Attributes"]["exitCode"])
                            except asyncio.CancelledError:
                                raise
                            except:
                                self._logger.exception("Cannot parse exitCode for container %s", container_id)
                                retval = -1

                            if container_id in self._containers_running:
                                self._create_safe_task(self.handle_job_closing(container_id, retval))
                            elif container_id in self._student_containers_running:
                                self._create_safe_task(self.handle_student_job_closing(container_id, retval))
                        elif event["Type"] == "container" and event["Action"] == "oom":
                            container_id = event["Actor"]["ID"]
                            if container_id in self._containers_running or container_id in self._student_containers_running:
                                self._logger.info("Container %s did OOM, killing it", container_id)
                                self._containers_killed[container_id] = "overflow"
                                try:
                                    self._create_safe_task(self._docker.kill_container(container_id))
                                except asyncio.CancelledError:
                                    raise
                                except:  # this call can sometimes fail, and that is normal.
                                    pass
                        else:
                            raise ValueError("Unknown docker event format")

                    except asyncio.CancelledError:
                        raise
                    except:
                        self._logger.exception("Docker event parsing failed: %s", str(event))

                raise Exception(
                    "Docker stopped feeding the event stream. This should not happen. Restarting the event stream...")
            except asyncio.CancelledError:
                shutdown = True
            except:
                self._logger.exception("Exception in _watch_docker_events")

    def __get_fd_limit(self):
        """Get soft and hard fd limits per simultaneous jobs"""
        fd_limits = resource.getrlimit(resource.RLIMIT_NOFILE)
        return int(fd_limits[0] / self._concurrency), int(fd_limits[1] / self._concurrency)

    def __new_job_sync(self, message: BackendNewJob, future_results):
        """ Synchronous part of _new_job. Creates needed directories, copy files, and starts the container. """
        course_id = message.course_id
        task_id = message.task_id

        debug = message.debug
        environment_type = message.environment_type
        environment_name = message.environment

        try:
            enable_network = message.environment_parameters.get("network_grading", False)
            limits = message.environment_parameters.get("limits", {})
            time_limit = int(limits.get("time", 30))
            hard_time_limit = int(limits.get("hard_time", None) or time_limit * 3)
            mem_limit = int(limits.get("memory", 200))
            run_cmd = message.environment_parameters.get("run_cmd", '')
        except:
            raise CannotCreateJobException('The agent is unable to parse the parameters')

        course_fs = self._fs.from_subfolder(course_id)
        task_fs = course_fs.from_subfolder(task_id)

        if not course_fs.exists() or not task_fs.exists():
            self._logger.warning("Task %s/%s unavailable on this agent", course_id, task_id)
            raise CannotCreateJobException(
                'Task unavailable on agent. Please retry later, the agents should synchronize soon. '
                'If the error persists, please contact your course administrator.')

        # Check for realistic memory limit value
        if mem_limit < 20:
            mem_limit = 20
        elif mem_limit > self._max_memory_per_slot:
            self._logger.warning("Task %s/%s ask for too much memory (%dMB)! Available: %dMB", course_id, task_id,
                                 mem_limit, self._max_memory_per_slot)
            raise CannotCreateJobException(
                'Not enough memory on agent (available: %dMB). Please contact your course administrator.' % self._max_memory_per_slot)

        if environment_type not in self._containers or environment_name not in self._containers[environment_type]:
            self._logger.warning("Task %s/%s ask for an unknown environment %s/%s", course_id, task_id,
                                 environment_type, environment_name)
            raise CannotCreateJobException('Unknown container. Please contact your course administrator.')

        environment = self._containers[environment_type][environment_name]["id"]
        runtime = self._containers[environment_type][environment_name]["runtime"]

        ports_needed = list(
            self._containers[environment_type][environment_name]["ports"])  # copy, as we modify it later!

        if debug == "ssh" and 22 not in ports_needed:
            ports_needed.append(22)

        ports = {}
        if len(ports_needed) > 0:  # if ssh_debug, put time limits to 30 min.
            time_limit = 30 * 60
            hard_time_limit = 30 * 60
        for p in ports_needed:
            if len(self._external_ports) == 0:
                self._logger.warning("User asked for a port but no one are available")
                raise CannotCreateJobException('No ports are available right now. Please retry later.')
            ports[p] = self._external_ports.pop()

        # Create directories for storing all the data for the job
        try:
            container_path = tempfile.mkdtemp(dir=self._tmp_dir)
        except Exception as e:
            self._logger.error("Cannot make container temp directory! %s", str(e), exc_info=True)
            for p in ports:
                self._external_ports.add(ports[p])
            raise CannotCreateJobException('Cannot make container temp directory.')

        task_path = path_join(container_path, 'task')  # tmp_dir/id/task/
        course_path = path_join(container_path, 'course')

        sockets_path = path_join(container_path, 'sockets')  # tmp_dir/id/socket/
        student_path = path_join(task_path, 'student')  # tmp_dir/id/task/student/
        systemfiles_path = path_join(task_path, 'systemfiles')  # tmp_dir/id/task/systemfiles/

        course_common_path = path_join(course_path, 'common')
        course_common_student_path = path_join(course_path, 'common', 'student')

        # Create the needed directories
        os.mkdir(sockets_path)
        os.chmod(container_path, 0o777)
        os.chmod(sockets_path, 0o777)
        os.mkdir(course_path)

        # TODO: avoid copy
        task_fs.copy_from(None, task_path)
        os.chmod(task_path, 0o777)

        if not os.path.exists(student_path):
            os.mkdir(student_path)
            os.chmod(student_path, 0o777)

        # Copy common and common/student if needed
        # TODO: avoid copy
        if course_fs.from_subfolder("$common").exists():
            course_fs.from_subfolder("$common").copy_from(None, course_common_path)
        else:
            os.mkdir(course_common_path)

        if course_fs.from_subfolder("$common").from_subfolder("student").exists():
            course_fs.from_subfolder("$common").from_subfolder("student").copy_from(None, course_common_student_path)
        else:
            os.mkdir(course_common_student_path)

        # Run the container
        try:
            container_id = self._docker.sync.create_container(environment, enable_network, mem_limit, task_path,
                                                              sockets_path, course_common_path,
                                                              course_common_student_path,
                                                              self.__get_fd_limit(), runtime,
                                                              ports)
        except Exception as e:
            self._logger.warning("Cannot create container! %s", str(e), exc_info=True)
            shutil.rmtree(container_path)
            for p in ports:
                self._external_ports.add(ports[p])
            raise CannotCreateJobException('Cannot create container.')

        # Store info
        info = DockerRunningJob(
            message=message,
            container_path=container_path,
            future_results=future_results,
            job_id=message.job_id,
            container_id=container_id,
            inputdata=message.inputdata,
            debug=debug,
            ports=ports,
            environment_type=environment_type,
            environment_name=environment_name,
            mem_limit=mem_limit,
            time_limit=time_limit,
            hard_time_limit=hard_time_limit,
            sockets_path=sockets_path,
            student_path=student_path,
            systemfiles_path=systemfiles_path,
            course_common_student_path=course_common_student_path,
            run_cmd=run_cmd,
            assigned_external_ports=list(ports.values()),
            student_containers=set(),
            enable_network=enable_network
        )

        self._containers_running[container_id] = info
        self._container_for_job[message.job_id] = container_id

        try:
            # Start the container
            self._docker.sync.start_container(container_id)
        except Exception as e:
            self._logger.warning("Cannot start container! %s", str(e), exc_info=True)
            shutil.rmtree(container_path)
            for p in ports:
                self._external_ports.add(ports[p])

            raise CannotCreateJobException('Cannot start container')

        return info

    async def new_job(self, message: BackendNewJob):
        """
        Handles a new job: starts the grading container
        """
        future_results = asyncio.Future()
        out = await self._loop.run_in_executor(None, lambda: self.__new_job_sync(message, future_results))
        self._create_safe_task(self.handle_running_container(out, future_results=future_results))
        await self._timeout_watcher.register_container(out.container_id, out.time_limit, out.hard_time_limit)

    async def create_student_container(self, parent_info, socket_id, environment_name,
                                       memory_limit, time_limit, hard_time_limit, share_network, write_stream, ssh,
                                       run_as_root):
        """
        Creates a new student container.
        :param write_stream: stream on which to write the return value of the container (with a correctly formatted msgpack message)
        """
        try:
            environment_type = parent_info.environment_type
            self._logger.debug("Starting new student container... %s/%s %s %s %s", environment_type, environment_name,
                               memory_limit, time_limit, hard_time_limit)

            if environment_type not in self._containers or environment_name not in self._containers[environment_type]:
                self._logger.warning("Student container asked for an unknown environment %s/%s",
                                     environment_type, environment_name)
                await self._write_to_container_stdin(write_stream, {"type": "run_student_retval", "retval": 254,
                                                                    "socket_id": socket_id})
                return

            environment = self._containers[environment_type][environment_name]["id"]

            if run_as_root:
                runtime_name = {k for k in self._runtimes if self._runtimes[k].run_as_root}.pop()
                runtime = self._runtimes[runtime_name].runtime
            else:
                runtime = self._containers[environment_type][environment_name]["runtime"]

            ports_needed = [22] if ssh else []
            ports = {}
            for p in ports_needed:
                if not self._external_ports:
                    self._logger.warning("User asked for a port but no one are available")
                    if self._external_ports is not None:
                        for port_to_free in ports:
                            self._external_ports.add(ports[port_to_free])
                    self._logger.exception(
                        "Cannot create student container! No ports are available right now. Please retry later.")
                    await self._write_to_container_stdin(write_stream, {"type": "run_student_retval", "retval": 254,
                                                                        "socket_id": socket_id})
                    raise CannotCreateJobException('No ports are available right now. Please retry later.')
                ports[p] = self._external_ports.pop()

            try:
                socket_path = path_join(parent_info.sockets_path, str(socket_id) + ".sock")
                container_id = await self._docker.create_container_student(runtime, environment,
                                                                           memory_limit, parent_info.student_path,
                                                                           socket_path,
                                                                           parent_info.systemfiles_path,
                                                                           parent_info.course_common_student_path,
                                                                           parent_info.environment_type,
                                                                           self.__get_fd_limit(),
                                                                           parent_info.container_id if share_network else None,
                                                                           ports)
            except Exception as e:
                self._logger.exception("Cannot create student container!")
                await self._write_to_container_stdin(write_stream, {"type": "run_student_retval", "retval": 254,
                                                                    "socket_id": socket_id})

                if isinstance(e, asyncio.CancelledError):
                    raise

                return

            info = DockerRunningStudentContainer(
                container_id=container_id,
                parent_info=parent_info,
                socket_id=socket_id,
                write_stream=write_stream,
                ssh=ssh,
                ports=ports,
                assigned_external_ports=list(ports.values())
            )

            parent_info.student_containers.add(container_id)
            self._student_containers_running[container_id] = info

            # send to the container that the sibling has started
            await self._write_to_container_stdin(write_stream, {"type": "run_student_started", "socket_id": socket_id,
                                                                "container_id": container_id})

            try:
                await self._docker.start_container(container_id)
            except Exception as e:
                self._logger.exception("Cannot start student container!")
                await self._write_to_container_stdin(write_stream, {"type": "run_student_retval", "retval": 254,
                                                                    "socket_id": socket_id})

                if isinstance(e, asyncio.CancelledError):
                    raise

                return

            # Verify the time limit
            await self._timeout_watcher.register_container(container_id, time_limit, hard_time_limit)
        except asyncio.CancelledError:
            raise
        except:
            self._logger.exception("Exception in create_student_container")

    async def read_stream(self, reader_stream, buffer):
        """Helper to read a read and put data on a buffer"""
        msg_header = await reader_stream.read(8)
        # Newer implementations feed EOL AFTER the last data block and not at the end of it.
        # It can then only be detected by reading the next stream byte. This is retrocompatible.
        if reader_stream.at_eof():
            return buffer

        outtype, length = struct.unpack_from('>BxxxL',
                                             msg_header)  # format imposed by docker in the attach endpoint
        if length != 0:
            content = await reader_stream.readexactly(length)
            if outtype == 1:  # stdout
                buffer += content

            if outtype == 2:  # stderr
                self._logger.debug("Received stderr from containers:\n%s", content)
            # 4 first bytes are the length of the message. If we have a complete message...
            return buffer
        else:
            raise Exception("Wrong format message received")

    def read_buffer(self, buffer, decode=True):
        """Helper to read a buffer containing data from a stream"""
        length = struct.unpack('!I', buffer[0:4])[0]
        msg = buffer[4:4 + length]  # ... get it
        buffer = buffer[4 + length:]  # ... withdraw it from the buffer
        if decode:
            msg = msgpack.unpackb(msg, use_list=False)
        return buffer, msg

    def buffer_has_data(self, buffer):
        """Helper to know if a buffer still has available data"""
        return len(buffer) > 4 and len(buffer) >= 4 + struct.unpack('!I', buffer[0:4])[0]

    async def start_ssh(self, reader_stream, info):
        """ Wait for ssh information from student_container and send ssh info to frontend """
        buffer = bytearray()
        try:
            while not reader_stream.at_eof():  # CHECK HERE
                buffer = await self.read_stream(reader_stream, buffer)
                while self.buffer_has_data(buffer):
                    buffer, msg = self.read_buffer(buffer)
                    self._logger.debug("Received msg %s from container %s", msg["type"], info.container_id)
                    if msg["type"] == "ssh_student":
                        info_student = None
                        if len(self._student_containers_running) > 0 and msg[
                            "container_id"] in info.student_containers:
                            info_student = self._student_containers_running[msg["container_id"]]
                            await self.send_ssh_job_info(info.job_id, self._address_host, info_student.ports[22],
                                                         msg["ssh_user"], msg["ssh_key"])
                        else:
                            self._logger.exception("Exception: no linked student_container running.")
                            self._create_safe_task(self.handle_job_closing(info.container_id, -1,
                                                                           manual_feedback="Trying to connect with ssh to a non-children student container !"))
                        return
        except asyncio.IncompleteReadError:
            self._logger.debug("Container output ended with an IncompleteReadError; It was probably killed.")
        except:
            self._logger.exception("Received incorrect message from container %s (job id %s)", info.container_id,
                                   info.job_id)

    async def _write_to_container_stdin(self, write_stream, message):
        """
        Send a message to the stdin of a container, with the right data
        :param write_stream: asyncio write stream to the stdin of the container
        :param message: dict to be msgpacked and sent
        """
        msg = msgpack.dumps(message, use_bin_type=True)
        self._logger.debug("Sending %i bytes to container", len(msg))
        write_stream.write(struct.pack('!I', len(msg)))
        write_stream.write(msg)
        await write_stream.drain()

    async def _handle_student_container_outputs(self, student_reader_stream, grading_write_stream):
        """ Receive outputs (stdout and stderr) from student_container and send them to grading_container without decoding """
        buffer = bytearray()
        try:
            while not student_reader_stream.at_eof():
                buffer = await self.read_stream(student_reader_stream, buffer)
                while self.buffer_has_data(buffer):
                    buffer, msg_encoded = self.read_buffer(buffer, decode=False)
                    try:
                        grading_write_stream.write(
                            struct.pack('!I', len(msg_encoded)))  # Transfer the message without decoding it
                        grading_write_stream.write(msg_encoded)
                        await grading_write_stream.drain()
                    except Exception as e:
                        self._logger.info("Student container closed the stream")
                        self._logger.info(e)
                        return
        except asyncio.IncompleteReadError:
            self._logger.debug("Container output ended with an IncompleteReadError; It was probably killed.")
            return
        except:
            self._logger.exception("Received incorrect message from student container")

    async def handle_running_container(self, info: DockerRunningJob, future_results):
        """ Talk with a container. Sends the initial input. Allows to start student containers """
        sock = await self._docker.attach_to_container(info.container_id)
        try:
            reader_stream, write_stream = await asyncio.open_connection(sock=sock._sock)
        except asyncio.CancelledError:
            raise
        except:
            self._logger.exception("Exception occurred while creating read/write stream to container")
            return None

        # Send hello msg
        hello_msg = {"type": "start", "input": info.inputdata, "debug": info.debug,
                     "envtypes": {x.envtype: x.shared_kernel for x in self._runtimes.values()}}
        if info.run_cmd is not None:
            hello_msg["run_cmd"] = info.run_cmd
        hello_msg["run_as_root"] = self._runtimes[info.environment_type].run_as_root
        hello_msg["shared_kernel"] = self._runtimes[info.environment_type].shared_kernel

        await self._write_to_container_stdin(write_stream, hello_msg)
        result = None

        buffer = bytearray()
        try:
            student_containers_streams = {}
            while not reader_stream.at_eof():
                buffer = await self.read_stream(reader_stream, buffer)
                while self.buffer_has_data(buffer):
                    buffer, msg = self.read_buffer(buffer)
                    try:
                        self._logger.debug("Received msg %s from container %s", msg["type"], info.container_id)
                        if msg["type"] == "run_student":
                            # start a new student container
                            environment = msg["environment"] or info.environment_name
                            memory_limit = min(msg["memory_limit"] or info.mem_limit, info.mem_limit)
                            time_limit = min(msg["time_limit"] or info.time_limit, info.time_limit)
                            hard_time_limit = min(msg["hard_time_limit"] or info.hard_time_limit, info.hard_time_limit)
                            share_network = msg["share_network"]
                            socket_id = msg["socket_id"]
                            ssh = msg["ssh"]
                            run_as_root = msg["run_as_root"]
                            assert "/" not in socket_id  # ensure task creator do not try to break the agent :-(
                            if ssh and not (info.enable_network and "ssh" in info.environment_type and self._ssh_allowed):
                                self._logger.error(
                                    "Exception: ssh for student requires to allow ssh and internet access in the task %s environment configuration tab",
                                    info.job_id)
                                self._create_safe_task(self.handle_job_closing(info.container_id, -1,
                                                                               manual_feedback="ssh for student requires to allow ssh and internet access in the task environment configuration tab!"))
                            else:
                                self._create_safe_task(
                                    self.create_student_container(info, socket_id, environment, memory_limit,
                                                                  time_limit, hard_time_limit, share_network,
                                                                  write_stream, ssh, run_as_root))

                        elif msg["type"] == "run_student_init":  # We use non docker-docker communication !
                            if msg["student_container_id"] not in student_containers_streams:
                                student_containers_streams[
                                    msg["student_container_id"]] = await self.open_student_stream(
                                    msg["student_container_id"])
                            await self._write_to_container_stdin(
                                student_containers_streams[msg["student_container_id"]][1],
                                {"type": "run_student_init",
                                 "socket_id": msg["socket_id"],
                                 "command": msg["command"],
                                 "teardown_script": msg["teardown_script"],
                                 "student_container_id": msg[
                                     "student_container_id"],
                                 "working_dir": msg["working_dir"],
                                 "ssh": msg["ssh"],
                                 "user": msg["user"]})

                            if msg["ssh"]:
                                await self.start_ssh(student_containers_streams[msg["student_container_id"]][0],
                                                     info)  # If using ssh with kata: wait for ssh info and start ssh
                            else:  # classical run_student (not ssh_student) with a kata runtime -> handle student_container outputs
                                self._loop.create_task(self._handle_student_container_outputs(
                                    student_containers_streams[msg["student_container_id"]][0], write_stream))

                        elif msg["type"] in ["stdin", "student_signal"]:  # Simply transfer to student_container
                            if msg["student_container_id"] not in student_containers_streams:
                                student_containers_streams[
                                    msg["student_container_id"]] = await self.open_student_stream(
                                    msg["student_container_id"])
                            await self._write_to_container_stdin(
                                student_containers_streams[msg["student_container_id"]][1], msg)

                        elif msg["type"] == "ssh_debug":
                            # send the data to the frontend (and client) to reach grading_container
                            self._logger.info("%s %s", info.container_id, str(msg))
                            await self.send_ssh_job_info(info.job_id, self._address_host, info.ports[22],
                                                         msg["ssh_user"], msg["ssh_key"])

                        elif msg["type"] == "ssh_student":
                            # send the data to the frontend (and client) to reach student_container
                            info_student = None
                            if len(self._student_containers_running) > 0 and msg[
                                "container_id"] in info.student_containers:
                                info_student = self._student_containers_running[msg["container_id"]]
                            else:
                                self._logger.exception("Exception: no linked student_container running.")
                                self._create_safe_task(self.handle_job_closing(info.container_id, -1,
                                                                               manual_feedback="Trying to connect with ssh to a non-children student container !"))
                            self._logger.info("%s %s", info_student.container_id, str(msg))
                            await self.send_ssh_job_info(info.job_id, self._address_host, info_student.ports[22],
                                                         msg["ssh_user"], msg["ssh_key"])
                        elif msg["type"] == "result":
                            result = msg["result"]  # last message containing the results of the container
                    except:
                        self._logger.exception("Received incorrect message from container %s (job id %s)",
                                               info.container_id, info.job_id)
        except asyncio.IncompleteReadError:
            self._logger.debug("Container output ended with an IncompleteReadError; It was probably killed.")
        except asyncio.CancelledError:
            write_stream.close()
            sock._sock.close()
            future_results.set_result(result)
            raise
        except:
            self._logger.exception("Exception while reading container %s output", info.container_id)

        write_stream.close()
        sock._sock.close()
        future_results.set_result(result)

        if not result:
            self._logger.warning("Container %s has not given any result", info.container_id)

    async def open_student_stream(self, student_container_id):
        student_sock = await self._docker.attach_to_container(student_container_id)
        student_reader_stream, student_write_stream = await asyncio.open_connection(sock=student_sock._sock)
        stream = (student_reader_stream, student_write_stream)
        return stream

    async def handle_student_job_closing(self, container_id, retval):
        """ Handle a closing student container. Do some cleaning, verify memory limits, timeouts, ... and returns data to the associated grading container """
        try:
            self._logger.debug("CLOSING STUDENT CONTAINER %s", container_id)
            try:
                info = self._student_containers_running[container_id]
                del self._student_containers_running[container_id]
            except asyncio.CancelledError:
                raise
            except:
                self._logger.warning("Student container %s that has finished(p1) was not launched by this agent",
                                     str(container_id), exc_info=True)
                return

            # Delete remaining student containers
            info.parent_info.student_containers.remove(container_id)

            # Allow other container to reuse the external ports this container has finished to use
            for p in info.assigned_external_ports:
                self._external_ports.add(p)

            killed = await self._timeout_watcher.was_killed(container_id)
            if container_id in self._containers_killed:
                killed = self._containers_killed[container_id]
                del self._containers_killed[container_id]

            if killed == "timeout":
                retval = 253
            elif killed == "overflow":
                retval = 252

            try:
                await self._write_to_container_stdin(info.write_stream, {"type": "run_student_retval", "retval": retval,
                                                                         "socket_id": info.socket_id})
            except asyncio.CancelledError:
                raise
            except:
                pass  # parent container closed

            # Do not forget to remove the container
            try:
                await self._docker.remove_container(container_id)
            except asyncio.CancelledError:
                raise
            except:
                pass  # ignore
        except asyncio.CancelledError:
            raise
        except:
            self._logger.exception("Exception in handle_student_job_closing")

    async def handle_job_closing(self, container_id, retval, manual_feedback=None):
        """
        Handle a closing student container. Do some cleaning, verify memory limits, timeouts, ... and returns data to the backend
        """
        try:
            self._logger.debug("Closing %s", container_id)
            try:
                info = self._containers_running[container_id]
                del self._containers_running[container_id]
            except asyncio.CancelledError:
                raise
            except:
                self._logger.warning("Container %s that has finished(p1) was not launched by this agent",
                                     str(container_id), exc_info=True)
                return
            # Close sub containers
            for student_container_id_loop in info.student_containers:
                # little hack to ensure the value of student_container_id_loop is copied into the closure
                async def close_and_delete(student_container_id=student_container_id_loop):
                    try:
                        await self._docker.kill_container(student_container_id)
                        await self._docker.remove_container(student_container_id)
                    except asyncio.CancelledError:
                        raise
                    except:
                        pass  # ignore

                self._create_safe_task(close_and_delete(student_container_id_loop))

            # Allow other container to reuse the external ports this container has finished to use
            for p in info.assigned_external_ports:
                self._external_ports.add(p)

            # Verify if the container was killed, either by the client, by an OOM or by a timeout
            killed = await self._timeout_watcher.was_killed(container_id)
            if container_id in self._containers_killed:
                killed = self._containers_killed[container_id]
                del self._containers_killed[container_id]

            stdout = ""
            stderr = ""
            result = "crash" if retval == -1 else None
            error_msg = None
            grade = None
            problems = {}
            custom = {}
            tests = {}
            archive = None
            state = info.inputdata.get("@state", "")  # init state to previous state

            if killed is not None:
                result = killed

            # If everything did well, continue to retrieve the status from the container
            if result is None:
                # Get logs back
                try:
                    return_value = await info.future_results

                    # Accepted types for return dict
                    accepted_types = {"stdout": str, "stderr": str, "result": str, "text": str, "grade": float,
                                      "problems": dict, "custom": dict, "tests": dict, "state": str, "archive": str}

                    keys_fct = {"problems": id_checker, "custom": id_checker, "tests": id_checker_tests}

                    # Check dict content
                    for key, item in return_value.items():
                        if not isinstance(item, accepted_types[key]):
                            raise Exception("Feedback file is badly formatted.")
                        elif accepted_types[key] == dict and key != "custom":  # custom can contain anything:
                            for sub_key, sub_item in item.items():
                                if not keys_fct[key](sub_key) or isinstance(sub_item, dict):
                                    raise Exception("Feedback file is badly formatted.")

                    # Set output fields
                    stdout = return_value.get("stdout", "")
                    stderr = return_value.get("stderr", "")
                    result = return_value.get("result", "error")
                    error_msg = return_value.get("text", "")
                    grade = return_value.get("grade", None)
                    problems = return_value.get("problems", {})
                    custom = return_value.get("custom", {})
                    tests = return_value.get("tests", {})
                    state = return_value.get("state", "")
                    archive = return_value.get("archive", None)
                    if archive is not None:
                        archive = base64.b64decode(archive)
                except Exception as e:
                    self._logger.exception("Cannot get back output of container %s! (%s)", container_id, str(e))
                    result = "crash"
                    error_msg = 'The grader did not return a readable output : {}'.format(str(e))

            # Default values
            if error_msg is None:
                error_msg = ""
            if grade is None:
                if result == "success":
                    grade = 100.0
                else:
                    grade = 0.0

            # Remove container
            try:
                await self._docker.remove_container(container_id)
            except asyncio.CancelledError:
                raise
            except:
                pass

            # Delete folders
            try:
                await self._ashutil.rmtree(info.container_path)
            except PermissionError:
                self._logger.debug("Cannot remove old container path!")
                pass  # todo: run a docker container to force removal

            # Return!
            if retval == -1 and manual_feedback is not None and isinstance(manual_feedback, str):
                await self.send_job_result(info.job_id, result, manual_feedback, grade, problems, tests, custom, state,
                                           archive, stdout, stderr)
            else:
                await self.send_job_result(info.job_id, result, error_msg, grade, problems, tests, custom, state,
                                           archive, stdout, stderr)

            # Do not forget to remove data from internal state
            del self._container_for_job[info.job_id]
        except asyncio.CancelledError:
            raise
        except:
            self._logger.exception("Exception in handle_job_closing")

    async def kill_job(self, message: BackendKillJob):
        """ Handles `kill` messages. Kill things. """
        try:
            if message.job_id in self._container_for_job:
                self._containers_killed[self._container_for_job[message.job_id]] = "killed"
                await self._docker.kill_container(self._container_for_job[message.job_id])
            else:
                self._logger.warning("Cannot kill container for job %s because it is not running", str(message.job_id))
                # Ensure the backend/frontend receive the info that the job is done. This will be ignored in the worst
                # case.
                await self.send_job_result(message.job_id, "killed", state=message.state)
        except asyncio.CancelledError:
            raise
        except:
            self._logger.exception("Exception in handle_kill_job")

    async def run(self):
        await self._init_clean()

        # Init Docker events watchers
        self._create_safe_task(self._watch_docker_events())
        self._create_safe_task(self._check_docker_state())

        try:
            await super(DockerAgent, self).run()
        except:
            await self._end_clean()
            raise

    def _detect_runtimes(self) -> Dict[str, DockerRuntime]:
        heuristic = [
            ("runc", lambda x, y: DockerRuntime(runtime=x, run_as_root=False, enables_gpu=False,
                                                shared_kernel=True, envtype="docker-ssh" if y else "docker")),
            ("crun", lambda x, y: DockerRuntime(runtime=x, run_as_root=False, enables_gpu=False,
                                                shared_kernel=True, envtype="docker-ssh" if y else "docker")),
            ("kata", lambda x, y: DockerRuntime(runtime=x, run_as_root=True, enables_gpu=False,
                                                shared_kernel=False, envtype="kata-ssh" if y else "kata")),
            ("nvidia", lambda x, y: DockerRuntime(runtime=x, run_as_root=False, enables_gpu=True,
                                                  shared_kernel=True, envtype="nvidia-ssh" if y else "nvidia"))
        ]
        retval = {}

        for runtime in self._docker.sync.list_runtimes().keys():
            for h_runtime, f in heuristic:
                if h_runtime in runtime:
                    for ssh_allowed in {self._ssh_allowed, False}:
                        v = f(runtime, ssh_allowed)
                        if v.envtype not in retval:
                            self._logger.info("Using %s as runtime with parameters %s", runtime, str(v))
                            retval[v.envtype] = v
                        else:
                            self._logger.warning(
                                "%s was detected as a runtime; it would duplicate another one, so we ignore it. %s",
                                runtime, str(v))
        return retval

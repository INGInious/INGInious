# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

"""
    (not asyncio) Interface to Docker
"""
import os
from datetime import datetime
from typing import List, Tuple, Dict

import docker
import logging

from docker.types import Ulimit

from inginious.agent.docker_agent._docker_runtime import DockerRuntime

DOCKER_AGENT_VERSION = 3


class DockerInterface(object):  # pragma: no cover
    """
        (not asyncio) Interface to Docker

        We do not test coverage here, as it is a bit complicated to interact with docker in tests.
        Docker-py itself is already well tested.
    """
    @property
    def _docker(self):
        return docker.from_env()
    
    def get_containers(self, runtimes: List[DockerRuntime]) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        :param runtimes: a list of DockerRuntime. Each DockerRuntime.envtype must appear only once.
        :return: a dict of available containers in the form
        {
            "envtype": {                       # the value of DockerRuntime.envtype. Eg "docker".
                "name": {                      # for example, "default"
                    "id": "container img id",  # "sha256:715c5cb5575cdb2641956e42af4a53e69edf763ce701006b2c6e0f4f39b68dd3"
                    "created": 12345678,       # create date
                    "ports": [22, 434],        # list of ports needed
                    "runtime": "runtime"       # the value of DockerRuntime.runtime. Eg "runc".
                }
            }
        }
        """
        assert len(set(x.envtype for x in runtimes)) == len(runtimes)  # no duplicates in the envtypes

        logger = logging.getLogger("inginious.agent.docker")

        # First, create a dict with {"env": {"id": {"title": "alias", "created": 000, "ports": [0, 1]}}}
        images = {x.envtype: {} for x in runtimes}

        for x in self._docker.images.list(filters={"label": "org.inginious.grading.name"}):
            title = None
            try:
                title = x.labels["org.inginious.grading.name"]
                created = x.history()[0]['Created']
                ports = [int(y) for y in x.labels["org.inginious.grading.ports"].split(
                    ",")] if "org.inginious.grading.ports" in x.labels else []

                for docker_runtime in runtimes:
                    if "org.inginious.grading.need_root" in x.labels and not docker_runtime.run_as_root:
                        continue
                    if "org.inginious.grading.need_gpu" in x.labels and not docker_runtime.enables_gpu:
                        continue

                    logger.info("Envtype %s (%s) can use container %s", docker_runtime.envtype, docker_runtime.runtime, title)
                    if x.labels.get("org.inginious.grading.agent_version") != str(DOCKER_AGENT_VERSION):
                        logger.warning(
                            "Container %s is made for an old/newer version of the agent (container version is "
                            "%s, but it should be %i). INGInious will ignore the container.", title,
                            str(x.labels.get("org.inginious.grading.agent_version")), DOCKER_AGENT_VERSION)
                        continue

                    images[docker_runtime.envtype][x.attrs['Id']] = {
                        "title": title,
                        "created": created,
                        "ports": ports,
                        "runtime": docker_runtime.runtime
                    }
            except:
                logging.getLogger("inginious.agent").exception("Container %s is badly formatted", title or "[cannot load title]")

        # Then, we keep only the last version of each name
        latest = {}
        for envtype, content in images.items():
            latest[envtype] = {}
            for img_id, img_c in content.items():
                if img_c["title"] not in latest[envtype] or latest[envtype][img_c["title"]]["created"] < img_c["created"]:
                    latest[envtype][img_c["title"]] = {"id": img_id, **img_c}
        return latest

    def get_host_ip(self, env_with_dig='ingi/inginious-c-default'):
        """
        Get the external IP of the host of the docker daemon. Uses OpenDNS internally.
        :param env_with_dig: any container image that has dig
        """
        try:
            container = self._docker.containers.create(env_with_dig, command="dig +short myip.opendns.com @resolver1.opendns.com")
            container.start()
            response = container.wait()
            assert response["StatusCode"] == 0 if isinstance(response, dict) else response == 0
            answer = container.logs(stdout=True, stderr=False).decode('utf8').strip()
            container.remove(v=True, link=False, force=True)
            return answer
        except:
            return None

    def create_container(self, image, network_grading, mem_limit, task_path, sockets_path,
                         course_common_path, course_common_student_path, fd_limit, runtime: str, ports=None):
        """
        Creates a container.
        :param image: env to start (name/id of a docker image)
        :param network_grading: boolean to indicate if the network should be enabled in the container or not
        :param mem_limit: in Mo
        :param task_path: path to the task directory that will be mounted in the container
        :param sockets_path: path to the socket directory that will be mounted in the container
        :param course_common_path:
        :param course_common_student_path:
        :param fd_limit: Tuple with soft and hard limits per slot for FS
        :param runtime: name of the docker runtime to use
        :param ports: dictionary in the form {docker_port: external_port}
        :return: the container id
        """
        task_path = os.path.abspath(task_path)
        sockets_path = os.path.abspath(sockets_path)
        course_common_path = os.path.abspath(course_common_path)
        course_common_student_path = os.path.abspath(course_common_student_path)
        if ports is None:
            ports = {}

        nofile_limit = Ulimit(name='nofile', soft=fd_limit[0], hard=fd_limit[1])

        response = self._docker.containers.create(
            image,
            stdin_open=True,
            mem_limit=str(mem_limit) + "M",
            memswap_limit=str(mem_limit) + "M",
            mem_swappiness=0,
            oom_kill_disable=True,
            network_mode=("bridge" if (network_grading or len(ports) > 0) else 'none'),
            ports=ports,
            volumes={
                task_path: {'bind': '/task'},
                sockets_path: {'bind': '/sockets'},
                course_common_path: {'bind': '/course/common', 'mode': 'ro'},
                course_common_student_path: {'bind': '/course/common/student', 'mode': 'ro'}
            },
            runtime=runtime,
            ulimits=[nofile_limit]
        )
        return response.id

    def create_container_student(self, runtime: str, image: str, mem_limit, student_path,
                                 socket_path, systemfiles_path, course_common_student_path,
                                 parent_runtime: str,fd_limit, share_network_of_container: str=None, ports=None):
        """
        Creates a student container
        :param fd_limit:Tuple with soft and hard limits per slot for FS
        :param runtime: name of the docker runtime to use
        :param image: env to start (name/id of a docker image)
        :param mem_limit: in Mo
        :param student_path: path to the task directory that will be mounted in the container
        :param socket_path: path to the socket that will be mounted in the container
        :param systemfiles_path: path to the systemfiles folder containing files that can override partially some defined system files
        :param course_common_student_path:
        :param share_network_of_container: (deprecated) if a container id is given, the new container will share its
                                           network stack.
        :param ports: dictionary in the form {docker_port: external_port}
        :return: the container id
        """
        student_path = os.path.abspath(student_path)
        socket_path = os.path.abspath(socket_path)
        systemfiles_path = os.path.abspath(systemfiles_path)
        course_common_student_path = os.path.abspath(course_common_student_path)
        secured_scripts_path = student_path+"/scripts"

        if ports is None:
            ports = {}

        if len(ports) > 0:
            net_mode = "bridge"  # TODO: better to use "bridge" or "container:" + grading_container_id ?
        elif not share_network_of_container:
            net_mode = "none"
        else:
            net_mode = 'container:' + share_network_of_container

        nofile_limit = Ulimit(name='nofile', soft=fd_limit[0], hard=fd_limit[1])

        response = self._docker.containers.create(
            image,
            stdin_open=True,
            command="_run_student_intern "+runtime + " " + parent_runtime,  # the script takes the runtimes as arguments
            mem_limit=str(mem_limit) + "M",
            memswap_limit=str(mem_limit) + "M",
            mem_swappiness=0,
            oom_kill_disable=True,
            network_mode=net_mode,
            ports=ports,
            volumes={
                student_path: {'bind': '/task/student'},
                secured_scripts_path: {'bind': '/task/student/scripts'},
                socket_path: {'bind': '/__parent.sock'},
                systemfiles_path: {'bind': '/task/systemfiles', 'mode': 'ro'},
                course_common_student_path: {'bind': '/course/common/student', 'mode': 'ro'}
            },
            runtime=runtime,
            ulimits=[nofile_limit]
        )

        return response.id

    def start_container(self, container_id):
        """ Starts a container (obviously) """
        self._docker.containers.get(container_id).start()

    def attach_to_container(self, container_id):
        """ A socket attached to the stdin/stdout of a container. The object returned contains a get_socket() function to get a socket.socket
        object and  close_socket() to close the connection """
        return self._docker.containers.get(container_id).attach_socket(params={
            'stdin': 1,
            'stdout': 1,
            'stderr': 0,
            'stream': 1,
        })

    def get_logs(self, container_id):
        """ Return the full stdout/stderr of a container"""
        stdout = self._docker.containers.get(container_id).logs(stdout=True, stderr=False).decode('utf8')
        stderr = self._docker.containers.get(container_id).logs(stdout=False, stderr=True).decode('utf8')
        return stdout, stderr

    def get_stats(self, container_id):
        """
        :param container_id:
        :return: an iterable that contains dictionnaries with the stats of the running container. See the docker api for content.
        """
        return self._docker.containers.get(container_id).stats(decode=True)

    def list_running_containers(self):
        """ Returns a set of running container ids """
        return {x.attrs.get('Id') for x in self._docker.containers.list(all=False, sparse=True)}

    def remove_container(self, container_id):
        """
        Removes a container (with fire)
        """
        self._docker.containers.get(container_id).remove(v=True, link=False, force=True)

    def kill_container(self, container_id, signal=None):
        """
        Kills a container
        :param signal: custom signal. Default is SIGKILL.
        """
        self._docker.containers.get(container_id).kill(signal)

    def event_stream(self, filters=None, since=None):
        """
        :param filters: filters to apply on messages. See docker api.
        :param since: time since when the events should be sent. See docker api.
        :return: an iterable that contains events from docker. See the docker api for content.
        """
        if filters is None:
            filters = {}
        return self._docker.events(decode=True, filters=filters, since=since)

    def list_runtimes(self) -> Dict[str, str]:
        """
        :return: dict of runtime: path_to_runtime
        """
        return {name: x["path"] for name, x in self._docker.info()["Runtimes"].items()}

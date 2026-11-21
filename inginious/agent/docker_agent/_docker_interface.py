# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

"""
    (not asyncio) Interface to Docker
"""
import os
import random
from typing import List, Tuple, Dict

import docker
import logging

from docker.types import Ulimit

from inginious.agent.docker_agent.capabilities import DockerAgentCapabilities
from inginious.common.agents import GradingEnvironment

DOCKER_AGENT_VERSION = 4


class DockerInterface:  # pragma: no cover
    """
        (not asyncio) Interface to Docker

        We do not test coverage here, as it is a bit complicated to interact with docker in tests.
        Docker-py itself is already well tested.
    """
    @property
    def _docker(self):
        return docker.from_env()

    def get_cgroup_version(self) -> str:
        """
        :return: the cgroup version, that is, "1" or "2".
        """
        return self._docker.info().get("CgroupVersion")
    
    def get_containers(self, capabilities: DockerAgentCapabilities) -> dict[str, GradingEnvironment]:
        """
        :param capabilities: Agent capabilities.
        :return: a dict of available containers in the form
        {
            "<env name>": {                # for example, "default"
                "id": "container img id",  # "sha256:715c5cb5575cdb2641956e42af4a53e69edf763ce701006b2c6e0f4f39b68dd3"
                "created": 12345678,       # create date
                "ports": [22, 434],        # list of ports needed
            }
        }
        """
        logger = logging.getLogger("inginious.agent.docker")
        environments = {}

        def filter_by_capability(label: str, capa: bool, labels: dict) -> bool:
            """
                Check whether the grading environment requests the capability <label>,
                and, if yes, whether the Agent exposes that capability.

                If the capability is not requested, the Agent is able to launch the environment.
            """
            if (requested := labels.get(label)) is not None:
                # Sanity check on the capability input.
                if not isinstance(requested, int) or requested not in [0, 1]:
                    logger.warning("Capability value is not 1 or 0. Ignoring.")
                    return False
                # The Agent can launch the environement if the capability is requested and it
                # supports it, or if the capability is not requested.
                return (requested == 1 and capa) or requested == 0
            return True

        def filter_by_capabilities(labels, capabilities: DockerAgentCapabilities) -> bool:
            run_as_root = filter_by_capability('org.inginious.need_root', capabilities.run_as_root, labels)
            gpu = filter_by_capability('org.inginious.need_gpu', capabilities.gpu, labels)
            ssh = filter_by_capability('org.inginious.need_ssh', capabilities.ssh, labels)
            return run_as_root and gpu and ssh
            
        for img in self._docker.images.list(filters={"label": "org.inginious.grading.name"}):
            if (env := img.labels.get("org.inginious.grading.name")) is None:
                logger.warning("Failed to load grading environement name. Ignoring.")
                continue
            
            created = img.history()[0]['Created']
            ports = [
                int(y) for y in img.labels["org.inginious.grading.ports"].split(",")
            ] if "org.inginious.grading.ports" in img.labels else []

            # Does the Agent support the grading environment?
            if not filter_by_capabilities(img.labels, capabilities):
                continue
            
            if (agent_version := img.labels.get("org.inginious.grading.agent_version")) is not None and agent_version != str(DOCKER_AGENT_VERSION):
                logger.warning(
                    f"Grading environment {env} is made for an old/newer version of the agent. Requested version is {agent_version}, but current version is {DOCKER_AGENT_VERSION}. Ignoring.")
                continue

            logger.info(f"Agent supports grading environement {env}")

            """
            environments =
            { <env>: {
                <id>: {'created': int, 'ports': list }
              } 
            }
            """
            if (id := img.attrs.get('Id')) is not None:
                img_data = {'created': created, 'ports': ports}
                if (env_data := environments.get(env)):
                    env_data[id] = img_data
                else:
                    environments[env] = {id: img_data}

        # TODO: Filter on release tag.
        # Then, we keep only the last version of each name
        latest = {}
        for env, env_data in environments.items():
            for id, img_data in env_data.items():
                if env not in latest or latest[env].created < img_data["created"]:
                    latest[env] = GradingEnvironment(id, **img_data)
        return latest

    def get_host_ip(self, image):
        """
        Get the external IP of the host of the docker daemon. Uses OpenDNS internally.
        :param image: any container image that has curl
        """
        try:
            container = self._docker.containers.create(image, command="curl -s https://icanhazip.com")
            container.start()
            response = container.wait()
            assert response["StatusCode"] == 0 if isinstance(response, dict) else response == 0
            answer = container.logs(stdout=True, stderr=False).decode('utf8').strip()
            container.remove(v=True, link=False, force=True)
            return answer
        except:
            return None

    def create_container(self, image, network_grading, debugger, mem_limit, task_path, sockets_path,
                         course_common_path, course_common_student_path, fd_limit, ports=None):
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

        cgroups1_params = {
            "mem_swappiness": 0, "oom_kill_disable": True
        } if self.get_cgroup_version() == "1" else {}

        response = self._docker.containers.create(
            image,
            stdin_open=True,
            mem_limit=str(mem_limit) + "M",
            memswap_limit=str(mem_limit) + "M",
            network_mode=("bridge" if (network_grading or len(ports) > 0) else 'none'),
            ports=ports,
            extra_hosts={"host.docker.internal": "host-gateway"},
            environment={"DEBUGGER" : debugger},
            volumes={
                task_path: {'bind': '/task', 'mode': 'Z'},
                sockets_path: {'bind': '/sockets', 'mode': 'Z'},
                course_common_path: {'bind': '/course/common', 'mode': 'ro,Z'},
                course_common_student_path: {'bind': '/course/common/student', 'mode': 'ro,Z'}
            },
            ulimits=[nofile_limit],
            security_opt=self._get_security_opts(sockets_path),
            **cgroups1_params
        )
        return response.id

    def create_container_student(self, image: str, mem_limit, student_path,
                                 sockets_path, socket_id, systemfiles_path, course_common_student_path,
                                 fd_limit, share_network_of_container: str=None, ports=None):
        """
        Creates a student container
        :param fd_limit:Tuple with soft and hard limits per slot for FS
        :param image: env to start (name/id of a docker image)
        :param mem_limit: in MB
        :param student_path: path to the task directory that will be mounted in the container
        :param sockets_path: path to the parent container sockets
        :param socket_id: id of the socket that will be mounted in the container
        :param systemfiles_path: path to the systemfiles folder containing files that can override partially some defined system files
        :param course_common_student_path:
        :param share_network_of_container: (deprecated) if a container id is given, the new container will share its
                                           network stack.
        :param ports: dictionary in the form {docker_port: external_port}
        :return: the container id
        """
        student_path = os.path.abspath(student_path)
        parent_socket_path = os.path.abspath(os.path.join(sockets_path, str(socket_id) + ".sock"))
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

        cgroups1_params = {
            "mem_swappiness": 0, "oom_kill_disable": True
        } if self.get_cgroup_version() == "1" else {}

        response = self._docker.containers.create(
            image,
            stdin_open=True,
            command="_run_student_intern",
            mem_limit=str(mem_limit) + "M",
            memswap_limit=str(mem_limit) + "M",
            network_mode=net_mode,
            ports=ports,
            volumes={
                student_path: {'bind': '/task/student', 'mode': 'Z'},
                secured_scripts_path: {'bind': '/task/student/scripts', 'mode': 'Z'},
                parent_socket_path: {'bind': '/__parent.sock', 'mode': 'Z'},
                systemfiles_path: {'bind': '/task/systemfiles', 'mode': 'ro,Z'},
                course_common_student_path: {'bind': '/course/common/student', 'mode': 'ro,Z'}
            },
            ulimits=[nofile_limit],
            security_opt=self._get_security_opts(sockets_path),
            **cgroups1_params
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

    def was_oom_killed(self, container_id):
        """
        :param container_id:
        :return: True if the container was killed by the OOM killer, False otherwise
        """
        return self._docker.containers.get(container_id).attrs['State'].get('OOMKilled', False)

    def event_stream(self, filters=None, since=None):
        """
        :param filters: filters to apply on messages. See docker api.
        :param since: time since when the events should be sent. See docker api.
        :return: an iterable that contains events from docker. See the docker api for content.
        """
        if filters is None:
            filters = {}
        return self._docker.events(decode=True, filters=filters, since=since)

    def _get_security_opts(self, seed: str) -> str:
        """
        :return: SELinux MCS label based on the given seed
        """
        c1, c2 = random.Random(seed).sample(range(1024), 2)
        return [f"label=level:s0:c{c1},c{c2}"]

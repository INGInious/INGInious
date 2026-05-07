# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from typing import Dict, Type, Tuple, Union, Any, List, Optional

import msgpack
from dataclasses import dataclass, is_dataclass, asdict

BackendJobId = str
ClientJobId = str
SPResult = Tuple[
    str, str
]  # JobId of the backend, composed with the address of the client and the client job id
_registered_messages: Dict[str, Type[Any]] = {}


#################################################################
#                                                               #
#                      Client to Backend                        #
#                                                               #
#################################################################


@dataclass(frozen=True)
class ClientHello:
    """Let the client say hello to the backend (and thus register to some events)"""

    name: str  # name of the client (do not need to be unique)


@dataclass(frozen=True)
class ClientNewJob:
    """Creates a new job"""

    job_id: ClientJobId  # the client-side job id that is associated to this job
    priority: int  # the job priority
    course_id: str  # course id of the task to run
    task_id: str  # task id of the task to run
    task_problems: Dict[str, Any]  # task dictionary
    inputdata: Dict[str, Any]  # student input data
    environment_type: str  # environment type
    environment: str  # environment to use (must exist in the environment type)
    environment_parameters: Dict[
        str, Any
    ]  # parameters for the environment (timeouts, limits, ...)
    debug: Union[
        str, bool
    ]  # True to enable debug, False to disable it, "ssh" to enable ssh debug
    launcher: str  # the name of the entity that launched this job, for logging purposes


@dataclass(frozen=True)
class ClientKillJob:
    """Kills a running job."""

    job_id: ClientJobId  # the client-side job id that is associated to the job to kill


@dataclass(frozen=True)
class ClientGetQueue:
    """Ask the backend to send the status of its job queue"""


#################################################################
#                                                               #
#                      Backend to Client                        #
#                                                               #
#################################################################


@dataclass(frozen=True)
class BackendUpdateEnvironments:
    """Update the information about the environments on the client, from the informations retrieved from the agents"""

    available_environments: Dict[
        str, List[str]
    ]  # dict of available environment aliases (as keys) and type of the related agent (as value)


@dataclass(frozen=True)
class BackendJobStarted:
    """Indicates to the backend that a job started"""

    job_id: ClientJobId  # the client-side job_id associated to the job


@dataclass(frozen=True)
class BackendJobDone:
    """Gives the result of a job."""

    job_id: ClientJobId  # the client-side job id associated with this job
    result: SPResult  # A tuple containing the result type and the text to be shown to the student
    # Result type can be:
    #     - "killed": the environment was killed externally (not really an error)
    #     - "crash": the environment crashed (INGInious error)
    #     - "overflow": the environment was killed due to a memory overflow (student/task writer error)
    #     - "timeout": the environment was killed due to a timeout (student/task writer error)
    #     - "success": the student succeeded to resolve this task
    #     - "failed": the student failed to succeed this task
    #     - "error": an error happenned in the grading script (task writer error)
    grade: float
    problems: Dict[
        str, SPResult
    ]  # particular feedbacks for each subproblem. Keys are subproblem ids.
    tests: Dict[str, Any]  # tests made in the environment
    custom: Dict[str, Any]  # custom values
    state: str
    archive: Optional[
        bytes
    ]  # bytes string containing an archive of the content of the environment as a tgz
    stdout: Optional[str]  # environment stdout
    stderr: Optional[str]  # environment stderr


@dataclass(frozen=True)
class BackendJobSSHDebug:
    """Gives the necessary info to SSH into a job running in ssh debug mode"""

    job_id: ClientJobId  # the client-side job id associated with this job
    host: str  # host to which the client should connect
    port: int  # port on which sshd is bound
    user: str  # user the client should use
    password: str  # password that allows to connect to the environment


@dataclass(frozen=True)
class BackendGetQueue:
    """
    Send the status of the job queue to the client. Attributes:

    - ``jobs_running`` : a list of tuples in the form
      (job_id, is_current_client_job, info, launcher, started_at, max_tuime)
      where:

        - job_id is a job id. It may be from another client.
        - is_current_client_job is a boolean indicating if the client that asked the request has started the job
        - agent_name is the agent name
        - info is "courseid/taskid"
        - launcher is the name of the launcher, which may be anything
        - started_at the time (in seconds since UNIX epoch) at which the job started
        - max_time the maximum time that can be used, or -1 if no timeout is set

    - ``jobs_waiting`` : a list of tuples in the form
      (job_id, is_current_client_job, info, launcher, max_time)
      where:

        - job_id is a job id. It may be from another client.
        - is_current_client_job is a boolean indicating if the client that asked the request has started the job
        - info is "courseid/taskid"
        - launcher is the name of the launcher, which may be anything
        - max_time the maximum time that can be used, or -1 if no timeout is set

    """

    jobs_running: List[Tuple[ClientJobId, bool, str, str, str, int, int]]
    jobs_waiting: List[Tuple[ClientJobId, bool, str, str, int]]


#################################################################
#                                                               #
#                      Backend to Agent                         #
#                                                               #
#################################################################


@dataclass(frozen=True)
class BackendNewJob:
    """Creates a new job"""

    job_id: BackendJobId  # the backend-side job id that is associated to this job
    course_id: str  # course id of the task to run
    task_id: str  # task id of the task to run
    task_problems: Dict[str, Any]  # task dictionary
    inputdata: Dict[str, Any]  # student input data
    environment_type: str  # environment type
    environment: str  # environment to use (must exist within the environment type)
    environment_parameters: Dict[
        str, Any
    ]  # parameters for the environment (timeouts, limits, ...)
    debug: Union[
        str, bool
    ]  # debug: True to enable debug, False to disable it, "ssh" to enable ssh debug


@dataclass(frozen=True)
class BackendKillJob:
    """Kills a running job."""

    job_id: (
        BackendJobId  # the backend-side job id that is associated to the job to kill
    )
    state: str  # submission state in case the job is lost at the agent


#################################################################
#                                                               #
#                      Agent to Backend                         #
#                                                               #
#################################################################


@dataclass(frozen=True)
class AgentHello:
    """Let the agent say hello and announce which environments it has available"""

    friendly_name: str  # a string containing a friendly name to identify agent
    available_job_slots: int  # an integer giving the number of concurrent
    available_environments: Dict[
        str, Dict[str, Dict[str, Any]]
    ]  # dict of available environments:
    # {
    #     "type": {
    #         "name": {                 #  for example, "default"
    #             "id": "env img id",   # "sha256:715c5cb5575cdb2641956e42af4a53e69edf763ce701006b2c6e0f4f39b68dd3"
    #             "created": 12345678,  # create date
    #             "ports": [22, 434],   # list of ports needed
    #         }
    #     }
    # }


@dataclass(frozen=True)
class AgentJobStarted:
    """Indicates to the backend that a job started"""

    job_id: BackendJobId  # the backend-side job_id associated to the job


@dataclass(frozen=True)
class AgentJobDone:
    """Gives the result of a job."""

    job_id: BackendJobId  # the backend-side job id associated with this job
    result: SPResult  # a tuple that contains the result itself, either:
    # - "killed": the environment was killed externally (not really an error)
    # - "crash": the environment crashed (INGInious error)
    # - "overflow": the environment was killed due to a memory overflow (student/task writer error)
    # - "timeout": the environment was killed due to a timeout (student/task writer error)
    # - "success": the student succeeded to resolve this task
    # - "failed": the student failed to succeed this task
    # - "error": an error happenned in the grading script (task writer error)
    # and the feedback text.
    grade: float  # grade
    problems: Dict[
        str, SPResult
    ]  # particular feedbacks for each subproblem. Keys are subproblem ids
    tests: Dict[str, Any]  # tests made in the environment
    custom: Dict[str, Any]  # custom values
    state: str
    archive: Optional[
        bytes
    ]  # bytes string containing an archive of the content of the environment as a tgz
    stdout: Optional[str]  # environment stdout
    stderr: Optional[str]  # environment stderr


@dataclass(frozen=True)
class AgentJobSSHDebug:
    """Gives the necessary info to SSH into a job running in ssh debug mode"""

    job_id: BackendJobId  # the backend-side job id associated with this job
    host: str  # host to which the client should connect
    port: int  # port on which sshd is bound
    user: str  # user the client should use
    password: str  # password that allows to connect to the environment


#################################################################
#                                                               #
#                           Heartbeat                           #
#                                                               #
#################################################################


@dataclass(frozen=True)
class Ping:
    """Ping message"""


@dataclass(frozen=True)
class Pong:
    """Pong message"""


@dataclass(frozen=True)
class Unknown:
    """Unknown message. Sent by a server that do not know a specific client; probably because the server restarted"""


#################################################################
#                                                               #
#                      Utility functions                        #
#                                                               #
#################################################################


def register_message(tcls: Type[Any]):
    """Register a new type of message"""
    _registered_messages[tcls.__name__] = tcls


# Add automatically all the dataclasses in this file, for simplicity
for cls in list(globals().values()):
    if is_dataclass(cls):
        register_message(cls)


def load(bmessage: bytes) -> Any:
    """
    From a bytestring given by a (distant) call to dump(), retrieve the original message
    :param bmessage: bytestring given by a dump() call on a message
    :return: the original message
    """
    message_dict = msgpack.loads(bmessage, use_list=False, strict_map_key=False)

    message_type = message_dict["@type"]
    del message_dict["@type"]

    try:
        cls = _registered_messages[message_type]
    except:
        raise TypeError("Unknown message type") from None

    try:
        obj = cls(**message_dict)
    except:
        raise TypeError("Invalid message content") from None

    return obj


def dump(msg: Any) -> bytes:
    """
    :return: a bytestring containing a black-box representation of the message, that can be loaded using messages.load.
    """
    d = asdict(msg)
    d["@type"] = msg.__class__.__name__
    return msgpack.dumps(d, use_bin_type=True)


class ZMQUtils(object):
    """
    Utilities that do serializing/unserializing of messages (whose metaclass is MessageMeta)
    """

    @classmethod
    async def recv_with_addr(cls, socket):
        message = await socket.recv_multipart()
        addr = message[0]
        obj = load(message[1])
        return addr, obj

    @classmethod
    async def send_with_addr(cls, socket, addr: bytes, obj):
        message = [addr, dump(obj)]
        await socket.send_multipart(message)

    @classmethod
    async def recv(cls, socket, skip_first=False):
        message = await socket.recv_multipart()
        return load(message[0] if not skip_first else message[1])

    @classmethod
    async def send(cls, socket, obj, send_white=False):
        message_obj = dump(obj)
        await socket.send_multipart(
            [message_obj] if not send_white else ["", message_obj]
        )


def run_tests():
    print("----------------- Verify basic instantiation")
    obj = ClientHello("test")
    print(obj.name)
    assert obj.name == "test"
    print()

    print("----------------- Dump test")
    obj2_dump = dump(obj)  # pylint: disable=no-member
    print(obj2_dump)
    print()

    print("----------------- Load test")
    obj3 = load(obj2_dump)
    print(type(obj3))
    assert type(obj3) == ClientHello
    print(obj3.name)
    assert obj3.name == "test"
    print()

    print("----------------- Assignation test")
    ok = True
    try:
        obj3.x = "a"
        ok = False
    except:
        pass
    if not ok:
        raise Exception("Should never happen")

    print("---------------- Invalid fields")
    ok = True
    try:
        load(msgpack.dumps({"@type": "ClientHello", "lol": "lol"}))
        ok = False
    except:
        pass
    if not ok:
        raise Exception("Should never happen")

    print("---------------- Invalid type")
    ok = True
    try:
        load(msgpack.dumps({"@type": "ClientHell", "name": "test"}))
        ok = False
    except:
        pass
    if not ok:
        raise Exception("Should never happen")

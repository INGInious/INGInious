from dataclasses import dataclass, asdict, field
from enum import IntEnum

import msgpack

from inginious.agent.docker_agent.common import GradingStatus

# ==== Common types ====

class MsgType(IntEnum):
    AgentInitMsg = 1
    StudentRetVal = 2
    StudentStarted = 3
    StudentInit = 4
    GradingResult = 5
    StudentRun = 6
    StudentSsh = 7
    GradingError = 8

@dataclass(frozen=True)
class _MsgBase:
    type: MsgType = None

    def serialize(self) -> bytes:
        return msgpack.dumps(asdict(self), use_bin_type=True)

    def send(self, channel):
        # channel.send(self.serialize())
        msg = self.serialize()
        msg_len = len(msg).to_bytes(4, 'big')
        channel.write(msg_len + msg)

    def is_student(self) -> bool:
        return self.type == MsgType.StudentInit or self.type == MsgType.StudentRetVal or self.type == MsgType.StudentStarted or self.type == MsgType.StudentRun

    @staticmethod
    def from_dict(o: dict):
        if (msg_type := o.get('type')) is not None:
            if msg_type == MsgType.AgentInitMsg:
                return AgentInitGrading(**o)
            elif msg_type == MsgType.StudentRetVal:
                return StudentRetVal(**o)
            elif msg_type == MsgType.StudentStarted:
                return StudentStarted(**o)
            elif msg_type == MsgType.StudentInit:
                return StudentInit(**o)
            elif msg_type == MsgType.GradingResult:
                return GradingResult(**o)
            elif msg_type == MsgType.StudentRun:
                return StudentRun(**o)
            elif msg_type == MsgType.GradingError:
                return GradingError(**o)
            else:
                raise ValueError
        else:
            raise KeyError

    @staticmethod
    def deserialize(o: bytes):
        o = msgpack.loads(o)
        if not isinstance(o, dict):
            raise TypeError
        return _MsgBase.from_dict(o)


# ==== Agent messages ====

@dataclass(frozen=True)
class _AgentInitGrading:
    input: dict
    envtypes: dict
    run_cmd: str
    run_as_root: bool = False
    shared_kernel: bool = True
    debug: bool = False

@dataclass(frozen=True)
class AgentInitGrading(_MsgBase, _AgentInitGrading):
    def __post_init__(self):
        object.__setattr__(self, 'type', MsgType.AgentInitMsg)


# ==== Grading container messages ====

@dataclass(frozen=True)
class _GradingResult:
    status: GradingStatus
    text: str
    problems: dict = field(default_factory=dict)
    tests: dict = field(default_factory=dict)
    stdout: str = None
    stderr: str = None
    archive: bytes = None

@dataclass(frozen=True)
class GradingResult(_MsgBase, _GradingResult):
    def __post_init__(self):
        object.__setattr__(self, 'type', MsgType.GradingResult)

@dataclass(frozen=True)
class _GradingError:
    text: str

@dataclass(frozen=True)
class GradingError(_MsgBase, _GradingError):
    def __post_init__(self):
        object.__setattr__(self, 'type', MsgType.GradingError)

# ==== Student container messages ====

@dataclass(frozen=True)
class _StudentBase:
    socket_id: int

@dataclass(frozen=True)
class _StudentRetVal:
    retval: int

@dataclass(frozen=True)
class StudentRetVal(_MsgBase, _StudentBase, _StudentRetVal):
    def __post_init__(self):
        object.__setattr__(self, 'type', MsgType.StudentRetVal)

@dataclass(frozen=True)
class _StudentStarted:
    container_id: int

@dataclass(frozen=True)
class StudentStarted(_MsgBase, _StudentBase, _StudentStarted):
    def __post_init__(self):
        object.__setattr__(self, 'type', MsgType.StudentStarted)

@dataclass(frozen=True)
class _StudentInit:
    command: str
    teardown_script: str
    student_container_id: int
    working_dir: str
    ssh: bool
    user: str

@dataclass(frozen=True)
class StudentInit(_MsgBase, _StudentBase, _StudentInit):
    def __post_init__(self):
        object.__setattr__(self, 'type', MsgType.StudentInit)

@dataclass(frozen=True)
class _StudentRun:
    environment: str
    time_limit: int
    hard_time_limit: int
    memory_limit: int
    token: bytes

@dataclass(frozen=True)
class _StudentRunDefaults:
    share_network: bool = False
    ssh: bool = False
    run_as_root: bool = False

@dataclass(frozen=True)
class StudentRun(_MsgBase, _StudentRunDefaults, _StudentBase, _StudentRun):
    def __post_init__(self):
        object.__setattr__(self, 'type', MsgType.StudentRun)

@dataclass(frozen=True)
class StudentSsh:
    ssh_user: str
    ssh_key: str
    container_id: int

    def __post_init__(self):
        object.__setattr__(self, 'type', MsgType.StudentSsh)

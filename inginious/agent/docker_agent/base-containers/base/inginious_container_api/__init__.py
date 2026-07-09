# coding=utf-8

from dataclasses import dataclass, asdict
from enum import IntEnum

import msgpack

from inginious.agent.docker_agent.messages import _MsgBase

DEBUG = False


class InternalMsgType(IntEnum):
    Done = 0
    ProxyToAgent = 1

@dataclass(frozen=True)
class _InternalMsgBase:
    type: InternalMsgType = None

    def serialize(self) -> bytes:
        return msgpack.dumps(asdict(self), use_bin_type=True)

    def send(self, channel):
        channel.send(self.serialize())

    @staticmethod
    def deserialize(raw: bytes):
        raw = msgpack.loads(raw)
        if not  isinstance(raw, dict):
            raise TypeError("Parsed bytes do not build a dict.")

        if (msg_type := raw.get('type')) is not None:
            if msg_type == InternalMsgType.Done:
                return InternalDone(**raw)
            elif msg_type == InternalMsgType.ProxyToAgent:
                return ProxyToAgent(**raw)
            else:
                raise ValueError(f'Unexpected msg type {msg_type}')
        else:
            raise KeyError('Msg type not found in parsed bytes.')

@dataclass(frozen=True)
class InternalDone(_InternalMsgBase):
    token: bytes = None

    def __post_init__(self):
        object.__setattr__(self, 'type', InternalMsgType.Done)

@dataclass(frozen=True)
class _ProxyToAgent:
    msg: _MsgBase

@dataclass(frozen=True)
class ProxyToAgent(_InternalMsgBase, _ProxyToAgent):
    def __post_init__(self):
        object.__setattr__(self, 'type', InternalMsgType.ProxyToAgent)

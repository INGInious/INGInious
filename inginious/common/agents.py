from dataclasses import dataclass, field
from enum import StrEnum
from abc import ABC

@dataclass(frozen=True)
class Capabilities(ABC):
    """ Agent capabilities. """
    doc: list = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'doc', {c: f.doc for c, f in self.__dataclass_fields__.items() if c != 'doc'})

class AgentType(StrEnum):
    OCI = 'docker'
    MCQ = 'mcq'

@dataclass(frozen=True)
class GradingEnvironment:
    """ Environment hash identifier """
    id: str
    """ Creation date in epoch """
    created: int
    """ List of requested ports """
    ports: list[int]
    """ Do not propagate the environment to the frontend """
    advertised: bool = True

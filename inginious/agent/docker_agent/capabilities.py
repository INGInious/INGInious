from dataclasses import dataclass, field
import os

from inginious.common.agents import Capabilities


@dataclass(frozen=True)
class DockerAgentCapabilities(Capabilities):

    """ Indicates whether the Agent supports GPUs. """
    gpu: bool = field(doc=_("The task requires a GPU."))
    """ Indicates whether the Agent supports running student code as root. """
    run_as_root: bool = field(doc=_("The task requires the student code to be ran as root. (EXPERIMENTAL)"))
    """ Indicates whether the Agent supports SSH proxying to student container. """
    ssh: bool = field(doc=_("The tasks requires providing access to the student container through SSH."))

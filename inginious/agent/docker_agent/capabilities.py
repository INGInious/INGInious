from dataclasses import dataclass, field
import gettext

from inginious.common.agents import Capabilities

_ = gettext.gettext

@dataclass(frozen=True)
class DockerAgentCapabilities(Capabilities):

    def __post_init__(self):
        object.__setattr__(self, '__translation_path__', 'agent/docker_agent/i18n')
        super().__post_init__()

    """ Indicates whether the Agent supports GPUs. """
    gpu: bool = field(doc=_("The task requires a GPU."))
    """ Indicates whether the Agent supports running student code as root. """
    run_as_root: bool = field(doc=_("The task requires the student code to be ran as root. (EXPERIMENTAL)"))
    """ Indicates whether the Agent supports SSH proxying to student container. """
    ssh: bool = field(doc=_("The tasks requires providing access to the student container through SSH."))

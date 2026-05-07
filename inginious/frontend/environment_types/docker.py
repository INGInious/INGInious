from inginious.frontend.environment_types.env_type import FrontendEnvType
from inginious.frontend.environment_types.generic_docker_oci_runtime import (
    GenericDockerOCIRuntime,
)


class DockerEnvType(GenericDockerOCIRuntime):
    @property
    def id(self):
        return "docker-ssh" if self._ssh_allowed else "docker"

    @property
    def name(self):
        return (
            _("Standard container + SSH")
            if self._ssh_allowed
            else _("Standard container")
        )

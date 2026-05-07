from inginious.frontend.environment_types.generic_docker_oci_runtime import (
    GenericDockerOCIRuntime,
)


class KataEnvType(GenericDockerOCIRuntime):
    @property
    def id(self):
        return "kata-ssh" if self._ssh_allowed else "kata"

    @property
    def name(self):
        return (
            _("Container running as root (Kata) + SSH")
            if self._ssh_allowed
            else _("Container running as root (Kata)")
        )

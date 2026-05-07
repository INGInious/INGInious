from inginious.frontend.environment_types.generic_docker_oci_runtime import (
    GenericDockerOCIRuntime,
)


class NvidiaEnvType(GenericDockerOCIRuntime):
    @property
    def id(self):
        return "nvidia-ssh" if self._ssh_allowed else "nvidia"

    @property
    def name(self):
        return (
            _("Container with GPUs (NVIDIA) + SSH")
            if self._ssh_allowed
            else _("Container with GPUs (NVIDIA)")
        )

# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from typing import NamedTuple


class DockerRuntime(NamedTuple):
    """
    Represents a runtime available in this Docker instance
    """

    runtime: str  # runtime name (as set in the configuration of Docker)
    run_as_root: bool  # indicates whether the runtime runs the container as root or not. Should always be False if shared_kernel is True
    enables_gpu: bool  # indicates whether the runtime enables the usage of GPU or not.
    shared_kernel: bool  # indicates whether the containers running on this runtime share the host kernel
    envtype: str  # environment type to be returned to the backend/client (for example, "docker" or "kata")
    # the envtype must be unique in the same DockerAgent.

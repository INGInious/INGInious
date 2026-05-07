import abc

from inginious.frontend.environment_types.docker import DockerEnvType
from inginious.frontend.environment_types.kata import KataEnvType
from inginious.frontend.environment_types.mcq import MCQEnvType
from inginious.frontend.environment_types.nvidia import NvidiaEnvType

__env_types = {}


def get_env_type(idx):
    """Return the FrontendEnvType with id idx. If this object does not exists, returns None."""
    return __env_types.get(idx, None)


def get_all_env_types():
    return __env_types


def register_env_type(env_obj):
    """env_obj is an instance of FrontendEnvType"""
    __env_types[env_obj.id] = env_obj


def register_base_env_types():
    # register standard env types here
    register_env_type(DockerEnvType())
    register_env_type(DockerEnvType(ssh_allowed=True))
    register_env_type(NvidiaEnvType())
    register_env_type(NvidiaEnvType(ssh_allowed=True))
    register_env_type(KataEnvType())
    register_env_type(KataEnvType(ssh_allowed=True))
    register_env_type(MCQEnvType())

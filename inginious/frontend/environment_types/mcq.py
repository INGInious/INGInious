from inginious.frontend.environment_types.env_type import FrontendEnvType


class MCQEnvType(FrontendEnvType):
    @property
    def id(self):
        return "mcq"

    @property
    def name(self):
        return _("Multiple Choice Question solver")

    def check_task_environment_parameters(self, data):
        return {}

    def studio_env_template(self, task):
        return ""

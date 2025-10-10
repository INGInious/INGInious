from abc import abstractmethod

from flask import render_template
from inginious.frontend.environment_types.env_type import FrontendEnvType


class GenericDockerOCIRuntime(FrontendEnvType):
    @property
    @abstractmethod
    def id(self):
        pass

    @property
    @abstractmethod
    def name(self):
        pass

    def check_task_environment_parameters(self, data):
        out = {}
        # Ensure that run_cmd is in the correct format
        if data.get('run_cmd', '') == '':
            out['run_cmd'] = None
        else:
            out['run_cmd'] = data['run_cmd']

        # Response is HTML
        out["response_is_html"] = data.get("response_is_html", False)

        # Network access in grading container?
        out["network_grading"] = data.get("network_grading", False)

        # Limits
        limits = {"time": 20, "memory": 1024, "disk": 1024}
        if "limits" in data:
            try:
                limits['time'] = int(data["limits"].get("time", 20))
                hard_time = data["limits"].get("hard_time", '')
                if str(hard_time).strip() == '':
                    hard_time = 3*limits['time']
                else:
                    hard_time = int(hard_time)
                limits['hard_time'] = hard_time
                limits['memory'] = int(data["limits"].get("memory", 1024))
                limits['disk'] = int(data["limits"].get("disk", 1024))

                if limits['time'] <= 0 or limits['hard_time'] <= 0 or limits['memory'] <= 0 or \
                        limits['disk'] <= 0:
                    raise Exception("Invalid limit")
            except:
                raise Exception("Invalid limit")
        out["limits"] = limits

        return out

    def studio_env_template(self, task, allow_html: bool):
        return render_template("course_admin/edit_tabs/env_generic_docker_oci.html", env_params=task.get("environment_parameters", {}),
                                content_is_html=allow_html, env_id=self.id)

    def __init__(self, ssh_allowed=False):
        self._ssh_allowed = ssh_allowed
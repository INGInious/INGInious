import abc


class FrontendEnvType(abc.ABC):
    """ Gives all the needed info to load and edit tasks in the frontend for a specific type of environment """
    @property
    @abc.abstractmethod
    def id(self):
        """ The id of the env type, as returned by the corresponding agent """
        pass

    @property
    @abc.abstractmethod
    def name(self):
        """ A human-readable, translated name """
        pass

    @abc.abstractmethod
    def check_task_environment_parameters(self, data):
        """ Given the parameters stored somewhere, as a dict, returns the parameters cleaned up and verified.
            This function should raise Exception if something is wrong with the input.
        """
        pass

    @abc.abstractmethod
    def studio_env_template(self, task, allow_html: bool):
        """ Return the HTML to be displayed inside the studio "environment" tab """
        pass
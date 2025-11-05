How to extend INGInious
=======================

Creating a new frontend
-----------------------

INGInious is mainly a backend that is agnostic. It can be used to run nearly everything.
The backend's code is in :ref:`backend`. You must use these classes to run new jobs.

The common module contains classes that are intended to be inherited by new "frontends".
The frontend given with INGInious is in fact an (big) extension of the common module.
You can use it as an example on how to extend INGInious.

Creating a new agent/environment type
-------------------------------------

An agent receives `submissions` and grades them. For this, it must implement the class `Agent`.

You will probably want to start from the very simple `MCQAgent` and extend from that.

Your agent may need some parameters to run correctly, these parameters depending from task to task.
INGInious sends, inside each submission, a dictionnary called `environment_parameters`. This dictionnary is filled
as the frontend wants it to be filled, so you must add some behavior into the frontend for it to send what you want.

In the webapp, this can be done by extending the class `inginious.frontend.environment_types.env_type.FrontendEnvType`,
and registering this new class using a call to the hook `register_env_type(env_obj)`.

Special environment parameters
------------------------------

INGInious as a whole (i.e. both the "backend" and the webapp) look for specific environment parameters. They are
not mandatory.

``limits[time]``

    An **expected** timeout in seconds. Allows INGInious to predict the size of the queue, and maybe other things in the
    future. Any value above (>=) 0 is taken into account. Any value below (<) will be displayed as "unknown".
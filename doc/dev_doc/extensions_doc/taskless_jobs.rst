Taskless jobs
=======

INGInious can handle taskless jobs. That means jobs that are not linked to a task or course.
They can be used to run background jobs without needing to create a course.
You can run a taskless job by using the `new_job()` method from the `Client` or `ClientSync` class, depending on if you
want to run the job asynchronously or synchronously (see :ref:`inginious.client.client` and :ref:`inginious.client.client_sync`
for usage). You can create and provide any environment based on the base environment.

^^^^^^^^^^^
Hello World
^^^^^^^^^^^

Here is an example of a taskless job running a simple Hello World script and returning it as feedback. You can use the `job_input`
to provide any data you want to provide to the job. You can then retrieve it with the get_input INGInious API. The environment,
as any other grading environment is based on the INGInious base environment.

""""""
Dockerfile
""""""

.. code-block:: Dockerfile

    ARG   VERSION=latest
    ARG   REGISTRY=ghcr.io
    FROM  ${REGISTRY}/inginious/env-base:${VERSION}

    LABEL org.opencontainers.image.description="Demo environment for taskless jobs. This envionment only returns a Hello World message."
    LABEL org.inginious.grading.name="taskless-hello_world"


    # clean and update
    RUN dnf clean metadata && \
        dnf -y upgrade

    # copy runfile to the course directory
    COPY run.py /course/run.py

""""""
run.py
""""""

.. code-block:: python

    from inginious_container_api import feedback, input

    message = "Hello World!"
    additional_message = input.get_input("hello_world_message")

    feedback.set_global_feedback(message + " " + additional_message)
    feedback.set_global_result("success")

"""""""""""""""
Running the job
"""""""""""""""

.. code-block:: python

    job_info = { "environment_type": "docker", "environment": "taskless-hello-world" }
    job_input = {
                "hello_world_message": "My name is John Doe and I am a software engineer."
            }

    ... = client_sync.new_job(0, job_info=job_info, inputdata=job_input, launcher_name="Plugin - taskless Hello World", debug=True)


^^^^^^^^^^^^^^^^^
Unreachable paths
^^^^^^^^^^^^^^^^^

**Please be advised** : The `/task` and `/course/common` paths are mounted during the container's creation. Therefore, any
runfile or ressource you put in these paths in your job's Docker image won't be accessible.
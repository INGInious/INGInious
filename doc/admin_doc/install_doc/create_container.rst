

Creating a new container image
==============================

Creating the Dockerfile
-----------------------

Container images can be viewed as small operating systems with specific software and configuration.
The main force of the container images is that they are very simple to create and modify, using Dockerfiles.

Here is an example of Dockerfile:

::

   # DOCKER-VERSION 1.1.0

   # Inherit from the default container, which have all the needed script to launch tasks
   FROM    ghcr.io/inginious/env-base

   # Set the environment name for tasks
   LABEL   org.inginious.grading.name="php"

   # Add php
   RUN     yum -y install php-cli

   # Add the php interpreter as run file interpreter (to allow run.php files)
   RUN echo 'run_types["php"] = "/bin/php"' >> /usr/lib/python3.6/site-packages/inginious_container_api/run_types.py

As easily seen, this Dockerfile creates a new container image that can launch PHP scripts.
The syntax of these Dockerfiles is extensively described on the website of Docker_,
but we will detail here the most important things to know.

Each Dockerfile used on INGInious should begin with ```FROM ghcr.io/inginious/env-base``` and
```LABEL org.inginious.grading.name="some_name"```. The first line indicates that you take as base for your new image
the default image provided with INGInious. This default image is itself based on CentOS 7, and uses *yum* (*rpm*)
as package manager. It is already provided with Python and basic commands, and with all the files needed by INGInious
to work. The second line is used to indicate the environment name (here, ```some_name```) that will be used for tasks.

The line ```RUN yum -y install php-cli``` indicates to Docker that it must run the command ```yum -y install php-cli```
inside the image. The ```yum``` command is the equivalent of ```apt-get``` (that is the package manager for Debian,
Ubuntu and derivates), but for Linux distributions that derivates from Fedora, like CentOS. This will install the package
```php-cli```. Creating new containers mainly consists on adding new packages to the *default* container, so it is
probable that your Dockerfile will contain mostly this type of lines.

Here is a little more advanced Dockerfile, that is used to provide Mozart/Oz in INGInious:

::

    FROM    ghcr.io/inginious/env-base
    LABEL   org.inginious.grading.name="oz"

    ADD mozart2.rpm /mozart.rpm
    RUN yum -y install emacs tcl tk
    RUN rpm -ivh /mozart.rpm
    RUN rm /mozart.rpm

Again, it inherits from ```ghcr.io/inginious/env-base``` and the environment name is set to ```oz```. Then, it
uses the command ```ADD```, that takes a file in the current directory of the Dockerfile (here, ```mozart2.rpm```)
and copy it inside the container image, here at the path ```/mozart.rpm```. It then uses three ```RUN``` commands to
install the dependencies of Mozart, then install Mozart itself, and then removing the now uneeded rpm.

Dockerfiles can do many more things, read the documentation on the Docker website to know more about the possibilities.


.. _new_container:

Compiling the Dockerfile
--------------------------

Once you have Docker up and running, it is very simple to create a container image from a Dockerfile:

::

    $ cd /path/to/your/dockerfile
    $ docker build -t my_container_image ./

Docker will then launch a container and run the Dockerfile on it, then will save the state of the disk, that is,
in fact, the container image. INGInious will automatically detect the environment based on the labels you've set in the
Dockerfile. Therefore, the tag ```my_container_image``` can be set to any value. As a convention, we adopted
```inginious-c-XXX```.

For the new environment to be available, you have to restart INGInious (or, at least, the Docker agent if you are running
INGInious components on separate machines). More details here: https://inginious.org/course/tutorial/12_environments

You can also enter directly in the container image to test it in the command line:

::

    $ docker run -t -i --rm my_container_image /bin/bash


It is also easy to rebuild the initially provided containers images.
If you have a proper INGInious version installed, no need for building images, you can re-download the provided images by simply running:
::

    $ inginious-container-update

If you are running on a dev environment (cloned from the repository), from the main directory, enter the following commands to take into consideration your local files:
::

    $ cd base-containers/base
    $ docker build -t ghcr.io/inginious/env-base ./
    $ cd ../default
    $ docker build -t ghcr.io/inginious/env-default ./

Note, this manual building step should not be necessary for a teacher.
Of course, if you rebuilt your images, you will have to restart inginious-webapp.

Leveraging other runtimes
-------------------------

INGInious relies on the Docker API to run containers. Docker default OCI runtime is *runc* and will typically meet
all your needs. However, you may want, for very specific tasks, leverage some features that are not supported by
*runc*. This is, for instance, the case of rooted containers, so that the student can perform root operations, or
the case of GPU-enabled containers.

INGInious currently supports the following OCI runtimes : *runc*, *crun*, *kata-runtime v1.x*, *nvidia-container*.

crun
````
`crun <https://github.com/containers/crun>`_ is a *runc*-like runtime but implemented in C instead of Go.
It generally provides you with better performance.

To activate *crun*, download the prebuilt binary from the project page and put it or symlink it to `/usr/bin/crun`.
Then, modify your ``/etc/docker/daemon.json`` file in order to add *crun* as a runtime, and set it as `default-runtime`
to make INGInious use it by default.

::

 {
    "default-runtime": "crun",
    "runtimes": {
        "crun": {
            "path": "/usr/bin/crun"
        }
    }
 }

Restart Docker and your INGInious agent.

Kata
````
`Kata <https://github.com/kata-containers/runtime>`_ actually runs lightweight virtual machines instead of containers,
to provide isolation and security advantages of VMs.

INGInious allows you to start rooted containers using Kata runtime. This allows you to provide root SSH access to the
students to make them perform administrator operations. The `run_student` container architecture protects your grading
files as only the `/task/student` folder is R/W in the student container.

To activate *kata*, download the prebuilt binaries from the project page or install the runtime from the appropriate
distribution repositories. Then, modify your ``/etc/docker/daemon.json`` file in order to add *kata-runtime* as a runtime.

::

 {
    "runtimes": {
        "kata-runtime": {
            "path": "/usr/bin/kata-runtime"
        }
    }
 }

Restart Docker and your INGInious agent. You will be able to run rooted containers by selecting *Kata* as the task
environment type. To restrict container availability to *Kata*, add the following label to your `Dockerfile`:

::

  LABEL org.inginious.grading.need_root=1

NVIDIA
``````

The `NVIDIA <https://github.com/NVIDIA/nvidia-container-runtime>`_ runtime is built upon *runc* and allows you to leverage
the host GPUs inside containers by exposing the device inside the container filesystem. It can be useful in case
you want to perform CUDA-powered computations or generating graphics, ...

To activate *nvidia* as runtime, you need to :

#. Install the nvidia driver and cuda toolkit. Repositories and instructions are provided on the
   `NVIDIA website <https://developer.nvidia.com/cuda-downloads>`_.
#. Install the cuda-container-toolkit. Repositories and instructions are provided in the
   `NVIDIA install guide <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html>`_.

Then, modify your ``/etc/docker/daemon.json`` file in order to add *nvidia* as a runtime.

::

 {
    "runtimes": {
        "nvidia": {
            "path": "/usr/bin/nvidia-container-runtime"
        }
    }
 }

Restart Docker and your INGInious agent. You will be able to run GPU-enabled containers by selecting *NVIDIA* as the task
environment type.

.. WARNING::

    To expose the GPU inside the container, the NVIDIA runtime still requires you to set the following environment variables in your ``Dockerfile``:
    ::

       ENV NVIDIA_VISIBLE_DEVICES all
       ENV NVIDIA_DRIVER_CAPABILITIES compute,utility

    Details on these environment variables are provided in the
    `NVIDIA user guide <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/user-guide.html>`_.
    You'll then need the appropriate libraries installed. You may probably want to base the INGInious containers on
    the ``nvidia/cuda:x.y.z-base-rockylinux8`` `CUDA container <https://gitlab.com/nvidia/container-images/cuda>`_.

To restrict container availability to *NVIDIA* (recommended), add the following label to your `Dockerfile`:

::

  LABEL org.inginious.grading.need_gpu=1

Share what you created
----------------------

If you created a Dockerfile for INGInious, feel free to make a pull request in the repository associated: https://github.com/INGInious/containers

.. _Docker: https://www.docker.com/

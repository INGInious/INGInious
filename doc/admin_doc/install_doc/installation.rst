Installation and deployment
===========================

Supported platforms
-------------------

INGInious runs Linux containers and is therefore intended to run on Linux.

You may be able to run it on other platforms supporting Linux containers, but no support is provided yet.
If you are willing to contribute this, feel free to contact us on Github.

Dependencies setup
------------------

INGInious needs:

- Python_ 3.10+
- Docker_ or Podman_
- MongoDB_

.. _Docker: https://www.docker.com
.. _Podman: https://podman.io/
.. _Python: https://www.python.org/
.. _MongoDB: http://www.mongodb.org/

RHEL/Rocky/Alma Linux 8+
````````````````````````

#. The previously mentioned dependencies can be installed:

   .. code-block:: bash

     # dnf install -y epel-release && crb enable
     # dnf install -y git gcc python3.12 python3.12-devel python3.12-pip dnf-plugins-core
     # dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
     # yum install -y docker-ce docker-ce-cli
     # cat <<EOF > /etc/yum.repos.d/mongodb-org-8.0.repo
     [mongodb-org-8.0]
     name=MongoDB Repository
     baseurl=https://repo.mongodb.org/yum/redhat/$releasever/mongodb-org/8.0/x86_64/
     gpgcheck=1
     enabled=1
     gpgkey=https://pgp.mongodb.com/server-8.0.asc
     EOF
     # dnf install -y mongodb-org mongodb-org-server

   You may also add ``xmlsec1-openssl-devel libtool-ltdl-devel`` for the SAML2 auth plugin.

#. You can now enable and start the ``mongod`` and ``docker`` services:
   ::

      # systemctl enable --now mongod docker

#. Check the cgroups version the container runtime is running on:
   ::
      # docker info | grep "Cgroup"
   If the cgroups version is ``2`` and cgroups driver is ``systemd``, apply the following systemd rule:
   ::
      # cat /etc/systemd/system/docker-.scope.d/99-inginious.conf
      [Scope]
      OOMPolicy=kill

Ubuntu 24.04+
`````````````

#. The previously mentioned dependencies can be installed:

   .. code-block:: bash

      $ sudo apt install git gcc python3-pip python3-dev python3-venv
      $ sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
      $ sudo chmod a+r /etc/apt/keyrings/docker.asc
      $ sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
      Types: deb
      URIs: https://download.docker.com/linux/ubuntu
      Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
      Components: stable
      Architectures: $(dpkg --print-architecture)
      Signed-By: /etc/apt/keyrings/docker.asc
      EOF
      $ sudo apt update
      $ sudo apt install docker-ce docker-ce-cli
      $ curl -fsSL https://pgp.mongodb.com/server-8.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
      $ echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
      $ sudo apt update
      $ sudo apt install mongodb-org

   You may also add ``libxmlsec1-dev libltdl-dev`` for the SAML2 auth plugin.

#. You can now enable and start the ``mongod`` and ``docker`` services:
   ::

      # systemctl enable --now mongod docker

#. Check the cgroups version the container runtime is running on:
   ::
      # docker info | grep "Cgroup"
   If the cgroups version is ``2`` and cgroups driver is ``systemd``, apply the following systemd rule:
   ::
      # cat /etc/systemd/system/docker-.scope.d/99-inginious.conf
      [Scope]
      OOMPolicy=kill

macOS
`````

.. WARNING::

    Documentation for macOS is outdated. Feel free to contribute.

We use brew_ to install some packages. Packages are certainly available too via macPorts.

.. _brew: http://brew.sh/

::

    $ brew tap mongodb/brew
    $ brew update
    $ brew install mongodb-community
    $ brew install python3

Follow the instruction of brew to enable mongodb.

The next step is to install `Docker for Mac <https://docs.docker.com/docker-for-mac/install/>`_.

.. _Installpip:

**Whatever the distribution, you should make docker available for non-root user:**

1. Run the ``groupadd`` command below to create a new group called ``docker``. Enter your password to continue running the command.

.. code-block:: bash

    sudo groupadd docker

If the ``docker`` group exists in the user group, you will get a message like "group already exists".

2. Next, run the ``usermod`` command below where the ``-aG`` options tell the command to add the INGInious running user ``<user>`` to the ``docker`` group.
This command causes your user account to have non-user access.

.. code-block:: bash

    sudo usermod -aG docker user

3. Run the ``newgrp`` command below to change the current real group ID to the ``docker`` group.

.. code-block:: bash

    sudo newgrp docker

Installing INGInious
--------------------

To keep a clean distribution, we recommend to work with a virtualenv:

.. code-block:: bash

    python3 -m venv /path/to/venv/INGInious
    source /path/to/venv/INGInious/bin/activate

The recommended setup is to install INGInious via pip from PyPI.
This allows you to use the latest supported version.
::

    $ pip install --upgrade pip
    $ pip install --upgrade inginious

This will automatically upgrade an existing version.

.. note::

   You may want to enable the LDAP/SAML2 plugin.
   In this case, you have to install more packages: simply add ``[ldap]`` or ``[saml2]`` to the above command, depending on your needs:

   ::

       $ pip install --upgrade inginious[saml2,ldap]

.. _config:

Configuring INGInious
---------------------

INGInious comes with a mini-LMS web app that provides statistics, group management, and the
INGInious studio, that allows to modify and test your tasks directly in your browser. It supports the LTI_ interface
that allows to interface with Learning Management System via the LTI_ specification. Any LMS supporting LTI_ is
compatible. This includes Moodle, edX, among many others.

.. _LTI: https://www.1edtech.org/standards/lti

It is recommended to create a folder for INGInious and subfolders for tasks and backup, e.g.:
::

    $ mkdir -p /var/www/inginious
    $ cd /var/www/inginious
    $ mkdir tasks
    $ mkdir backup

To configure the web app automatically, use the ``inginious-install`` CLI.

::

    $ inginious-install

This will help you create the configuration file in the current directory.
When asked about the tasks folder, enter an absolute folder: /var/www/inginious/tasks .
Similarly, when asked about the backup folder, enter an absolute folder: /var/www/inginious/backup .

For manual configuration and details, see
:ref:`ConfigReference`.
In particular, make sure to add smtp configuration into your `configuration.yaml` file, since INGInious must send email during new user registration.

The detailed ``inginious-install`` reference can be found at :ref:`inginious-install`.

Running INGInious
-----------------

During the configuration step, you were asked to setup either a local or remote backend. In the former case, the frontend
will automatically start a local backend and grading agents.
Additionally, if you intend to have many simultaneous submissions, it is highly recommended to use Gunicorn behind a webserver, such as lighttpd or Apache -- see below.

With local backend/agent -- no webserver
````````````````````````````````````````
To run the frontend, please use the ``inginious-webapp`` CLI. This will open a small Python
web server and display the url on which it is bind in the console. Some parameters (configuration file, host, port)
can be specified. Details are available at :ref:`inginious-webapp`.

With remote backend/agent -- no webserver
`````````````````````````````````````````
To run INGInious with a remote backend (and agents), do as follows:

#. On the backend host, launch the backend (see :ref:`inginious-backend`) :
   ::

        inginious-backend tcp://backend-host:2001 tcp://backend-host:2000

   The agents will connect on ``tcp://backend-host:2001`` and clients on ``tcp://backend-host:2000``
#. Possibly on different hosts, launch the Docker and MCQ agents (see :ref:`inginious-agent-docker`
   and :ref:`inginious-agent-mcq`) :
   ::

        inginious-agent-docker tcp://backend-host:2001
        inginious-agent-mcq tcp://backend-host:2001
#. In your INGInious frontend configuration file (see :ref:`ConfigReference`), set ``backend`` to :
   ::

        backend: tcp://backend-host:2000
#. Run the frontend using :ref:`inginious-webapp`.
   ::

         inginious-webapp --config /path/to/configuration.yaml

.. _production:

With local backend/agent and a webserver
````````````````````````````````````````

In production environments, `Gunicorn <https://gunicorn.org/>`_ serves the INGInious applications in replacement of the
built-in Python server, behind a webserver acting as a reverse proxy. The following guides suggest to expose the
INGInious webapp on http port and WebDAV on port 8080 on the same host.
You are free to adapt them to your use case (for instance, adding SSL support or using two hostnames).

Create a folder for INGInious, for example ``/var/www/INGInious``. Put your configuration file in that folder, as well
as your tasks, backup, download, and temporary (if local backend) directories (see :ref:`config` for more details on
these folders).

Install Gunicorn in the same Python environment as INGInious:
::

    # pip3 install gunicorn

Start the web app and, if needed, the WebDAV server, each on its own local port:
::

    $ export INGINIOUS_WEBAPP_CONFIG="/var/www/INGInious/configuration.yaml"
    $ gunicorn 'inginious.scripts.webapp:wsgi_app()' --bind 127.0.0.1:8000
    $ gunicorn 'inginious.scripts.webdav:wsgi_app()' --bind 127.0.0.1:8001 --workers 1

The user running these commands must own the INGInious folder, and be allowed to launch containers and to connect to
MongoDB.

.. WARNING::
    **If you use a local backend with remote Docker daemon**, you may need to set the ``DOCKER_HOST`` variable in the
    environment of Gunicorn. To know the value to set, start a terminal that has access to the docker daemon (the
    terminal should be able to run ``docker info``), and write ``echo $DOCKER_HOST``. If it returns nothing, just ignore
    this comment. It is possible that you may need to do the same for the env variable ``DOCKER_CERT_PATH`` and
    ``DOCKER_TLS_VERIFY`` too.

In some cases docker won't be able to run INGInious containers due to invalid temp directory just
make sure you append this in your INGInious configuration.yaml

  ::

   local-config:
       tmp_dir: /var/www/INGInious/agent_tmp

Static files are served by the web app through Gunicorn, the webserver only has to forward the requests.

.. _lighttpd:

Using lighttpd
``````````````

Add the following rules in a ``/etc/lighttpd/vhosts.d/inginious.conf`` file:
::

    server.modules += ( "mod_proxy" )

    $SERVER["socket"] == ":80" {
        proxy.server = ( "" => (( "host" => "127.0.0.1", "port" => 8000 )) )
    }

    $SERVER["socket"] == ":8080" {
        proxy.server = ( "" => (( "host" => "127.0.0.1", "port" => 8001 )) )
    }

Append this at the end of ``/etc/lighttpd/lighttpd.conf``:

  ::

   include "/etc/lighttpd/vhosts.d/inginious.conf"

Finally, start the server:

::

    # systemctl enable lighttpd
    # systemctl start lighttpd

.. _apache:

Using Apache
````````````

Enable the Apache proxy modules. On Ubuntu:
::

    # a2enmod proxy proxy_http

On RHEL-based distributions, ``mod_proxy`` and ``mod_proxy_http`` are provided by the ``httpd`` package.

Then, add the following virtual hosts to your Apache configuration, and listen on port 8080 if you use WebDAV:

  ::

    <VirtualHost *:80>
        ServerName my_inginious_domain
        ProxyPreserveHost On
        ProxyPass / http://127.0.0.1:8000/
        ProxyPassReverse / http://127.0.0.1:8000/
    </VirtualHost>

    <VirtualHost *:8080>
        ServerName my_inginious_domain
        ProxyPreserveHost On
        ProxyPass / http://127.0.0.1:8001/
        ProxyPassReverse / http://127.0.0.1:8001/
    </VirtualHost>

Finally, reload Apache and open the URL of your website in a browser.

Optional apps
=============

.. _webdav_setup:

WebDAV setup
------------

An optional WebDAV server can be used with INGInious to allow course administrators to access
their course filesystem. This is an additional app that needs to be launched on another port or hostname.
Run the WebDAV server using :ref:`inginious-webdav`.

  ::

    inginious-webdav --config /path/to/configuration.yaml --port 8000

In your configuration file (see :ref:`ConfigReference`), set ``webdav_host`` to:
  ::

    <protocol>://<hostname>:<port>

where ``protocol`` is either ``http`` or ``https``, ``hostname`` and ``port`` the hostname and port
where the WebDAV app is running.

.. _webterm_setup:

Webterm setup
-------------

An optional web terminal can be used with INGInious to load the remote SSH debug session. This rely on an external tool.

To install this tool :
::

    $ git clone https://github.com/INGInious/xterm
    $ cd xterm && npm install

You can then launch the tool by running:
::

    $ npm start bind_hostname bind_port debug_host:debug_ports

This will launch the app on ``http://bind_hostname:bind_port``. The ``debug_host`` and ``debug_ports`` parameters are
the debug paramaters on the local (see :ref:`ConfigReference`) or remote (see :ref:`inginious-agent-docker`) Docker agent.

To make the INGInious frontend aware of that application, update your configuration file by setting the ``webterm``
field to ``http://bind_hostname:bind_port`` (see :ref:`ConfigReference`).

For more information on this tool, please see `INGInious-xterm <https://github.com/INGInious/xterm>`_. Please
note that INGInious-xterm must be launched using SSL if the frontend is launched using SSL.

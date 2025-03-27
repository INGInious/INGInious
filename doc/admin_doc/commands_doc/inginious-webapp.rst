.. _inginious-webapp:

inginious-webapp
================

Start the Web App Frontend. This command can run a standalone web server (see ``--host`` and ``--port`` options) or as a FastCGI backend.

.. program:: inginious-webapp

::

    inginious-webapp [-h] [--config CONFIG] [--host HOST] [--port PORT]

.. option:: --config

   Specify the configuration file to use. By default, it is configuration.yaml or configuration.json, depending on which is found first.
   This can also be specified via the ``INGINIOUS_WEBAPP_CONFIG`` environment variable.

.. option:: --host HOST

   Specify the host to which to bind to. By default, it is localhost.
   This can also be specified via the ``INGINIOUS_WEBAPP_HOST`` environment variable.

.. option:: --port PORT

   Specify the port to which to bind to. By default, it is 8080.
   This can also be specified via the ``INGINIOUS_WEBAPP_PORT`` environment variable.

.. option:: -h, --help

   Display the help message.

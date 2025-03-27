.. _inginious-webdav:

inginious-webdav
================

Start the WebDAV frontend. This command can run a standalone web server (see ``--host`` and ``--port`` options), or as a FastCGI backend.

.. program:: inginious-webdav

::

    inginious-webdav [-h] [--config CONFIG] [--host HOST] [--port PORT]

.. option:: --config

   Specify the configuration file to use. By default, it is configuration.yaml or configuration.json, depending on which is found first.
   This can also be specified via the ``INGINIOUS_WEBAPP_CONFIG`` environment variable.

.. option:: --host HOST

   Specify the host to which to bind to. By default, it is localhost.
   This can also be specified via the ``INGINIOUS_WEBDAV_HOST`` environment variable.

.. option:: --port PORT

   Specify the port to which to bind to. By default, it is 8080.
   This can also be specified via the ``INGINIOUS_WEBDAV_PORT`` environment variable.

.. option:: -h, --help

   Display the help message.

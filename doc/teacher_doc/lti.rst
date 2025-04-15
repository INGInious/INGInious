.. _configure_LTI:

Using through LTI (edX, Moodle, ...)
=====================================

INGInious implements the LTI specification in order to integrate into edX, Moodle, or any other LMS that also implements
this specification. To get started, all you need is to activate the LTI mode in the course administration. You'll then be able to use INGInious tasks as activities in your LMS.


.. _LTI11: https://www.imsglobal.org/spec/lti/v1p1p2

Using LTI v1.1
``````````````

Setting up INGInious
--------------------

LTI 1.1 relies on a pair of consumer key and shared secret to make the LTI platform and tool communicate. For each
different platform you want to integrate INGInious with, a par of key and secret is needed.

In your INGInious course settings, activate LTI mode and then fill the *LTI 1.1 keys* with one or multiple pair of keys
and secrets, separated by a colon (``:``). For instance:
::

        consumer_key_1:a_very_secret_password
        consumer_key_2:wow_such_secret

This defines two LTI consumer keys, ``consumer_key_1`` and ``consumer_key_2``, with secrets ``a_very_secret_password`` and
``wow_such_secret``. You also need to check the *Send grades back* option to actually send the scores from INGInious to your LTI.

Setting up (Open) edX
---------------------

In your course *Advanced settings*, make that the `lti_consumer` module is present in the *Advanced module list*.

#. Look for the *Lti passports* field in the course *Advanced settings*. Add a new passport, consisting of the
   LTI consumer and secret defined before, by adding a entry to the list:
   ::

     passport_id:consumer_key:a_very_secret_password
   This ``passport_id`` can be set to any value and will only be used inside edX.
#. In your course outline, in the *Add New Component*, select *Advanced* and then *LTI Consumer*. A new LTI component
   is added to the component list. Click on *Edit*.
#. Set a *Display Name* and the *LTI version* to ``LTI 1.1/LTI 1.2``.
#. Set the *LTI ID* to the ``passport_id`` you've chosen before.
#. Set the *LTI URL* to:
   ::

     https://HOST:PORT/lti/course_id/task_id
#. Optionally, set the *Scored* option to ``True`` and click on *Save*.

The LTI component will then launch in the edX studio. Please note that user identifiers in the live version and
in the studio are not the same. You'll have to perform two LTI binding in INGInious.

Setting up Moodle
-----------------

Make sure the *External tool* (``mod_lti``) plugin is enabled. In case of doubt, ask your Moodle administrator.

In your course view, click on *More* and then *LTI External Tools*. Existing tools may be configured and listed here.
Click on *Add tool* below.

#. Set the *Tool name* to ``My INGInious task`` and the Tool URL to:
   ::

    https://HOST:PORT/lti/course_id/task_id

#. Set the *LTI version* to  ``LTI1.0/1.1``
#. Set the *Consumer key* and *Shared secret* to the values defined before.
#. Optionally, enable the *Accept grades from the tool* under the *Privacy* section and and save.

The tool added will be listed in the activities that can be added to the course.


Using LTI v1.3
``````````````

Generating a pair of keys
-------------------------

LTI 1.3 relies on RSA asymmetric ciphering for the communication between the platform and the tool.
A pair of private and public key is therefore needed before going further.

* If you're running on a Unix system, launch your terminal and type:
  ::

    openssl genrsa > private.pem
    openssl rsa -in private.pem -pubout -out public.pem
  This will generate a pair of RSA keys in files ``private.pem`` and ``public.pem`` with default ciphering options.
* If you're running on Windows, use PuTTYgen to generate such a pair in PEM format.

Setting up (Open) edX
---------------------

In your course *Advanced settings*, make that the `lti_consumer` module is present in the *Advanced module list*.

#. In your course outline, in the *Add New Component*, select *Advanced* and then *LTI Consumer*. A new LTI component
   is added to the component list. Click on *Edit*.
#. Set a *Display Name* and the *LTI version* to ``LTI 1.3``.
#. Set the *Tool Launch URL* to:
   ::

     https://HOST:PORT/lti1.3/launch/course_id/task_id
#. Set the *Registered Redirect URIs* to the single same value:
   ::

    ["https://HOST:PORT/lti1.3/launch/course_id/task_id"]
#. Set the *Tool Initiate Login URL* to:
   ::

    https://HOST:PORT/lti1.3/oidc_login/course_id
#. Choose the *Tool public key mode*.

   * If you choose *Public key (Default)*, copy/paste the whole key, including the header and footer.
   * If you choose *Keyset URL*, copy/paste the URL mentioned in your INGInious course settings page below the LTI1.3
     config field.

#. Optionally, activate or deactivate the *LTI Assignment and Grades Service* and then click on *Save*.

The component then updates and gives you the configuration to import into your INGInious LTI settings.

* Platform ID: ``https://courses.edx.org``
* Client ID: ``<activity_client_id>``
* Deployment ID: ``<activity_deployment_id>``
* Keyset URL: ``https://courses.edx.org/api/lti_consumer/v1/public_keysets/<keyset_id>``
* Access Token URL: ``https://courses.edx.org/api/lti_consumer/v1/token/<keyset_id>``
* Login URL: ``https://courses.edx.org/api/lti_consumer/v1/launch/``


Setting up Moodle
-----------------

Make sure the *External tool* (``mod_lti``) plugin is enabled. In case of doubt, ask your Moodle administrator.

In your course view, click on *More* and then *LTI External Tools*. Existing tools may be configured and listed here.
Click on *Add tool* below.

#. Set the *Tool name* to ``My INGInious task`` and the Tool URL to:
   ::

    https://HOST:PORT/lti1.3/launch/course_id/task_id

#. Set the *LTI version* to  ``LTI1.3``
#. Choose the way you want to share the public key.

   * If you choose *Keyset URL*, copy/paste the URL mentioned in your INGInious course settings page below the LTI1.3
     config field.
   * If you choose *RSA key*, copy/paste the whole key, including the header and footer.
#. Set the *Initial login URL* to:
   ::

    https://HOST:PORT/lti1.3/oidc_login/course_id
#. Set the *Redirection URI* to the same value as *Tool URL*.
#. Optionally, enable the *IMS LTI Assignment and Grade Services* under the *Services* section and save.

The tool added will be listed in the activities that can be added to the course.

In order to import the platform settings into our INGInious course, go to the *External tool* plugin
administration and click on *Manage tools*. You will see a list of tiles of configured tools.

In the tile named ``My INGInious task``, click on *View configurationd details*. Moodle will then provide you the
following information :

* Platform ID: ``<moodle_instance_url>``
* Client ID: ``<activity_client_id>``
* Deployment ID: ``<activity_deployment_id>``
* Public keyset URL: ``<moodle_instance_url>/mod/lti/certs.php``
* Access token URL: ``<moodle_instance_url>/mod/lti/token.php``
* Authentication request URL: ``<moodle_instance_url>/mod/lti/auth.php``

Setting up INGInious
--------------------

Once you have gathered all the information provided by the RSA keys and the platfor, update your *LTI 1.3* configuration
in your INGInious course settings. This is defined using the JSON format:

::

    {
      "<platform_id>: [
        {
          "auth_audience": null,
          "auth_login_url": "<plaform_auth_or_login_url>",
          "auth_token_url": "<platform_access_token_url>",
          "client_id": "<activity_client_id>",
          "default": true,
          "deployment_ids": [
            "<activity_deployment_id>"
          ],
          "key_set": null,
          "key_set_url": "<platform_keyset_url>",
          "private_key": "-----BEGIN RSA PRIVATE KEY-----\n<private_key_content>\n-----END RSA PRIVATE KEY-----",
          "public_key": "-----BEGIN PUBLIC KEY-----\n<public_key_content>\n-----END PUBLIC KEY-----"
        }
      ]
    }

Each platform, identified by ``platform_id``, is composed of a list of *LTI client IDs* that can support multiple
*LTI deployment IDs*. In the case the platform generates a new *LTI client ID* per activity, this configuration will
have to be duplicated for each one.

Setting up other LMS
````````````````````

INGInious has only been tested with edX and Moodle, but it should work out-of-the-box with any LMS that respects
LTI 1.1 or LTI 1.3. You are on your own for the configuration, though; but with the LTI keys and the
launch URL, it should be enough to configure anything.

Plugins
=======

INGInious provides a simple plugin system that allow to register some hooks to extend existing features, create new
frontend pages and features, and add new authentication methods.

Hooks actually call callback functions that you indicated with the ``add_hook`` method from ``PluginManager``. Please
note that all hooks may be called by another thread, so all actions done into a hook have to be thread-safe.

Tutorial
--------

The following code adds a new page displaying ``This is a simple demo plugin`` on the ``/plugindemo`` location.

.. code-block:: python

    from inginious.frontend.pages.utils import INGIniousPage


    class DemoPage(INGIniousPage):
        """ A simple demo page showing how to add a new page """

        def GET(self):
            """ GET request """
            return "This is a simple demo plugin"


    def init(plugin_manager, course_factory, client, plugin_config):
        """ Init the plugin """
        plugin_manager.add_page("/plugindemo", DemoPage.as_view('demopage'))


The plugin is initialized by the plugin manager, which is the frontend-extended hook manager, by calling method ``init``.
This method takes four arguments:

- ``plugin_manager`` which is the plugin manager singleton object. The detailed API is available at
  :ref:`inginious.frontend.plugin_manager`.

- ``course_factory`` which is the course factory singleton object, giving you abstraction to the tasks folder. The detailed
  API is available at :ref:`inginious.frontend.course_factory`.

- ``client`` which is the INGInious client singleton object, giving you access to the backend features, as launching
  a new job. The detailed API is available at :ref:`inginious.client.client`.

- ``plugin_config`` which is a dictionary containing the plugin configuration fields set in your ``configuration.yaml``
  file. For instance, configuration:
  ::

        plugins:
            - plugin_module: inginious.frontend.plugins.demo
              param1: "value1"

  will generate the following ``plugin_config`` dictionary :
  ::

        {"plugin_module": "inginious.frontend.plugins.demo", "param1": "value1"}


The remaining INGInious classes can be used from your plugins using correct imports. The ``init`` method gives you access
to the different singletons used by INGInious which are instantiated at boot time. For instance, ``LTIPage`` class can
be used as base for a new LTI page.

The ``plugin_module`` configuration parameter corresponds to the Python package in which the ``init`` method is found.
A demonstration plugin is found in the ``inginious.frontend.plugins.demo``. You do not need to include your plugin
in the INGInious sources. As long as your plugin is found in the Python path, it will remain usable by INGInious.

List of hooks
-------------

You may be interested to generate some actions useful for your plugins before or after some INGInious events. You
would therefore need to add a hook method. This can be done using the ``add_hook`` method of package
:ref:`inginious.frontend.plugin_manager`. For instance, the following plugin :

.. code-block:: python

    import logging

    def submission_done(submission, archive, newsub):
        logging.getLogger("inginious.frontend.plugins.demo").info("Submission " + str(submission['_id']) + " done.")

    def init(plugin_manager, course_factory, client, plugin_config):
        """ Init the plugin """
        plugin_manager.add_hook("submission_done", submission_done)

will log each submission id that has been returning from the backend.

Each hook available in INGInious is described here, starting with its name and parameters. Please refer to the complete
:ref:`inginious.frontend` package documentation for more information on the data returned by those hooks.

``css``
    Returns : List of path to CSS files.

    Used to add CSS files in the header. 
    Should return the path to a CSS file (relative to the root of INGInious).
``course_admin_menu`` (``course``)
    ``course`` : :ref:`inginious.frontend.courses.Course`

    Returns : Tuple (link, name) or None.

    Used to add links to the administration menu. This hook should return a tuple (link,name) 
    where link is the relative link from the index of the course administration.
    You can also return None.
``submission_admin_menu`` (``course``, ``task``, ``submission`` ``template_helper``)
    ``course`` : :ref:`inginious.frontend.courses.Course`
    
    ``task`` : :ref:`inginious.frontend.tasks.Task`

    ``submission`` : OrderedDict

    ``template_helper`` : :ref:`inginious.frontend.template_helper.TemplateHelper`

    Returns : HTML or None.

    Used to add HTML to the administration menu displayed at the top of a submission. 
    ``course`` is the course the submission was made for.
    ``task`` is the task the submission was made for.
    ``submission`` is the submission's data.
    ``template_helper`` is an object of type TemplateHelper, that can be useful to render templates.
``task_list_item`` (``course``, ``task``, ``tasks_data`` ``template_helper``)
    ``course`` : :ref:`inginious.frontend.courses.Course`
    
    ``task`` : :ref:`inginious.frontend.tasks.Task`

    ``tasks_data`` : dict

    ``template_helper`` : :ref:`inginious.frontend.template_helper.TemplateHelper`

    Returns : HTML or None.

    Used to add HTML underneath each item's progress bar in a course's task list (``/course/<courseid>``).
    This hook is called once for each task the course has. 
    If a course has 20 tasks, the hook is then called 20 times each time the task list is rendered.
    ``course`` is the course the submission was made for.
    ``task`` is the task the submission was made for.
    ``tasks_data`` is a dictionary used by INGInious which contains the grade and completion status of each of the course's tasks for the visiting user.
    ``template_helper`` is an object of type TemplateHelper, that can be useful to render templates.
``main_menu`` (``template_helper``)
    ``template_helper`` : :ref:`inginious.frontend.template_helper.TemplateHelper`

    Returns : HTML or None.

    Allows to add HTML to the menu displayed on the main (course list) page. ``template_helper`` is an object
    of type TemplateHelper, that can be useful to render templates.
``course_menu`` (``course``, ``template_helper``)
    ``course`` : :ref:`inginious.frontend.courses.Course`

    ``template_helper`` : :ref:`inginious.frontend.template_helper.TemplateHelper`

    Returns : HTML or None.

    Allows to add HTML to the menu displayed on the course page. Course is the course object related to the page. ``template_helper`` is an object
    of type TemplateHelper, that can be useful to render templates.
``task_menu`` (``course``, ``task``, ``template_helper``)
    ``course`` : :ref:`inginious.frontend.courses.Course`

    ``task`` : :ref:`inginious.frontend.tasks.Task`

    ``template_helper`` : :ref:`inginious.frontend.template_helper.TemplateHelper`

    Returns: HTML or None.

    Allows to add HTML to the menu displayed on the course page. ``course`` is the course object related to the page. ``task``
    is the task object related to the page. ``template_helper`` is an object of type TemplateHelper, that can be useful to render templates.
``javascript_header``
    Returns : List of path to Javascript files.

    Used to add Javascript files in the header. 
    Should return the path to a Javascript file (relative to the root of INGInious).
``javascript_footer``
    Returns : List of path to Javascript files.

    Used to add Javascript files in the footer. 
    Should return the path to a Javascript file (relative to the root of INGInious).
``course_accessibility`` (``course``, ``default``)
    Returns: inginious.frontend.accessible_time.AccessibleTime

    ``course`` : inginious.frontend.courses.Course

    ``default`` : Default value as specified in the configuration

    Overrides the course accessibility.

    Overrides the task accessibility
``task_limits`` (``course``, ``taskid``, ``default``)
    Returns: Task limits dictionary

    ``course`` : inginious.frontend.courses.Course

    ``task`` : inginious.frontend.tasks.Task

    ``default`` : Default value as specified in the configuration

    Overrides the task limits
``task_context`` (``course``, ``taskid``, ``default``)
    Returns: inginious.frontend.parsable_text.ParsableText

    ``course`` : inginious.frontend.courses.Course

    ``task`` : inginious.frontend.tasks.Task

    ``default`` : Default value as specified in the configuration

    Overrides the task context
``task_network_grading`` (``course``, ``taskid``, ``default``)
    Returns: True or False

    ``course`` : inginious.frontend.courses.Course

    ``task`` : inginious.frontend.tasks.Task

    ``default`` : Default value as specified in the configuration

    Overrides the task network-enable option
``new_submission`` (``submission``, ``inputdata``)
    ``submissionid`` : ObjectId corresponding to the submission recently saved in database.

    ``submission`` : Dictionary containing the submission metadata without ``input`` field.

    ``inputdata`` : Dictionary containing the raw input data entered by the student. Each key corresponding to the
    problem id.

    Called when a new submission is received.
    Please note that the job is not yet send to the backend when this hook is called,
    pay also attention that a submission is the name given to a job that was made through the frontend.
    It implies that jobs created by plugins will not call ``new_submission`` nor ``submission_done``.
``submission_done`` (``submission``, ``archive``, ``newsub``)
    ``submission`` : Dictionary containing the submission metadata.

    ``archive`` : Bytes containing the archive file generated by the job execution. This can be ``None`` if no archive
    is generated (for einstance, in MCQ).

    ``newsub`` : Boolean indicating if the submission is a new one or a replay.

    Called when a submission has ended. The submissionid is contained in the dictionary submission, under the field ``_id``.
``template_helper`` ()
    Returns : Tuple (name,func)

    Adds a new helper to the instance of TemplateHelper. Should return a tuple (name,func) where name is the name that will
    be indicated when calling the TemplateHelper.call method, and func is the function that will be called.
``feedback_text`` (``task``, ``submission``, ``text``)
    Returns : {"task": ``task``, "submission": ``submission``, "text": ``modified_text``}

    Modifies the feedback to be displayed. This hook is called each time a submission is displayed. You have to return
    the origin ``task`` and ``submission`` objects in the return value. ``text`` is in HTML format.
``feedback_script`` (``task``, ``submission``)
    Return : javascript as an ``str``.

    Javascript returned by this hook will be executed by the distant web browser when the submission is loaded.
    This hook is called each time a submission is displayed. Pay attention to output correct javascript, as it may
    break the webpage.

``task_editor_tab`` (``course``, ``taskid``, ``task_data``, ``template_helper``)
    ``course`` : inginious.frontend.courses.Course

    ``task_data`` : OrderedDict
    
    ``template_helper`` : inginious.frontend.template_helper.TemplateHelper
    
    This hook allows to add additional tabs on the task editor.
    
    ``course`` is the course object related to task, ``task_data`` is the task descriptor content and ``template_helper`` is an
    object of type TemplateHelper, that can be useful to render templates such as tab content.

``task_editor_submit`` (``course``, ``taskid``, ``task_data``, ``task_fs``)
    ``course`` : inginious.frontend.courses.Course

    ``task_data`` : OrderedDict
    
    ``task_fs`` : inginious.common.filesystems.local.LocalFSProvider
    
    This hook allows to process form data located in the added tabs.
    
    ``course`` is the course object related to task, ``task_data`` is the task descriptor content and ``task_fs`` is an
    object of type LocalFSProvider.    

Other useful methods for plugins
--------------------------------

These functions are meant to be called by plugins.

``inginious.frontend.envrionment_types.register_env_type(env_obj)``

    ``env_obj`` a ``FrontendEnvType`` object to be registered (to be displayed in the frontend and made accessible both
    in the studio and for submitting tasks).

Additional subproblems
----------------------

Additional subproblems can be defined and added via plugins. A basic example is available on GitHub repo
`INGInious/problems-demo <https://github.com/INGInious/problems-demo>`_.

Subproblems are defined at both the backend and frontend side. At the backend side, it consists of a class inheriting
from ``inginious.common.tasks_problems.Problem`` and implementing the following abstract methods:

   - ``get_type(cls)`` returning an alphanumerical string representing the problem type.
   - ``input_is_consistent(self, task_input, default_allowed_extension, default_max_size`` returning ``True`` if the
     ``task_input`` dictionary provided by the INGInious client is consistent and correct for the agent.
   - ``input_type(self)`` returning ``str``, ``dict`` or ``list`` according to the actual data sent to the agent.
   - ``check_answer(self, task_input, language)`` returning a tuple whose items are:

        #. either ``True``, ``False`` or ``None``, indicating respectively that the answer is valid, invalid,
           or need to be sent to VM
        #. the second is the error message assigned to the task, if any (unused for now)
        #. the third is the error message assigned to this problem, if any
        #. the fourth is the number of errors.

     This method should be called via a compatible agent, as for MCQs. The Docker
     agent will not call this method. ``task_input`` is the dictionary provided
     by the INGInious client after its consistency was checked. ``language`` is the gettext 2-letter language code.
   - ``get_text_fields(cls)`` returns a dictionary whose keys are the problem YAML fields that require translation and values
     are always True.
   - ``parse_problem(self, problem_content)`` returns the modified `problem_content`` returned by the INGInious studio.
     For instance, strings-encoded int values can be cast to int here.

At the frontend side, it consists of a class inheriting from ``inginious.frontend.tasks_problems.DisplayableProblem``
and implementing the following abstract methods:

  - ``get_type_name(cls, language)`` returning a human-readable transleted string representing the problem type.
    ``language`` is the gettext 2-letter language code.
  - ``get_renderer(cls, template_helper)`` returning the template renderer used for the subproblem. ``template_helper``
    is the webapp ``TemplateHelper`` singleton. It can be used to specify a local template folder.
  - ``show_input(self, template_helper, language, seed)`` returning a HTML code displayed after the subproblem context to the
    student. ``template_helper`` is the webapp ``TemplateHelper`` singleton. ``language`` is the gettext 2-letter language
    code. ``seed`` is a seed to be used in the random number generator. For simplicity, it should be a string and the usage
    of the username is recommended, as the seed is made to ensure that a user always see the same exercise.
    Classes inheriting from DisplayableProblem should prepend/append a salt to the seed and then create a new
    instance of Random from it. See ``inginious.frontend.tasks_problems.DisplayableMultipleChoiceProblem``
    for an example.
  - ``show_editbox(cls, template_helper, key, language)`` returning a HTML code corresponding to the subproblem edition box.
    ``language`` is the gettext 2-letter language code. ``template_helper`` is the webapp ``TemplateHelper`` singleton.
    ``key`` is the problem type sent by the frontend.

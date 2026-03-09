.. _run_file:

Run file
========

When the student have submit his/her code, INGInious starts a new Docker container
with the right *environment* for the task (as given in the *task.yaml* file). Inside this
container is launched a script, that we call the *run* script, that you have to provide in the
directory of your task.

Naming your `run` script
------------------------

.. tip::

    TL;DR: name your script `run.py` if you use Python or `run.sh` if you use bash. You can put a run script
    inside the *common* folder of a course, and it will be used by default if no run file exists in a task.

The file chosen by INGInious as your *run* file is dependent on the environment. Here is how INGInious resolves
the best file to run (the resolution ends a soon a one of the rule is respected):

1. If a custom run command was provided, this command is run.
2. If a file named **`run`** exists in the **task** folder, this file is run.
   Note that in this case the file will need a shebang (see below)
3. Depending on the container *environment*, files named **`run.EXT`** in the **task** folder,
   where EXT is a container-specific extension, will be run.

   ========== ==== ========
   Container  EXT  Language
   ========== ==== ========
   all        py3  IPython3
   all        py   IPython3
   all        sh   bash
   ========== ==== ========

   It is possible to add your own extensions/languages in new containers.
4. If a file named **`run`** exists in the **common course** folder, this file is run.
   Note that in this case the file will need a shebang (see below)
5. Depending on the container *environment*, files named **`run.EXT`** in the **common course** folder,
   where EXT is a container-specific extension, will be run. See table above.

.. tip::

    If you simply name you run script **`run`**, don't forget to indicate which interpreter
    should be used to execute the script.
    To do that, use a shebang:

    ::

        #!/bin/bash
        feedback-result success


Here is a simple example of a *run.py* file, compatible with the *default* environment,
that simply returns that the student's code is OK:

::

    set_global_result("success")

This is actually an IPython code.

In general, the *run* script is simply an executable application (a bash script, a python script, or
a compiled executable runnable by the container). INGInious' default containers provides
commands (also available as python libraries) to interact with the backend.

By default, the script is run by a non-root user.
You can modify the container to change this (and everything else).

Python run scripts are run with IPython
---------------------------------------

IPython is a Python interpreter that adds some very useful features to Python, notably magic commands.

The main feature that you will use is probably the bang (`!`) magic command, that allows your to run a command
like if you were in bash (or any "basic" shell):

::

    # run a command
    ! touch hello.txt

    # you can store the output, as an array of line
    out = !ls -1

    # we are still in python
    length = len(out)
    print(length, ";".join(out))

By default, the INGInious version of IPython loads utility libraries of INGInious (feedback, input, lang, rst)
into the global namespace, so you don't have to.

If you want to use the INGInious IPython interpreter in another script, the interpreter is
located at `/bin/inginious-ipython`.

Check the API documentation
---------------------------

The prefered way to create run script is via the IPython interpreter.
:ref:`The full description of the API available from Python is available here.<inginious_container_api>`

Feedback commands
-----------------

feedback-result
```````````````
The *feedback-result* command sets the submission result of a task, or a problem.

.. tabs::

    .. code-tab:: ipython3

        # set the global result
        set_global_result("success")  # Set global result to success

        # set the result of a specific suproblem
        set_problem_result("failed", "q1")  # Set 'q1' subproblem result to failed

    .. code-tab:: py

        from inginious_container_api import feedback

        # set the global result
        feedback.set_global_result("success")  # Set global result to success

        # set the result of a specific suproblem
        feedback.set_problem_result("failed", "q1")  # Set 'q1' subproblem result to failed

    .. code-tab:: bash

        # format: feedback-result [-i|--id PROBLEM_ID] RESULT
        feedback-result success  # Set global result to success
        feedback-result -i q1 failed  # Set 'q1' subproblem result to failed

The execution result can be of different types:

- success : the student succeeded the task
- failed : there are error in the student answer
- timeout : the tests timed out
- overflow :there was a memory/disk overflow
- crash : the tests crashed

Any other type will be modified to "crash".

feedback-grade
``````````````

The *feedback-grade* command sets the submission grade.

.. tabs::

    .. code-tab:: ipython3

        set_grade(87.8) # Set the grade to 87.8%

    .. code-tab:: py

        from inginious_container_api import feedback
        feedback.set_grade(87.8) # Set the grade to 87.8%

    .. code-tab:: bash

        # format: feedback-grade GRADE
        feedback-grade 87.8


If no grade is specified (i.e. the command is never called), the result score will be binary.
This means that a failed
submission will give a 0.0% score to the student, while a successful submission will
give a 100.0% score to the student.


feedback-msg-tpl
````````````````

The *feedback-msg-tpl* sets the feedback message associated to the task or a subproblem, using a `Jinja2 <http://jinja.pocoo.org/docs/2.9/>` template.

It needs the name of a template. The command attempt to use a translated version of the template first; given that you give TPLNAME as first
argument to the command, *feedback-msg-tpl* will attempt to find the template, by search in this order:

- `[local_dir]/TPLNAME.XX_XX.tpl`
- `[task_dir]/lang/XX_XX/TPLNAME.tpl` (preferred way)
- `[local_dir]/TPLNAME.tpl`

Once found, the template is parsed using `Jinja2 <http://jinja.pocoo.org/docs/2.9/>`, which allows you to send parameters to the template.

.. tabs::

    .. code-tab:: ipython3

        # format:
        # set_feedback_from_tpl(template_name, template_options, problem_id=None, append=False)
        # template_name is the file to format without extension. See above for details.
        # template_options is a dict in the form {name: value}. See below
        # problem_id is the problem id to which the feedback must be assigned. If None, the feedback is global
        # append is a boolean indicating if the feedback must be appended or not (overwritting the current feedback)

        set_feedback_from_tpl("feedback", {"option1":"value1", "anothername":"anothervalue"})

    .. code-tab:: py

        from inginious_container_api import feedback

        # format:
        # feedback.set_feedback_from_tpl(template_name, template_options, problem_id=None, append=False)
        # template_name is the file to format without extension. See above for details.
        # template_options is a dict in the form {name: value}. See below
        # problem_id is the problem id to which the feedback must be assigned. If None, the feedback is global
        # append is a boolean indicating if the feedback must be appended or not (overwritting the current feedback)

        feedback.set_feedback_from_tpl("feedback", {"option1":"value1", "anothername":"anothervalue"})

    .. code-tab:: bash

        # format: feedback-msg-tpl [-a | --append] [-i | --id PROBLEM_ID] TPLNAME [option1=value1 option2=value2 ...]
        # TPLNAME is the file to format without extension. See above for details.
        # Options can be indicated at the end of the command, and will be passed to the template (see below)
        # --append is a boolean flag indicating if the feedback must be appended or not (overwritting the current feedback)
        # --id PROBLEM_ID. PROBLEM_ID is the problem id to which the feedback must be assigned.
        #                  If not indicated, the feedback is global

        feedback-msg-tpl feedback option1=value1 anothername=anothervalue


Inside your template (named `feedback.tpl` in the examples above), you can use these parameters like this:

::

    Option 1 was {{ option1 }} and the option 2 was {{ anothername }}

Which will return

::

    Option 1 was value1 and the option 2 was anothervalue

See the Jinja2 documentation to discover all possibilities.

Your template must return a valid RestructuredText.

feedback-msg
````````````
The *feedback-msg* command sets the feedback message associated to the task or a subproblem.

.. tabs::

    .. code-tab:: ipython3

        # format:
        # set_global_feedback(feedback, append=False)
        # append is a boolean indicating if the feedback must be appended or not (overwritting the current feedback)

        set_global_feedback(
            """This is the correct answer.

            Well done!"""
        )

        # format:
        # set_problem_feedback(feedback, problem_id, append=False)
        # problem_id is the problem id to which this feedback must be associated
        # append is a boolean indicating if the feedback must be appended or not (overwritting the current feedback)

        set_problem_feedback(
            """This is the correct answer.

            Well done!"""
        , "q1")

    .. code-tab:: py

        from inginious_container_api import feedback

        # format:
        # set_global_feedback(feedback, append=False)
        # append is a boolean indicating if the feedback must be appended or not (overwritting the current feedback)

        feedback.set_global_feedback(
            """This is the correct answer.

            Well done!"""
        )

        # format:
        # set_problem_feedback(feedback, problem_id, append=False)
        # problem_id is the problem id to which this feedback must be associated
        # append is a boolean indicating if the feedback must be appended or not (overwritting the current feedback)

        feedback.set_problem_feedback(
            """This is the correct answer.

            Well done!"""
        , "q1")

    .. code-tab:: bash

        feedback-msg -ae -m "This is the correct answer.\n\nWell done!"

        # It has several
        # optional parameters:
        #
        # -a, --append                        append to current feedback, if not specified, replace the
        #                                     current feedback.
        # -i, --id PROBLEM_ID                 problem id to which associate the feedback, leave empty
        #                                     for the whole task.
        # -e, --escape                        interprets backslash escapes
        # -m, --message MESSAGE               feedback message
        # If the message is not specified, the feedback message is read from stdin.

.. _feedback-custom:

feedback-custom
```````````````
The *feedback-custom* command sets a pair of key/value custom feedback, mainly used with plugins.

.. tabs::

    .. code-tab:: ipython3

        # format: set_custom_value(key, value)
        # Please refer to the plugin documentation to know which value you have to set for ``key`` and ``value`` parameters.
        # value can be anything that can be encoded to JSON by the default python library.
        set_custom_value("score", 56) # Set the `score` key to value 56

    .. code-tab:: py

        # format: set_custom_value(key, value)
        # Please refer to the plugin documentation to know which value you have to set for ``key`` and ``value`` parameters.
        # value can be anything that can be encoded to JSON by the default python library.
        feedback.set_custom_value("score", 56) # Set the `score` key to value 56

    .. code-tab:: bash

        # format: feedback-custom [-j|--json] key value

        # The ``--json`` parameter indicates if ``value`` must be parsed as a JSON string.
        # Please refer to the plugin documentation to know which value you have to set for ``key`` and ``value`` parameters.

        # For instance, the following command set the value ``56`` to the ``score`` key:
        feedback-custom score 56


tag-set
```````

The *tag-set* command sets the value of the tag specified by the tag identifier to ``True`` or ``False``.



.. tabs::

    .. code-tab:: ipython3

        # format: set_tag(tag, value):
        # Set the tag 'tag' to the value True or False.
        # :param value: should be a boolean
        # :param tag: should be the id of the tag. Can not starts with '*auto-tag-'

        # For instance, the following command set the value of the ``my_tag`` tag to ``True``:
        set_tag("my_tag", True)


    .. code-tab:: py

        from inginious_container_api import feedback

        # format: set_tag(tag, value):
        # Set the tag 'tag' to the value True or False.
        # :param value: should be a boolean
        # :param tag: should be the id of the tag. Can not starts with '*auto-tag-'

        # For instance, the following command set the value of the ``my_tag`` tag to ``True``:
        feedback.set_tag("my_tag", True)

    .. code-tab:: bash

        # format: tag-set tag value

        # For instance, the following command set the value of the ``my_tag`` tag to ``True``:
        tag-set my_tag true

tag
```

The *tag* command defines a new unexpected tag to appear in the submission feedback.

.. tabs::

    .. code-tab:: ipython3

        # format: set_tag(tag, value):
        # Set the tag 'tag' to the value True or False.
        # :param value: should be a boolean
        # :param tag: should be the id of the tag. Can not starts with '*auto-tag-'

        # # For instance, the following command defines a new ``A new tag`` tag that will appear in the submission feedback:
        tag("A new tag") # Sets a new unexpected tag


    .. code-tab:: py

        from inginious_container_api import feedback

        # format: set_tag(tag, value):
        # Set the tag 'tag' to the value True or False.
        # :param value: should be a boolean
        # :param tag: should be the id of the tag. Can not starts with '*auto-tag-'

        # # For instance, the following command defines a new ``A new tag`` tag that will appear in the submission feedback:
        feedback.tag("A new tag") # Sets a new unexpected tag

    .. code-tab:: bash

        # format: tag value

        # For instance, the following command defines a new ``A new tag`` tag that will appear in the submission feedback:
        tag "A new tag"

reStructuredText helper commands
--------------------------------

Several helper commands are available to format the feedback text, which format is reStructuredText.

rst-code
````````

The *rst-code* command generates a code-block with the specified code snippet and language
to enable syntax highlighting.


.. tabs::

    .. code-tab:: ipython3

        codeblock = get_codeblock("java", "int a = 42;") # Java codeblock with `int a = 42;` code

        set_global_feedback(codeblock, True) # Appends the codeblock to the global feedback


    .. code-tab:: py

        from inginious_container_api import rst, feedback

        codeblock = rst.get_codeblock("java", "int a = 42;") # Java codeblock with `int a = 42;` code

        feedback.set_global_feedback(codeblock, True) # Appends the codeblock to the global feedback

    .. code-tab:: bash

        # format: rst-code [-l | --language LANGUAGE] [-e | --escape] [-c | --code CODE]

        # -l, --language LANGUAGE    snippet language, leave empty to disable syntax highlighting
        # -e, --escape               interprets backslash escapes
        # -c, --code CODE            snippet code

        # If the code parameter is not specified, it is read on standard input. The result is written on standard output.
        # For instance, the command can be used as follows:
        cat test.java | rst-code -l java | feedback-msg -a



rst-image
`````````

The *rst-image* command generates a raw reStructuredText block containing an image to display.

.. tabs::

    .. code-tab:: ipython3

        # get_imageblock(filename, format='')
        imgblock = get_imageblock("smiley.png") # RST block with image
        set_global_feedback(imgblock, True) # Appends the image block to the global feedback


    .. code-tab:: py

        from inginious_container_api import rst, feedback

        # get_imageblock(filename, format='')
        imgblock = rst.get_imageblock("smiley.png") # RST block with image
        feedback.set_global_feedback(imgblock, True) # Appends the image block to the global feedback

    .. code-tab:: bash

        # format: rst-image [-f|--format FORMAT] FILEPATH

        # Appends the image block to the global feedback
        rst-image smiley.png | feedback-msg -a

The optional *format* parameter is used to specify the image format (jpg, png,...) if this is not explicitly specified
the image filename. The output is written on the standard output. For instance, the command can be used as follows:

get_admonition / rst-msgblock
`````````````````````````````

The *get_admonition* (python) / *rst-msgblock* (bash) command is used to generate a reStructuredText admonition in a
specific colour according to the message type.

You must indicate a type for the admonition (via the first arg in Python, or via the `-c` arg in bash). The type can be:

- `success` (green box)
- `info` (blue box)
- `warning` (orange box)
- `danger` (red box)

You can also indicate a title (second parameter in Python, `-t` in bash). It can be empty.

.. tabs::

    .. code-tab:: ipython3

        # RST message block of class "success" and title "Yeah!"
        admonition = get_admonition("success", "Yeah!", "Well done!")
        set_global_feedback(admonition, True) # Appends the block to the global feedback


    .. code-tab:: py

        from inginious_container_api import rst, feedback

        # RST message block of class "success" and title "Yeah!"
        admonition = rst.get_admonition("success", "Yeah!", "Well done!")
        feedback.set_global_feedback(admonition, True) # Appends the block to the global feedback

    .. code-tab:: bash

        # format: rst-image [-c | --class CSS_CLASS] [-e | --escape] [-t | --title TITLE] [-m | --message MESSAGE]
        # -c, --class CSS_CLASS    Type (Bootstrap alert CSS class). See above for details.
        # -e, --escape             interprets backslash escapes
        # -t, --title TITLE        message title
        # -m, --message MESSAGE    message text
        # If the message parameter is not set, the message is read from standard input.

        rst-msgblock -c info -m "This is a note" | feedback -ae

rst-indent
``````````

The *rst-indent* command is used to add indentation to a given text.

.. tabs::

    .. code-tab:: ipython3

        rawhtml = indent_block(1, "<p>A paragraph!</p>", "\t") # Indent the HTML code with 1 unit of tabulations
        set_global_feedback(".. raw::\n\n" + rawhtml, True) # Appends the block to the global feedback

    .. code-tab:: py

        from inginious_container_api import rst, feedback

        rawhtml = rst.indent_block(1, "<p>A paragraph!</p>", "\t") # Indent the HTML code with 1 unit of tabulations
        feedback.set_global_feedback(".. raw::\n\n" + rawhtml, True) # Appends the block to the global feedback

    .. code-tab:: bash

        # format: rst-image [-c | --class CSS_CLASS] [-e | --escape] [-t | --title TITLE] [-m | --message MESSAGE]
        # -e, --escape                      interprets backslash escapes
        # -c, --indent-char INDENT_CHAR     indentation char, default = tabulation
        # -a, --amount AMOUNT               amount of indentation, default = 1
        # -m, --message MESSAGE             message text

        # If the message parameter is not set, the message is read from standard input.

        # For instance, the command can be used as follows, to add an image to the feedback,
        # (inside a list item, for instance):
        rst-msgblock -c info -m "This is a note" | feedback -ae


The amount of indentation can be negative to de-indent the text.

Input commands
--------------

get_input
`````````

The *get_input* command/function returns the input given by the student for a specific problem id.
For example, for the problem id "pid":

.. tabs::

    .. code-tab:: ipython3

        thecode = get_input("pid")

    .. code-tab:: py

        from inginious_container_api import input
        thecode = input.get_input("pid")

    .. code-tab:: bash

        getinput pid

When a problem is defined with several boxes, the argument becomes *pid/bid* where "pid"
stands for the problem id and "bid" for "box id". If the problem is a file upload, the problem id can be appended
with ``:filename`` or ``:value`` to retrieve its filename or value.

Note that *get_input* can also retrieve the username/group of the user that submitted the task. You simply have to run

.. tabs::

    .. code-tab:: ipython3

        username = get_input("@username")

    .. code-tab:: py

        username = input.get_input("@username")

    .. code-tab:: bash

        getinput @username

If the submission is made as a user, it will contain the username. It it's made as a group,
it will contain the list of the user's usernames in the
group, joined with ','.

You can retrieve the email of the user that submitted the task with the
following lines. If this is a group submission, this will give a list of
the user's emails in the group, joined with ','.

.. tabs::

    .. code-tab:: ipython3

        username = get_input("@email")

    .. code-tab:: py

        username = input.get_input("@email")

    .. code-tab:: bash

        getinput @email

The four letter code of the student's language (for example `en_US` or `fr_FR`) can also be retrieved using

.. tabs::

    .. code-tab:: ipython3

        lang = get_input("@lang")

    .. code-tab:: py

        lang = input.get_input("@lang")

    .. code-tab:: bash

        getinput @lang

The submission time, following the datetime format "%Y-%M-%D %H:%M:%S.%f", can be retrieved using

.. tabs::

    .. code-tab:: ipython3

        submission_time = get_input("@time")

    .. code-tab:: py

        submission_time = input.get_input("@time")

    .. code-tab:: bash

        getinput @time


With python or ipython, you can directly retrieve the submission time as a `datetime.datetime` object by using

.. tabs::

    .. code-tab:: ipython3

        submission_time = get_submission_time()

    .. code-tab:: py

        submission_time = input.get_submission_time()


Random inputs may also be generated if you configured it so. You can access these random inputs using

.. tabs::

    .. code-tab:: ipython3

        lang = get_input("@random")

    .. code-tab:: py

        lang = input.get_input("@random")

    .. code-tab:: bash

        getinput @random

Note that this returns the list of random values corresponding to the number of random inputs asked in the task configuration.

Finally, note that plugins are free to add new `@`-prefixed fields to the available input using the `new_submission` hook.

parsetemplate
`````````````

The *parsetemplate* command injects the input given by the student in a template.

A template file must be given to the function/command. An output file can also be given, and if
none is given, the template will be replaced.

.. tabs::

    .. code-tab:: ipython3

        parse_template("student.c") # Parse the `student.c` template file
        parse_template("template.c", "student.c") # Parse the `template.c` template file and save the parsed file into `student.c`

    .. code-tab:: py

        from inginious_container_api import input
        input.parse_template("student.c") # Parse the `student.c` template file
        input.parse_template("template.c", "student.c") # Parse the `template.c` template file and save the parsed file into `student.c`

    .. code-tab:: bash

        # parsetemplate [-o|--output outputfile] template
        parsetemplate "student.c" # Parse the `student.c` template file
        parsetemplate -o "student.c" "template.c" # Parse the `template.c` template file and save the parsed file into `student.c`


The markup in the templates is very simple: *@prefix@problemid@suffix@*.
Prefix allows to correct the indentation when needed (this is useful in Python).

Example of template file (in java)
::

    public class Main
    {
        public static void main(String[] args)
        {
    @        @problem_one@@
        }
    }

To access the filename and text content of a submitted file, the *problemid* can be
followed by a *:filename* or *:value* suffix.

.. _run_student:

run_student
-----------

*run_student* allows the *run file* to start, at will, sub-containers. This makes you able to secure the grading,
making sure the untrusted code made by the student don't interact with yours.

The sub-container is launched with a different user who has read-write accesses to the task ``student``
subdirectory. Only the changes made in that directory will remain in the main container.

*run_student* is fully configurable; you can change the container image (environment), set new timeouts, new memory
limits, ... And you can call it as many time as you want.

Here is the list of the main parameters:

- container (--container in the run_student command)
        Name of the container to use. The default is the same as the current container.
- time limit (--time)
        Timeout (in CPU time) for the container, in seconds. The default is the same as the current container.
- hard time limit (--hard-time)
        Hard timeout for the container (in real time), in seconds.
        The default is three times the value indicated for the time limit.
- memory limit (--memory)
        Maximum memory for the container, in Megabytes. The default is the same as the current container.
- network sharing (--share-network)
        Share the network stack of the grading container with the student container. This is not the case by
        default. If the container container has network access, this will also be the case for the student!
- start student as root (--run-as-root)
        Start the student_container on a safe non shared kernel runtime with root access.

Beyond these optionals args, *run_student* various commands also takes an additional (mandatory) argument:
the command to be run in the new container.

More technically, please note that:

- the *run_student* **command** (accesible in bash) proxies stdin, stdout, stderr, most signals and the return value
- There are special return values:
    - 251: ``run_student`` is not available in this container/environment
    - 252: the command was killed due to an out-of-memory
    - 253: the command timed out
    - 254: an error occurred while running the proxy

In Python, two flavours of *run_student* are available: `run` and `run_simple`. The first is a low-level function,
which allows you to modify most of the behavior of the behavior of the function. The second aims to solve the most used
use case: run a command with a given input, and returns its output. A small description of `run_simple` is available in
the examples below, please check the API directly for more information.

.. tabs::

    .. code-tab:: ipython3

        # runs student/script.sh in another safe container, with a timeout of 60 seconds,
        # and stores the output in the variables `stdout` and `stderr`, and the return value
        # inside the variable `retval`.
        stdout, stderr, retval = run_student_simple("student/script.sh", time_limit=60)

    .. code-tab:: py

        from inginious_container_api import run_student

        # runs student/script.sh in another safe container, with a timeout of 60 seconds,
        # and stores the output in the variables `stdout` and `stderr`, and the return value
        # inside the variable `retval`.
        stdout, stderr, retval = run_student.run_student_simple("student/script.sh", time_limit=60)

    .. code-tab:: bash

        # runs student/script.sh in another safe container, with a timeout of 60 seconds,
        # and stores the output in the variable `output`, as an array of lines.
        output=`run_student --time 60 student/script.sh`



.. _ssh_student:

ssh_student
-----------

.. DANGER::

    The *ssh_student* feature requires to allow ssh and internet connection in the environment configuration tab.
    Note, to use ssh_student, at least one inginious-agent in your deployment must handle ssh. For more details, see: :ref:`inginious-docker-agent<inginious-agent-docker>`


*ssh_student* allows the *run file* to start a sub-containers and to give ssh access to it. It can accept a setup script to run on the student container before launching the ssh server. It is also possible to specify a teardown script to be run on the student container when the student leaves the ssh session.
This makes you able to secure the grading while giving the student the chance to interact and enter commands within his own container. All the ssh session is recorded into the ``.ssh_logs`` file resulting in the ``student`` subdirectory after the ssh session closed. Please note the setup and teardown scripts will not be run as root to avoid any potential damage to the supervisor (unless the student has root access, meaning it is using a runtime that does not share kernel between containers).

When the student exits the ssh connection, after the teardown script, his specific container is killed and only the changes made to the ``student`` subdirectory will remain in the main (grading) container.

*ssh_student* is nearly as configurable as *run_student* is; you can change the container image (environment), set new timeouts, new memory
limits, ...

Here is the list of the main parameters:

- container (--container in the ssh_student command)
        Name of the container to use. The default is the same as the current container.
- time limit (--time)
        Timeout (in CPU time) for the container, in seconds. The default is the same as the current container.
- hard time limit (--hard-time)
        Hard timeout for the container (in real time), in seconds.
        The default is three times the value indicated for the time limit.
        We recommand here to put a very large time limit since the student will require some time to connect (copy-paste the command) and to solve the exercice in live via the ssh connection.
        Example would be 900 (15 min) or 1800 (30 min). In any case, when the student exits the connection, the container will be killed regardless of its remaining hard time limit.
- memory limit (--memory)
        Maximum memory for the container, in Megabytes. The default is the same as the current container.
- run as root (--run-as-root)
        Start the student_container on a safe non shared kernel runtime with root access.

Beyond these optionals args, *ssh_student* also takes two additionnal string arguments:
the **setup-script** to be run in the new container before starting the ssh server and the **teardown-script** to be run at ssh session closure.

More technically about these optional arguments, please note that:

- The **setup-script** can take the form of direct commands or a script file which may start new subprocess. Only the main body of the script will be executed and finished before starting the ssh server. If you want subprocess to continue running in background while the student has ssh access, these subprocess must be launched in a non-blocking way (such as using `subprocess.Popen <https://docs.python.org/fr/3/library/subprocess.html#subprocess.Popen>`_ inside a python setup script).
- The **teardown-script** follows the same principle. Please note that teardown_script files should be placed in *student/scripts*. This specific directory will automatically be isolated from the student during the ssh session so that the student can not inspect the scripts unless he has root privileges.


Here are the different return values:
    -   0: the student correctly connected and leaved the ssh connection
    - 251: ``ssh_student`` is not available in this container/environment
    - 252: the container was killed due to an out-of-memory
    - 253: the container timedout or no student connected within 2 minutes
    - 254: an error occurred while running the proxy


.. tabs::

    .. code-tab:: ipython3

        # runs a python script in another safe container, then gives ssh access to that container
        # with a timeout of 30 minutes for the student to resolve the exercise and exit the connection.
        retval = ssh_student(setup_script="pyhon3 student/scripts/setup.py", hard_time_limit=1800)

    .. code-tab:: py

        from inginious_container_api import ssh_student

        # runs a python script in another safe container, then gives ssh access to that container
        # with a timeout of 30 minutes for the student to resolve the exercise and exit the connection.
        retval = ssh_student.ssh_student(setup_script="python3 student/scripts/setup.py", hard_time_limit=1800)

    .. code-tab:: bash

        # runs a python script in another safe container, then gives ssh access to that container
        # with a timeout of 30 minutes for the student to resolve the exercise and exit the connection.
        retval=`ssh_student --hard-time 1800 --setup-script "python3 student/scripts/setup.py"`



Archiving files
---------------

The folder /archive inside the container allows you to store anything you may need outside the container.
The content of the folder will be automatically compressed and saved in the database, and will be downloadable
in the INGInious web interface.

This feature is useful for debug purposes, but also for analytics and for more complex plugins.

Who is running the run file?
----------------------------

By default it is a user named ``worker`` (id 4242, gid 4242). Some docker runtime allow to run safely as root;
in these runtimes, the script are thus started by ``root`` (id 0, gid 0).

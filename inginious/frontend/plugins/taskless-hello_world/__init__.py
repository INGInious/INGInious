# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" A demo taskless job plugin that adds a page """

from inginious.frontend.pages.utils import INGIniousPage
from inginious.client.client_sync import ClientSync

from flask import render_template
import os


PATH_TO_PLUGIN = os.path.abspath(os.path.dirname(__file__))
PATH_TO_TEMPLATES = os.path.join(PATH_TO_PLUGIN, "templates")


def init(plugin_manager, client, config):
    """ Init the plugin """

    class TasklessJobPage(INGIniousPage):
        """ Simple page to call the taskless hello world job """

        def GET(self):
            """ GET request : render simple page with button that will call the taskless hello world job"""
            return render_template("taskless-hello_world/templates/call.html", template_folder=PATH_TO_TEMPLATES)


        def POST(self):
            """ POST request : call the taskless hello world job and return the result """
            client_sync = ClientSync(client)

            result, grade, problems, tests, custom, state, archive, stdout, stderr = client_sync.new_job(
                priority=0,
                job_info={"environment_type": "docker", "environment": "taskless-hello_world"},
                inputdata={"hello_world_message": "My name is John Doe and I am a software engineer."},
                launcher_name="Plugin - taskless Hello World",
                debug=False
            )

            return render_template("taskless-hello_world/templates/result.html", template_folder=PATH_TO_TEMPLATES, message=result[1])


    plugin_manager.add_page("/taskless_hello_world",TasklessJobPage.as_view('taskless_hello_world'))
    plugin_manager.add_template_prefix("taskless-hello_world", PATH_TO_PLUGIN)

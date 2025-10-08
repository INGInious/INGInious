# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Job queue status page """

from flask import request, render_template
from datetime import datetime

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.user_manager import user_manager
from inginious.frontend.arch_helper import get_client
from inginious.frontend.submission_manager import submission_manager

class QueuePage(INGIniousAuthPage):
    """ Page allowing to view the status of the backend job queue """

    def GET_AUTH(self):
        """ GET request """
        jobs_running, jobs_waiting = submission_manager.get_job_queue_snapshot()
        return render_template("queue.html", jobs_running=jobs_running, jobs_waiting=jobs_waiting,
                                           from_timestamp=lambda x: datetime.fromtimestamp(x).astimezone())

    def POST_AUTH(self, *args, **kwargs):
        if user_manager.user_is_superadmin():
            inputs = request.form
            jobid = inputs["jobid"]
            get_client().kill_job(jobid)
        return self.GET_AUTH()
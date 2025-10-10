# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Job queue status page """

from flask import request, render_template
from datetime import datetime

from inginious.frontend.pages.utils import INGIniousAuthPage


class QueuePage(INGIniousAuthPage):
    """ Page allowing to view the status of the backend job queue """

    def GET_AUTH(self):
        """ GET request """
        jobs_running, jobs_waiting = self.submission_manager.get_job_queue_snapshot()
        return render_template("queue.html", jobs_running=jobs_running, jobs_waiting=jobs_waiting,
                                           from_timestamp=lambda x: datetime.fromtimestamp(x).astimezone())

    def POST_AUTH(self, *args, **kwargs):
        if self.user_manager.user_is_superadmin():
            inputs = request.form
            jobid = inputs["jobid"]
            self.client.kill_job(jobid)
        return self.GET_AUTH()
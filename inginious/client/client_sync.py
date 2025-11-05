# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" A synchronized "layer" for Client """
import threading


class ClientSync(object):
    """ Runs job synchronously """

    def __init__(self, client):
        self._client = client

    def new_job(self, priority, course, task, inputdata, launcher_name="Unknown", debug=False):
        """
            Runs a new job.
            It works exactly like the Client class, instead that there is no callback and directly returns result, in the form of a tuple
            (result, grade, problems, tests, custom, archive).
        """
        job_semaphore = threading.Semaphore(0)

        def manage_output(result, grade, problems, tests, custom, state, archive, stdout, stderr):
            """ Manages the output of this job """
            manage_output.job_return = (result, grade, problems, tests, custom, state, archive, stdout, stderr)
            job_semaphore.release()

        manage_output.job_return = None

        self._client.new_job(priority, course, task, inputdata, manage_output, launcher_name, debug)
        job_semaphore.acquire()
        job_return = manage_output.job_return
        return job_return

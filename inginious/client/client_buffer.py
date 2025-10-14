# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Contains ClientBuffer, which creates a buffer for a Client """

import uuid


class ClientBuffer(object):
    """ A buffer for a Client """

    def __init__(self, client):
        self._client = client
        self._waiting_jobs = []
        self._jobs_done = {}

    def new_job(self, priority, course, task, inputdata, launcher_name="Unknown", debug=False):
        """ Runs a new job. It works exactly like the Client class, instead that there is no callback """
        bjobid = uuid.uuid4()
        self._waiting_jobs.append(str(bjobid))
        self._client.new_job(priority, course, task, inputdata,
                             (lambda result, grade, problems, tests, custom, archive, stdout, stderr:
                              self._callback(bjobid, result, grade, problems, tests, custom, archive, stdout, stderr)),
                             launcher_name, debug)
        return bjobid

    def _callback(self, bjobid, result, grade, problems, tests, custom, archive, stdout, stderr):
        """ Callback for self._client.new_job """
        if str(bjobid) in self._waiting_jobs:
            self._jobs_done[str(bjobid)] = (result, grade, problems, tests, custom, archive, stdout, stderr)
            self._waiting_jobs.remove(str(bjobid))

    def is_waiting(self, bjobid):
        """ Return true if the job is in queue """
        return str(bjobid) in self._waiting_jobs

    def is_done(self, bjobid):
        """ Return true if the job is done """
        return str(bjobid) in self._jobs_done

    def get_result(self, bjobid):
        """
            Get the result of task. Must only be called ONCE, AFTER the task is done (after a successfull call to is_done).
            :return a tuple (result, grade, problems, tests, custom, archive)
            result is itself a tuple containing the result string and the main feedback (i.e. ('success', 'You succeeded')
            grade is a number between 0 and 100 indicating the grade of the users
            problems is a dict of tuple, in the form {'problemid': result}
            test is a dict of tests made in the container
            custom is a dict containing random things set in the container
            archive is either None or a bytes containing a tgz archive of files from the job
        """
        result = self._jobs_done[str(bjobid)]
        del self._jobs_done[str(bjobid)]
        return result

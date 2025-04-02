# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from bson.json_util import dumps

from inginious.frontend.pages.course_admin.submissions_data import SubmissionsEndpoint

class UserTasksEndpoint(SubmissionsEndpoint):
    """ Endpoint to retrieve user task data """

    def page(self, params):
        msg = dumps(self.database.user_tasks.find(params))
        return self.response(msg)


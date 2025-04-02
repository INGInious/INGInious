# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from flask import request
from bson.json_util import dumps

from inginious.frontend.pages.course_admin.api_auth import DataAPIPage

class SubmissionsEndpoint(DataAPIPage):
    """ Endpoint to retrieve submission data """

    def GET(self, courseid):
        """ GET request """
        courseid = self.verify()

        # DB request parameters
        # params = {"courseid": courseid}
        params = {"courseid": "LSINF1101-PYTHON"}  # rep
        if "taskid" in request.args:
            params["taskid"] = request.args.get("taskid")
        if "username" in request.args:
            params["username"] = request.args.get("username")
        return self.page(params)

    def page(self, params):
        msg = dumps(self.database.submissions.find(params))
        return self.response(msg)


# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from flask import request
from bson.json_util import dumps

from inginious.frontend.pages.api_auth import DataAPIPage

class SubmissionsEndpoint(DataAPIPage):
    """ Endpoint to retrieve submission data """

    def GET(self, courseid):
        """ GET request """

        admin, username = self.verify(courseid)

        # DB request parameters
        params = {"courseid": courseid}
        if not admin:
            params["username"] = username

        textfilters = ["taskid", "username", "status", "result"]
        for filt in textfilters:
            if filt in request.args:
                params[filt] = request.args.get(filt)

        if "mingrade" in request.args and "maxgrade" in request.args:
            params["grade"] = {"$gte": float(request.args["mingrade"]), "$lte": float(request.args["maxgrade"])}
        elif "mingrade" in request.args:
            params["grade"] = {"$gte": float(request.args["mingrade"])}
        elif "maxgrade" in request.args:
            params["grade"] = {"$lte": float(request.args["maxgrade"])}

        return self.page(params)

    def page(self, params):
        msg = dumps(self.database.submissions.find(params))
        return self.response(msg)

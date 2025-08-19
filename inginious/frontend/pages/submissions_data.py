# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from pydoc import describe

from flask import request, abort
from bson.json_util import dumps
from datetime import datetime

from inginious.frontend.pages.api_auth import DataAPIPage

class SubmissionsAdminEndpoint(DataAPIPage):
    """ Endpoint to retrieve submission data """

    def GET(self, courseid):
        """ GET request """
        # DB request parameters
        admin, username = self.verify(courseid)
        if admin:
            params = {"courseid": courseid}
        else:
            abort(401, description="User tokens can't be used on the admin endpoint.")

        return self.page(params)

    def page(self, params):
        textfilters = ["taskid", "username", "status", "result"]
        for filt in textfilters:
            if filt in request.args:
                params[filt] = request.args.get(filt)

        if "sort" in request.args:
            if request.args["sort"] in ["grade", "username", "status", "result", "taskid"]:
                sorting = request.args["sort"]
            elif request.args["sort"] == "date":
                sorting = "submitted_on"
            else:
                abort(400, description="Unrecognized sort value")
        else:
            sorting = "submitted_on"

        order = 1
        if "order" in request.args:
            if request.args["order"] == "-1":
                order = -1

        if "mingrade" in request.args and "maxgrade" in request.args:
            params["grade"] = {"$gte": float(request.args["mingrade"]), "$lte": float(request.args["maxgrade"])}
        elif "mingrade" in request.args:
            params["grade"] = {"$gte": float(request.args["mingrade"])}
        elif "maxgrade" in request.args:
            params["grade"] = {"$lte": float(request.args["maxgrade"])}

        if "mindate" in request.args and "maxdate" in request.args:
            params["submitted_on"] = {"$gte": datetime.strptime(request.args["mindate"], "%Y-%m-%dT%H:%M:%S"), "$lte": datetime.strptime(request.args["maxdate"], "%Y-%m-%dT%H:%M:%S")}
        elif "mindate" in request.args:
            params["submitted_on"] = {"$gte": datetime.strptime(request.args["mindate"], "%Y-%m-%dT%H:%M:%S")}
        elif "maxdate" in request.args:
            params["submitted_on"] = {"$lte": datetime.strptime(request.args["miaxate"], "%Y-%m-%dT%H:%M:%S")}

        msg = dumps(self.database.submissions.find(params).sort({sorting:order}))
        return self.response(msg)

class SubmissionsUserEndpoint(SubmissionsAdminEndpoint):
    def GET(self):
        """ GET request """
        _, username = self.verify()
        params = {"username": username}
        if "course" in request.args:
            params["courseid"] = request.args["course"]
        return self.page(params)

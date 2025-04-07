# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from flask import request
from bson.json_util import dumps

from inginious.frontend.pages.course_admin.api_auth import DataAPIPage

class UserTasksEndpoint(DataAPIPage):
    """ Endpoint to retrieve user task data """

    def GET(self, courseid):
        """ GET request """

        self.verify(courseid)

        # DB request parameters
        params = {"courseid": courseid}
        textfilters = ["taskid", "username"]
        for filt in textfilters:
            if filt in request.args:
                params[filt] = request.args.get(filt)

        if "succeeded" in request.args:
            if request.args.get("succeeded") == "true":
                params["succeeded"] = True
            elif request.args.get("succeeded") == "false":
                params["succeeded"] = False

        if "evaluation" in request.args:
            if request.args.get("evaluation") == "true":
                params["submissionid"] = {"$ne": None}
            elif request.args.get("evaluation") == "false":
                params["submissionid"] = {"$eq": None}

        if "mingrade" in request.args and "maxgrade" in request.args:
            params["grade"] = {"$gte": float(request.args["mingrade"]), "$lte": float(request.args["maxgrade"])}
        elif "mingrade" in request.args:
            params["grade"] = {"$gte": float(request.args["mingrade"])}
        elif "maxgrade" in request.args:
            params["grade"] = {"$lte": float(request.args["maxgrade"])}

        if "mintrials" in request.args and "maxtrials" in request.args:
            params["tried"] = {"$gte": float(request.args["mintrials"]), "$lte": float(request.args["maxtrials"])}
        elif "mintrials" in request.args:
            params["tried"] = {"$gte": float(request.args["mintrials"])}
        elif "maxtrialse" in request.args:
            params["tried"] = {"$lte": float(request.args["maxtrials"])}

        return self.page(params)

    def page(self, params):
        msg = dumps(self.database.user_tasks.find(params))
        return self.response(msg)


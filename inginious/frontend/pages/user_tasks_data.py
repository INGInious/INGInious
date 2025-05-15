# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
from flask import request, abort
from bson.json_util import dumps

from inginious.frontend.pages.api_auth import DataAPIPage

class UserTasksAdminEndpoint(DataAPIPage):
    """ Endpoint to retrieve user task data """

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
        textfilters = ["taskid", "username"]
        for filt in textfilters:
            if filt in request.args:
                params[filt] = request.args.get(filt)

        if "sort" in request.args:
            if request.args["sort"] in ["grade", "username", "succeeded", "evaluation", "taskid"]:
                sorting = request.args["sort"]
            elif request.args["sort"] == "trials":
                sorting = "tried"
            else:
                abort(400, description="Unrecognized sort value")
        else:
            sorting = "username"

        order = 1
        if "order" in request.args:
            if request.args["order"] == "-1":
                order = -1

        if "succeeded" in request.args:
            if request.args.get("succeeded") == "true":
                params["succeeded"] = True
            elif request.args.get("succeeded") == "false":
                params["succeeded"] = False
            else:
                abort(400, description="Unrecognized value.")

        if "evaluation" in request.args:
            if request.args.get("evaluation") == "true":
                params["submissionid"] = {"$ne": None}
            elif request.args.get("evaluation") == "false":
                params["submissionid"] = {"$eq": None}
            else:
                abort(400, description="Unrecognized value.")

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

        msg = dumps(self.database.user_tasks.find(params).sort({sorting:order}))
        return self.response(msg)

class UserTasksUserEndpoint(UserTasksAdminEndpoint):
    def GET(self):
        """ GET request """
        _, username = self.verify()
        params = {"username": username}
        if "course" in request.args:
            params["courseid"] = request.args["course"]
        return self.page(params)

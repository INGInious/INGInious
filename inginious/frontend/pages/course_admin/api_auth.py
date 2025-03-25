# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from flask import request, Response
import jwt
from datetime import datetime
import json
from bson.json_util import dumps

from inginious.frontend.pages.course_admin.utils import INGIniousAdminPage


class CourseAPIAuthPage(INGIniousAdminPage):

    def GET(self, courseid):
        """ GET request """
        auth_header = request.headers.get('Authorization')
        msg, code = self.decode_token(auth_header)
        if code == 200:
            # DB request parameters
            params = {"courseid": msg}
            if "taskid" in request.args:
                params["taskid"] = request.args.get("taskid")
            if "username" in request.args:
                params["username"] = request.args.get("username")

            if request.args.get("type") == "tasks":
                msg = dumps(self.database.user_tasks.find(params))
            elif request.args.get("type") == "submissions":
                msg = dumps(self.database.submissions.find(params))
            else:
                msg = json.dumps({"message": "No data type specified"})
        else:
            # error message
            msg = json.dumps({"message": msg})

        return self.page(msg, code)

    def decode_token(self, auth_header):
        """ Returns decoded courseid or error, and http code """
        key = str(self.app.jwt_key)

        try:
            if auth_header[:7] != "Bearer ":
                return ("token not bearer", 401)
            token = auth_header[7:]
            decoded = jwt.decode(token, key, algorithms=["HS256"])
        except:
            return ("No token", 401)

        try:
            tok_id = decoded["_id"]
            expire = datetime.strptime(decoded["expire"], "%Y-%m-%d %H:%M:%S")
            courseid = decoded["courseid"]
        except:
            return ("Invalid token", 401)

        stored_token = self.database.tokens.find_one({"$expr": {"$eq": ["$_id", {"$toObjectId": tok_id}]}})
        if stored_token is None:
            return ("Token no found", 401)

        if expire < datetime.now():
            return ("The token has expired", 403)

        return (courseid, 200)

    def page(self, msg, code):
        """ Sends response in json """
        response = Response()
        response.response = msg
        response.content_type = "text/json; charset=utf-8"
        response.status_code = code
        return response

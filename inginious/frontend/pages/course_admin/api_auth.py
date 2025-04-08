# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from flask import request, Response, abort
import jwt
import json
from bson.objectid import ObjectId

from inginious.frontend.pages.utils import INGIniousPage


class DataAPIPage(INGIniousPage):
    """ Token verification and handler for the data API """

    def __init__(self):
        super().__init__()
        self.jwt_key = str(self.app.jwt_key)

    def verify(self, courseid):
        """ verify if a token is valid """
        auth_header = request.headers.get('Authorization')
        try:
            token = auth_header.split()[1]
            decoded = jwt.decode(token, self.jwt_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            abort(403, description="The authentification token is expired.")
        except:
            abort(401, description="No authentification token found.")
        try:
            tok_id = decoded["_id"]
        except:
            abort(401, description="Invalid token.")
        if decoded["courseid"] != courseid:
            abort(401, description="Token course doesn't match requested course.")

        stored_token = self.database.tokens.find_one({'_id': ObjectId(tok_id)})
        if stored_token is None:
            abort(401, description="Authentification token not recognized.")

        return True

    def response(self, msg):
        response = Response()
        response.response = json.dumps(msg)
        response.content_type = "text/json; charset=utf-8"
        response.status_code = 200
        return response

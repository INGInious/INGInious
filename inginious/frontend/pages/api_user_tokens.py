# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from collections import OrderedDict

import flask
import jwt
from datetime import datetime
from bson.objectid import ObjectId

from inginious.frontend.pages.utils import INGIniousPage

class CourseAPIUserTokensPage(INGIniousPage):
    """ List information about api tokens """

    def GET(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        try:
            course = self.course_factory.get_course(courseid)
        except CourseNotFoundException as ex:
            raise NotFound(description=str(ex))
        username = self.user_manager.session_username()
        return self.page(course, username)

    def POST(self, courseid):
        """ POST request """
        try:
            course = self.course_factory.get_course(courseid)
        except CourseNotFoundException as ex:
            raise NotFound(description=str(ex))

        username = self.user_manager.session_username()
        user_input = flask.request.form

        if "add_token" in user_input:
            descr = user_input.get("descr", "")
            expire = user_input.get("expiration", "")
            if expire == "":
                expire = datetime.max
            else:
                expire = datetime.strptime(expire, "%Y-%m-%d %H:%M:%S")
            document = {"courseid": courseid, "exp": expire, "description": descr, "scope": "user", "username": username}
            self.database.tokens.insert_one(document)
            document["_id"] = str(document["_id"]) # otherwise can't be serialized to JSON by jwt
            msg = str(self.generate_token(document))

        else:
            tok_id = user_input.get("token_id", "")
            self.database.tokens.delete_one({'_id': ObjectId(tok_id), "courseid": courseid, "scope": "user", "username": username})
            msg = "removed"

        return self.page(course, username, msg)

    def generate_token(self, document):
        """ Give a token """
        key = str(self.app.jwt_key)
        encoded = jwt.encode(document, key, algorithm="HS256")
        return encoded

    def page(self, course, username, msg=""):
        """ Display the page """
        tokens = list(self.database.tokens.find({"courseid": course.get_id(), "scope": "user", "username": username}))
        for token in tokens:
            if token["exp"].year == datetime.max.year:
                token["exp"] = "max"
        now = datetime.now()
        return self.template_helper.render("api_user_tokens.html", course=course, msg=msg, tokens=tokens, now=now)

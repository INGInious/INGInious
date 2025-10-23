# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import json
import re

from flask import Response
from mongoengine import Q

from inginious.frontend.pages.course_admin.utils import INGIniousAdminPage
from inginious.frontend.models.user import User

class CourseAdminSearchUserPage(INGIniousAdminPage):
    """ Return users based on their username or realname """

    def GET_AUTH(self, courseid, request):  # pylint: disable=arguments-differ
        """ GET request """
        # check rights
        self.get_course_and_check_rights(courseid, allow_all_staff=True)

        request = re.escape(request) # escape for safety. Maybe this is not needed...
        query =  ((Q(username__iregex=".*" + request + ".*") or Q(realname__iregex=".*" + request + ".*"))
                  and Q(activate__exists=False, username__ne=""))

        users = User.objects(query).only("username", "realname").limit(10)
        return Response(content_type='text/json; charset=utf-8',response=json.dumps([[
            {'username': entry['username'], 'realname': entry['realname']}
            for entry in users
        ]]))

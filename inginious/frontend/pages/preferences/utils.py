# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.


from flask import redirect

from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.plugin_manager import plugin_manager


class PrefRedirectPage(INGIniousAuthPage):
    """ Redirect preferences to /profile """

    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ GET request """

        return redirect('/preferences/profile')

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        return self.GET_AUTH()
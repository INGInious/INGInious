# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Course page """
import sys
from datetime import datetime
import flask
from flask import redirect
from werkzeug.exceptions import Forbidden

from inginious.common.base import id_checker
from inginious.frontend.exceptions import ImportTasksetException
from inginious.frontend.log import get_taskset_logger
from inginious.frontend.marketplace_tasksets import get_all_marketplace_tasksets, get_marketplace_taskset
from inginious.frontend.pages.utils import INGIniousAuthPage

if sys.platform == 'win32':
    import pbs
    git = pbs.Command('git')
else:
    from sh import git  # pylint: disable=no-name-in-module


class MarketplacePage(INGIniousAuthPage):
    """ Course marketplace """

    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ GET request """
        # Change to teacher privilege when created
        if not self.user_manager.user_is_superadmin():
            raise Forbidden(description=_("You don't have superadmin rights on this taskset."))
        return self.show_page()

    def POST_AUTH(self):  # pylint: disable=arguments-differ
        """ POST request """
        # Change to teacher privilege when created
        if not self.user_manager.user_is_superadmin():
            raise Forbidden(description=_("You're not allowed to do that"))

        user_input = flask.request.form
        errors = []
        if "new_tasksetid" in user_input:
            new_tasksetid = user_input["new_tasksetid"]
            try:
                taskset = get_marketplace_taskset(user_input["tasksetid"])
                import_taskset(taskset, new_tasksetid, self.user_manager.session_username(), self.taskset_factory)
            except ImportTasksetException as e:
                errors.append(str(e))
            except:
                errors.append(_("User returned an invalid form."))
            if not errors:
                return redirect(self.app.get_homepath() + "/taskset/{}".format(new_tasksetid))
        return self.show_page(errors)

    def show_page(self, errors=None):
        """ Prepares and shows the taskset marketplace """
        if errors is None:
            errors = []
        tasksets = get_all_marketplace_tasksets()
        return self.template_helper.render("marketplace.html", tasksets=tasksets, errors=errors)


def import_taskset(taskset, new_tasksetid, username, taskset_factory):
    if not id_checker(new_tasksetid):
        raise ImportTasksetException("Course with invalid name: " + new_tasksetid)
    taskset_fs = taskset_factory.get_taskset_fs(new_tasksetid)

    if taskset_fs.exists("taskset.yaml") or taskset_fs.exists("course.yaml") or taskset_fs.exists("course.json"):
        raise ImportTasksetException("Course with id " + new_tasksetid + " already exists.")

    try:
        git.clone(taskset.get_link(), taskset_fs.prefix)
    except:
        raise ImportTasksetException(_("Couldn't clone taskset into your instance"))

    try:
        old_descriptor = taskset_factory.get_taskset_descriptor_content(new_tasksetid)
    except:
        old_descriptor ={}

    try:
        new_descriptor = {"description": old_descriptor.get("description", ""),
                          'admins': [username],
                          "accessible":  {"start": datetime.max.replace(microsecond=0), "end": datetime.max.replace(microsecond=0)},
                          "tags": old_descriptor.get("tags", {})}
        if "name" in old_descriptor:
            new_descriptor["name"] = old_descriptor["name"] + " - " + new_tasksetid
        else:
            new_descriptor["name"] = new_tasksetid
        if "toc" in old_descriptor:
            new_descriptor["toc"] = old_descriptor["toc"]
        taskset_factory.update_taskset_descriptor_content(new_tasksetid, new_descriptor)
    except:
        taskset_factory.delete_taskset(new_tasksetid)
        raise ImportTasksetException(_("An error occur while editing the taskset description"))

    get_taskset_logger(new_tasksetid).info("Course %s cloned from the marketplace.", new_tasksetid)


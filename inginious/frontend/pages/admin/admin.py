# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Admin index page"""

from flask import request, jsonify

from inginious.frontend.pages.utils import INGIniousAdministratorPage


class AdministrationUsersPage(INGIniousAdministratorPage):
    """User Admin page."""

    def GET_AUTH(self, *args, **kwargs):
        """ Display admin users page """
        return self.show_page()

    def POST_AUTH(self, *args, **kwargs):
        """ Display admin users page"""
        return self.show_page()

    def show_page(self):
        """Display page"""

        page = int(request.form.get("page")) if request.form.get("page") is not None else 1
        user_per_page = 10  # TODO probably better to let user define user_per_page
        all_users = self.user_manager.get_users_info(usernames=None, limit=user_per_page, skip=(page-1)*user_per_page)
        size_users = self.user_manager.get_users_count()
        pages = size_users // user_per_page + (size_users % user_per_page > 0) if user_per_page > 0 else 1

        return self.template_helper.render("admin/admin_users.html", all_users=all_users,
                                           number_of_pages=pages, page_number=page)


class AdministrationUserActionPage(INGIniousAdministratorPage):
    """Action on User Admin page."""

    def POST_AUTH(self, *args, **kwargs):
        username = request.form.get("username")
        action = request.form.get("action")
        feedback = None
        if action == "activate":
            activate_hash = self.user_manager.get_user_activate_hash(username)
            if not self.user_manager.activate_user(activate_hash):
                feedback = _("User not found")
        elif action == "delete":
            if not self.user_manager.delete_user(username):
                feedback = _("Impossible to delete this user")
        elif action == "get_bindings":
            user_info = self.user_manager.get_user_info(username)
            return jsonify(user_info.bindings if user_info is not None else {})
        elif action == "revoke_binding":
            binding_id = request.form.get("binding_id")
            error, feedback = self.user_manager.revoke_binding(username, binding_id)
        elif action == "add_user":
            realname = request.form.get("realname")
            email = request.form.get("email")
            password = request.form.get("password")
            feedback = self.user_manager.create_user({
                "username": username,
                "realname": realname,
                "email": email,
                "password": password,
                "bindings": {},
                "language": "en",
                "code_indentation": "4"})
        else:
            feedback = _("Unknown action.")
        if feedback:
            return jsonify({"error": True, "message": feedback})
        return jsonify({"message": ""})

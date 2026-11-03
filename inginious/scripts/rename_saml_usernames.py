#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

"""
Renames the accounts bound to a SAML2 auth method to the username given by its ``default_username`` configuration.
Only displays the changes unless --apply is given. Stop the webapp and backup the database before applying.
A failed run can safely be launched again, as the account itself is renamed last.
"""
import argparse
import glob
import os

from pymongo import MongoClient

from inginious.common.base import get_default_username, load_json_or_yaml
from inginious.scripts.database_update import get_config

SAML_PLUGIN = "inginious.frontend.plugins.auth.saml2_auth"
USERNAME_FIELDS = [("user_tasks", "username"), ("lis_outcome_queue", "username"), ("lti_grade_queue", "username")]
USERNAME_LIST_FIELDS = [("submissions", "username"), ("courses", "students"), ("audiences", "students"),
                        ("audiences", "tutors"), ("groups", "students")]
COURSE_USERNAME_ENTRIES = ["admins", "tutors", "registration_ac_list"]


def plan_renames(database, auth_configs, superadmins):
    """
    :return: a tuple (renames, skipped). renames is a list of user documents with their new username added
        as "new_username", skipped a list of (user document, reason) of the accounts that are left untouched.
    """
    candidates, skipped = [], []
    for auth_config in auth_configs:
        for user in database.users.find({"bindings." + auth_config["id"]: {"$exists": True}}):
            uid, additional = user["bindings"][auth_config["id"]]
            user["new_username"] = get_default_username(auth_config, uid, user["email"], additional)
            if user["username"] in superadmins:
                skipped.append((user, "superadmin"))
            elif not user["new_username"]:
                skipped.append((user, "no identifier in binding"))
            elif user["new_username"] != user["username"]:
                candidates.append(user)

    renames = []
    for user in candidates:
        same_target = [other for other in candidates if other["new_username"] == user["new_username"]]
        if len(same_target) > 1:
            skipped.append((user, "several accounts for " + user["new_username"]))
        elif database.users.find_one({"username": user["new_username"]}):
            skipped.append((user, "username " + user["new_username"] + " already taken"))
        else:
            renames.append(user)
    return renames, skipped


def apply_rename(database, user):
    """ Renames a single account and everything that refers to it """
    old, new = user["username"], user["new_username"]
    # An account without username has no data yet, and matching on it would alter the data of other such accounts
    if old:
        for collection, field in USERNAME_FIELDS:
            database[collection].update_many({field: old}, {"$set": {field: new}})
        for collection, field in USERNAME_LIST_FIELDS:
            for document in database[collection].find({field: old}, {field: 1}):
                usernames = [new if username == old else username for username in document[field]]
                database[collection].update_one({"_id": document["_id"]}, {"$set": {field: usernames}})
    database.sessions.update_many({"email": user["email"]}, {"$set": {"username": new}})
    database.users.update_one({"_id": user["_id"]}, {"$set": {"username": new}})


def find_course_references(tasks_directory, usernames):
    """ :return: a list of (course file, entry, username) for the usernames used in the course files, that are not
        stored in the database """
    references = []
    for path in sorted(glob.glob(os.path.join(tasks_directory, "*", "course.yaml"))):
        course = load_json_or_yaml(path)
        for entry in COURSE_USERNAME_ENTRIES:
            references += [(path, entry, username) for username in course.get(entry) or [] if username in usernames]
    return references


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", help="Configuration file", default=os.environ.get("INGINIOUS_WEBAPP_CONFIG", ""))
    parser.add_argument("--apply", help="Rename the accounts instead of only displaying the changes", action="store_true")
    args = parser.parse_args()

    config = get_config(args.config)
    auth_configs = [plugin for plugin in config.get("plugins") or []
                    if plugin.get("plugin_module") == SAML_PLUGIN and plugin.get("default_username")]
    if not auth_configs:
        parser.error("No SAML2 auth method with a default_username entry in the configuration")

    mongo_client = MongoClient(host=config.get("mongo_opt", {}).get("host", "localhost"))
    database = mongo_client[config.get("mongo_opt", {}).get("database", "INGInious")]

    renames, skipped = plan_renames(database, auth_configs, config.get("superadmins") or [])
    for user in renames:
        print("RENAME {!r} -> {!r} ({})".format(user["username"], user["new_username"], user["email"]))
        if args.apply:
            apply_rename(database, user)
    for user, reason in skipped:
        print("SKIP {!r} ({}): {}".format(user["username"], user["email"], reason))

    references = find_course_references(config.get("tasks_directory", "./tasks"), {user["username"] for user in renames})
    for path, entry, username in references:
        print("UPDATE MANUALLY {}: {!r} in {}".format(path, username, entry))

    print("{} {} accounts, skipped {}, {} course file entries to update manually".format(
        "Renamed" if args.apply else "Would rename", len(renames), len(skipped), len(references)))


if __name__ == "__main__":
    main()

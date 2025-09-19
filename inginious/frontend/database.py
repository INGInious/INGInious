# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import pymongo

from gridfs import GridFS
from pymongo import MongoClient
from bson.codec_options import CodecOptions

DB_VERSION = 18
_mongo_client = None

# Exposing each collection separately is needed to avoid importing a None value in other modules
courses = None
submissions = None
audiences = None
groups = None
user_tasks = None
gridfs = None
sessions = None
lis_outcome_queue = None
lti_grade_queue = None
users = None

def init_app(config):
    """ Initialize the webapp """
    global _mongo_client, courses, submissions, audiences, groups, user_tasks, gridfs, sessions, lis_outcome_queue, lti_grade_queue, users

    _mongo_client = MongoClient(host=config.get('host', 'localhost'))
    database =  _mongo_client.get_database(config.get('database', 'INGInious'), codec_options=CodecOptions(tz_aware=True))

    # Init database if needed
    db_version = database.db_version.find_one({})
    if db_version is None:
        database.submissions.create_index([("username", pymongo.ASCENDING)])
        database.submissions.create_index([("courseid", pymongo.ASCENDING)])
        database.submissions.create_index([("courseid", pymongo.ASCENDING), ("taskid", pymongo.ASCENDING)])
        database.submissions.create_index([("submitted_on", pymongo.DESCENDING)])  # sort speed
        database.submissions.create_index([("status", pymongo.ASCENDING)])  # update_pending_jobs speedup
        database.user_tasks.create_index([("username", pymongo.ASCENDING), ("courseid", pymongo.ASCENDING), ("taskid", pymongo.ASCENDING)], unique=True)
        database.user_tasks.create_index([("username", pymongo.ASCENDING), ("courseid", pymongo.ASCENDING)])
        database.user_tasks.create_index([("courseid", pymongo.ASCENDING), ("taskid", pymongo.ASCENDING)])
        database.user_tasks.create_index([("courseid", pymongo.ASCENDING)])
        database.user_tasks.create_index([("username", pymongo.ASCENDING)])
        database.db_version.insert_one({"db_version": DB_VERSION})
    elif db_version.get("db_version", 0) != DB_VERSION:
        raise Exception("Please update the database before running INGInious")

    courses = database.courses
    audiences = database.audiences
    groups = database.groups
    user_tasks = database.user_tasks
    sessions = database.sessions
    lis_outcome_queue = database.lis_outcome_queue
    lti_grade_queue = database.lti_grade_queue
    users = database.users
    submissions = database.submissions

    gridfs = GridFS(database)

def close():
    global _mongo_client
    _mongo_client.close()
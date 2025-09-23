# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Manages submissions """
import io
import gettext
import logging
import os.path
import tarfile
import tempfile
import time
from typing import Dict, List
import bson
import pymongo

import flask
from datetime import datetime, timezone
from bson.objectid import ObjectId
from pymongo.collection import ReturnDocument

import inginious.common.custom_yaml
from inginious.frontend.parsable_text import ParsableText
from inginious.frontend import database
from inginious.frontend.user_manager import user_manager
from inginious.frontend.plugin_manager import plugin_manager


class WebAppSubmissionManager:
    """ Manages submissions. Communicates with the database and the client. """

    def __init__(self, client, lti_score_publishers):
        """
        :type client: inginious.client.client.AbstractClient
        :type database: pymongo.database.Database
        :type gridfs: gridfs.GridFS
        :return:
        """
        self._client = client
        self._logger = logging.getLogger("inginious.webapp.submissions")
        self._lti_score_publishers = lti_score_publishers

    def _job_done_callback(self, submissionid, task, result, grade, problems, tests, custom, state, archive, stdout,
                           stderr, task_dispenser,  newsub=True):
        """ Callback called by Client when a job is done. Updates the submission in the database with the data returned after the completion of the
        job """
        submission = self.get_submission(submissionid, False)

        submission = self.get_input_from_submission(submission)

        data = {
            "status": ("done" if result[0] == "success" or result[0] == "failed" else "error"),
            # error only if error was made by INGInious
            "result": result[0],
            "grade": grade,
            "text": result[1],
            "tests": tests,
            "problems": problems,
            "archive": (database.gridfs.put(archive) if archive is not None else None),
            "custom": custom,
            "state": state,
            "stdout": stdout,
            "stderr": stderr
        }

        unset_obj = {
            "jobid": "",
            "ssh_host": "",
            "ssh_port": "",
            "ssh_user": "",
            "ssh_password": ""
        }

        # Save submission to database
        try:
            submission = database.submissions.find_one_and_update(
                {"_id": submission["_id"]},
                {"$set": data, "$unset": unset_obj},
                return_document=ReturnDocument.AFTER
            )

            for username in submission["username"]:
                user_manager.update_user_stats(username, task, submission, result[0], grade, state, newsub, task_dispenser)

        # Check for size as it also takes the MongoDB command into consideration
        except pymongo.errors.DocumentTooLarge:
            data = {"status": "error", "text": _("Maximum submission size exceeded. Check feedback, stdout, stderr and state."), "grade": 0.0}
            submission = database.submissions.find_one_and_update(
                {"_id": submission["_id"]},
                {"$set": data, "$unset": unset_obj},
                return_document=ReturnDocument.AFTER
            )

        plugin_manager.call_hook("submission_done", submission=submission, archive=archive, newsub=newsub)

        if "lti_version" in submission:
            lti_score_publisher = self._lti_score_publishers.get(submission["lti_version"], None)
            if lti_score_publisher:
                lti_score_publisher.add(submission)

    def _before_submission_insertion(self, task, inputdata, debug, obj):
        """
        Called before any new submission is inserted into the database. Allows you to modify obj, the new document that will be inserted into the
        database. Should be overridden in subclasses.

        :param task: Task related to the submission
        :param inputdata: input of the student
        :param debug: True, False or "ssh". See add_job.
        :param obj: the new document that will be inserted
        """
        username = user_manager.session_username()
        course = task.get_course()
        is_group_task =course.get_task_dispenser().get_group_submission(task.get_id())

        if is_group_task and not user_manager.has_staff_rights_on_course(course, username):
            group = database.groups.find_one({"courseid": course.get_id(), "students": username})
            obj.update({"username": group["students"]})
        else:
            obj.update({"username": [username]})

        lti_info = user_manager.session_lti_info()
        if lti_info is not None and course.lti_send_back_grade():
            lti_score_publisher = self._lti_score_publishers.get(lti_info["version"], None)
            if lti_score_publisher:
                obj.update({"lti_version": lti_info["version"]})
                lti_score_publisher.tag_submission(obj, lti_info)

        # If we are submitting for a group, send the group (user list joined with ",") as username
        if "group" not in [p.get_id() for p in task.get_problems()]:  # do not overwrite
            username = user_manager.session_username()
            if is_group_task and not user_manager.has_staff_rights_on_course(course, username):
                group = database.groups.find_one({"courseid": course.get_id(), "students": username})
                users = database.users.find({"username": {"$in": group["students"]}})
                inputdata["@username"] = ','.join(group["students"])
                inputdata["@email"] = ','.join([user["email"] for user in users])

    def _after_submission_insertion(self, task, inputdata, debug, submission, submissionid, task_dispenser):
        """
                Called after any new submission is inserted into the database, but before starting the job.  Should be overridden in subclasses.
                :param task: Task related to the submission
                :param inputdata: input of the student
                :param debug: True, False or "ssh". See add_job.
                :param submission: the new document that was inserted (do not contain _id)
                :param submissionid: submission id of the submission
                """

        return self._delete_exceeding_submissions(user_manager.session_username(), task, task_dispenser)

    def replay_job(self, task, submission, task_dispenser, copy=False, debug=False):
        """
        Replay a submission: add the same job in the queue, keeping submission id, submission date and input data
        :param submission: Submission to replay
        :param copy: If copy is true, the submission will be copied to admin submissions before replay
        :param debug: If debug is true, more debug data will be saved
        """
        if not user_manager.session_logged_in():
            raise Exception("A user must be logged in to submit an object")

        # Don't enable ssh debug
        ssh_callback = lambda host, port, user, password: self._handle_ssh_callback(submission["_id"], host, port, user, password)

        # Load input data and add username to dict
        inputdata = bson.BSON.decode(database.gridfs.get(submission["input"]).read())

        if not copy:
            submissionid = submission["_id"]
            username = submission["username"][0]  # TODO: this may be inconsistent with add_job

            # Remove the submission archive : it will be regenerated
            if submission.get("archive", None) is not None:
                database.gridfs.delete(submission["archive"])
        else:
            del submission["_id"]
            username = user_manager.session_username()
            submission["username"] = [username]
            submission["submitted_on"] = datetime.now(tz=timezone.utc)
            my_user_task = database.user_tasks.find_one(
                {"courseid": task.get_course_id(), "taskid": task.get_id(), "username": username},
                {"tried": 1, "_id": 0})
            tried_count = my_user_task["tried"]
            inputdata["@attempts"] = str(tried_count + 1)
            inputdata["@username"] = username
            inputdata["@email"] = user_manager.session_email()
            inputdata["@lang"] = user_manager.session_language()
            submission["input"] = database.gridfs.put(bson.BSON.encode(inputdata))
            submission["tests"] = {}  # Be sure tags are reinitialized
            submission["user_ip"] = flask.request.remote_addr
            submissionid = database.submissions.insert_one(submission).inserted_id

        # Clean the submission document in db
        database.submissions.update_one(
            {"_id": submission["_id"]},
            {"$set": {"status": "waiting", "response_type": task.get_response_type()},
             "$unset": {"result": "", "grade": "", "text": "", "tests": "", "problems": "", "archive": "", "state": "",
                        "custom": ""}
             })

        jobid = self._client.new_job(1, task, inputdata,
                                     (lambda result, grade, problems, tests, custom, state, archive, stdout, stderr:
                                      self._job_done_callback(submissionid, task, result, grade, problems, tests,
                                                              custom, state, archive, stdout, stderr, task_dispenser, copy)),
                                     "Frontend - {}".format(submission["username"]), debug, ssh_callback)


        database.submissions.update_one(
            {"_id": submission["_id"], "status": "waiting"},
            {"$set": {"jobid": jobid,"last_replay": datetime.now()}}
        )

        if not copy:
            self._logger.info("Replaying submission %s - %s - %s - %s", submission["username"], submission["courseid"],
                              submission["taskid"], submission["_id"])
        else:
            self._logger.info("Copying submission %s - %s - %s - %s as %s", submission["username"],
                              submission["courseid"],
                              submission["taskid"], submission["_id"], user_manager.session_username())

    def get_available_environments(self) -> Dict[str, List[str]]:
        """:return a list of available environments """
        return self._client.get_available_environments()

    def get_submission(self, submissionid, user_check=True):
        """ Get a submission from the database """
        sub = database.submissions.find_one({'_id': ObjectId(submissionid)})
        if user_check and not self.user_is_submission_owner(sub):
            return None
        return sub

    def add_job(self, task, inputdata, task_dispenser, debug=False):
        """
        Add a job in the queue and returns a submission id.
        :param task:  Task instance
        :type task: inginious.frontend.tasks.Task
        :param inputdata: the input as a dictionary
        :type inputdata: dict
        :param debug: If debug is true, more debug data will be saved
        :type debug: bool or string
        :returns: the new submission id and the removed submission id
        """
        if not user_manager.session_logged_in():
            raise Exception("A user must be logged in to submit an object")

        username = user_manager.session_username()

        # Prevent student from submitting several submissions together
        waiting_submission = database.submissions.find_one({
            "courseid": task.get_course_id(),
            "taskid": task.get_id(),
            "username": username,
            "status": "waiting"})

        if waiting_submission is not None:
            raise Exception("A submission is already pending for this task!")

        obj = {
            "courseid": task.get_course_id(),
            "taskid": task.get_id(),
            "status": "waiting",
            "submitted_on": datetime.now(tz=timezone.utc),
            "username": [username],
            "response_type": task.get_response_type(),
            "user_ip": flask.request.remote_addr
        }

        # Send additional data to the client in inputdata. For now, the username and the language. New fields can be added with the
        # new_submission hook
        inputdata["@username"] = username
        inputdata["@email"] = user_manager.session_email()
        inputdata["@lang"] = user_manager.session_language()
        inputdata["@time"] = str(obj["submitted_on"])
        my_user_task = database.user_tasks.find_one(
            {"courseid": task.get_course_id(), "taskid": task.get_id(), "username": username}, {"tried": 1, "_id": 0})
        tried_count = my_user_task["tried"]
        inputdata["@attempts"] = str(tried_count + 1)
        # Retrieve input random
        states = database.user_tasks.find_one(
            {"courseid": task.get_course_id(), "taskid": task.get_id(), "username": username},
            {"random": 1, "state": 1})
        inputdata["@random"] = states["random"] if "random" in states else []
        inputdata["@state"] = states["state"] if "state" in states else ""

        # Send LTI information to the client except "consumer_key"
        lti_info = user_manager.session_lti_info()
        if lti_info:
            for key in lti_info:
                if key == "consumer_key" or key.startswith("outcome"): # Skip "consumer_key" and "outcome*"
                    continue
                self._logger.debug("LTI data : %s, %s",key, lti_info[key])
                # Add @lti_ prefix
                key_str = "@lti_" + key
                inputdata[key_str] = lti_info[key]

        plugin_manager.call_hook("new_submission", submission=obj, inputdata=inputdata)

        self._before_submission_insertion(task, inputdata, debug, obj)
        obj["input"] = database.gridfs.put(bson.BSON.encode(inputdata))
        submissionid = database.submissions.insert_one(obj).inserted_id
        to_remove = self._after_submission_insertion(task, inputdata, debug, obj, submissionid, task_dispenser)

        ssh_callback = lambda host, port, user, password: self._handle_ssh_callback(submissionid, host, port, user, password)

        jobid = self._client.new_job(0, task, inputdata,
                                     (lambda result, grade, problems, tests, custom, state, archive, stdout, stderr:
                                      self._job_done_callback(submissionid, task, result, grade, problems, tests,
                                                              custom, state, archive, stdout, stderr, task_dispenser, True)),
                                     "Frontend - {}".format(username), debug, ssh_callback)

        database.submissions.update_one(
            {"_id": submissionid, "status": "waiting"},
            {"$set": {"jobid": jobid}}
        )

        self._logger.info("New submission from %s - %s - %s/%s - %s", user_manager.session_username(),
                          user_manager.session_email(), task.get_course_id(), task.get_id(),
                          flask.request.remote_addr)

        return submissionid, to_remove

    def _delete_exceeding_submissions(self, username, task, task_dispenser):
        """ Deletes exceeding submissions from the database, to keep the database relatively small """
        max_submissions_bound = -1
        no_stored_submissions = task_dispenser.get_no_stored_submissions(task.get_id())
        if max_submissions_bound <= 0:
            max_submissions = no_stored_submissions
        elif no_stored_submissions <= 0:
            max_submissions = max_submissions_bound
        else:
            max_submissions = min(max_submissions_bound, no_stored_submissions)

        if max_submissions <= 0:
            return []
        tasks = list(database.submissions.find(
            {"username": username, "courseid": task.get_course_id(), "taskid": task.get_id()},
            projection=["_id", "status", "result", "grade", "submitted_on"],
            sort=[('submitted_on', pymongo.ASCENDING)]))

        # List the entries to keep
        to_keep = set([])

        if task_dispenser.get_evaluation_mode(task.get_id()) == 'best':
            # Find the best "status"="done" and "result"="success"
            idx_best = -1
            for idx, val in enumerate(tasks):
                if val["status"] == "done":
                    if idx_best == -1 or tasks[idx_best]["grade"] < val["grade"]:
                        idx_best = idx

            # Always keep the best submission
            if idx_best != -1:
                to_keep.add(tasks[idx_best]["_id"])

        # Always keep running submissions
        for val in tasks:
            if val["status"] == "waiting":
                to_keep.add(val["_id"])

        while len(to_keep) < max_submissions and len(tasks) > 0:
            to_keep.add(tasks.pop()["_id"])

        to_delete = {val["_id"] for val in tasks}.difference(to_keep)
        database.submissions.delete_many({"_id": {"$in": list(to_delete)}})

        return list(map(str, to_delete))

    def get_input_from_submission(self, submission, only_input=False):
        """
            Get the input of a submission. If only_input is False, returns the full submissions with a dictionnary object at the key "input".
            Else, returns only the dictionnary.
        """
        # do not recharge if not needed
        if isinstance(submission["input"], dict):
            return submission["input"] if only_input else submission

        inp = bson.BSON.decode(database.gridfs.get(submission['input']).read())
        if only_input:
            return inp
        else:
            submission["input"] = inp
            return submission

    def get_feedback_from_submission(self, submission, only_feedback=False, show_everything=False):
        """
            Get the input of a submission. If only_input is False, returns the full submissions with a dictionnary object at the key "input".
            Else, returns only the dictionnary.

            If show_everything is True, feedback normally hidden is shown.
        """
        if only_feedback:
            submission = {"text": submission.get("text", None), "problems": dict(submission.get("problems", {}))}
        if "text" in submission:
            submission["text"] = ParsableText(submission["text"], submission["response_type"], show_everything).parse()
        if "problems" in submission:
            for problem in submission["problems"]:
                if isinstance(submission["problems"][problem], str):  # fallback for old-style submissions
                    submission["problems"][problem] = (
                    submission.get('result', 'crash'), ParsableText(submission["problems"][problem],
                                                                    submission["response_type"],
                                                                    show_everything).parse())
                else:  # new-style submission

                    try:
                        submission["problems"][problem] = (
                        submission["problems"][problem][0], ParsableText(submission["problems"][problem][1],
                                                                     submission["response_type"],
                                                                     show_everything).parse())
                    except TypeError:
                        self._logger.error(
                            "Something went wrong with provided feedback for submission %s", str(submission["_id"])
                            )
                        submission["problems"][problem] = (
                            'crash', ParsableText(_("Feedback is badly formatted."),
                                                                    submission["response_type"],
                                                                    show_everything).parse())
        return submission

    def is_running(self, submissionid, user_check=True):
        """ Tells if a submission is running/in queue """
        submission = self.get_submission(submissionid, user_check)
        return submission["status"] == "waiting"

    def is_done(self, submissionid_or_submission, user_check=True):
        """ Tells if a submission is done and its result is available """
        # TODO: not a very nice way to avoid too many database call. Should be refactored.
        if isinstance(submissionid_or_submission, dict):
            submission = submissionid_or_submission
        else:
            submission = self.get_submission(submissionid_or_submission, False)
        if user_check and not self.user_is_submission_owner(submission):
            return None
        return submission["status"] == "done" or submission["status"] == "error"

    def kill_running_submission(self, submissionid, user_check=True):
        """ Attempt to kill the remote job associated with this submission id.
        :param submissionid:
        :param user_check: Check if the current user owns this submission
        :return: True if the message asking to kill the job was sent, False if an error occurred
        """
        submission = self.get_submission(submissionid, user_check)
        if not submission:
            self._logger.warning("Was asked to kill submission with id %s, but it cannot be found in the database", str(submissionid))
            return False
        if "jobid" not in submission:
            self._logger.warning("Was asked to kill submission with id %s, but it does not seem to be running", str(submissionid))
            return False

        self._client.kill_job(submission["jobid"])
        return True

    def user_is_submission_owner(self, submission):
        """ Returns true if the current user is the owner of this jobid, false else """
        if not user_manager.session_logged_in():
            raise Exception("A user must be logged in to verify if he owns a jobid")

        return user_manager.session_username() in submission["username"]

    def get_user_submissions(self, task):
        """ Get all the user's submissions for a given task """
        if not user_manager.session_logged_in():
            raise Exception("A user must be logged in to get his submissions")

        cursor = database.submissions.find({"username": user_manager.session_username(),
                                                  "taskid": task.get_id(), "courseid": task.get_course_id()})
        cursor.sort([("submitted_on", -1)])
        return list(cursor)

    def get_user_last_submissions(self, limit=5, mongo_request=None):
        """ Get last submissions of a user """
        if mongo_request is None:
            mongo_request = {}

        mongo_request.update({"username": user_manager.session_username()})

        # Before, submissions were first sorted by submission date, then grouped
        # and then resorted by submission date before limiting. Actually, grouping
        # and pushing, keeping the max date, followed by result filtering is much more
        # efficient
        data = database.submissions.aggregate([
            {"$match": mongo_request},
            {"$group": {"_id": {"courseid": "$courseid", "taskid": "$taskid"},
                        "submitted_on": {"$max": "$submitted_on"},
                        "submissions": {"$push": {
                            "_id": "$_id",
                            "result": "$result",
                            "status": "$status",
                            "courseid": "$courseid",
                            "taskid": "$taskid",
                            "submitted_on": "$submitted_on"
                        }},
                        }},
            {"$project": {
                "submitted_on": 1,
                "submissions": {
                    # This could be replaced by $filter if mongo v3.2 is set as dependency
                    "$setDifference": [
                        {"$map": {
                            "input": "$submissions",
                            "as": "submission",
                            "in": {
                                "$cond": [{"$eq": ["$submitted_on", "$$submission.submitted_on"]}, "$$submission",
                                          False]
                            }
                        }},
                        [False]
                    ]
                }
            }},
            {"$sort": {"submitted_on": pymongo.DESCENDING}},
            {"$limit": limit}
        ])

        return [item["submissions"][0] for item in data]

    def get_submission_archive(self, course, submissions, sub_folders, archive_file=None, simplify=False):
        """
        :param course: the course object linked to the submission
        :param submissions: a list of submissions
        :param sub_folders: a list of folders in which to place the submission. For example,
            ["taskid", "submissionid"] place each submission inside a folder taskid/submissionid/ (with taskid replaced
            with the actual task id, the same being true for submissionid). The possible values are:
            - "taskid": replaced by the task id
            - "submissionid": replaced by the submission id
            - "audience": replaced by the name of the audience "audiencedesc_(audienceid)"
            - "group": replaced by the list of username who submitted
            - "username": replaced by the username
            Some of these (like "username" and "audience") are not unique for a submission. If they are multiple answers
            possible, the files are duplicated at multiple locations.

            For example: given a submission #9083081 by the group ["a", "b"], and a sub_folders value of
            ["username", "submissionid"], the archive will contain two folders:
            - a/9083081/
            - b/9083081/
        :return: a file-like object containing a tgz archive of all the submissions
        """

        if "audience" in sub_folders:
            student_audiences = user_manager.get_course_audiences_per_student(course)

        def generate_paths(sub, path, remaining_sub_folders):
            if len(remaining_sub_folders) == 0:
                yield path
            elif remaining_sub_folders[0] == "taskid":
                yield from generate_paths(sub, path + [sub['taskid']], remaining_sub_folders[1:])
            elif remaining_sub_folders[0] == "username":
                for username in sub["username"]:
                    yield from generate_paths(sub, path + [username], remaining_sub_folders[1:])
            elif remaining_sub_folders[0] == "audience":
                for username in sub["username"]:
                    if username in student_audiences:
                        for audience in student_audiences[username]:
                            yield from generate_paths(sub, path +
                                                      [(audience["description"] +" (" + str(audience["_id"]) + ")").replace(" ", "_")],
                                                      remaining_sub_folders[1:])
                    else:
                        yield from generate_paths(sub, path + ['-'.join(sorted(sub['username']))], remaining_sub_folders[1:])
            elif remaining_sub_folders[0] == "group":
                yield from generate_paths(sub, path + ['-'.join(sorted(sub['username']))], remaining_sub_folders[1:])
            elif remaining_sub_folders[0] == "submissionid":
                yield from generate_paths(sub, path + [str(sub['_id'])], remaining_sub_folders[1:])
            elif remaining_sub_folders[0] == "submissiondateid":
                yield from generate_paths(sub, path + [(sub['submitted_on']).isoformat()], remaining_sub_folders[1:])
            else:
                yield from generate_paths(sub, path + [remaining_sub_folders[0]], remaining_sub_folders[1:])

        file_to_put = {}
        for submission in submissions:
            # generate all paths where the submission must belong
            for base_path in generate_paths(submission, [], sub_folders):
                base_path = "/".join(base_path)
                path, i = base_path, 1
                while path in file_to_put:
                    path = base_path + "-" + str(i)
                    i += 1
                file_to_put[path] = submission

        tmpfile = archive_file if archive_file is not None else tempfile.TemporaryFile()
        tar = tarfile.open(fileobj=tmpfile, mode='w:gz')
        error = ""

        # NOTE there is a bit of redundancy here: if a submission is in multiple folder, the file will be reprocessed
        # each time. Not sure optimizing this is necessary.
        for base_path, submission in file_to_put.items():
            try:
                submission = self.get_input_from_submission(submission)
                submission_yaml = io.BytesIO(inginious.common.custom_yaml.dump(submission).encode('utf-8'))
                submission_yaml_fname = base_path + '/submission.test'

                # Avoid putting two times the same submission on the same place
                if submission_yaml_fname not in tar.getnames():

                    info = tarfile.TarInfo(name=submission_yaml_fname)
                    info.size = submission_yaml.getbuffer().nbytes
                    info.mtime = time.mktime(submission["submitted_on"].timetuple())

                    # Add file in tar archive
                    tar.addfile(info, fileobj=submission_yaml)

                    # If there is an archive, add it too
                    if 'archive' in submission and submission['archive'] is not None and submission['archive'] != "":
                        subfile = database.gridfs.get(submission['archive'])
                        subtar = tarfile.open(fileobj=subfile, mode="r:gz")

                        for member in subtar.getmembers():
                            subtarfile = subtar.extractfile(member)
                            member.name = base_path + "/archive/" + member.name
                            tar.addfile(member, subtarfile)

                        subtar.close()
                        subfile.close()

                    # If there files that were uploaded by the student, add them
                    if submission['input'] is not None:
                        for pid, problem in submission['input'].items():
                            if isinstance(problem, dict) and "filename" in problem:
                                # Get the extension (match extensions with more than one dot too)
                                DOUBLE_EXTENSIONS = ['.tar.gz', '.tar.bz2', '.tar.bz', '.tar.xz']
                                ext = ""
                                if not problem['filename'].endswith(tuple(DOUBLE_EXTENSIONS)):
                                    _, ext = os.path.splitext(problem['filename'])
                                else:
                                    for t_ext in DOUBLE_EXTENSIONS:
                                        if problem['filename'].endswith(t_ext):
                                            ext = t_ext

                                subfile = io.BytesIO(problem['value'])
                                if simplify and (pid + ext) != "submission.test":
                                    taskfname = base_path + '/' + pid + ext
                                else:
                                    taskfname = base_path + '/uploaded_files/' + pid + ext

                                # Generate file info
                                info = tarfile.TarInfo(name=taskfname)
                                info.size = subfile.getbuffer().nbytes
                                info.mtime = time.mktime(submission["submitted_on"].timetuple())

                                # Add file in tar archive
                                tar.addfile(info, fileobj=subfile)

            except Exception as e:
                error = str(submission["_id"])
                break

        # Close tarfile and put tempfile cursor at 0
        tar.close()
        tmpfile.seek(0)
        return tmpfile, error

    def _handle_ssh_callback(self, submission_id, host, port, user, password):
        """ Handles the creation of a remote ssh server """
        if host is not None:  # ignore late calls (a bit hacky, but...)
            obj = {
                "ssh_host": host,
                "ssh_port": port,
                "ssh_user": user,
                "ssh_password": password
            }
            database.submissions.update_one({"_id": submission_id}, {"$set": obj})

    def get_job_queue_snapshot(self):
        """ Get a snapshot of the remote backend job queue. May be a cached version.
        May not contain recent jobs. May return None if no snapshot is available

        :return: a tuple of two lists (None, None):

        - ``jobs_running`` : a list of tuples in the form
          (job_id, is_current_client_job, info, launcher, started_at, max_time)
          where

            - job_id is a job id. It may be from another client.
            - is_current_client_job is a boolean indicating if the client that asked the request has started the job
            - agent_name is the agent name
            - info is "courseid/taskid"
            - launcher is the name of the launcher, which may be anything
            - started_at the time (in seconds since UNIX epoch) at which the job started
            - max_time the maximum time that can be used, or -1 if no timeout is set

        - ``jobs_waiting`` : a list of tuples in the form
          (job_id, is_current_client_job, info, launcher, max_time)
          where

            - job_id is a job id. It may be from another client.
            - is_current_client_job is a boolean indicating if the client that asked the request has started the job
            - info is "courseid/taskid"
            - launcher is the name of the launcher, which may be anything
            - max_time the maximum time that can be used, or -1 if no timeout is set

        """
        return self._client.get_job_queue_snapshot()

    def get_job_queue_info(self, jobid):
        """Get job queue info
        :param jobid: the JOB id (not the submission id!). You should retrieve it before calling this function by
        calling ``get_submission(...)["job_id"]``.
        :return: If the submission is in the queue, then returns a tuple (nb tasks before running (or ``-1`` if running), approx wait time in seconds)
        Else, returns None
        """
        return self._client.get_job_queue_info(jobid)


def update_pending_jobs():
    """ Updates pending jobs status in the database """

    # Updates the submissions that are waiting with the status error, as the server restarted
    database.submissions.update_many({'status': 'waiting'},
                                {"$unset": {'jobid': ""},
                                 "$set": {'status': 'error', 'grade': 0.0, 'text': 'Internal error. Server restarted'}})

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Manages submissions """
import io
import logging
import os.path
import tarfile
import tempfile
import time
from typing import Dict, List
import pymongo

import flask
from datetime import datetime, timezone

import inginious.common.custom_yaml
from inginious.frontend.parsable_text import ParsableText
from inginious.frontend.plugins import plugin_manager
from inginious.frontend.models.user_task import UserTask
from inginious.frontend.models.user import User
from inginious.frontend.models.submission import Submission
from inginious.frontend.models.group import Group


class WebAppSubmissionManager:
    """ Manages submissions. Communicates with the database and the client. """

    def __init__(self, client, user_manager, lti_score_publishers):
        """
        :type client: inginious.client.client.AbstractClient
        :type user_manager: inginious.frontend.user_manager.UserManager
        :return:
        """
        self._client = client
        self._user_manager = user_manager
        self._logger = logging.getLogger("inginious.webapp.submissions")
        self._lti_score_publishers = lti_score_publishers

        # Updates the submissions that are waiting with the status error, as the server restarted
        Submission.objects(status="waiting").update(
            status='error', grade=0.0, text='Internal error. Server restarted', unset__jobid=True
        )

    def _job_done_callback(self, submissionid, course, task, result, grade, problems, tests, custom, state, archive, stdout,
                           stderr, task_dispenser,  newsub=True):
        """ Callback called by Client when a job is done. Updates the submission in the database with the data returned after the completion of the
        job """
        submission = self.get_submission(submissionid, False)

        if archive:
            submission.archive.put(archive)
            submission.save()

        update_query = {
            "status": ("done" if result[0] == "success" or result[0] == "failed" else "error"),
            # error only if error was made by INGInious
            "result": result[0],
            "grade": grade,
            "text": result[1],
            "tests": tests,
            "problems": problems,
            "custom": custom,
            "state": state,
            "stdout": stdout,
            "stderr": stderr
        }

        unset_obj = {
            "unset__jobid": "",  "unset__ssh_host": "", "unset__ssh_port": "",
            "unset__ssh_user": "", "unset__ssh_password": ""
        }

        update_query.update(unset_obj)

        # Save submission to database
        try:
            submission = Submission.objects(id=submissionid).modify(**update_query, new=True)
            for username in submission["username"]:
                self._user_manager.update_user_stats(username, course, task, submission, result[0], grade, state, newsub, task_dispenser)
        # Check for size as it also takes the MongoDB command into consideration
        except pymongo.errors.DocumentTooLarge:
            update_query = {"status": "error", "text": _("Maximum submission size exceeded. Check feedback, stdout, stderr and state."), "grade": 0.0}
            update_query.update(unset_obj)
            submission = Submission.objects(id=submissionid).modify(**update_query, new=True)

        plugin_manager.call_hook("submission_done", submission=submission, archive=archive, newsub=newsub)

        if "lti_version" in submission:
            lti_score_publisher = self._lti_score_publishers.get(submission["lti_version"], None)
            if lti_score_publisher:
                lti_score_publisher.add(submission)

    def _before_submission_insertion(self, course, task, inputdata, debug, obj):
        """
        Called before any new submission is inserted into the database. Allows you to modify obj, the new document that will be inserted into the
        database. Should be overridden in subclasses.

        :param task: Task related to the submission
        :param inputdata: input of the student
        :param debug: True, False or "ssh". See add_job.
        :param obj: the new document that will be inserted
        """
        username = self._user_manager.session_username()
        is_group_task =course.get_task_dispenser().get_group_submission(task.get_id())

        if is_group_task and not self._user_manager.has_staff_rights_on_course(course, username):
            group = Group.objects.get(courseid=course.id, students=username)
            obj.update({"username": group["students"]})
        else:
            obj.update({"username": [username]})

        lti_info = self._user_manager.session_lti_info()
        if lti_info is not None and course.lti_send_back_grade():
            lti_score_publisher = self._lti_score_publishers.get(lti_info["version"], None)
            if lti_score_publisher:
                obj.update({"lti_version": lti_info["version"]})
                lti_score_publisher.tag_submission(obj, lti_info)

        # If we are submitting for a group, send the group (user list joined with ",") as username
        if "group" not in [p.get_id() for p in task.get_problems()]:  # do not overwrite
            username = self._user_manager.session_username()
            if is_group_task and not self._user_manager.has_staff_rights_on_course(course, username):
                group = Group.objects.get(courseid=course.id, students=username)
                users = User.objects(username__in=group["students"])
                inputdata["@username"] = ','.join(group["students"])
                inputdata["@email"] = ','.join([user["email"] for user in users])

    def _after_submission_insertion(self, course, task, inputdata, debug, submission, submissionid, task_dispenser):
        """
                Called after any new submission is inserted into the database, but before starting the job.  Should be overridden in subclasses.
                :param task: Task related to the submission
                :param inputdata: input of the student
                :param debug: True, False or "ssh". See add_job.
                :param submission: the new document that was inserted (do not contain _id)
                :param submissionid: submission id of the submission
                """

        return self._delete_exceeding_submissions(self._user_manager.session_username(), course, task, task_dispenser)

    def replay_job(self, course, task, submission, task_dispenser, copy=False, debug=False):
        """
        Replay a submission: add the same job in the queue, keeping submission id, submission date and input data
        :param submission: Submission to replay
        :param copy: If copy is true, the submission will be copied to admin submissions before replay
        :param debug: If debug is true, more debug data will be saved
        """
        if not self._user_manager.session_logged_in():
            raise Exception("A user must be logged in to submit an object")

        # Load input data and add username to dict
        inputdata = submission.get_input()

        if not copy:
            submissionid = submission.id

            # Clean the submission document in db
            if submission.archive is not None:
                submission.archive.delete()
                submission.save()

            unset_query = {
                "unset__result": True, "unset__grade": True, "unset__text": True, "unset__tests": True,
                "unset__problems": True, "unset__archive": True, "unset__state": True, "unset__custom": True
            }

            Submission.objects(id=submissionid).update(status="waiting", **unset_query)

        else:
            username = self._user_manager.session_username()
            submission = Submission(username=[username], courseid=course.get_id(), taskid=task.get_id(),
                                    submitted_on=datetime.now().astimezone(), status="waiting",
                                    user_ip=flask.request.remote_addr)

            # Update metadata
            my_user_task = UserTask.objects(courseid=course.get_id(), taskid=task.get_id(), username=username).only("tried").get()
            tried_count = my_user_task.tried
            inputdata["@attempts"] = str(tried_count + 1)
            inputdata["@username"] = username
            inputdata["@email"] = self._user_manager.session_email()
            inputdata["@lang"] = self._user_manager.session_language()

            submission.set_input(inputdata)
            submissionid = submission.save().id

        # Don't enable ssh debug
        ssh_callback = lambda host, port, user, password: self._handle_ssh_callback(submissionid, host, port, user, password)

        jobid = self._client.new_job(1, course, task, inputdata,
                                     (lambda result, grade, problems, tests, custom, state, archive, stdout, stderr:
                                      self._job_done_callback(submissionid, course, task, result, grade, problems, tests,
                                                              custom, state, archive, stdout, stderr, task_dispenser, copy)),
                                     "Frontend - {}".format(submission["username"]), debug, ssh_callback)

        # Callback may have been received, perform atomic operation
        Submission.objects(id=submissionid).update(jobid=jobid, last_replay=datetime.now().astimezone())

        if not copy:
            self._logger.info("Replaying submission %s - %s - %s - %s", submission["username"], submission["courseid"],
                              submission["taskid"], submissionid)
        else:
            self._logger.info("Copying submission %s - %s - %s - %s as %s", submission["username"],
                              submission["courseid"],
                              submission["taskid"], submissionid, self._user_manager.session_username())

    def get_available_environments(self) -> Dict[str, List[str]]:
        """:return a list of available environments """
        return self._client.get_available_environments()

    def get_submission(self, submissionid, user_check=True):
        """ Get a submission from the database """
        sub = Submission.objects.get(id=submissionid)
        if user_check and not self.user_is_submission_owner(sub):
            return None
        return sub

    def add_job(self, course, task, inputdata, task_dispenser, debug=False):
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
        if not self._user_manager.session_logged_in():
            raise Exception("A user must be logged in to submit an object")

        username = self._user_manager.session_username()

        # Prevent student from submitting several submissions together
        waiting_submission = Submission.objects(
            courseid=course.get_id(), taskid=task.get_id(), username=username, status="waiting"
        ).first()

        if waiting_submission:
            raise Exception("A submission is already pending for this task!")

        obj = {
            "courseid": course.get_id(),
            "taskid": task.get_id(),
            "status": "waiting",
            "submitted_on": datetime.now(tz=timezone.utc),
            "username": [username],
            "user_ip": flask.request.remote_addr
        }

        # Send additional data to the client in inputdata. For now, the username and the language. New fields can be added with the
        # new_submission hook
        inputdata["@username"] = username
        inputdata["@email"] = self._user_manager.session_email()
        inputdata["@lang"] = self._user_manager.session_language()
        inputdata["@time"] = str(obj["submitted_on"])

        my_user_task = UserTask.objects.get(courseid=course.get_id(), taskid=task.get_id(), username=username)
        inputdata["@attempts"] = str(my_user_task.tried + 1)
        inputdata["@random"] = list(my_user_task.random)
        inputdata["@state"] = my_user_task.state

        # Send LTI information to the client except "consumer_key"
        lti_info = self._user_manager.session_lti_info()
        if lti_info:
            for key in lti_info:
                if key == "consumer_key" or key.startswith("outcome"): # Skip "consumer_key" and "outcome*"
                    continue
                self._logger.debug("LTI data : %s, %s",key, lti_info[key])
                # Add @lti_ prefix
                key_str = "@lti_" + key
                inputdata[key_str] = lti_info[key]

        plugin_manager.call_hook("new_submission", submission=obj, inputdata=inputdata)

        self._before_submission_insertion(course, task, inputdata, debug, obj)

        submission = Submission(**obj)
        submission.set_input(inputdata)
        submissionid = submission.save().id
        to_remove = self._after_submission_insertion(course, task, inputdata, debug, obj, submissionid, task_dispenser)

        ssh_callback = lambda host, port, user, password: self._handle_ssh_callback(submissionid, host, port, user, password)

        jobid = self._client.new_job(0, course, task, inputdata,
                                     (lambda result, grade, problems, tests, custom, state, archive, stdout, stderr:
                                      self._job_done_callback(submissionid, course, task, result, grade, problems, tests,
                                                              custom, state, archive, stdout, stderr, task_dispenser, True)),
                                     "Frontend - {}".format(username), debug, ssh_callback)

        # Submission may already have been modified by callback,
        Submission.objects(id=submissionid).update(jobid=jobid)

        self._logger.info("New submission from %s - %s - %s/%s - %s", self._user_manager.session_username(),
                          self._user_manager.session_email(), course.get_id(), task.get_id(),
                          flask.request.remote_addr)

        return submissionid, to_remove

    def _delete_exceeding_submissions(self, username, course, task, task_dispenser):
        """ Deletes exceeding submissions from the database, to keep the database relatively small """
        max_submissions = task_dispenser.get_no_stored_submissions(task.get_id())
        if max_submissions <= 0:
            return []

        tasks = list(Submission.objects(
            username=username, courseid=course.get_id(), taskid=task.get_id()
        ).only( "id", "status", "result", "grade", "submitted_on").order_by("-submitted_on"))

        # List the entries to keep
        to_keep = set([])

        # Keep the current evaluation submission
        user_task = UserTask.objects.get(courseid=course.get_id(), taskid=task.get_id(), username=username)
        if user_task.submissionid:
            to_keep.add(user_task.submissionid)

        # Keep running submissions
        for val in tasks:
            if val.status == "waiting":
                to_keep.add(val.id)

        # Fill the remaining slots with most recent submissions
        for val in tasks:
            if len(to_keep) < max_submissions:
                to_keep.add(val.id)

        to_delete = {val.id for val in tasks}.difference(to_keep)
        Submission.objects(id__in=to_delete).delete()

        return list(map(str, to_delete))

    def get_input_from_submission(self, submission, only_input=False):
        """
            Get the input of a submission. If only_input is False, returns the full submissions with a dictionnary object at the key "input".
            Else, returns only the dictionnary.
        """
        # do not recharge if not needed
        if isinstance(submission["input"], dict):
            return submission["input"] if only_input else submission

        inp = submission.get_input()
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
            submission["text"] = ParsableText(submission["text"], "rst", show_everything).parse()
        if "problems" in submission:
            for problem in submission["problems"]:
                if isinstance(submission["problems"][problem], str):  # fallback for old-style submissions
                    submission["problems"][problem] = (
                    submission.get('result', 'crash'), ParsableText(submission["problems"][problem],"rst",
                                                                    show_everything).parse())
                else:  # new-style submission

                    try:
                        submission["problems"][problem] = (
                        submission["problems"][problem][0], ParsableText(submission["problems"][problem][1],"rst",
                                                                     show_everything).parse())
                    except TypeError:
                        self._logger.error(
                            "Something went wrong with provided feedback for submission %s", str(submission["_id"])
                            )
                        submission["problems"][problem] = (
                            'crash', ParsableText(_("Feedback is badly formatted."),"rst", show_everything).parse())
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
        if not self._user_manager.session_logged_in():
            raise Exception("A user must be logged in to verify if he owns a jobid")

        return self._user_manager.session_username() in submission["username"]

    def get_user_submissions(self, course, task):
        """ Get all the user's submissions for a given task """
        if not self._user_manager.session_logged_in():
            raise Exception("A user must be logged in to get his submissions")

        cursor = Submission.objects(
            username=self._user_manager.session_username(), taskid=task.get_id(), courseid=course.get_id()
        ).order_by("-submitted_on")

        return list(cursor)

    def get_user_last_submissions(self, limit=5, query=None):
        """ Get last submissions of a user """
        if query is None:
            query = {}

        query.update({"username": self._user_manager.session_username()})

        # Before, submissions were first sorted by submission date, then grouped
        # and then resorted by submission date before limiting. Actually, grouping
        # and pushing, keeping the max date, followed by result filtering is much more
        # efficient
        user_submissions = Submission.objects(**query)

        data = user_submissions.aggregate([
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
            {"$sort": {"submitted_on": -1}},
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
            student_audiences = self._user_manager.get_course_audiences_per_student(course)

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
                submission_yaml = io.BytesIO(inginious.common.custom_yaml.dump(submission.to_mongo().to_dict()).encode('utf-8'))
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
                        subfile = submission['archive']
                        subtar = tarfile.open(fileobj=subfile, mode="r:gz")

                        for member in subtar.getmembers():
                            subtarfile = subtar.extractfile(member)
                            member.name = base_path + "/archive/" + member.name
                            tar.addfile(member, subtarfile)

                        subtar.close()
                        subfile.close()

                    # If there files that were uploaded by the student, add them
                    if submission['input'] is not None:
                        for pid, problem in submission.get_input().items():
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
                error = str(submission.id)
                break

        # Close tarfile and put tempfile cursor at 0
        tar.close()
        tmpfile.seek(0)
        return tmpfile, error

    def _handle_ssh_callback(self, submission_id, host, port, user, password):
        """ Handles the creation of a remote ssh server """
        if host is not None:  # ignore late calls (a bit hacky, but...)
            Submission.objects(id=submission_id).update(
                ssh_host=host, ssh_port=port, ssh_user=user, ssh_password=password
            )

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

# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" A plugin that allows to save submissions to a Git repository """
import queue
import io
import sys
import logging
import os.path
import shutil
import tarfile
import threading
import inginious.common.custom_yaml

if sys.platform == 'win32':
    import pbs
    git = pbs.Command('git')
else:
    from sh import git  # pylint: disable=no-name-in-module


class SubmissionGitSaver(threading.Thread):
    """
        Thread class that saves results from submission in the git repo.
        It must be a thread as a git commit can take some time and because we extract archives returned by the Client.
        But it must also be launched only one time as our git operations are not really process/tread-safe ;-)
    """

    def __init__(self, plugin_manager, config):
        threading.Thread.__init__(self)
        self._logger = logging.getLogger("inginious.webapp.plugins.SubmissionGitSaver")

        self.queue = queue.Queue()
        mustdoinit = False
        self.repopath = config.get("repo_directory", "./repo_submissions")
        if not os.path.exists(self.repopath):
            mustdoinit = True
            os.mkdir(self.repopath)
        self.git = git.bake('--work-tree=' + self.repopath, '--git-dir=' + os.path.join(self.repopath, '.git'))
        if mustdoinit:
            self.git.init()
        plugin_manager.add_hook('submission_done', self.add)
        self._logger.info("SubmissionGitSaver started")

    def add(self, submission, archive, _):
        """ Add a new submission to the repo (add the to queue, will be saved async)"""
        self.queue.put((submission, submission["result"], submission["grade"], submission["problems"], submission["tests"], submission["custom"], archive))

    def run(self):
        while True:
            try:
                submission, result, grade, problems, tests, custom, archive = self.queue.get()
                self.save(submission, result, grade, problems, tests, custom, archive)
            except Exception as inst:
                self._logger.exception("Exception in JobSaver: " + str(inst), exc_info=True)

    def save(self, submission, result, grade, problems, tests, custom, archive):  # pylint: disable=unused-argument
        """ saves a new submission in the repo (done async) """
        # Save submission to repo
        self._logger.info("Save submission " + str(submission["_id"]) + " to git repo")
        # Verify that the directory for the course exists
        if not os.path.exists(os.path.join(self.repopath, submission["courseid"])):
            os.mkdir(os.path.join(self.repopath, submission["courseid"]))
        # Idem with the task
        if not os.path.exists(os.path.join(self.repopath, submission["courseid"], submission["taskid"])):
            os.mkdir(os.path.join(self.repopath, submission["courseid"], submission["taskid"]))
        # Idem with the username, but empty it
        dirname = os.path.join(self.repopath, submission["courseid"], submission["taskid"], str.join("-", submission["username"]))
        if os.path.exists(dirname):
            shutil.rmtree(dirname)
        os.mkdir(dirname)
        # Now we can put the input, the output and the zip
        open(os.path.join(dirname, 'submitted_on'), "w+").write(str(submission["submitted_on"]))
        open(os.path.join(dirname, 'input.yaml'), "w+").write(inginious.common.custom_yaml.dump(submission["input"]))
        result_obj = {
            "result": result[0],
            "text": result[1],
            "problems": problems
        }
        open(os.path.join(dirname, 'result.yaml'), "w+").write(inginious.common.custom_yaml.dump(result_obj))
        if archive is not None:
            os.mkdir(os.path.join(dirname, 'output'))
            tar = tarfile.open(mode='r:gz', fileobj=io.BytesIO(archive))
            tar.extractall(os.path.join(dirname, 'output'))
            tar.close()

        self.git.add('--all', '.')
        title = " - ".join([str(submission["courseid"]) + "/" + str(submission["taskid"]),
                            str(submission["_id"]),
                            str.join("-", submission["username"]),
                            ("success" if result[0] == "success" else "failed")])
        self.git.commit('-m', title)


def init(plugin_manager, _2, config):
    """
        Init the plugin

        Available configuration:
        ::

            plugins:
                - plugin_module: inginious.frontend.plugins.git_repo
                  repo_directory: "./repo_submissions"

    """
    submission_git_saver = SubmissionGitSaver(plugin_manager, config)
    submission_git_saver.daemon = True
    submission_git_saver.start()

# coding=utf-8
from __future__ import annotations

from tempfile import TemporaryDirectory
import logging
import re
import os

from pygit2 import init_repository, GitError, Signature, Keypair, RemoteCallbacks, clone_repository
from pygit2.enums import FileStatus

from inginious.common.filesystems.git.utils import GitBackend, MyRepo, get_rc
from inginious.common.filesystems.git.gitolite import Gitolite
from inginious.common.filesystems.local import LocalFSProvider
from inginious.common.filesystems import FsType
from inginious.common.base import GitInfo


DEFAULT_BACKEND = GitBackend.gitolite
DEFAULT_INITIAL_HEAD = 'main'
DEFAULT_GITOLITE_PATH = 'gitolite-admin'
DEFAULT_GITOLITE_USER = 'git'

logger = logging.getLogger("inginious.fs.git")

class GitFSProvider(LocalFSProvider):
    """ This FileSystemProvider abstracts a LocalFSProvider versionned with Git.
    """

    @classmethod
    def get_needed_args(cls):
        return {
            "location": (str, True, "On-disk path to the directory containing courses/tasks."),
            "remote": (str, False, "URL from the remote registry."),
            "backend": (str, False, "The remote Git backend. Defaults to gitolite."),
            "initial_head": (str, False, "The initial head reference."),
            "gitolite_path": (str, False, "Path towards the local copy of the gitolite-admin repo."),
            "gitolite_user": (str, False, "Username to connect to the gitolite instance."),
            "user": (GitInfo, False, "Git informations for superadmin user.")
        }

    @classmethod
    def init_from_args(cls,
        location: str,
        remote: str=None,
        backend: GitBackend=DEFAULT_BACKEND,
        initial_head: str=DEFAULT_INITIAL_HEAD,
        gitolite_path: str=DEFAULT_GITOLITE_PATH,
        gitolite_user: str=DEFAULT_GITOLITE_USER,
        user: GitInfo=None
    ) -> GitFSProvider:
        return GitFSProvider(location, remote, backend, initial_head, gitolite_path, gitolite_user, user)

    def from_subfolder(self,
        subfolder: str,
    ) -> GitFSProvider:
        self._checkpath(subfolder)
        return GitFSProvider(self.prefix + subfolder, self.remote, self.backend, self.initial_head, self.gitolite_path, self.gitolite_user)

    def __init__(self,
        prefix: str,
        remote: str=None,
        backend: str=DEFAULT_BACKEND,
        initial_head: str=DEFAULT_INITIAL_HEAD,
        gitolite_path: str=DEFAULT_GITOLITE_PATH,
        gitolite_user: str=DEFAULT_GITOLITE_USER,
        user: GitInfo=None
    ) -> GitFSProvider:
        super().__init__(prefix)
        try:
            self.repo = MyRepo(prefix)
        except GitError:
            self.repo = None
        self.remote = remote
        self.backend = backend
        self.initial_head = initial_head
        self.gitolite_path = gitolite_path
        self.gitolite_user = gitolite_user
        if self.backend == GitBackend.gitolite:
            try:
                self.gitolite = Gitolite(gitolite_path)
            except GitError:
                # Only admnistrators can create new courses from the web GUI, so
                # the user should have access to gitolite-admin repo.
                # FIXME: This currently does not work...
                # print(f"failed to init gitolite {gitolite_path}")
                # (_, rc) = get_rc(user)
                # if self.remote is not None and rc is not None:
                #     self.gitolite = clone_repository(f'{self.remote}/gitolite-admin', gitolite_path, callbacks=rc)
                pass

    def _id_from_prefix(self) -> str:
        prefix = self.prefix if not self.prefix.endswith('/') else self.prefix[:-1]
        return os.path.basename(prefix)

    def _origin_url(self) -> str:
        return None if self.remote is None else f'{self.remote}/{self._id_from_prefix()}'

    def ensure_exists(self, type: FsType=FsType.other, user: GitInfo=None, push: bool=True) -> None:
        # Sanity check, we only initialize repositories if needed.
        if type == FsType.other:
            super().ensure_exists()
        else:
            logger.info(f"FS at <{self.prefix}> for FsType <{type}> does not exist. Creating...")
            common_path = '$common'
            try:
                MyRepo(self.prefix)
            except GitError:
                (user_sig, rc) = get_rc(user)
                # Current prefix does not exists and we should initialize a new
                # repository, i.e., we add a course or a task.
                #
                # First, we initialize the remote repository.
                logger.info(f"Initializing remote repository for backend <{self.backend}>.")
                # FIXME: Extend this for additional backends, e.g., GitHub, Gitlab, ...
                # This will probably require interactions through REST APIs.
                if self.backend == GitBackend.gitolite:
                    courseid = self._id_from_prefix()
                    self.gitolite.init_repo(user, courseid, push=push)

                # Second, we create the local copy of the repostory.
                init_repository(
                    self.prefix,
                    initial_head=DEFAULT_INITIAL_HEAD,
                    origin_url=self._origin_url()
                )
                self.repo = MyRepo(self.prefix)

                # Third, we handle the $common submodule.
                if type == FsType.course:
                    # If are creating a course, we initialize the course's $common.
                    self._init_common(user, push=push)
                elif type == FsType.task:
                    # If we add a task to a course, we add the course's $common
                    # submodule to the task.
                    course_prefix = os.path.dirname(self.prefix[:-1])
                    course = self.__class__.init_from_args(
                        course_prefix,
                        remote=self.remote,
                        gitolite_path=self.gitolite_path
                    )
                    taskid = self._id_from_prefix()
                    logger.info(f'Adding $common submodule to task {taskid}.')
                    if (common := course.repo.submodules.get('$common')) is not None:
                        (_, rc) = get_rc(user)
                        logger.info(common.url)
                        self.repo.submodules.add(common.url, common_path, callbacks=rc)
                        logger.info(f'$common submodule added to task {taskid}.')
                    else:
                        logger.warn('The expected  $common submodule has not been found. Skipping.')

                # Fourth, if we are required, we push the new repository to the remote.
                if push:
                    self.repo._try_push('origin', rc)
      
    def _should_stage(self, filepath: str) -> bool:
        """ Determine whether `filepath` should be staged or not. We should stage
            if `filepath` is tracked and is modified, or if `filepath` is
            untracked.

            :param filepath: The path towards the file to stage or not.

            :return: True if `filepath` must be staged, else False.
        """
        return False if self.repo is None or (status := self.repo.status().get(filepath)) is None else status in [FileStatus.WT_NEW, FileStatus.WT_MODIFIED]

    def _is_reserved(self, filepath: str, kind: str) -> bool:
        """ Determine whether the `filepath` points towards a reserved directory.

            :param filepath: The path towards a potential reserved directory.

            :return: True if `filepath` points toward a task directory.
        """
        descriptors = [f'{kind}.{ext}' for ext in ['yaml', 'json']]
        is_reserved = False
        if os.path.isdir(filepath):
            dir_content = os.listdir(filepath)
            [is_reserved := is_reserved or descr in dir_content for descr in descriptors]
        return is_reserved

    def _is_task(self, filepath: str) -> bool:
        """ Determine whether the `filepath` points towards a task directory.

            :param filepath: The path towards a potential task directory.

            :return: True if `filepath` points toward a task directory.
        """
        self._is_reserved(filepath, 'task')

    def _is_course(self, filepath: str) -> bool:
        """ Determine whether the `filepath` points towards a course directory.

            :param filepath: The path towards a potential course directory.

            :return: True if `filepath` points toward a course directory.
        """
        self._is_reserved(filepath, 'course')
    
    def _is_submodule(self, filepath: str) -> bool:
        """ Determine whether `filepath` points toward a submodule.

            :param filepath: The path towards a potential submodule.

            :return: True if `filepath` points to a submodule, else False.
        """
        # return len([sm for sm in self.repo.submodules if sm.name == filepath]) == 1
        return self.repo.submodules.get(filepath) is not None

    def _try_stage(self, filepath: str, should_stage: bool) -> None:
        """ Stage `filepath` if `should_stage` is True. Add tasks as course's
            submodules, which in turn, stages the task submodule. 

            :param filepath: The entry to stage.
            :param should_stage: Whether we should stage or not `filepath`.
        """
        if should_stage:
            if self._is_task(filepath) and not self._is_submodule(filepath):
                # Add newly created tasks as course submodule.
                # There is a limitation with pygit2 which does not allow adding
                # a local submodule, e.g., like `git submodule add localdir`.
                # Therfore, we should first create the task, 
                # self.repo.submodules.add(filepath, filepath, callbacks=None)
                pass
            else:
                self.repo.index.add(filepath)
                self.repo.index.write()
                
    def try_stage(self, filepath: str) -> None:
        self._try_stage(filepath, self._should_stage(filepath))

    def try_commit(self, filepath: str, msg: str=None, user: GitInfo=None, push:bool=True) -> None:
        # Should we stage the descriptor?
        should_stage = self._should_stage(filepath)
        # If we have to stage `filepath` or if `filepath` is already staged, we commit.
        if should_stage or ((status := self.repo.status().get(filepath)) is not None and status == FileStatus.INDEX_MODIFIED):
            # Stage `filepath` if needed.
            self._try_stage(filepath, should_stage)
            if user is not None:
                # This function is only called for writing course / task
                # descriptor, so we commit directly upon call if the content has
                # changed.
                (user_sig, rc) = get_rc(user)
                self.repo._try_commit(user_sig, msg)
                if push and rc is not None:
                    self.repo._try_push('origin', rc, logger)

    def _init_common(self, user: GitInfo, push: bool=True):
        # Initialize callbacks from user information.
        (user_sig, rc) = get_rc(user)

        # Create temporary $common repository
        courseid = self._id_from_prefix()
        logger.info(f"Initializing $common submodule for course <{courseid}>.")
        prefix = TemporaryDirectory()
        common_path = f'{prefix.name}/{courseid}/.common'
        common_url = f'{origin_url}/.common' if (origin_url := self._origin_url()) is not None else None
        if common_url is None:
            logger.warning("Remote URL is not specified, changes will not be pushed to the remote.")
        common = init_repository(common_path, initial_head=DEFAULT_INITIAL_HEAD, origin_url=common_url)
        common = MyRepo(common_path)

        # Add .gitkeep so that $common can be added as a submodule.
        with open(f'{common_path}/.gitkeep', 'wb') as fd:
            fd.write(b"")
        common.index.add('.gitkeep')
        common._try_commit(user_sig, '$common repository created.')

        # Add temporary $common as a local submodule and update url to remote.
        # This allows adding the $common submodule without having to interact
        # with the remote.
        common_sm = self.repo.submodules.add(common_path, '$common', callbacks=rc)
        if common_url is not None:
            common_sm.url = common_url
            self.repo.index.add('.gitmodules')
            self.repo.index.write()

        # Commit the $common submodule addition.
        self.repo._try_commit(user_sig, '$common submodule added.')

        if push:
            logger.info("Pushing the $common submodule to remote...")
            # Push the $common repository to remote.
            common._try_push('origin', rc, logger)

        # Cleanup
        prefix.cleanup()

    def put(self, filepath: str, content, msg: str=None, user: GitInfo=None, push: bool=True) -> None:
        super().put(filepath, content)
        # This function is called each time the button 'save changes' is pressed
        # on the web GUI, even if the content is unchanged...
        # We check that content has indeed changed before trying to commit.
        self.try_commit(filepath, msg, user, push)

    def delete(self, filepath: str=None) -> None:
        super().delete(filepath)
        if self.repo is not None and filepath is not None:
            self.repo.index.add([filepath])

    def move(self, src, dest):
        super().move(src, dest)
        if self.repo is not None:
            self.repo.index.add([src, dest])

    def copy_to(self, src_disk, dest=None):
        super().copy_to(src_disk, dest)
        if dest is None and self.repo is not None:
            self.repo.index.add([self.prefix])

    def distribute(self, filepath, allow_folders=True):
        # TODO: return tar archive with self.repo.archive(fd)
        # SEE: https://gitpython.readthedocs.io/en/stable/reference.html#git.repo.base.Repo.archive
        super().distribute(filepath, allow_folders)

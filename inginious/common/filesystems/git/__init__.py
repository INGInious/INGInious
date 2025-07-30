# coding=utf-8
from __future__ import annotations

from tempfile import TemporaryDirectory
from enum import StrEnum
import re
import os

from pygit2 import init_repository, Repository, GitError, Signature, Keypair, RemoteCallbacks
from pygit2.enums import FileStatus

from inginious.common.filesystems.local import LocalFSProvider

DEFAULT_INITIAL_HEAD = 'main'
DEFAULT_BACKEND = GitBackend.gitolite

class GitBackend(StrEnum):
    gitolite = 'gitolite'

class MyRepo(Repository):
    """ Some helper wrapping pygit2.Repository
    """

    def _try_push(self):
        try:
            origin = self.remotes[remote]
            origin.push([self.repo.listall_references()[0]], callbacks=cbs)
        except KeyError:
            # TODO: get logger
            print('No origin remote')

class GitFSProvider(LocalFSProvider):
    """ This FileSystemProvider abstracts a LocalFSProvider versionned with Git.
    """

    @classmethod
    def get_needed_args(cls):
        return {
            "location": (str, True, "On-disk path to the directory containing courses/tasks."),
            "remote": (str, False, "URL from the remote registry."),
            "backend": (str, False, "The remote Git backend. Defaults to gitolite.")
            "initial_head": (str, False, "The initial head reference.")
        }

    @classmethod
    def init_from_args(cls, location: str, remote: str=None, backend: GitBackend=DEFAULT_BACKEND, initial_head: str=DEFAULT_INITIAL_HEAD) -> GitFSProvider:
        return GitFSProvider(location, remote)

    def from_subfolder(self, subfolder: str, remote: str=None, backend: GitBackend=DEFAULT_BACKEND, initial_head: str=DEFAULT_INITIAL_HEAD) -> GitFSProvider:
        self._checkpath(subfolder)
        return GitFSProvider(self.prefix + subfolder, remote)

    def __init__(self, prefix: str, remote: str=None, backend: str=DEFAULT_BACKEND, initial_head: str=DEFAULT_INITIAL_HEAD) -> GitFSProvider:
        super().__init__(prefix)
        try:
            self.repo = Repository(prefix)
        except GitError:
            self.repo = None
        self.remote = remote
        self.backend = backend

    def _id_from_prefix(self) -> str:
        prefix = self.prefix if not self.prefix.endswith('/') else self.prefix[:-1]
        return os.path.basename(prefix)

    def _origin_url(self) -> str:
        return f'{self.remote}/{self._id_from_prefix()}'

    def ensure_exists(self) -> None:
        common_path = '$common'
        try:
            Repository(self.prefix)
        except GitError:
            self.repo = init_repository(self.prefix, initial_head=INITIAL_HEAD, origin_url=self._origin_url())
            if self._is_task(self.prefix):
                # We are a newly added task. If parent course contains a $common
                # submodule, we add it in the task.
                course_prefix = os.path.dirname(self.prefix)
                course = GitFSProvider.init_from_args(course_prefix)
                if course._is_submodule(common_path):
                    common = course.from_subfolder(common_path)
                    if (url := common.repo.remotes.get('origin')) is not None:
                        self.repo.submodules.add(url, common_path, callbacks=None)
      
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
        return len([sm for sm in self.repo.submodules if sm.name == filepath]) == 1

    def _try_push(self, remote: str, cbs):
        try:
            origin = self.repo.remotes[remote]
            origin.push([self.repo.listall_references()[0]], callbacks=cbs)
        except KeyError:
            # TODO: get logger
            print('No origin remote')

    def _try_stage(self, filepath: str, should_stage: bool) -> None:
        """ Stage `filepath` if `should_stage` is True. Add tasks as course's
            submodules, which in turn, stages the task submodule. 

            :param filepath: The entry to stage.
            :param should_stage: Whether we should stage or not `filepath`.
        """
        if should_stage:
                # common = self.from_subfolder('$common')
                # common.ensure_exists()

            if self._is_task(filepath) and not self._is_submodule(filepath):
                # Add newly created tasks as course submodule.
                # There is a limitation with pygit2 which does not allow adding
                # a local submodule, e.g., like `git submodule add localdir`.
                # Therfore, we should first create the task, 
                self.repo.submodules.add(name=filepath, path=filepath)
            else:
                self.repo.index.add(filepath)
                self.repo.index.write()
                
    def try_stage(self, filepath: str) -> None:
        self._try_stage(filepath, self._should_stage(filepath))

    def try_commit(self, filepath: str, msg: str=None, user: tuple[str, str]=None) -> None:
        # Should we stage the descriptor?
        should_stage = self._should_stage(filepath)
        # Is the descriptor already staged? We should have a valid HEAD to test
        # that case.
        # This may commit other staged files, e.g., when adding a newly created
        # task.
        descr_changed = should_stage or (self.repo.head.is_valid() and len(self.repo.index.diff("HEAD", paths=[filepath])) == 1)
        if descr_changed:
            self._try_stage(filepath, should_stage)
            if user is not None:
                # if filepath == 'course.yaml' and not self.exists('$common'):
                #     self._init_common(user)
                user = Signature(user[0], user[1])
                # This function is only called for writing course / task
                # descriptor, so we commit directly upon call if the content has
                # changed.
                tree = self.repo.index.write_tree()
                # history = [commit.id for commit in self.repo.walk(self.repo.head.target)]
                history = []
                self.repo.create_commit(
                    'HEAD',
                    user,
                    user,
                    f"Automated save from web GUI{'.' if msg is None else f': {msg}'}",
                    tree,
                    history
                )

    
    def init_common(self, user: tuple[str, str], rc):
        # Create temporary $common repository
        courseid = self._id_from_prefix()
        user = Signature(user[0], user[1])
        prefix = TemporaryDirectory(prefix='/dev/shm/')
        common_path = f'{prefix}/{courseid}/.common'
        common_url = f'{self._origin_url()}/.common'
        common = init_repository(common_path, initial_head=INITIAL_HEAD, origin_url=common_url)

        # Add .gitkeep to make it usable through git.
        with open(f'{common_path}/.gitkeep', 'wb') as fd: fd.write(b"")
        common.index.add('.gitkeep')
        tree = common.index.write_tree()
        history = []
        common.create_commit('HEAD', user, user, f'$common directory created.', tree, history)

        # If we use gitolite as backend, we first have to initialize the repo on the remote
        if self.backend == GitBackend.gitolite:
            try:
                gitolite = Repository('gitolite-admin')
            except GitError:
                pass
                # Only admnistrators can create new courses from the web GUI, so
                # it is safe the user should have access to gitolite-admin repo.
                # TODO: clone gitolite-admin
                
            # TODO: init gitolite remote

        # Push the $common repository to remote
        common = GitFSProvider.init_from_args(common_path)
        # FIXME: Get keys from user
        # kp = Keypair('admin', '/home/nicolas/.ssh/gitolite.pub', '/home/nicolas/.ssh/gitolite', 'test')
        # rc = RemoteCallbacks(credentials=lambda _url, usr, _t: kp if usr == kp.credential_tuple[0] else None)
        common._try_push('origin', rc)

        # Add it as submodule
        self.repo.submodules.add(common_url, '$common', callbacks=rc)

        # Cleanup
        prefix.cleanup()

    def put(self, filepath: str, content, msg: str=None, user: tuple[str, str]=None) -> None:
        super().put(filepath, content)
        # This function is called each time the button 'save changes' is pressed
        # on the web GUI, even if the content is unchanged...
        # We check that content has indeed changed before trying to commit.
        self.try_commit(filepath, msg, user)

    def delete(self, filepath: str=None) -> None:
        super().delete(filepath)
        if self.repo is not None and filepath is not None:
            self.repo.index.add([filepath])

    def move(self, src, dest):
        super().move(src, dest)
        if self.repo is not None:
            self.repo.index.add([src, dst])

    def copy_to(self, src_disk, dest=None):
        super().copy_to(src_disk, dest)
        if dest is None and self.repo is not None:
            self.repo.index.add([self.prefix])

    def distribute(self, filepath, allow_folders=True):
        # TODO: return tar archive with self.repo.archive(fd)
        # SEE: https://gitpython.readthedocs.io/en/stable/reference.html#git.repo.base.Repo.archive
        super().distribute(filepath, allow_folders)

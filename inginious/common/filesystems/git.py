# coding=utf-8
from __future__ import annotations
import os

from git import Repo, exc, Actor, Remote, Submodule

from inginious.common.filesystems.local import LocalFSProvider

class GitFSProvider(LocalFSProvider):
    """ This FileSystemProvider abstracts a LocalFSProvider versionned with Git.
    """

    @classmethod
    def get_needed_args(cls):
        return {"location": (str, True, "On-disk path to the directory containing courses/tasks.")}        

    @classmethod
    def init_from_args(cls, location):
        return GitFSProvider(location)

    def from_subfolder(self, subfolder) -> GitFSProvider:
        self._checkpath(subfolder)
        return GitFSProvider(self.prefix + subfolder)

    def _is_prefix_allowed(self, prefix: str) -> bool:
        # See https://github.com/gitpython-developers/GitPython/issues/832
        banned = ['$', '%']
        allowed = True
        [allowed := allowed and c not in prefix for c in banned]
        return allowed

    def __init__(self, prefix: str):
        super().__init__(prefix)
        try:
            self.repo = Repo(prefix) if self._is_prefix_allowed(prefix) else None
        except exc.NoSuchPathError:
            self.repo = None
        except exc.InvalidGitRepositoryError:
            # tasks/ directory won't be initialized as a git repository.
            self.repo = None

    def ensure_exists(self) -> None:
        if self._is_prefix_allowed(self.prefix):
            self.repo = Repo.init(self.prefix, b="main")
            if len([remote for remote in self.repo.remotes if remote.name == 'origin']) == 0:
                Remote.add(self.repo, 'origin', f'ingitolite:{self.prefix}')

    def _should_stage(self, filepath: str) -> bool:
        # We should stage if the filepath is tracked but has a diff, or if the
        # filepath is untracked.
        return False if self.repo is None else len(self.repo.index.diff(None, paths=[filepath])) == 1 or filepath in self.repo.untracked_files

    def _is_task(self, filepath: str) -> bool:
        descriptors = [f'task.{ext}' for ext in ['yaml', 'json']]
        is_task = False
        if os.path.isdir(filepath):
            [is_task := is_task or descr in os.listdir(filepath) for descr in descriptors]
        return is_task

    def _is_submodule(self, filepath: str) -> bool:
        return len([sm for sm in self.repo.submodules if sm.name == filepath]) == 1

    def _try_stage(self, filepath: str, should_stage: bool) -> None:
        if should_stage:
            if self._is_task(filepath) and not self._is_submodule(filepath):
                # Add newly created tasks as course submodule.
                Submodule.add(self.repo, name=filepath, path=filepath)
            else:
                self.repo.git.add([filepath])

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
                actor=Actor(name=user[0], email=user[1])
                # This function is only called for writing course / task
                # descriptor, so we commit directly upon call if the content has
                # changed.
                self.repo.index.commit(
                    f"Automated save from web GUI{'.' if msg is None else f': {msg}'}" ,
                    author=actor,
                    committer=actor
                )

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

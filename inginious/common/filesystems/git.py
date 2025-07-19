# coding=utf-8
from __future__ import annotations

from git import Repo, exc, Actor

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

    def __init__(self, prefix: str):
        super().__init__(prefix)
        # TODO: filter directories beginning with '$'.
        try:
            self.repo = Repo(prefix)
        except exc.NoSuchPathError:
            self.repo = None
        except exc.InvalidGitRepositoryError:
            # tasks/ directory won't be initialized as a git repository.
            self.repo = None

    def ensure_exists(self) -> None:
        self.repo = Repo.init(self.prefix, b="main")
        with self.repo.config_writer() as cfg:
            # TODO: Set user SSH key ?
            pass

    def _try_commit(self, filepath: str, msg: str=None, user: tuple[str, str]=None):
        # Should we stage the descriptor?
        to_stage = len(self.repo.index.diff(None, paths=[filepath])) == 1 or filepath in self.repo.untracked_files
        # Is the descriptor already staged? We should have a valid HEAD to test
        # that case.
        # FIXME: This may commit other staged files. Is that an issue?
        descr_changed = to_stage or (self.repo.head.is_valid() and len(self.repo.index.diff("HEAD", paths=[filepath])) == 1)
        if descr_changed:
            if to_stage:
                self.repo.index.add([filepath])
                self.repo.index.write()
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
        self._try_commit(filepath, msg, user)

    def delete(self, filepath: str=None) -> None:
        super().delete(filepath)
        if filepath is not None:
            self.repo.index.add([filepath])

    def move(self, src, dest):
        super().move(src, dest)
        self.repo.index.add([src, dst])

    def copy_to(self, src_disk, dest=None):
        super().copy_to(src_disk, dest)
        if dest is None:
            self.repo.index.add([self.prefix])

    def distribute(self, filepath, allow_folders=True):
        # TODO: return tar archive with self.repo.archive(fd)
        # SEE: https://gitpython.readthedocs.io/en/stable/reference.html#git.repo.base.Repo.archive
        super().distribute(filepath, allow_folders)

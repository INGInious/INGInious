# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

"""
Abstract class for filesystems providers.
"""

from __future__ import annotations
from abc import ABCMeta, abstractmethod
from datetime import datetime
from enum import StrEnum

from inginious.common.base import GitInfo


class FsType(StrEnum):
    course = 'course'
    task = 'task'
    other = 'other'

class FileSystemProvider(metaclass=ABCMeta):
    """ Provides tools to access a given filesystem. The filesystem may be distant, and subclasses of FileSystemProvider should take care of
        doing appropriate caching.
    """

    @classmethod
    @abstractmethod
    def get_needed_args(cls):
        """ Returns a list of arguments needed to create a FileSystemProvider. In the form
            {
                "arg1": (int, False, "description1"),
                "arg2: (str, True, "description2")
            }

            The first part of the tuple is the type, the second indicates if the arg is mandatory
            Only int and str are supported as types.
        """

    @classmethod
    @abstractmethod
    def init_from_args(cls, **args):
        """ Given the args from get_needed_args, creates the FileSystemProvider """

    def __init__(self, prefix: str):
        """ Init the filesystem provider with a given prefix.

        :param prefix: The FileSystemPrrovider prefix.
        """
        self.prefix = prefix
        if not self.prefix.endswith("/"):
            self.prefix += "/"

    def _checkpath(self, path):
        """ Checks that a given path is valid.

        :raises FileNotFoundError: If path is invalid.
        """
        if path.startswith("/") or ".." in path or path.strip() != path:
            raise FileNotFoundError()

    @abstractmethod
    def try_stage(self, filepath: str) -> None:
        """
        For versioned filesystems, try staging `filepath` if it points to
        modified content. Otherwise, do nothing.

        :param filepath: The path towards items to stage if modified.
        """

    @abstractmethod
    def try_commit(self, filepath: str, msg: str=None, user: GitInfo=None):
        """
        For versioned filesystems, add `filepath` content to the history with
        `msg` message from `user` author. Otherwise, do nothing.
        If `user` is not provided, `filepath` content is only staged, if needed,
        and not committed.

        :param filepath: Path towards item(s) to commit.
        :param msg: An optional commit message.
        :param user: Optional authorship information for the commit.
        """

    @abstractmethod
    def from_subfolder(self, subfolder: str) -> FileSystemProvider:
        """
        :param subfolder: The prefix of the new FileSystemProvider.

        :returns: A new FileSystemProvider, with `subfolder` as prefix.
        """

    @abstractmethod
    def exists(self, path: str=None) -> bool:
        """
        :param path: A path to verify.

        :returns: True if the file at the given path exists. If the path is not given, then checks the existence of the prefix.
        """

    @abstractmethod
    def ensure_exists(self, type: FsType=FsType.other, user: GitInfo=None, push: bool=True) -> None:
        """ Ensure that the current prefix exists. If it is not the case, creates the directory. """

    @abstractmethod
    def put(self, filepath: str, content, msg: str=None, user: GitInfo=None):
        """ Write `content` in `filepath`"""

    @abstractmethod
    def get_fd(self, filepath: str, timestamp:datetime=None):
        """ Returns a file descriptor.
            If timestamp is not None, it gives an indication to the cache that the file must have been retrieved from the (possibly distant)
            filesystem since the timestamp.

            :raises FileNotFoundError: if the file does not exists or cannot be retrieved.
            :raises IsADirectoryError: if `filepath` points to a directory.

            :returns: A file descriptor pointing to `filepath`.
        """

    @abstractmethod
    def get(self, filepath: str, timestamp:datetime=None):
        """ Get the content of a file.
            If timestamp is not None, it gives an indication to the cache that the file must have been retrieved from the (possibly distant)
            filesystem since the timestamp.

            :raises FileNotFoundError: If the file does not exists or cannot be retrieved.
        """

    @abstractmethod
    def list(self, folders: bool=True, files: bool=True, recursive: bool=False) -> list:
        """ List all the files/folder in this prefix. Folders are always ending with a '/'

        :param folders: Switch to list folders.
        :param files: Switch to list files.
        :param recursive: Switch to list recursively the prefix content.

        :returns: The list of files/folders in the prefix.
        """

    @abstractmethod
    def delete(self, filepath: str=None):
        """ Delete a path recursively. If filepath is None, then the prefix will be deleted.

        :param filepath: The prefix entry to delete.

        :raises FileNotFoundError: If `filepath` points to a non-existing entry in the prefix.
        """

    @abstractmethod
    def get_last_modification_time(self, filepath):
        """ Get a timestamp representing the time of the last modification of the file at filepath """

    @abstractmethod
    def move(self, src, dest):
        """ Move path src to path dest, recursively. """

    @abstractmethod
    def copy_to(self, src_disk, dest=None):
        """ Copy the content of *on-disk folder* src_disk into dir dest. If dest is None, copy to the prefix."""

    @abstractmethod
    def copy_from(self, src, dest_disk):
        """ Copy the content of src into the *on-disk folder* dest_disk. If src is None, copy from the prefix. """

    @abstractmethod
    def distribute(self, filepath, allow_folders=True):
        """ Give information on how to distribute a file. Provides Zip files of folders. Can return:
            ("file", mimetype, fileobj) where fileobj is an object-like file (with read()) and mimetype its mime-type.
            ("url", None, url) where url is a url to a distant server which possess the file.
            ("invalid", None, None) if the file cannot be distributed
        """

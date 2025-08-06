# coding=utf-8
from __future__ import annotations

from enum import StrEnum
import logging

from cryptography.hazmat.primitives.serialization import PublicFormat, PrivateFormat, Encoding, NoEncryption
from pygit2 import Repository, Signature, GitError, KeypairFromMemory, RemoteCallbacks

from inginious.common.base import GitInfo


_logger = logging.getLogger('inginious.fs.git.utils')

class GitBackend(StrEnum):
    gitolite = 'gitolite'

class MyRepo(Repository):
    """ Some helpers wrapping pygit2.Repository.
    """

    def _try_push(self, remote: str, rc: RemoteCallbacks, logger=None):
        if logger is not None:
            logger.info(f"Trying to push to {remote}.")
        try:
            origin = self.remotes[remote]
            origin.push([self.head.name], callbacks=rc)
            if logger is not None:
                logger.info(f"Pushed to {remote}.")
        except KeyError:
            if logger is not None:
                logger.error(f"Remote <{remote}> does not exist for the current repository, could not push.")
        except GitError as e:
            if logger is not None:
                logger.error(f"Failed to push to remote {remote}: {e}")
        except Exception as e:
            if logger is not None:
                logger.error(f"Unexpected error: {e}")

    def _try_commit(self, user: Signature, msg: str=None) -> None:
        tree = self.index.write_tree()
        msg = f"Automated save from web GUI{'.' if msg is None else f': {msg}'}"
        try:
            history = [self.head.target]
        except GitError:
            history = []
        except Exception as e:
            _logger.error(e)
            raise e

        self.create_commit('HEAD', user, user, msg, tree, history)
            
def get_rc(user: GitInfo=None) -> Union[tuple[None, None], tuple[Signature, RemoteCallbacks]]:
    if user is None:
        return (None, None)
    user_sig = Signature(user.realname, user.email)
    if user.key is not None:
        private = user.key.private_bytes(Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()).decode('utf-8')
        public = user.key.public_key().public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH).decode('utf-8')
        # TODO: Get gitolite username from config
        kp = KeypairFromMemory("admin", public, private, 'test')
        rc = RemoteCallbacks(credentials=lambda _url, _usr, _t: kp)
        rc.push_update_reference=lambda refname, msg: _logger.warning(f"Push failed: {msg}") if msg is not None else ''
    else:
        rc = None
    return (user_sig, rc)

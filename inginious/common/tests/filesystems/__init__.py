import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from inginious.common.filesystems.git.utils import get_rc
from inginious.common.base import GitInfo

def commit_msg(msg: str) -> str:
    return f'Automated save from web GUI: {msg}'

def check_commit(commit, message: str, user: GitInfo):
    user = (user.realname, user.email)
    assert commit.message == commit_msg(message)
    assert (commit.author.name, commit.author.email) == user
    assert (commit.committer.name, commit.committer.email) == user

def check_n_last_commit(repo, message, user, n) -> None:
    commits = [commit for commit in repo.walk(repo.head.target)]
    assert len(commits) == n
    check_commit(commits[0], message, user)

def check_single_commit(repo, message, user):
    check_n_last_commit(repo, message, user, 1)

@pytest.fixture
def user():
    key = b'Cb>T\xa3\xf5sy\x19\xc0F2&\xeb*mQ|\xaa\xbd/\x94\x13D\xb2-m\xe4\x13\xbe(\x1b'
    return GitInfo('INGInious superadmin', 'superadmin@test.test', 'superadmin', Ed25519PrivateKey.from_private_bytes(key))

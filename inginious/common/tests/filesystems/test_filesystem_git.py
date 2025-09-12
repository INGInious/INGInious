# pylint: disable=redefined-outer-name

import os

from pygit2 import Repository
import pytest
import yaml

from inginious.common.filesystems.git.utils import GitBackend
from inginious.common.base import get_json_or_yaml, GitInfo
from inginious.common.filesystems import FsType
from inginious.common.filesystems.git import *

from inginious.common.tests.filesystems.git.gitolite import *
from inginious.common.tests.filesystems import *


@pytest.fixture
def remote():
    return 'ssh://superadmin@ingitolite:2222'

@pytest.fixture
def init_content():
    content = {
        'accessible': False,
        'name': 'course0'
    }
    return yaml.dump(content)

@pytest.fixture
def course0_prefix(tmp_path):
    courseid = 'course0'
    return (courseid, tmp_path / courseid)

@pytest.fixture
def course0_fs(gitolite_new_repo, remote, course0_prefix):
    (courseid, prefix) = course0_prefix

    return (
        courseid,
        GitFSProvider.init_from_args(
            str(prefix),
            remote=remote,
            gitolite_path=gitolite_new_repo
        )
    )

@pytest.fixture
def course0_task0_fs(course0_fs):
    (courseid, course_fs) = course0_fs
    
def test_init_from_args_0(course0_prefix):
    (courseid, prefix) = course0_prefix
    prefix = f'{str(prefix)}/'

    #FuT
    course_fs = GitFSProvider.init_from_args(prefix)

    assert course_fs.repo is None
    assert course_fs.prefix == prefix
    assert course_fs.remote is None
    assert course_fs.backend == DEFAULT_BACKEND
    # with pytest.raises(AttributeError):
        # course_fs.gitolite

def test_init_from_args_1(course0_prefix, gitolite_new_repo):
    (courseid, prefix) = course0_prefix
    prefix = f'{str(prefix)}/'

    #FuT
    course_fs = GitFSProvider.init_from_args(prefix, gitolite_path=gitolite_new_repo)

    assert course_fs.repo is None
    assert course_fs.prefix == prefix
    assert course_fs.remote is None
    assert course_fs.backend == DEFAULT_BACKEND
    assert course_fs.gitolite is not None

def test_id_from_prefix_course(course0_fs):
    (courseid, course_fs) = course0_fs

    assert course_fs._id_from_prefix() == courseid

def test_origin_url_course(course0_fs, remote):
    (courseid, course_fs) = course0_fs

    assert course_fs._origin_url() == f'{remote}/{courseid}'

def test_ensure_exists_0(gitolite_new_repo, course0_prefix, user):
    (courseid, prefix) = course0_prefix
    prefix = str(prefix)
    course_fs = GitFSProvider.init_from_args(prefix, gitolite_path=gitolite_new_repo)

    # FuT
    course_fs.ensure_exists(FsType.course, user=user, push=False)

    # Checks.
    # 
    # This could raise a GitError if the course repository has not been correctly
    # initialized.
    course = Repository(prefix)

    # 1. Ensure working tree is clean.
    assert len(course.status()) == 0

    # 2. Ensure that no remote is set.
    assert len(course.remotes) == 0

    # 3. Ensure only the $common submodule is set and contains a single commit.
    assert len(course.listall_submodules()) == 1
    common = course.submodules['$common']
    assert common.url != f'{remote}/{courseid}/.common'
    common = common.open()
    expected_msg = 'Automated save from web GUI: $common repository created.'
    check_single_commit(common, expected_msg, user)

    # 4. Ensure that the new course contains a single commit which is the
    # $common submodule addition.
    expected_msg = 'Automated save from web GUI: $common submodule added.'
    check_single_commit(course, expected_msg, user)

def test_ensure_exists_1(gitolite_new_repo, course0_prefix, user, remote):
    (courseid, prefix) = course0_prefix
    prefix = str(prefix)
    course_fs = GitFSProvider.init_from_args(prefix, remote=remote, gitolite_path=gitolite_new_repo)

    # FuT
    course_fs.ensure_exists(FsType.course, user=user, push=False)

    # Checks.
    # 
    # This could raise a GitError if the course repository has not been correctly
    # initialized.
    course = Repository(prefix)

    # 1. Ensure working tree is clean.
    assert len(course.status()) == 0

    # 2. Ensure that the remote is correctly set.
    assert len(course.remotes) == 1
    origin = course.remotes[0]
    assert origin.name == 'origin'
    assert origin.url == f'{remote}/{courseid}'

    # 3. Ensure only the $common submodule is set, contains a single commit and
    # has the correct 'origin' remote.
    assert len(course.listall_submodules()) == 1
    common = course.submodules['$common']
    assert common.url == f'{remote}/{courseid}/.common'
    common = common.open()
    expected_msg = 'Automated save from web GUI: $common repository created.'
    check_single_commit(common, expected_msg, user)
    assert len(common.remotes) == 1
    origin = common.remotes[0]
    assert origin.name == 'origin'
    # FIXME: The $common remote origin url is not correct and still points to
    # temporary directory.
    # assert origin.url == f'{remote}/{courseid}/.common'

    # 4. Ensure that the new course contains a single commit which is the
    # $common submodule addition.
    expected_msg = 'Automated save from web GUI: $common submodule added.'
    check_single_commit(course, expected_msg, user)
    
@pytest.mark.skip(reason='Have to fix $common submodule creation.')
def test_create_course(remote, tmp_path, user, init_content):
    commit_msg = 'Course created.'
    courseid = 'course0'
    prefix = tmp_path / courseid
    
    # FuTs
    course_fs = GitFSProvider.init_from_args(str(prefix), remote)
    course_fs.ensure_exists(FsType.course, user=user, push=False)
    course_fs.put(
        'course.yaml',
        get_json_or_yaml('course.yaml', init_content),
        msg = commit_msg,
        user = user
    )

    # 1. Ensure that minimal structure is respected.
    assert set(os.listdir(str(prefix))) == set(['course.yaml', '$common', '.git'])

    # 2. Ensure 'course.yaml' is a file.
    assert (prefix / 'course.yaml').is_file()

    # Could raise GitError
    course = Repository(prefix)

    # 3. Ensure that working directory is clean.
    assert len(course.status()) == 0
    
    # 4. Ensure that there is a single commit with the expected metadata.
    commits = [commit for commit in course.walk(course.head.target)]
    assert len(commits) == 1
    assert commits[0].message == f'Automated save from web GUI: {commit_msg}'
    assert (commits[0].author.name, commits[0].author.email) == user
    assert (commits[0].committer.name, commits[0].committer.email) == user
    # TODO: Check signature

    # 5. Ensure that origin is set to correct URL
    assert len(course.remotes) == 1
    # Could raise KeyError
    origin = course.remotes['origin']
    assert origin.url == f'{remote}/{courseid}'

    # 6. Ensure $common is the sole submodule.
    submodules = [sm for sm in course.submodules]
    assert len(submodules) == 1
    assert '$common' == submodules[0].name
    assert set(os.listdir(str(prefix / '$common'))) == set(['.gitkeep', '.git'])

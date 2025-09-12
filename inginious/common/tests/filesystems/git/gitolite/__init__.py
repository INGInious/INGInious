from importlib.resources import files

import pytest

import inginious.common.tests.filesystems.git.gitolite


@pytest.fixture
def admin():
    return 'superadmin'

@pytest.fixture
def default_cfg():
    """ Build the default gitolite configuration.
    """
    return """repo gitolite-admin
    RW+ = superadmin
"""

@pytest.fixture
def course0(default_cfg):
    courseid = 'course0'
    content = default_cfg + f"""\n@course_{courseid} = {courseid} {courseid}/.common
repo @course_{courseid}
    RW+ = superadmin
"""
    return (courseid, content)

@pytest.fixture
def course0_task0(default_cfg):
    courseid = 'course0'
    taskid = 'task0'
    content = default_cfg + f"""\n@course_{courseid} = {courseid} {courseid}/.common {courseid}/{taskid}
repo @course_{courseid}
    RW+ = superadmin
"""
    return (courseid, taskid, content)

def _init_repo(prefix, patch, admin):
    from pygit2 import Diff, Signature, init_repository
    from pygit2.enums import ApplyLocation

    # Load patch
    with open(patch, 'rb') as fd:
        diff = Diff.parse_diff(fd.read())

    # Init temporary gitolite-admin repository
    prefix = str(prefix / 'gitolite-admin')
    r = init_repository(prefix, initial_head='main')

    # Apply patch
    r.apply(diff, ApplyLocation.BOTH)
    tree = r.index.write_tree()
    s = Signature(admin, admin)
    r.create_commit('HEAD', s, s, 'Initial commit', tree, [])

    return prefix

@pytest.fixture
def gitolite_new_repo(admin, tmp_path):
    """ Initialize a temporary gitolite-admin repository based on a Git patch.
    """
    patch = files(inginious.common.tests.filesystems.git.gitolite).joinpath('gitolite.patch')
    return _init_repo(tmp_path, patch, admin)

@pytest.fixture
def gitolite_course0_repo(admin, tmp_path):
    """ Initialize a temporary gitolite-admin repository based on a Git patch.
    """
    patch = files(inginious.common.tests.filesystems.git.gitolite).joinpath('gitolite-course0.patch')
    return _init_repo(tmp_path, patch, admin)

@pytest.fixture
def gitolite_course0_task0_repo(admin, tmp_path):
    """ Initialize a temporary gitolite-admin repository based on a Git patch.
    """
    patch = files(inginious.common.tests.filesystems.git.gitolite).joinpath('gitolite-course0-patch0.patch')
    return _init_repo(tmp_path, patch, admin)

from importlib.resources import files

import pytest

from inginious.common.filesystems.git.gitolite import Gitolite
import inginious.common.tests.filesystems

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
    RW+ = superadmin"""
    return (courseid, content)

@pytest.fixture
def course0_task0(default_cfg):
    courseid = 'course0'
    taskid = 'task0'
    content = default_cfg + f"""\n@course_{courseid} = {courseid} {courseid}/.common {courseid}/{taskid}
repo @course_{courseid}
    RW+ = superadmin"""
    return (courseid, taskid, content)

def test_add_course_content_non_existing(admin, default_cfg, course0): 
    courseid = course0[0]
    expected = course0[1]
    config = default_cfg

    # FuT
    content = Gitolite._add_course_content(config, admin, courseid)

    assert content == expected

def test_add_course_content_existing(admin, course0): 
    courseid = course0[0]
    config = course0[1]

    # FuT
    content = Gitolite._add_course_content(config, admin, courseid)

    assert content is None

def test_add_task_content_non_existing(admin, course0, course0_task0):
    courseid = course0_task0[0]
    expected = course0_task0[2]
    taskid = course0_task0[1]
    config = course0[1]

    #FuT
    content = Gitolite._add_task_content(config, admin, courseid, taskid)

    assert content == expected

def test_add_task_content_existing(admin, course0_task0):
    courseid = course0_task0[0]
    taskid = course0_task0[1]
    config = course0_task0[2]

    #FuT
    content = Gitolite._add_task_content(config, admin, courseid, taskid)

    assert content is None

def _init_repo(prefix, patch, admin):
    from pygit2 import Repository, Diff, Signature, init_repository
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
    patch = files(inginious.common.tests.filesystems).joinpath('gitolite.patch')
    return _init_repo(tmp_path, patch, admin)

@pytest.fixture
def gitolite_course0_repo(admin, tmp_path):
    """ Initialize a temporary gitolite-admin repository based on a Git patch.
    """
    patch = files(inginious.common.tests.filesystems).joinpath('gitolite-course0.patch')
    return _init_repo(tmp_path, patch, admin)

@pytest.fixture
def gitolite_course0_task0_repo(admin, tmp_path):
    """ Initialize a temporary gitolite-admin repository based on a Git patch.
    """
    patch = files(inginious.common.tests.filesystems).joinpath('gitolite-course0-patch0.patch')
    return _init_repo(tmp_path, patch, admin)
   
def test_init_repo_course(admin, gitolite_new_repo):

    from pygit2 import Repository
    prefix = gitolite_new_repo

    gitolite = Gitolite(prefix)

    # FuT
    gitolite.init_repo((admin, admin), 'course0', push=False)

    r = Repository(prefix)

    # 1. Ensure working tree is clean.
    assert len(r.status()) == 0
    
    # 2. Ensure that gitolite-admin contains exactly 2 commits.
    history = [commit for commit in r.walk(r.head.target)]
    assert len(history) == 2

    # 3. Ensure that latest commit content is correct.
    commit = history[0]
    assert commit.author.name == admin
    assert commit.author.email == admin
    assert commit.committer.name == admin
    assert commit.committer.email == admin
    assert commit.message == 'Course <course0> created.'
    diff = r.diff(history[1], history[0])
    expected_diff = """@@ -3,3 +3,6 @@ repo gitolite-admin
 
 repo testing
     RW+     =   @all
+@course_course0 = course0 course0/.common
+repo @course_course0
+    RW+ = superadmin
\\ No newline at end of file"""
    # Skip diff header that may change from run to run.
    assert '\n'.join(diff.patch.splitlines()[4:]) == expected_diff

    
def test_init_repo_course_double(admin, gitolite_course0_repo):

    from pygit2 import Repository
    prefix = gitolite_course0_repo

    gitolite = Gitolite(prefix)
    initial_history = [commit for commit in gitolite.walk(gitolite.head.target)]

    # FuT
    gitolite.init_repo((admin, admin), 'course0', push=False)

    r = Repository(prefix)

    # 1. Ensure working tree is clean.
    assert len(r.status()) == 0
    
    # 2. Ensure that gitolite-admin contains exactly 1 unchanged commits.
    history = [commit for commit in r.walk(r.head.target)]
    assert len(history) == 1
    assert history[0] == initial_history[0]

def test_init_repo_task(admin, gitolite_course0_repo):

    from pygit2 import Repository

    prefix = gitolite_course0_repo
    gitolite = Gitolite(prefix)

    # FuT
    gitolite.init_repo((admin, admin), 'course0', taskid='task0', push=False)

    r = Repository(prefix)

    # 1. Ensure working tree is clean.
    assert len(r.status()) == 0
    
    # 2. Ensure that gitolite-admin contains exactly 2 commits.
    history = [commit for commit in r.walk(r.head.target)]
    assert len(history) == 2

    # 3. Ensure that latest commit content is correct.
    commit = history[0]
    assert commit.author.name == admin
    assert commit.author.email == admin
    assert commit.committer.name == admin
    assert commit.committer.email == admin
    assert commit.message == 'Course <course0>: Task <task0> created.'
    diff = r.diff(history[1], history[0])
    expected_diff = """@@ -3,6 +3,6 @@ repo gitolite-admin
 
 repo testing
     RW+     =   @all
-@course_course0 = course0 course0/.common
+@course_course0 = course0 course0/.common course0/task0
 repo @course_course0
     RW+ = superadmin
\\ No newline at end of file"""
    # Skip diff header that may change from run to run.
    assert '\n'.join(diff.patch.splitlines()[4:]) == expected_diff

def test_init_repo_task_double(admin, gitolite_course0_task0_repo):

    from pygit2 import Repository

    prefix = gitolite_course0_task0_repo
    gitolite = Gitolite(prefix)
    initial_history = [commit for commit in gitolite.walk(gitolite.head.target)]

    # FuT
    gitolite.init_repo((admin, admin), 'course0', taskid='task0', push=False)

    r = Repository(prefix)

    # 1. Ensure working tree is clean.
    assert len(r.status()) == 0
    
    # 2. Ensure that gitolite-admin contains exactly 1 unchanged commit.
    history = [commit for commit in r.walk(r.head.target)]
    assert len(history) == 1
    assert history[0] == initial_history[0]

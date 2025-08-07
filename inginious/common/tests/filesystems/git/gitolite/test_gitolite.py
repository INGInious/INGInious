import pytest

from inginious.common.filesystems.git.gitolite import Gitolite
from inginious.common.tests.filesystems.git.gitolite import *
from inginious.common.tests.filesystems import *


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

def test_init_repo_course(gitolite_new_repo, user):

    from pygit2 import Repository
    prefix = gitolite_new_repo

    gitolite = Gitolite(prefix)

    # FuT
    gitolite.init_repo(user, 'course0', push=False)

    r = Repository(prefix)

    # 1. Ensure working tree is clean.
    assert len(r.status()) == 0
    
    # 2. Ensure that gitolite-admin contains exactly 2 commits.
    history = [commit for commit in r.walk(r.head.target)]
    assert len(history) == 2

    # 3. Ensure that latest commit content is correct.
    check_commit(history[0], 'Course <course0> created.', user)
    diff = r.diff(history[1], history[0])
    expected_diff = """@@ -3,3 +3,6 @@ repo gitolite-admin
 
 repo testing
     RW+     =   @all
+@course_course0 = course0 course0/.common
+repo @course_course0
+    RW+ = superadmin"""
    # Skip diff header that may change from run to run.
    assert '\n'.join(diff.patch.splitlines()[4:]) == expected_diff

def test_init_repo_course_double(admin, gitolite_course0_repo, user):

    from pygit2 import Repository
    prefix = gitolite_course0_repo

    gitolite = Gitolite(prefix)
    initial_history = [commit for commit in gitolite.walk(gitolite.head.target)]

    # FuT
    gitolite.init_repo(user, 'course0', push=False)

    r = Repository(prefix)

    # 1. Ensure working tree is clean.
    assert len(r.status()) == 0
    
    # 2. Ensure that gitolite-admin contains exactly 1 unchanged commits.
    history = [commit for commit in r.walk(r.head.target)]
    assert len(history) == 1
    assert history[0] == initial_history[0]

def test_init_repo_task(admin, gitolite_course0_repo, user):

    from pygit2 import Repository

    prefix = gitolite_course0_repo
    gitolite = Gitolite(prefix)

    # FuT
    gitolite.init_repo(user, 'course0', taskid='task0', push=False)

    r = Repository(prefix)

    # 1. Ensure working tree is clean.
    assert len(r.status()) == 0
    
    # 2. Ensure that gitolite-admin contains exactly 2 commits.
    history = [commit for commit in r.walk(r.head.target)]
    assert len(history) == 2

    # 3. Ensure that latest commit content is correct.
    check_commit(history[0], 'Course <course0>: Task <task0> created.', user)
    diff = r.diff(history[1], history[0])
    expected_diff = """@@ -4,6 +4,6 @@ repo gitolite-admin
 repo testing
     RW+     =   @all
 
-@course_course0 = course0 course0/.common
+@course_course0 = course0 course0/.common course0/task0
 repo @course_course0
     RW+ = superadmin"""
    # Skip diff header that may change from run to run.
    assert '\n'.join(diff.patch.splitlines()[4:]) == expected_diff

def test_init_repo_task_double(admin, gitolite_course0_task0_repo, user):

    from pygit2 import Repository

    prefix = gitolite_course0_task0_repo
    gitolite = Gitolite(prefix)
    initial_history = [commit for commit in gitolite.walk(gitolite.head.target)]

    # FuT
    gitolite.init_repo(user, 'course0', taskid='task0', push=False)

    r = Repository(prefix)

    # 1. Ensure working tree is clean.
    assert len(r.status()) == 0
    
    # 2. Ensure that gitolite-admin contains exactly 1 unchanged commit.
    history = [commit for commit in r.walk(r.head.target)]
    assert len(history) == 1
    assert history[0] == initial_history[0]

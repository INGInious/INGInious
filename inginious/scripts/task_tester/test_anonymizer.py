import subprocess as sp
import tarfile
import shutil
import time
import os
import re

from jinja2 import DictLoader, Environment, select_autoescape 
import pytest

FIELDS_TO_REPLACE = [
    ('user_ip', ''), ('_id', ''), ('archive', ''), ('grade', ''), ('submitted_on', ''),
    ('time', ''), ('@time', ''), ('@email', 'anonymized@anonymized'), ('@username', 'anonymized')
]

BASE_CMD = 'python3 inginious/scripts/task_tester/submission_anonymizer.py '

@pytest.fixture
def get_simple_submission():
    """ Generate a sample submission with varying fields """

    templates = dict()

    templates['tmpl1'] = """_id: 123456789123456789123456
archive: null
best: false
courseid: {{courseid}}
custom: ''
grade: 0.0
input:
    '@attempts': '1'
    '@email': {{user}}_firstname.{{user}}_lastname@test.test
    '@lang': fr
    '@random': []
    '@state': ''
    '@time': '{{time}}'
    '@username': {{user}}
    cmp: |-
        |  in   |  out  |
        |   0   |   1   |
        |   1   |   0   |
    hdl: |-
        CHIP Not {
            IN in;
            OUT out;

            PARTS:
            Nand(a=in, b=in, out=out);
        }
    tst: |-
        load Not.hdl,
        output-file Not.out,
        output-list in%B3.1.3 out%B3.1.3;

        set in 0,
        eval,
        output;

        set in 1,
        eval,
        output;
problems: {}
response_type: rst
result: crash
state: {}
status: error
stderr: ''
stdout: ''
submitted_on: {{time}}
taskid: {{taskid}}
tests: {}
text: Environment not available.
user_ip: 192.0.2.236
username:
{% for user in users %}- {{user}}{% endfor %}
"""
    def _get_simple_submission(users: list, time: str, courseid:str, taskid: str) -> str:
        env = Environment(loader=DictLoader(templates), autoescape=select_autoescape())
        tmpl = env.get_template('tmpl1')
        return tmpl.render(users=users, time=time, courseid=courseid, taskid=taskid)

    yield _get_simple_submission
        
@pytest.fixture
def get_simple_archive(tmp_path, get_simple_submission):
    """ Generate a sample submissions archive for 3 users, with a single submission per user """

    courseid = 'test_course'
    taskid = 'Not'

    print(tmp_path)

    archive = os.path.join(tmp_path, 'submissions.tgz')
    tmp = os.path.join(tmp_path, 'tmp')

    os.mkdir(tmp)
    users = ['user1', 'user2', 'user3']

    with tarfile.open(archive, mode='w:gz') as tar:
        for user in users:
            current_time = time.strftime('%Y-%m-%d-%H:%M:%S', time.localtime())
            user_path = '%s/%s/%s' % (taskid, user, current_time)
            os.makedirs(os.path.join(tmp, user_path))
            sub_name = '%s/submission.test' % user_path
            sub_path = os.path.join(tmp, sub_name)
            sub = get_simple_submission([user], current_time, courseid, taskid)
            with open(sub_path, 'w') as fd:
                fd.write(sub)
            tar.add(sub_path, sub_name)

    yield tmp_path, courseid, taskid, archive, users
    
    shutil.rmtree(tmp_path)

@pytest.fixture
def mock_inginious_install(tmp_path):

    prefix = os.path.join(tmp_path, 'INGInious')
    os.mkdir(prefix)
    task_dir = os.path.join(prefix, 'tasks')
    os.mkdir(task_dir)
    os.mkdir(os.path.join(prefix, 'backups'))

    config = """backend: local
backup_directory: {prefix}/backups
local-config: {{}}
mongo_opt:
  database: INGInious
  host: localhost
session_parameters:
  ignore_change_ip: false
  secret_key: e2248350925fdedd7259fb52847232effbf1a10610fsgsdfgsdfgsdfgsdfgsdfg
  secure: false
  timeout: 86400
superadmins:
- superadmin
tasks_directory: {prefix}/tasks
use_minified_js: true
"""
    config_path = os.path.join(prefix, 'configuration.yaml')
    with open(config_path, 'w') as fd:
        fd.write(config.format(prefix=prefix))

    def _mock(courseid, taskid):
        os.makedirs(os.path.join(task_dir, courseid, taskid))
        return prefix, config_path

    yield _mock 

def check_anonymization(path, data, cmd):

    """ Run FUT """
    out = sp.run(cmd, shell=True, capture_output=True)

    """ Get archive data """
    _, courseid, taskid, archive, users = data

    """ FUT correctly ended """
    assert out.returncode == 0

    """ No error has been mentioned """
    assert out.stderr == b''

    """ The course directory has been created """
    assert courseid in os.listdir(path)

    task_path = os.path.join(path, courseid, taskid, 'test')
    anonymized = os.listdir(task_path)

    """ Ensure that we get one anonymized submission per student """
    assert len(anonymized) == len(users)

    """ For each anonymized submission, ensure that the required fields have been cleared """
    for submission in anonymized:
        
        """ Load submission content """
        with open(os.path.join(task_path, submission), 'r') as fd:
            content = fd.read()

        """ Check for cleared fields """
        for field, value in FIELDS_TO_REPLACE:
            if value == '':
                assert field not in content
            else:
                for element in re.findall('%s(.*)' % field, content):
                    assert element.split(':')[-1].strip() == value

def test_simple_prefix(get_simple_archive):
    """ Test a simple submission archive with 3 users and a single submission per user.
        The INGInious modules are not present.
    """

    try:
        from inginious.common.base import load_json_or_yaml
        pytest.skip("This test does not expect the INGInious modules")
    except ModuleNotFoundError:
        pass

    """ Get archive data """
    path, courseid, taskid, archive, users = get_simple_archive

    """ Run FUT """
    cmd = BASE_CMD + "--prefix={prefix} {courseid} {archive}".format(courseid=courseid, archive=archive, prefix=path)
    check_anonymization(path, get_simple_archive, cmd)

def test_simple_configuration(get_simple_archive, mock_inginious_install):
    """ Test a simple submission archive with 3 users and a single submission per user.
        The INGInious modules must be present.
    """

    try:
        from inginious.common.base import load_json_or_yaml
    except ModuleNotFoundError:
        pytest.skip("This test expects the INGInious modules")

    """ Get archive data """
    path, courseid, taskid, archive, users = get_simple_archive
    prefix, config = mock_inginious_install(courseid, taskid)

    """ Run FUT """
    cmd = BASE_CMD + "--configuration={config} {courseid} {archive}".format(courseid=courseid, archive=archive, config=config)

    check_anonymization(os.path.join(prefix, 'tasks'), get_simple_archive, cmd)

def test_simple_no_configuration(get_simple_archive, mock_inginious_install):
    """ Test a simple submission archive with 3 users and a single submission per user.
        The INGInious modules must be present.
    """

    try:
        from inginious.common.base import load_json_or_yaml
    except ModuleNotFoundError:
        pytest.skip("This test expects the INGInious modules")

    """ Get archive data """
    path, courseid, taskid, archive, users = get_simple_archive
    prefix, config = mock_inginious_install(courseid, taskid)

    """ Run FUT """
    cmd = BASE_CMD + "--configuration={config} {courseid} {archive}".format(courseid=courseid, archive=archive, config='non-existing-path')
    out = sp.run(cmd, capture_output=True, shell=True)
    assert out.returncode == 1

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import sys
import os
from setuptools import setup, find_packages

install_requires = [
    "docker==7.1.0",
    "docutils==0.21.2",
    "Flask==3.0.2",
    "Flask-Mail==0.10.0",
    "itsdangerous==2.2.0",
    "Jinja2==3.1.5",
    "lti==0.9.5",
    "MarkupSafe==3.0.2",
    "msgpack==1.1.0",
    "natsort==8.4.0",
    "psutil==6.1.1",
    "pymongo==4.11",
    "pytidylib==0.3.2",
    "PyYAML==6.0.2",
    "pyzmq==26.2.1",
    "requests==2.31.0",
    "requests-oauthlib==2.0.0",
    "sh==2.2.1",
    "watchdog==6.0.0",
    "Werkzeug==3.0.1",
    "WsgiDAV==4.3.3",
    "zipstream==1.1.4",
    "pytidylib==0.3.2",
    "argon2-cffi == 23.1.0"
]

test_requires = [
    "pytest == 8.3.4",
    "coverage == 7.6.9"
]

doc_requires = [
    "ipython==8.12.3",
    "sphinx==7.4.7",
    "sphinx-autodoc-typehints==2.3.0",
    "sphinx-rtd-theme==3.0.0",
    "sphinx-tabs==3.4.5"
]

entry_points = {} if os.environ.get("INGINIOUS_COMPOSE") else {
    'console_scripts': [
        "inginious-agent-docker = inginious.scripts.agent_docker:main",
        "inginious-agent-mcq = inginious.scripts.agent_mcq:main",
        "inginious-backend = inginious.scripts.backend:main",
        "inginious-webapp = inginious.scripts.webapp:main",
        "inginious-webdav = inginious.scripts.webdav:main",
        "inginious-install = inginious.scripts.install:main",
        "inginious-autotest = inginious.scripts.autotest:main",
        "inginious-synchronize = inginious.scripts.sync.synchronize:main",
        "inginious-container-update = inginious.scripts.container_update:main",
        "inginious-database-update = inginious.scripts.database_update:main",
        "inginious-test-task = inginious.scripts.task_tester.task_tester:main",
        "inginious-submission-anonymizer = inginious.scripts.task_tester.submission_anonymizer:main"
    ]
}

# Setup
setup(
    name="INGInious",
    use_scm_version=True,
    description="An intelligent grader that allows secured and automated testing of code made by students.",
    packages=find_packages(),
    setup_requires=['setuptools_scm==8.1.0'],
    install_requires=install_requires,
    tests_require=test_requires,
    extras_require={
        "ldap": ["ldap3==2.9.1"],
        "saml2": ["python3-saml==1.16.0"],
        "test": test_requires,
        "doc": test_requires + doc_requires
    },
    entry_points=entry_points,
    include_package_data=True,
    test_suite='nose.collector',
    author="INGInious contributors",
    author_email="inginious@info.ucl.ac.be",
    license="AGPL 3",
    url="https://github.com/INGInious/INGInious",
    long_description=open(os.path.join(os.path.dirname(__file__), 'README.rst'), encoding='utf8').read()
)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from hashlib import sha256
import tempfile
import tarfile
import shutil
import sys
import os
import re

try:
    from inginious.common.filesystems.local import LocalFSProvider
    from inginious.common.base import load_json_or_yaml, loads_json_or_yaml, get_json_or_yaml
    inginious_modules = True
except ModuleNotFoundError:
    inginious_modules = False


FIELDS_TO_REPLACE = [
    ('user_ip', ''), ('_id', ''), ('archive', ''), ('grade', ''), ('submitted_on', ''),
    ('\'@time\'', ''), ('@email', 'anonymized@anonymized'), ('@username', 'anonymized')
]

_EMPTY_FIELDS = []
_OTHER_FIELDS = []


def anonymize(prefix: str, archive: str):
    """ Anonymize all the submissions contained in an archive generated via the Webapp interface
        This script removes the fields allowing the identification of the original author in each
        submission.

        :param prefix: The FileSystemProvider prefix of the current INGInious installation.
        :param archive: The path toward the archive containing the provided submissions.
    """

    if inginious_modules:
        fs = LocalFSProvider(prefix)

    """ The submission files are treated in a temporary directory in a ramfs before being written
        on the filesystem.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with tarfile.open(archive, 'r') as tar:
            """ Explore each entry of the archive """
            while entry := tar.next():

                """ Sanity checks """
                if entry is None: break
                if not entry.isfile(): continue

                filename, extension = os.path.splitext(entry.name)
                if extension != ".test": continue

                """ Get submission file content """
                tar.extract(entry, path=tmpdir, filter="data")
                with open(os.path.join(tmpdir, entry.name), 'r') as fd:
                    content = fd.read()

                """ Generate the test file content """
                if inginious_modules:

                    """ If INGInious modules are available, we can parse the submission """
                    new_content = loads_json_or_yaml(entry.name, content)

                    """ Get task ID """
                    try:
                        task = new_content['taskid']
                    except KeyError:
                        print('Submission <%s> malformed' % entry.name)
                        continue

                else:

                    """ INGInious modules are not available so we have to parse the submission by
                        hand.
                    """

                    """ The submission format is 'taskid/username' """
                    match = re.search('taskid:(.*)', content)
                    if not match:
                        print('Submission <%s> malformed' % entry.name)
                        continue

                    head, tail = match.span()
                    task = content[head:tail].split(':')[-1].strip()

                """ Remove identifiable fields """
                new_content = re.sub(r'(%s):(.*)' % '|'.join(_EMPTY_FIELDS), '', content)

                for field, new_value in _OTHER_FIELDS:
                    new_content = re.sub(r'\'%s\':(.*)' % field, '\'{field}\': {new_value}'.format(field=field, new_value=new_value), new_content)

                """ Remove usernames """
                # TODO test this if multiple users 
                #new_content = re.sub(r'username:(\n|\r\n|\r)[-(.*)(\r|\r\n|\n)]*', '', new_content)
                new_content = re.sub(r'username:(\n|\r\n|\r)-(.*)', '', new_content)

                """ Remove empty lines """
                new_content = '\n'.join(filter(lambda x: not re.match(r'^\s*$', x), new_content.splitlines()))

                new_name = '_'.join(filename.split('/'))
                new_name_hash = sha256(new_name.encode('utf-8')).hexdigest()
                new_submission_filename = '%s.test' % new_name_hash
                new_submission_file = os.path.join(task, 'test', new_submission_filename)

                if inginious_modules:
                    new_content = get_json_or_yaml('', new_content)
                    fs.put(new_submission_file, new_content)
                else:
                    new_submission_file = os.path.join(prefix, new_submission_file)
                    try:
                        """ Write the anonymized submission """
                        with open(new_submission_file, 'w') as fd: fd.write(new_content)
                    except FileNotFoundError:
                        """ This is the first submission we write for a given task, we have to create the associated 
                            task directory
                        """
                        os.makedirs(os.path.dirname(new_submission_file))
                        with open(new_submission_file, 'w') as fd: fd.write(new_content)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        'Anonymize INGInious submissions and install them in an INGInious instance if possible.'
    )
    parser.add_argument('courseid', type=str, help='The course ID corresponding to the submissions'
                                                    'to anonymize.')
    parser.add_argument('archive', type=str, help='Path to the submissions archive.')
    parser.add_argument('-c', '--configuration', type=str, help='Path towards an INGInious instance configuration file.\
        This is the preferred method to directly install the anonymized submissions within an existing instance.')
    parser.add_argument('-p', '--prefix', type=str, help='The path towards the tasks directory of an existing INGInious instance.\
        It will be used if this script is run outside of a valid INGInious installation')
    args = parser.parse_args()

    archive = args.archive
    courseid = args.courseid
    prefix = args.prefix
    config_path = args.configuration

    """ Configuration file safety checks """
    if config_path and (not os.path.exists(config_path) or not os.path.isfile(config_path)):
        print('Config file does not exist, nothing to do.')
        exit(1)

    """ Prefix path safety checks """
    if prefix and not os.path.exists(prefix):
        print('Prefix path does not exist, nothing to do.')
        exit(1)

    """ Achive path safety check """
    if not os.path.exists(archive):
        print('Archive path does not exist, nothing to do.')
        exit(1)

    if config_path:
        if inginious_modules:
            """ If a configuration file is provided and INGInious modules are present, we use the 'tasks_directory' entry from
                the configuration as prefix.
            """
            config = load_json_or_yaml(config_path)
            if prefix: print('Ignoring provided prefix')
            prefix = config['tasks_directory']
        else:
            """ If INGInious modules are not present, we fallback on the prefix argument. If it is present we use it else we
                create an output directory in the current working directory.
            """
            print('You asked to use the INGInious modules but they are not installed. Fallback on --prefix if provided.')

    if not prefix:
        print('No prefix available. Impossible to directly install the submissions within the course directory. Fallback to\
            current directory.')
        prefix = os.getcwd()

    prefix = os.path.join(os.path.abspath(prefix), courseid)

    for field, new_value in FIELDS_TO_REPLACE:
        if new_value == '':
            _EMPTY_FIELDS.append(field)
        else:
            _OTHER_FIELDS.append((field, new_value))

    anonymize(prefix, archive)


if __name__ == "__main__":
    main()

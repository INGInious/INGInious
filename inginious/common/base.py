# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Basic dependencies for every modules that uses INGInious """
import codecs
import json
import os.path
import hashlib
import re

import inginious.common.custom_yaml
from collections import OrderedDict, namedtuple


GitInfo = namedtuple("GitInfo", ["realname", "email", "username", "key"])

def id_checker(id_to_test):
    """Checks if a id is correct"""
    return bool(re.match(r'[a-z0-9\-\._]+$', id_to_test, re.IGNORECASE))


def id_checker_tests(id_to_test):
    """Checks if a id is correct"""
    return bool(re.match(r'[a-z0-9\-\._*]+$', id_to_test, re.IGNORECASE))


def load_json_or_yaml(file_path):
    """ Load JSON or YAML depending on the file extension. Returns a dict """
    with open(file_path, "r") as f:
        if os.path.splitext(file_path)[1] == ".json":
            return json.load(f)
        else:
            return inginious.common.custom_yaml.load(f)


def loads_json_or_yaml(file_path, content):
    """ Load JSON or YAML depending on the file extension. Returns a dict """
    if os.path.splitext(file_path)[1] == ".json":
        return json.loads(content)
    else:
        return inginious.common.custom_yaml.load(content)


def write_json_or_yaml(file_path, content):
    """ Write JSON or YAML depending on the file extension. """
    with codecs.open(file_path, "w", "utf-8") as f:
        f.write(get_json_or_yaml(file_path, content))


def get_json_or_yaml(file_path, content):
    """ Generate JSON or YAML depending on the file extension. """
    if os.path.splitext(file_path)[1] == ".json":
        return json.dumps(content, sort_keys=False, indent=4, separators=(',', ': '))
    else:
        return inginious.common.custom_yaml.dump(content)


def hash_file(fileobj):
    """
    :param fileobj: a file object
    :return: a hash of the file content
    """
    hasher = hashlib.md5()
    buf = fileobj.read(65536)
    while len(buf) > 0:
        hasher.update(buf)
        buf = fileobj.read(65536)
    return hasher.hexdigest()


def directory_content_with_hash(directory):
    """
    :param directory: directory in which the function list the files
    :return: dict in the form {file: (hash of the file, stat of the file)}
    """
    output = {}
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            p = os.path.join(root, filename)
            file_stat = os.stat(p)
            with open(p, 'rb') as f:
                output[os.path.relpath(p, directory)] = (hash_file(f), file_stat.st_mode)
    return output


def directory_compare_from_hash(from_directory, to_directory):
    """
    :param from_directory: dict in the form {file: (hash of the file, stat of the file)} from directory_content_with_hash
    :param to_directory: dict in the form {file: (hash of the file, stat of the file)} from directory_content_with_hash
    :return: a tuple containing two list: the files that should be uploaded to "to_directory" and the files that should be removed from "to_directory"
    """
    from_directory = dict(
        [(os.path.normpath(path), (filehash, stat)) for path, (filehash, stat) in from_directory.items()])
    to_directory = dict([(os.path.normpath(path), (filehash, stat)) for path, (filehash, stat) in to_directory.items()])

    to_upload = []
    to_delete = []
    for path, (filehash, stat) in from_directory.items():
        if not path in to_directory or to_directory[path] != (filehash, stat):
            to_upload.append(path)
    for path in to_directory:
        if path not in from_directory:
            to_delete.append(path)
    return (to_upload, to_delete)


def dict_from_prefix(prefix, dictionary):
    """
        >>> from collections import OrderedDict
        >>> od = OrderedDict()
        >>> od["problem[q0][a]"]=1
        >>> od["problem[q0][b][c]"]=2
        >>> od["problem[q1][first]"]=1
        >>> od["problem[q1][second]"]=2
        >>> AdminCourseEditTask.dict_from_prefix("problem",od)
        OrderedDict([('q0', OrderedDict([('a', 1), ('b', OrderedDict([('c', 2)]))])), ('q1', OrderedDict([('first', 1), ('second', 2)]))])
    """
    o_dictionary = OrderedDict()
    for key, val in dictionary.items():
        if key.startswith(prefix):
            o_dictionary[key[len(prefix):].strip()] = val
    dictionary = o_dictionary

    if len(dictionary) == 0:
        return None
    elif len(dictionary) == 1 and "" in dictionary:
        return dictionary[""]
    else:
        return_dict = OrderedDict()
        for key, val in dictionary.items():
            ret = re.search(r"^\[([^\]]+)\](.*)$", key)
            if ret is None:
                continue
            return_dict[ret.group(1)] = dict_from_prefix("[{}]".format(ret.group(1)), dictionary)
        return return_dict

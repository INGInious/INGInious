# pylint: disable=redefined-outer-name
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import copy
import os
import shutil
import tempfile

import pytest

from inginious.common.base import (
    directory_compare_from_hash,
    directory_content_with_hash,
    hash_file,
    id_checker,
    load_json_or_yaml,
    write_json_or_yaml,
)


@pytest.fixture()
def init_tmp_dir(request):
    """Create a temporary folder"""
    dir_path = tempfile.mkdtemp()
    yield (dir_path)
    """ Some FUT could create content in the prefix """
    shutil.rmtree(dir_path)


class TestIdChecker(object):
    """Test the id checker"""

    def test_id_checker_valid_1(self):
        assert id_checker("azertyuiopZERTYUIO65456_5-a") is True

    def test_id_checker_invalid_1(self):
        assert id_checker("a@a") is False

    def test_id_checker_invalid_2(self):
        assert id_checker("") is False

    def test_id_checker_invalid_3(self):
        assert id_checker("test/test") is False


class TestJSONYAMLReaderWriter(object):
    """Test the functions load_json_or_yaml and write_json_or_yaml"""

    def test_json_read(self, init_tmp_dir):
        tmp_dir = init_tmp_dir
        with open(os.path.join(tmp_dir, "input.json"), "w") as f:
            f.write('{"key1":"data1","key2":{"key3":[1,2]}}')
        assert load_json_or_yaml(os.path.join(tmp_dir, "input.json")) == {
            "key1": "data1",
            "key2": {"key3": [1, 2]},
        }

    def test_json_write(self, init_tmp_dir):
        tmp_dir = init_tmp_dir
        write_json_or_yaml(
            os.path.join(tmp_dir, "output.json"),
            {"key1": "data1", "key2": {"key3": [1, 2]}},
        )
        assert load_json_or_yaml(os.path.join(tmp_dir, "output.json")) == {
            "key1": "data1",
            "key2": {"key3": [1, 2]},
        }

    def test_yaml_read(self, init_tmp_dir):
        tmp_dir = init_tmp_dir
        with open(os.path.join(tmp_dir, "input.yaml"), "w") as f:
            f.write("""
            key1: data1
            key2:
                key3:
                    - 1
                    - 2
            """)
        assert load_json_or_yaml(os.path.join(tmp_dir, "input.yaml")) == {
            "key1": "data1",
            "key2": {"key3": [1, 2]},
        }

    def test_yaml_write(self, init_tmp_dir):
        tmp_dir = init_tmp_dir
        write_json_or_yaml(
            os.path.join(tmp_dir, "output.yaml"),
            {"key1": "data1", "key2": {"key3": [1, 2]}},
        )
        assert load_json_or_yaml(os.path.join(tmp_dir, "output.yaml")) == {
            "key1": "data1",
            "key2": {"key3": [1, 2]},
        }


class TestDirectoryHash(object):
    """Test all the functions that involves file hash"""

    def test_hash_file(self):
        with tempfile.TemporaryFile() as tmp:
            tmp.write(b"some random text")
            tmp.flush()
            tmp.seek(0)
            the_hash = hash_file(tmp)
        assert the_hash == "07671a038c0eb43723d421693b073c3b"

    def test_directory_content_with_hash(self, init_tmp_dir):
        temp_dir = init_tmp_dir
        test_dir = os.path.join(temp_dir, "test1")

        # Create data
        os.mkdir(test_dir)
        os.mkdir(os.path.join(test_dir, "subdir"))

        goal = {}

        with open(os.path.join(test_dir, "file1"), "w") as f:
            f.write("random text 1")
        goal["file1"] = (
            "d7e62e68f60f6974309b263192d5fea2",
            os.stat(os.path.join(test_dir, "file1")).st_mode,
        )

        with open(os.path.join(test_dir, "file2"), "w") as f:
            f.write("random text 2")
        goal["file2"] = (
            "5ae848320fda7796dc2f3a1a68300e07",
            os.stat(os.path.join(test_dir, "file2")).st_mode,
        )

        with open(os.path.join(test_dir, "subdir", "file3"), "w") as f:
            f.write("random text 3")
        goal["subdir/file3"] = (
            "312aa75e0816015cdb5ef1989de7bf3f",
            os.stat(os.path.join(test_dir, "subdir", "file3")).st_mode,
        )

        # Test the function
        assert directory_content_with_hash(test_dir) == goal

    def test_directory_compare_from_hash(self, init_tmp_dir):
        temp_dir = init_tmp_dir
        test_dir = os.path.join(temp_dir, "test2")

        # Create data
        os.mkdir(test_dir)
        os.mkdir(os.path.join(test_dir, "subdir"))

        with open(os.path.join(test_dir, "file1"), "w") as f:
            f.write("random text 1")
        with open(os.path.join(test_dir, "file2"), "w") as f:
            f.write("random text 2")
        with open(os.path.join(test_dir, "subdir", "file3"), "w") as f:
            f.write("random text 3")
        with open(os.path.join(test_dir, "file4"), "w") as f:
            f.write("random text 4")
        with open(os.path.join(test_dir, "file5"), "w") as f:
            f.write("random text 5")
        with open(os.path.join(test_dir, "file6"), "w") as f:
            f.write("random text 6")

        l1 = directory_content_with_hash(test_dir)
        l2 = copy.deepcopy(l1)

        # Perturb the data
        l2["file1"] = (l2["file1"][0], 0)
        l2["file2"] = ("not a valid hash", l2["file2"])
        l2["file4"] = ("not a valid hash", 0)
        del l2["file5"]

        # Compare and test
        to_update, to_delete = directory_compare_from_hash(l2, l1)
        assert set(to_update) == set(["file1", "file2", "file4"])
        assert set(to_delete) == set(["file5"])

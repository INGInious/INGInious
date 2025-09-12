# pylint: disable=redefined-outer-name

import os
import tempfile
import shutil
import hashlib

import pytest

from inginious.common.filesystems.local import LocalFSProvider
from inginious.common.filesystems.git import GitFSProvider


FS = {
    'test1.txt': b'test string 1',
    'subfolder/test2.txt': b'test string 2',
}

FS = {filepath: {'content': content, 'hash': hash(content)} for filepath, content in FS.items()}

def compare_files(filepath, content):
    return FS[filepath]['hash'] == hash(content)

def myhash(content: str) -> str:
    return hashlib.sha256(content).hexdigest()

@pytest.fixture(params=[LocalFSProvider, GitFSProvider])
def init_tmp_dir(request):
    """ Create a temporary folder """
    dir_path = tempfile.mkdtemp()
    yield (request.param, dir_path)
    """ Some FUT could create content in the prefix """
    shutil.rmtree(dir_path)

@pytest.fixture
def init_prefix(init_tmp_dir):
    """ Create a prefix directory for the FSProvider under test """
    provider, tmp_dir = init_tmp_dir
    prefix = 'prefix'
    full_prefix = os.path.join(tmp_dir, prefix)
    os.mkdir(full_prefix)
    provider = provider(full_prefix)

    yield (provider, full_prefix)

    if os.path.exists(full_prefix):
        shutil.rmtree(full_prefix)

@pytest.fixture
def init_prefix_with_file(init_prefix):
    """ Create a prefix folder with a direct file within
        /tmp/<tmp_dir>/prefix
        |_ test1.txt
    """
    provider, full_prefix = init_prefix

    filename = 'test1.txt'
    filepath = os.path.join(full_prefix, filename)
    with open(filepath, 'wb') as fd:
        fd.write(FS[filename]['content'])

    yield (provider, full_prefix, filename)

    if os.path.exists(filepath):
        os.remove(filepath)

@pytest.fixture
def init_subfolder(init_prefix):
    """ Create a prefix folder with a subfolder named 'subfolder' within
        /tmp/<tmp_dir>/prefix
        |_ subfolder/
    """

    provider, full_prefix = init_prefix

    test_dir = 'subfolder'
    subdir = os.path.join(full_prefix, test_dir)
    os.mkdir(subdir)

    yield (provider, full_prefix, test_dir)

    if os.path.exists(subdir):
        os.rmdir(subdir)

@pytest.fixture
def init_subfolder_with_file(init_subfolder):
    """ Generate
        /tmp/<tmp_dir>/prefix
        |_ subfolder/
            |_ test2.txt (file2)
    """

    provider, full_prefix, subfolder = init_subfolder

    filename = 'test2.txt'
    filepath = subfolder + '/' + filename
    full_filepath = os.path.join(full_prefix, filepath)
    with open(full_filepath, 'wb') as fd:
        fd.write(FS[filepath]['content'])

    yield (provider, full_prefix, filepath)

    if os.path.exists(full_filepath):
        os.remove(full_filepath)

@pytest.fixture
def init_full(init_prefix_with_file, init_subfolder_with_file):
    """ Generates
        /tmp/<tmp_dir>/prefix
        |_ test.txt (file1)
        |_ subfolder/
            |_ test.txt (file2)
    """
    provider, prefix, file1 = init_prefix_with_file
    _, _, file2 = init_subfolder_with_file
    return (provider, prefix, file1, file2)


class TestInit:
    """ FileSystemProvider initialization """

    def test_prefix(self, init_prefix):
        """ Test the prefix of a newly generated FileSystemProvider without trailing slash """
        provider, prefix = init_prefix
        assert provider.prefix == prefix + '/'

    def test_prefix_trailing(self, init_tmp_dir):
        """ Test the prefix of a newly generated FileSystemProvider with trailing slash """
        provider, tmp_dir = init_tmp_dir
        prefix = tmp_dir + 'prefix/'
        provider = provider(prefix)
        assert provider.prefix == prefix

    def test_prefix_non_existing(self, init_tmp_dir):
        """ Test the prefix of a newly generated LocalFSProvider with non-existing prefix """
        provider, tmp_dir = init_tmp_dir
        prefix = tmp_dir + 'prefix'
        provider = provider(prefix)
        assert provider.prefix == prefix + '/'


class TestFromSubfolder:
    """ from_subfolder() tests """

    def test_subfolder(self, init_subfolder):
        """ Test the creation of a new FileSystemProvider whose prefix is a subfolder of an existing one """
        provider, prefix, subfolder = init_subfolder
        sub_provider = provider.from_subfolder(subfolder)
        assert sub_provider != provider # from_subfolder must return a new FileSystemProvider object
        assert sub_provider.prefix == os.path.join(prefix, subfolder) + '/'


class TestExists:
    """ exists() tests """

    def test_exists_prefix_and_subfolder(self, init_subfolder):
        """ Test if LocalFSP can check that its prefix and subfolder exists """
        provider, prefix, subfolder = init_subfolder
        assert provider.exists()
        assert provider.exists(os.path.join(prefix, subfolder))

    def test_exists_non_existing_path(self, init_tmp_dir):
        """ Test if LocalFSP can check that a subfolder does not exist """
        provider, tmp_dir = init_tmp_dir
        provider = provider(tmp_dir)
        assert not provider.exists(os.path.join(provider.prefix, 'test'))

    def test_exists_non_existing_prefix(self, init_tmp_dir):
        """ Test if LocalFSP can check that its prefix does not exist """
        provider, tmp_dir = init_tmp_dir
        prefix = os.path.join(tmp_dir, 'prefix')
        provider = provider(prefix)
        assert not provider.exists()


class TestEnsureExists:
    """ ensure_exists() tests """

    def test_ensure_exists(self, init_subfolder_with_file):
        """ Test if LocalFSP can check the existence of its prefix without overriding its content """
        provider, prefix, filepath = init_subfolder_with_file
        provider.ensure_exists()
        assert os.path.exists(os.path.join(prefix, filepath))

    def test_ensure_exists_prefix(self, init_tmp_dir):
        """ Test if LocalFSP can create its prefix folder if it does not exist """
        provider, tmp_dir = init_tmp_dir
        prefix = os.path.join(tmp_dir, 'prefix')
        provider = provider(prefix)
        provider.ensure_exists()
        assert os.path.exists(prefix)

    def test_ensure_exists_subfolder(self, init_tmp_dir):
        """ Test if LocalFSP can create its prefix in nested non-existing folders """
        provider, tmp_dir = init_tmp_dir
        prefix1 = os.path.join(tmp_dir, 'prefix1')
        prefix2 = os.path.join(prefix1, 'prefix2')
        provider = provider(prefix2)
        provider.ensure_exists()
        assert os.path.exists(prefix2)


class TestPut:
    """ put() tests """
    # TODO


class TestGetFd:
    """ get_fd() tests """

    def test_get_fd_full_path(self, init_prefix_with_file):
        """ Test getting fd on valid full path """
        provider, prefix, filename = init_prefix_with_file
        with pytest.raises(FileNotFoundError):
            provider.get_fd(os.path.join(prefix, filename))

    def test_get_fd_non_existing_file(self, init_prefix):
        """ Test get_fd on non-existing filepath """
        provider, _ = init_prefix
        with pytest.raises(FileNotFoundError):
            provider.get_fd('test.txt')

    def test_get_fd_directory(self, init_subfolder):
        """ Test get_fd on filepath leading to a folder """
        provider, _, subfolder = init_subfolder
        with pytest.raises(IsADirectoryError):
            provider.get_fd(subfolder)

    def test_get_fd(self, init_prefix_with_file):
        """ Test getting fd on a valid file """
        provider, _, filename = init_prefix_with_file
        with provider.get_fd(filename) as fd:
            assert compare_files(filename, fd.read())


class TestGet:
    """ get() tests """
    # TODO


class TestList:
    """ list() tests """

    def test_list_file_populated(self, init_full):
        """ List direct files """
        provider, _, filename, _ = init_full
        assert provider.list(files=True, folders=False) == [filename]

    def test_list_file_populated_recursive(self, init_full):
        """ List all files recursively """
        provider, _, file1, file2 = init_full
        assert set(provider.list(files=True, folders=False, recursive=True)) == set([file1, file2])

    def test_list_folder_populated(self, init_full):
        """ List direct directories """
        provider, _, _, file2 = init_full
        assert set(provider.list(files=False, folders=True)) == set(['%s/' % file2.split('/')[0]])

    def test_list_folder_populated_recursive(self, init_full):
        """ List all directories recursively """
        provider, _, _, file2 = init_full
        assert set(provider.list(files=False, folders=True, recursive=True)) == set(['%s/' % file2.split('/')[0]])

    def test_list_empty(self, init_prefix):
        """ List direct empty prefix """
        provider, _ = init_prefix
        assert provider.list(files=True, folders=True) == []

    def test_list_empty_recursively(self, init_prefix):
        """ List empty prefix recursively """
        provider, _ = init_prefix
        assert provider.list(files=True, folders=True, recursive=True) == []

    def test_list_populated_disabled(self, init_full):
        """ List nothing """
        provider, _, _, _ = init_full
        assert provider.list(files=False, folders=False) == []

    def test_list_populated_disabled_recursive(self, init_full):
        """ List nothing recursively """
        provider, _, _, _ = init_full
        assert provider.list(files=False, folders=False, recursive=True) == []

    def test_list_populated(self, init_full):
        """ List all direct prefix's content """
        provider, _, file1, file2 = init_full
        assert set(provider.list(files=True, folders=True)) == set([file1, '%s/' % file2.split('/')[0]])

    def test_list_populated_recursively(self, init_full):
        """ List all prefix's content recursively """
        provider, prefix, file1, file2 = init_full
        assert set(provider.list(files=True, folders=True, recursive=True)) == set([file1, file2, '%s/' % file2.split('/')[0]])

    def test_list_non_existing_prefix(self, init_tmp_dir):
        """ Try to list non-existing prefix """
        provider, tmp_dir = init_tmp_dir
        prefix = os.path.join(tmp_dir, 'prefix')
        provider = provider(prefix)
        with pytest.raises(FileNotFoundError):
            provider.list()

class TestDelete:
    """ delete() tests """

    def test_delete_non_existing(self, init_tmp_dir):
        """ Delete non-existing prefix """
        provider, tmp_dir = init_tmp_dir
        prefix = os.path.join(tmp_dir, 'prefix')
        provider = provider(prefix)
        with pytest.raises(FileNotFoundError):
            provider.delete()

    def test_delete_empty_prefix(self, init_prefix):
        """ Delete existing empty prefix """
        provider, prefix = init_prefix
        provider.delete()
        assert not os.path.exists(prefix)

    def test_delete_populated_prefix(self, init_full):
        """ Delete a populated prefix """
        provider, prefix, _, _ = init_full
        provider.delete()
        assert not os.path.exists(prefix)

    def test_delete_subfolder_file(self, init_full):
        """ Delete a subfolder file without removing the subfolder """
        provider, prefix, file1, file2 = init_full
        provider.delete(file2)
        assert os.path.exists(os.path.join(prefix, file1))
        assert os.path.exists(os.path.join(prefix, file2.split('/')[0]))

    def test_delete_subfolder(self, init_full):
        """ Delete a subfolder """
        provider, prefix, file1, file2 = init_full
        subfolder = file2.split('/')[0]
        provider.delete(subfolder)
        assert os.path.exists(os.path.join(prefix, file1))
        assert not os.path.exists(os.path.join(prefix, subfolder))

    def test_delete_fullpath(self, init_full):
        """ Try to delete a full path """
        provider, prefix, _, file2 = init_full
        subfolder = file2.split('/')[0]
        with pytest.raises(FileNotFoundError):
            provider.delete(os.path.join(prefix, subfolder))


class TestGetLastModificationTime:
    """ get_last_modification_time() test """
    # TODO


class TestMove:
    """ move() tests """

    def test_move(self, init_full):
        """ Try to move a file at the same directory level """
        provider, prefix, file1, file2 = init_full
        file1_path = os.path.join(prefix, file1)
        dest = 'moved_%s' % file1
        full_dest = os.path.join(prefix, dest)
        provider.move(file1, dest)
        assert not os.path.exists(file1_path)
        assert os.path.exists(full_dest)
        with open(full_dest, 'rb') as fd:
            assert compare_files(file1, fd.read())
        assert os.path.exists(os.path.join(prefix, file2))

    def test_move_non_existing_file(self, init_prefix):
        """ Try to move a non existing file """
        provider, _ = init_prefix
        with pytest.raises(FileNotFoundError):
            provider.move('non-existing.src', 'non-existing.dst')


class TestCopyTo:
    """ copy_to() tests """
    # TODO

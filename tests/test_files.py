""" test module for the ae.files namespace portion. """
import glob
import os
from io import TextIOWrapper

import pytest
import shutil

from ae.files import RegisteredFile, CachedFile, FilesRegister, series_file_name


class TestHelpers:
    def test_series_file_name_basics(self):
        assert series_file_name("tests/series_tests.tst") == "tests/series_tests 01.tst"
        assert series_file_name("tests/series_tests.tst", marker='_copy_') == "tests/series_tests_copy_01.tst"
        assert series_file_name("tests/series_tests.tst", digits=1) == "tests/series_tests 1.tst"

    def test_series_file_name_create(self):
        file_mask = "tests/series_tests*.tst"
        try:
            assert series_file_name("tests/series_tests.tst", create=True) == "tests/series_tests 01.tst"
            assert series_file_name("tests/series_tests.tst", create=True) == "tests/series_tests 02.tst"
        finally:
            for file in glob.glob(file_mask):
                os.remove(file)

    def test_series_file_name_conflict(self):
        file_mask = "tests/series_tests*.tst"
        try:
            open(file_mask.replace('*', ' aaa'), 'w').close()
            open(file_mask.replace('*', ' 04'), 'w').close()
            assert series_file_name("tests/series_tests.tst", create=True) == "tests/series_tests 03.tst"
            assert series_file_name("tests/series_tests.tst") == "tests/series_tests 05.tst"
        finally:
            for file in glob.glob(file_mask):
                os.remove(file)


file_root = 'TstRootFolder'
file_name = 'tst_file'
file_ext = '.xy'
file_without_properties = os.path.join(file_root, file_name + file_ext)
file_properties = {'int': 72, 'float': 1.5, 'str': 'value'}
file_content = "test file content"


@pytest.fixture
def files_to_test():
    """ provide test file with properties. """
    fn = file_root
    os.mkdir(fn)
    with open(file_without_properties, 'w') as fp:
        fp.write(file_content)

    for name, value in file_properties.items():
        fn = os.path.join(fn, name + '_' + str(value))
        os.mkdir(fn)
    fn = os.path.join(fn, file_name + file_ext)
    with open(fn, 'w') as fp:
        fp.write(file_content)

    yield file_without_properties, fn

    shutil.rmtree(file_root)


class FileLoaderMockClass:
    """ cacheables file object loader mock class """
    @staticmethod
    def load(file):
        """ create and return file object """
        return file


def file_loader_mock_func(file):
    """ cacheables file object loader mock function """
    return file


def property_matcher_mock(file):
    """ file property matcher mock. """
    return file.properties == file_properties


def file_sorter_mock(file):
    """ file sorter mock. """
    return file.properties.get('int', 0)


class TestRegisteredFile:
    """ test RegisteredFile class. """
    def test_init_without_properties(self, files_to_test):
        wop, _ = files_to_test

        rf = RegisteredFile(wop)
        assert rf.path == file_without_properties
        assert rf.stem == file_name
        assert rf.ext == file_ext
        assert rf.properties == dict()

    def test_init_with_properties(self, files_to_test):
        _, wip = files_to_test
        sep = os.path.sep

        rf = RegisteredFile(wip)
        assert rf.path.startswith(file_root)
        assert rf.path.endswith(file_name + file_ext)
        assert all(sep + _ + '_' in rf.path for _ in file_properties.keys())
        assert all('_' + str(_) + sep in rf.path for _ in file_properties.values())
        assert rf.stem == file_name
        assert rf.ext == file_ext
        assert rf.properties == file_properties

    def test_repr(self, files_to_test):
        _, wip = files_to_test
        rf = RegisteredFile(wip)
        assert eval(repr(rf))
        assert isinstance(eval(repr(rf)), RegisteredFile)
        assert eval(repr(rf)) == rf

    def test_empty_kwargs(self):
        with pytest.raises(AssertionError):
            RegisteredFile('tests/test_files.py', any_kw_arg='tst')


class TestCachedFile:
    """ test CachedFile class. """
    def test_init_without_properties(self, files_to_test):
        wop, _ = files_to_test

        cf = CachedFile(wop, FileLoaderMockClass.load)
        assert cf.path == file_without_properties
        assert cf.stem == file_name
        assert cf.ext == file_ext
        assert cf.properties == dict()
        assert cf.late_loading
        assert cf.loaded_object is cf   # mock is returning passed cf instance

        cf = CachedFile(wop)
        assert isinstance(cf.loaded_object, TextIOWrapper)
        cf.loaded_object.close()

    def test_init_with_properties(self, files_to_test):
        _, wip = files_to_test
        sep = os.path.sep

        cf = CachedFile(wip, file_loader_mock_func)
        assert cf.path.startswith(file_root)
        assert cf.path.endswith(file_name + file_ext)
        assert all(sep + _ + '_' in cf.path for _ in file_properties.keys())
        assert all('_' + str(_) + sep in cf.path for _ in file_properties.values())
        assert cf.stem == file_name
        assert cf.ext == file_ext
        assert cf.properties == file_properties
        assert cf.loaded_object is cf   # mock is returning passed cf instance

    def test_init_early_loading(self, files_to_test):
        wop, wip = files_to_test

        cf = CachedFile(wip, file_loader_mock_func)
        assert cf._loaded_object is None

        cf = CachedFile(wop, FileLoaderMockClass.load, late_loading=False)
        assert cf._loaded_object is cf

    def test_file_io_open(self):
        cf = CachedFile('tests/conftest.py', object_loader=lambda f: open(f.path))
        assert isinstance(cf.loaded_object, TextIOWrapper)
        assert cf.loaded_object.read()
        cf.loaded_object.close()

    def test_file_io_open_read(self):
        def load_file_content(lcf):
            """ read file content """
            with open(lcf.path) as fp:
                content = fp.read()
            return content

        cf = CachedFile('tests/conftest.py', object_loader=load_file_content)
        assert isinstance(cf.loaded_object, str)
        assert cf.loaded_object == load_file_content(cf)

    def test_file_io_open_read_lines(self):
        def load_file_content(lcf):
            """ read file content """
            with open(lcf.path) as fp:
                content = fp.readlines()
            return content

        cf = CachedFile('tests/conftest.py', object_loader=load_file_content)
        assert isinstance(cf.loaded_object, list)
        assert cf.loaded_object == load_file_content(cf)


class TestFilesRegister:
    """ test FilesRegister class. """
    def test_init_min(self):
        fr = FilesRegister()
        assert not fr.property_watcher
        assert not fr.file_sorter
        assert not fr.keys()
        assert not fr.values()

    def test_init_property_matcher(self):
        fr = FilesRegister(property_matcher=property_matcher_mock)
        assert fr.property_watcher is property_matcher_mock

    def test_init_file_sorter(self):
        fr = FilesRegister(file_sorter=file_sorter_mock)
        assert fr.file_sorter is file_sorter_mock

    def test_init_add_path(self, files_to_test):
        wop, wip = files_to_test
        fr = FilesRegister(os.path.join(file_root, '**'))
        assert len(fr) == 1
        assert file_name in fr
        files = fr[file_name]
        assert len(files) == 2
        assert all(_.path in (wop, wip) for _ in files)
        assert all(_.stem == file_name for _ in files)
        assert all(_.ext == file_ext for _ in files)
        assert all(_.properties in (dict(), file_properties) for _ in files)

    def test_init_add_path_redirect(self, files_to_test):
        wop, wip = files_to_test
        fri = FilesRegister(os.path.join(file_root, '**'))
        fr = FilesRegister().add_path(os.path.join(file_root, '**'))
        assert len(fri) == len(fr)
        assert file_name in fr
        files = fr[file_name]
        assert len(files) == 2
        assert all(_.path in (wop, wip) for _ in files)
        assert all(_.stem == file_name for _ in files)
        assert all(_.ext == file_ext for _ in files)
        assert all(_.properties in (dict(), file_properties) for _ in files)

        old_len = len(fr)
        assert 'test_files' not in fr
        fr.add_file('tests/test_files.py')
        assert old_len < len(fr)
        assert 'test_files' in fr

    def test_find_file_by_name(self, files_to_test):
        fr = FilesRegister(os.path.join(file_root, '**'))
        assert fr.find_file(file_name).stem == file_name

    def test_find_file_by_properties(self, files_to_test):
        fr = FilesRegister(os.path.join(file_root, '**'))
        ff = fr.find_file(file_name, properties=file_properties)
        assert ff
        assert ff.stem == file_name
        assert ff.properties == file_properties

    def test_find_file_by_property_matcher(self, files_to_test):
        fr = FilesRegister(os.path.join(file_root, '**'))
        ff = fr.find_file(file_name, property_matcher=property_matcher_mock)
        assert ff
        assert ff.stem == file_name
        assert ff.properties == file_properties

    def test_find_file_by_property_matcher_and_file_sorter(self, files_to_test):
        fr = FilesRegister(os.path.join(file_root, '**'))
        ff = fr.find_file(file_name, properties=file_properties, file_sorter=file_sorter_mock)
        assert ff
        assert ff.stem == file_name
        assert ff.properties == file_properties

    def test_find_file_by_file_sorter(self, files_to_test):
        fr = FilesRegister(os.path.join(file_root, '**'))
        ff = fr.find_file(file_name, file_sorter=file_sorter_mock)
        assert ff
        assert ff.stem == file_name
        assert ff.properties == dict()      # finds the one without properties because int-default==0

    def test_find_file_with_default_property_matcher(self):
        fr = FilesRegister(property_matcher=property_matcher_mock)
        assert fr.property_watcher is property_matcher_mock

    def test_find_file_with_default_file_sorter(self):
        fr = FilesRegister(file_sorter=file_sorter_mock)
        assert fr.file_sorter is file_sorter_mock

    def test_call_find_file_redirect(self, files_to_test):
        fr = FilesRegister(file_root)
        assert fr(file_name, properties=file_properties) == fr.find_file(file_name, properties=file_properties)

    def test_cache_file_class(self, files_to_test):
        wop, wip = files_to_test
        fr = FilesRegister(os.path.join(file_root, '**'), file_class=CachedFile, object_loader=file_loader_mock_func)
        assert len(fr) == 1
        assert file_name in fr
        files = fr[file_name]
        assert len(files) == 2
        assert all(_.path in (wop, wip) for _ in files)
        assert all(_.stem == file_name for _ in files)
        assert all(_.ext == file_ext for _ in files)
        assert all(_.properties in (dict(), file_properties) for _ in files)

        assert all(isinstance(_, CachedFile) for _ in files)

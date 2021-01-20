""" test module for the ae.files namespace portion. """
import glob
import os
import pathlib
import pytest
import shutil
from io import TextIOWrapper

from ae.files import file_transfer_progress, series_file_name, RegisteredFile, CachedFile, FilesRegister


class TestHelpers:
    def test_file_transfer_progress_transferred(self):
        assert file_transfer_progress(0) == "0 Bytes"
        assert file_transfer_progress(1023) == "1023 Bytes"

        assert file_transfer_progress(1024) == "1 KBytes"
        assert file_transfer_progress(1025) == "1.001 KBytes"
        assert file_transfer_progress(1026) == "1.002 KBytes"
        assert file_transfer_progress(1027) == "1.003 KBytes"
        assert file_transfer_progress(1028) == "1.004 KBytes"
        assert file_transfer_progress(1029) == "1.005 KBytes"
        assert file_transfer_progress(1030) == "1.006 KBytes"

        assert file_transfer_progress(1023 * 1024) == "1023 KBytes"
        assert file_transfer_progress(1024 * 1024 - 1) == "1023.999 KBytes"
        assert file_transfer_progress(1024 * 1024) == "1 MBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 - 1) == "1024.000 MBytes"
        assert file_transfer_progress(1024 * 1024 * 1024) == "1 GBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 - 1) == "1024.000 GBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024) == "1 TBytes"

        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 + 1) == "1.000 TBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 + 1025 * 1024) == "1.000 TBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 + 1024 * 1024 * 1024) == "1.001 TBytes"

    def test_file_transfer_progress_with_total(self):
        assert file_transfer_progress(0, 1) == "0 / 1 Bytes"
        assert file_transfer_progress(0, 1023) == "0 / 1023 Bytes"
        assert file_transfer_progress(0, 1024) == "0 Bytes / 1 KBytes"

    def test_file_transfer_progress_done(self):
        assert file_transfer_progress(1, 1) == "1 Bytes"
        assert file_transfer_progress(1024, 1024) == "1 KBytes"
        assert file_transfer_progress(1024 * 1024, 1024 * 1024) == "1 MBytes"
        assert file_transfer_progress(1024 * 1024 * 1024, 1024 * 1024 * 1024) == "1 GBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024, 1024 * 1024 * 1024 * 1024) == "1 TBytes"

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
    def test_add_file(self):
        fr = FilesRegister()
        fr.add_file("test.xx")
        fr.add_file("test.yy")
        fr.add_file("test.yy")

        fr.add_file("test3")
        fr.add_file("test3.a")
        fr.add_file("test3.b")

        assert len(fr) == 2
        assert 'test' in fr
        assert 'test3' in fr
        assert fr.find_file('test')
        assert fr.find_file('test3')

        assert len(fr['test']) == 3
        assert fr['test'] == ['test.xx', 'test.yy', 'test.yy']

        assert len(fr['test3']) == 3
        assert fr['test3'] == ['test3', 'test3.a', 'test3.b']

        assert fr.find_file('test6') is None

    def test_add_file_reversed(self):
        fr = FilesRegister()
        fr.add_file("test.xx", first_index=-1)
        fr.add_file("test.yy", first_index=-2)
        fr.add_file("test.zz", first_index=-3)
        assert fr['test'] == ['test.zz', 'test.yy', 'test.xx']

    def test_add_files(self):
        fr = FilesRegister()
        files1 = ['tst.a', 'tst.b', 'tst.c']
        fr.add_files(files1)
        assert fr['tst'] == files1

        files2 = ['tst.1', 'tst.z', 'tst']
        fr.add_files(tuple(files2), first_index=0)
        assert fr['tst'] == files2 + files1

    def test_add_files_reversed(self):
        fr = FilesRegister()
        files1 = ['tst.a', 'tst.b', 'tst.c']
        fr.add_files(files1, first_index=-1)
        assert fr['tst'] == list(reversed(files1))

        files2 = ['tst.1', 'tst.z', 'tst']
        fr.add_files(tuple(files2), first_index=-4)
        assert fr['tst'] == list(reversed(files1 + files2))

    def test_add_register(self):
        fr = FilesRegister()
        fr.add_file("test.xx")
        fr.add_file("test.yy")
        fr.add_file("test3")

        fr2 = FilesRegister()
        fr2.add_file("dir/test.zz")
        fr2.add_file("dir3/test6")

        fr.add_register(fr2)
        assert len(fr) == 3
        assert len(fr['test']) == 3
        assert fr.find_file('test')
        assert fr.find_file('test3')
        assert fr.find_file('test6')

    def test_add_path_init(self, files_to_test):
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

    def test_add_path_redirect(self, files_to_test):
        wop, wip = files_to_test
        fri = FilesRegister(os.path.join(file_root, '**'))
        fr = FilesRegister()
        assert len(fr.add_paths(os.path.join(file_root, '**'))) == len(files_to_test)
        assert len(fri) == len(fr)
        assert file_name in fr
        files = fr[file_name]
        assert len(files) == len(files_to_test)
        assert all(_.path in (wop, wip) for _ in files)
        assert all(_.stem == file_name for _ in files)
        assert all(_.ext == file_ext for _ in files)
        assert all(_.properties in (dict(), file_properties) for _ in files)

        old_len = len(fr)
        assert 'test_files' not in fr
        fr.add_file('tests/test_files.py')
        assert old_len < len(fr)
        assert 'test_files' in fr

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

    def test_call_find_file_redirect(self, files_to_test):
        fr = FilesRegister(file_root)
        assert fr(file_name, properties=file_properties) == fr.find_file(file_name, properties=file_properties)

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

    def test_reclassify(self):
        fr = FilesRegister()
        fr.add_file('ttt')
        fr.add_file('dir/ttt')
        assert len(fr['ttt']) == 2

        assert all(isinstance(file, str) for file in fr['ttt'])
        fr.reclassify()
        assert all(isinstance(file, CachedFile) for file in fr['ttt'])
        fr.reclassify(file_class=RegisteredFile)
        assert all(isinstance(file, RegisteredFile) for file in fr['ttt'])
        fr.reclassify(file_class=pathlib.Path)
        assert all(isinstance(file, pathlib.Path) for file in fr['ttt'])
        fr.reclassify(file_class=pathlib.PurePath)
        assert all(isinstance(file, pathlib.PurePath) for file in fr['ttt'])

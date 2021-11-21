""" test module for the ae.files namespace portion. """
import os
import pytest
import shutil

from io import TextIOWrapper

from ae.base import norm_line_sep, read_file, write_file
from ae.files import (
    copy_bytes, file_lines, file_transfer_progress, read_file_text, write_file_text, RegisteredFile, CachedFile)


class TestHelpers:
    def test_file_lines(self):
        text = "line1\nline2\rline3\r\n"
        fnm = "tests/tst_lines.txt"
        try:
            write_file_text(text, fnm)
            assert file_lines(fnm) == tuple(norm_line_sep(text).split("\n"))
        finally:
            if os.path.exists(fnm):
                os.remove(fnm)

    def test_file_transfer_progress_transferred(self):
        assert file_transfer_progress(0) == "0 Bytes"
        assert file_transfer_progress(1023) == "1023 Bytes"
        assert file_transfer_progress(1023, decimal_places=1) == "1023 Bytes"

        assert file_transfer_progress(1024) == "1 KBytes"
        assert file_transfer_progress(1025) == "1.001 KBytes"
        assert file_transfer_progress(1026) == "1.002 KBytes"
        assert file_transfer_progress(1027) == "1.003 KBytes"
        assert file_transfer_progress(1028) == "1.004 KBytes"
        assert file_transfer_progress(1029) == "1.005 KBytes"
        assert file_transfer_progress(1030) == "1.006 KBytes"
        assert file_transfer_progress(1030, decimal_places=0) == "1 KBytes"
        assert file_transfer_progress(1030, decimal_places=1) == "1.0 KBytes"

        assert file_transfer_progress(1023 * 1024) == "1023 KBytes"
        assert file_transfer_progress(1024 * 1024 - 1) == "1023.999 KBytes"
        assert file_transfer_progress(1024 * 1024) == "1 MBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 - 1) == "1024.000 MBytes"
        assert file_transfer_progress(1024 * 1024 * 1024) == "1 GBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 - 1) == "1024.000 GBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 - 1, decimal_places=1) == "1024.0 GBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024) == "1 TBytes"

        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 + 1) == "1.000 TBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 + 1025 * 1024) == "1.000 TBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 + 1024 * 1024 * 1024) == "1.001 TBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 + 1024 * 1024 * 1024, decimal_places=0) == "1 TBytes"
        assert file_transfer_progress(1024 * 1024 * 1024 * 1024 + 1024 * 1024 * 1024, decimal_places=1) == "1.0 TBytes"

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

    def test_read_file_text(self):
        text = "line1\nline2\rline3\r\n"
        fnm = "tests/tst_content.txt"
        try:
            write_file_text(text, fnm)
            assert read_file_text(fnm) == norm_line_sep(text)

            write_file_text(norm_line_sep(text), fnm)
            assert read_file_text(fnm) == norm_line_sep(text)
        finally:
            if os.path.exists(fnm):
                os.remove(fnm)

    def test_read_file_text_error(self):
        assert read_file_text("tests/not_existing file.xxx") == ""
        assert read_file_text(":invalid \\=// file name....") == ""

    def test_write_file_text(self):
        text = "line1\nline2\rline3\r\n"
        fnm = "tests/tst_write.txt"
        try:
            assert write_file_text(text, fnm)
            assert read_file_text(fnm) == norm_line_sep(text)
        finally:
            if os.path.exists(fnm):
                os.remove(fnm)

    def test_write_file_text_error(self):
        assert not write_file_text("what ever", "folder_not_existing/writefile.xxx")
        assert not write_file_text("what else", ":invalid \\=// file name....")


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
    write_file(file_without_properties, file_content)

    for name, value in file_properties.items():
        fn = os.path.join(fn, name + '_' + str(value))
        os.mkdir(fn)
    fn = os.path.join(fn, file_name + file_ext)
    write_file(fn, file_content)

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


class TestCopyBytes:
    """ ae.files.copy_bytes unit tests. """
    def test_arg_errors(self, files_to_test):
        f1, f2 = files_to_test
        file_obj1 = open(f1, "rb")

        errors = []
        assert not copy_bytes("x", "y", errors=errors, progress_kwarg1="z")
        assert errors

        errors = []
        assert not copy_bytes(file_obj1, "y", errors=errors)
        assert errors

        errors = []
        assert not copy_bytes(file_obj1, "y", move_file=True, errors=errors)
        assert errors

        errors = []
        assert not copy_bytes("x", file_obj1, overwrite=True, errors=errors)
        assert errors

        errors = []
        assert not copy_bytes("x", file_obj1, recoverable=True, errors=errors)
        assert errors

        errors = []
        assert not copy_bytes(f1, "in/:/valid", errors=errors)  # dst file creation error
        assert errors

        errors = []
        assert not copy_bytes(f1, file_obj1, errors=errors)     # exception because file_obj1 is opened for read-only
        assert errors

        file_obj1.seek(0, 2)    # put src_file (file_obj1) to EOF to simulate empty chunk error
        errors = []
        assert not copy_bytes(file_obj1, f2, total_bytes=999, overwrite=True, errors=errors)
        assert errors

        file_obj1.close()

    def test_basics(self, files_to_test):
        f1, f2 = files_to_test

        errors = []
        assert not copy_bytes(f1, f2, errors=errors)
        assert errors

        errors = []
        assert copy_bytes(f1, f2, overwrite=True, errors=errors) == f2
        assert not errors

        assert copy_bytes(f2, f1, overwrite=True) == f1

    def test_move_file(self, files_to_test):
        f1, f2 = files_to_test
        os.remove(f2)

        assert not os.path.exists(f2)
        assert copy_bytes(f1, f2, move_file=True)
        assert not os.path.exists(f1)
        assert os.path.exists(f2)

    def test_progress_func(self, files_to_test):
        f1, f2 = files_to_test
        progress_called = False
        progress_kwargs = {}
        progress_return = False
        
        def pro_fnc(**kwargs):
            """ progress callback function """
            nonlocal progress_kwargs, progress_called, progress_return
            progress_kwargs = kwargs
            progress_called = True
            return progress_return
            
        pro_kwarg1 = 'tst_arg'
        
        errors = []
        assert copy_bytes(f1, f2, overwrite=True, errors=errors, progress_func=pro_fnc, pro_kwarg1=pro_kwarg1)
        assert not errors
        assert progress_called
        assert 'pro_kwarg1' in progress_kwargs
        assert progress_kwargs['pro_kwarg1'] == pro_kwarg1
        
        progress_called = False
        progress_return = True
        assert not copy_bytes(f1, f2, overwrite=True, errors=errors, progress_func=pro_fnc, pro_kwarg1=pro_kwarg1)
        assert errors
        assert progress_called
        assert 'pro_kwarg1' in progress_kwargs
        assert progress_kwargs['pro_kwarg1'] == pro_kwarg1

    def test_recoverable(self, files_to_test):
        f1, f2 = files_to_test

        assert copy_bytes(f1, f2, overwrite=True, recoverable=True)
        assert read_file_text(f2) == read_file_text(f1)

        half_len = int(len(file_content) / 2)
        write_file(f2, bytes(file_content[:half_len], 'utf8'), extra_mode="b")

        assert copy_bytes(f1, f2, overwrite=True, recoverable=True)
        assert read_file_text(f2) == read_file_text(f1)


class TestRegisteredFile:
    """ test RegisteredFile class. """
    def test_init_without_properties(self, files_to_test):
        wop, _ = files_to_test

        rf = RegisteredFile(wop)
        assert rf.path == file_without_properties
        assert rf.stem == file_name
        assert rf.ext == file_ext
        assert rf.properties == {}

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
        assert cf.properties == {}
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
            return read_file(lcf.path)

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

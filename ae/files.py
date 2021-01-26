"""
generic file object helpers
===========================

This namespace portion is pure Python providing helpers for file object and content managing. It only depends on the
:mod:`ae.base` namespace portion. Helper functions for to manage directory/folder structures are provided by the
:mod:`ae.paths` portion.

The helper function :func:`copy_bytes` provides recoverable copies of binary files and file streams, with progress
callbacks for each copied bytes chunk/buffer.

:func:`file_lines` and :func:`read_file_text` are helpers for to read/load text file contents. The function
:func:`write_file_text` stores a string to a text file.

An instance of the classes :class:`RegisteredFile` and :class:`CachedFile`, encapsulate and optionally cache
the contents of a files within a file object. These instances are compatible with the file objects provided by Python's
:mod:`pathlib` module. But also pure path strings can be used as file objects (see also the :data:`FileObject` type).

All these types of file objects are supported by the files register class :class:`~ae.paths.FilesRegister` from the
:mod:`ae.paths` portion.


registered file
---------------

A registered file object represents a single file on your file system and can be instantiated from one of the classes
:class:`RegisteredFile` or :class:`CachedFile` provided by this module/portion::

    from ae.files import RegisteredFile

    rf = RegisteredFile('path/to/the/file_name.extension')

    assert str(rf) == 'path/to/the/file_name.extension'
    assert rf.path == 'path/to/the/file_name.extension'
    assert rf.stem == 'file_name'
    assert rf.ext == '.extension'
    assert rf.properties == dict()

File properties will be automatically attached to each file object instance with the instance attribute
:attr:`~RegisteredFile.properties`. In the last example it results in an empty dictionary because the
:attr:`~RegisteredFile.path` of this file object does not contain folder names with an underscore character.


file properties
^^^^^^^^^^^^^^^

File property names and values are automatically determined from the names of their sub-folders, specified in the
:attr:`~RegisteredFile.path` attribute. Every sub-folder name containing an underscore character in the format
<property-name>_<value> will be interpreted as a file property::

    rf = RegisteredFile('property1_69/property2_3.69/property3_whatever/file_name.ext')
    assert rf.properties['property1'] == 69
    assert rf.properties['property2'] == 3.69
    assert rf.properties['property3'] == 'whatever'

The property types `int`, `float` and `string` are recognized and converted into a property value. Boolean values
can be coded as 1 and 0 integers.


cached file
-----------

A cached file created from the :class:`CachedFile` behaves like a :ref:`registered file` and additionally provides the
possibility to cache parts or the whole file content as well as the file pointer of the opened file::

    cf = CachedFile('integer_69/float_3.69/string_whatever/file_name.ext')

    assert str(cf) == 'integer_69/float_3.69/string_whatever/file_name.ext'
    assert cf.path == 'integer_69/float_3.69/string_whatever/file_name.ext'
    assert cf.stem == 'file_name'
    assert cf.ext == '.ext'
    assert cf.properties['integer'] == 69
    assert cf.properties['float'] == 3.69
    assert cf.properties['string'] == 'whatever'

On instantiation of the :class:`CachedFile` file object the default file object loader function
:func:`_default_object_loader` will be used, which opens a file stream via Python's `open` built-in. Alternatively
you can specify a specific file object loader with the :paramref:`~CachedFile.object_loader` parameter or by assigning
a callable directly to the :attr:`~CachedFile.object_loader` attribute::

    cf = CachedFile('integer_69/float_3.69/string_whatever/file_name.ext',
                    object_loader=lambda cached_file_obj: my_open_method(cached_file_obj.path))

The cached file object is accessible via the :attr:`~CachedFile.loaded_object` attribute of the cached file object
instance::

    assert isinstance(cf.loaded_object, TextIOWrapper)
    cf.loaded_object.seek(...)
    cf.loaded_object.read(...)

    cf.loaded_object.close()

"""
import os
import pathlib
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Tuple, Union, cast

from ae.base import norm_line_sep                                                   # type: ignore


__version__ = '0.1.14'


COPY_BUF_LEN = 16 * 1024


FileObject = Union[str, 'RegisteredFile', 'CachedFile', pathlib.Path, pathlib.PurePath, Any]
""" file object type, e.g. a file path str or any class or callable where the returned instance/value is either a string
    or an object with a `stem` attribute (holding the file name w/o extension), like e.g. :class:`CachedFile`,
    :class:`RegisteredFile`, :class:`pathlib.Path` or :class:`pathlib.PurePath`.
"""
PropertyType = Union[int, float, str]                                           #: types of file property values
PropertiesType = Dict[str, PropertyType]                                        #: dict of file properties
FilenameOrStream = Union[str, BinaryIO]                                         #: file name or file stream pointer


_default_progress_callback = lambda **_: None       # noqa: E731


def copy_bytes(src_file: FilenameOrStream, dst_file: FilenameOrStream, *,
               transferred_bytes: int = 0, total_bytes: int = 0, buf_size: int = COPY_BUF_LEN, overwrite: bool = False,
               move_file: bool = False, recoverable: bool = False, errors: Optional[List[str]] = None,
               progress_func: Callable = _default_progress_callback, **progress_kwargs) -> str:
    """ recoverable copy of a file or stream (file-like object), optionally with progress callbacks.

    :param src_file:            source file name or opened stream (file-like) object. If passing a non-seekable stream
                                together with a non-zero value in :paramref:`~copy_bytes.transferred_bytes` then the
                                source stream has to be set to the correct position before you call this function.
                                If passing any source stream then also the total file/stream size has to be passed
                                into the :paramref:`~copy_bytes.total_bytes` parameter. Source file streams do also
                                not support a True value in the :paramref:`move_file` argument.
    :param dst_file:            destination file name or opened stream (file-like) object. Recoverable copies and copies
                                with a True value in the :paramref:`~copy_bytes.overwrite` argument are not supported
                                (always use a destination file name if you need a recoverable/overwriting copy).
    :param transferred_bytes:   file offset at which the copy process starts. If not passed for recoverable copies, then
                                `copy_bytes` will determine this value from the file length of the destination file.
    :param total_bytes:         source file size in bytes (needed only if :paramref:`~copy_bytes.src_file' is a stream).
    :param buf_size:            size of copy buffer/chunk in bytes (that get copied before each progress callback).
    :param overwrite:           pass True to allow overwrite of destination file. If the destination file exists already
                                then this function will return an error (when this argument get not passed or is False).
    :param move_file:           pass True to delete source file on complete copying (only works if source is a stream).
    :param recoverable:         pass True to allow recoverable file copy (only working if source is a stream).
    :param errors:              pass empty list for to get a list of detailed error messages.
    :param progress_func:       optional callback for to dispatch or break/cancel the copy progress for large files.
                                If the callback returns a non-empty value it will be interpreted as cancel reason,
                                the copy process will be stopped and a error will be returned.
    :param progress_kwargs:     optional additional kwargs passed to the progress function. The kwargs `total_bytes`
                                and `transferred_bytes` will be updated before the callback.
    :return:                    destination file name/stream as string or empty string on error.

    .. hint::
        This function is extending the compatible Python functions :func:`shutil.copyfileobj`, :func:`shutil.copyfile`,
        :func:`shutil.copy`, :func:`shutil.copy2` or :meth:`http.server.SimpleHTTPRequestHandler.copyfile`
        with recoverability and a progress callback. It can also be used as :paramref:`~shutil.copytree.copy_function`
        by :func:`shutil.copytree` and :func:`move`.
    """
    src_named = isinstance(src_file, str)
    dst_named = isinstance(dst_file, str)
    if not isinstance(errors, list):
        errors = list()

    if progress_func == _default_progress_callback and progress_kwargs:
        errors.append(f"no progress callback function passed but kwargs={progress_kwargs}")
    if not src_named:
        if not total_bytes:
            errors.append("total_bytes has to be specified for source file-stream")
        if move_file:
            errors.append("source file-stream cannot be moved")
    if not dst_named and (overwrite or recoverable):
        errors.append("destination file-stream cannot be overwritten or recovered (pass file name instead)")
    if dst_named and not overwrite and os.path.exists(dst_file):    # type: ignore # mypy does not recognize src_named
        errors.append("destination file exists already (pass True to the overwrite parameter for to overwrite)")
    if errors:
        return ""

    src_fp: BinaryIO = cast(BinaryIO, None)
    try:
        src_fp = open(cast(str, src_file), "rb") if src_named else cast(BinaryIO, src_file)
        dst_fp = open(cast(str, dst_file), "ab+") if dst_named else cast(BinaryIO, dst_file)
    except (OSError, Exception) as ex:
        errors.append(str(ex))
        if src_named and src_fp:
            src_fp.close()
        return ""

    try:
        if not total_bytes:
            total_bytes = os.fstat(src_fp.fileno()).st_size        # ALT: src_fp.seek(0, 2) and src_fp.tell()
        if recoverable:
            if not transferred_bytes:
                transferred_bytes = os.fstat(dst_fp.fileno()).st_size
            if transferred_bytes and src_fp.seekable():
                src_fp.seek(transferred_bytes)
            dst_fp.close()
        while transferred_bytes < total_bytes:
            chunk = src_fp.read(buf_size)
            if not chunk:
                errors.append("source chunk is empty before reaching the end of the file")
                break

            if recoverable:
                with open(dst_file, "ab+") as dst_fp:   # type: ignore # mypy does not recognize src_named ensuring str
                    dst_fp.write(chunk)
            else:
                dst_fp.write(chunk)
            transferred_bytes += len(chunk)

            progress_kwargs.update(transferred_bytes=transferred_bytes, total_bytes=total_bytes)
            cancel_reason = progress_func(**progress_kwargs)
            if cancel_reason:
                errors.append(f"progress function request cancellation; reason={cancel_reason}")
                break

    except (OSError, Exception) as ex:
        errors.append(str(ex))

    finally:
        if dst_named and not dst_fp.closed:
            dst_fp.close()
        if src_named:
            src_fp.close()
            if move_file and not errors:
                os.remove(src_file)         # type: ignore # silly mypy does not recognize src_named ensuring str

    return "" if errors else str(dst_file)


def file_lines(file_path: str, encoding: Optional[str] = None) -> Tuple[str, ...]:
    """ returning lines of the text file specified by file_path argument as tuple.

    :param file_path:           file path/name to parse/load.
    :param encoding:            encoding used to load and convert/interpret the file content.
    :return:                    tuple of the lines found in the specified file
                                or empty tuple if the file could not be found or opened.
    """
    return tuple(norm_line_sep(read_file_text(file_path, encoding=encoding) or "").split("\n"))


def file_transfer_progress(transferred_bytes: int, total_bytes: int = 0, decimal_places: int = 3) -> str:
    """ return string to display the transfer progress of transferred bytes in short and user readable format.

    :param transferred_bytes:   number of transferred bytes.
    :param total_bytes:         number of total bytes.
    :param decimal_places:      number of decimal places (should be between 0 and 3).
    :return:                    formatted string to display progress of currently running transfer.
    """
    def _unit_size(size: float) -> Tuple[float, str]:
        for unit in ("", "K", "M", "G", "T"):
            if size < 1024.0:
                break
            size /= 1024.0
        return size, unit + "Bytes"

    trs, tru = _unit_size(transferred_bytes)
    if total_bytes and transferred_bytes != total_bytes:
        tos, tou = _unit_size(total_bytes)
        tru = ("" if tru == tou else tru + " ") + "/ {tos:.{de}f} {tou}".format(
            tos=tos, de=decimal_places if tos % 1 > 0 else 0, tou=tou)

    return "{trs:.{de}f} {tru}".format(trs=trs, de=decimal_places if trs % 1 > 0 else 0, tru=tru)


def read_file_text(file_path: str, encoding: Optional[str] = None, error_handling: str = 'ignore') -> Optional[str]:
    """ returning content of the text file specified by file_path argument as string.

    :param file_path:           file path/name to load into a string.
    :param encoding:            encoding used to load and convert/interpret the file content.
    :param error_handling:      pass `'strict'` or `None` to get `None` instead of empty string return value on
                                either decoding ValueError exception or
                                any `OSError`, `FileNotFoundError` or `PermissionError` exception.
                                The default value `'ignore'` will ignore any decoding errors (missing some characters)
                                and will return an empty string on any file/os exception.
    :return:                    file content string. If the file could not be decoded, found or opened,
                                then return empty string or None (None only if `'strict'` got passed to the
                                :paramref:'~file_content.error_handling` parameter).
    """
    try:
        with open(file_path, encoding=encoding, errors=error_handling) as file_handle:
            return file_handle.read()
    except (FileNotFoundError, OSError, PermissionError, ValueError):
        return "" if error_handling == 'ignore' else None


def write_file_text(text_or_lines: Union[str, List[str], Tuple[str]], file_path: str, encoding: Optional[str] = None
                    ) -> bool:
    """ write the passed text string or list of line strings into the text file specified by file_path argument.

    :param text_or_lines:       new file content either passed as string or list of line strings (will be
                                concatenated with the line separator of the current OS: os.linesep).
    :param file_path:           file path/name to write the passed content into (overwriting any previous content!).
    :param encoding:            encoding used to write/convert/interpret the file content to write.
    :return:                    True if the content got written to the file, False on any file/OS error.
    """
    content = text_or_lines if isinstance(text_or_lines, str) else os.linesep.join(text_or_lines)
    try:
        with open(file_path, 'w', encoding=encoding) as file_handle:
            file_handle.write(content)
    except (FileExistsError, FileNotFoundError, OSError, PermissionError, ValueError):
        return False
    return True


class RegisteredFile:
    """ represents a single file - see also :ref:`registered file` examples. """
    def __init__(self, file_path: str, **kwargs):
        """ initialize registered file_obj instance.

        :param file_path:       file path string.
        :param kwargs:          not supported, only there to have compatibility to :class:`CachedFile` for to detect
                                invalid kwargs.
        """
        assert not kwargs, "RegisteredFile does not have any kwargs - maybe want to use CachedFile as file_class."
        self.path: str = file_path                                      #: file path
        self.stem: str                                                  #: file basename without extension
        self.ext: str                                                   #: file name extension
        dir_name, base_name = os.path.split(file_path)
        self.stem, self.ext = os.path.splitext(base_name)

        self.properties: PropertiesType = dict()                        #: file properties
        for folder in dir_name.split(os.path.sep):
            parts = folder.split("_", maxsplit=1)
            if len(parts) == 2:
                self.add_property(*parts)

    def __eq__(self, other: FileObject) -> bool:
        """ allow equality checks.

        :param other:           other file object to compare this instance with.
        :return:                True if both objects are of this type and contain a file with the same path, else False.
        """
        return isinstance(other, self.__class__) and other.path == self.path

    def __repr__(self):
        """ for config var storage and eval recovery.

        :return:    evaluable/recoverable representation of this object.
        """
        return f"{self.__class__.__name__}({self.path!r})"

    def __str__(self):
        """ return file path.

        :return:    file path string of this file object.
        """
        return self.path

    def add_property(self, property_name: str, str_value: str):
        """ add a property to this file object instance.

        :param property_name:   stem of the property to add.
        :param str_value:       literal of the property value (int/float/str type will be detected).
        """
        try:
            property_value: PropertyType = int(str_value)
        except ValueError:
            try:
                property_value = float(str_value)
            except ValueError:
                property_value = str_value
        self.properties[property_name] = property_value


def _default_object_loader(file_obj: FileObject):
    """ file object loader that is opening the file and keeping the handle of the opened file.

    :param file_obj:            file object (path string or obj with `path` attribute holding the complete file path).
    :return:                    file handle to the opened file.
    """
    return open(str(file_obj))


class CachedFile(RegisteredFile):
    """ represents a cacheables registered file object - see also :ref:`cached file` examples. """
    def __init__(self, file_path: str,
                 object_loader: Callable[['CachedFile', ], Any] = _default_object_loader, late_loading: bool = True):
        """ create cached file object instance.

        :param file_path:       path string of the file.
        :param object_loader:   callable converting the file_obj into a cached object (available
                                via :attr:`~CachedFile.loaded_object`).
        :param late_loading:    pass False for to convert/load file_obj cache early, directly at instantiation.
        """
        super().__init__(file_path)
        self.object_loader = object_loader
        self.late_loading = late_loading
        self._loaded_object = None if late_loading else object_loader(self)

    @property
    def loaded_object(self) -> Any:
        """ loaded object class instance property.

        :return: loaded and cached file object.
        """
        if self.late_loading and not self._loaded_object:
            self._loaded_object = self.object_loader(self)
        return self._loaded_object

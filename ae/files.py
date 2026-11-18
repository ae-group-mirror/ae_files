"""
generic file object helpers
===========================

this namespace portion is pure Python code, providing helpers for file object and content managing. it only depends
on the :mod:`ae.base` namespace portion. more info and examples you find at :ref:`file content handling`.
"""
from __future__ import annotations  # allow type forward references (PEP 563), can be removed in Python 3.14+ (PEP 749)

import io
import os
import pathlib

from collections.abc import Callable
from typing import Any, IO, cast

from ae.base import (                                               # type: ignore
    dummy_function, norm_line_sep, os_path_isfile, os_path_split, os_path_splitext, read_file, write_file)


__version__ = '0.4.31'


type FileObject = str | RegisteredFile | CachedFile | pathlib.Path | pathlib.PurePath | Any
""" file object type, e.g. a file path str or any class or callable where the returned instance/value is either a
    string or an object with a `stem` attribute (holding the file name w/o extension), like e.g. :class:`CachedFile`,
    :class:`RegisteredFile`, :class:`pathlib.Path` or :class:`pathlib.PurePath`.
"""
type PropertyType = int | float | str                                           #: types of file property values
type PropertiesType = dict[str, PropertyType]                                   #: dict of file properties
type FilenameOrStream = str | IO[bytes] | io.BufferedIOBase | io.RawIOBase      #: file name or binary file/stream


# pylint: disable=too-many-arguments,too-many-locals,too-many-statements
def copy_bytes(src_file: FilenameOrStream, dst_file: FilenameOrStream, *,
               transferred_bytes: int = 0, total_bytes: int = 0, buf_size: int = 16 * 1024, overwrite: bool = False,
               move_file: bool = False, recoverable: bool = False, errors: list[str] | None = None,
               progress_func: Callable = dummy_function, **progress_kwargs) -> str:
    """ recoverable copy of a file or stream (file-like object), optionally with progress callbacks.

    :param src_file:            source file name or opened stream (file-like) object. if passing a non-seekable stream
                                together with a non-zero value in :paramref:`.transferred_bytes`, then the
                                source stream has to be set to the correct position before you call this function.
                                if passing any source stream, then also the total file/stream size has to be passed
                                into the :paramref:`.total_bytes` parameter. source file streams do also
                                not support a `True` value in the :paramref:`.move_file` argument.
    :param dst_file:            destination file name or opened stream (file-like) object. recoverable copies and copies
                                with a `True` value in the :paramref:`.overwrite` argument are not allowed;
                                always use a destination file name if you need a recoverable/overwriting copy.
    :param transferred_bytes:   file offset at which the copy process starts. if not passed for recoverable copies, then
                                this function will determine the offset from the file length of the destination file.
    :param total_bytes:         source file size in bytes (needed if :paramref:`.src_file` is a stream).
    :param buf_size:            size of copy buffer/chunk in bytes (that get copied before each progress callback).
    :param overwrite:           pass `True` to allow overwriting of the destination (the :paramref:`.dst_file` argument
                                has to be a path in this case). if this argument is `False` (this argument's default),
                                and the destination file exists already, then this function will return an error.
    :param move_file:           pass `True` to delete the source file on complete copying (the :paramref:`.src_file`
                                argument has to be a file path in this case).
    :param recoverable:         pass `True` to allow a recoverable file copy (:paramref:`.dst_file` has to be a path).
    :param errors:              pass a list to extend it with detailed error messages.
    :param progress_func:       optional callback to dispatch or break/cancel the copy progress for large files.
                                if the callback returns a non-empty value, it will be interpreted as cancel reason,
                                the copy process will be stopped, and an error will be returned.
    :param progress_kwargs:     optional additional kwargs passed to the progress function. the kwargs `total_bytes`
                                and `transferred_bytes` will be updated before the callback.
    :return:                    destination file name/stream as string or empty string on error.
    """
    src_named = isinstance(src_file, str)
    dst_named = isinstance(dst_file, str)
    src_path = cast(str, src_file)
    dst_path = cast(str, dst_file)
    src_fp: IO[bytes] = cast(IO[bytes], cast(object, None))
    dst_fp: IO[bytes] = cast(IO[bytes], cast(object, None))
    err: list[str] = errors if isinstance(errors, list) else []

    def _args_check() -> bool:
        if progress_func is dummy_function and progress_kwargs:
            err.append(f"no progress callback function passed but {progress_kwargs=}")
        if not src_named:
            if not total_bytes:
                err.append("total_bytes has to be specified for source file-stream")
            if move_file:
                err.append("source file-stream cannot be moved")
        if not dst_named and (overwrite or recoverable):
            err.append("destination file-stream cannot be overwritten or recovered (pass file name instead)")
        if dst_named and not overwrite and os_path_isfile(dst_path):
            err.append("destination file exists already (pass `True` to the overwrite parameter to overwrite)")
        return not err

    def _open_check() -> bool:
        nonlocal src_fp, dst_fp
        try:
            src_fp = (open(src_path, "rb") if src_named else        # pylint: disable=consider-using-with
                      cast(IO[bytes], src_file))
            dst_fp = (open(dst_path, "ab+") if dst_named else       # pylint: disable=consider-using-with
                      cast(IO[bytes], dst_file))
        except (OSError, Exception) as ex:                          # pylint: disable=broad-exception-caught
            err.append(str(ex))
            if src_named and src_fp:
                src_fp.close()
            return False
        return True

    def _copy():
        nonlocal dst_fp, total_bytes, transferred_bytes
        if not total_bytes:
            total_bytes = os.fstat(src_fp.fileno()).st_size         # ALT: src_fp.seek(0, 2) and src_fp.tell()

        if recoverable:
            if not transferred_bytes:
                transferred_bytes = os.fstat(dst_fp.fileno()).st_size
            if transferred_bytes and src_fp.seekable():
                src_fp.seek(transferred_bytes)
            dst_fp.close()

        while transferred_bytes < total_bytes:
            chunk = src_fp.read(buf_size)
            if not chunk:
                err.append("source chunk is empty before reaching the end of the file")
                break

            if recoverable:
                with open(dst_path, "ab+") as dst_fp:
                    dst_fp.write(chunk)
            else:
                dst_fp.write(chunk)
            transferred_bytes += len(chunk)

            progress_kwargs.update(transferred_bytes=transferred_bytes, total_bytes=total_bytes)
            cancel_reason = progress_func(**progress_kwargs)
            if cancel_reason:
                err.append(f"progress function request cancellation; {cancel_reason=}")
                break

    def _close():
        if dst_named and not dst_fp.closed:
            dst_fp.close()
        if src_named:
            src_fp.close()
            if move_file and not err:
                os.remove(src_path)

    if _args_check() and _open_check():
        try:
            _copy()
        except (OSError, Exception) as copy_exc:                    # pylint: disable=broad-exception-caught
            err.append(str(copy_exc))
        finally:
            _close()

    return "" if err else (dst_path if dst_named else cast(str, dst_file))


def file_lines(file_path: str, encoding: str | None = None) -> tuple[str, ...]:
    """ returning lines of the text file specified by file_path argument as tuple.

    :param file_path:           file path/name to parse/load.
    :param encoding:            encoding used to load and convert/interpret the file content.
    :return:                    tuple of the lines found in the specified file
                                or empty tuple if the file could not be found or opened.
    """
    return tuple(norm_line_sep(read_file_text(file_path, encoding=encoding) or "").splitlines())


def file_transfer_progress(transferred_bytes: int, total_bytes: int = 0, decimal_places: int = 3) -> str:
    """ return string to display the transfer progress of transferred bytes in short and user-readable format.

    :param transferred_bytes:   number of transferred bytes.
    :param total_bytes:         number of total bytes.
    :param decimal_places:      number of decimal places (should be between 0 and 3).
    :return:                    formatted string to display the progress of the currently running transfer.
    """
    def _unit_size(size: float) -> tuple[float, str]:
        for unit in ("", "K", "M", "G", "T"):
            if size < 1024.0:
                break
            size /= 1024.0
        return size, unit + "Bytes"

    tra_size, tra_unit = _unit_size(transferred_bytes)
    if total_bytes and transferred_bytes != total_bytes:
        tot_size, tot_unit = _unit_size(total_bytes)
        decimals = decimal_places if tot_size % 1 > 0 else 0
        tra_unit = ("" if tra_unit == tot_unit else tra_unit + " ") + f"/ {tot_size:.{decimals}f} {tot_unit}"

    decimals = decimal_places if tra_size % 1 > 0 else 0
    return f"{tra_size:.{decimals}f} {tra_unit}"


def read_file_text(file_path: str, encoding: str | None = None, error_handling: str = 'ignore') -> str | None:
    """ returning content of the text file specified by file_path argument as string, while suppressing exceptions.

    :param file_path:           file path/name to load into a string.
    :param encoding:            encoding used to load and convert/interpret the file content (see built-in `open`).
    :param error_handling:      passed onto the `errors` parameter of the built-in `open` function.
    :return:                    the file contents as a string. if the file could not be decoded, found or opened,
                                returns an empty string (if :paramref:`~read_file_text.error_handling` is unspecified
                                or set to `'ignore'`), otherwise `None`. this function suppresses and catches
                                exceptions such as `FileNotFoundError`, `OSError`, `PermissionError`, and `ValueError`.
    """
    try:
        return read_file(file_path, encoding=encoding, error_handling=error_handling)
    except (FileNotFoundError, OSError, PermissionError, ValueError):
        return "" if error_handling == 'ignore' else None


def write_file_text(text_or_lines: str | list[str] | tuple[str], file_path: str, encoding: str | None = None) -> bool:
    """ write the passed text string or list of line strings into the text file specified by file_path argument.

    :param text_or_lines:       new file content either passed as string or list of line strings (will be
                                concatenated with the line separator of the current OS: os.linesep).
    :param file_path:           file path/name to write the passed content into (overwriting any previous content!).
    :param encoding:            encoding used to write/convert/interpret the file content to write.
    :return:                    `True` if the content got written to the file, `False` on error/exception.
                                this function suppresses and catches exceptions such as `FileExistsError`,
                                `FileNotFoundError`, `OSError`, `PermissionError`, and `ValueError`.
    """
    content = text_or_lines if isinstance(text_or_lines, str) else os.linesep.join(text_or_lines)
    try:
        write_file(file_path, content, encoding=encoding)
    except (FileExistsError, FileNotFoundError, OSError, PermissionError, ValueError):
        return False
    return True


class RegisteredFile:
    """ represents a single file - see also :ref:`registered file` examples. """
    def __init__(self, file_path: str, **kwargs):
        """ initialize the registered file instance.

        :param file_path:       file path string.
        :param kwargs:          not supported, only there to have compatibility to the :class:`CachedFile` class,
                                to detect invalid kwargs.
        """
        assert not kwargs, "RegisteredFile does not have any kwargs - maybe want to use CachedFile as file_class."
        self.path: str = file_path                                  #: file path
        self.stem: str                                              #: file basename without extension
        self.ext: str                                               #: file name extension
        dir_path, base_name = os_path_split(file_path)
        self.stem, self.ext = os_path_splitext(base_name)

        self.properties: PropertiesType = {}                        #: file properties
        for folder in dir_path.replace("\\", "/").split("/"):
            parts = folder.split("_", maxsplit=1)
            if len(parts) == 2:
                self.add_property(*parts)

    def __eq__(self, other: FileObject) -> bool:
        """ allow equality checks.

        :param other:           another file object to compare this instance with.
        :return:                `True` if the other object is also of this type and has the same path, else `False`.
        """
        return isinstance(other, self.__class__) and other.path == self.path

    def __repr__(self) -> str:
        """ for config var storage and eval recovery.

        :return:    evaluable/recoverable representation of this object.
        """
        return f"{self.__class__.__name__}({self.path!r})"

    def __str__(self) -> str:
        """ return the file path of the registered file.

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


def _default_object_loader(file_obj: FileObject) -> io.TextIOWrapper:
    """ file object loader that is opening the file and keeping the handle of the opened file.

    :param file_obj:            file object (path string or obj with `path` attribute holding the complete file path).
    :return:                    file handle to the opened file.
    """
    return open(str(file_obj))                                      # pylint: disable=unspecified-encoding


class CachedFile(RegisteredFile):
    """ represents a cacheables registered file object - see also :ref:`cached file` examples. """
    def __init__(self, file_path: str,
                 object_loader: Callable[[CachedFile, ], Any] = _default_object_loader, late_loading: bool = True):
        """ create a cached file object instance.

        :param file_path:       path string of the file.
        :param object_loader:   callable converting the file_obj into a cached object (available
                                via :attr:`~CachedFile.loaded_object`).
        :param late_loading:    pass `False` to convert/load file_obj cache early, directly at instantiation.
        """
        super().__init__(file_path)
        self.object_loader = object_loader
        self.late_loading = late_loading
        self._loaded_object = None if late_loading else object_loader(self)

    @property
    def loaded_object(self) -> Any:
        """ loaded object class instance property.

        :return: the loaded and cached file object.
        """
        if self.late_loading and not self._loaded_object:
            self._loaded_object = self.object_loader(self)
        return self._loaded_object

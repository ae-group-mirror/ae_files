"""
file collection, grouping and caching
=====================================

This namespace portion is pure Python, only depending on the :mod:`ae.paths` namespace portion and is providing helpers
for file managing.

Useful for dynamic selection of image/font/audio/resource... files depending on the current user preferences, hardware
and/or software environment.

The class :class:`FilesRegister` collect and group available files for to later find the best fitting match for a
requested purpose.

The classes :class:`RegisteredFile` and :class:`CachedFile` encapsulate and optionally cache files into file objects.
The instances of these two classes are compatible to the file object classes provided by the :mod:`pathlib` module.
But also pure path strings can be used as file objects by the class :class:`FilesRegister` (see also the
:data:`FileObject` type).


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

The :attr:`~RegisteredFile.properties` attribute of the :class:`RegisteredFile` instance is empty in the above example
because the :attr:`~RegisteredFile.path` does not contain folder names with an underscore character.


file properties
^^^^^^^^^^^^^^^

File properties are provided in the :attr:`~RegisteredFile.properties` attribute which is a dict instance, where the key
is the name of the property. Each item of this attribute reflects a property of the registered file.

Property names and values are automatically determined via the names of their specified sub-folders. Every sub-folder
name containing an underscore character in the format <property-name>_<value> will be interpreted as a file property::

    rf = RegisteredFile('property1_69/property2_3.69/property3_whatever/file_name.ext')
    assert rf.properties['property1'] == 69
    assert rf.properties['property2'] == 3.69
    assert rf.properties['property3'] == 'whatever'

Currently the property types `int`, `float` and `string` are recognized and converted into a property value.


cached file
-----------

A cached file created from the :class:`CachedFile` behaves like a :ref:`registered file` and additionally provides the
possibility to cache parts or the whole file content as well as the file pointer of the opened file::

    cf = CachedFile('integer_69/float_3.69/string_whatever/file_name.ext',
                    object_loader=lambda cached_file: open(cached_file.path))

    assert str(cf) == 'integer_69/float_3.69/string_whatever/file_name.ext'
    assert cf.path == 'integer_69/float_3.69/string_whatever/file_name.ext'
    assert cf.stem == 'file_name'
    assert cf.ext == '.ext'
    assert cf.properties['integer'] == 69
    assert cf.properties['float'] == 3.69
    assert cf.properties['string'] == 'whatever'

    assert isinstance(cf.loaded_object, TextIOWrapper)
    cf.loaded_object.seek(...)
    cf.loaded_object.read(...)

    cf.loaded_object.close()


files register
--------------

A files register does the collection and selection of files for your application, for example for to find and select
resource files like icon/image or sound files.

Files can be collected from various places and then be provided by a single instance of the class
:class:`FilesRegister`::

    from ae.files import FilesRegister

    fr = FilesRegister('first/path/to/collect')
    fr.add_paths('second/path/to/collect/files/from')

    registered_file = fr.find_file('file_name')

If a file with the base name (stem) `file_name` exists in a sub-folder of the two provided paths then the
:meth:`~FilesRegister.find_file` method will return a file object of type :class:`RegisteredFile`.

Several files with the same base name can be collected and registered e.g. with different formats, for to be selected by
the app by their different properties. Assuming your application is providing an icon image in two sizes, provided
within the following directory structure::

    resources/
        size_72/
            app_icon.jpg
        size_150/
            app_icon.png

First create an instance of :class:`FilesRegister` for to collect both image files from the `resources` folder::

    fr = FilesRegister('resources')

The resulting object `fr` behaves like a dict object, where the item key is the file name without extension (app_icon)
and the item value is a list of instances of :class:`RegisteredFile`. Both files in the resources folder are provided as
one dict item::

    assert 'app_icon' in fr
    assert len(fr) == 1
    assert len(fr['app_icon']) == 2
    assert isinstance(fr['app_icon'][0], RegisteredFile)

For to select the appropriate image file you can use the :meth:`~FilesRegister.find_file` method::

    app_icon_image_path = fr.find_file('app_icon', dict(size=current_size))

As a shortcut you can alternatively call the object directly (leaving `.find_file` away)::

    app_icon_image_path = fr('app_icon', dict(size=current_size))

For more complex selections you can use callables passed into the :paramref:`~FilesRegister.find_file.property_matcher`
and :paramref:`~FilesRegister.find_file.file_sorter` arguments of :meth:`~FilesRegister.find_file`.

"""
import glob
import os
import pathlib
import sys
from typing import Any, Callable, Dict, Iterable, Optional, Type, Union

from ae.paths import path_files                                                 # type: ignore


__version__ = '0.1.9'


FileObject = Union[str, 'RegisteredFile', 'CachedFile', pathlib.Path, pathlib.PurePath, Any]
""" file object type, e.g. a file path str or any class or callable where the returned instance/value is either a string
    or an object with a `stem` attribute (holding the file name w/o extension), like e.g. :class:`CachedFile`,
    :class:`RegisteredFile`, :class:`pathlib.Path` or :class:`pathlib.PurePath`.
"""

PropertyType = Union[int, float, str]                                           #: types of property values
PropertiesType = Dict[str, PropertyType]                                        #: dict of file properties


APPEND_TO_END_OF_FILE_LIST = sys.maxsize
""" special flag default value for the `first_index` argument of the `add_*` methods of :class:`FilesRegister` for to
    append new file objects to the end of the name's register file object list.
"""
INSERT_AT_BEGIN_OF_FILE_LIST = -APPEND_TO_END_OF_FILE_LIST
""" special flag default value for the `first_index` argument of the `add_*` methods of :class:`FilesRegister` for to
    insert new file objects always at the begin of the name's register file object list.
"""


def series_file_name(file_path: str, digits: int = 2, marker: str = " ", create: bool = False) -> str:
    """ determine non-existent series file name with an unique series index.

    :param file_path:           file path and name (optional with extension).
    :param digits:              number of digits used for the series index.
    :param marker:              marker that will be put at the end of the file name and before the series index.
    :param create:              pass True to create the file (for to reserve the series index).
    :return:                    file path extended with unique/new series index.
    """
    path_stem, ext = os.path.splitext(file_path)
    path_stem += marker

    found_files = glob.glob(path_stem + "*" + ext)
    index = len(found_files) + 1
    while True:
        file_path = path_stem + format(index, "0" + str(digits)) + ext
        if not os.path.exists(file_path):
            break
        index += 1

    if create:
        open(file_path, 'w').close()

    return file_path


class RegisteredFile:
    """ represents a single file. """
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
    """ represents a cacheables registered file object. """
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


class FilesRegister(dict):
    """ file register catalog. """
    def __init__(self, *add_path_args,
                 property_matcher: Optional[Callable[[FileObject, ], bool]] = None,
                 file_sorter: Optional[Callable[[FileObject, ], Any]] = None,
                 **add_path_kwargs):
        """ create files register instance.

        This method gets redirected with :paramref:`~FilesRegister.add_path_args` and
        :paramref:`~FilesRegister.add_path_kwargs` arguments to :meth:`~FilesRegister.add_paths`.

        :param add_path_args:   if passed then :meth:`~FilesRegister.add_paths` will be called with
                                this args tuple.
        :param property_matcher: property matcher callable, used as default value by
                                :meth:`~FilesRegister.find_file` if not passed there.
        :param file_sorter:     file sorter callable, used as default value by
                                :meth:`~FilesRegister.find_file` if not passed there.
        :param add_path_kwargs: passed onto call of :meth:`~FilesRegister.add_paths` if the
                                :paramref:`FilesRegister.add_path_args` got provided by caller.
        """
        super().__init__()
        self.property_watcher = property_matcher
        self.file_sorter = file_sorter
        if add_path_args:
            self.add_paths(*add_path_args, **add_path_kwargs)

    def __call__(self, *find_args, **find_kwargs) -> Optional[FileObject]:
        """ add_path_args and kwargs will be completely redirected to :meth:`~FilesRegister.find_file`. """
        return self.find_file(*find_args, **find_kwargs)

    def add_file(self, file_obj: FileObject, first_index: int = APPEND_TO_END_OF_FILE_LIST):
        """ add a single file to the list of this dict mapped by the file-name/stem as dict key.

        :param file_obj:        either file path string or any object with a `stem` attribute.
        :param first_index:     pass list index -n-1..n-1 for to insert the :paramref:`.file_obj` in the name's list.
                                Values greater than n (==len(file_list)) will append the file_obj to the end of the file
                                object list and values less than n-1 will insert the file_obj to the begin.
        """
        name = os.path.splitext(os.path.basename(file_obj))[0] if isinstance(file_obj, str) else file_obj.stem
        if name in self:
            list_len = len(self[name])
            if first_index < 0:
                first_index = max(0, list_len + first_index + 1)
            else:
                first_index = min(first_index, list_len)
            self[name].insert(first_index, file_obj)
        else:
            self[name] = [file_obj]

    def add_files(self, files: Iterable[FileObject], first_index: int = APPEND_TO_END_OF_FILE_LIST):
        """ add files from another :class:`FilesRegister` instance.

        :param files:           Iterable with file objects to be added.
        :param first_index:     pass list index -n-1..n-1 for to insert the first file_obj in each name's register list.
                                Values greater than n (==len(file_list)) will append the file_obj to the end of the file
                                object list. The order of the added items will be unchanged if this value is greater
                                or equal to zero. Negative values will add the items from :paramref:`.files` in reversed
                                order and **after** the item specified by this index value (so passing -1 will append
                                the items to the end in reversed order, while passing -(n+1) will insert them at the
                                begin in reversed order).
        """
        increment = -1 if first_index < 0 else 1
        for file_obj in files:
            self.add_file(file_obj, first_index=first_index)
            first_index += increment

    def add_paths(self, *file_path_masks: str, recursive: bool = True, first_index: int = APPEND_TO_END_OF_FILE_LIST,
                  file_class: Type[FileObject] = RegisteredFile, **init_kwargs) -> 'FilesRegister':
        """ add files found in the folder(s) specified by the :paramref:`~add_paths.file_path_masks` args.

        :param file_path_masks: file path masks (with optional wildcards and :data:`~ae.paths.PATH_PLACEHOLDERS`)
                                specifying the files to collect (by default including the sub-folders).
        :param recursive:       pass False to only collect the given folder (ignoring sub-folders).
        :param first_index:     pass list index -n-1..n-1 for to insert the first file_obj in each name's register list.
                                Values greater than n (==len(file_list)) will append the file_obj to the end of the file
                                object list. The order of the added items will be unchanged if this value is greater
                                or equal to zero. Negative values will add the found items in reversed
                                order and **after** the item specified by this index value (so passing -1 will append
                                the items to the end in reversed order, while passing -(n+1) will insert them at the
                                begin in reversed order).
        :param file_class:      The used file object class (see :data:`FileObject`). Each found file object will passed
                                to the class constructor (callable) and added to the list which is a item of this dict.
        :param init_kwargs:     additional/optional kwargs passed onto the used :paramref:`.file_class`. Pass e.g.
                                the object_loader to use, if :paramref:`~add_paths.file_class` is
                                :class:`CachedFile` (instead of the default: :class:`RegisteredFile`).
        :return:                this instance.
        """
        for mask in file_path_masks:
            self.add_files(path_files(mask, recursive=recursive, file_class=file_class, **init_kwargs),
                           first_index=first_index)
        return self

    def add_register(self, files_register: 'FilesRegister', first_index: int = APPEND_TO_END_OF_FILE_LIST):
        """ add files from another :class:`FilesRegister` instance.

        :param files_register:  files register instance containing the file_obj to be added.
        :param first_index:     pass list index -n-1..n-1 for to insert the first file_obj in each name's register list.
                                Values greater than n (==len(file_list)) will append the file_obj to the end of the file
                                object list. The order of the added items will be unchanged if this value is greater
                                or equal to zero. Negative values will add the found items in reversed
                                order and **after** the item specified by this index value (so passing -1 will append
                                the items to the end in reversed order, while passing -(n+1) will insert them at the
                                begin in reversed order).
        """
        for files in files_register.values():
            self.add_files(files, first_index=first_index)

    def find_file(self, name: str, properties: Optional[PropertiesType] = None,
                  property_matcher: Optional[Callable[[FileObject, ], bool]] = None,
                  file_sorter: Optional[Callable[[FileObject, ], Any]] = None,
                  ) -> Optional[FileObject]:
        """ find file_obj in this register via properties, property matcher callables and/or file sorter.

        :param name:            file name (stem without extension) to find.
        :param properties:      properties for to select the correct file.
        :param property_matcher: callable for to match the correct file.
        :param file_sorter:     callable for to sort resulting match results.
        :return:                registered/cached file object of the first found/correct file.
        """
        assert not (properties and property_matcher), "pass either properties dict of matcher callable, not both"
        if not property_matcher:
            property_matcher = self.property_watcher
        if not file_sorter:
            file_sorter = self.file_sorter

        file = None
        if name in self:
            files = self[name]
            if len(files) > 1 and (properties or property_matcher):
                if property_matcher:
                    matching_files = [_ for _ in files if property_matcher(_)]
                else:
                    matching_files = [_ for _ in files if _.properties == properties]
                if matching_files:
                    files = matching_files
            if len(files) > 1 and file_sorter:
                files.sort(key=file_sorter)
            file = files[0]
        return file

    def reclassify(self, file_class: Type[FileObject] = CachedFile, **init_kwargs):
        """ re-instantiate all name's file registers items to instances of the class :paramref:`~.file_class`.

        :param file_class:      The new file object class (see :data:`FileObject`). Each found file object will passed
                                to the class constructor (callable) and replace the file object in the name' file list.
        :param init_kwargs:     additional/optional kwargs passed onto the used file_class. Pass e.g.
                                the object_loader to use, if :paramref:`~.file_class` is
                                :class:`CachedFile` (the default file_obj class).
        """
        for _name, files in self.items():
            for idx, file in enumerate(files):
                files[idx] = file_class(str(file), **init_kwargs)           # type: ignore

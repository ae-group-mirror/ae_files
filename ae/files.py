"""
file collection, grouping and caching
=====================================

This namespace portion is pure Python, only depending on the
:mod:`ae.paths` namespace portion and is providing helpers for
file managing.

The classes :class:`FilesRegister`, :class:`RegisteredFile` and
:class:`CachedFile` collect, group and cache
available files for to later find the best fitting match for
a requested purpose.

Usable for dynamic selection of image/font/audio/... files depending
on the current user preferences, hardware and/or software environment.


registered file
---------------

A registered file object represents a single file on your file system and
can be instantiated from one of the classes :class:`RegisteredFile` or
:class:`CachedFile` provided by this module/portion::

    from ae.files import RegisteredFile

    rf = RegisteredFile('path/to/the/file_name.extension')

    assert rf.path == 'path/to/the/file_name.extension'
    assert rf.stem == 'file_name'
    assert rf.ext == '.extension'
    assert rf.properties == dict()

The :attr:`~RegisteredFile.properties` attribute of the :class:`RegisteredFile`
instance is empty in the above example because the :attr:`~RegisteredFile.path`
does not contain folder names with an underscore character.


file properties
^^^^^^^^^^^^^^^

File properties are provided in the :attr:`~RegisteredFile.properties` attribute
which is a dict instance, where the key is the name of the property.
Each item of this attribute reflects a property of the registered file.

Property names and values are automatically determined
via the names of their specified sub-folders. Every sub-folder name containing an
underscore character in the format <name>_<value> will be interpreted
as a file property::

    rf = RegisteredFile('name1_69/name2_3.69/name3_whatever/file_name.ext')
    assert rf.properties['name1'] == 69
    assert rf.properties['name2'] == 3.69
    assert rf.properties['name3'] == 'whatever'

Currently the property types `int`, `float` and `string` are recognized
and converted into a property value.


cached file
-----------

A cached file created from the :class:`CachedFile` behaves like a
:ref:`registered file` and additionally provides the possibility to cache
parts or the whole file content as well as the file pointer
of the opened file::

    cf = CachedFile('integer_69/float_3.69/string_whatever/file_name.ext',
                    object_loader=lambda cached_file: open(cached_file.path))

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

A files register does the collection and selection of files for your application,
for example for to find and select resource files like icon/image or sound files.

Files can be collected from various places and then be provided by a single
instance of the class :class:`FilesRegister`::

    from ae.files import FilesRegister

    fr = FilesRegister('first/path/to/collect')
    fr.add_path('second/path/to/collect/files/from')

    registered_file = fr.find_file('file_name')

If a file with the base name `file_name` exists in a sub-folder of the two
provided paths then the :meth:`~FilesRegister.find_file` method will return
a object of type :class:`RegisteredFile`.

Several files with the same base name can be collected and registered e.g.
with different formats, for to be selected by the app by their different
properties. Assuming your application is providing an icon image in two
sizes, provided within the following directory structure::

    resources/
        size_72/
            app_icon.jpg
        size_150/
            app_icon.png

First create an instance of :class:`FilesRegister` for to collect both
image files from the `resources` folder::

    fr = FilesRegister('resources')

The resulting object `fr` behaves like a dict object,
where the item key is the file name without extension (app_icon) and
the item value is a list of instances of :class:`RegisteredFile`.
Both files in the resources folder are provided as one dict item::

    assert 'app_icon' in fr
    assert len(fr) == 1
    assert len(fr['app_icon']) == 2
    assert isinstance(fr['app_icon'][0], RegisteredFile)

For to select the appropriate image file you can use the
:meth:`~FilesRegister.find_file` method::

    app_icon_image_path = fr.find_file('app_icon', dict(size=current_size))

As a shortcut you can alternatively call the object directly
(leaving `.find_file` away)::

    app_icon_image_path = fr('app_icon', dict(size=current_size))

For more complex selections you can use callables passed
into the :paramref:`~FilesRegister.find_file.property_matcher` amd
:paramref:`~FilesRegister.find_file.file_sorter` arguments
of :meth:`~FilesRegister.find_file`.

"""
import glob
import os
from typing import Any, Callable, Dict, Optional, Type, Union

from ae.paths import path_files                 # type: ignore


__version__ = '0.1.5'


PropertyType = Union[int, float, str]           #: types of property values
PropertiesType = Dict[str, PropertyType]        #: dict of file properties


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

    # following alternative implementation fails if files exits with non-numeric indexes
    # found_files = sorted(glob.glob(path_stem + "*" + ext), reverse=True)
    # stem_len = len(path_stem)
    # index = int(found_files[0][stem_len:stem_len + digits]) + 1 if found_files else 1
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
    def __init__(self, path: str, **kwargs):
        """ initialize registered file instance.

        :param path:    file path.
        :param kwargs:  not supported, only there for compatibility to :class:`CachedFile` for to detect invalid kwargs.
        """
        assert not kwargs, "RegisteredFile does not have any kwargs - maybe want to use CachedFile as file_class."
        self.path: str = path                                           #: file path
        self.stem: str                                                  #: file basename without extension
        self.ext: str                                                   #: file name extension
        dir_name, base_name = os.path.split(path)
        self.stem, self.ext = os.path.splitext(base_name)

        self.properties: PropertiesType = dict()                        #: file properties
        # dir_name: str  # PyCharm needs the str type annotation
        for folder in dir_name.split(os.path.sep):
            # PyCharm assumes dir_name/folder are of type bytes?!?!?
            # noinspection PyTypeChecker
            parts = folder.split("_", maxsplit=1)
            if len(parts) == 2:
                self.add_property(*parts)

    def __eq__(self, other) -> bool:
        """ allow equality checks.

        :param other:   other object to compare this instance with.
        :return:        True if both objects contain a file with the same path, else False.
        """
        return isinstance(other, self.__class__) and other.path == self.path

    def __repr__(self):
        """ for config var storage and eval recovery.

        :return:    evaluable/recoverable representation of this object.
        """
        return f"{self.__class__.__name__}({self.path!r})"

    def add_property(self, property_name: str, str_value: str):
        """ add a property to this file instance.

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


def _default_object_loader(file):
    """ file object loader that is opening the file and keeping the handle of the opened file.

    :param file:                file object with a `path` attribute (holding the complete file path).
    :return:                    file handle to the opened file.
    """
    return open(file.path)


class CachedFile(RegisteredFile):
    """ represents a cacheables registered file. """
    def __init__(self, path: str,
                 object_loader: Callable[['CachedFile', ], Any] = _default_object_loader, late_loading: bool = True):
        """ create cached file instance.

        :param path:            path of the file.
        :param object_loader:   callable converting the file into a cached object (available
                                via :attr:`~CachedFile.loaded_object`).
        :param late_loading:    pass False for to convert/load file cache early, directly at instantiation.
        """
        super().__init__(path)
        self.object_loader = object_loader
        self.late_loading = late_loading
        self._loaded_object = None if late_loading else object_loader(self)

    @property
    def loaded_object(self):
        """ loaded object class instance property.

        :return: loaded and cached file object.
        """
        if self.late_loading and not self._loaded_object:
            self._loaded_object = self.object_loader(self)
        return self._loaded_object


class FilesRegister(dict):
    """ file register catalog. """
    def __init__(self, *args,
                 property_matcher: Optional[Callable[[RegisteredFile, ], bool]] = None,
                 file_sorter: Optional[Callable[[RegisteredFile, ], Any]] = None,
                 **add_path_kwargs):
        """ create files register instance.

        This method gets redirected with :paramref:`~FilesRegister.args` and
        :paramref:`~FilesRegister.add_path_kwargs` arguments to :meth:`~FilesRegister.add_path`.

        :param args:                if passed then :meth:`~FilesRegister.add_path` will be called with
                                    this args tuple.
        :param property_matcher:    property matcher callable, used as default value by
                                    :meth:`~FilesRegister.find_file` if not passed there.
        :param file_sorter:         file sorter callable, used as default value by
                                    :meth:`~FilesRegister.find_file` if not passed there.
        :param add_path_kwargs:     passed onto call of :meth:`~FilesRegister.add_path` if the
                                    :paramref:`FilesRegister.args` got provided by caller.
        """
        super().__init__()
        self.property_watcher = property_matcher
        self.file_sorter = file_sorter
        if args:
            self.add_path(*args, **add_path_kwargs)

    def __call__(self, *args, **kwargs):
        """ args and kwargs will be completely redirected to :meth:`~FilesRegister.find_file`. """
        return self.find_file(*args, **kwargs)

    def add_file(self, file: Union[Any]):
        """ add a single file to the list of this dict mapped by the file-name/stem as dict key.

        :param file:                either file path string or any object with a `stem` attribute.
        """
        name = os.path.splitext(os.path.basename(file))[0] if isinstance(file, str) else file.stem
        if name in self:
            self[name].append(file)
        else:
            self[name] = [file]

    def add_path(self, file_path_mask: str, recursive: bool = True,
                 file_class: Type[Any] = RegisteredFile, **file_class_kwargs) -> 'FilesRegister':
        """ add files found in folder specified by :paramref:`~add_path.path`.

        :param file_path_mask:      glob file path mask (with optional wildcards) specifying the files to
                                    collect (by default including the sub-folders).
        :param recursive:           pass False to only collect the given folder (ignoring sub-folders).
        :param file_class:          pass str or any class or callable where the returned instance/value is either
                                    a string or an object with a `stem` attribute (holding the file name w/o extension),
                                    like e.g. :class:`CachedFile`, :class:`RegisteredFile` or `pathlib.PurePath`.
                                    Each found file will passed to the class constructor and added to the
                                    list which is a item of this dict.
        :param file_class_kwargs:   additional/optional kwargs passed onto the used file_class. Pass e.g.
                                    the object_loader to use, if :paramref:`~add_path.file_class` is
                                    :class:`CachedFile` (instead of the default: :class:`RegisteredFile`).
        :return:
        """
        for file in path_files(file_path_mask, recursive=recursive, file_class=file_class, **file_class_kwargs):
            self.add_file(file)
        return self

    def find_file(self, name: str, properties: Optional[PropertiesType] = None,
                  property_matcher: Optional[Callable[[RegisteredFile, ], bool]] = None,
                  file_sorter: Optional[Callable[[RegisteredFile, ], Any]] = None,
                  ) -> Optional[RegisteredFile]:
        """ add file in folder specified by :paramref:`~add_path.path`.

        :param name:                file name (without extension) to find.
        :param properties:          properties for to select the correct file.
        :param property_matcher:    callable for to match the correct file.
        :param file_sorter:         callable for to sort resulting match results.
        :return:                    registered/cached file object of the first found/correct file.
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

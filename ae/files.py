""" This namespace portion is providing helpers for to handle files.

With the help of the classes :class:`RegisteredFile`, :class:`CachedFile` and
:class:`FilesRegister` your app could for example collect all available
image resource files for an easy selection of the best matching image
for the current screen resolutions.


registered file
===============

A registered file object represents a single file on your file system and
can be instantiated from one of the classes :class:`RegisteredFile` or
:class:`CachedFile` provided by this module/portion::

    from ae.files import RegisteredFile

    rf = RegisteredFile('path/to/the/file_name.extension')

    assert rf,path == 'path/to/the/file_name.extension'
    assert rf.name == 'file_name'
    assert rf.ext == '.extension'
    assert rf.properties == dict()

The :attr:`~RegisteredFile.properties` attribute of the :class:`RegisteredFile`
instance is empty in the above example because the :attr:`~RegisteredFile.path`
does not contain folder names with an underscore character.


file properties
---------------

File properties are provided in dict object, where each item reflects a property,
where the key is the name of the property.

Property names and values are automatically determined
via the names of their specified sub-folders. Every sub-folder name containing an
underscore character in the format <name>_<value> will be interpreted
as a file property::

    rf = RegisteredFile('integer_69/float_3,69/string_whatever/file_name.ext')
    assert rf.properties['integer'] == 69
    assert rf.properties['float'] == 3.69
    assert rf.properties['string'] == 'whatever'

Currently the types int, float and string are supported for property values.


cached file
===========

A cached file created from the :class:`CachedFile' behaves like
:ref:`registered file` and additionally provides the possibility to cache
parts or thw whole content of the file as well as the file pointer
of the file opened::

    cf = CachedFile('integer_69/float_3,69/string_whatever/file_name.ext',
                    object_loader=lambda cached_file: open(cached_file.path))

    assert cf,path == 'integer_69/float_3,69/string_whatever/file_name.ext'
    assert cf.name == 'file_name'
    assert cf.ext == '.ext'
    assert cf.properties['integer'] == 69
    assert cf.properties['float'] == 3.69
    assert cf.properties['string'] == 'whatever'

    assert isinstance(cf.loaded_object, TextIOWrapper)
    cf.loaded_object.seek(...)
    cf.loaded_object.read(...)

    cf.loaded_object.close()


files register
==============

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

Several files with the same base name can be collected and registered e,g,
with different formats, for to be selected by the app by their different
properties. Assuming your application is providing an icon image in two
sizes, provided within the following directory structure:

    resources
        size_72
            app_icon.jpg
        size_150
            app_icon.png

First create an instance of :class:`FilesRegister` for to collect both
image files::

    fr = FilesRegister('resources')

After the files collection the resulting `fr` behaves like a dict object,
where the key is the file name (app_icon) without extension and
the value is a list of instances of :class:`RegisteredFile`. So
both files in the resources folder are provided as one dict item::

    assert 'app_icon` in fr
    assert len(fr['app_icon']) == 2
    assert isinstance(fr['app_icon`][0], RegisteredFile)

For to select the appropriate image file you can use the
:meth:`~FilesRegister.find_file` method::

    app_icon_image_path = fr.find_file('app_icon', dict(size=current_size))

For more complex selections you can use callables which have to be passed
into the :paramref:`~FilesRegister.find_file.property_matcher` amd
:paramref:`~FilesRegister.find_file.file_sorter` arguments
of :meth:`~FilesRegister.find_file`.
"""
import glob
import os
from typing import Any, Callable, Dict, Optional, Type, Union


__version__ = '0.0.1'


PropertyType = Union[int, float, str]           #: types of property values
PropertiesType = Dict[str, PropertyType]        #: dict of file properties


class RegisteredFile:
    """ represents a single file. """
    def __init__(self, path: str, **kwargs):
        """ initialize registered file instance.

        :param path:    file path.
        :param kwargs:  not supported, only there for compatibility to :class:`CachedFile` for to detect invalid kwargs.
        """
        assert not kwargs, "RegisteredFile does not have any kwargs - maybe want to use CachedFile as file_class."
        self.path: str = path                                           #: file path
        self.name: str                                                  #: file basename without extension
        self.ext: str                                                   #: file name extension
        dir_name, base_name = os.path.split(path)
        self.name, self.ext = os.path.splitext(base_name)

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

        :param property_name:   name of the property to add.
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

        This method gets redirected with *args and **add_path_kwargs to :meth:`~FilesRegister.add_path`.

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

    def add_path(self, path: str, recursive: bool = True, file_class: Type[RegisteredFile] = RegisteredFile,
                 **file_class_kwargs) -> 'FilesRegister':
        """ add file in folder specified by :paramref:`~add_path.path`.

        :param path:                path to root folder for to collect file from (by default including
                                    from the sub-folders of the root folder).
        :param recursive:           pass False to only collect the given folder (ignoring sub-folders).
        :param file_class:          pass :class:`CachedFile` for to cache the files that will be collected.
        :param file_class_kwargs:   additional/optional kwargs passed onto the used file_class. Pass e.g.
                                    the object_loader to use if :paramref:`~add_path.file_class` is
                                    :class:`CachedFile` (do not use with RegisteredFile).
        :return:
        """
        if recursive and not path.endswith('**'):
            path = os.path.join(path, '**')
        files = list()
        for part in glob.glob(path, recursive=recursive):
            if os.path.isfile(part):
                files.append(file_class(part, **file_class_kwargs))
        for file in files:
            name = file.name
            if name in self:
                self[name].append(file)
            else:
                self[name] = [file]
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

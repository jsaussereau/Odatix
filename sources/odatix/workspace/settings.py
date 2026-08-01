# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""
Typed settings objects, and how they map to the YAML files of a workspace.

A settings class declares its keys once, as :class:`Setting` descriptors::

    class MySettings(Settings):
        rtl_path = Setting("", type="str", section="Source files")
        use_parameters = Setting(False, type="bool", style="yesno")

and gets, for free: attribute access with type coercion (``settings.rtl_path``),
dict access for code that would rather use it as a mapping
(``settings["rtl_path"]``), loading with defaults, and writing back either as a
freshly generated file (with its section comments) or as an update of the user's
own file that leaves comments, ordering and unknown keys alone.

Anything the class does not declare is not lost: it is kept in ``settings.extra``
and written back where it was.

Note: this is deliberately not built on ``dataclasses``, which Odatix cannot use
in the modules reachable from its command line (Python 3.6 support).
"""

import copy

from ruamel.yaml.comments import CommentedMap

from odatix.workspace.yaml_io import (
    flow_seq,
    new_document,
    parse_bool,
    parse_int,
    parse_int_list,
    read_document,
    read_yaml,
    write_document,
    yes_no,
)

__all__ = ["Setting", "Settings", "load_settings", "save_settings", "render", "apply"]


######################################
# Field declaration
######################################

class Setting(object):
    """
    One key of a settings file.

    Args:
        default: value used when the file does not define the key.
        type (str | type): how the value is read and written. One of "any",
            "str", "int", "optional_int", "bool", "list", "str_list",
            "int_list", "dict", or a :class:`Settings` subclass for a nested
            block.
        key (str): name of the key in the file, when it differs from the
            attribute name.
        section (str): title of the block this key opens. Rendered as a comment
            above it when Odatix generates the file.
        comment (str): end-of-line comment, rendered the same way.
        style (str): "yesno" to write booleans as Yes/No, "flow" to write a list
            inline as "[a, b]".
        when (str): name of another (boolean) setting this key depends on,
            optionally prefixed with "!" to negate it. The key is only written
            when the condition holds, and is removed from the file when it stops
            holding, so mutually exclusive settings never coexist in a file.
        alt_key (str): key the value is written under when the `when` condition
            does not hold, instead of being removed. This is how a workspace
            file remembers a value that is currently switched off.
        alt_comment (str): end-of-line comment of that other key.
        stored (bool): False for a setting that only exists in memory (a switch
            whose state is read back from which key the file uses, for
            instance). It is never written, but it is part of the settings.
        skip_if_empty (bool): do not write the key at all when its value is
            empty.
        doc (str): what the setting means, for the API documentation and the
            command line help.
    """

    _order = 0

    def __init__(self, default=None, type="any", key=None, section=None, comment=None,
                 style=None, when=None, skip_if_empty=False, doc=None, factory=None,
                 alt_key=None, alt_comment=None, stored=True):
        Setting._order += 1
        self.order = Setting._order
        self.name = None
        self.key = key
        self.default = default
        self.type = type
        self.section = section
        self.comment = comment
        self.style = style
        self.when = when
        self.skip_if_empty = skip_if_empty
        self.doc = doc
        self.factory = factory
        self.alt_key = alt_key
        self.alt_comment = alt_comment
        self.stored = stored

    ######################################
    # Values
    ######################################

    def make_default(self):
        """A fresh default value (never shared between two settings objects)."""
        if self.factory is not None:
            return self.factory()
        if self._nested_class() is not None:
            return self._nested_class()()
        return copy.deepcopy(self.default)

    def _nested_class(self):
        return self.type if isinstance(self.type, type) and issubclass(self.type, Settings) else None

    def coerce(self, value):
        """Read a value of any origin (file, form field, user code) as this setting's type."""
        nested = self._nested_class()
        if nested is not None:
            if isinstance(value, nested):
                return value
            return nested.from_dict(value if isinstance(value, dict) else {})

        if self.type == "str":
            return "" if value is None else str(value)
        if self.type == "int":
            return parse_int(value, self.default)
        if self.type == "optional_int":
            return parse_int(value, None)
        if self.type == "bool":
            return parse_bool(value, bool(self.default))
        if self.type == "int_list":
            return parse_int_list(value)
        if self.type == "str_list":
            if value is None or value == "":
                return []
            if isinstance(value, (list, tuple)):
                return [str(item) for item in value if item is not None]
            return [str(value)]
        if self.type == "list":
            if value is None or value == "":
                return []
            if isinstance(value, (list, tuple)):
                return list(value)
            return [value]
        if self.type == "dict":
            return dict(value) if isinstance(value, dict) else {}
        return value

    def dump(self, value):
        """Turn a value into what is written in the file."""
        nested = self._nested_class()
        if nested is not None:
            return render(value)
        if self.style == "yesno":
            return yes_no(value)
        if self.style == "flow":
            return flow_seq(value)
        if self.type == "optional_int" and value is None:
            return ""
        return value

    def is_empty(self, value):
        if self._nested_class() is not None:
            # A block is empty when it would write nothing, not when its fields
            # happen to be unset: what it writes is what matters here.
            return len(render(value)) == 0
        if self.type == "bool":
            return not value
        return value is None or value == "" or value == [] or value == {}


######################################
# Settings objects
######################################

class SettingsMeta(type):
    """Collects the :class:`Setting` declarations of a class, in declaration order."""

    def __new__(mcs, name, bases, namespace):
        specs = {}
        order = []
        for base in bases:
            for spec_name in getattr(base, "_spec_order", []):
                if spec_name not in specs:
                    order.append(spec_name)
                specs[spec_name] = base._specs[spec_name]

        own = [(key, value) for key, value in namespace.items() if isinstance(value, Setting)]
        own.sort(key=lambda item: item[1].order)
        body = dict((key, value) for key, value in namespace.items() if not isinstance(value, Setting))

        cls = super(SettingsMeta, mcs).__new__(mcs, name, bases, body)
        for spec_name, spec in own:
            spec.name = spec_name
            if spec.key is None:
                spec.key = spec_name
            if spec_name not in specs:
                order.append(spec_name)
            specs[spec_name] = spec
        cls._specs = specs
        cls._spec_order = order
        return cls


_SettingsBase = SettingsMeta("_SettingsBase", (object,), {})


class Settings(_SettingsBase):
    """
    Base class of every settings object of the workspace API.

    Instances behave both as objects (``settings.rtl_path``) and as mappings
    (``settings["rtl_path"]``, ``dict(settings.items())``), so they can be
    handed to code that expects either.
    """

    #: True for settings whose file is expected to spell every key out, even the
    #: ones left at their default (the run settings files, which Odatix reads
    #: key by key and refuses when one is missing).
    write_all_settings = False

    def __init__(self, **values):
        object.__setattr__(self, "extra", {})
        # What the file held when it was read. Saving compares against it, so
        # that a setting nobody touched is left in the file exactly as it was,
        # quoting and layout included.
        object.__setattr__(self, "_file_data", {})
        for name in self._spec_order:
            object.__setattr__(self, name, self._specs[name].make_default())
        for key, value in values.items():
            self[key] = value

    ######################################
    # Introspection
    ######################################

    @classmethod
    def specs(cls):
        """The declared settings, in file order."""
        return [cls._specs[name] for name in cls._spec_order]

    @classmethod
    def spec(cls, name):
        return cls._specs.get(name)

    ######################################
    # Attribute access
    ######################################

    def __setattr__(self, name, value):
        spec = self._specs.get(name)
        if spec is not None:
            value = spec.coerce(value)
        object.__setattr__(self, name, value)

    ######################################
    # Mapping access
    ######################################

    def __getitem__(self, key):
        name = self._name_of(key)
        if name is not None:
            return getattr(self, name)
        return self.extra[key]

    def __setitem__(self, key, value):
        name = self._name_of(key)
        if name is not None:
            setattr(self, name, value)
        else:
            self.extra[key] = value

    def __delitem__(self, key):
        name = self._name_of(key)
        if name is not None:
            setattr(self, name, self._specs[name].make_default())
        else:
            del self.extra[key]

    def __contains__(self, key):
        return self._name_of(key) is not None or key in self.extra

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def _name_of(self, key):
        if key in self._specs:
            return key
        for name in self._spec_order:
            if self._specs[name].key == key:
                return name
        return None

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return [self._specs[name].key for name in self._spec_order] + list(self.extra.keys())

    def values(self):
        return [self[key] for key in self.keys()]

    def items(self):
        return [(key, self[key]) for key in self.keys()]

    def update(self, values=None, **kwargs):
        """Set several settings at once, from a mapping and/or keyword arguments."""
        for source in (values, kwargs):
            if not source:
                continue
            for key, value in (source.items() if hasattr(source, "items") else source):
                self[key] = value
        return self

    ######################################
    # Conversion
    ######################################

    @classmethod
    def from_dict(cls, data):
        """Build a settings object from a plain mapping, keeping unknown keys in ``extra``."""
        settings = cls()
        if not isinstance(data, dict):
            return settings
        known_keys = set()
        for name in cls._spec_order:
            spec = cls._specs[name]
            known_keys.add(spec.key)
            if spec.alt_key:
                known_keys.add(spec.alt_key)
            if spec.key in data:
                setattr(settings, name, data[spec.key])
                settings._set_condition(spec, True)
            elif spec.alt_key and spec.alt_key in data:
                # The value is in the file under the key that says it is off.
                setattr(settings, name, data[spec.alt_key])
                settings._set_condition(spec, False)
        extra = dict((key, value) for key, value in data.items() if key not in known_keys)
        object.__setattr__(settings, "extra", extra)
        object.__setattr__(settings, "_file_data", dict(data))
        return settings

    def to_dict(self, include_extra=True, skip_disabled=False):
        """
        A plain mapping of the settings.

        Args:
            include_extra (bool): include the keys the class does not declare.
            skip_disabled (bool): leave out the keys whose ``when`` condition
                does not hold, i.e. the ones that would not be written to file.
        """
        data = {}
        for name in self._spec_order:
            spec = self._specs[name]
            if skip_disabled and not self._condition_holds(spec):
                continue
            value = getattr(self, name)
            if isinstance(value, Settings):
                value = value.to_dict(include_extra=include_extra, skip_disabled=skip_disabled)
            data[spec.key] = value
        if include_extra:
            data.update(copy.deepcopy(self.extra))
        return data

    def copy(self):
        clone = self.__class__.from_dict(self.to_dict())
        object.__setattr__(clone, "_file_data", dict(self._file_data))
        return clone

    def _mark_saved(self):
        """Take what is now in memory as the reference of what the file holds."""
        object.__setattr__(self, "_file_data", self.to_dict())
        for name in self._spec_order:
            value = getattr(self, name)
            if isinstance(value, Settings):
                value._mark_saved()

    def _unchanged(self, spec, value):
        """Whether a setting still holds what the file it was read from said."""
        if spec.key not in self._file_data:
            return False
        try:
            return spec.coerce(self._file_data[spec.key]) == value
        except Exception:
            return False

    def _condition_holds(self, spec):
        if not spec.when:
            return True
        name = spec.when
        negated = name.startswith("!")
        if negated:
            name = name[1:]
        value = bool(getattr(self, name, False))
        return not value if negated else value

    def _set_condition(self, spec, holds):
        """
        Set the switch a setting depends on, when reading tells which of its two
        keys the file uses.
        """
        if not spec.when or not spec.alt_key:
            return
        name = spec.when
        negated = name.startswith("!")
        if negated:
            name = name[1:]
        if name in self._specs:
            setattr(self, name, not holds if negated else holds)

    ######################################
    # Comparison / display
    ######################################

    def __eq__(self, other):
        if isinstance(other, Settings):
            return self.to_dict() == other.to_dict()
        if isinstance(other, dict):
            return self.to_dict() == other
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __repr__(self):
        inner = ", ".join(
            "{0}={1!r}".format(name, getattr(self, name)) for name in self._spec_order
        )
        return "{0}({1})".format(self.__class__.__name__, inner)


######################################
# Documents
######################################

def render(settings, header=None):
    """
    Build a complete YAML document from a settings object, with the section
    comments that make a generated Odatix file readable.
    """
    data = new_document(header)
    pending_section = None
    for spec in settings.specs():
        if not spec.stored:
            continue
        holds = settings._condition_holds(spec)
        key = spec.key if holds else spec.alt_key
        value = getattr(settings, spec.name)
        if key is None or (spec.skip_if_empty and spec.is_empty(value)):
            if spec.section and pending_section is None:
                pending_section = spec.section
            continue
        data[key] = spec.dump(value)
        # A section whose first key is not written passes its title on to what
        # follows, unless that opens a section of its own.
        section = spec.section or pending_section
        pending_section = None
        if section:
            data.yaml_set_comment_before_after_key(key, before="\n" + section)
        comment = spec.comment if holds else spec.alt_comment
        if comment:
            data.yaml_add_eol_comment(comment, key=key)
    for key, value in settings.extra.items():
        data[key] = value
    return data


def apply(settings, data):
    """
    Write a settings object into an existing document, leaving its comments,
    its key order and everything it holds that the settings class does not
    declare untouched.

    Only what actually changed is written: a setting nobody touched keeps the
    exact text it had in the file, and a setting left at its default is not
    added to a file that never mentioned it.
    """
    if data is None:
        data = CommentedMap()
    for spec in settings.specs():
        if not spec.stored:
            continue
        holds = settings._condition_holds(spec)
        key = spec.key if holds else spec.alt_key
        if key != spec.key:
            data.pop(spec.key, None)
        if spec.alt_key and key != spec.alt_key:
            data.pop(spec.alt_key, None)
        if key is None:
            continue
        value = getattr(settings, spec.name)
        if spec.skip_if_empty and spec.is_empty(value):
            data.pop(key, None)
            continue
        unchanged = key == spec.key and settings._unchanged(spec, value)
        if unchanged and key in data:
            continue
        if (not settings.write_all_settings
                and key not in data and not unchanged and value == spec.make_default()):
            # A default the file never mentioned: saying it explicitly would add
            # noise, and would freeze a value the user may want Odatix to own.
            continue
        if isinstance(value, Settings) and isinstance(data.get(key), CommentedMap):
            apply(value, data[key])
        else:
            data[key] = spec.dump(value)
    for key in settings._file_data:
        if key not in settings.extra and key not in [spec.key for spec in settings.specs()]:
            data.pop(key, None)
    for key, value in settings.extra.items():
        if key in data and settings._file_data.get(key) == value:
            continue  # untouched: leave the file's own version, as it was written
        data[key] = value
    return data


def load_settings(settings_class, path):
    """
    Read a settings file. A file that does not exist yields the defaults, which
    is what a workspace object that has not been saved yet holds.
    """
    return settings_class.from_dict(read_yaml(path, default={}))


def save_settings(settings, path, header=None, regenerate=False):
    """
    Write a settings object to `path`.

    An existing file is updated in place, so the comments and the extra keys the
    user put there survive. A file that does not exist yet (or `regenerate`) is
    generated from scratch, with its header and section comments.
    """
    import os

    if regenerate or not os.path.isfile(path):
        document = render(settings, header=header)
    else:
        document = apply(settings, read_document(path))
    write_document(path, document)
    settings._mark_saved()
    return path

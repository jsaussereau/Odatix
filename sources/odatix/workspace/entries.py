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
The shape shared by everything a workspace holds.

Architectures, simulations, workflows and tools are all directories under a
root directory, and they are all created, renamed, duplicated and deleted the
same way. :class:`Entry` is one of those directories, :class:`Collection` is the
set of them, and both are subclassed to add what is specific to each kind.
"""

import os
import shutil

from natsort import natsorted

import odatix.lib.hard_settings as hard_settings
from odatix.lib.utils import copytree
from odatix.workspace.errors import AlreadyExistsError, InvalidNameError, NotFoundError

__all__ = ["Entry", "Collection", "check_name"]


def check_name(name, kind="entry"):
    """
    Refuse a name that cannot be a directory name, before anything is written.
    """
    if name is None or str(name).strip() == "":
        raise InvalidNameError("A {0} name cannot be empty.".format(kind))
    name = str(name)
    for character in hard_settings.invalid_filename_characters:
        if character in name:
            raise InvalidNameError(
                "Invalid {0} name '{1}': it cannot contain '{2}'.".format(kind, name, character)
            )
    return name


class Entry(object):
    """
    One directory of a workspace, holding the definition of an architecture, a
    simulation, a workflow or a tool.
    """

    #: What this kind of entry is called in error messages.
    kind = "entry"

    def __init__(self, workspace, root, name):
        self.workspace = workspace
        self.root = root
        self.name = str(name)

    ######################################
    # Location
    ######################################

    @property
    def path(self):
        """Path of the directory holding this entry."""
        return os.path.join(self.root, self.name)

    @property
    def exists(self):
        return os.path.isdir(self.path)

    def require(self):
        """Raise unless the entry exists on disk. Returns the entry, to be chained."""
        if not self.exists:
            raise NotFoundError("No such {0}: '{1}'.".format(self.kind, self.name))
        return self

    ######################################
    # Lifecycle
    ######################################

    def create(self):
        """Create the directory of this entry. Does nothing if it already exists."""
        os.makedirs(self.path, exist_ok=True)
        return self

    def delete(self):
        """Delete this entry and everything in its directory."""
        if os.path.isdir(self.path):
            shutil.rmtree(self.path)
        elif os.path.exists(self.path):
            os.remove(self.path)
        return self

    def rename(self, new_name):
        """
        Rename this entry. The object keeps pointing at it under its new name.
        """
        new_name = check_name(new_name, self.kind)
        if new_name == self.name:
            return self
        self.require()
        target = os.path.join(self.root, new_name)
        if os.path.exists(target):
            raise AlreadyExistsError("A {0} named '{1}' already exists.".format(self.kind, new_name))
        shutil.move(self.path, target)
        self.name = new_name
        return self

    def duplicate(self, new_name):
        """Copy this entry under another name, and return the copy."""
        new_name = check_name(new_name, self.kind)
        self.require()
        target = os.path.join(self.root, new_name)
        if os.path.exists(target):
            raise AlreadyExistsError("A {0} named '{1}' already exists.".format(self.kind, new_name))
        copytree(self.path, target)
        return self.__class__(self.workspace, self.root, new_name)

    ######################################
    # Display
    ######################################

    def __repr__(self):
        return "<{0} {1!r}>".format(self.__class__.__name__, self.name)

    def __eq__(self, other):
        return (
            isinstance(other, Entry)
            and self.__class__ is other.__class__
            and os.path.abspath(self.path) == os.path.abspath(other.path)
        )

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __hash__(self):
        return hash((self.__class__.__name__, os.path.abspath(self.path)))


class Collection(object):
    """
    The entries of one kind held by a workspace.

    Iterating over a collection yields entry objects; :meth:`names` gives their
    names. Both ``"MyArch" in ws.architectures`` and
    ``ws.architectures["MyArch"]`` work.
    """

    entry_class = Entry

    def __init__(self, workspace, path):
        self.workspace = workspace
        self._path = path

    ######################################
    # Location
    ######################################

    @property
    def path(self):
        """Directory holding the entries of this collection."""
        return self._path() if callable(self._path) else self._path

    @property
    def kind(self):
        return self.entry_class.kind

    ######################################
    # Listing
    ######################################

    def names(self):
        """Names of the entries, in natural order."""
        path = self.path
        if not path or not os.path.isdir(path):
            return []
        return natsorted([
            entry for entry in os.listdir(path)
            if os.path.isdir(os.path.join(path, entry))
        ])

    def __iter__(self):
        for name in self.names():
            yield self._make(name)

    def __len__(self):
        return len(self.names())

    def __contains__(self, item):
        name = item.name if isinstance(item, Entry) else item
        return self.exists(name)

    def __getitem__(self, name):
        return self._make(name).require()

    def get(self, name, default=None):
        """The entry, or `default` when there is no such entry."""
        entry = self._make(name)
        return entry if entry.exists else default

    def entry(self, name):
        """
        The entry of that name, whether or not it exists yet. Its settings are
        then the defaults, and saving it is what creates it: this is what an
        editor works on while a new entry is being filled in.
        """
        return self._make(name)

    def exists(self, name):
        return self._make(name).exists

    def _make(self, name):
        return self.entry_class(self.workspace, self.path, name)

    ######################################
    # Lifecycle
    ######################################

    def create(self, name, **kwargs):
        """
        Create an entry and return it. Raises if it already exists, so a
        creation never silently lands on someone else's directory.
        """
        name = check_name(name, self.kind)
        entry = self._make(name)
        if entry.exists:
            raise AlreadyExistsError("A {0} named '{1}' already exists.".format(self.kind, name))
        entry.create()
        self._initialize(entry, **kwargs)
        return entry

    def _initialize(self, entry, **kwargs):
        """Hook for subclasses: fill a freshly created entry."""

    def delete(self, name):
        """Delete an entry. Deleting one that is already gone does nothing."""
        return self._make(name).delete()

    def rename(self, name, new_name):
        """Rename an entry, and return it."""
        return self[name].rename(new_name)

    def duplicate(self, name, new_name):
        """Copy an entry under another name, and return the copy."""
        return self[name].duplicate(new_name)

    ######################################
    # Display
    ######################################

    def __repr__(self):
        return "<{0} {1}>".format(self.__class__.__name__, self.names())

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
Exceptions raised by the workspace API.

They all derive from :class:`WorkspaceError`, so a caller that does not care
about the details can catch that one. They also derive from the built-in
exception a caller would naturally expect (``KeyError`` when something is
missing from a collection, ``ValueError`` when an argument is refused), so code
written against the plain-Python conventions keeps working.
"""

__all__ = [
    "WorkspaceError",
    "NotFoundError",
    "AlreadyExistsError",
    "InvalidNameError",
    "NotAWorkspaceError",
    "InvalidSettingsError",
]


class WorkspaceError(Exception):
    """Base class of every error raised by the workspace API."""


class NotFoundError(WorkspaceError, KeyError):
    """An architecture, simulation, workflow, tool, domain... does not exist."""

    def __str__(self):
        # KeyError renders its argument with repr(), which reads badly in a
        # message meant for a user ("'no such architecture'").
        return self.args[0] if self.args else ""


class AlreadyExistsError(WorkspaceError, ValueError):
    """The name asked for is already taken."""


class InvalidNameError(WorkspaceError, ValueError):
    """The name asked for cannot be used on disk (empty, path separator, ...)."""


class NotAWorkspaceError(WorkspaceError, ValueError):
    """The directory holds no Odatix settings file."""


class InvalidSettingsError(WorkspaceError, ValueError):
    """
    A settings file cannot be used as it is: it is missing, it is not valid
    YAML, or it holds a value of the wrong kind.

    This is what reading a file *for a run* raises. Reading one to edit it never
    does: a file being written is allowed to be incomplete.

    Args:
        message (str): what is wrong, as told to a user.
        path (str): the file it is wrong in.
        key (str): the key it is wrong at, when it is about one key.
        hints (list): what a user can do about it, one line each.
    """

    def __init__(self, message, path=None, key=None, hints=None):
        super(InvalidSettingsError, self).__init__(message)
        self.message = message
        self.path = path
        self.key = key
        self.hints = list(hints) if hints else []

    def __str__(self):
        return self.message

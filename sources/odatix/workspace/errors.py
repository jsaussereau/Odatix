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

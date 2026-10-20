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
Odatix's job handler is jobtender (https://github.com/jsaussereau/jobtender):
sessions, daemons, the terminal monitor, the API they talk through.

This package stays for the code that imports it under its former name: every
odatix.lib.parallel_job_handler.<module> is jobtender.<module> itself, the
same module object, not a copy -- what a test patches in one is patched in the
other. New code imports jobtender.
"""

import importlib
import importlib.abc
import importlib.util
import sys

import jobtender
from jobtender import *  # noqa: F401,F403
from jobtender import __all__  # noqa: F401

_PREFIX = __name__ + "."
_TARGET = "jobtender."


class _AliasLoader(importlib.abc.Loader):
    """Loads odatix.lib.parallel_job_handler.<x> as the module jobtender.<x>."""

    def __init__(self, target):
        self._target = target

    def create_module(self, spec):
        return importlib.import_module(self._target)

    def exec_module(self, module):
        pass


class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(_PREFIX):
            return None
        alias = _TARGET + fullname[len(_PREFIX):]
        if importlib.util.find_spec(alias) is None:
            return None
        return importlib.util.spec_from_loader(fullname, _AliasLoader(alias))


# First: the package has no files of its own to be found anywhere else.
sys.meta_path.insert(0, _AliasFinder())
__path__ = []

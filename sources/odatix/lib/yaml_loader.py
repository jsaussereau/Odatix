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
The YAML loader and emitter Odatix reads and writes its files with.

PyYAML ships two implementations of the same parser: a pure-Python one, and
bindings to libyaml. The second is several times faster *and* releases the GIL
for the parse, which matters twice over here: a results file or an exploration
archive of a few megabytes costs seconds with the pure-Python parser, and the
pages that read them do so from a request thread while jobs are running.

libyaml is not always built into the installed PyYAML, hence the fallback --
same behaviour, just slower.

Use :data:`SafeLoader` wherever a file is read (``yaml.load(f, Loader=...)``)
and :data:`SafeDumper` wherever one is written, rather than ``yaml.safe_load``
and ``yaml.safe_dump``, which always take the Python path.
"""

import yaml

try:
  SafeLoader = yaml.CSafeLoader
  SafeDumper = yaml.CSafeDumper
except AttributeError:  # pragma: no cover - depends on the PyYAML build
  SafeLoader = yaml.SafeLoader
  SafeDumper = yaml.SafeDumper

#: True when the libyaml bindings are in use.
FAST = SafeLoader is not yaml.SafeLoader

__all__ = ["SafeLoader", "SafeDumper", "FAST", "safe_load"]


def safe_load(stream):
  """``yaml.safe_load``, with the fast parser when there is one."""
  return yaml.load(stream, Loader=SafeLoader)

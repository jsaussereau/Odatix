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
Where the program of a simulator is, as the system runs it.

On Linux and macOS, a program is found in the PATH by its name. On Windows,
some simulators are installed under another name than the one their commands
use: the OSS CAD Suite ships Verilator as a Perl script, "verilator", that
Windows cannot start, next to "verilator_bin.exe", the binary it runs. Asked
for "verilator", Windows gets the binary.
"""

import os
import shutil

#: What runs a program on Windows when its own name does not: tried in order
WINDOWS_ALTERNATIVES = {
  "verilator": ["verilator_bin"],
}


def which(program):
  """
  The path of a program, as `shutil.which` gives it, or None. On Windows, a
  program that is not found by its name, or only as a file without an
  extension (a script Windows cannot start), is looked for under the names of
  WINDOWS_ALTERNATIVES first.
  """
  path = shutil.which(program)
  if os.name != "nt":
    return path
  if path is not None and os.path.splitext(path)[1]:
    return path
  for alternative in WINDOWS_ALTERNATIVES.get(os.path.basename(str(program)).lower(), []):
    found = shutil.which(alternative)
    if found is not None:
      return found
  return path

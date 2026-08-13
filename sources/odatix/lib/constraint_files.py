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
User constraint files handed to a job on top of the ones Odatix generates.

Odatix writes the timing constraint of a job itself ($constraints_file in tcl):
init_script.tcl creates it and update_freq rewrites it whole at every iteration
of an fmax search. Anything a user puts there would therefore be lost, which is
why constraints they provide -- an IO placement xdc for an FPGA board, timing
exceptions, a floorplan script -- live in files of their own, copied into the
job's work directory and read *in addition to* the generated one.

They are declared under a "constraints" key, in the target file of a tool (what
depends on the part or the board) and/or in the "_settings.yml" of an
architecture (what depends on the design). Either file can declare them for all
of its jobs or for some of them -- under "target_settings/<target>" in a target
file, in a rule of the "overrides" section in an architecture one (see
:mod:`odatix.lib.overrides`), which is where a constraint that depends on both
the design and the tool goes. All of them are read, and what they declare adds
up. Three shapes are accepted:

    constraints: pinout.xdc

    constraints:
      - pinout.xdc
      - exceptions.xdc

    constraints:
      - files: [pinout.xdc, banks.xdc]
        scope: pnr
      - file: exceptions.xdc      # scope defaults to "all"

The scope says which stage of a job reads the file: "synthesis", "pnr", or
"all". It matters when the two stages are run by different tools ("odatix pnr"),
where a floorplan has no meaning for the synthesis tool and a synthesis
exception has none for the place & route one.
"""

import os
import shutil

import odatix.lib.hard_settings as hard_settings
import odatix.lib.printc as printc
from odatix.lib.variables import replace_variables

script_name = os.path.basename(__file__)

#: The stages a constraint file can be read at. "all" means both.
SCOPES = ("synthesis", "pnr")
DEFAULT_SCOPE = "all"


class ConstraintFileError(Exception):
    """A "constraints" declaration Odatix cannot build a job from."""


def _entry_source(entry):
  return entry.get("source", "")


def _normalize_scope(scope, where):
  scope = str(scope).strip().lower() if scope is not None else DEFAULT_SCOPE
  if scope == "":
    scope = DEFAULT_SCOPE
  if scope != DEFAULT_SCOPE and scope not in SCOPES:
    raise ConstraintFileError(
      'Invalid scope "' + scope + '" for a constraint file in "' + where + '". '
      + 'Valid scopes are "' + '", "'.join(SCOPES) + '" and "' + DEFAULT_SCOPE + '".'
    )
  return scope


def _entries_of_item(item, where):
  """Turn one item of a "constraints" list into a list of {source, scope}."""
  if isinstance(item, str):
    return [{"source": item, "scope": DEFAULT_SCOPE}]

  if not isinstance(item, dict):
    raise ConstraintFileError(
      'Invalid constraint entry of type "' + item.__class__.__name__ + '" in "' + where + '". '
      + "A constraint entry is either a file path or a mapping with a \"file\"/\"files\" key."
    )

  files = item.get("files", item.get("file"))
  if isinstance(files, str):
    files = [files]
  if not isinstance(files, list) or not files:
    raise ConstraintFileError(
      'A constraint entry in "' + where + '" has no "file" or "files" key.'
    )

  scope = _normalize_scope(item.get("scope"), where)
  entries = []
  for path in files:
    if not isinstance(path, str):
      raise ConstraintFileError(
        'Invalid constraint file of type "' + path.__class__.__name__ + '" in "' + where + '". '
        + "A constraint file is a path."
      )
    entries.append({"source": path, "scope": scope})
  return entries


def read_constraints(data, filename, variables=None, parent=None):
  """
  Read the "constraints" key of a settings mapping.

  Args:
    data (dict): the mapping holding the key (a whole settings file, or one of
      the rules of its "overrides" section).
    filename (str): file the mapping comes from, for error messages.
    variables (Variables): user accessible variables to expand in the paths.
    parent (str): path of the mapping inside the file, for error messages.

  Returns:
    list: {"source", "scope"} entries, with existing source paths made absolute.

  Raises:
    ConstraintFileError: on an invalid declaration or a file that does not exist.
      A constraint file that cannot be found is an error and not a warning: a
      job that silently runs without the pinout it was given would produce a
      result that looks valid and is not.
  """
  if not isinstance(data, dict):
    return []

  declaration = data.get("constraints")
  if declaration is None:
    return []

  where = filename if not parent else filename + " (" + parent + ")"

  if isinstance(declaration, (str, dict)):
    declaration = [declaration]
  if not isinstance(declaration, list):
    raise ConstraintFileError(
      'Key "constraints" in "' + where + '" is of type "' + declaration.__class__.__name__
      + '" while it should be a file path or a list.'
    )

  entries = []
  for item in declaration:
    entries.extend(_entries_of_item(item, where))

  for entry in entries:
    source = replace_variables(entry["source"], variables)
    if not os.path.isfile(source):
      raise ConstraintFileError(
        'The constraint file "' + source + '" declared in "' + where + '" does not exist.'
      )
    entry["source"] = os.path.realpath(source)

  return entries


def resolve(entries):
  """
  Give each entry the path it gets inside the job's work directory.

  One file gives one entry, whatever the number of declarations naming it: the
  same pinout mentioned by the tool's target file and again by one of its
  targets is copied once and read once. The scopes of those declarations are
  merged -- a file wanted at both stages, whether because a declaration says
  "all" or because two of them say "synthesis" and "pnr", ends up scoped "all".

  Two *different* files sharing a basename get distinct destinations, so an
  "io.xdc" from the target and an "io.xdc" from the architecture do not
  overwrite each other.

  Args:
    entries (list): {"source", "scope"} entries, in declaration order.

  Returns:
    list: one entry per file, in order of first declaration, each with a "dest"
      key relative to the work directory.
  """
  resolved = []
  index_of = {} # source -> its entry in resolved
  taken = set() # destinations already handed out

  for entry in entries:
    source = _entry_source(entry)
    scope = entry.get("scope", DEFAULT_SCOPE)

    known = index_of.get(source)
    if known is not None:
      if known["scope"] != scope:
        known["scope"] = DEFAULT_SCOPE
      continue

    name = os.path.basename(source)
    root, extension = os.path.splitext(name)
    candidate = name
    suffix = 2
    while candidate in taken:
      candidate = root + "_" + str(suffix) + extension
      suffix += 1
    taken.add(candidate)

    known = {
      "source": source,
      "scope": scope,
      "dest": hard_settings.work_constraint_path + "/" + candidate,
    }
    index_of[source] = known
    resolved.append(known)

  return resolved


def for_scope(entries, scope):
  """The destinations of the entries a given stage reads, in declaration order."""
  return [
    entry["dest"] for entry in (entries or [])
    if entry.get("scope") in (scope, DEFAULT_SCOPE)
  ]


def copy_constraint_files(arch):
  """
  Copy the constraint files of a job into its work directory.

  Copying rather than pointing at the originals is what the rest of the work
  directory does, and what makes a job re-runnable on its own after the fact,
  whatever happened to the sources in between.

  Returns:
    bool: True on success. On failure the error is printed and False returned,
      so the caller can give up on this job the way it does for the other copies.
  """
  entries = getattr(arch, "constraint_files", None)
  if not entries:
    return True

  for entry in entries:
    destination = os.path.join(arch.tmp_dir, *entry["dest"].split("/"))
    try:
      directory = os.path.dirname(destination)
      if directory and not os.path.isdir(directory):
        os.makedirs(directory)
      shutil.copy2(entry["source"], destination)
    except Exception as e:
      printc.error(
        'Could not copy constraint file "' + entry["source"] + '" to "'
        + os.path.realpath(destination) + '"',
        script_name,
      )
      printc.cyan("error details: ", end="", script_name=script_name)
      print(str(e))
      return False

  return True

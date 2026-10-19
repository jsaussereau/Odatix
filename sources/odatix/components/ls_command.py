# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
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
"odatix ls": what the workspace holds, its architectures, simulations and
workflows (and their configurations with -a), as "odatix ps" lists its
sessions.
"""

import fnmatch
import json
import shutil

import odatix.lib.printc as printc
from odatix.workspace import open_workspace, WorkspaceError

#: The kinds "odatix ls" lists, in order: (option dest, title, collection).
KINDS = (
  ("architectures", "Architectures", "architectures"),
  ("simulations", "Simulations", "simulations"),
  ("workflows", "Workflows", "workflows"),
)


def add_arguments(parser):
  parser.add_argument("patterns", nargs="*", metavar="PATTERN", help='only the entries whose name matches one of these patterns, e.g. "Example_*" (shell-style wildcards)')
  parser.add_argument("-l", "--long", action="store_true", help="one name per line (default: names in columns, as unix ls)")
  parser.add_argument("-a", "--all", action="store_true", help="also list the configurations of each entry, domain by domain")
  parser.add_argument("--arch", dest="architectures", action="store_true", help="list the architectures (default: architectures, simulations and workflows)")
  parser.add_argument("-s", "--sim", dest="simulations", action="store_true", help="list the simulations")
  parser.add_argument("-W", "--workflow", dest="workflows", action="store_true", help="list the workflows")
  parser.add_argument("--json", action="store_true", help="print the list as JSON")


def matches(name, patterns):
  return not patterns or any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def configurations(entry):
  """
  The configurations of an entry, as {domain label: [names]}, for the domains
  that substitute parameters. Simulations have no domains of their own here:
  they run on the configurations of their architectures.
  """
  domains = getattr(entry, "domains", None)
  if domains is None or not hasattr(domains, "main") or not hasattr(domains.main, "configuration_names"):
    return {}
  result = {}
  for domain in domains:
    if not domain.use_parameters:
      continue
    result[domain.label] = list(domain.configuration_names())
  return result


def collect(workspace, kinds, patterns, with_configurations):
  """{collection: [{"name": ..., "configurations": {...}}]} for the kinds asked."""
  listing = {}
  for dest, _title, collection in KINDS:
    if dest not in kinds:
      continue
    entries = []
    for entry in getattr(workspace, collection):
      if not matches(entry.name, patterns):
        continue
      item = {"name": entry.name}
      if with_configurations:
        item["configurations"] = configurations(entry)
      entries.append(item)
    listing[collection] = entries
  return listing


def columns(names, indent):
  """
  The names in columns across the terminal, filled down then across, each
  column as wide as its longest name, as unix ls does: the fewest rows whose
  columns fit in the width.
  """
  if not names:
    return []
  width = shutil.get_terminal_size((80, 24)).columns - len(indent)
  gap = 2
  for rows in range(1, len(names) + 1):
    cols = [names[i:i + rows] for i in range(0, len(names), rows)]
    widths = [max(len(name) for name in col) for col in cols]
    if sum(widths) + gap * (len(cols) - 1) <= width:
      break
  lines = []
  for row in range(rows):
    cells = [(col[row], w) for col, w in zip(cols, widths) if row < len(col)]
    line = "".join(name.ljust(w + gap) for name, w in cells[:-1]) + cells[-1][0]
    lines.append(indent + line)
  return lines


def print_names(names, indent, long_format):
  for line in (["{}{}".format(indent, name) for name in names] if long_format else columns(names, indent)):
    print(line)


def print_listing(listing, long_format=False):
  first = True
  for _dest, title, collection in KINDS:
    if collection not in listing:
      continue
    if not first:
      print()
    first = False
    entries = listing[collection]
    printc.bold("{} ({})".format(title, len(entries)))
    if not entries:
      printc.grey("  none")
    if not any(item.get("configurations") for item in entries):
      print_names([item["name"] for item in entries], "  ", long_format)
      continue
    for item in entries:
      print("  " + item["name"])
      for label, names in item["configurations"].items():
        # The main domain's configurations right under the entry, those of
        # each other domain under its name, as "-a MyCPU + width/16bits" reads.
        indent = "    "
        if label != item["name"]:
          printc.grey(indent + "+ " + label)
          indent += "  "
        print_names(names, indent, long_format)


def main(args):
  try:
    workspace = open_workspace(".", required=True)
  except WorkspaceError as e:
    printc.error(str(e), "odatix ls")
    return False

  asked = {
    "architectures": args.architectures,
    "simulations": args.simulations,
    "workflows": args.workflows,
  }
  kinds = [dest for dest, _title, _collection in KINDS if asked[dest]]
  if not kinds:
    kinds = [dest for dest, _title, _collection in KINDS]

  try:
    listing = collect(workspace, kinds, args.patterns, args.all)
  except WorkspaceError as e:
    printc.error(str(e), "odatix ls")
    return False

  if args.json:
    print(json.dumps(listing, indent=2))
  else:
    print_listing(listing, args.long)
  return True

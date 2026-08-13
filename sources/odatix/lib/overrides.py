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
Settings a file applies to some of its jobs only.

A settings file says most things once, for every job it produces. What it has
to say for a part of them goes in its "overrides" section: an ordered list of
rules, each saying *which* jobs it applies to and *what* it changes about them.

    overrides:
      - targets: xc7a100t-csg324-1
        fmax_synthesis:
          upper_bound: 600

      - tools: vivado
        targets: [xc7a100t-*, xc7k70t-*]
        constraints:
          - pinout.xdc @ pnr

      - tools: vivado@power_opt
        configurations: "*bits"
        custom_freq_synthesis:
          list: [50, 100]

A rule selects jobs on four axes: the tool that runs them ("tools"), the
synthesis target ("targets"), and the configuration ("configurations"). Each
selector takes one name, a list of names, or shell-style patterns ("xc7a*"), and
a selector a rule does not name is not restricted: a rule with no selector at
all applies to every job, which is the same as saying it at the top level.

A flow is named after the tool it belongs to, the way a work directory names it:
"vivado" matches every flow of Vivado, "vivado@power_opt" only that one, and
"*@power_opt" that flow of whichever tool declares it.

Rules apply in file order, on top of what the file says at its top level: the
last rule that matches a job has the last word on the keys it names, and says
nothing about the keys it does not. Two exceptions, which are what the keys
mean rather than a special case of the ordering:

  * "constraints" add up. A design does not stop needing its timing exceptions
    because the board it runs on has a pinout, so every matching rule's files
    are read, in order, after the ones declared at the top level.
  * a frequency list can ask to be added to the one of the level above it,
    with "list_append", instead of replacing it.

This section replaces the per target sections settings files used to have. What
used to be written under "targets/<target>" is a rule selecting that target, and
what was written a level below it, for one configuration of that target, is a
rule selecting both.
"""

import fnmatch

__all__ = [
    "OVERRIDES_KEY",
    "SELECTORS",
    "OverrideError",
    "matches",
    "select",
    "blocks",
    "resolve",
    "describe",
]

#: Key holding the rules in a settings file.
OVERRIDES_KEY = "overrides"

#: The selector of a rule, by the axis it restricts. The values are what
#: :func:`matches` is given for that axis.
SELECTORS = ("tools", "targets", "configurations")

#: Separator between a tool and one of its flows, in a "tools" selector. The
#: same one work directories are named with ("vivado@power_opt").
FLOW_SEPARATOR = "@"


class OverrideError(Exception):
    """An "overrides" section Odatix cannot build a job from."""


######################################
# Matching
######################################

def _patterns(value, key, where):
  """The patterns of one selector, or None when it restricts nothing."""
  if value is None:
    return None
  if isinstance(value, str):
    value = [value]
  if not isinstance(value, (list, tuple)):
    raise OverrideError(
      'Selector "' + key + '" of an override in "' + where + '" is of type "'
      + value.__class__.__name__ + '" while it should be a name or a list of names.'
    )
  patterns = []
  for item in value:
    if not isinstance(item, str):
      raise OverrideError(
        'Selector "' + key + '" of an override in "' + where + '" holds a "'
        + item.__class__.__name__ + '" while it should hold names.'
      )
    item = item.strip()
    if item:
      patterns.append(item)
  # An empty selector, or one holding only "*", restricts nothing.
  if not patterns or all(pattern == "*" for pattern in patterns):
    return None
  return patterns


def _matches_name(patterns, value):
  if patterns is None:
    return True
  value = value or ""
  return any(fnmatch.fnmatchcase(value, pattern) for pattern in patterns)


def _matches_tool(patterns, tool, flow):
  """
  Whether a "tools" selector covers a tool, or one of its flows.

  A pattern without a flow matches the tool whatever it runs; one with a flow
  has to match both halves.
  """
  if patterns is None:
    return True
  tool = tool or ""
  flow = flow or ""
  for pattern in patterns:
    tool_pattern, separator, flow_pattern = pattern.partition(FLOW_SEPARATOR)
    if not fnmatch.fnmatchcase(tool, tool_pattern.strip()):
      continue
    if not separator or fnmatch.fnmatchcase(flow, flow_pattern.strip()):
      return True
  return False


def matches(rule, tool="", flow="", target="", configuration="", where=""):
  """
  Whether one rule applies to a job.

  Args:
    rule (dict): the rule, selectors included.
    tool (str): the EDA tool running the job, "" when it has none.
    flow (str): the flow of that tool the job runs.
    target (str): the synthesis target.
    configuration (str): the configuration.
    where (str): the file the rule comes from, for error messages.

  Raises:
    OverrideError: on a selector Odatix cannot read.
  """
  if not isinstance(rule, dict):
    raise OverrideError(
      'An override in "' + where + '" is of type "' + rule.__class__.__name__
      + '" while it should be a list of settings.'
    )
  if not _matches_tool(_patterns(rule.get("tools"), "tools", where), tool, flow):
    return False
  if not _matches_name(_patterns(rule.get("targets"), "targets", where), target):
    return False
  if not _matches_name(_patterns(rule.get("configurations"), "configurations", where), configuration):
    return False
  return True


######################################
# Reading a section
######################################

def rules(data, where=""):
  """
  The rules of a settings mapping, in file order.

  Raises:
    OverrideError: when the section is not a list of rules.
  """
  if not isinstance(data, dict):
    return []
  declaration = data.get(OVERRIDES_KEY)
  if declaration is None:
    return []
  if isinstance(declaration, dict):
    declaration = [declaration]
  if not isinstance(declaration, list):
    raise OverrideError(
      'Key "' + OVERRIDES_KEY + '" in "' + where + '" is of type "'
      + declaration.__class__.__name__ + '" while it should be a list of overrides.'
    )
  for rule in declaration:
    if not isinstance(rule, dict):
      raise OverrideError(
        'An override in "' + where + '" is of type "' + rule.__class__.__name__
        + '" while it should be a list of settings.'
      )
  return declaration


def select(data, tool="", flow="", target="", configuration="", where=""):
  """
  What the rules matching a job say, in file order.

  Returns:
    list: one mapping per matching rule, its selectors taken out, so that what
      is left is only settings.
  """
  selected = []
  for rule in rules(data, where):
    if matches(rule, tool=tool, flow=flow, target=target, configuration=configuration, where=where):
      selected.append({key: value for key, value in rule.items() if key not in SELECTORS})
  return selected


def blocks(data, key, tool="", flow="", target="", configuration="", where=""):
  """
  What a job gets for one key, from the most specific level to the most
  general: the last matching rule first, the top level of the file last.

  Levels that say nothing about the key are left out, so an empty result means
  the file never mentions it for this job.
  """
  levels = select(data, tool=tool, flow=flow, target=target, configuration=configuration, where=where)
  levels.reverse()
  levels.append(data if isinstance(data, dict) else {})
  return [level[key] for level in levels if isinstance(level, dict) and key in level]


def resolve(data, tool="", flow="", target="", configuration="", where=""):
  """
  The settings of a job: the top level of the file with every matching rule
  applied to it, in order.

  A key holding a mapping is merged key by key, so that a rule changing one
  bound of a frequency range keeps the other. Anything else is replaced.

  "constraints" is not merged here: what every level declares is read, which
  :func:`odatix.lib.constraint_files.read_constraints` is given level by level.
  """
  resolved = dict(data) if isinstance(data, dict) else {}
  resolved.pop(OVERRIDES_KEY, None)

  for rule in select(data, tool=tool, flow=flow, target=target, configuration=configuration, where=where):
    for key, value in rule.items():
      if isinstance(value, dict) and isinstance(resolved.get(key), dict):
        merged = dict(resolved[key])
        merged.update(value)
        resolved[key] = merged
      else:
        resolved[key] = value
  return resolved


def describe(rule):
  """
  A rule's selectors, as the one line a message or a form header shows.

  "Every job" when it restricts nothing.
  """
  parts = []
  for key in SELECTORS:
    value = rule.get(key) if isinstance(rule, dict) else None
    if value is None:
      continue
    if isinstance(value, str):
      value = [value]
    names = [str(item).strip() for item in value if str(item).strip()]
    if names and not all(name == "*" for name in names):
      parts.append(key + ": " + ", ".join(names))
  return " | ".join(parts) if parts else "Every job"

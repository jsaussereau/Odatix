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
The architectures a simulation runs on, and what it does differently for each.

A testbench is written for a design, or for a handful of designs sharing an
interface. Which ones they are, and what the simulation changes for each of
them, is the "architectures" block of "<simulation>/_settings.yml"::

    architectures:
      - Example_Cordic_sv:
          param_domains:
            width:
              param_target_file: "tb/tb_cordic.sv"
            width:                            # the same domain, substituted a second time
              combine: both                   # the architecture's substitution still applies
              param_target_file: "tb/tb_top.sv"
              param_dir: "tb_params"          # one configuration per value of the domain
          metrics_file: "_metrics_sv.yml"

      - Example_Cordic_vhdl        # runs on it, nothing to change

What a "param_domains" entry substitutes is said either with "param_file" (the
same parameters whichever configuration of the domain runs) or with "param_dir",
a directory of the simulation holding one configuration per value of the domain
-- ".txt" files, rules in its own "_settings.yml", or both, exactly like the
configurations of a parameter domain of an architecture. Both together make
"param_file" the default of the domain: the values the directory does not
describe fall back to it.

An entry named after a domain the architecture already has customizes what that
domain substitutes. "combine" says how: "replace" (the default) means only the
substitution described here is done, in place of the architecture's, while
"both" leaves the architecture's substitution alone and does a second one -- the
same domain written into the testbench as well as into the design, each with its
own target file, delimiters and parameters, anything unsaid being inherited from
the architecture's domain.

An architecture that is listed with nothing under it is simply an architecture
the simulation is meant to run on. Listing them is an indication, not a
restriction: running a simulation on an architecture it does not list works, and
only warns.

Names accept wildcards ("*" matching every architecture), and the entries that
match the design under test are applied in the order they are written, so a
specific architecture placed after a wildcard refines it.

Nothing here prints: what a user should be told comes back as
:class:`odatix.workspace.selection.Message` objects, the way selections already
report, so the command line, the graphical interface and scripts each say it
their own way.
"""

import fnmatch
import os

import odatix.workspace.space as space
from odatix.workspace.selection import Message

__all__ = [
    "ARCHITECTURES_KEY",
    "ARCH_SETTING_KEYS",
    "ArchitectureEntry",
    "parse",
    "names",
    "settings_for",
    "to_yaml",
    "COMBINE_REPLACE",
    "COMBINE_BOTH",
    "COMBINE_MODES",
    "DOMAIN_SETTING_KEYS",
    "combine_mode",
    "resolve_param_file",
]


# Key of a simulation settings file the block is written under.
ARCHITECTURES_KEY = "architectures"

# What an architecture entry may hold besides the architecture name. Anything
# else under an entry is kept as it is, so a settings file is never truncated by
# a version of Odatix that does not know a key yet.
ARCH_SETTING_KEYS = ("param_domains", "metrics_file")

#: What one entry of "param_domains" may hold. Anything else is left untouched,
#: for the same reason as ARCH_SETTING_KEYS.
DOMAIN_SETTING_KEYS = (
    "use_parameters",
    "param_target_file",
    "start_delimiter",
    "stop_delimiter",
    "param_file",
    "param_dir",
    "domain_value",
    "combine",
)

#: Only the substitution the simulation describes is done, in place of the one
#: the architecture's domain describes.
COMBINE_REPLACE = "replace"

#: The architecture's substitution is done as usual, and the one the simulation
#: describes is done as well: the same domain substituted in two places.
COMBINE_BOTH = "both"

#: What "both" used to be called, when it meant appending to the same
#: substitution. Still read, so settings files written then keep working.
COMBINE_ALIASES = {"append": COMBINE_BOTH, "add": COMBINE_BOTH}

COMBINE_MODES = (COMBINE_REPLACE, COMBINE_BOTH)


def combine_mode(overrides):
    """
    How one "param_domains" entry combines with what the architecture's domain
    of the same name already substitutes: :data:`COMBINE_REPLACE` (the default,
    the simulation's substitution instead of the architecture's) or
    :data:`COMBINE_BOTH` (both substitutions done).

    An unknown value falls back to replacing, which is what every simulation
    written before this did.
    """
    if not isinstance(overrides, dict):
        return COMBINE_REPLACE
    value = str(overrides.get("combine", "") or "").strip().lower()
    value = COMBINE_ALIASES.get(value, value)
    return value if value in COMBINE_MODES else COMBINE_REPLACE


def resolve_param_file(overrides, sim_dir, domain_value="", messages=None, where=""):
    """
    The file holding the parameters one "param_domains" entry substitutes.

    A simulation says it two ways:

    - ``param_file``, one file substituted whichever configuration of the domain
      runs;
    - ``param_dir``, a directory of the simulation holding one configuration per
      value of the domain -- written as ".txt" files, described by rules in its
      own "_settings.yml", or both, exactly like the configurations of a
      parameter domain of an architecture.

    Given both, the directory is looked up first and ``param_file`` is the
    default: the configurations the directory does not describe fall back to it,
    instead of being an error.

    Args:
        overrides (dict): what the entry holds.
        sim_dir (str): directory of the simulation, the paths are relative to.
        domain_value (str): the configuration of the domain being run, which is
            what a "param_dir" is looked up by.
        messages (list): filled with what the user should be told about it.
        where (str): how to name the entry in those messages.

    Returns:
        str: path of the file, or None when the entry names none (or names one
        that does not exist, a message then saying so).
    """
    messages = messages if messages is not None else []
    where = where or '"param_domains"'

    if not isinstance(overrides, dict):
        return None

    param_file = str(overrides.get("param_file", "") or "")
    param_dir = str(overrides.get("param_dir", "") or "")

    # The default the directory falls back to, resolved first so a missing file
    # is reported whether or not the directory ends up covering the
    # configuration being run.
    default_path = None
    if param_file:
        default_path = os.path.join(sim_dir, param_file)
        if not os.path.isfile(default_path):
            messages.append(Message("error", 'There is no parameter file "' + default_path + '", referenced by ' + where))
            return None

    if not param_dir:
        return default_path

    directory = os.path.join(sim_dir, param_dir)
    if not os.path.isdir(directory):
        if default_path is not None:
            return default_path
        messages.append(Message("error", 'There is no parameter directory "' + directory + '", referenced by ' + where))
        return None

    if not domain_value:
        if default_path is not None:
            return default_path
        messages.append(Message(
            "error",
            where + ' holds a "param_dir" but the domain has no configuration to look up in it',
            ['Give "param_file" instead, or "domain_value" to name the configuration to run'],
        ))
        return None

    # Files and rules alike, resolved on the fly: nothing has to be generated
    # beforehand, the same way an architecture's configurations are read.
    path = space.config_file(directory, domain_value)
    if path is None:
        # A "param_file" given alongside is the default of the domain: the
        # configurations the directory does not describe use it.
        if default_path is not None:
            return default_path
        known = space.resolved_names(directory)
        messages.append(Message(
            "error",
            'There is no configuration "' + domain_value + '" in "' + directory + '", referenced by ' + where,
            ['This directory holds: ' + (", ".join(known) if known else "nothing")],
        ))
        return None
    return path


class ArchitectureEntry(object):
    """One architecture a simulation runs on, and what it changes for it."""

    def __init__(self, name, settings=None):
        self.name = str(name)
        self.settings = dict(settings) if isinstance(settings, dict) else {}

    @property
    def param_domains(self):
        value = self.settings.get("param_domains")
        return value if isinstance(value, dict) else {}

    @property
    def metrics_file(self):
        value = self.settings.get("metrics_file")
        return str(value) if value not in (None, "") else ""

    def __repr__(self):
        return "<ArchitectureEntry {0!r} {1!r}>".format(self.name, self.settings)


def _entry_from_mapping(mapping, messages, where):
    """
    Read one architecture entry written as a mapping.

    Both of these say the same thing, the second being what YAML makes of an
    entry whose keys are written at the same indentation as its name::

        - Example_Cordic_sv:
            param_domains: {...}

        - Example_Cordic_sv:
          param_domains: {...}

    The first is a name whose value holds the settings, the second a name with
    no value next to the settings themselves. Both are accepted, since the
    difference is one space and no one would expect it to matter.
    """
    entries = []
    loose = {}
    named = []

    for key, value in mapping.items():
        if str(key) in ARCH_SETTING_KEYS:
            loose[str(key)] = value
        else:
            named.append((str(key), value))

    if not named:
        messages.append(Message(
            "error",
            where + " does not name an architecture",
            ['An entry of "' + ARCHITECTURES_KEY + '" is an architecture name, '
             'optionally followed by what the simulation changes for it'],
        ))
        return entries

    if len(named) > 1 and loose:
        messages.append(Message(
            "error",
            where + ' names several architectures ("' + '", "'.join(name for name, _ in named)
            + '") and cannot tell which one "' + '", "'.join(sorted(loose)) + '" belongs to',
        ))
        return entries

    for name, value in named:
        settings = {}
        if isinstance(value, dict):
            settings.update(value)
        elif value not in (None, ""):
            messages.append(Message(
                "error",
                where + ': "' + name + '" must hold a mapping of settings, or nothing at all',
            ))
            continue
        settings.update(loose)
        entries.append(ArchitectureEntry(name, settings))

    return entries


def parse(value, messages=None, where=""):
    """
    Read the "architectures" block of a simulation settings file.

    Accepts a list of names, a list of mappings, a mapping of name to settings,
    or a single name. Returns the entries in the order they are written, which
    is the order they are applied in.

    Args:
        value: what the settings file holds under "architectures".
        messages (list): filled with what the user should be told about it.
        where (str): how to name the block in those messages.

    Returns:
        list: the :class:`ArchitectureEntry` objects it stands for.
    """
    messages = messages if messages is not None else []
    where = where or '"' + ARCHITECTURES_KEY + '"'

    if value in (None, "", [], {}):
        return []

    if isinstance(value, str):
        return [ArchitectureEntry(value)]

    if isinstance(value, dict):
        return _entry_from_mapping(value, messages, where)

    if not isinstance(value, list):
        messages.append(Message(
            "error", where + " must be a list of architectures",
        ))
        return []

    entries = []
    for item in value:
        if item in (None, ""):
            continue
        if isinstance(item, str):
            entries.append(ArchitectureEntry(item))
        elif isinstance(item, dict):
            entries.extend(_entry_from_mapping(item, messages, where))
        else:
            messages.append(Message(
                "error",
                where + ": " + repr(item) + " is not an architecture name",
            ))
    return entries


def names(entries):
    """The architecture names (or patterns) the entries list, in order."""
    return [entry.name for entry in entries]


def _merge_param_domains(into, added):
    """Merge one entry's parameter domain overrides into what matched before."""
    for domain, overrides in (added or {}).items():
        if not isinstance(overrides, dict):
            into[str(domain)] = overrides
            continue
        merged = dict(into.get(str(domain)) or {})
        merged.update(overrides)
        into[str(domain)] = merged


def settings_for(entries, arch):
    """
    What a simulation changes for one architecture.

    Every entry whose name matches (wildcards included) contributes, in the
    order they are written: a later entry overrides what an earlier one said,
    key by key, and parameter domains merge domain by domain -- so a wildcard
    entry can set what every architecture shares and a named one refine it.

    Args:
        entries (list): what :func:`parse` returned.
        arch (str): the architecture under test.

    Returns:
        dict: the settings that apply to it, empty when nothing matches.
    """
    settings = {}
    for entry in entries:
        if not fnmatch.fnmatch(str(arch), entry.name):
            continue
        for key, value in entry.settings.items():
            if key == "param_domains" and isinstance(value, dict):
                _merge_param_domains(settings.setdefault("param_domains", {}), value)
            else:
                settings[key] = value
    return settings


def matches(entries, arch):
    """Whether an architecture is one the entries list."""
    return any(fnmatch.fnmatch(str(arch), entry.name) for entry in entries)


def to_yaml(entries):
    """
    Turn entries back into what is written in the settings file.

    An architecture with nothing to change is written as its bare name, so a
    simulation that only lists what it runs on stays a plain list of names.
    """
    written = []
    for entry in entries:
        settings = {
            key: value for key, value in entry.settings.items()
            if value not in (None, "", {}, [])
        }
        written.append({entry.name: settings} if settings else entry.name)
    return written

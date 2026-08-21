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
            width:                            # every substitution of "width"
              - param_target_file: "tb/tb_cordic.sv"
              - param_target_file: "Makefile" # the same domain, written elsewhere too
                start_delimiter: "# ODATIX PARAMS START"
                stop_delimiter: "# ODATIX PARAMS STOP"
                param_dir: "make_params"      # one configuration per value of the domain
          metrics_file: "_metrics_sv.yml"

      - Example_Cordic_vhdl        # runs on it, nothing to change

The value of a domain is the list of the substitutions this simulation does for
it: one value of a parameter domain has consequences in as many files as it
takes -- a testbench, a Makefile, a wrapper -- each written with its own target
file, delimiters and parameters. A single substitution may be written as the
mapping itself, without the list, which is the same thing (see
:func:`substitutions`).

What a substitution writes is said either with "param_file" (the same parameters
whichever configuration of the domain runs) or with "param_dir", a directory of
the simulation holding one configuration per value of the domain -- ".txt"
files, rules in its own "_settings.yml", or both, exactly like the
configurations of a parameter domain of an architecture. Both together make
"param_file" the default of the domain: the values the directory does not
describe fall back to it.

Where a "param_dir" is given, that directory also says how its parameters are
written -- "use_parameters", "param_target_file", "start_delimiter" and
"stop_delimiter" in its own "_settings.yml", the way a parameter domain of an
architecture says them -- and the substitution is left with what points at it.
The same keys written in the substitution itself are still read, and still win
(see :func:`domain_settings`).

A domain the architecture already has is customized rather than declared: every
substitution listed inherits from the architecture's domain whatever it does not
say. "combine" says what becomes of the architecture's own substitution:
"replace" does this one in its place, "both" leaves it alone and does this one
as well. Unwritten, the first substitution of the list replaces and the ones
after it are added, which is what listing several of them means.

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

import odatix.lib.hard_settings as hard_settings
import odatix.workspace.selectors as selectors
import odatix.workspace.space as space
from odatix.workspace.selection import Message
from odatix.workspace.yaml_io import read_yaml

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
    "DIRECTORY_SETTING_KEYS",
    "domain_settings",
    "substitutions",
    "domain_number",
]


# Key of a simulation settings file the block is written under.
ARCHITECTURES_KEY = "architectures"

# What an architecture entry may hold besides the architecture name. Anything
# else under an entry is kept as it is, so a settings file is never truncated by
# a version of Odatix that does not know a key yet.
ARCH_SETTING_KEYS = ("param_domains", "metrics_file")

#: What one substitution of "param_domains" may hold. Anything else is left untouched,
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

#: Other ways of saying "both", so that the obvious word works.
COMBINE_ALIASES = {"append": COMBINE_BOTH, "add": COMBINE_BOTH}

COMBINE_MODES = (COMBINE_REPLACE, COMBINE_BOTH)


#: What a "param_dir" says about the substitution in its own "_settings.yml",
#: instead of in the entry pointing at it. A directory of configurations
#: describes how its parameters are written the way an architecture's parameter
#: domain does, so the same keys are read from the same file, and the entry is
#: left with what points at it ("param_dir", "param_file", "combine",
#: "domain_value").
DIRECTORY_SETTING_KEYS = (
    "use_parameters",
    "param_target_file",
    "start_delimiter",
    "stop_delimiter",
)


def directory_settings(param_dir, sim_dir):
    """
    What the "_settings.yml" of a "param_dir" says about the substitution: the
    keys of :data:`DIRECTORY_SETTING_KEYS` it actually holds, and nothing else.

    Only the keys written in the file are returned, so that "said nothing about
    it" stays different from "said the default", the way an entry's own keys
    already read.
    """
    if not param_dir or not sim_dir:
        return {}
    path = os.path.join(sim_dir, str(param_dir), hard_settings.param_settings_filename)
    data = read_yaml(path, default=None)
    if not isinstance(data, dict):
        return {}
    return dict((key, data[key]) for key in DIRECTORY_SETTING_KEYS if key in data)


def domain_settings(overrides, sim_dir):
    """
    The substitution one "param_domains" entry describes, wherever it is written.

    Where the entry points at a directory of configurations, that directory's
    own "_settings.yml" says how its parameters are written, so it is read
    first; what the entry itself still holds refines it, which is what the
    settings files written before this said everything with.
    """
    if not isinstance(overrides, dict):
        return {}
    settings = directory_settings(overrides.get("param_dir"), sim_dir)
    if not settings:
        return dict(overrides)
    settings.update(overrides)
    return settings


def substitutions(value):
    """
    The substitutions one domain of a "param_domains" block describes, in the
    order they are written.

    A domain's value is a list, one item per place its values are written -- a
    testbench, a Makefile, a wrapper. A single substitution may be written as
    the mapping itself, without the list, and means a list of one.

    Anything else (a name, a number, nothing at all) describes no substitution
    and yields an empty list, which the caller reports its own way.
    """
    if isinstance(value, dict):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, dict)]
    return []


def default_combine_mode(index):
    """
    What a substitution that does not say "combine" does with the
    architecture's own substitution of the domain, given its place in the list.

    The first one replaces it -- customizing a domain is what a simulation
    writes one substitution for -- and the ones after it are added, since
    listing several of them is asking for several substitutions, not for the
    last one only.
    """
    return COMBINE_REPLACE if index == 0 else COMBINE_BOTH


def combine_mode(overrides, index=0):
    """
    How one substitution combines with what the architecture's domain of the
    same name already substitutes: :data:`COMBINE_REPLACE` (the simulation's
    substitution instead of the architecture's) or :data:`COMBINE_BOTH` (both
    substitutions done).

    Unwritten (or written as something else than one of :data:`COMBINE_MODES`),
    it is :func:`default_combine_mode` of its place in the list.
    """
    if not isinstance(overrides, dict):
        return default_combine_mode(index)
    value = str(overrides.get("combine", "") or "").strip().lower()
    value = COMBINE_ALIASES.get(value, value)
    return value if value in COMBINE_MODES else default_combine_mode(index)


def domain_number(source):
    """
    What the configuration being substituted holds, as a selector reads it
    ("$value"): the single number of its parameter file, or None.

    ``source`` is the path of that file, its content, or a callable handing
    either back -- a run knows the path, the configuration editor knows the
    text, and neither should have to read a file a selector may never look at.
    """
    if callable(source):
        try:
            source = source()
        except Exception:
            return None
    if source is None:
        return None
    text = str(source)
    if os.path.isfile(text):
        try:
            with open(text, "r") as f:
                text = f.read()
        except Exception:
            return None
    return selectors.number_of(text)


def resolve_param_file(overrides, sim_dir, domain_value="", messages=None, where="", domain_content=None):
    """
    The file holding the parameters one "param_domains" entry substitutes.

    A simulation says it two ways:

    - ``param_file``, one file substituted whichever configuration of the domain
      runs;
    - ``param_dir``, a directory of the simulation holding one configuration per
      value of the domain -- written as ".txt" files, described by rules in its
      own "_settings.yml", or both, exactly like the configurations of a
      parameter domain of an architecture. That file may also name several
      configurations at once, under "match" (see
      :mod:`odatix.workspace.selectors`).

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
        domain_content: what that configuration substitutes -- a path, a text,
            or a callable handing one back (see :func:`domain_number`). Only
            read by a "match" block comparing "$value".

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

    # Files, rules and selectors alike, resolved on the fly: nothing has to be
    # generated beforehand, the same way an architecture's configurations are
    # read.
    path, _selector = space.matched_config_file(
        directory, domain_value,
        value=domain_number(domain_content),
        messages=messages,
    )
    if any(message.level == "error" for message in messages):
        return None
    if path is None:
        # A "param_file" given alongside is the default of the domain: the
        # configurations the directory does not describe use it.
        if default_path is not None:
            return default_path
        known = space.resolved_names(directory)
        messages.append(Message(
            "error",
            'There is no configuration "' + domain_value + '" in "' + directory + '", referenced by ' + where,
            [
                'This directory holds: ' + (", ".join(known) if known else "nothing"),
                'Its "' + hard_settings.param_settings_filename + '" may also name several configurations at '
                'once, under "' + selectors.MATCH_KEY + '" ("P*", "$value > 7", ...)',
            ],
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
    """
    Merge what one entry substitutes into what the entries before it did.

    A domain both of them describe with a single substitution is refined key by
    key, so that a wildcard entry can say what every architecture shares and a
    named one change one thing of it. As soon as either of them lists several
    substitutions there is no telling which refines which, so the later entry
    says the whole list, replacing what the earlier one held for that domain.
    """
    for domain, value in (added or {}).items():
        domain = str(domain)
        before = substitutions(into.get(domain))
        after = substitutions(value)
        if not after:
            into[domain] = value
        elif len(before) <= 1 and len(after) == 1:
            merged = dict(before[0]) if before else {}
            merged.update(after[0])
            into[domain] = merged
        else:
            into[domain] = [dict(item) for item in after]


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

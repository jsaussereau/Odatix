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
What a simulation substitutes for one architecture, as the configuration editor
shows it.

A simulation says, per architecture it runs on, what it does with the parameter
domains of that architecture: where their values are written, whether they are
written at all, and which configurations they take those values from (see
:mod:`odatix.workspace.sim_architectures`). Those are configurations like any
other, so they are edited where every other set of configurations is: the
configuration editor, opened on "?sim=<simulation>&arch=<architecture>".

One section is one substitution: a domain whose value has consequences in
several files (a testbench, the Makefile building it) is substituted several
times, and is shown once per substitution.

Only what points at them stays in the simulation's own settings file -- which
domain, which directory, which default parameter file, and whether the
architecture's own substitution still applies. How the parameters are written
(target file, delimiters, and whether they are written at all) is said in the
"_settings.yml" of the directory holding them, exactly like a parameter domain
of an architecture says it.
"""

import fnmatch

import odatix.lib.hard_settings as hard_settings
import odatix.workspace.sim_architectures as sim_architectures
from odatix.workspace.domains import ParameterDomain

#: Keys of a substitution that point at what it substitutes, and stay written
#: in the simulation's settings file.
ENTRY_KEYS = ("param_dir", "param_file", "combine", "domain_value")


######################################
# Reading
######################################

def find_entry(simulation, arch_name, index=None):
    """
    The architecture entry a URL names: ``(entries, position)``, the position
    being None when the simulation lists no such architecture.

    Two entries may name the same architecture (a wildcard refined by a named
    one, or the same design listed twice), so a position is accepted and used
    when it does name that architecture.
    """
    entries = simulation.architecture_entries
    if index is not None:
        try:
            index = int(index)
        except (TypeError, ValueError):
            index = None
    if index is not None and 0 <= index < len(entries) and entries[index].name == str(arch_name):
        return entries, index
    for position, entry in enumerate(entries):
        if entry.name == str(arch_name):
            return entries, position
    return entries, None


def param_domains_of(entry):
    """
    The substitutions one entry describes, in the order they are written:
    ``(domain name, overrides)``, one per substitution.

    A domain written in several places is several substitutions of the same
    name, and is shown as several sections, so the name is not what identifies
    one of them here.
    """
    domains = []
    for domain, value in (entry.param_domains or {}).items():
        for index, overrides in enumerate(sim_architectures.substitutions(value)):
            overrides = dict(overrides)
            # Unwritten, what a substitution does with the architecture's own
            # depends on its place in the list, which the section no longer
            # knows once it is shown on its own: settle it here, so the section
            # shows what actually happens and writes it back explicitly.
            overrides["combine"] = sim_architectures.combine_mode(overrides, index)
            domains.append((str(domain), overrides))
    return domains


def domain_directory(simulation, param_dir):
    """
    The directory of configurations a "param_dir" names, as a parameter domain:
    the same thing a domain of an architecture is, held by the simulation.

    None when the entry names no directory: a domain substituting one file
    whichever configuration runs has no configurations to edit.
    """
    param_dir = str(param_dir or "").strip()
    if not param_dir:
        return None
    return ParameterDomain(simulation, param_dir)


def domain_settings(simulation, overrides):
    """
    What one "param_domains" entry says about the substitution, wherever it is
    written: the settings of the directory it points at, refined by the keys the
    entry itself still holds (which is how it was all written before the
    directory said it).
    """
    param_dir = str((overrides or {}).get("param_dir", "") or "").strip()
    settings = {}
    domain = domain_directory(simulation, param_dir)
    if domain is not None and domain.exists:
        settings = domain.settings.to_dict()
    for key in sim_architectures.DIRECTORY_SETTING_KEYS:
        if key in (overrides or {}):
            settings[key] = overrides[key]
    return settings


######################################
# Writing
######################################

def entry_overrides(values, previous=None):
    """
    What one "param_domains" entry holds once the editor has saved it.

    Everything the entry carried that this page does not edit is kept, and the
    substitution keys are dropped as soon as a directory says them, so the same
    thing is never written in two places.
    """
    previous = dict(previous) if isinstance(previous, dict) else {}
    overrides = {
        key: value for key, value in previous.items()
        if key not in ENTRY_KEYS and key not in sim_architectures.DIRECTORY_SETTING_KEYS
    }

    param_dir = str(values.get("param_dir", "") or "").strip()
    param_file = str(values.get("param_file", "") or "").strip()
    if param_dir:
        overrides["param_dir"] = param_dir
    if param_file:
        overrides["param_file"] = param_file
    # Always written: which substitution of a domain replaces the architecture's
    # own is otherwise a matter of the order they are in, which the editor is
    # free to change.
    overrides["combine"] = sim_architectures.combine_mode(values)
    domain_value = str(previous.get("domain_value", "") or "").strip()
    if domain_value:
        overrides["domain_value"] = domain_value

    if not param_dir:
        # Nothing points at a directory, so there is no "_settings.yml" of its
        # own to say how the parameters are written: the entry keeps saying it.
        #
        # A key it never held and that says nothing (an empty file name, a
        # replacement left enabled) stays unwritten: saying nothing is what
        # leaves the architecture's own settings for that domain alone, and is
        # not the same as saying the default.
        for key in sim_architectures.DIRECTORY_SETTING_KEYS:
            if key in previous:
                overrides[key] = values.get(key, previous[key])
            elif key in values and values[key] not in ("", None, True):
                overrides[key] = values[key]
    return overrides


def _written_combine(overrides, index):
    """
    One substitution as it is written, with "combine" only where it says
    something the order does not already say: the first substitution of a domain
    takes the architecture's place and the ones after it are added, so that is
    what a file left without the key means.
    """
    overrides = dict(overrides)
    if overrides.get("combine") == sim_architectures.default_combine_mode(index):
        overrides.pop("combine", None)
    return overrides


def save_param_domains(simulation, position, domains):
    """
    Write the "param_domains" of one architecture entry back to the simulation's
    settings file.

    The sections of one domain are written as the list of its substitutions, in
    the order they are shown; a domain substituted in one place only is written
    as that substitution itself, which is the same thing and reads better.

    Args:
        simulation: the simulation being edited.
        position (int): which of its architecture entries is being written.
        domains (list): ``(domain name, overrides)`` in the order they are shown,
            one per substitution. A domain with no name is one being filled in,
            and is not written.
    """
    entries = simulation.architecture_entries
    if position is None or not (0 <= position < len(entries)):
        return simulation

    param_domains = {}
    for name, overrides in domains:
        name = str(name or "").strip()
        if not name:
            continue
        param_domains.setdefault(name, []).append(overrides)
    param_domains = {
        name: [_written_combine(overrides, index) for index, overrides in enumerate(written)]
        for name, written in param_domains.items()
    }
    param_domains = {
        name: written[0] if len(written) == 1 else written
        for name, written in param_domains.items()
    }

    settings = dict(entries[position].settings)
    if param_domains:
        settings["param_domains"] = param_domains
    else:
        settings.pop("param_domains", None)
    entries[position] = sim_architectures.ArchitectureEntry(entries[position].name, settings)

    simulation.settings.architectures = sim_architectures.to_yaml(entries)
    return simulation.save()


######################################
# The domains of the architecture
######################################

def architecture_domain_names(architectures, arch):
    """
    The parameter domains one architecture entry can override, the main one
    first. An entry naming several architectures at once (a wildcard) overrides
    the domains of all of them.
    """
    try:
        if arch and "*" not in arch and "?" not in arch:
            return architectures[arch].domains.names()
        names = []
        for name in sorted(architectures.names()):
            if arch and not fnmatch.fnmatch(name, arch):
                continue
            for domain in architectures[name].domains.names():
                if domain not in names:
                    names.append(domain)
        return names
    except Exception:
        return []


def domain_options(architectures, arch, current=""):
    """
    Options of the domain dropdown of a section: the domains the architecture
    defines, plus the one the entry already names when it defines it no longer
    (or never did -- a domain of the simulation's own).
    """
    names = architecture_domain_names(architectures, arch)
    options = [
        {
            "label": "Main parameter domain" if name == hard_settings.main_parameter_domain else name,
            "value": name,
        }
        for name in names
    ]
    if current and current not in names:
        options.append({"label": current, "value": current})
    return options


def new_domain_name(architectures, arch, used):
    """
    The domain a new section starts on: the first one of the architecture that
    is not overridden yet, falling back to a name of its own.
    """
    for name in architecture_domain_names(architectures, arch):
        if name not in used:
            return name
    base = "new_domain"
    suffix = 1
    while base + str(suffix) in used:
        suffix += 1
    return base + str(suffix)


def architecture_source_paths(architectures, arch):
    """
    Where the sources of the architecture(s) an entry names are read from.

    A simulation writes its parameters into one of its own files, but just as
    well into a file of the architecture under test: that RTL is copied next to
    the simulation before it runs (see
    :func:`odatix.components.run_common.resolve_sim_param_target_file`), so a
    target file is looked up here too. An architecture whose RTL is generated
    has no such file yet, but the design it is generated from is copied whole,
    so that is what is read instead.
    """
    paths = []
    try:
        names = (
            [arch] if arch and "*" not in arch and "?" not in arch
            else [name for name in sorted(architectures.names()) if not arch or fnmatch.fnmatch(name, arch)]
        )
    except Exception:
        return paths
    for name in names:
        try:
            settings = architectures[name].settings
        except Exception:
            continue
        path = settings.design_path if getattr(settings, "generate_rtl", False) else settings.rtl_path
        path = str(path or "").strip()
        if path and path not in paths:
            paths.append(path)
    return paths

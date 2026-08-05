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
The configurations of a parameter domain.

A configuration is a text file ("04bits.txt") holding the parameters that are
substituted into the design for one point of the sweep. They can be written by
hand, one file per configuration, or generated from a template and a set of
variables (see :class:`ConfigGeneration`), which is what the "generate"
command does.
"""

import os
from itertools import product

from natsort import natsorted
from ruamel.yaml.comments import CommentedMap

import odatix.lib.hard_settings as hard_settings
from odatix.workspace.entries import check_name
from odatix.workspace.errors import AlreadyExistsError, NotFoundError
from odatix.workspace.settings import Setting, Settings
from odatix.workspace.yaml_io import flow_seq

__all__ = [
    "Configuration",
    "ConfigurationCollection",
    "ConfigGeneration",
    "variable_definition",
    "configuration_names",
    "count_combinations",
    "combinations",
    "CONFIG_EXTENSION",
]

CONFIG_EXTENSION = ".txt"


def configuration_names(path):
    """
    The configurations held by a directory, without their extension, in natural
    order. A directory that does not exist holds none.
    """
    if not path or not os.path.isdir(path):
        return []
    return natsorted([
        entry[:-len(CONFIG_EXTENSION)]
        for entry in os.listdir(path)
        if entry.endswith(CONFIG_EXTENSION) and os.path.isfile(os.path.join(path, entry))
    ])


######################################
# Configuration files
######################################

class Configuration(object):
    """
    One configuration file of a parameter domain.

    The name never carries the ".txt" extension: that is a detail of how it is
    stored, and every other part of Odatix (job selections, result files, work
    directories) names a configuration without it.
    """

    kind = "configuration"

    def __init__(self, domain, name):
        self.domain = domain
        self.name = str(name)[:-len(CONFIG_EXTENSION)] if str(name).endswith(CONFIG_EXTENSION) else str(name)

    @property
    def filename(self):
        return self.name + CONFIG_EXTENSION

    @property
    def path(self):
        return os.path.join(self.domain.path, self.filename)

    @property
    def exists(self):
        return os.path.isfile(self.path)

    def require(self):
        if not self.exists:
            raise NotFoundError("No such configuration: '{0}'.".format(self.name))
        return self

    ######################################
    # Content
    ######################################

    def read(self):
        """The parameters held by this configuration, as text ("" when it does not exist)."""
        if not self.exists:
            return ""
        with open(self.path, "r") as f:
            return f.read()

    def write(self, content):
        """Replace the content of this configuration, creating it if needed."""
        os.makedirs(self.domain.path, exist_ok=True)
        with open(self.path, "w") as f:
            f.write("" if content is None else str(content))
        return self

    @property
    def content(self):
        return self.read()

    @content.setter
    def content(self, value):
        self.write(value)

    ######################################
    # Lifecycle
    ######################################

    def delete(self):
        if self.exists:
            os.remove(self.path)
        return self

    def rename(self, new_name):
        new_name = check_name(new_name, self.kind)
        target = Configuration(self.domain, new_name)
        if target.name == self.name:
            return self
        self.require()
        if target.exists:
            raise AlreadyExistsError("A configuration named '{0}' already exists.".format(target.name))
        os.rename(self.path, target.path)
        self.name = target.name
        return self

    def duplicate(self, new_name):
        target = Configuration(self.domain, check_name(new_name, self.kind))
        self.require()
        if target.exists:
            raise AlreadyExistsError("A configuration named '{0}' already exists.".format(target.name))
        return target.write(self.read())

    def __repr__(self):
        return "<Configuration {0!r}>".format(self.name)


class ConfigurationCollection(object):
    """The configurations of one parameter domain."""

    def __init__(self, domain):
        self.domain = domain

    @property
    def path(self):
        return self.domain.path

    def names(self):
        """Configuration names, without extension, in natural order."""
        return configuration_names(self.path)

    def filenames(self):
        """Configuration file names, extension included."""
        return [name + CONFIG_EXTENSION for name in self.names()]

    def __iter__(self):
        for name in self.names():
            yield Configuration(self.domain, name)

    def __len__(self):
        return len(self.names())

    def __contains__(self, item):
        name = item.name if isinstance(item, Configuration) else item
        return Configuration(self.domain, name).exists

    def __getitem__(self, name):
        return Configuration(self.domain, name).require()

    def get(self, name, default=None):
        configuration = Configuration(self.domain, name)
        return configuration if configuration.exists else default

    def exists(self, name):
        return Configuration(self.domain, name).exists

    def create(self, name, content=""):
        """Create a configuration file. Raises if one of that name already exists."""
        configuration = Configuration(self.domain, check_name(name, "configuration"))
        if configuration.exists:
            raise AlreadyExistsError("A configuration named '{0}' already exists.".format(configuration.name))
        return configuration.write(content)

    def write(self, name, content=""):
        """Create or replace a configuration file."""
        return Configuration(self.domain, name).write(content)

    def delete(self, name):
        """Delete a configuration. Deleting one that is already gone does nothing."""
        return Configuration(self.domain, name).delete()

    def rename(self, name, new_name):
        return self[name].rename(new_name)

    def duplicate(self, name, new_name):
        return self[name].duplicate(new_name)

    def clear(self):
        """Delete every configuration file of the domain."""
        for configuration in list(self):
            configuration.delete()

    def __repr__(self):
        return "<ConfigurationCollection {0}>".format(self.names())


######################################
# Configuration generation
######################################

class VariablesSetting(Setting):
    """
    The "variables" mapping of a generation block.

    A variable of type "list" holds its values inline ("list: [1, 2, 4]"), which
    is both how it reads best and how Odatix has always written it.
    """

    def dump(self, value):
        variables = CommentedMap()
        for name, definition in (value or {}).items():
            if isinstance(definition, dict):
                definition = CommentedMap(definition)
                settings = definition.get("settings")
                if definition.get("type") == "list" and isinstance(settings, dict) and "list" in settings:
                    settings = CommentedMap(settings)
                    settings["list"] = flow_seq(settings["list"])
                    definition["settings"] = settings
            variables[name] = definition
        return variables


class ConfigGeneration(Settings):
    """
    How the configurations of a domain are generated ("generate_configurations_settings").

    `template` is the text substituted into the design, `name` the name given to
    each generated configuration, both written with ``${variable}``
    placeholders; `variables` holds one definition per variable.
    """

    name = Setting("", type="str", doc="Name given to each generated configuration, e.g. \"${width}bits\".")
    # A template is usually a block of text, but a list of lines is accepted too
    # (the generator joins it), so it is taken as it comes.
    template = Setting("", type="any", doc="Text written in each generated configuration file.")
    variables = VariablesSetting(factory=dict, type="dict", doc="Definition of each variable, by name.")

    ######################################
    # Variables
    ######################################

    def set_variable(self, name, type, settings, format=None, group=None):
        """
        Declare a variable (replacing any declaration of the same name).

        Args:
            name (str): name used as ``${name}`` in the template and the
                configuration name.
            type (str): "range", "list" or "function".
            settings (dict): what that type needs, e.g. ``{"from": 1, "to": 8}``
                for a range, ``{"list": [1, 2, 4]}`` for a list.
            format (str): optional format applied to the values.
            group (str): optional pairing group. Variables sharing a group are
                zipped together (value by value) instead of being crossed.
        """
        definition = {"type": type, "settings": settings if settings is not None else {}}
        if format:
            definition["format"] = format
        if group:
            definition["group"] = group
        self.variables[str(name)] = definition
        return definition

    def remove_variable(self, name):
        self.variables.pop(name, None)

    def variable_names(self):
        return list(self.variables.keys())


def variable_definition(name, type, settings, format=None, group=None):
    """
    Build a single ``{name: definition}`` variable mapping, for callers that
    assemble a generation block themselves.
    """
    generation = ConfigGeneration()
    definition = generation.set_variable(name, type, settings, format=format, group=group)
    return {str(name): definition}


######################################
# Combinations
######################################

def count_combinations(domains_configs):
    """
    How many configurations the given ``{domain: [configuration, ...]}`` mapping
    amounts to, i.e. the size of the cross product of its domains.
    """
    if not domains_configs:
        return 0
    total = 1
    found = False
    for configurations in domains_configs.values():
        if configurations:
            total *= len(configurations)
            found = True
    return total if found else 0


def combinations(domains_configs, arch_name):
    """
    Expand a ``{domain: [configuration, ...]}`` mapping into the list of
    configuration combinations it stands for, each written the way a job
    selection names it ("<domain>/<configuration>", the main domain being named
    after the architecture itself).
    """
    if not domains_configs:
        return []

    domain_names = list(domains_configs.keys())
    config_lists = [domains_configs[domain] for domain in domain_names]

    expanded = []
    for combo in product(*config_lists):
        parts = []
        for domain, configuration in zip(domain_names, combo):
            display_domain = arch_name if domain == hard_settings.main_parameter_domain else domain
            parts.append("{0}/{1}".format(display_domain, configuration))

        if domain_names and domain_names[0] != hard_settings.main_parameter_domain:
            expanded.append([arch_name] + parts)
        else:
            expanded.append(parts)

    return expanded

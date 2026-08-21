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
Parameter domains.

A parameter domain is one axis of a sweep: a set of configurations that are
combined with the configurations of the other domains. Every architecture and
every workflow has a main domain, whose settings and configurations live in its
own directory, plus any number of named domains, one subdirectory each.

The main domain is not stored like the others (it shares the instance's
settings file), but it behaves like the others here, so code that walks the
domains of an instance does not have to special-case it.
"""

import os
import shutil

from natsort import natsorted

import odatix.lib.hard_settings as hard_settings
from odatix.lib.utils import copytree
from odatix.workspace.configs import (
    CONFIGURATIONS_KEY,
    LEGACY_CONFIGURATION_KEYS,
    ConfigGeneration,
    Configurations,
    ConfigurationsSetting,
    ConfigurationCollection,
    VariablesSetting,
    WithVariables,
)
from odatix.workspace.entries import check_name
from odatix.workspace.errors import AlreadyExistsError, InvalidNameError, NotFoundError
from odatix.workspace.settings import Setting, Settings, load_settings, save_settings
from odatix.workspace.space import ConfigSet, config_set_rules
from odatix.workspace.yaml_io import file_header

__all__ = ["MAIN_DOMAIN", "DomainSettings", "ParameterDomain", "ParameterDomainCollection"]

#: Name of the domain an instance carries itself, rather than in a subdirectory.
MAIN_DOMAIN = hard_settings.main_parameter_domain


######################################
# Settings
######################################

class DomainSettings(WithVariables, Settings):
    """
    Settings of a named parameter domain ("<instance>/<domain>/_settings.yml").

    A domain says where its parameters are written in the design, and how its
    configurations are built -- when they are not simply written by hand, one
    file each.
    """

    dropped_keys = LEGACY_CONFIGURATION_KEYS
    replacement_key = CONFIGURATIONS_KEY

    use_parameters = Setting(
        True, type="bool", style="yesno", section="Delimiters for parameter files",
        doc="Whether the configurations of this domain are substituted into a file at all.",
    )
    param_target_file = Setting(
        "", type="str",
        doc="File the parameters are written into, relative to the design directory.",
    )
    start_delimiter = Setting("", type="str", doc="Text after which the parameters are written. Escape sequences such as \\n are supported.")
    stop_delimiter = Setting("", type="str", doc="Text before which the parameters are written. Escape sequences such as \\n are supported.")

    configurations = ConfigurationsSetting(
        type=Configurations, section="Configurations", skip_if_empty=True,
        doc="Name and template the configurations of this domain are built from. "
            "A list declares several rule sets, whose union the domain is.",
    )

    match = Setting(
        factory=dict, type="dict", section="Matching", skip_if_empty=True,
        doc="Which configuration is substituted for the ones this directory does not "
            "hold, by selector: a name, a pattern (\"P*\"), a regular expression "
            "(\"/^M[0-9]+$/\") or a condition on \"$name\" and \"$value\" "
            "(\"$value > 7\"). See odatix.workspace.selectors.",
    )

    variables = VariablesSetting(
        factory=dict, type="dict", section="Variables", skip_if_empty=True,
        doc="Definition of each variable, by name. Variables are the values the "
            "configurations are built from. A domain with no template substitutes "
            "them as \"${name}\" into commands instead.",
    )

    # Read so that the files written before "configurations" existed keep
    # meaning what they meant. Never written again: see dropped_keys.
    generate_configurations = Setting(False, type="bool", style="yesno", stored=False)
    generate_configurations_settings = Setting(type=ConfigGeneration, stored=False)


######################################
# Domains
######################################

class ParameterDomain(object):
    """
    One parameter domain of an architecture or of a workflow.
    """

    kind = "parameter domain"

    def __init__(self, instance, name=MAIN_DOMAIN):
        self.instance = instance
        self.name = str(name)
        self._settings = None

    ######################################
    # Location
    ######################################

    @property
    def is_main(self):
        return self.name == MAIN_DOMAIN

    @property
    def path(self):
        """Directory holding the settings and the configurations of this domain."""
        if self.is_main:
            return self.instance.path
        return os.path.join(self.instance.path, self.name)

    @property
    def settings_path(self):
        return os.path.join(self.path, hard_settings.param_settings_filename)

    @property
    def exists(self):
        return os.path.isdir(self.path)

    def require(self):
        if not self.exists:
            raise NotFoundError(
                "No such parameter domain: '{0}' of '{1}'.".format(self.name, self.instance.name)
            )
        return self

    @property
    def label(self):
        """How the domain is named to a user: the instance's name for the main one."""
        return self.instance.name if self.is_main else self.name

    ######################################
    # Settings
    ######################################

    @property
    def settings_class(self):
        """
        The settings class of this domain: the instance's own for the main
        domain (an architecture's main settings file holds much more than a
        domain's), :class:`DomainSettings` for the others.
        """
        if self.is_main:
            return self.instance.settings_class
        return DomainSettings

    @property
    def settings(self):
        """
        The settings of this domain, read from file on first access and kept
        until :meth:`save` or :meth:`reload`.
        """
        if self._settings is None:
            self._settings = load_settings(self.settings_class, self.settings_path)
        return self._settings

    @settings.setter
    def settings(self, value):
        if isinstance(value, Settings):
            self._settings = value
        else:
            self._settings = self.settings_class.from_dict(value)

    def reload(self):
        """Forget the settings held in memory and read them from file again."""
        self._settings = None
        return self

    def save(self, regenerate=False):
        """
        Write the settings of this domain back to its file, keeping the comments
        and the keys Odatix does not know about.
        """
        os.makedirs(self.path, exist_ok=True)
        title = self.instance.name if self.is_main else "{0} - {1}".format(self.instance.name, self.name)
        save_settings(
            self.settings, self.settings_path,
            header=file_header("Settings for " + title), regenerate=regenerate,
        )
        return self

    def update(self, values=None, **kwargs):
        """Change some settings and write them back, in one call."""
        self.settings.update(values, **kwargs)
        return self.save()

    @property
    def use_parameters(self):
        """
        Whether this domain substitutes parameters into the design.

        A domain without a settings file substitutes nothing: there is nowhere
        for it to say where its parameters go.
        """
        if not os.path.isfile(self.settings_path):
            return False
        return bool(self.settings.use_parameters)

    ######################################
    # Configurations
    ######################################

    @property
    def configs(self):
        """The configurations of this domain."""
        return ConfigurationCollection(self)

    @property
    def config_set(self):
        """
        Everything this domain resolves to: what its rules describe, together
        with the configuration files it holds.

        Resolving is a computation, so what a domain holds can be asked for
        without anything having been generated first.

        A named domain says everything by declaring a single variable; the main
        one shares its settings file with the instance, whose variables may
        instead feed its commands, so there nothing is implied.
        """
        return ConfigSet(
            self.path,
            config_set_rules(
                self.settings.to_dict(), source=self.settings_path, implicit=not self.is_main
            ),
        )

    def resolve_configurations(self):
        """The configurations of this domain, rules and files together."""
        return self.config_set.resolve()

    def blacklisted_configurations(self):
        """Rule-produced configurations excluded from runs but shown by the editor."""
        return self.config_set.blacklisted()

    def configuration_names(self):
        """
        The names of the configurations of this domain, in natural order.

        What the rules describe counts, whether or not it was ever written to
        disk: a sweep is over what the domain holds, not over what happens to
        have been generated.
        """
        return self.config_set.names()

    @property
    def describes_configurations(self):
        """Whether this domain says how its configurations are built."""
        return self.config_set.space.generates

    def preview_configurations(self):
        """
        The configurations the rules of this domain describe, as a
        ``{name: content}`` mapping, without writing anything.

        Returns an empty mapping when the domain describes none, i.e. when its
        configurations are only the files it holds.
        """
        space = self.config_set.space
        if not space.valid:
            return {}
        return {point.name: point.content for point in space.points()}

    def generate_configurations(self, overwrite=False, clear=False, prune=False):
        """
        Write the configuration files this domain describes, and return the
        names written.

        Generating is no longer something to do before a run -- a run resolves
        what it needs on its own. It stays available for a workspace that would
        rather keep its configurations as files, to read them or to track them.

        Args:
            overwrite (bool): take a configuration that was edited by hand back
                to what its rule says. Without it, edits are left alone.
            clear (bool): delete every existing configuration first, so that
                only what the rules describe is left.
            prune (bool): delete what an earlier generation left behind and the
                rules no longer describe -- never a file written by hand.
        """
        return self.config_set.materialize(overwrite=overwrite, clear=clear, prune=prune)

    ######################################
    # Lifecycle
    ######################################

    def create(self):
        """Create the directory of this domain."""
        os.makedirs(self.path, exist_ok=True)
        return self

    def delete(self):
        """Delete this domain and its configurations. The main domain cannot be deleted."""
        if self.is_main:
            raise InvalidNameError("The main parameter domain cannot be deleted.")
        if os.path.isdir(self.path):
            shutil.rmtree(self.path)
        return self

    def rename(self, new_name):
        """Rename this domain. The main domain cannot be renamed."""
        if self.is_main:
            raise InvalidNameError("The main parameter domain cannot be renamed.")
        new_name = check_name(new_name, self.kind)
        if new_name == MAIN_DOMAIN:
            raise InvalidNameError("'{0}' is reserved for the main parameter domain.".format(MAIN_DOMAIN))
        if new_name == self.name:
            return self
        self.require()
        target = os.path.join(self.instance.path, new_name)
        if os.path.exists(target):
            raise AlreadyExistsError("A parameter domain named '{0}' already exists.".format(new_name))
        os.rename(self.path, target)
        self.name = new_name
        return self

    def duplicate(self, new_name, instance=None):
        """
        Copy this domain, under `instance` when given (so a domain can be copied
        from one architecture to another) or next to itself otherwise.

        Copying the main domain keeps only what a domain is made of: its
        configuration files and the settings a domain declares. The rest of an
        instance's main settings (its sources, its signals...) does not belong
        to a named domain.
        """
        instance = instance if instance is not None else self.instance
        new_name = check_name(new_name, self.kind)
        if new_name == MAIN_DOMAIN:
            raise InvalidNameError("Cannot duplicate to the main parameter domain.")
        if instance is self.instance and new_name == self.name:
            raise AlreadyExistsError("Source and target parameter domain are the same.")

        self.require()
        target = ParameterDomain(instance, new_name)
        if target.exists:
            raise AlreadyExistsError("A parameter domain named '{0}' already exists.".format(new_name))

        if self.is_main:
            os.makedirs(target.path, exist_ok=True)
            for item in os.listdir(self.path):
                source_item = os.path.join(self.path, item)
                if os.path.isdir(source_item) or item == hard_settings.param_settings_filename:
                    continue
                shutil.copyfile(source_item, os.path.join(target.path, item))
            settings = DomainSettings.from_dict(self.settings.to_dict())
            settings.extra.clear()
            target.settings = settings
            target.save()
        else:
            copytree(self.path, target.path)
        return target

    ######################################
    # Display
    ######################################

    def __repr__(self):
        return "<ParameterDomain {0!r} of {1!r}>".format(self.name, self.instance.name)

    def __eq__(self, other):
        return (
            isinstance(other, ParameterDomain)
            and self.name == other.name
            and os.path.abspath(self.instance.path) == os.path.abspath(other.instance.path)
        )

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __hash__(self):
        return hash((self.name, os.path.abspath(self.instance.path)))


class ParameterDomainCollection(object):
    """
    The parameter domains of an architecture or of a workflow.

    Iterating over it yields the main domain first, then the named ones in
    natural order. :meth:`sub_names` gives only the named ones, i.e. the
    subdirectories that exist on disk.
    """

    def __init__(self, instance):
        self.instance = instance

    @property
    def main(self):
        """The domain the instance carries itself."""
        return self._make(MAIN_DOMAIN)

    def _make(self, name):
        """
        The domain object of that name. The main one is the instance's own, so
        that ``instance.settings`` and ``instance.domains.main.settings`` are one
        and the same: editing one and saving the other must never lose changes.
        """
        if name == MAIN_DOMAIN:
            main = getattr(self.instance, "main_domain", None)
            if main is not None:
                return main
        return ParameterDomain(self.instance, name)

    def sub_names(self):
        """Names of the domains stored in a subdirectory, in natural order."""
        path = self.instance.path
        if not os.path.isdir(path):
            return []
        return natsorted([
            entry for entry in os.listdir(path)
            if os.path.isdir(os.path.join(path, entry))
            and not entry.startswith("_") and not entry.startswith(".")
        ])

    def names(self):
        """Names of every domain, the main one first."""
        return [MAIN_DOMAIN] + self.sub_names()

    def __iter__(self):
        for name in self.names():
            yield self._make(name)

    def __len__(self):
        return len(self.names())

    def __contains__(self, item):
        name = item.name if isinstance(item, ParameterDomain) else item
        return self.exists(name)

    def __getitem__(self, name):
        return self._make(name).require()

    def get(self, name, default=None):
        domain = self._make(name)
        return domain if domain.exists else default

    def entry(self, name):
        """The domain of that name, whether or not it exists yet."""
        return self._make(name)

    def exists(self, name):
        return self._make(name).exists

    def create(self, name, **settings):
        """Create a named parameter domain, and return it."""
        name = check_name(name, "parameter domain")
        if name == MAIN_DOMAIN:
            raise InvalidNameError("'{0}' is reserved for the main parameter domain.".format(MAIN_DOMAIN))
        domain = ParameterDomain(self.instance, name)
        if domain.exists:
            raise AlreadyExistsError("A parameter domain named '{0}' already exists.".format(name))
        domain.create()
        if settings:
            domain.update(settings)
        return domain

    def delete(self, name):
        """Delete a domain. Deleting one that is already gone does nothing."""
        return self._make(name).delete()

    def rename(self, name, new_name):
        return self[name].rename(new_name)

    def duplicate(self, name, new_name, instance=None):
        return self[name].duplicate(new_name, instance=instance)

    def configs(self):
        """The configurations of every domain, as a ``{domain: [name, ...]}`` mapping."""
        return dict((domain.name, domain.configs.names()) for domain in self)

    def __repr__(self):
        return "<ParameterDomainCollection {0}>".format(self.names())

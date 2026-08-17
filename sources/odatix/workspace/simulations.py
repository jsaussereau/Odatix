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
Simulations: what a workspace runs on its architectures besides synthesis.

A simulation is a directory holding a settings file (how the parameters of the
architecture under test are substituted into the testbench, and what the
simulation runs), an optional metrics file, and whatever the simulation needs
to run (a Makefile, sources, ...).
"""

import os

import odatix.lib.hard_settings as hard_settings
from odatix.workspace.entries import Collection, Entry
from odatix.workspace.metrics import METRICS_FILENAME, MetricsFile
from odatix.workspace.settings import Setting, Settings, load_settings, save_settings
from odatix.workspace.yaml_io import file_header

__all__ = ["ProgressSettings", "SimulationSettings", "Simulation", "SimulationCollection"]


######################################
# Settings
######################################

class ProgressSettings(Settings):
    """How a run reports its progress to the monitor."""

    file = Setting("", type="str", skip_if_empty=True, doc="Log file the progress is read from.")
    regex = Setting("", type="str", skip_if_empty=True, doc="Pattern the percentage is read with.")


class SimulationSettings(Settings):
    """
    Settings of a simulation ("<simulation>/_settings.yml").
    """

    architectures = Setting(
        factory=list, type="list", skip_if_empty=True, section="Architectures",
        doc="Architectures this simulation runs on, and what it changes for each of them: a list "
            "of names, a name optionally holding \"param_domains\" (per-domain parameter "
            "substitution) and \"metrics_file\" (the metrics file to extract with, instead of "
            "\"_metrics.yml\"). Names accept wildcards, \"*\" standing for every architecture, and "
            "entries matching the architecture under test are applied in the order they are "
            "written. Listing an architecture is an indication, not a restriction: running the "
            "simulation on one it does not list is allowed, and only prints a warning.",
    )

    # Deprecated: superseded by "param_domains", which covers both of the blocks below and any
    # number of domains instead of one. Still read so existing simulations keep running.
    use_parameters = Setting(
        True, type="bool", style="yesno", section="Delimiters for parameter files (deprecated, use param_domains)",
        doc="Deprecated. Whether the parameters of the architecture are substituted into the testbench.",
    )
    param_target_file = Setting("", type="str", doc="Deprecated. File the parameters are written into.")
    start_delimiter = Setting("", type="str", doc="Deprecated. Text after which the parameters are written. Escape sequences such as \\n are supported.")
    stop_delimiter = Setting("", type="str", doc="Deprecated. Text before which the parameters are written. Escape sequences such as \\n are supported.")

    override_parameters = Setting(
        False, type="bool", style="yesno", section="Parameter override (deprecated, use param_domains)",
        doc="Deprecated. Whether this simulation substitutes parameters of its own on top of the architecture's.",
    )
    override_param_file = Setting("", type="str", when="override_parameters", doc="Deprecated. File holding the overriding parameters.")
    override_param_target_file = Setting("", type="str", when="override_parameters", doc="Deprecated. File they are written into.")
    override_start_delimiter = Setting("", type="str", when="override_parameters", doc="Deprecated. Text after which they are written. Escape sequences such as \\n are supported.")
    override_stop_delimiter = Setting("", type="str", when="override_parameters", doc="Deprecated. Text before which they are written. Escape sequences such as \\n are supported.")

    invariant_domains = Setting(
        None, type="any", skip_if_empty=True, section="Invariant parameter domains",
        doc="Parameter domains this simulation's result does not depend on. "
            "A list of domain names, or a mapping giving the value to run for each.",
    )

    progress = Setting(
        type=ProgressSettings, skip_if_empty=True, section="Progress tracking",
        doc="How the run reports its progress to the monitor.",
    )
    tasks = Setting(
        factory=list, type="list", skip_if_empty=True, section="Execution",
        doc="What the simulation runs, as a task graph. Without it, \"make sim\" is run.",
    )


######################################
# Simulations
######################################

class Simulation(Entry):
    """One simulation of a workspace."""

    kind = "simulation"

    settings_class = SimulationSettings

    def __init__(self, workspace, root, name):
        super(Simulation, self).__init__(workspace, root, name)
        self._settings = None

    ######################################
    # Settings
    ######################################

    @property
    def settings_path(self):
        return os.path.join(self.path, hard_settings.sim_settings_filename)

    @property
    def settings(self):
        """The settings of this simulation, read from file on first access."""
        if self._settings is None:
            self._settings = load_settings(self.settings_class, self.settings_path)
        return self._settings

    @settings.setter
    def settings(self, value):
        self._settings = value if isinstance(value, Settings) else self.settings_class.from_dict(value)

    def reload(self):
        """Forget the settings held in memory and read them from file again."""
        self._settings = None
        return self

    def save(self, regenerate=False):
        """Write the settings of this simulation back to its file."""
        os.makedirs(self.path, exist_ok=True)
        save_settings(
            self.settings, self.settings_path,
            header=file_header("Settings for " + self.name), regenerate=regenerate,
        )
        return self

    def update(self, values=None, **kwargs):
        """Change some settings and write them back, in one call."""
        self.settings.update(values, **kwargs)
        return self.save()

    ######################################
    # Metrics
    ######################################

    @property
    def metrics_path(self):
        return os.path.join(self.path, METRICS_FILENAME)

    @property
    def metrics(self):
        """The metrics this simulation extracts from its runs."""
        return MetricsFile(self.metrics_path)


class SimulationCollection(Collection):
    """The simulations of a workspace."""

    entry_class = Simulation

    def _initialize(self, entry, **settings):
        if settings:
            entry.update(settings)

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
Workflows: arbitrary command graphs swept over parameter domains.

A workflow is the tool-agnostic counterpart of an architecture: instead of
running an EDA tool on a design, it runs the commands it declares on the
sources it points at, for every configuration of its parameter domains, and
extracts whatever metrics it declares from the result.
"""

import os

from odatix.workspace.architectures import Architecture, ArchitectureCollection
from odatix.workspace.configs import ConfigGeneration
from odatix.workspace.metrics import METRICS_FILENAME, MetricsFile
from odatix.workspace.settings import Setting, Settings
from odatix.workspace.simulations import ProgressSettings

__all__ = ["SourcesSettings", "WorkflowSettings", "Workflow", "WorkflowCollection"]


######################################
# Settings
######################################

class SourcesSettings(Settings):
    """Where the files a workflow runs on are copied from."""

    path = Setting("", type="str", doc="Directory copied into each work directory.")
    whitelist = Setting(factory=list, type="list", style="flow", skip_if_empty=True, doc="What to copy from it.")
    blacklist = Setting(factory=list, type="list", style="flow", skip_if_empty=True, doc="What not to copy from it.")


class WorkflowSettings(Settings):
    """
    Settings of a workflow ("<workflow>/_settings.yml"), which are also the
    settings of its main parameter domain.
    """

    sources = Setting(
        type=SourcesSettings, section="Design sources (copied into each work directory)",
        doc="Where the files the workflow runs on come from.",
    )

    use_parameters = Setting(
        True, type="bool", style="yesno", section="Delimiters for parameter files",
        doc="Whether the configurations of the main domain are substituted into a file.",
    )
    param_target_file = Setting("", type="str", skip_if_empty=True, doc="File the parameters are written into.")
    start_delimiter = Setting("", type="str", skip_if_empty=True, doc="Text after which the parameters are written.")
    stop_delimiter = Setting("", type="str", skip_if_empty=True, doc="Text before which the parameters are written.")

    progress = Setting(
        type=ProgressSettings, skip_if_empty=True, section="Progress tracking",
        doc="How the run reports its progress to the monitor.",
    )
    tasks = Setting(
        factory=list, type="list", section="Execution",
        doc="What the workflow runs, as a task graph. Execution starts at the task named \"main\".",
    )

    generate_configurations = Setting(
        False, type="bool", style="yesno", section="Configuration generation",
        doc="Whether the configurations of the main domain are generated from a template.",
    )
    generate_configurations_settings = Setting(
        type=ConfigGeneration, when="generate_configurations", skip_if_empty=True,
        doc="Template, name and variables the configurations are generated from.",
    )


######################################
# Workflows
######################################

class Workflow(Architecture):
    """
    One workflow of a workspace.

    A workflow is swept exactly like an architecture (same parameter domains,
    same configurations, same generation), so it is one here too; what differs
    is its settings and the metrics file it carries.
    """

    kind = "workflow"

    settings_class = WorkflowSettings

    ######################################
    # Metrics
    ######################################

    @property
    def metrics_path(self):
        return os.path.join(self.path, METRICS_FILENAME)

    @property
    def metrics(self):
        """The metrics this workflow extracts from its runs."""
        return MetricsFile(self.metrics_path)

    ######################################
    # Tasks
    ######################################

    @property
    def tasks(self):
        """The task graph of this workflow, as it is stored."""
        return self.settings.tasks

    @tasks.setter
    def tasks(self, value):
        self.settings.tasks = value


class WorkflowCollection(ArchitectureCollection):
    """The workflows of a workspace."""

    entry_class = Workflow

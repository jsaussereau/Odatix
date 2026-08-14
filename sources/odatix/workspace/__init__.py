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
The Odatix workspace configuration API.

Everything a user configures by hand in the YAML files of a workspace can be
read and written from here, from Python or from the "odatix config" command.
The graphical interface uses the very same API, so nothing it can do is out of
reach of a script.

Start by opening the workspace of the current directory::

    from odatix.workspace import Workspace

    ws = Workspace.open()

Then work on what it holds. Collections behave like the mappings they are
(``in``, ``[]``, iteration, ``len``), and every entry knows where it lives, so
no path is ever passed around::

    counter = ws.architectures.create("Counter")
    counter.settings.rtl_path = "examples/counter"
    counter.settings.top_level_file = "counter.sv"
    counter.settings.top_level_module = "counter"
    counter.settings.clock_signal = "clk"
    counter.settings.use_parameters = True
    counter.save()

    counter.configs.write("08bits", "WIDTH = 8")
    counter.configs.write("16bits", "WIDTH = 16")

    width = counter.domains.create("width")
    width.settings.configurations.name = "${width}bits"
    width.settings.configurations.template = "WIDTH = ${width}"
    width.settings.set_variable("width", "range", {"from": 8, "to": 32, "step": 8})
    width.save()
    width.configuration_names()  # a run resolves these; writing them out is optional

Settings objects are typed: they know their keys, their defaults and how each
one is written. What a settings file holds that Odatix does not know about is
never lost: it stays in the file, and in ``settings.extra``.

Writing a settings file keeps its comments and its layout. A file that does not
exist yet is generated with the section comments that make it readable.
"""

from odatix.workspace.architectures import (
    Architecture,
    ArchitectureCollection,
    ArchitectureSettings,
    CustomFrequencies,
    FrequencyBounds,
)
from odatix.workspace.configs import (
    ConfigGeneration,
    Configuration,
    ConfigurationCollection,
    combinations,
    count_combinations,
)
from odatix.workspace.clean import (
    DANGEROUS_PATHS,
    CleanResult,
    CleanSettingsFile,
    PathRemoval,
    remove_path,
)
from odatix.workspace.core import Workspace, WorkspacePaths
from odatix.workspace.derived import DerivedMetricsFile
from odatix.workspace.domains import (
    MAIN_DOMAIN,
    DomainSettings,
    ParameterDomain,
    ParameterDomainCollection,
)
from odatix.workspace.entries import Collection, Entry
from odatix.workspace.errors import (
    AlreadyExistsError,
    InvalidNameError,
    InvalidSettingsError,
    NotAWorkspaceError,
    NotFoundError,
    WorkspaceError,
)
from odatix.workspace.jobs import (
    JOB_MODES,
    AnalysisJobSettings,
    CustomFreqSynthesisJobSettings,
    FmaxSynthesisJobSettings,
    JobConfig,
    JobConfigCollection,
    JobSettings,
    PnrJobSettings,
    SimulationJobSettings,
    WorkflowJobSettings,
)
from odatix.workspace.metrics import MetricsFile
from odatix.workspace.selection import JobRequest, Message
from odatix.workspace.selection import expand as expand_selection
from odatix.workspace.selection import parse as parse_request
from odatix.workspace.settings import Setting, Settings
from odatix.workspace.simulations import (
    Simulation,
    SimulationCollection,
    SimulationSettings,
)
from odatix.workspace.targets import Target, TargetFile, TargetFileCollection
from odatix.workspace.tools import (
    Flow,
    JobExecution,
    Step,
    Tool,
    ToolCollection,
    ToolFormat,
    ToolMetrics,
    ToolSettings,
)
from odatix.workspace.workflows import (
    Workflow,
    WorkflowCollection,
    WorkflowSettings,
)


def open_workspace(root=".", required=False):
    """Open the workspace held by a directory (see :meth:`Workspace.open`)."""
    return Workspace.open(root=root, required=required)


__all__ = [
    # Entry point
    "Workspace",
    "WorkspacePaths",
    "open_workspace",
    # Errors
    "WorkspaceError",
    "NotFoundError",
    "AlreadyExistsError",
    "InvalidNameError",
    "NotAWorkspaceError",
    "InvalidSettingsError",
    # Building blocks
    "Entry",
    "Collection",
    "Setting",
    "Settings",
    # What a run targets
    "JobRequest",
    "Message",
    "parse_request",
    "expand_selection",
    # Architectures
    "Architecture",
    "ArchitectureCollection",
    "ArchitectureSettings",
    "FrequencyBounds",
    "CustomFrequencies",
    # Parameter domains and configurations
    "MAIN_DOMAIN",
    "ParameterDomain",
    "ParameterDomainCollection",
    "DomainSettings",
    "Configuration",
    "ConfigurationCollection",
    "ConfigGeneration",
    "combinations",
    "count_combinations",
    # Simulations
    "Simulation",
    "SimulationCollection",
    "SimulationSettings",
    # Workflows
    "Workflow",
    "WorkflowCollection",
    "WorkflowSettings",
    # Tools and targets
    "Tool",
    "ToolCollection",
    "ToolSettings",
    "ToolFormat",
    "ToolMetrics",
    "Flow",
    "JobExecution",
    "Step",
    "Target",
    "TargetFile",
    "TargetFileCollection",
    # Metrics
    "MetricsFile",
    "DerivedMetricsFile",
    # Cleaning
    "CleanSettingsFile",
    "CleanResult",
    "PathRemoval",
    "DANGEROUS_PATHS",
    "remove_path",
    # Runs
    "JOB_MODES",
    "JobConfig",
    "JobConfigCollection",
    "JobSettings",
    "FmaxSynthesisJobSettings",
    "CustomFreqSynthesisJobSettings",
    "PnrJobSettings",
    "SimulationJobSettings",
    "WorkflowJobSettings",
    "AnalysisJobSettings",
]

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
The workspace itself: where everything a user configures lives.

A workspace is a directory holding an "odatix.yml" settings file, which says
where its architectures, simulations, workflows, tools and targets are. Opening
one gives access to all of them::

    from odatix.workspace import Workspace

    ws = Workspace.open()
    for architecture in ws.architectures:
        print(architecture.name, architecture.settings.top_level_module)
"""

import os

from odatix.lib.settings import OdatixSettings
from odatix.workspace.architectures import ArchitectureCollection
from odatix.workspace.clean import CleanSettingsFile
from odatix.workspace.derived import DerivedMetricsFile
from odatix.workspace.errors import NotAWorkspaceError
from odatix.workspace.jobs import JobConfigCollection
from odatix.workspace.simulations import SimulationCollection
from odatix.workspace.targets import TargetFileCollection
from odatix.workspace.tools import ToolCollection
from odatix.workspace.workflows import WorkflowCollection

__all__ = ["Workspace", "WorkspacePaths"]


#: Every path setting of a workspace, with the OdatixSettings attribute holding
#: its default value.
PATH_SETTINGS = (
    ("arch_path", "DEFAULT_ARCH_PATH"),
    ("sim_path", "DEFAULT_SIM_PATH"),
    ("workflow_path", "DEFAULT_WORKFLOW_PATH"),
    ("tools_path", "DEFAULT_TOOLS_PATH"),
    ("target_path", "DEFAULT_TARGET_PATH"),
    ("work_path", "DEFAULT_WORK_PATH"),
    ("simulation_work_path", "DEFAULT_SIMULATION_WORK_PATH"),
    ("fmax_synthesis_work_path", "DEFAULT_FMAX_SYNTHESIS_WORK_PATH"),
    ("custom_freq_synthesis_work_path", "DEFAULT_CUSTOM_FREQ_SYNTHESIS_WORK_PATH"),
    ("pnr_work_path", "DEFAULT_PNR_WORK_PATH"),
    ("analysis_work_path", "DEFAULT_ANALYSIS_WORK_PATH"),
    ("workflow_work_path", "DEFAULT_WORKFLOW_WORK_PATH"),
    ("result_path", "DEFAULT_RESULT_PATH"),
    ("benchmark_file", "DEFAULT_BENCHMARK_FILE"),
    ("clean_settings_file", "DEFAULT_CLEAN_SETTINGS_FILE"),
    ("simulation_settings_file", "DEFAULT_SIMULATION_SETTINGS_FILE"),
    ("fmax_synthesis_settings_file", "DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE"),
    ("custom_freq_synthesis_settings_file", "DEFAULT_CUSTOM_FREQ_SYNTHESIS_SETTINGS_FILE"),
    ("pnr_settings_file", "DEFAULT_PNR_SETTINGS_FILE"),
    ("analysis_settings_file", "DEFAULT_ANALYSIS_SETTINGS_FILE"),
    ("workflow_settings_file", "DEFAULT_WORKFLOW_SETTINGS_FILE"),
    ("derived_metrics_file", "DEFAULT_DERIVED_METRICS_FILE"),
)


class WorkspacePaths(object):
    """
    Where each part of a workspace is.

    Every path is resolved against the workspace directory, so an API used from
    anywhere reads and writes the same files as the commands run from inside it.
    A path a workspace does not set falls back to the Odatix default.
    """

    def __init__(self, root, settings=None):
        self.root = root or "."
        settings = settings if isinstance(settings, dict) else {}
        # The paths as the settings file writes them, before they are resolved
        # against the workspace directory. The ones naming a sub-directory of
        # the work directory are only meaningful that way (see :meth:`under`).
        self._raw = {}
        for name, default_attribute in PATH_SETTINGS:
            value = settings.get(name)
            if not isinstance(value, str) or value.strip() == "":
                value = getattr(OdatixSettings, default_attribute)
            self._raw[name] = value
            setattr(self, name, self.resolve(value))
        #: Where a target file kept at the old default location is looked up.
        self.target_fallback_path = self.resolve(OdatixSettings.DEFAULT_TARGET_FALLBACK_PATH)

    def under_work_path(self, name):
        """
        The work directory of one kind of job ("fmax_synthesis_work_path", ...).

        Those settings name a sub-directory of the work directory, not a path of
        their own, so they are joined to it rather than resolved against the
        workspace like every other path.
        """
        value = self._raw.get(name, "")
        if os.path.isabs(value):
            return value
        return os.path.join(self.work_path, value)

    def resolve(self, path):
        """A workspace path as an absolute-or-relative path usable from anywhere."""
        if not path:
            return path
        if os.path.isabs(path) or self.root in ("", "."):
            return path
        return os.path.join(self.root, path)

    def to_dict(self):
        return dict((name, getattr(self, name)) for name, _default in PATH_SETTINGS)

    def __repr__(self):
        return "<WorkspacePaths {0!r}>".format(self.root)


class Workspace(object):
    """
    An Odatix workspace.

    This is the entry point of the configuration API: everything a user can
    configure hangs off it, and nothing else needs to be given a path.
    """

    #: Name of the settings file of a workspace.
    SETTINGS_FILENAME = OdatixSettings.DEFAULT_SETTINGS_FILE

    def __init__(self, root=".", settings=None):
        self.root = root or "."
        self._settings = dict(settings) if isinstance(settings, dict) else None
        self._paths = None

    ######################################
    # Opening
    ######################################

    @classmethod
    def open(cls, root=".", required=False):
        """
        Open the workspace held by a directory.

        Args:
            root (str): the workspace directory. The current one by default,
                which is where the Odatix commands run.
            required (bool): raise :class:`NotAWorkspaceError` when the
                directory holds no settings file. Without it, the workspace
                opens on the Odatix defaults, which is what a directory about to
                be initialized looks like.
        """
        workspace = cls(root=root)
        if required and not workspace.exists:
            raise NotAWorkspaceError(
                "'{0}' holds no Odatix settings file ('{1}'). Run \"odatix init\" to create one.".format(
                    workspace.root, cls.SETTINGS_FILENAME
                )
            )
        workspace.settings  # resolve now, so a broken settings file is reported here
        return workspace

    @classmethod
    def from_dict(cls, settings, root="."):
        """
        Open a workspace from settings already in hand, without reading the
        settings file again.
        """
        return cls(root=root, settings=settings)

    @classmethod
    def init(cls, root=".", examples=False):
        """
        Create the configuration files of a workspace in a directory, and open
        it. An existing configuration is overwritten, as "odatix init" does.
        """
        current = os.getcwd()
        if root and root != ".":
            os.makedirs(root, exist_ok=True)
        try:
            os.chdir(root or ".")
            OdatixSettings.init_directory_nodialog(include_examples=examples, silent=True)
        finally:
            os.chdir(current)
        return cls.open(root=root)

    ######################################
    # Settings
    ######################################

    @property
    def settings_file(self):
        """Path of the settings file of this workspace."""
        return os.path.join(self.root, self.SETTINGS_FILENAME) if self.root != "." else self.SETTINGS_FILENAME

    @property
    def exists(self):
        """Whether the directory actually holds a workspace."""
        return os.path.isfile(self.settings_file)

    @property
    def settings(self):
        """
        The settings file of this workspace, as plain values. Missing keys are
        not filled in here: :attr:`paths` is what applies the defaults.
        """
        if self._settings is None:
            data = OdatixSettings.get_settings_file_dict(self.settings_file, silent=True)
            self._settings = data if isinstance(data, dict) else {}
        return self._settings

    @property
    def paths(self):
        """Where each part of this workspace is."""
        if self._paths is None:
            self._paths = WorkspacePaths(self.root, self.settings)
            self._latch_tools_path()
        return self._paths

    def _latch_tools_path(self):
        """
        Tell the tool resolution helpers where this workspace keeps its tools.
        They are reached from everywhere and hold no workspace, so the path
        lives on the settings class, exactly as reading a settings file sets it.
        """
        OdatixSettings.user_tools_path = os.path.realpath(self._paths.tools_path)

    def reload(self):
        """Read the settings file again, and forget the resolved paths."""
        self._settings = None
        self._paths = None
        return self

    def save_settings(self, values=None, **kwargs):
        """
        Write the settings file of this workspace. Only the settings that are
        set are written: an empty one means "use the Odatix default".
        """
        settings = dict(self.settings)
        for source in (values, kwargs):
            if source:
                settings.update(source)
        OdatixSettings.save_dict_to_file(settings, self.settings_file)
        self._settings = settings
        self._paths = None
        return self

    def odatix_settings(self):
        """
        The settings as an :class:`~odatix.lib.settings.OdatixSettings` object,
        for the parts of Odatix that take one.
        """
        return OdatixSettings(self.settings_file, silent=True)

    ######################################
    # What the workspace holds
    ######################################

    @property
    def architectures(self):
        """The architectures of this workspace."""
        return ArchitectureCollection(self, lambda: self.paths.arch_path)

    @property
    def simulations(self):
        """The simulations of this workspace."""
        return SimulationCollection(self, lambda: self.paths.sim_path)

    @property
    def workflows(self):
        """The workflows of this workspace."""
        return WorkflowCollection(self, lambda: self.paths.workflow_path)

    @property
    def tools(self):
        """The EDA tools usable by this workspace, built-in ones included."""
        return ToolCollection(self, lambda: self.paths.tools_path)

    @property
    def targets(self):
        """The synthesis targets, one file per EDA tool."""
        return TargetFileCollection(self)

    @property
    def jobs(self):
        """What each run command of this workspace runs, and how."""
        return JobConfigCollection(self)

    @property
    def derived_metrics(self):
        """The metrics this workspace computes from the ones its runs produce."""
        return DerivedMetricsFile(self.paths.derived_metrics_file)

    @property
    def clean_settings(self):
        """What "odatix clean" removes from this workspace."""
        return CleanSettingsFile(self.paths.clean_settings_file, root=self.root)

    ######################################
    # Display
    ######################################

    def __repr__(self):
        return "<Workspace {0!r}>".format(os.path.abspath(self.root))

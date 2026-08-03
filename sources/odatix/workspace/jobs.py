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
What each Odatix command runs, and how.

Every run command reads one settings file of the workspace: what to run (the
architectures, the workflows, the simulations, or the synthesis jobs to place
and route), and how to run it (how many jobs in parallel, whether to overwrite
existing results, at which frequencies...). Those files are what
``ws.jobs.fmax_synthesis`` and its siblings hold.

The command line overrides several of these settings; the comments the
generated files carry say which flag overrides what.
"""

import odatix.lib.hard_settings as hard_settings
from odatix.workspace.errors import InvalidSettingsError, NotFoundError
from odatix.workspace.settings import Setting, Settings, load_settings, save_settings
from odatix.workspace.yaml_io import file_header, read_mapping

__all__ = [
    "JOB_MODES",
    "REQUIRED_KEYS",
    "FrequencyRange",
    "FrequenciesSettings",
    "FmaxBoundsSettings",
    "JobSettings",
    "FmaxSynthesisJobSettings",
    "CustomFreqSynthesisJobSettings",
    "PnrJobSettings",
    "SimulationJobSettings",
    "WorkflowJobSettings",
    "AnalysisJobSettings",
    "JobConfig",
    "JobConfigCollection",
]


######################################
# Frequencies
######################################

class FrequencyRange(Settings):
    """A range of synthesis frequencies, in MHz."""

    start = Setting(50, type="optional_int", key="from", comment="overridden by --from", doc="First frequency, in MHz.")
    stop = Setting(100, type="optional_int", key="to", comment="overridden by --to", doc="Last frequency, in MHz.")
    step = Setting(10, type="optional_int", comment="overridden by --step", doc="Step between frequencies, in MHz.")


class FrequenciesSettings(Settings):
    """
    The frequencies a custom frequency synthesis runs at.

    A list and a range can both be kept in the file, each switched on or off:
    the one that is off is written under "disabled_list" / "disabled_range", so
    its values are remembered without being run.
    """

    override = Setting(
        False, type="bool", style="yesno",
        comment="if false, those values are only used when no architecture-specific frequencies are defined",
        doc="Whether these frequencies replace the architecture-specific ones.",
    )
    use_custom_freq_list = Setting(True, type="bool", stored=False, doc="Whether the list of frequencies is used.")
    frequencies = Setting(
        factory=lambda: list(hard_settings.default_custom_freq_list), type="int_list", key="list",
        alt_key="disabled_list", when="use_custom_freq_list", style="flow",
        comment="overridden by --at", alt_comment=" not used but settings are saved",
        doc="Frequencies to synthesize at, in MHz.",
    )
    use_custom_freq_range = Setting(True, type="bool", stored=False, doc="Whether the range of frequencies is used.")
    range = Setting(
        type=FrequencyRange, alt_key="disabled_range", when="use_custom_freq_range",
        alt_comment=" not used but settings are saved",
        doc="Range of frequencies to synthesize at.",
    )

    @classmethod
    def from_dict(cls, data):
        settings = super(FrequenciesSettings, cls).from_dict(data)
        if not isinstance(data, dict):
            return settings
        # A file that holds both keys, the used one left empty, means the values
        # to remember are the disabled ones.
        if not settings.frequencies and data.get("disabled_list"):
            settings.frequencies = data.get("disabled_list")
            settings.use_custom_freq_list = False
        if not data.get("range") and data.get("disabled_range"):
            settings.range = data.get("disabled_range")
            settings.use_custom_freq_range = False
        return settings


class FmaxBoundsSettings(Settings):
    """The bounds the fmax binary search runs in, for the whole run."""

    override = Setting(
        False, type="bool", style="yesno",
        comment="if false, those values are only used when no architecture-specific bounds are defined",
        doc="Whether these bounds replace the architecture-specific ones.",
    )
    lower_bound = Setting(
        None, type="optional_int",
        comment="overridden by --from (empty: use default / architecture-specific bound)",
        doc="Lowest frequency tried, in MHz.",
    )
    upper_bound = Setting(
        None, type="optional_int",
        comment="overridden by --to (empty: use default / architecture-specific bound)",
        doc="Highest frequency tried, in MHz.",
    )


######################################
# Run settings
######################################

class JobSettings(Settings):
    """
    What every run command reads, whatever it runs.
    """

    # Odatix reads these files key by key and stops when one is missing, so they
    # spell every setting out rather than relying on defaults.
    write_all_settings = True

    overwrite = Setting(
        False, type="bool", style="yesno", section=" overwrite existing results",
        comment="overridden by -o / --overwrite",
        doc="Whether results that already exist are run again.",
    )
    ask_continue = Setting(
        False, type="bool", style="yesno", section=" prompt 'Continue? (Y/n)' after settings checks",
        comment="overridden by -y / --noask",
        doc="Whether the run stops for a confirmation once it knows what it will do.",
    )
    exit_when_done = Setting(
        False, type="bool", style="yesno", section=" exit monitor when all jobs are done",
        comment="overridden by -E / --exit",
        doc="Whether the monitor closes by itself once every job is done.",
    )
    log_size_limit = Setting(
        300, type="int", section=" size of the log history per job in the monitor",
        comment="overridden by --logsize",
        doc="How many log lines the monitor keeps per job.",
    )
    nb_jobs = Setting(
        8, type="any", section=" maximum number of parallel jobs ('auto' = number of CPUs minus one)",
        comment="overridden by -j / --jobs",
        doc="How many jobs run in parallel. An integer, or \"auto\".",
    )
    force_single_thread = Setting(
        False, type="bool", style="yesno",
        section=" force single thread execution (to avoid cpu overload when running many jobs in parallel)",
        doc="Whether each job is asked to use a single thread.",
    )


#: What an architecture selection looks like, shared by the runs that select
#: architectures. Declared per class rather than in a base one, so that each
#: generated file lists what it runs last, after how it runs it.
def _architecture_selection():
    return Setting(
        factory=list, type="any", section=" targeted architectures",
        doc="Architecture configurations to run, as \"<architecture>/<configuration>\".",
    )


class ArchitectureJobSettings(JobSettings):
    """
    Run settings that only select architectures, with nothing specific to add.
    """

    selection_key = "architectures"

    architectures = _architecture_selection()


class FmaxSynthesisJobSettings(JobSettings):
    """Settings of an "odatix fmax" run."""

    selection_key = "architectures"

    fmax_synthesis = Setting(
        type=FmaxBoundsSettings, section=" fmax binary search bounds (in MHz)",
        doc="Bounds the binary search runs in.",
    )
    architectures = _architecture_selection()


class CustomFreqSynthesisJobSettings(JobSettings):
    """Settings of an "odatix synth" run."""

    selection_key = "architectures"

    frequencies = Setting(
        type=FrequenciesSettings, section=" synthesis frequencies (in MHz)",
        doc="Frequencies the designs are synthesized at.",
    )
    architectures = _architecture_selection()


class AnalysisJobSettings(JobSettings):
    """Settings of an "odatix analyze" run."""

    selection_key = "architectures"

    tools = Setting(
        factory=list, type="str_list", section=" eda tools to run the analysis with",
        comment="overridden by -t / --tool",
        doc="EDA tools the RTL analysis runs with.",
    )
    architectures = _architecture_selection()


class PnrJobSettings(JobSettings):
    """Settings of an "odatix pnr" run."""

    selection_key = "sources"

    sources = Setting(
        factory=list, type="str_list",
        section=(
            " completed synthesis jobs to place & route, written"
            "\n <source_type>/<source_tool>[@<source_flow>]/<target>/<architecture>/<configuration>[@<frequency>MHz]"
            '\n with "*" accepted at every level'
        ),
        doc="Completed synthesis jobs to start from.",
    )


class SimulationSelection(Setting):
    """
    The simulations of a run, each with the architecture configurations it runs
    on. The file holds them as a list of single-key mappings, which reads well
    and is what "odatix sim" expects.
    """

    def coerce(self, value):
        if isinstance(value, dict):
            return dict((str(name), _as_entry_list(entries)) for name, entries in value.items())
        selection = {}
        for item in (value or []):
            if not isinstance(item, dict):
                continue
            for name, entries in item.items():
                selection.setdefault(str(name), []).extend(_as_entry_list(entries))
        return selection

    def dump(self, value):
        from ruamel.yaml.comments import CommentedMap, CommentedSeq

        simulations = CommentedSeq()
        for name, entries in (value or {}).items():
            if not name:
                continue
            simulations.append(CommentedMap({str(name): CommentedSeq([str(entry) for entry in entries if entry])}))
        return simulations


def _as_entry_list(entries):
    if entries is None:
        return []
    if isinstance(entries, str):
        entries = [entries]
    if not isinstance(entries, (list, tuple)):
        return []
    return [str(entry) for entry in entries if entry is not None]


def simulation_selection_list(selection):
    """
    The "simulations" value of a run settings file, built from a
    ``{simulation: [architecture configuration, ...]}`` mapping.
    """
    return SimulationSelection().dump(selection)


class SimulationJobSettings(JobSettings):
    """Settings of an "odatix sim" run."""

    selection_key = "simulations"

    simulations = SimulationSelection(
        factory=dict, section=" targeted simulations",
        doc="Simulations to run, each with the architecture configurations it runs on.",
    )


class WorkflowJobSettings(JobSettings):
    """Settings of an "odatix workflow" run."""

    selection_key = "workflows"

    workflows = Setting(
        factory=list, type="any", section=" targeted workflows",
        doc="Workflow configurations to run, as \"<workflow>/<configuration>\".",
    )


######################################
# Run modes
######################################

#: The run commands of Odatix, with what their settings file is called in the
#: workspace settings, what it holds, and how it is named to a user.
JOB_MODES = {
    "fmax_synthesis": {
        "label": "fmax synthesis",
        "settings_class": FmaxSynthesisJobSettings,
        "settings_file": "fmax_synthesis_settings_file",
        "command": "fmax",
    },
    "custom_freq_synthesis": {
        "label": "custom frequency synthesis",
        "settings_class": CustomFreqSynthesisJobSettings,
        "settings_file": "custom_freq_synthesis_settings_file",
        "command": "synth",
    },
    "pnr": {
        "label": "place & route",
        "settings_class": PnrJobSettings,
        "settings_file": "pnr_settings_file",
        "command": "pnr",
    },
    "simulation": {
        "label": "simulations",
        "settings_class": SimulationJobSettings,
        "settings_file": "simulation_settings_file",
        "command": "sim",
    },
    "workflow": {
        "label": "workflows",
        "settings_class": WorkflowJobSettings,
        "settings_file": "workflow_settings_file",
        "command": "workflow",
    },
    "analysis": {
        "label": "RTL analysis",
        "settings_class": AnalysisJobSettings,
        "settings_file": "analysis_settings_file",
        "command": "analyze",
    },
}

#: Names the GUI and the command line also use for a mode.
MODE_ALIASES = {
    "analyze": "analysis",
    "fmax": "fmax_synthesis",
    "synth": "custom_freq_synthesis",
    "freq": "custom_freq_synthesis",
    "custom_freq": "custom_freq_synthesis",
    "sim": "simulation",
    "simulations": "simulation",
    "workflows": "workflow",
}


def resolve_mode(mode):
    """The canonical name of a run mode."""
    mode = str(mode)
    mode = MODE_ALIASES.get(mode, mode)
    if mode not in JOB_MODES:
        raise NotFoundError("Unknown run mode: '{0}'.".format(mode))
    return mode


######################################
# Reading a run settings file
######################################

#: Tells "the file said nothing" from "the file said nothing was selected".
_UNSET = object()

#: Keys a run settings file has to spell out, whatever it runs. They say what
#: happens to results that already exist and how much of the machine the run
#: takes: Odatix does not guess them, it refuses to start without them.
REQUIRED_KEYS = ("overwrite", "ask_continue", "nb_jobs")


def _require_bool(data, key, path):
    value = data[key]
    if not isinstance(value, bool):
        raise InvalidSettingsError(
            'Value "{0}" for key "{1}" in "{2}" is of type "{3}" while it should be a boolean.'.format(
                value, key, path, type(value).__name__
            ),
            path=path,
            key=key,
        )
    return value


def _require_nb_jobs(data, path):
    """The number of parallel jobs: an integer, or the "auto" keyword."""
    from odatix.lib.utils import AUTO_NB_JOBS_KEYWORD, is_auto_nb_jobs

    value = data["nb_jobs"]
    if is_auto_nb_jobs(value):
        return value
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidSettingsError(
            'Value "{0}" for key "nb_jobs" in "{1}" must be an integer or "{2}".'.format(
                value, path, AUTO_NB_JOBS_KEYWORD
            ),
            path=path,
            key="nb_jobs",
        )
    return value


######################################
# Job configuration files
######################################

class JobConfig(object):
    """
    The settings file of one run command.
    """

    def __init__(self, workspace, mode, path):
        self.workspace = workspace
        self.path = path
        self._settings = None
        self._raw_selection = _UNSET
        try:
            self.mode = resolve_mode(mode)
        except NotFoundError:
            # A run whose mode Odatix does not name: it still selects
            # architectures and is still run the same way.
            self.mode = None
            self._label = str(mode)

    ######################################
    # Description
    ######################################

    @property
    def label(self):
        """How this run is named to a user."""
        return JOB_MODES[self.mode]["label"] if self.mode else self._label

    @property
    def command(self):
        """The Odatix command that reads this file."""
        return JOB_MODES[self.mode]["command"] if self.mode else None

    @property
    def settings_class(self):
        return JOB_MODES[self.mode]["settings_class"] if self.mode else ArchitectureJobSettings

    @property
    def selection_key(self):
        """The key holding what this run targets."""
        return self.settings_class.selection_key

    @property
    def exists(self):
        import os

        return os.path.isfile(self.path)

    ######################################
    # Settings
    ######################################

    @property
    def settings(self):
        """The settings of this run, read from file on first access."""
        if self._settings is None:
            self._settings = load_settings(self.settings_class, self.path)
        return self._settings

    @settings.setter
    def settings(self, value):
        self._settings = value if isinstance(value, Settings) else self.settings_class.from_dict(value)

    def load(self):
        """
        Read this run settings file the way a run needs it, and keep it.

        :attr:`settings` reads a file the way the graphical interface edits it:
        whatever it leaves out falls back on a default, and a file that does not
        exist yet is simply an empty configuration. A run cannot work like that,
        so this checks the file instead: it must exist, hold a mapping, spell
        out every key of :data:`REQUIRED_KEYS` plus the one saying what to run,
        and give them values of the right kind.

        Returns:
            Settings: the settings of this run, also kept as :attr:`settings`.

        Raises:
            InvalidSettingsError: the file cannot be run from.
        """
        data = read_mapping(self.path)

        for key in REQUIRED_KEYS:
            if key not in data:
                raise InvalidSettingsError(
                    'Cannot find key "{0}" in "{1}".'.format(key, self.path), path=self.path, key=key
                )
        _require_bool(data, "overwrite", self.path)
        _require_bool(data, "ask_continue", self.path)
        _require_nb_jobs(data, self.path)

        if self.selection_key not in data:
            raise InvalidSettingsError(
                'Cannot find key "{0}" in "{1}".'.format(self.selection_key, self.path),
                path=self.path,
                key=self.selection_key,
                hints=[
                    'You must define what this {0} run targets in "{1}" before using this command.'.format(
                        self.label, self.path
                    )
                ],
            )

        self._settings = self.settings_class.from_dict(data)
        # What the file literally holds under the selection key. The typed
        # setting reshapes it (a simulation selection becomes a mapping), which
        # is not what every run flow expects to be handed.
        self._raw_selection = data[self.selection_key]
        return self._settings

    @property
    def raw_selection(self):
        """
        What the file holds under its selection key, exactly as written.

        Reading a selection this way keeps the difference between "no entry"
        (an empty list) and "the key is there but says nothing" (``None``),
        which is what the run flows report as an empty run settings file.
        """
        return self.selection if self._raw_selection is _UNSET else self._raw_selection

    def reload(self):
        self._settings = None
        self._raw_selection = _UNSET
        return self

    def save(self, regenerate=False):
        """Write the settings of this run back to its file."""
        save_settings(
            self.settings, self.path,
            header=file_header("Odatix settings for " + self.label), regenerate=regenerate,
        )
        return self

    def update(self, values=None, **kwargs):
        """Change some settings and write them back, in one call."""
        self.settings.update(values, **kwargs)
        return self.save()

    ######################################
    # What the run targets
    ######################################

    @property
    def selection(self):
        """What this run targets, whatever the run calls it."""
        return self.settings[self.selection_key]

    @selection.setter
    def selection(self, value):
        self.settings[self.selection_key] = value

    def __repr__(self):
        return "<JobConfig {0!r} {1!r}>".format(self.mode, self.path)


def job_config(path, mode="fmax_synthesis"):
    """
    A run settings file worked on by path, outside of a workspace (a temporary
    file a run is started from, for instance).
    """
    return JobConfig(None, mode, path)


class JobConfigCollection(object):
    """
    The run settings files of a workspace, one per command:
    ``ws.jobs.fmax_synthesis``, ``ws.jobs["simulation"]``, ...
    """

    def __init__(self, workspace):
        self.workspace = workspace

    def names(self):
        return list(JOB_MODES.keys())

    def __getitem__(self, mode):
        mode = resolve_mode(mode)
        path = getattr(self.workspace.paths, JOB_MODES[mode]["settings_file"])
        return JobConfig(self.workspace, mode, path)

    def __getattr__(self, name):
        if name.startswith("_") or name in ("workspace",):
            raise AttributeError(name)
        try:
            return self[name]
        except NotFoundError:
            raise AttributeError(name)

    def __iter__(self):
        for mode in self.names():
            yield self[mode]

    def __contains__(self, mode):
        try:
            resolve_mode(mode)
        except NotFoundError:
            return False
        return True

    def get(self, mode, default=None):
        try:
            return self[mode]
        except NotFoundError:
            return default

    def __repr__(self):
        return "<JobConfigCollection {0}>".format(self.names())

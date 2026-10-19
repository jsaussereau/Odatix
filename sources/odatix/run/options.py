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
What a run is asked to do on top of what its settings file says.

These are the command line flags, as an object: a run reads its settings file,
and what is set here takes precedence, exactly as "--overwrite" does. A setting
left unset keeps what the file says, which is why most of them default to None
rather than to a value.
"""

from odatix.workspace.settings import Setting, Settings

__all__ = ["RunOptions"]


class RunOptions(Settings):
    """
    What one run does differently from what its settings file says.

    Built the same way as the settings of a workspace, so a value given as text
    (from a command line or a form) is read the same way here as it is there.
    """

    ######################################
    # What runs it
    ######################################

    # Taken as it comes: an RTL analysis runs several tools at once, and names
    # them as a list.
    tool = Setting("", type="any", doc="EDA tool the jobs run with, or the tools an analysis runs.")
    flow = Setting(None, type="any", doc="Flow of that tool. Its default flow when unset.")
    # Which of the targets the tool's target file enables this run actually uses.
    # Empty means all of them, which is what a run has always done: the target
    # file is where targets are turned on and off. It is only when something
    # else chooses one target at a time -- an exploration searching the targets,
    # typically -- that a run has to be told a subset without the file changing
    # under the other runs sharing it.
    targets = Setting(
        factory=list, type="str_list",
        doc="Synthesis targets to run on, out of those the tool's target file enables. All of them when empty.",
    )
    # The architectures to run, written as the entries of "architectures" in the
    # run settings file: a command line names them the same way, and they replace
    # that list for this run only, the file staying as it is.
    architectures = Setting(
        factory=list, type="str_list",
        doc="Architectures to run, as entries of the run settings file's \"architectures\". Its own list when empty.",
    )
    # The simulations to run, by name, on the architectures the run settings
    # file gives them -- or on "architectures" when set.
    simulations = Setting(
        factory=list, type="str_list",
        doc="Simulations to run, by name. Every simulation of the run settings file when empty.",
    )
    # The workflows to run, written as the entries of "workflows" in the run
    # settings file, which they replace for this run only.
    workflows = Setting(
        factory=list, type="str_list",
        doc="Workflows to run, as entries of the run settings file's \"workflows\". Its own list when empty.",
    )
    until = Setting(None, type="any", doc="Last step of the flow to run, inclusive.")
    rerun_from = Setting(None, type="any", doc="Step to run again, with the ones after it.")

    ######################################
    # What it does with what already exists
    ######################################

    overwrite = Setting(False, type="bool", doc="Run again what is already done.")
    keep = Setting(False, type="bool", doc="Keep previous results, by timestamping the new ones.")
    resume = Setting(False, type="bool", doc="Pick a stopped run up where it left off.")

    ######################################
    # How much of the machine it takes
    ######################################

    nb_jobs = Setting(None, type="any", doc="How many jobs run at once. The settings file's own value when unset.")
    log_size_limit = Setting(None, type="optional_int", doc="How many log lines the monitor keeps per job.")
    force_single_thread = Setting(False, type="bool", doc="Ask each job to use a single thread.")

    ######################################
    # How it talks, and to whom
    ######################################

    # A script must never stop on a question nobody is there to answer, so a run
    # only asks when it is explicitly told to.
    noask = Setting(True, type="bool", doc="Do not stop for the 'Continue?' confirmation.")
    exit_when_done = Setting(False, type="bool", doc="Close the monitor once every job is done.")
    detach = Setting(True, type="bool", doc="Hand the jobs over to the daemon without attaching a monitor.")
    session = Setting(None, type="any", doc="Daemon session to enqueue into.")
    session_access = Setting(
        None, type="any",
        doc=(
            "Who may use a session this run starts besides its owner: \"user\" (nobody), \"group\" "
            "(the group of the workspace) or \"other\" (every user). None is what the workspace says "
            "(\"session_access\" in odatix.yml)."
        ),
    )
    configure_session = Setting(
        True, type="bool",
        doc=(
            "Apply how this run wants the daemon to behave, on top of enqueueing its jobs. "
            "A run that is itself a job of the session it enqueues into (see odatix.dse) "
            "leaves it as it found it."
        ),
    )
    debug = Setting(False, type="bool", doc="Report what reading the settings files finds.")
    check_eda_tool = Setting(True, type="bool", doc="Check the eda tool actually runs before using it.")
    continue_on_error = Setting(False, type="bool", doc="Keep going when a job fails.")

    ######################################
    # Frequencies
    ######################################

    lower_bound = Setting(None, type="optional_int", doc="Lowest frequency of an fmax search, in MHz.")
    upper_bound = Setting(None, type="optional_int", doc="Highest frequency of an fmax search, in MHz.")
    frequencies = Setting(
        factory=list, type="int_list",
        doc="Frequencies a fixed-frequency synthesis runs at, in MHz. The settings file's own when empty.",
    )

    ######################################
    # Place & route
    ######################################

    source_result_types = Setting(None, type="any", doc="Result types a place & route starts from.")
    from_type = Setting(None, type="any", doc="Result type the sources of a place & route come from.")
    from_tool = Setting(None, type="any", doc="EDA tool they come from.")
    from_flow = Setting(None, type="any", doc="Flow they come from.")

    ######################################
    # Where things are
    ######################################

    # Each of these replaces what the workspace says. A run started from a
    # script leaves them alone; the command line fills them in from its own
    # options ("--work", "--archpath", ...).
    settings_file = Setting(None, type="any", doc="Run settings file to read, instead of the workspace's own.")
    work_path = Setting(None, type="any", doc="Where the jobs run, instead of the workspace's own work directory.")
    result_path = Setting(None, type="any", doc="Where the results are written. Nothing is exported when empty.")
    arch_path = Setting(None, type="any", doc="Where the architectures are.")
    sim_path = Setting(None, type="any", doc="Where the simulations are.")
    workflow_path = Setting(None, type="any", doc="Where the workflows are.")
    target_path = Setting(None, type="any", doc="Where the target files of the eda tools are.")
    source_work_root = Setting(None, type="any", doc="Work directory a place & route reads its sources from.")

    ######################################
    # Exporting
    ######################################

    custom_metrics_file = Setting(None, type="any", doc="Extra metrics to read from the reports.")
    output_filename = Setting(None, type="any", doc="Name of the result file, when the run writes one.")

    ######################################
    # From a command line
    ######################################

    #: What a command does when it is not told otherwise: it asks before
    #: starting, and attaches the monitor to the jobs it starts. A script is
    #: the other way around (see the defaults above).
    COMMAND_DEFAULTS = {"noask": False, "detach": False}

    @classmethod
    def from_namespace(cls, args, **overrides):
        """
        The options a command line gives, as parsed by argparse.

        Every option of a run command lands in the setting of the same name
        (see odatix.components.cli_options), so this is a plain copy. What the
        command line leaves unset keeps the default of a command, and
        "--noexport" is the empty result path that exports nothing.

        Args:
            args (argparse.Namespace): the parsed command line.
            **overrides: settings the command works out itself from its own
                options ("--from"/"--to"/"--step" into ``frequencies``, ...).
        """
        options = cls(**cls.COMMAND_DEFAULTS)
        for name, value in vars(args).items():
            if name in cls._specs and value is not None:
                options[name] = value
        if getattr(args, "noexport", False):
            options.result_path = ""
        options.update(overrides)
        return options

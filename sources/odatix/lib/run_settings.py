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
Reading the settings file of a run, for the command line.

What the file holds, and what makes it valid, is the workspace API's business
(:class:`odatix.workspace.JobConfig`). What is left here is the command line's
own way of reacting to a file it cannot run from: report it the way every other
Odatix message is reported, and exit.

A script does not want that. It reads the same files through the API instead::

    from odatix.workspace import Workspace

    settings = Workspace.open().jobs.fmax_synthesis.load()
    print(settings.nb_jobs, settings.architectures)

which raises :class:`~odatix.workspace.InvalidSettingsError` rather than
stopping the interpreter.
"""

import os
import sys

import odatix.lib.printc as printc
from odatix.workspace.errors import InvalidSettingsError
from odatix.workspace.jobs import JobSettings, job_config

script_name = os.path.basename(__file__)

DEFAULT_EXIT_WHEN_DONE = JobSettings.spec("exit_when_done").default
DEFAULT_LOG_SIZE_LIMIT = JobSettings.spec("log_size_limit").default


def read_job_settings(settings_filename, mode):
    """
    Read a run settings file, or exit.

    Args:
        settings_filename (str): the file to read.
        mode (str): what the run is, one of :data:`odatix.workspace.JOB_MODES`.
            It says which key holds what the run targets.

    Returns:
        tuple: (overwrite, ask_continue, exit_when_done, log_size_limit,
        nb_jobs, selection), the selection being what the file holds under its
        own key, exactly as written.
    """
    config = job_config(settings_filename, mode)
    try:
        settings = config.load()
    except InvalidSettingsError as error:
        printc.error(str(error), script_name)
        for hint in error.hints:
            printc.note(hint, script_name)
        sys.exit(-1)

    return (
        settings.overwrite,
        settings.ask_continue,
        settings.exit_when_done,
        settings.log_size_limit,
        settings.nb_jobs,
        config.raw_selection,
    )


def get_synth_settings(settings_filename):
    """Read the run settings of a synthesis or an RTL analysis run."""
    return read_job_settings(settings_filename, "fmax_synthesis")


def get_pnr_settings(settings_filename):
    """
    Read the run settings of a place & route run.

    Same shape as get_synth_settings, except that what a pnr run selects is not
    architectures but the completed synthesis jobs to start from ("sources"), each
    written as
    "<source_type>/<source_tool>[@<source_flow>]/<target>/<architecture>/<configuration>[@<frequency>MHz]"
    with "*" accepted at every level (see odatix.lib.pnr_source).
    """
    return read_job_settings(settings_filename, "pnr")


def get_sim_settings(settings_filename):
    """Read the run settings of a simulation run."""
    return read_job_settings(settings_filename, "simulation")


def get_workflow_settings(settings_filename):
    """Read the run settings of a workflow run."""
    return read_job_settings(settings_filename, "workflow")

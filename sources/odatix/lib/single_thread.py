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
Running each job on a single thread ("force_single_thread" in a run settings
file).

Many jobs run at once, and a tool that takes every core in each of them
oversubscribes the processor. A run asked to keep each job on one thread tells
it two ways, so that every tool hears it:

- the environment of the job: ``ODATIX_SINGLE_THREAD=1``, which the scripts of
  Odatix read (settings.tcl, the simulation runner, a workflow's own commands),
  and the thread counts of the usual runtimes (OpenMP, BLAS...), which tools
  built on them follow. Each command line of the job sets them first (see
  wrap_command), so they hold wherever the job runs, in the daemon too;
- ``set single_thread 1`` in the settings.tcl of the job, written with the
  other settings of the job (see prepare_work), for the tools that read it
  from there only: those that run inside a container, which the environment
  does not reach.

What each tool does of it is in its own scripts (odatix_single_thread in
_common/settings.tcl for the Tcl ones).
"""

import os

#: The variable the scripts of a job read to know they run on one thread.
ENV_VARIABLE = "ODATIX_SINGLE_THREAD"

#: What the environment of a single-threaded job sets: ours, and the thread
#: counts of the runtimes tools are built on.
SINGLE_THREAD_ENV = {
    ENV_VARIABLE: "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}


def requested(settings_filename):
    """
    Whether a run settings file asks for single-threaded jobs. A file that
    cannot be read does not: the run reports it on its own.
    """
    from odatix.workspace.yaml_io import parse_bool, read_mapping

    try:
        return parse_bool(read_mapping(settings_filename).get("force_single_thread"), False)
    except Exception:
        return False


def in_environment(environ=None):
    """Whether the environment says the job runs on a single thread."""
    environ = os.environ if environ is None else environ
    return str(environ.get(ENV_VARIABLE, "")).strip().lower() in ("1", "true", "yes")


def environment_prefix(windows=None):
    """
    What a command line starts with to run with the environment of a
    single-threaded job, in the shell the job handler runs it with: sh, or
    cmd.exe under Windows. Under Windows, WSLENV hands the variables over to
    what a job runs in WSL too.
    """
    windows = (os.name == "nt") if windows is None else windows
    names = sorted(SINGLE_THREAD_ENV)
    if windows:
        sets = ['set "{0}={1}"'.format(name, SINGLE_THREAD_ENV[name]) for name in names]
        sets.append('set "WSLENV=%WSLENV%:' + ":".join(names) + '"')
        return " & ".join(sets) + " & "
    return "export " + " ".join("{0}={1}".format(name, SINGLE_THREAD_ENV[name]) for name in names) + "; "


def wrap_command(command, windows=None):
    """
    A job command (a command line, a list of lines, or execution stages of
    {"name", "command"} tasks) whose every command line runs with the
    environment of a single-threaded job.
    """
    prefix = environment_prefix(windows)
    if isinstance(command, str):
        return prefix + command
    if isinstance(command, list):
        return prefix + "\n".join(map(str, command))
    if isinstance(command, dict):
        stages = {}
        for level, tasks in command.items():
            wrapped = []
            for task in tasks:
                if isinstance(task, dict) and isinstance(task.get("command"), str):
                    task = type(task)(task)
                    task["command"] = prefix + task["command"]
                wrapped.append(task)
            stages[level] = wrapped
        return stages
    return command


def apply(job):
    """Make a job run on a single thread. A job is only changed once."""
    if not getattr(job, "single_thread", False):
        job.command = wrap_command(job.command)
        job.single_thread = True
    return job


def apply_to_jobs(jobs):
    for job in jobs or []:
        apply(job)

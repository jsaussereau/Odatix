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

"""
The search, run as a job of the daemon like everything else.

An exploration is not work, it is what asks for work: it decides what to
synthesize, waits for it, reads what came out and decides again, for hours. Run
from a terminal, it would own that terminal for as long as it lasts -- and the
monitor, which is the only thing worth looking at while a batch runs, cannot be
up at the same time as the loop that prints between two batches.

So the loop is handed to the daemon as a job of its own: a *driver* (see
:data:`~odatix.lib.parallel_job_handler.job.DRIVER_KIND`). Everything the search
says becomes the log of that job, its progress bar is the progress of the whole
exploration, and the batches it enqueues appear underneath it in the same
session. The command then behaves like every other run: it asks once, attaches
the monitor, and the user is free to detach and come back.
"""

import os
import sys

from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler
from odatix.lib.parallel_job_handler.job import DRIVER_KIND, ParallelJob

__all__ = ["driver_paths", "build_driver", "start_exploration", "run_worker"]

#: What the driver writes its progress with: the percentage, alone on a line.
#: Nothing else parses the file, so nothing else has to be read out of it.
PROGRESS_PATTERN = r"^\s*([0-9]+)\s*$"


def driver_paths(workspace, session=None):
    """
    Where an exploration keeps what the daemon needs to run it.

    One directory per session, because two explorations can be running at once
    -- the whole point of a session -- and they would otherwise hand each other
    their settings and read each other's progress.
    """
    directory = os.path.join(workspace.paths.work_path, "dse", _slug(session))
    os.makedirs(directory, exist_ok=True)
    return {
        "directory": directory,
        "settings_file": os.path.join(directory, "exploration.yml"),
        "progress_file": os.path.join(directory, "progress.txt"),
    }


def default_session(session=None):
    """
    The daemon session an exploration lives in.

    Every batch goes into the one the driver is itself running in, so that the
    monitor holds the whole exploration rather than one step of it. A run that
    names no session gets one of its own rather than joining whatever was
    running, which is what starting an exploration means.
    """
    session = str(session).strip() if session is not None else ""
    return session or "dse-{0}".format(os.getpid())


def build_driver(workspace, settings, session, paths=None, architectures=None):
    """
    The exploration, as a job the daemon can run.

    Args:
        workspace (Workspace): the workspace being explored.
        settings (DseSettings): what the exploration was asked to do, as the
            command line left it.
        session (str): the daemon session the driver runs in, and enqueues into.
        paths (dict): where its files go (see :func:`driver_paths`).
        architectures (list): what it explores, for the name shown in the
            monitor.

    Returns:
        ParallelJobHandler: the driver, ready to be enqueued.
    """
    from odatix.workspace.settings import save_settings

    paths = paths if paths is not None else driver_paths(workspace, session)

    # The worker reads what the command line already resolved, rather than being
    # handed the flags again: there is one place where what an exploration does
    # is decided, and it is the settings object.
    save_settings(settings, paths["settings_file"], regenerate=True)
    _forget(paths["progress_file"])

    names = list(architectures or settings.architecture_names())
    display_name = "exploration: {0}".format(", ".join(names)) if names else "exploration"

    command = " ".join([
        _quote(sys.executable),
        # Unbuffered, or the log of the job would stay empty until the
        # exploration is over and its output is flushed.
        "-u",
        "-m",
        "odatix.odatix_main",
        "dse",
        "--worker",
        # The log of the driver is the story of the search, from its first line:
        # the banner belongs to the terminal the command was typed in.
        "--nobanner",
        "--config", _quote(paths["settings_file"]),
        "--session", _quote(session),
    ])

    job = ParallelJob(
        process=None,
        command=command,
        directory=workspace.root,
        generate_rtl=False,
        generate_command="",
        target="",
        arch=", ".join(names),
        display_name=display_name,
        status_file="",
        progress_file=paths["progress_file"],
        tmp_dir=paths["directory"],
        log_size_limit=int(settings.log_size_limit),
        kind=DRIVER_KIND,
        progress_pattern=PROGRESS_PATTERN,
    )

    handler = ParallelJobHandler(
        [job],
        nb_jobs=_nb_jobs(settings.nb_jobs),
        process_group=True,
        # The session closes when the exploration is over, which is now what
        # being over means: the driver is the last thing left running.
        auto_exit=bool(settings.exit_when_done),
        log_size_limit=int(settings.log_size_limit),
    )
    return handler


def start_exploration(workspace, settings, session=None, detach=False, architectures=None):
    """
    Hand the exploration to the daemon, and show it the way a run shows its jobs.

    Returns:
        str: the session it runs in.
    """
    from odatix.components.run_common import start_parallel_jobs

    session = default_session(session)
    handler = build_driver(workspace, settings, session, architectures=architectures)
    start_parallel_jobs(handler, detach=detach, session=session)
    return session


def run_worker(workspace, settings, session, cancel_event=None):
    """
    Be the exploration: what the driver job runs.

    Nothing is asked here and nothing is attached: the terminal belongs to the
    monitor, and the batches this enqueues go into the session this is already
    running in.

    Returns:
        list: the archive of each campaign.
    """
    from odatix.dse.campaign import Exploration

    paths = driver_paths(workspace, session)
    exploration = Exploration(
        workspace, settings,
        cancel_event=cancel_event,
        session=session,
        progress_file=paths["progress_file"],
    )
    return exploration.run(confirm=False)


def _nb_jobs(value):
    """How many jobs at once, as a handler wants it: a number, whatever was said."""
    from odatix.lib.utils import resolve_nb_jobs

    try:
        return max(1, int(resolve_nb_jobs(value)))
    except (TypeError, ValueError):
        return 4


def _slug(session):
    """A session name as a directory name, or "current" when there is none."""
    import re

    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(session or "")).strip("-._")
    return slug or "current"


def _quote(text):
    """A path as a shell will read it back."""
    try:
        from shlex import quote
    except ImportError:  # pragma: no cover - Python 2 shells are not supported
        return str(text)
    return quote(str(text))


def _forget(path):
    """Drop what a previous exploration left, so its progress is not read as ours."""
    try:
        os.remove(path)
    except OSError:
        pass

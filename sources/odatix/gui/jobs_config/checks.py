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
The two background phases of a run: checking the settings (which produces the
run plan the popup displays), and preparing the jobs.

Both are one call into :class:`odatix.run.Run`, which is the same run a command
line or a script would start. What is left here is what the page needs of it:
its two phases started in a thread, everything it says collected for the popup,
and its outcome published through prepare_state.
"""

import contextlib

import odatix.lib.printc as printc

from odatix.gui.jobs_config import prepare_state
from odatix.gui.jobs_config.prepare_state import _collect_tool_check
from odatix.run import Run, RunCancelled, RunError


@contextlib.contextmanager
def _collected():
    """
    Everything the run says goes to the popup, not to a terminal nobody is
    watching: the diagnostics as messages, the rest as the run log.
    """
    with printc.collect(prepare_state._prepare_messages.add):
        with contextlib.redirect_stdout(prepare_state._prepare_log_buffer):
            yield


def start_check(mode, workspace, **options):
    """
    Work out what a run would do, without touching anything.

    Args:
        mode (str): the kind of run, as the url names it.
        workspace (Workspace): the workspace it runs in, which is where every
            path it needs comes from.
        **options: what this run does differently from what its settings file
            says (see :class:`odatix.run.RunOptions`), e.g. the eda tool picked
            on the page and the temporary settings file its unsaved state was
            written to.
    """
    try:
        run = Run(
            workspace, mode,
            cancel_event=prepare_state._prepare_cancel_event,
            # From the page a run always resumes where it stopped: re-running an
            # already completed step ("--rerun-from") is a command line thing.
            rerun_from=None,
            **options
        )
        # The eda tool check keeps running in the background instead of blocking
        # this phase, so the run plan shows up without waiting for the tool to
        # start. Its outcome gates the Start button.
        run.tool_check_sink = _collect_tool_check
        prepare_state._prepare_run = run

        with _collected():
            run.check()
        prepare_state._prepare_status = {"status": "checked", "error": None}
    except RunCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except Exception as error:
        prepare_state._prepare_status = {"status": "error", "error": str(error)}


def start_prepare():
    """
    Write the work directory of every job of the run that was checked. Nothing
    is started: enqueueing is what the Start button does.
    """
    run = prepare_state._prepare_run
    try:
        if run is None:
            raise RuntimeError("Missing preparation settings")
        with _collected():
            prepare_state._prepare_parallel_jobs = run.prepare()
        prepare_state._prepare_status = {"status": "prepared", "error": None}
    except RunCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except RunError as error:
        # Jobs that pass the checklist can still fail while their work directory
        # is written (a missing design_path, for instance). When every one of
        # them did, there is nothing left to enqueue.
        prepare_state._prepare_status = {"status": "error", "error": str(error)}
    except Exception as error:
        prepare_state._prepare_status = {"status": "error", "error": str(error)}

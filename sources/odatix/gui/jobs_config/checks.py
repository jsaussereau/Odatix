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
from urllib.parse import quote

import odatix.lib.hard_settings as hard_settings
import odatix.lib.printc as printc
from odatix.lib.parallel_job_handler import daemon_control

from odatix.gui.jobs_config import prepare_state
from odatix.gui.jobs_config.common import _normalize_session_selector
from odatix.gui.jobs_config.prepare_state import _collect_tool_check
from odatix.run import Run, RunCancelled, RunError
from odatix.run.errors import NothingToRun


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
    except NothingToRun as error:
        # Every job is already done or running: not a failure, an answer.
        prepare_state._prepare_status = {"status": "nothing", "error": str(error)}
    except Exception as error:
        prepare_state._prepare_status = {"status": "error", "error": str(error)}


def start_prepare():
    """
    Write the work directory of every job of the run that was checked, then
    hand the jobs over to a session (what the Start button asks for).

    Done in this thread, not in the callback polling the popup: starting a new
    session takes seconds, which held that callback (and the popup) still.
    """
    run = prepare_state._prepare_run
    try:
        if run is None:
            raise RuntimeError("Missing preparation settings")
        with _collected():
            prepare_state._prepare_parallel_jobs = run.prepare()
        prepare_state._prepare_status = {"status": "prepared", "error": None}
        _enqueue_prepared_jobs()
    except RunCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except RunError as error:
        # Jobs that pass the checklist can still fail while their work directory
        # is written (a missing design_path, for instance). When every one of
        # them did, there is nothing left to enqueue.
        prepare_state._prepare_status = {"status": "error", "error": str(error)}
    except Exception as error:
        prepare_state._prepare_status = {"status": "error", "error": str(error)}


def _monitor_href(state):
    """Where the monitor of the session the jobs went to is."""
    session_id = str(state.get("session_id", "")).strip()
    session_name = str(state.get("session_name", "")).strip()
    if session_id:
        href = "/monitor?session=" + quote(session_id, safe="")
    elif session_name:
        href = "/monitor?session=" + quote(session_name, safe="")
    else:
        host = str(state.get("host", hard_settings.daemon_default_host))
        port = int(state.get("port", hard_settings.daemon_default_port))
        href = "/monitor?host={0}&port={1}".format(quote(host, safe=""), port)
    # Where the monitor sends the results of these jobs once they are done:
    # an analysis has its own Explorer page.
    if prepare_state._prepare_synth_type == "analyze":
        href += "&explorer=analysis"
    return href


def _enqueue_prepared_jobs():
    """
    Hand the prepared jobs over to the session picked on the page (a new one
    by default), and publish where its monitor is.
    """
    if prepare_state._prepare_parallel_jobs is None:
        return
    with prepare_state._prepare_enqueue_lock:
        if prepare_state._prepare_enqueued or prepare_state._prepare_monitor_href is not None:
            return
        prepare_state._prepare_enqueued = True
    settings = prepare_state._prepare_runtime_settings
    session = _normalize_session_selector(settings.get("session")) if isinstance(settings, dict) else None
    # Who may use the session, if a new one is started (see enqueue_parallel_jobs).
    try:
        prepare_state._prepare_parallel_jobs.session_access = (
            settings.get("session_access") if isinstance(settings, dict) else None
        )
    except AttributeError:
        pass
    try:
        state, _response = daemon_control.enqueue_parallel_jobs(
            prepare_state._prepare_parallel_jobs,
            session=session,
        )
    except Exception as exc:
        with prepare_state._prepare_enqueue_lock:
            prepare_state._prepare_enqueued = False
        prepare_state._prepare_messages.add("error", "Failed to enqueue jobs in session: {0}".format(exc))
        prepare_state._prepare_status = {"status": "error", "error": str(exc)}
        return
    prepare_state._prepare_monitor_href = _monitor_href(state or {})
    # The jobs are built and in a session: the settings they were built from
    # are no longer read.
    prepare_state._remove_temp_settings_file()
    prepare_state._prepare_status = {"status": "launched", "error": None}

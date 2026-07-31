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
Everything a run of the "Run jobs" page keeps between callbacks: the background
threads, their captured log, the current status, the plan they produced, and the
eda tool checks they started.

The state lives at module level (a run is global to the app, like the daemon it
enqueues into) and is *always* accessed through this module, e.g.
``prepare_state._prepare_status``: importing the names directly would bind a
copy that never sees the updates written by the threads.
"""

import io
import os
import threading

from dash import html

import odatix.components.run_common as run_common
from odatix.lib.run_report import MessageLog

class _ThreadSafeBuffer(io.StringIO):
    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()

    def write(self, s):
        with self._lock:
            return super().write(s)

    def getvalue(self):
        with self._lock:
            return super().getvalue()

    def flush(self):
        with self._lock:
            return super().flush()

_prepare_thread = None
_prepare_cancel_event = threading.Event()
_prepare_log_buffer = _ThreadSafeBuffer()
_prepare_status = {"status": "idle", "error": None}
_prepare_parallel_jobs = None
_prepare_monitor_href = None
_prepare_check_data = None
_prepare_messages = MessageLog()
_prepare_runtime_settings = None
_prepare_exec_thread = None
_prepare_synth_type = None
_prepare_enqueued = False
_prepare_enqueue_lock = threading.Lock()
# Eda tool checks started by the check phase and handed over instead of being
# waited for, so the run plan shows up without waiting for the tool to launch
# (see _tool_check_state and the "EDA tool" stat card of the run popup).
_prepare_tool_checks = []
_prepare_tool_check_reported = False
# Temporary settings file written from the current (unsaved) page state so a run
# uses it without saving; removed at the start of the next run.
_prepare_temp_settings_file = None

def _reset_prepare_state():
    global _prepare_cancel_event, _prepare_log_buffer, _prepare_status, _prepare_parallel_jobs, _prepare_monitor_href
    global _prepare_check_data, _prepare_messages, _prepare_runtime_settings, _prepare_exec_thread, _prepare_synth_type, _prepare_enqueued
    global _prepare_tool_checks, _prepare_tool_check_reported, _prepare_temp_settings_file
    # Remove the previous run's temporary settings file, if any.
    if _prepare_temp_settings_file:
        try:
            os.remove(_prepare_temp_settings_file)
        except OSError:
            pass
        _prepare_temp_settings_file = None
    _prepare_cancel_event = threading.Event()
    _prepare_log_buffer = _ThreadSafeBuffer()
    _prepare_status = {"status": "checking", "error": None}
    _prepare_parallel_jobs = None
    _prepare_monitor_href = None
    _prepare_check_data = None
    _prepare_messages = MessageLog()
    _prepare_runtime_settings = None
    _prepare_exec_thread = None
    _prepare_synth_type = None
    _prepare_enqueued = False
    _prepare_tool_checks = []
    _prepare_tool_check_reported = False
    run_common.reset_prepare_progress()


######################################
# Eda tool check (background)
######################################


def _collect_tool_check(tool_check):
    """
    Sink handed to check_settings(): the eda tool check keeps running in the
    background instead of blocking the check phase, so the run plan is
    displayed as soon as it is known. Its outcome gates the Start button.
    """
    _prepare_tool_checks.append(tool_check)


def _tool_check_state():
    """
    State of the background eda tool checks, or None when there is none:
        status: "running" | "passed" | "failed"
        done/total: how many checks have finished
        tools: the tools still being checked, or the ones that failed
    Never blocks: a check is only read once it is done.
    """
    checks = list(_prepare_tool_checks)
    if not checks:
        return None

    pending = [check for check in checks if check.running()]
    if pending:
        return {
            "status": "running",
            "done": len(checks) - len(pending),
            "total": len(checks),
            "tools": [check.tool for check in pending],
        }

    failed = [check for check in checks if not check.result()[0]]
    return {
        "status": "failed" if failed else "passed",
        "done": len(checks),
        "total": len(checks),
        "tools": [check.tool for check in failed],
    }


def _report_tool_check_failures(state):
    """Add the failed checks to the diagnostics, once per run."""
    global _prepare_tool_check_reported
    if _prepare_tool_check_reported or not state or state["status"] == "running":
        return
    _prepare_tool_check_reported = True
    for check in _prepare_tool_checks:
        if not check.result()[0]:
            _prepare_messages.add("error", check.failure_message())


def _tool_check_card(state):
    """The eda tool check as a stat card, next to the job counts: a live
    "checking" state while the tool starts up, then passed/failed."""
    if state["status"] == "running":
        glyph, style = "⧗", "incomplete"
        count = f"{state['done']}/{state['total']}" if state["total"] > 1 else "…"
        label = "Checking " + ", ".join(state["tools"])
    elif state["status"] == "failed":
        glyph, style = "✗", "failed"
        count = str(len(state["tools"]))
        label = "EDA tool not found: " + ", ".join(state["tools"])
    else:
        glyph, style = "✓", "passed"
        count = str(state["total"])
        label = "EDA tool ready" if state["total"] == 1 else "EDA tools ready"

    return html.Div(
        [
            html.Div(glyph, className="xpa-stat-glyph"),
            html.Div(
                [
                    html.Div(count, className="xpa-stat-count"),
                    html.Div(label, className="xpa-stat-label"),
                ],
                className="xpa-stat-text",
            ),
        ],
        className="xpa-stat-card xpa-" + style,
    )


def _prepare_progress_bar():
    """
    HTML progress bar of the job-preparation phase (copies into the work
    directory, parameter replacements), rendered in the run popup while the
    preparation thread runs. The green section is the jobs prepared
    successfully, the red section the jobs whose preparation failed, with
    ok/failed counts (state published by run_common.PrepareProgress).
    """
    progress = run_common.get_prepare_progress()
    if not progress or progress.get("total", 0) <= 0:
        return ""
    total = progress["total"]
    done = progress.get("done", 0)
    ok = progress.get("ok", 0)
    failed = progress.get("failed", 0)
    ok_pct = 100.0 * ok / total
    failed_pct = 100.0 * failed / total

    counts = [html.Span(f"{done}/{total} jobs prepared")]
    counts.append(html.Span(f"  ✔ {ok}", style={"color": "var(--theme-success-color)", "fontWeight": "600"}))
    if failed > 0:
        counts.append(html.Span(f"  ✘ {failed}", style={"color": "var(--theme-caution-color)", "fontWeight": "600"}))

    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Div(style={"width": f"{ok_pct}%", "background": "var(--theme-success-color)", "transition": "width 0.3s"}),
                    html.Div(style={"width": f"{failed_pct}%", "background": "var(--theme-caution-color)", "transition": "width 0.3s"}),
                ],
                className="jobs-progress-track",
            ),
            html.Div(counts, className="jobs-progress-counts"),
        ],
        style={"margin": "10px 0"},
    )

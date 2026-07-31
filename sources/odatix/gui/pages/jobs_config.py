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

import os
import re
import threading
import io
import contextlib
import itertools
import tempfile
from urllib.parse import quote
import dash
from dash import html, dcc, Input, Output, State, ctx
from typing import Optional, Sequence#, Literal

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url, ansi_to_html_spans
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
import odatix.lib.eda_tools as eda_tools
import odatix.lib.pnr_source as pnr_source
import odatix.lib.printc as printc
import odatix.lib.run_report as run_report
from odatix.lib.run_report import JobPlan, MessageLog
from odatix.lib.settings import OdatixSettings
from odatix.lib.utils import is_auto_nb_jobs, resolve_nb_jobs, AUTO_NB_JOBS_KEYWORD
import odatix.components.run_common as run_common
import odatix.components.run_fmax_synthesis as run_fmax_synthesis
import odatix.components.run_range_synthesis as run_range_synthesis
import odatix.components.run_workflow as run_workflow
import odatix.components.run_simulations as run_simulations
import odatix.components.run_analysis as run_analysis
import odatix.lib.virtual_param_domain as virtual_param_domain
import odatix.components.run_pnr as run_pnr
from odatix.lib.parallel_job_handler import daemon_control

page_path = "/run_jobs"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Job Selection',
    name='Run jobs',
    order=3,
)

MAX_PREVIEW_COMBINATIONS = 10000

# Display labels of the job types the page can be opened with (?type=...),
# shown as a tag in the summary strip of the header.
RUN_MODE_LABELS = {
    "fmax_synthesis": "Fmax synthesis",
    "custom_freq_synthesis": "Custom frequency synthesis",
    "pnr": "Place & route",
    "analyze": "RTL analysis",
    "workflow": "Workflow",
    "simulation": "Simulation",
}

def _analysis_tools():
    """Discovered eda tools that support the RTL analysis job type."""
    return eda_tools.tools_supporting("analysis")


def _analysis_tool_options():
    """Checklist options for the analysis 'Tools' tile, one per discovered tool
    that supports the analysis job type."""
    return [
        {"label": eda_tools.get_tool_label(tool), "value": tool}
        for tool in _analysis_tools()
    ]

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


######################################
# Run popup: structured run plan
######################################

# Per section, beyond this many items the list is truncated: the popup must stay
# usable when a run expands to thousands of configurations.
MAX_SECTION_ITEMS = 200


def _prepare_plan():
    """
    The JobPlan built by the check phase, or None while it has not run yet.
    Every check_settings() returns it as the last element of its result.
    """
    data = _prepare_check_data
    if not data:
        return None
    plan = data[-1]
    return plan if isinstance(plan, JobPlan) else None


def _plan_noun():
    if _prepare_synth_type == "workflow":
        return "workflows"
    if _prepare_synth_type == "simulation":
        return "simulations"
    if _prepare_synth_type == "pnr":
        return "place & route jobs"
    return "architectures"


def _summary_row(glyph, style, title, count, subtitle, items=None, content=None, body_class="", opened=False):
    """
    One collapsible line: a glyph, a title, how many, and the detail folded
    inside. Same shape for diagnostics and for job categories, so the popup
    reads as a single list. `items` is a list of strings rendered as a bullet
    list (diagnostics); `content` is pre-built body children (grouped jobs).
    """
    if content is not None:
        body = content
    else:
        items = items or []
        hidden = max(0, len(items) - MAX_SECTION_ITEMS)
        body = [html.Ul(
            [html.Li(item, className="jobs-plan-item", title=item) for item in items[:MAX_SECTION_ITEMS]],
            className="jobs-plan-items",
        )]
        if hidden:
            body.append(html.Div(f"+ {hidden} more not listed", className="xpa-detail-note"))

    return html.Details(
        children=[
            html.Summary(
                children=[
                    html.Span(glyph, className="xpa-row-badge xpa-" + style),
                    html.Span(title, className="xpa-row-name"),
                    html.Span(subtitle, className="jobs-plan-subtitle") if subtitle else None,
                    html.Span(str(count), className="jobs-plan-count xpa-" + style),
                ],
                className="xpa-row-summary jobs-plan-summary",
            ),
            html.Div(body, className=("xpa-row-body jobs-plan-body " + body_class).strip()),
        ],
        open=opened,
        className="xpa-row xpa-row-" + style,
    )


def _plan_total_card(count, label):
    """A total-style stat card (big number, no glyph) — dashboard style borrowed
    from the analysis page, for the "to run" / "won't run" headline counts."""
    return html.Div(
        [
            html.Div(str(count), className="xpa-stat-count"),
            html.Div(label, className="xpa-stat-label"),
        ],
        className="xpa-stat-card xpa-total",
    )


def _plan_category_card(category, count, total):
    """One stat card per job category present in the plan, styled and labeled
    the same way as its per-card status badge (glyph, label, severity color)."""
    info = run_report.meta(category)
    percent = (100 * count / total) if total else 0
    return html.Div(
        [
            html.Div(info["glyph"], className="xpa-stat-glyph"),
            html.Div(
                [
                    html.Div(str(count), className="xpa-stat-count"),
                    html.Div(info["label"], className="xpa-stat-label"),
                ],
                className="xpa-stat-text",
            ),
            html.Div(f"{percent:.0f}%", className="xpa-stat-percent"),
        ],
        className="xpa-stat-card xpa-" + info["style"],
    )


def _plan_header(plan):
    """Dashboard-style summary: how many jobs will run, how many won't, and the
    breakdown by category — same stat-card look as the Explorer analysis page."""
    counts = plan.counts()
    total = len(plan)
    to_run = plan.run_count()
    skipped = total - to_run

    cards = [_plan_total_card(to_run, _plan_noun().capitalize() + " to run")]
    if skipped:
        cards.append(_plan_total_card(skipped, "Won't run"))
    cards.extend(
        _plan_category_card(category, counts[category], total)
        for category in run_report.SEVERITY_ORDER if counts[category]
    )

    tool_check = _tool_check_state()
    if tool_check is not None:
        cards.append(_tool_check_card(tool_check))

    return html.Div(children=cards, className="jobs-plan-stats xpa-stats")


# Diagnostic rows of the popup: which levels they cover, how they look, and
# whether they start expanded. Errors are what blocks a run, so they show up
# open; tips and notes are grouped in one muted row to keep the list short.
DIAGNOSTIC_ROWS = [
    (("error",), "Errors", "✗", "failed", True),
    (("warning",), "Warnings", "⚠", "warning", False),
    (("tip", "note"), "Notes & tips", "i", "incomplete", False),
]


def _message_rows(message_log):
    """One collapsible row per diagnostic group."""
    rows = []
    for levels, title, glyph, style, opened in DIAGNOSTIC_ROWS:
        messages = [message for level in levels for message in message_log.of_level(level)]
        if not messages:
            continue
        # Count every occurrence, but list each distinct message once (with ×N).
        total = sum(message["count"] for message in messages)
        items = [
            message["message"] + (f"  (×{message['count']})" if message["count"] > 1 else "")
            for message in messages
        ]
        rows.append(_summary_row(
            glyph=glyph,
            style=style,
            title=title,
            count=total,
            subtitle=f"{len(messages)} distinct" if len(messages) != total else None,
            items=items,
            body_class="messages",
            opened=opened,
        ))
    return rows


# A job name reads "Base (target) @ freq (bound)", the base itself being
# "architecture/config". Pull the parenthesized and @-prefixed parts out so jobs
# can be grouped by their characteristics instead of repeating them per row.
_JOB_NAME_PART = re.compile(r"\s*\(([^()]*)\)|\s*(@[^()]*?)(?=\s*\(|\s*$)")

# Beyond this many architecture groups in a category, the rest is summarized.
MAX_PLAN_GROUPS = 60


def _parse_job(name):
    """Split a job display name into architecture, config, target and frequency."""
    base = _JOB_NAME_PART.sub("", name).strip()
    target = freq = None
    for paren, at in _JOB_NAME_PART.findall(name):
        text = (paren or at).strip()
        if not text:
            continue
        # "@ 30 MHz" or a "(250 - 500 MHz)" bound are frequencies; anything else
        # in parentheses is the eda target.
        if text.startswith("@") or text.endswith("MHz"):
            freq = text
        else:
            target = text
    arch, sep, config = base.partition("/")
    if not sep:
        # No base configuration ("arch/config"): a "[domain:value, ...]" suffix is
        # the parameter-domain configuration, not part of the architecture name
        # (e.g. "Example_Rom_Chisel [addr:06bits, data:14bits]").
        bracket = base.find(" [")
        if bracket != -1:
            arch, config = base[:bracket].strip(), base[bracket:].strip()
    return {"arch": arch or base, "config": config, "target": target, "freq": freq}


def _badge(text, kind):
    return html.Span(text, className="jobs-plan-badge " + kind)


def _status_badge(category):
    """Pill on an architecture card telling why it sits in its bucket: the glyph
    and label of its category (New, Overwritten, Existing, ...), colored by style."""
    info = run_report.meta(category)
    return html.Span(
        children=[
            html.Span(info["glyph"], className="jobs-plan-status-glyph"),
            html.Span(info["label"]),
        ],
        className="jobs-plan-status xpa-" + info["style"],
        title=info["description"],
    )


def _shared(jobs, key):
    """The value of `key` if every job shares it, else None."""
    values = {job[key] for job in jobs}
    return next(iter(values)) if len(values) == 1 and None not in values else None


def _group_span_class(config_count):
    """
    How many grid columns a card should claim, as a CSS class. A card with many
    configs is allowed to grow wider so its config list flows into several inner
    columns instead of stacking into one tall, narrow strip — this keeps a mix of
    small and large groups evenly spread across the width. Cards without a config
    list (config_count <= 1) always stay a single column.
    """
    if config_count >= 40:
        return "span-3"
    if config_count >= 12:
        return "span-2"
    return ""


def _job_group(arch, jobs, style, category=None):
    """
    A fancy card for one architecture: its name, a status badge telling why it is
    in its bucket, the characteristics common to all of its jobs as badges, a
    count, and the configs that differ underneath.
    """
    shared_target = _shared(jobs, "target")
    shared_freq = _shared(jobs, "freq")

    head_badges = []
    if shared_target:
        head_badges.append(_badge(shared_target, "target"))
    if shared_freq:
        head_badges.append(_badge(shared_freq, "freq"))

    # Title line: the full name and the name-derived characteristics (target,
    # frequency), then the config count on the right. The status badge — why the
    # card is in its bucket — goes on its own line below, so the two kinds of
    # badge never read as one row.
    title = html.Div(
        children=[
            html.Span(arch, className="jobs-plan-group-name", title=arch),
            *head_badges,
        ],
        className="jobs-plan-group-title",
    )
    head_children = [title]
    meta_badges = []
    if category is not None:
        meta_badges.append(_status_badge(category))
    meta_badges.append(
        html.Span(f"{len(jobs)} config" + ("s" if len(jobs) != 1 else ""), className="jobs-plan-group-count-badge")
    )
    head_children.append(html.Span(meta_badges, className="jobs-plan-group-badges"))
    head = html.Div(head_children, className="jobs-plan-group-head")

    # Only list configs when there is more than the architecture itself to show.
    only_arch = len(jobs) == 1 and not jobs[0]["config"]
    if only_arch and not (jobs[0]["target"] and not shared_target):
        return html.Div(head, className="jobs-plan-group")

    rows = []
    for job in jobs:
        badges = []
        if job["target"] and not shared_target:
            badges.append(_badge(job["target"], "target"))
        if job["freq"] and not shared_freq:
            badges.append(_badge(job["freq"], "freq"))
        rows.append(html.Li(
            children=[html.Span(job["config"] or "default", className="jobs-plan-config"), *badges],
            className="jobs-plan-config-row",
        ))

    span = _group_span_class(len(rows))
    return html.Div(
        children=[head, html.Ul(rows, className="jobs-plan-configs")],
        className=("jobs-plan-group " + span).strip(),
    )


def _bucket_entries(plan, want_run):
    """(name, category) of every job whose category will/won't run, most severe
    category first, matching the severity order used everywhere else."""
    entries = []
    for category in run_report.SEVERITY_ORDER:
        if run_report.runs(category) != want_run:
            continue
        for name in plan.names(category, colored=False):
            entries.append((name, category))
    return entries


def _bucket_content(entries):
    """Group a bucket's jobs into architecture cards, one card per (architecture,
    category) so every card carries a single, truthful status badge. Cards of the
    same architecture stay adjacent, ordered by category severity."""
    groups = {}
    arch_order = []
    for name, category in entries:
        job = _parse_job(name)
        key = (job["arch"], category)
        if key not in groups:
            groups[key] = []
            if job["arch"] not in arch_order:
                arch_order.append(job["arch"])
        groups[key].append(job)

    ordered_keys = sorted(
        groups,
        key=lambda key: (arch_order.index(key[0]), run_report.meta(key[1])["severity"]),
    )
    content = [
        _job_group(arch, groups[(arch, category)], run_report.meta(category)["style"], category=category)
        for arch, category in ordered_keys[:MAX_PLAN_GROUPS]
    ]
    hidden = len(ordered_keys) - len(content)
    if hidden > 0:
        content.append(html.Div(f"+ {hidden} more not listed", className="xpa-detail-note"))
    return content


# The two run-plan buckets. Jobs are no longer split into one row per status;
# they fall into just these two, and the reason each job is here (its category:
# new, cached, invalid, ...) is shown as a status badge on its card.
# (want_run, title, glyph, style, opened)
PLAN_BUCKETS = [
    (True, "Will run", "▸", "passed", True),
    (False, "Won't run", "⊘", "incomplete", False),
]


def _job_rows(plan):
    """The two bucket rows — jobs that will run and jobs that are skipped — each
    with its architecture cards grouped and status-badged by category."""
    counts = plan.counts()
    rows = []
    for want_run, title, glyph, style, opened in PLAN_BUCKETS:
        entries = _bucket_entries(plan, want_run)
        if not entries:
            continue
        labels = [
            run_report.meta(category)["label"]
            for category in run_report.SEVERITY_ORDER
            if run_report.runs(category) == want_run and counts[category]
        ]
        rows.append(_summary_row(
            glyph=glyph,
            style=style,
            title=title,
            count=len(entries),
            subtitle=", ".join(labels),
            content=_bucket_content(entries),
            body_class="groups",
            opened=opened,
        ))
    return rows


def _section(title, rows):
    if not rows:
        return None
    return html.Div(
        children=[html.Div(title, className="jobs-plan-section-title"), html.Div(rows, className="jobs-plan-rows")],
        className="jobs-plan-section",
    )


def _run_popup_body(status):
    """
    Content of the run popup, entirely built from the structured report the run
    scripts produce: a headline, the diagnostics, and the jobs, each foldable.
    """
    plan = _prepare_plan()
    children = []

    if plan:
        children.append(_plan_header(plan))
    else:
        # The eda tool check outlives the check phase: show its card even when
        # there is no plan to display yet.
        tool_check = _tool_check_state()
        if tool_check is not None:
            children.append(html.Div([_tool_check_card(tool_check)], className="jobs-plan-stats xpa-stats"))

    children.append(_section("Diagnostics", _message_rows(_prepare_messages)))
    if plan:
        children.append(_section(_plan_noun().capitalize(), _job_rows(plan)))
    elif status in ("checking", "preparing"):
        children.append(html.Div("Checking settings…", className="jobs-plan-placeholder"))
    elif not _prepare_messages:
        children.append(html.Div("No job found for this selection.", className="jobs-plan-placeholder"))

    return html.Div([child for child in children if child is not None], className="jobs-plan")


def _run_popup_render_key(status):
    """
    Cheap signature of what the popup body displays. The popup is refreshed on a
    timer: re-rendering identical content would fold the sections back under the
    user while they are reading them.
    """
    plan = _prepare_plan()
    tool_check = _tool_check_state() or {}
    return "|".join([
        str(status),
        str(len(plan) if plan else 0),
        str(len(_prepare_messages)),
        str(tool_check.get("status")),
        str(tool_check.get("done")),
    ])


def _normalize_session_selector(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text == "__new_session__":
        return None
    return text


def _session_option(daemon: dict) -> dict:
    host = str(daemon.get("host", hard_settings.daemon_default_host))
    port = int(daemon.get("port", hard_settings.daemon_default_port))
    session_id = str(daemon.get("session_id", "")).strip()
    session_name = str(daemon.get("session_name", "")).strip()

    value = session_id or session_name or f"{host}:{port}"
    label = session_id or session_name or f"{host}:{port}"
    return {
        "label": label,
        "value": value,
        "title": f"{host}:{port}",
    }

def _run_check_custom_freq_settings(
    run_config_settings_filename,
    arch_path,
    tool,
    flow,
    until_step,
    work_path,
    target_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
    check_eda_tool,
    custom_freq_list=None,
):
    global _prepare_status, _prepare_check_data
    if custom_freq_list is None:
        custom_freq_list = []
    try:
        with printc.collect(_prepare_messages.add), contextlib.redirect_stdout(_prepare_log_buffer):
            _prepare_check_data = run_range_synthesis.check_settings(
                run_config_settings_filename,
                arch_path,
                tool,
                flow,
                until_step,
                # Re-running an already completed step ("--rerun-from") is
                # CLI-only: from the GUI a run always resumes where it stopped.
                None,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                check_eda_tool,
                custom_freq_list=custom_freq_list,
                debug=False,
                keep=False,
                cancel_event=_prepare_cancel_event,
                tool_check_sink=_collect_tool_check,
            )
        _prepare_status = {"status": "checked", "error": None}
    except run_range_synthesis.SynthesisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _run_check_pnr_settings(
    run_config_settings_filename,
    source_work_root,
    tool,
    flow,
    until_step,
    work_path,
    target_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
    check_eda_tool,
    source_result_types=None,
):
    global _prepare_status, _prepare_check_data
    try:
        with printc.collect(_prepare_messages.add), contextlib.redirect_stdout(_prepare_log_buffer):
            _prepare_check_data = run_pnr.check_settings(
                run_config_settings_filename=run_config_settings_filename,
                source_work_root=source_work_root,
                tool=tool,
                flow=flow,
                until_step=until_step,
                # Re-running an already completed step ("--rerun-from") is
                # CLI-only: from the GUI a run always resumes where it stopped.
                rerun_from_step=None,
                work_path=work_path,
                target_path=target_path,
                overwrite=overwrite_enabled,
                noask=noask,
                exit_when_done=exit_when_done_enabled,
                log_size_limit=log_size_val,
                nb_jobs=nb_jobs_val,
                check_eda_tool=check_eda_tool,
                source_result_types=source_result_types,
                debug=False,
                cancel_event=_prepare_cancel_event,
                tool_check_sink=_collect_tool_check,
            )
        _prepare_status = {"status": "checked", "error": None}
    except run_pnr.PnrCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _run_check_fmax_settings(
    run_config_settings_filename,
    arch_path,
    tool,
    flow,
    until_step,
    work_path,
    target_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
    continue_on_error,
    check_eda_tool,
):
    global _prepare_status, _prepare_check_data
    try:
        with printc.collect(_prepare_messages.add), contextlib.redirect_stdout(_prepare_log_buffer):
            _prepare_check_data = run_fmax_synthesis.check_settings(
                run_config_settings_filename,
                arch_path,
                tool,
                flow,
                until_step,
                # Re-running an already completed step ("--rerun-from") is
                # CLI-only: from the GUI a run always resumes where it stopped.
                None,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                continue_on_error,
                check_eda_tool,
                forced_fmax_lower_bound=None,
                forced_fmax_upper_bound=None,
                debug=False,
                keep=False,
                cancel_event=_prepare_cancel_event,
                tool_check_sink=_collect_tool_check,
            )
        _prepare_status = {"status": "checked", "error": None}
    except run_fmax_synthesis.SynthesisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _run_check_analysis_settings(
    run_config_settings_filename,
    arch_path,
    tool,
    flow,
    work_path,
    target_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
    check_eda_tool,
):
    global _prepare_status, _prepare_check_data
    try:
        with printc.collect(_prepare_messages.add), contextlib.redirect_stdout(_prepare_log_buffer):
            _prepare_check_data = run_analysis.check_settings(
                run_config_settings_filename,
                arch_path,
                tool,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                check_eda_tool,
                debug=False,
                keep=False,
                cancel_event=_prepare_cancel_event,
                tool_check_sink=_collect_tool_check,
                flows=run_analysis.parse_flow_selection([flow] if flow else None, tool if isinstance(tool, (list, tuple)) else [tool]),
            )
        _prepare_status = {"status": "checked", "error": None}
    except run_analysis.AnalysisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except SystemExit:
        # check_settings() calls sys.exit(-1) when there is no valid architecture
        # to analyze: turn that into a normal error status.
        _prepare_status = {"status": "error", "error": "No valid architecture to analyze. See log above for details."}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _run_check_workflow_settings(
    run_config_settings_filename,
    workflow_path,
    work_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
):
    global _prepare_status, _prepare_check_data
    try:
        with printc.collect(_prepare_messages.add), contextlib.redirect_stdout(_prepare_log_buffer):
            _prepare_check_data = run_workflow.check_settings(
                run_config_settings_filename,
                workflow_path,
                work_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                debug=False,
                keep=False,
            )
        _prepare_status = {"status": "checked", "error": None}
    except SystemExit:
        # check_settings() calls sys.exit(-1) on invalid workflow settings
        # instead of raising: turn that into a normal error status.
        _prepare_status = {"status": "error", "error": "Invalid workflow settings. See log above for details."}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _run_check_simulation_settings(
    run_config_settings_filename,
    arch_path,
    sim_path,
    work_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
):
    global _prepare_status, _prepare_check_data
    try:
        with printc.collect(_prepare_messages.add), contextlib.redirect_stdout(_prepare_log_buffer):
            _prepare_check_data = run_simulations.check_settings(
                run_config_settings_filename=run_config_settings_filename,
                arch_path=arch_path,
                sim_path=sim_path,
                work_path=work_path,
                overwrite=overwrite_enabled,
                noask=noask,
                exit_when_done=exit_when_done_enabled,
                log_size_limit=log_size_val,
                nb_jobs=nb_jobs_val,
                debug=False,
                keep=False,
            )
        _prepare_status = {"status": "checked", "error": None}
    except SystemExit:
        # check_settings() calls sys.exit(-1) on invalid simulation settings
        # instead of raising: turn that into a normal error status.
        _prepare_status = {"status": "error", "error": "Invalid simulation settings. See log above for details."}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _run_prepare_synthesis():
    global _prepare_status, _prepare_parallel_jobs
    try:
        if not _prepare_check_data:
            raise RuntimeError("Missing preparation settings")
        # Per-job export context captured at run time (see the run callback);
        # it lets prepare_* tag every job so the daemon exports results as jobs
        # finish (au fil de l'eau).
        export_ctx = {}
        if isinstance(_prepare_runtime_settings, dict):
            export_ctx = _prepare_runtime_settings.get("export") or {}
        with printc.collect(_prepare_messages.add), contextlib.redirect_stdout(_prepare_log_buffer):
            if _prepare_synth_type == "simulation":
                (
                    simulation_instances,
                    prepare_job,
                    job_list,
                    exit_when_done,
                    log_size_limit,
                    nb_jobs,
                    _plan,
                ) = _prepare_check_data
                _prepare_parallel_jobs = run_simulations.prepare_simulations(
                    simulation_instances=simulation_instances,
                    prepare_job=prepare_job,
                    job_list=job_list,
                    exit_when_done=exit_when_done,
                    log_size_limit=log_size_limit,
                    nb_jobs=nb_jobs,
                    export_output_dir=export_ctx.get("output_dir"),
                    export_work_root=export_ctx.get("work_root"),
                    export_sim_path=export_ctx.get("sim_path"),
                )
            elif _prepare_synth_type == "workflow":
                (
                    workflow_instances,
                    prepare_job,
                    job_list,
                    exit_when_done,
                    log_size_limit,
                    nb_jobs,
                    _plan,
                ) = _prepare_check_data
                _prepare_parallel_jobs = run_workflow.prepare_workflows(
                    workflow_instances=workflow_instances,
                    prepare_job=prepare_job,
                    job_list=job_list,
                    exit_when_done=exit_when_done,
                    log_size_limit=log_size_limit,
                    nb_jobs=nb_jobs,
                    export_output_dir=export_ctx.get("output_dir"),
                    export_work_root=export_ctx.get("work_root"),
                    export_workflow_path=export_ctx.get("workflow_path"),
                )
            else:
                (
                    architecture_instances,
                    prepare_job,
                    job_list,
                    tool_settings_file,
                    arch_handler,
                    exit_when_done,
                    log_size_limit,
                    nb_jobs,
                    _plan,
                ) = _prepare_check_data
                if _prepare_synth_type == "fmax_synthesis":
                    _prepare_parallel_jobs = run_fmax_synthesis.prepare_synthesis(
                        architecture_instances=architecture_instances,
                        prepare_job=prepare_job,
                        job_list=job_list,
                        tool_settings_file=tool_settings_file,
                        arch_handler=arch_handler,
                        exit_when_done=exit_when_done,
                        log_size_limit=log_size_limit,
                        nb_jobs=nb_jobs,
                        cancel_event=_prepare_cancel_event,
                        export_output_dir=export_ctx.get("output_dir"),
                        export_tool=export_ctx.get("tool"),
                        export_flow=export_ctx.get("flow"),
                        export_work_path=export_ctx.get("work_path"),
                        use_benchmark=export_ctx.get("use_benchmark", False),
                        benchmark_file=export_ctx.get("benchmark_file"),
                    )
                elif _prepare_synth_type == "pnr":
                    # Explicit rather than left to the fallback below: a place &
                    # route batch sent to run_range_synthesis would be exported
                    # as custom frequency synthesis results, writing wrong
                    # records without ever failing.
                    _prepare_parallel_jobs = run_pnr.prepare_pnr(
                        architecture_instances=architecture_instances,
                        prepare_job=prepare_job,
                        job_list=job_list,
                        tool_settings_file=tool_settings_file,
                        arch_handler=arch_handler,
                        exit_when_done=exit_when_done,
                        log_size_limit=log_size_limit,
                        nb_jobs=nb_jobs,
                        cancel_event=_prepare_cancel_event,
                        export_output_dir=export_ctx.get("output_dir"),
                        export_tool=export_ctx.get("tool"),
                        export_flow=export_ctx.get("flow"),
                        export_work_path=export_ctx.get("work_path"),
                        use_benchmark=export_ctx.get("use_benchmark", False),
                        benchmark_file=export_ctx.get("benchmark_file"),
                    )
                elif _prepare_synth_type == "analyze":
                    _prepare_parallel_jobs = run_analysis.prepare_synthesis(
                        architecture_instances=architecture_instances,
                        prepare_job=prepare_job,
                        job_list=job_list,
                        tool_settings_file=tool_settings_file,
                        arch_handler=arch_handler,
                        exit_when_done=exit_when_done,
                        log_size_limit=log_size_limit,
                        nb_jobs=nb_jobs,
                        cancel_event=_prepare_cancel_event,
                        export_output_dir=export_ctx.get("output_dir"),
                        analysis_work_root=export_ctx.get("analysis_work_root"),
                        flows=export_ctx.get("flows"),
                    )
                else:
                    _prepare_parallel_jobs = run_range_synthesis.prepare_synthesis(
                        architecture_instances=architecture_instances,
                        prepare_job=prepare_job,
                        job_list=job_list,
                        tool_settings_file=tool_settings_file,
                        arch_handler=arch_handler,
                        exit_when_done=exit_when_done,
                        log_size_limit=log_size_limit,
                        nb_jobs=nb_jobs,
                        cancel_event=_prepare_cancel_event,
                        export_output_dir=export_ctx.get("output_dir"),
                        export_tool=export_ctx.get("tool"),
                        export_flow=export_ctx.get("flow"),
                        export_work_path=export_ctx.get("work_path"),
                        use_benchmark=export_ctx.get("use_benchmark", False),
                        benchmark_file=export_ctx.get("benchmark_file"),
                    )
        _prepare_status = {"status": "prepared", "error": None}
    except run_range_synthesis.SynthesisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except run_fmax_synthesis.SynthesisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except run_analysis.AnalysisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except run_pnr.PnrCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except SystemExit:
        # abort_if_empty_job_list() calls sys.exit(-1) when every selected job
        # failed while being built (e.g. a missing design_path): turn that into
        # a normal error status instead of silently launching an empty session.
        _prepare_status = {"status": "error", "error": "None of the selected jobs could be prepared. See log above for details."}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _checklist_enabled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return True in value or len(value) > 0
    return bool(value)

def _to_int(value, default):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default

# The "Job Settings" fields, with the defaults used both to initialize the
# widgets (job_settings_form) and to build the saved baseline, so a fresh load
# never falsely reports "unsaved changes".
_JOB_SETTINGS_DEFAULTS = {
    "overwrite": False,
    "force_single_thread": True,
    "nb_jobs": 8,
    "log_size_limit": 300,
    "ask_continue": True,
    "exit_when_done": False,
}

def _nb_jobs_setting(nb_jobs, auto_enabled):
    """Return the persisted nb_jobs value: the "auto" keyword when the Auto
    switch is on, otherwise the integer entered in the widget."""
    if auto_enabled:
        return AUTO_NB_JOBS_KEYWORD
    return _to_int(nb_jobs, _JOB_SETTINGS_DEFAULTS["nb_jobs"])

def _job_settings_current(overwrite, force_single_thread, nb_jobs, log_size_limit, ask_continue, exit_when_done, auto_nb_jobs=None) -> dict:
    """Job Settings as edited in the widgets (used for the 'current' selection)."""
    return {
        "overwrite": _checklist_enabled(overwrite),
        "force_single_thread": _checklist_enabled(force_single_thread),
        "nb_jobs": _nb_jobs_setting(nb_jobs, _checklist_enabled(auto_nb_jobs)),
        "log_size_limit": _to_int(log_size_limit, _JOB_SETTINGS_DEFAULTS["log_size_limit"]),
        "ask_continue": _checklist_enabled(ask_continue),
        "exit_when_done": _checklist_enabled(exit_when_done),
    }

def _collect_run_settings(
    run_mode,
    selection_key,
    switch_values,
    switch_ids,
    preview_values,
    preview_ids,
    overwrite,
    force_single_thread,
    nb_jobs,
    auto_nb_jobs,
    log_size_limit,
    ask_continue,
    exit_when_done,
    override_arch_frequencies,
    use_custom_freq_list,
    target_frequencies,
    use_custom_freq_range,
    from_frequency,
    to_frequency,
    step_frequency,
    lower_bound,
    upper_bound,
    analysis_tools,
    sim_selection_values=None,
    sim_selection_ids=None,
) -> dict:
    """
    Build the settings dict that reflects the current, possibly unsaved, state of
    the page: the enabled architectures/configurations, the job settings, and the
    mode-specific frequency/tool fields. Shared by the "Save" callback and the
    "Run" callback (which writes it to a temporary file to run without saving).
    """
    if run_mode == "simulation":
        # Simulations hold a mapping, not a flat list (see
        # _collect_simulation_selection), so they short-circuit the shared
        # architecture/preview flattening below.
        return {
            selection_key: _collect_simulation_selection(
                switch_values, switch_ids, sim_selection_values, sim_selection_ids
            ),
            **_job_settings_current(
                overwrite, force_single_thread, nb_jobs, log_size_limit, ask_continue, exit_when_done,
                auto_nb_jobs=auto_nb_jobs,
            ),
        }

    if run_mode == "pnr":
        # Place & route cards hold their selection in the same per-instance store
        # simulations use (see _pnr_job_sections), but write it as the flat
        # selector list the settings file expects.
        enabled_tools = {
            sid.get("arch")
            for value, sid in zip(switch_values or [], switch_ids or [])
            if isinstance(sid, dict) and bool(value)
        }
        selectors = []
        for value, pid in zip(sim_selection_values or [], sim_selection_ids or []):
            if not isinstance(pid, dict) or pid.get("sim") not in enabled_tools:
                continue
            selectors.extend(str(entry) for entry in (value or []) if entry is not None)
        return {
            selection_key: list(dict.fromkeys(selectors)),
            **_job_settings_current(
                overwrite, force_single_thread, nb_jobs, log_size_limit, ask_continue, exit_when_done,
                auto_nb_jobs=auto_nb_jobs,
            ),
        }

    preview_by_arch = {}
    for val, pid in zip(preview_values or [], preview_ids or []):
        arch = pid.get("arch") if isinstance(pid, dict) else None
        if arch:
            preview_by_arch[arch] = list(val or [])

    architectures = []
    for val, sid in zip(switch_values or [], switch_ids or []):
        arch = sid.get("arch") if isinstance(sid, dict) else None
        if arch and bool(val):
            for item in preview_by_arch.get(arch, []):
                if item is not None:
                    architectures.append(str(item))
    # Remove duplicates but keep order
    architectures = list(dict.fromkeys(architectures))

    current_settings = {
        selection_key: architectures,
        **_job_settings_current(overwrite, force_single_thread, nb_jobs, log_size_limit, ask_continue, exit_when_done, auto_nb_jobs=auto_nb_jobs),
    }
    if run_mode == "custom_freq_synthesis":
        current_settings["frequencies"] = workspace.create_custom_frequencies_settings_dict(
            _checklist_enabled(override_arch_frequencies),
            target_frequencies,
            from_frequency,
            to_frequency,
            step_frequency,
            use_custom_freq_list=_checklist_enabled(use_custom_freq_list),
            use_custom_freq_range=_checklist_enabled(use_custom_freq_range),
        )
    if run_mode == "fmax_synthesis":
        current_settings["fmax_synthesis"] = workspace.create_fmax_bounds_settings_dict(
            lower_bound,
            upper_bound,
            override_enabled=_checklist_enabled(override_arch_frequencies),
        )
    if run_mode == "analyze":
        current_settings["tools"] = [tool for tool in (analysis_tools or []) if tool]

    return current_settings


def _write_temp_run_settings(settings_path, current_settings, run_mode, use_custom_freq_list, use_custom_freq_range):
    """
    Write the current (unsaved) page settings to a temporary settings file so a
    run can use them without touching the real settings file, and return its
    path. The real file's other keys are preserved (loaded and overlaid).
    """
    base_settings = workspace.load_arch_selection_settings(settings_path) if settings_path else {}
    payload = {**(base_settings or {}), **current_settings}

    fd, temp_path = tempfile.mkstemp(prefix="odatix_run_", suffix=".yml")
    os.close(fd)
    workspace.save_architecture_selection(
        temp_path,
        payload,
        run_mode=run_mode,
        use_custom_freq_list=use_custom_freq_list,
        use_custom_freq_range=use_custom_freq_range,
    )
    return temp_path


def _job_settings_baseline(settings: dict) -> dict:
    """Job Settings as loaded from the settings file (used for the saved
    baseline). Must mirror how job_settings_form() initializes the widgets."""
    settings = settings or {}
    nb_jobs_raw = settings.get("nb_jobs", _JOB_SETTINGS_DEFAULTS["nb_jobs"])
    return {
        "overwrite": bool(settings.get("overwrite", _JOB_SETTINGS_DEFAULTS["overwrite"])),
        "force_single_thread": bool(settings.get("force_single_thread", _JOB_SETTINGS_DEFAULTS["force_single_thread"])),
        "nb_jobs": AUTO_NB_JOBS_KEYWORD if is_auto_nb_jobs(nb_jobs_raw) else _to_int(nb_jobs_raw, _JOB_SETTINGS_DEFAULTS["nb_jobs"]),
        "log_size_limit": _to_int(settings.get("log_size_limit", _JOB_SETTINGS_DEFAULTS["log_size_limit"]), _JOB_SETTINGS_DEFAULTS["log_size_limit"]),
        "ask_continue": bool(settings.get("ask_continue", _JOB_SETTINGS_DEFAULTS["ask_continue"])),
        "exit_when_done": bool(settings.get("exit_when_done", _JOB_SETTINGS_DEFAULTS["exit_when_done"])),
    }

def _get_synth_settings_path(search: str, odatix_settings: dict) -> str:
    run_mode = get_key_from_url(search, "type")
    if run_mode == "custom_freq_synthesis":
        return odatix_settings.get(
            "custom_freq_synthesis_settings_file",
            OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_SETTINGS_FILE,
        )
    if run_mode == "fmax_synthesis":
        return odatix_settings.get(
            "fmax_synthesis_settings_file",
            OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
        )
    if run_mode == "pnr":
        return odatix_settings.get(
            "pnr_settings_file",
            OdatixSettings.DEFAULT_PNR_SETTINGS_FILE,
        )
    if run_mode == "analyze":
        return odatix_settings.get(
            "analysis_settings_file",
            OdatixSettings.DEFAULT_ANALYSIS_SETTINGS_FILE,
        )
    if run_mode == "simulation":
        return odatix_settings.get(
            "simulation_settings_file",
            OdatixSettings.DEFAULT_SIMULATION_SETTINGS_FILE,
        )
    if run_mode == "workflow":
        # Without this, the Job Settings form of a workflow run would be filled
        # from the fmax synthesis settings file while the selection is saved to
        # the workflow one: the page would always claim "unsaved changes" and
        # Save would overwrite the workflow settings with the fmax values.
        return odatix_settings.get(
            "workflow_settings_file",
            OdatixSettings.DEFAULT_WORKFLOW_SETTINGS_FILE,
        )
    return odatix_settings.get(
        "fmax_synthesis_settings_file",
        OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
    )

######################################
# Place & route mode
######################################
#
# A place & route run is the only job type whose input is not in the workspace
# configuration but in the work tree: it starts from synthesis jobs that have
# already run and succeeded, possibly with another eda tool (see
# odatix.lib.pnr_source).
#
# The page keeps the shape a simulation has: one card per eda tool, holding one
# nested card per architecture that tool synthesized, where the completed jobs
# are picked with the very same widgets an architecture gets everywhere else —
# one panel per parameter domain plus the preview checklist.
#
# There is nothing to *combine* here though (what a job is was decided by the
# synthesis): the domains are read back from what is on disk, by splitting the
# work directory names of the sources, and checking a domain value selects the
# sources that have it rather than generating a new combination.


def _pnr_tool_of(work_dirname):
    """The eda tool a work directory name belongs to ("genus@fast" -> "genus")."""
    return eda_tools.split_tool_work_dirname(str(work_dirname))[0]


def _pnr_sources_by_tool(work_root, odatix_settings):
    """
    The completed synthesis jobs of the workspace, grouped by the work directory
    of the tool that produced them ("design_compiler", "genus@fast", ...).

    Jobs that did not write the handoff files are listed too, so a synthesis that
    cannot be placed & routed shows up as unusable rather than silently missing.
    """
    result_types = None
    if isinstance(odatix_settings, dict):
        result_types = {
            job_type: {"path": odatix_settings.get(f"{job_type}_work_path") or job_type}
            for job_type in pnr_source.SOURCE_JOB_TYPES
        }

    grouped = {}
    for source in pnr_source.discover_sources(work_root, result_types=result_types, require_handoff=False):
        grouped.setdefault(source.work_dirname, []).append(source)
    return grouped


def _group_pnr_selections(sources_setting, work_dirnames) -> dict:
    """
    Group the saved selectors by the card they belong to, i.e. by the work
    directory of the tool that ran the synthesis.

    The generic _group_arch_selections cannot be used here for two reasons: the
    first "/"-separated segment of a selector is the source job type, not the
    tool, and a selector may name the tool with a wildcard, in which case it
    belongs to *every* card rather than to one named "*" (which would leave them
    all switched off while the settings file selects them).
    """
    grouped = {}
    for entry in sources_setting or []:
        if entry is None:
            continue
        parsed = pnr_source.parse_selector(str(entry))
        if parsed is None:
            continue
        if parsed["work_dirname"] == pnr_source.WILDCARD:
            targets = list(work_dirnames)
        else:
            targets = [parsed["work_dirname"]]
        for work_dirname in targets:
            grouped.setdefault(work_dirname, []).append(str(entry))
    return grouped


# The levels of a source that are not parameter domains but still tell two
# sources apart. They get a panel of their own, keyed with a "@" prefix so they
# can never collide with the name of a real parameter domain.
PNR_JOB_TYPE_DOMAIN = "@job_type"
PNR_TARGET_DOMAIN = "@target"
PNR_FREQUENCY_DOMAIN = "@frequency"

PNR_DOMAIN_TITLES = {
    PNR_JOB_TYPE_DOMAIN: "Synthesis type",
    PNR_TARGET_DOMAIN: "Target",
    PNR_FREQUENCY_DOMAIN: "Frequency",
}


def _pnr_split_config_token(token, known_domains):
    """
    Split a "<domain>_<configuration>" token of a work directory name back into
    the domain and the configuration it was built from (see
    ArchitectureHandler: the work directory of a configuration with parameter
    domains is "<config>+<domain>_<value>+...").

    The separator is also a legal character of both names, so the known domains
    of the architecture are tried first, longest first; the split falls back to
    the first "_" for an architecture that does not exist anymore.
    """
    for domain in sorted(known_domains or [], key=len, reverse=True):
        prefix = str(domain) + "_"
        if token.startswith(prefix):
            return str(domain), token[len(prefix):]
    domain, _, value = token.partition("_")
    return domain, value


def _pnr_source_tokens(source, known_domains):
    """The domain -> value mapping describing one source: its parameter domains,
    read back from the work directory name, plus the levels above it."""
    tokens = {
        PNR_JOB_TYPE_DOMAIN: source.job_type,
        PNR_TARGET_DOMAIN: source.target,
        PNR_FREQUENCY_DOMAIN: source.frequency_segment,
    }
    parts = [part for part in str(source.configuration).split("+") if part]
    if parts:
        tokens[hard_settings.main_parameter_domain] = parts[0]
    for part in parts[1:]:
        domain, value = _pnr_split_config_token(part, known_domains)
        if domain and value:
            tokens[domain] = value
    return tokens


def _pnr_domain_values(tokens_by_selector, known_domains):
    """
    The panels an architecture card shows, in display order: its main parameter
    domain, its parameter domains, then the target and the frequency. A level
    every source of the card shares says nothing (a single chip to pick from),
    so only the synthesis type is dropped when it is uniform — the target and
    the frequency are kept, they are what a place & route job is named after.
    """
    values = {}
    for tokens in tokens_by_selector.values():
        for domain, value in tokens.items():
            values.setdefault(domain, set()).add(value)

    order = [hard_settings.main_parameter_domain]
    order += [domain for domain in (known_domains or []) if domain in values]
    order += [domain for domain in sorted(values) if domain not in order and not domain.startswith("@")]
    order += [PNR_TARGET_DOMAIN, PNR_FREQUENCY_DOMAIN, PNR_JOB_TYPE_DOMAIN]

    ordered = {}
    for domain in order:
        if domain not in values:
            continue
        if domain == PNR_JOB_TYPE_DOMAIN and len(values[domain]) < 2:
            continue
        ordered[domain] = sorted(values[domain])
    return ordered


def _pnr_domain_title(domain):
    if domain in PNR_DOMAIN_TITLES:
        return PNR_DOMAIN_TITLES[domain]
    if domain == hard_settings.main_parameter_domain:
        return "Main parameter domain"
    return domain


def _pnr_value_label(domain, value):
    """A domain value as a chip reads it. Only the frequency needs help: it is
    stored as the work directory name ("50MHz", or "fmax" for an fmax search)."""
    if domain == PNR_FREQUENCY_DOMAIN and value.endswith("MHz"):
        return value[: -len("MHz")] + " MHz"
    return value


def _pnr_source_label(source):
    """How a source reads in the preview checklist of its architecture card (the
    architecture itself is the card, so it is not repeated)."""
    label = source.configuration + "  ·  " + source.target
    if source.frequency is not None:
        label += "  ·  " + str(source.frequency) + " MHz"
    else:
        label += "  ·  fmax"
    return label


def _pnr_unusable_badge_text(n_unusable: int) -> str:
    """The badge counting the synthesis jobs left out of an architecture card
    because they handed no netlist over."""
    word = "synthesis" if n_unusable == 1 else "syntheses"
    return f"{n_unusable} {word} without netlist"


def _pnr_config_widgets(work_dirname, arch_name, sources, selected_values, enabled, arch_path):
    """
    Build the body an architecture gets inside a place & route card: one panel
    per parameter domain of its completed synthesis jobs, and the preview
    checklist holding those jobs.

    Returns the same (domain_tiles, preview_tile, info) triple as
    _arch_config_widgets, so the nested-card layout and the callbacks keyed on
    those widget ids apply unchanged. Unlike an architecture card, the domain
    panels enumerate nothing: they *select* among the sources that exist.

    Args:
        selected_values: the saved selectors of this tool (wildcards included);
            the ones this architecture matches are checked.
        enabled: whether that saved selection applies. Nothing saved yet means
            everything runnable is pre-checked, so enabling the card is a single
            click (exactly like a disabled architecture card).
    """
    id_extra = {"sim": work_dirname}
    known_domains = workspace.get_param_domains(arch_path, arch_name) if arch_path else []

    # A synthesis that handed no netlist over cannot be placed & routed. Listing
    # it would only add unselectable noise, so it is left out of the card and
    # only counted, in a badge next to the configuration count.
    options = []
    tokens_by_selector = {}
    n_unusable = 0
    for source in sources:
        if source.missing_handoff_files():
            n_unusable += 1
            continue
        options.append({"label": _pnr_source_label(source), "value": source.selector})
        tokens_by_selector[source.selector] = _pnr_source_tokens(source, known_domains)

    available = list(tokens_by_selector.keys())

    if enabled:
        parsed_selectors = [pnr_source.parse_selector(entry) for entry in selected_values or []]
        selected = [
            source.selector
            for source in sources
            if source.selector in tokens_by_selector
            and any(parsed and pnr_source.source_matches(source, parsed) for parsed in parsed_selectors)
        ]
    else:
        selected = list(available)

    domains_values = _pnr_domain_values(tokens_by_selector, known_domains)

    # A domain chip is checked when at least one selected source has that value:
    # the panels describe what the preview holds, the same way they do for an
    # architecture.
    checked_by_domain = {}
    for selector in selected:
        for domain, value in tokens_by_selector.get(selector, {}).items():
            checked_by_domain.setdefault(domain, set()).add(value)

    domain_tiles = []
    for domain, values in domains_values.items():
        checklist = dcc.Checklist(
            options=[{"label": _pnr_value_label(domain, value), "value": value} for value in values],
            id={"type": "domain-config-checklist", "arch": arch_name, "domain": domain, **id_extra},
            value=[value for value in values if value in checked_by_domain.get(domain, set())],
            className="odx-chips",
        )
        domain_tiles.append(
            ui.panel(
                title=[
                    html.Span(_pnr_domain_title(domain)),
                    html.Span(f"{len(values)}", className="odx-badge"),
                ],
                tools=_select_all_buttons(
                    "domain-config-select-all", {"arch": arch_name, "domain": domain, **id_extra}
                ),
                body=checklist,
            )
        )

    # A source is picked whole or not at all: there is no default configuration
    # to mirror. The checkbox is still rendered (empty, hidden) because the
    # callbacks shared with the simulation cards are keyed on it.
    domain_tiles.append(
        html.Div(
            dcc.Checklist(
                options=[],
                id={"type": "default-config-checklist", "arch": arch_name, "domain": "default", **id_extra},
                value=[],
            ),
            style={"display": "none"},
        )
    )

    preview_tile = ui.panel(
        title=_preview_title(len(options), False, len(selected)),
        title_id={"type": "preview-config-title", "arch": arch_name, **id_extra},
        tools=_select_all_buttons("preview-config-select-all", {"arch": arch_name, **id_extra}),
        body=dcc.Checklist(
            options=options,
            id={"type": "preview-config-checklist", "arch": arch_name, **id_extra},
            value=selected,
            className="odx-check-list",
        ),
        body_className="scroll tall",
    )

    info = {
        "n_combos": len(options),
        "n_selected": len(selected),
        "default_selected": False,
        "filtered_selected": selected,
        # Only the domains that got a panel: this store is the "previous state"
        # sync_preview_values compares the panels against, so a domain it cannot
        # see must not appear in it (it would read as a domain just emptied).
        "domains_configs": {
            domain: sorted(checked_by_domain[domain])
            for domain in domains_values
            if checked_by_domain.get(domain)
        },
        "sources": tokens_by_selector,
        "n_unusable": n_unusable,
        "unmatched": [],
        "too_many": False,
    }
    return domain_tiles, preview_tile, info


def _pnr_sync_preview_values(
    arch_metadata, current_domains, current_preview_values, changed_domain, added_values, removed_values
):
    """
    What checking (or unchecking) a domain value does to the preview of a place
    & route card. The sources are not combined, they exist or they do not, so
    the panels select among them instead of generating combinations:

      * a value checked selects every source that has it *and* whose other
        levels are checked too, so the panels read as a filter,
      * a value unchecked deselects every source that has it.

    Called by sync_preview_values once it has worked out what changed, so both
    kinds of card share the "which domain moved" bookkeeping.
    """
    sources = (arch_metadata or {}).get("sources") or {}
    preview_set = set(current_preview_values or [])

    for selector, tokens in sources.items():
        value = tokens.get(changed_domain)
        if value in removed_values:
            preview_set.discard(selector)
        elif value in added_values:
            if all(
                tokens.get(domain) in set(values)
                for domain, values in current_domains.items()
                if domain != changed_domain
            ):
                preview_set.add(selector)

    return sorted(preview_set)


def _pnr_job_sections(context, selection_settings):
    """
    Build one card per eda tool that ran a synthesis, each holding a nested card
    per architecture it synthesized, exactly like a simulation card holds the
    architectures it runs on.

    Returns:
        tuple: (sections, baseline_selection) where baseline_selection is the
        flat selector list a fresh page load is equivalent to (used as the
        "saved" baseline so nothing falsely reads as unsaved).
    """
    arch_path = context.get("arch_path", "")
    sources_by_tool = context["sources_by_tool"]
    selection_map = _group_pnr_selections(
        selection_settings.get(context["selection_key"], []), context["instances"]
    )

    baseline_selection = []
    sections = []
    for work_dirname in context["instances"]:
        tool_sources = sources_by_tool.get(work_dirname, [])
        tool_enabled = work_dirname in selection_map
        saved_selectors = selection_map.get(work_dirname, [])

        sources_by_arch = {}
        for source in tool_sources:
            sources_by_arch.setdefault(source.architecture, []).append(source)

        arch_cards = []
        tool_entries = []
        n_total = 0
        n_selected_total = 0
        n_unusable_total = 0
        for arch_name, arch_sources in sources_by_arch.items():
            domain_tiles, preview_tile, info = _pnr_config_widgets(
                work_dirname, arch_name, arch_sources, saved_selectors, tool_enabled, arch_path
            )
            # An architecture none of the saved selectors names runs nothing yet;
            # its sub-card is off, with everything pre-checked.
            arch_enabled = tool_enabled and bool(info["filtered_selected"])

            n_total += info["n_combos"]
            n_unusable_total += info["n_unusable"]
            if arch_enabled:
                n_selected_total += info["n_selected"]
                tool_entries.extend(info["filtered_selected"])

            arch_cards.append(
                html.Div(
                    children=[
                        html.Div(
                            children=html.Div(
                                children=[
                                    dcc.Checklist(
                                        options=[{"label": "", "value": True}],
                                        value=[True] if arch_enabled else [],
                                        id={"type": "sim-arch-switch", "sim": work_dirname, "arch": arch_name},
                                        className="checklist-switch",
                                    ),
                                    html.Span(arch_name, className="jobs-arch-name"),
                                    html.Span(
                                        _simulation_badge_text(
                                            info["n_combos"], info["n_selected"], arch_enabled
                                        ),
                                        id={"type": "arch-count", "sim": work_dirname, "arch": arch_name},
                                        className="odx-badge",
                                    ),
                                ] + ([
                                    html.Span(
                                        _pnr_unusable_badge_text(info["n_unusable"]),
                                        title="These syntheses handed no netlist over: they cannot be placed & routed.",
                                        className="odx-badge caution",
                                    )
                                ] if info["n_unusable"] else []),
                                className="jobs-arch-headline",
                            ),
                            className="jobs-arch-header",
                        ),
                        html.Div(
                            children=html.Div(
                                children=[
                                    html.Div(domain_tiles, className="jobs-domains"),
                                    preview_tile,
                                ],
                                className="jobs-arch-grid",
                            ),
                            id={"type": "sim-arch-body", "sim": work_dirname, "arch": arch_name},
                            className="jobs-arch-body animated-section" + ("" if arch_enabled else " hide"),
                        ),
                        dcc.Store(
                            id={"type": "arch-metadata", "sim": work_dirname, "arch": arch_name},
                            data={
                                "kind": "pnr",
                                "arch_name": arch_name,
                                "n_combos": info["n_combos"],
                                "sources": info["sources"],
                            },
                        ),
                        dcc.Store(
                            id={"type": "domain-selections", "sim": work_dirname, "arch": arch_name},
                            data=info["domains_configs"],
                        ),
                        dcc.Store(
                            id={"type": "sim-arch-extra", "sim": work_dirname, "arch": arch_name},
                            data=[],
                        ),
                    ],
                    id={"type": "sim-arch-card", "sim": work_dirname, "arch": arch_name},
                    className="jobs-arch-card nested" + (" enabled" if arch_enabled else ""),
                )
            )

        if not arch_cards:
            arch_cards.append(
                ui.panel(
                    title="Synthesized designs",
                    body=html.Div("No completed synthesis found for this tool.", className="odx-panel-note"),
                )
            )

        tool_entries = list(dict.fromkeys(tool_entries))
        if tool_enabled:
            baseline_selection.extend(tool_entries)

        tool_buttons = html.Div(
            children=[
                ui.icon_button(
                    icon=icon("gear", className="icon"),
                    text=context["settings_text"],
                    tooltip="Open the settings of this tool",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["settings_link"](work_dirname),
                    multiline=True,
                    width="135px",
                ),
                ui.icon_button(
                    icon=icon("metrics", className="icon blue"),
                    text=context["config_text"],
                    tooltip="Open the Exported Metrics Editor for this tool",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["config_link"](work_dirname),
                    multiline=False,
                    width="135px",
                ),
            ],
            className="jobs-arch-buttons",
        )

        sections.append(
            html.Div(
                children=[
                    html.Div(
                        children=[
                            html.Div(
                                children=[
                                    dcc.Checklist(
                                        options=[{"label": "", "value": True}],
                                        value=[True] if tool_enabled else [],
                                        id={"type": "arch-title", "arch": work_dirname, "is_switch": True},
                                        className="checklist-switch",
                                    ),
                                    html.Span(
                                        work_dirname,
                                        id={"type": "arch-title", "arch": work_dirname},
                                        className="jobs-arch-name",
                                    ),
                                    html.Span(
                                        _simulation_badge_text(n_total, n_selected_total, tool_enabled),
                                        id={"type": "sim-count", "sim": work_dirname},
                                        className="odx-badge",
                                    ),
                                ] + ([
                                    html.Span(
                                        _pnr_unusable_badge_text(n_unusable_total),
                                        title="These syntheses handed no netlist over: they cannot be placed & routed.",
                                        className="odx-badge caution",
                                    )
                                ] if n_unusable_total else []),
                                className="jobs-arch-headline",
                            ),
                            tool_buttons,
                        ],
                        className="jobs-arch-header",
                    ),
                    html.Div(
                        children=html.Div(arch_cards, className="jobs-sim-archs"),
                        id={"type": "param-domains-container", "arch": work_dirname},
                        className="jobs-arch-body animated-section" + ("" if tool_enabled else " hide"),
                    ),
                    dcc.Store(
                        id={"type": "sim-metadata", "sim": work_dirname},
                        data={"sim_name": work_dirname, "n_entries": n_total},
                    ),
                    dcc.Store(id={"type": "sim-orphan-entries", "sim": work_dirname}, data=[]),
                    # What this tool places & routes, kept in sync with the
                    # nested architecture cards and read by Save / Run.
                    dcc.Store(id={"type": "sim-selection", "sim": work_dirname}, data=tool_entries),
                ],
                id={"type": "job-section", "arch": work_dirname},
                className="jobs-arch-card" + (" enabled" if tool_enabled else ""),
            )
        )

    return sections, list(dict.fromkeys(baseline_selection))


def _run_context(search, odatix_settings) -> dict:
    """
    Resolve everything that differs between job types (architectures vs
    workflows) from the ?type=... url parameter.

    Returns a dict with:
        mode           : "workflow" or "arch"
        base_path      : architectures / workflows directory
        settings_path  : the selection settings file to read/write
        selection_key  : the yaml key holding the selection ("workflows" / "architectures")
        instances      : list of instance names to display
        settings_link  : lambda name -> settings editor url
        config_link    : lambda name -> config editor url
        settings_text  : label of the settings button
        title          : plural heading of the instance section
    """
    settings = odatix_settings or {}
    run_mode = get_key_from_url(search, "type")
    if run_mode == "simulation":
        base_path = settings.get("sim_path", OdatixSettings.DEFAULT_SIM_PATH)
        return {
            "mode": "simulation",
            "base_path": base_path,
            # Simulations run *on* architectures, so a simulation section needs
            # the architecture directory too (unlike every other job type, where
            # base_path is the only directory involved).
            "arch_path": settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH),
            "settings_path": settings.get("simulation_settings_file", OdatixSettings.DEFAULT_SIMULATION_SETTINGS_FILE),
            "selection_key": "simulations",
            "instances": workspace.get_simulations(base_path),
            "settings_link": lambda name: f"/sim_editor?sim={name}",
            "config_link": lambda name: f"/metric_editor?simulation={name}",
            "config_text": "Edit Metrics",
            "settings_text": "Simulation Settings",
            "title": "Simulations",
        }
    if run_mode == "pnr":
        # A place & route run selects completed synthesis jobs, not
        # architectures: the "instances" are the eda tools that ran them, and
        # each card holds the jobs that tool produced.
        work_root = settings.get("work_path", OdatixSettings.DEFAULT_WORK_PATH)
        sources_by_tool = _pnr_sources_by_tool(work_root, settings)
        return {
            "mode": "pnr",
            "base_path": work_root,
            # The parameter domains of a source are read back from its work
            # directory name, which needs the domain names of the architecture
            # it was synthesized from (see _pnr_split_config_token).
            "arch_path": settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH),
            "settings_path": _get_synth_settings_path(search, settings),
            "selection_key": "sources",
            "instances": list(sources_by_tool.keys()),
            "sources_by_tool": sources_by_tool,
            "settings_link": lambda name: f"/tool_editor?tool={_pnr_tool_of(name)}",
            "config_link": lambda name: f"/metric_editor?tool={_pnr_tool_of(name)}",
            "settings_text": "Tool Settings",
            "config_text": "Edit Metrics",
            "title": "Synthesized designs",
        }
    if run_mode == "workflow":
        base_path = settings.get("workflow_path", OdatixSettings.DEFAULT_WORKFLOW_PATH)
        return {
            "mode": "workflow",
            "base_path": base_path,
            "settings_path": settings.get("workflow_settings_file", OdatixSettings.DEFAULT_WORKFLOW_SETTINGS_FILE),
            "selection_key": "workflows",
            "instances": workspace.get_workflows(base_path),
            "settings_link": lambda name: f"/workflow_editor?workflow={name}",
            "config_link": lambda name: f"/config_editor?workflow={name}",
            "settings_text": "Workflow Settings",
            "config_text": "Edit Configs",
            "title": "Workflows",
        }
    base_path = settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    return {
        "mode": "arch",
        "base_path": base_path,
        "settings_path": _get_synth_settings_path(search, settings),
        "selection_key": "architectures",
        "instances": workspace.get_architectures(base_path),
        "settings_link": lambda name: f"/arch_editor?arch={name}",
        "config_link": lambda name: f"/config_editor?arch={name}",
        "settings_text": "Architecture Settings",
        "config_text": "Edit Configs",
        "title": "Architectures",
    }

def _arch_name_from_entry(entry: str) -> str:
    first_part = str(entry).split(" + ")[0].strip()
    if "/" in first_part:
        return first_part.split("/")[0].strip()
    return first_part

def _group_arch_selections(architectures_setting) -> dict:
    if not architectures_setting:
        return {}
    if isinstance(architectures_setting, dict):
        architectures = list(architectures_setting)
    else:
        architectures = list(architectures_setting)
    grouped = {}
    for entry in architectures:
        if entry is None:
            continue
        arch_name = _arch_name_from_entry(entry)
        if not arch_name:
            continue
        grouped.setdefault(arch_name, []).append(str(entry))
    return grouped

def _virtual_variant_tokens(base_path, name, mode):
    """
    Resolve the virtual parameter domains of a workflow or an architecture
    (command-placeholder variables defined under
    "generate_configurations_settings.variables" in its _settings.yml), by
    reusing the exact generation logic used at run time
    (run_workflow.check_settings() / ArchitectureHandler.expand_virtual_param_domains()).

    For architectures, the variables only become a parameter domain when
    "generate_command" actually references them; otherwise they keep their sole
    original meaning (generating configuration files), exactly like
    ArchitectureHandler._expand_arch_virtual_param_domains() decides.

    Returns:
        variants      : list of ["domain/value", ...] token lists, one per
                        generated variant (empty if there is none). These are
                        meant to be appended to every physical combination.
        domain_values : dict domain name -> sorted list of distinct values
                        seen across variants (for display only).
        error         : error message if the variable settings are invalid,
                         else None.
    """
    settings = workspace.load_workflow_settings(base_path, name)
    virtual_domain_names = virtual_param_domain.get_virtual_domain_names(settings)
    if not virtual_domain_names:
        return [], {}, None

    if mode != "workflow":
        # Only "generate_command" consumes these variables as a parameter domain.
        generate_command = settings.get("generate_command", "") if settings.get("generate_rtl", False) else ""
        if not (virtual_param_domain.referenced_variable_names(generate_command) & virtual_domain_names):
            return [], {}, None

    settings_file = workspace.get_workflow_settings_path(base_path, name)
    variants = virtual_param_domain.build_variants(settings=settings, settings_file=settings_file, debug=False)
    if variants is None:
        return [], {}, "Invalid variable settings. Check the settings file."

    token_lists = [list(variant.get("requested_param_domains", [])) for variant in variants]
    token_lists = [tokens for tokens in token_lists if tokens]
    domain_values = {}
    for tokens in token_lists:
        for token in tokens:
            domain, _, value = token.partition("/")
            domain_values.setdefault(domain, set()).add(value)
    domain_values = {domain: sorted(values) for domain, values in domain_values.items()}
    return token_lists, domain_values, None

def _select_all_buttons(button_type: str, id_keys: dict) -> html.Div:
    """Build a 'Select all' / 'Clear' button pair for a checklist.

    button_type is the pattern-matching id "type"; id_keys holds the other
    wildcard keys identifying the target checklist (e.g. arch/domain).
    """
    return html.Div(
        children=[
            html.Button("Select all", id={"type": button_type, "action": "show", **id_keys}, n_clicks=0, className="odx-mini-button small-button"),
            html.Button("Clear", id={"type": button_type, "action": "hide", **id_keys}, n_clicks=0, className="odx-mini-button small-button"),
        ],
        className="xp-filter-buttons",
    )

def _preview_title(n_combos: int, default_enabled: bool, n_selected: int = 0) -> list:
    """Content of the preview panel heading: the "Preview" label plus a badge
    counting the selected combinations, accounting for the default config.

    n_combos is the total number of non-default combinations and n_selected how
    many of them are currently checked, shown as "n_selected/n_combos". The
    default config is counted separately: "+1 default" when it is enabled
    alongside other combos, or "1 default" when it is the only selected entry.
    """
    if n_combos <= 0:
        detail = "1 default" if default_enabled else "0 combinations"
    else:
        word = "combination" if n_combos == 1 else "combinations"
        suffix = " +1 default" if default_enabled else ""
        detail = f"{n_selected}/{n_combos} {word}{suffix}"
    return [html.Span("Preview"), html.Span(detail, className="odx-badge")]


def _arch_badge_text(n_combos: int, n_selected: int, default_enabled: bool, arch_enabled: bool=True) -> str:
    """Badge shown next to an architecture name: how many of its configurations
    are currently selected (the default config counts as one). A disabled
    architecture runs nothing, so only its total is shown."""
    total = n_combos + 1
    word = "config" if total == 1 else "configs"
    if not arch_enabled:
        return f"{total} {word}"
    selected = n_selected + (1 if default_enabled else 0)
    return f"{selected}/{total} {word}"

def _extract_domain_values(arch_name: str, selections) -> dict:
    """Return mapping of domain -> set(values) found in preview selection strings."""
    values_by_domain = {}
    for entry in selections or []:
        if entry is None:
            continue
        parts = [p.strip() for p in str(entry).split(" + ") if p.strip()]
        for part in parts:
            if "/" not in part:
                continue
            domain, value = part.split("/", 1)
            if domain == arch_name:
                domain = hard_settings.main_parameter_domain
            if not domain or value == "":
                continue
            values_by_domain.setdefault(domain, set()).add(value)
    return values_by_domain

def _analysis_tools_selection(search: str, settings_path: str) -> list:
    """Tools the analysis 'Tools' checklist is initialized to: the "tools" list
    saved in the analysis settings file plus the tool selected on the "Choose
    EDA Tool" page (?tool=...). Shared by init_form (widget init) and the saved
    baseline so a refresh does not falsely report "unsaved changes"."""
    selected_tools = list(workspace.load_analysis_tools(settings_path))
    url_tool = get_key_from_url(search, "tool")
    if url_tool and url_tool not in selected_tools:
        selected_tools.append(url_tool)
    return selected_tools

def _expand_wildcard_selection(entry: str, domains_configs: dict, arch_name: str) -> list:
    """
    Expand a saved selection entry that uses a domain-value wildcard (e.g.
    "Arch + addr/* + data/5", or the bare main-domain form "Arch/*"), mirroring
    the wildcard syntax ArchitectureHandler.configuration_wildcard() understands
    at run time, into every concrete "arch + domain/value + ..." combo string it
    represents (the exact format produced by workspace.generate_config_combinations).

    Returns [entry] unchanged if it uses no wildcard ("*") value.
    """
    parts = [p.strip() for p in str(entry).split(" + ") if p.strip()]
    if not parts:
        return []

    constraints = {}
    order = []
    for part in parts:
        if "/" not in part:
            continue
        domain, value = part.split("/", 1)
        if domain == arch_name:
            domain = hard_settings.main_parameter_domain
        constraints[domain] = value
        order.append(domain)

    if "*" not in constraints.values():
        return [entry]

    value_lists = [
        domains_configs.get(domain, []) if constraints[domain] == "*" else [constraints[domain]]
        for domain in order
    ]

    expanded = []
    for combo_values in itertools.product(*value_lists):
        replaced_parts = [
            f"{arch_name if domain == hard_settings.main_parameter_domain else domain}/{value}"
            for domain, value in zip(order, combo_values)
        ]
        if order and order[0] != hard_settings.main_parameter_domain:
            combo = [arch_name] + replaced_parts
        else:
            combo = replaced_parts
        expanded.append(" + ".join(combo))
    return expanded


def _arch_domains_configs(arch_path, arch_name) -> dict:
    """The configurations of every parameter domain of an architecture that
    actually uses parameters, keyed by domain (main domain included)."""
    domains_configs = {}
    domains = [hard_settings.main_parameter_domain] + workspace.get_param_domains(arch_path, arch_name)
    for domain in domains:
        if not workspace.check_parameter_domain_use_parameters(arch_path, arch_name, domain):
            continue
        configurations = workspace.get_config_files(arch_path, arch_name, domain)
        if not configurations:
            continue
        # Remove .txt extension
        domains_configs[domain] = [cfg[:-4] if cfg.endswith(".txt") else cfg for cfg in configurations]
    return domains_configs


def _arch_config_widgets(arch_path, arch_name, selected_values, arch_enabled, mode, id_extra=None):
    """
    Build the body an architecture gets on this page: one panel per parameter
    domain to pick values from, the "Default configuration" panel, and the
    preview checklist holding the resulting combinations (the fine-grained
    control over what actually runs).

    id_extra is merged into every pattern-matching id. It is empty for the
    architecture-keyed job types, and {"sim": <name>} for the architecture
    panels nested in a simulation card, which keeps the two sets of widgets in
    separate callback groups while they share this layout (see
    _simulation_job_sections).

    Args:
        selected_values: the saved selection of this architecture, in preview
            format ("Arch + domain/value + ..."); wildcards are expanded here.
        arch_enabled: whether that saved selection applies. A disabled
            architecture has nothing saved yet, so everything is pre-checked:
            enabling it is then a single click.

    Returns:
        tuple: (domain_tiles, preview_tile, info) where info holds
        n_combos / n_selected / default_selected / filtered_selected (what the
        preview checklist renders as checked) / domains_configs / unmatched
        (saved entries no combination of this architecture accounts for).
    """
    id_extra = id_extra or {}
    domains_configs = _arch_domains_configs(arch_path, arch_name)

    selected_domain_values = _extract_domain_values(arch_name, selected_values) if arch_enabled else {}
    domain_tiles = []
    for domain, configurations in domains_configs.items():
        if arch_enabled:
            domain_selected = selected_domain_values.get(domain, set())
            if "*" in domain_selected:
                # Wildcard ("domain/*" or the bare "arch_name/*" main-domain
                # form): select every configuration in this domain, like
                # ArchitectureHandler.configuration_wildcard() does at run time.
                checklist_values = list(configurations)
            else:
                checklist_values = [cfg for cfg in configurations if cfg in domain_selected]
        else:
            checklist_values = list(configurations)
        checklist = dcc.Checklist(
            options=[{"label": cfg, "value": cfg} for cfg in configurations],
            id={"type": "domain-config-checklist", "arch": arch_name, "domain": domain, **id_extra},
            value=checklist_values,
            className="odx-chips",
        )
        domain_tiles.append(
            ui.panel(
                title=[
                    html.Span(domain if domain != hard_settings.main_parameter_domain else "Main parameter domain"),
                    html.Span(f"{len(configurations)}", className="odx-badge"),
                ],
                tools=_select_all_buttons(
                    "domain-config-select-all", {"arch": arch_name, "domain": domain, **id_extra}
                ),
                body=checklist,
            )
        )

    # Virtual parameter domains (command-placeholder variables)
    virtual_panel_title = "Workflow variables" if mode == "workflow" else "Variables"
    virtual_variants, virtual_domain_values, virtual_error = _virtual_variant_tokens(arch_path, arch_name, mode)
    if virtual_error:
        domain_tiles.append(
            ui.panel(
                title=virtual_panel_title,
                body=html.Div(virtual_error, className="error-message"),
            )
        )
    elif virtual_domain_values:
        domain_tiles.append(
            ui.panel(
                title=virtual_panel_title,
                body=[
                    html.Div(
                        [
                            html.Span(f"{domain}:", className="jobs-var-name"),
                            html.Span(", ".join(values)),
                        ],
                        className="jobs-var-line",
                    )
                    for domain, values in virtual_domain_values.items()
                ],
            )
        )

    # Compute the preview data up-front so the "Default Configuration" tile
    # and the preview stay consistent about whether the default config
    # (the bare "<arch_name>" entry) is selected. n_combos counts the
    # non-default combinations only; the default config is counted apart.
    # Virtual parameter domains behave like any other parameter domain: every
    # variant is combined with every physical combination (and with the bare
    # architecture, which has no physical configuration of its own), exactly
    # like the expansion performed at run time.
    n_physical_combos = workspace.count_combinations(domains_configs)
    if virtual_variants:
        n_combos = (n_physical_combos + 1) * len(virtual_variants)
    else:
        n_combos = n_physical_combos
    too_many = n_combos > MAX_PREVIEW_COMBINATIONS
    formatted_combinations = []
    filtered_selected = []
    unmatched = []
    if not too_many:
        physical_combos = workspace.generate_config_combinations(domains_configs, arch_name)
        if virtual_variants:
            non_default_combos = [
                base + tokens
                for base in [[f"{arch_name}"]] + physical_combos
                for tokens in virtual_variants
            ]
        else:
            non_default_combos = physical_combos
        all_combinations = [[f"{arch_name}"]] + non_default_combos
        if len(all_combinations) > MAX_PREVIEW_COMBINATIONS:
            all_combinations = [{comb[0]} for comb in all_combinations]  # Only show default if too many combinations
        formatted_combinations = [{"label": " + ".join(comb), "value": " + ".join(comb)} for comb in all_combinations]
        available_values = [opt.get("value") for opt in formatted_combinations]
        # Expand domain-value wildcards ("domain/*", or the bare "arch/*"
        # main-domain form) into every concrete combo they represent before
        # matching against the available combinations: a raw wildcard entry
        # never matches literally, which used to silently drop it from the
        # preview (and from what gets saved back on the next Save).
        # Virtual domains are wildcard-expandable too ("Arch + width/*").
        wildcard_domains = dict(domains_configs)
        wildcard_domains.update(virtual_domain_values or {})
        expanded_selected = []
        for entry in selected_values or []:
            expanded_selected.extend(_expand_wildcard_selection(entry, wildcard_domains, arch_name))
        filtered_selected = [val for val in expanded_selected if val in available_values]
        unmatched = [val for val in expanded_selected if val not in available_values]
        # Select all combinations for disabled architectures
        if not arch_enabled:
            filtered_selected = [" + ".join(comb) for comb in all_combinations]
            unmatched = []
        default_selected = arch_name in filtered_selected
        n_selected = len([v for v in filtered_selected if v != arch_name])
    else:
        default_selected = (not arch_enabled) or (arch_name in (selected_values or []))
        # Nothing is enumerated, so nothing can be matched: the saved entries are
        # carried over untouched rather than dropped.
        unmatched = list(selected_values or []) if arch_enabled else []
        n_selected = 0

    # Default configuration tile. Its checkbox is kept in sync with the
    # default "<arch_name>" entry of the preview checklist (both directions),
    # see sync_default_to_preview / sync_preview_to_default.
    domain_tiles.append(
        ui.panel(
            title="Default configuration",
            body=dcc.Checklist(
                options=[{"label": f"{arch_name} (default)", "value": arch_name}],
                id={"type": "default-config-checklist", "arch": arch_name, "domain": "default", **id_extra},
                value=[arch_name] if default_selected else [],
                className="odx-check-list",
            ),
        )
    )

    if too_many:
        preview_tile = ui.panel(
            title=_preview_title(n_combos, default_selected, n_selected),
            title_id={"type": "preview-config-title", "arch": arch_name, **id_extra},
            body=html.Div(
                f"Too many combinations to display (> {MAX_PREVIEW_COMBINATIONS}).",
                className="odx-panel-note",
            ),
        )
    else:
        preview_tile = ui.panel(
            title=_preview_title(n_combos, default_selected, n_selected),
            title_id={"type": "preview-config-title", "arch": arch_name, **id_extra},
            tools=_select_all_buttons("preview-config-select-all", {"arch": arch_name, **id_extra}),
            body=dcc.Checklist(
                options=formatted_combinations,
                id={"type": "preview-config-checklist", "arch": arch_name, **id_extra},
                value=filtered_selected,
                className="odx-check-list",
            ),
            body_className="scroll tall",
        )

    info = {
        "n_combos": n_combos,
        "n_selected": n_selected,
        "default_selected": default_selected,
        "filtered_selected": filtered_selected,
        "domains_configs": domains_configs,
        "unmatched": unmatched,
        "too_many": too_many,
        "virtual_variants": virtual_variants,
    }
    return domain_tiles, preview_tile, info


######################################
# Simulation mode
######################################
#
# A simulation run is set up the other way around from every other job type: the
# instances are the simulations, and what each of them selects is a set of
# *architecture configurations* to run on -- not configurations of its own (a
# simulation has none). The settings file mirrors that shape:
#
#   simulations:
#     - TB_Example:
#       - Example_Counter_vhdl/04bits
#       - Example_Counter_vhdl/08bits+width/16
#
# A simulation card therefore nests one collapsible sub-card per architecture,
# each holding the very same widgets an architecture gets in every other job
# type (parameter-domain panels plus the preview checklist), built by
# _arch_config_widgets. Those nested widgets carry an extra "sim" id key, which
# keeps them in callback groups of their own while the layout stays shared.
#
# The union of what the nested previews have checked is mirrored into a
# per-simulation store ("sim-selection"), which is what Save and Run read.


def _sim_entry_from_combo(combo: str) -> str:
    """Convert a preview combination ("Arch + domain/value") into the syntax the
    simulation settings file uses ("Arch+domain/value")."""
    return "+".join(part.strip() for part in str(combo).split(" + ") if part.strip())


def _combo_from_sim_entry(entry: str) -> str:
    """Inverse of _sim_entry_from_combo."""
    return " + ".join(part.strip() for part in str(entry).split("+") if part.strip())


def _sim_entry_arch(entry: str) -> str:
    """The architecture a simulation settings entry runs on."""
    return str(entry).split("+", 1)[0].split("/", 1)[0].strip()


def _simulation_job_sections(context, selection_settings):
    """
    Build one card per simulation, each holding a collapsible sub-card per
    architecture where the configurations that simulation runs are picked, the
    same way they are picked for a synthesis.

    Returns:
        tuple: (sections, baseline_selection) where baseline_selection is the
        simulation -> entries mapping a fresh page load is equivalent to (used
        as the "saved" baseline so nothing falsely reads as unsaved).
    """
    arch_path = context["arch_path"]
    simulations = context["instances"]

    selection_map = workspace.load_simulation_selection(context["settings_path"])
    architectures = workspace.get_architectures(arch_path)

    baseline_selection = {}
    sections = []
    for sim_name in simulations:
        sim_enabled = sim_name in selection_map

        # Group the saved entries by the architecture they belong to, converted
        # to the preview syntax _arch_config_widgets expects.
        saved_by_arch = {}
        for entry in selection_map.get(sim_name, []):
            saved_by_arch.setdefault(_sim_entry_arch(entry), []).append(_combo_from_sim_entry(entry))

        arch_cards = []
        # Kept apart, and concatenated at the end in this exact order, so the
        # baseline matches how sync_simulation_selection() rebuilds the store:
        # the "unsaved changes" check compares the two lists element by element.
        checked_entries = []
        extra_entries = []
        n_total = 0
        n_selected_total = 0
        for arch_name in architectures:
            # An architecture this simulation does not mention runs nothing yet;
            # its sub-card is off, with everything pre-checked so that turning it
            # on is a single click (exactly like a disabled architecture card).
            arch_enabled = sim_enabled and arch_name in saved_by_arch
            domain_tiles, preview_tile, info = _arch_config_widgets(
                arch_path,
                arch_name,
                saved_by_arch.get(arch_name, []),
                arch_enabled,
                context["mode"],
                id_extra={"sim": sim_name},
            )

            n_configs = info["n_combos"] + 1
            n_total += n_configs
            selected = list(info["filtered_selected"])
            # Entries this architecture cannot enumerate (too many combinations)
            # or no longer offers are carried untouched so saving never silently
            # drops a hand-written selection.
            extra = list(info["unmatched"])
            if arch_enabled:
                n_selected_total += len(selected) + len(extra)
                checked_entries.extend(_sim_entry_from_combo(value) for value in selected)
                extra_entries.extend(_sim_entry_from_combo(value) for value in extra)

            arch_cards.append(
                html.Div(
                    children=[
                        html.Div(
                            children=html.Div(
                                children=[
                                    dcc.Checklist(
                                        options=[{"label": "", "value": True}],
                                        value=[True] if arch_enabled else [],
                                        id={"type": "sim-arch-switch", "sim": sim_name, "arch": arch_name},
                                        className="checklist-switch",
                                    ),
                                    html.Span(arch_name, className="jobs-arch-name"),
                                    html.Span(
                                        _arch_badge_text(
                                            info["n_combos"],
                                            info["n_selected"],
                                            info["default_selected"],
                                            arch_enabled,
                                        ),
                                        id={"type": "arch-count", "sim": sim_name, "arch": arch_name},
                                        className="odx-badge",
                                    ),
                                ],
                                className="jobs-arch-headline",
                            ),
                            className="jobs-arch-header",
                        ),
                        html.Div(
                            children=html.Div(
                                children=[
                                    html.Div(domain_tiles, className="jobs-domains"),
                                    preview_tile,
                                ],
                                className="jobs-arch-grid",
                            ),
                            id={"type": "sim-arch-body", "sim": sim_name, "arch": arch_name},
                            className="jobs-arch-body animated-section" + ("" if arch_enabled else " hide"),
                        ),
                        dcc.Store(
                            id={"type": "arch-metadata", "sim": sim_name, "arch": arch_name},
                            data={
                                "arch_name": arch_name,
                                "n_combos": info["n_combos"],
                                "virtual_variants": info["virtual_variants"],
                            },
                        ),
                        dcc.Store(
                            id={"type": "domain-selections", "sim": sim_name, "arch": arch_name},
                            data=info["domains_configs"],
                        ),
                        # Saved entries no combination accounts for: kept aside
                        # and re-contributed to the selection as they are.
                        dcc.Store(
                            id={"type": "sim-arch-extra", "sim": sim_name, "arch": arch_name},
                            data=[_sim_entry_from_combo(value) for value in extra],
                        ),
                    ],
                    id={"type": "sim-arch-card", "sim": sim_name, "arch": arch_name},
                    className="jobs-arch-card nested" + (" enabled" if arch_enabled else ""),
                )
            )

        # Entries of a saved selection whose architecture does not exist anymore
        # have no sub-card to live in. They are still this simulation's, so they
        # ride along in a store rather than being dropped on the next Save.
        orphan_entries = [
            _sim_entry_from_combo(value)
            for arch_name, values in saved_by_arch.items()
            if arch_name not in architectures
            for value in values
        ]
        if sim_enabled and orphan_entries:
            n_selected_total += len(orphan_entries)
            n_total += len(orphan_entries)

        if not arch_cards:
            arch_cards.append(
                ui.panel(
                    title="Architectures",
                    body=html.Div(f"No architecture found in {arch_path}.", className="odx-panel-note"),
                )
            )

        sim_entries = list(dict.fromkeys(checked_entries + extra_entries + orphan_entries))
        if sim_enabled:
            baseline_selection[sim_name] = sim_entries

        sim_buttons = html.Div(
            children=[
                ui.icon_button(
                    icon=icon("gear", className="icon"),
                    text=context["settings_text"],
                    tooltip="Open the settings of this simulation",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["settings_link"](sim_name),
                    multiline=True,
                    width="135px",
                ),
                ui.icon_button(
                    icon=icon("metrics", className="icon blue"),
                    text=context["config_text"],
                    tooltip="Open the Exported Metrics Editor for this simulation",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["config_link"](sim_name),
                    multiline=False,
                    width="135px",
                ),
            ],
            className="jobs-arch-buttons",
        )

        sections.append(
            html.Div(
                children=[
                    html.Div(
                        children=[
                            html.Div(
                                children=[
                                    dcc.Checklist(
                                        options=[{"label": "", "value": True}],
                                        value=[True] if sim_enabled else [],
                                        id={"type": "arch-title", "arch": sim_name, "is_switch": True},
                                        className="checklist-switch",
                                    ),
                                    html.Span(sim_name, id={"type": "arch-title", "arch": sim_name}, className="jobs-arch-name"),
                                    html.Span(
                                        _simulation_badge_text(n_total, n_selected_total, sim_enabled),
                                        id={"type": "sim-count", "sim": sim_name},
                                        className="odx-badge",
                                    ),
                                ],
                                className="jobs-arch-headline",
                            ),
                            sim_buttons,
                        ],
                        className="jobs-arch-header",
                    ),
                    html.Div(
                        children=html.Div(arch_cards, className="jobs-sim-archs"),
                        id={"type": "param-domains-container", "arch": sim_name},
                        className="jobs-arch-body animated-section" + ("" if sim_enabled else " hide"),
                    ),
                    dcc.Store(
                        id={"type": "sim-metadata", "sim": sim_name},
                        data={"sim_name": sim_name, "n_entries": n_total},
                    ),
                    dcc.Store(
                        id={"type": "sim-orphan-entries", "sim": sim_name},
                        data=orphan_entries,
                    ),
                    # What this simulation runs, kept in sync with the nested
                    # architecture cards and read by Save / Run.
                    dcc.Store(
                        id={"type": "sim-selection", "sim": sim_name},
                        data=sim_entries,
                    ),
                ],
                id={"type": "job-section", "arch": sim_name},
                className="jobs-arch-card" + (" enabled" if sim_enabled else ""),
            )
        )

    return sections, baseline_selection


def _simulation_badge_text(n_entries, n_selected, enabled=True):
    word = "config" if n_entries == 1 else "configs"
    if not enabled:
        return f"{n_entries} {word}"
    return f"{n_selected}/{n_entries} {word}"


def _collect_simulation_selection(switch_values, switch_ids, selection_values, selection_ids) -> dict:
    """
    The simulation -> architecture entries mapping the page currently describes,
    keeping only the simulations whose switch is on.
    """
    by_sim = {}
    for value, sel_id in zip(selection_values or [], selection_ids or []):
        sim_name = sel_id.get("sim") if isinstance(sel_id, dict) else None
        if sim_name:
            by_sim[sim_name] = list(dict.fromkeys([str(v) for v in (value or []) if v is not None]))

    selection = {}
    for value, sid in zip(switch_values or [], switch_ids or []):
        sim_name = sid.get("arch") if isinstance(sid, dict) else None
        if sim_name and bool(value):
            selection[sim_name] = by_sim.get(sim_name, [])
    return selection


######################################
# UI Components
######################################

def job_settings_form(settings, run_mode="default", selected_tools=None):
    frequencies = settings.get("frequencies", {})
    range = frequencies.get("range", {})
    fmax_bounds = settings.get("fmax_synthesis", {})
    if not isinstance(fmax_bounds, dict):
        fmax_bounds = {}

    auto_nb_jobs = is_auto_nb_jobs(settings.get("nb_jobs"))

    if selected_tools is None:
        selected_tools = settings.get("tools", [])
    selected_tools = [tool for tool in selected_tools if tool in _analysis_tools()]

    return html.Div(
        children=[
            html.Div([
                html.Div("Execution", className="odx-panel-caption"),
                html.Div(
                    children=[
                        ui.switch_row(
                            "Overwrite existing result",
                            id="overwrite",
                            checked=settings.get("overwrite", False),
                            tooltip="If enabled, previous results will be overwritten. (overridden by -o / --overwrite).",
                        ),
                        ui.switch_row(
                            "Force single threading",
                            id="force_single_thread",
                            checked=settings.get("force_single_thread", True),
                            tooltip="If enabled, each job will run using a single thread.",
                        ),
                    ],
                    className="odx-switch-stack",
                ),
                html.Div(
                    children=[
                        ui.form_field(
                            label="Maximum number of parallel jobs",
                            id="nb_jobs",
                            type="number",
                            value=str(resolve_nb_jobs(AUTO_NB_JOBS_KEYWORD)) if auto_nb_jobs else str(settings.get("nb_jobs", 8)),
                            disabled=auto_nb_jobs,
                            tooltip="Maximum number of jobs to run in parallel. (overridden by -j / --jobs)",
                            style={"flex": "1"},
                        ),
                        ui.inline_switch(
                            "Auto",
                            id="auto-nb-jobs",
                            checked=auto_nb_jobs,
                            tooltip="Automatically use the number of available CPUs minus one.",
                        ),
                    ],
                    className="odx-field-row",
                ),
            ], className="odx-panel padded"),
            html.Div([
                html.Div("Monitor", className="odx-panel-caption"),
                ui.form_field(
                    label="Size of the log history per job",
                    id="log_size_limit",
                    type="number",
                    value=str(settings.get("log_size_limit", 300)),
                    tooltip="Number of log lines to keep per job. (overridden by --logsize)",
                ),
                html.Div("Command line", className="odx-panel-caption"),
                html.Div(
                    children=[
                        ui.switch_row(
                            "Ask for confirmation after checking settings",
                            id="ask_continue",
                            checked=settings.get("ask_continue", _JOB_SETTINGS_DEFAULTS["ask_continue"]),
                            tooltip="Prompt 'Continue? (Y/n)' after settings checks. (overridden by -y / --noask).",
                        ),
                        ui.switch_row(
                            "Exit terminal monitor when all jobs are done",
                            id="exit_when_done",
                            checked=settings.get("exit_when_done", _JOB_SETTINGS_DEFAULTS["exit_when_done"]),
                            tooltip="Exit the monitor automatically when all jobs are finished. (overridden by -E / --exit).",
                        ),
                    ],
                    className="odx-switch-stack",
                    style={"marginTop": "var(--space-2)"},
                ),
            ], className="odx-panel padded"),
            html.Div([
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                html.Span("EDA tools", style={"display": "inline-block"}),
                            ],
                            className="odx-panel-caption",
                            style={"display": "inline-block"},
                        ),
                        ui.tooltip_icon("Select every eda tool the RTL analysis should run with (saved as the 'tools' list of the analysis settings file, overridden by -t / --tool). The jobs of all selected tools run together in a single monitor session.", tooltip_options="secondary bottom"),
                    ],
                ),
                dcc.Checklist(
                    options=_analysis_tool_options(),
                    value=selected_tools,
                    id="analysis-tools",
                    className="checklist-switch list",
                ),
            ], className="odx-panel padded", style={"display": "block" if run_mode == "analyze" else "none"}),
            html.Div([
                html.Div("Synthesis constraints", className="odx-panel-caption"),
                html.Div(
                    ui.switch_row(
                        "Override frequencies",
                        id="override-arch-frequencies",
                        checked=(
                            fmax_bounds.get("override", False) if run_mode == "fmax_synthesis"
                            else frequencies.get("override", False)
                        ),
                        tooltip="Override architecture-specific frequencies.",
                    ),
                    className="odx-switch-stack",
                ),
                html.Div(
                    children=[
                        ui.inline_switch(
                            "List",
                            id="use-custom-freq-list",
                            checked=frequencies.get("use_custom_freq_list", False),
                            tooltip="Synthesize at each frequency of the list below.",
                        ),
                        ui.form_field(
                            label="Target frequencies (MHz)",
                            id="target_frequencies",
                            type="text",
                            value=", ".join(str(f) for f in frequencies.get("list", [])),
                            tooltip="Comma-separated target frequencies for the synthesis.",
                            style={"flex": "1"},
                        ),
                    ],
                    className="odx-field-row",
                    style={"display": "flex" if run_mode == "custom_freq_synthesis" else "none", "marginBottom": "var(--space-3)"},
                ),
                html.Div(
                    children=[
                        ui.inline_switch(
                            "Range",
                            id="use-custom-freq-range",
                            checked=frequencies.get("use_custom_freq_range", False),
                            tooltip="Synthesize at every frequency of the range below.",
                        ),
                        ui.form_field(
                            label="From (MHz)",
                            id="from_frequency",
                            type="number",
                            value=str(range.get("from", "")),
                            tooltip="Lower frequency for the synthesis.",
                        ),
                        ui.form_field(
                            label="To (MHz)",
                            id="to_frequency",
                            type="number",
                            value=str(range.get("to", "")),
                            tooltip="Upper frequency for the synthesis.",
                        ),
                        ui.form_field(
                            label="Step (MHz)",
                            id="step_frequency",
                            type="number",
                            value=str(range.get("step", "")),
                            tooltip="Frequency step for the synthesis.",
                        ),
                    ],
                    className="odx-field-row",
                    style={"display": "flex" if run_mode == "custom_freq_synthesis" else "none"},
                ),
                html.Div(
                    children=[
                        ui.form_field(
                            label="Lower Bound (MHz)",
                            id="lower_bound",
                            type="number",
                            value=str(fmax_bounds.get("lower_bound", "")),
                            tooltip="Lower bound of the binary search for the maximum frequency.",
                            style={"flex": "1"},
                        ),
                        ui.form_field(
                            label="Upper Bound (MHz)",
                            id="upper_bound",
                            type="number",
                            value=str(fmax_bounds.get("upper_bound", "")),
                            tooltip="Upper bound of the binary search for the maximum frequency.",
                            style={"flex": "1"},
                        ),
                    ],
                    className="odx-field-row",
                    style={"display": "flex" if run_mode == "fmax_synthesis" else "none"},
                )
            ], className="odx-panel padded", style={"display": "block" if run_mode in ("custom_freq_synthesis", "fmax_synthesis") else "none"}),
        ], className="odx-grid",
    )

######################################
# Callbacks
######################################

@dash.callback(
    Output({"page": page_path, "action": "session-dropdown"}, "options"),
    Output({"page": page_path, "action": "session-dropdown"}, "value"),
    Input(f"url_{page_path}", "search"),
    Input("session-list-interval", "n_intervals"),
    State({"page": page_path, "action": "session-dropdown"}, "value"),
)
def update_session_dropdown(_search, _n, current_value):
    options = [{"label": "New session...", "value": "__new_session__", "title": "Run jobs in a new session"}]
    try:
        daemons = daemon_control.list_daemons()
    except Exception:
        daemons = []

    options.extend(_session_option(daemon) for daemon in daemons)

    values = {option.get("value") for option in options}
    selected = str(current_value).strip() if current_value is not None else "__new_session__"
    if selected not in values:
        selected = "__new_session__"

    return options, selected

@dash.callback(
    Output("job-settings-form-container", "children"),
    Output("job-settings-initial-settings", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_form(search, page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update

    run_mode = get_key_from_url(search, "type")
    settings_path = _get_synth_settings_path(search, odatix_settings or {})
    
    settings = workspace.load_arch_selection_settings(settings_path)
    if settings is None:
        settings = {}
    if run_mode == "custom_freq_synthesis":
        # Normalize the frequencies for the form, but keep the other job
        # settings (overwrite, nb_jobs, ...) so their widgets reflect the file.
        settings = {**settings, **workspace.get_frequencies_form_values(settings)}

    selected_tools = None
    if run_mode == "analyze":
        selected_tools = _analysis_tools_selection(search, settings_path)

    return job_settings_form(settings, run_mode, selected_tools=selected_tools), settings

@dash.callback(
    Output("nb_jobs", "disabled"),
    Output("nb_jobs", "value"),
    Input("auto-nb-jobs", "value"),
    State("nb_jobs", "value"),
    prevent_initial_call=True,
)
def toggle_auto_nb_jobs(auto_nb_jobs, nb_jobs):
    """Disable (and blank) the nb_jobs input while the Auto switch is on; restore
    a sensible value when it is turned back off."""
    if _checklist_enabled(auto_nb_jobs):
        return True, str(resolve_nb_jobs(AUTO_NB_JOBS_KEYWORD))
    restored = nb_jobs if nb_jobs not in (None, "") else _JOB_SETTINGS_DEFAULTS["nb_jobs"]
    return False, str(restored)

@dash.callback(
    Output("job-section", "children"),
    Output("job-section-heading", "children"),
    Output("jobs-config-main-title", "children"),
    Output("jobs-config-saved-selection", "data", allow_duplicate=True),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_param_domains(
    search, page, odatix_settings
):
    triggered_id = ctx.triggered_id

    if triggered_id == "url":
        if page != page_path:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    context = _run_context(search, odatix_settings)
    arch_path = context["base_path"]
    architectures = context["instances"]
    run_mode = get_key_from_url(search, "type")

    settings_path = context["settings_path"]
    selection_settings = workspace.load_arch_selection_settings(settings_path)

    # Simulations select architecture configurations rather than their own, so
    # they get their own sections (see _simulation_job_sections).
    if context["mode"] == "simulation":
        job_sections, baseline_selection = _simulation_job_sections(context, selection_settings)
        if not job_sections:
            job_sections = [
                html.Div(
                    f"No simulation found in {context['base_path']}.",
                    className="odx-panel odx-empty",
                )
            ]
        saved_baseline = {
            context["selection_key"]: baseline_selection,
            **_job_settings_baseline(selection_settings),
        }
        return job_sections, context["title"], "Select the configurations each simulation runs on", saved_baseline

    # A place & route run selects completed synthesis jobs, grouped by tool then
    # by architecture, so it gets the same nested sections (see
    # _pnr_job_sections).
    if context["mode"] == "pnr":
        job_sections, baseline_selection = _pnr_job_sections(context, selection_settings)
        if not job_sections:
            job_sections = [
                html.Div(
                    f"No completed synthesis found in {context['base_path']}.",
                    className="odx-panel odx-empty",
                )
            ]
        saved_baseline = {
            context["selection_key"]: baseline_selection,
            **_job_settings_baseline(selection_settings),
        }
        return job_sections, context["title"], "Select the synthesized designs to place & route", saved_baseline

    selection_map = _group_arch_selections(selection_settings.get(context["selection_key"], []))
    # Baseline of the "saved" selection, computed exactly like the widgets are
    # initialized below, so a fresh page load does not falsely report "unsaved
    # changes" (the store starts empty and is only written on Save otherwise).
    baseline_selection = []
    job_sections = []
    for arch_name in architectures:
        arch_enabled = arch_name in selection_map
        domain_tiles, preview_tile, info = _arch_config_widgets(
            arch_path,
            arch_name,
            selection_map.get(arch_name, []),
            arch_enabled,
            context["mode"],
        )
        n_combos = info["n_combos"]
        n_selected = info["n_selected"]
        default_selected = info["default_selected"]
        domains_configs = info["domains_configs"]

        # Enabled architectures contribute their (rendered) preview selection to
        # the saved baseline, exactly like save_architecture_selections() builds
        # its "current" selection from the switch + preview widgets.
        if arch_enabled:
            baseline_selection.extend(info["filtered_selected"])

        arch_buttons = html.Div(
            children=[
                ui.icon_button(
                    icon=icon("gear", className="icon"),
                    text=context["settings_text"],
                    tooltip=f"Open the settings of this {context['mode']}",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["settings_link"](arch_name),
                    multiline=True,
                    width="135px",
                ),
                ui.icon_button(
                    icon=icon("edit", className="icon blue"),
                    text=context.get("config_text", "Edit Configs"),
                    tooltip=f"Open the {context.get('config_text', 'Edit Configs')} page for this {context['mode']}",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["config_link"](arch_name),
                    multiline=False,
                    width="135px",
                ),
            ],
            className="jobs-arch-buttons",
        )
        job_section = html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                dcc.Checklist(
                                    options=[{"label": "", "value": True}],
                                    value=[True] if arch_enabled else [],
                                    id={"type": "arch-title", "arch": arch_name, "is_switch": True},
                                    className="checklist-switch",
                                ),
                                html.Span(arch_name, id={"type": "arch-title", "arch": arch_name}, className="jobs-arch-name"),
                                html.Span(
                                    _arch_badge_text(n_combos, n_selected, default_selected, arch_enabled),
                                    id={"type": "arch-count", "arch": arch_name},
                                    className="odx-badge",
                                ),
                            ],
                            className="jobs-arch-headline",
                        ),
                        arch_buttons,
                    ],
                    className="jobs-arch-header",
                ),
                html.Div(
                    children=html.Div(
                        children=[
                            html.Div(domain_tiles, className="jobs-domains"),
                            preview_tile,
                        ],
                        className="jobs-arch-grid",
                    ),
                    id={"type": "param-domains-container", "arch": arch_name},
                    className="jobs-arch-body animated-section" + ("" if arch_enabled else " hide"),
                ),
                dcc.Store(
                    id={"type": "arch-metadata", "arch": arch_name},
                    data={
                        "arch_name": arch_name,
                        "n_combos": n_combos,
                        "virtual_variants": info["virtual_variants"],
                    },
                ),
                dcc.Store(
                    id={"type": "domain-selections", "arch": arch_name},
                    data=domains_configs,
                ),
            ],
            id={"type": "job-section", "arch": arch_name},
            className="jobs-arch-card" + (" enabled" if arch_enabled else ""),
        )
        job_sections.append(job_section)

    if not job_sections:
        job_sections = [
            html.Div(
                f"No {context['title'].lower()} found in {context['base_path']}.",
                className="odx-panel odx-empty",
            )
        ]
    main_title = f"Select {context['mode'] if context['mode'] == 'workflow' else 'architecture'} configurations to run"

    # Build the "saved" baseline in the exact same shape as the "current"
    # selection computed by save_architecture_selections(), so a fresh load
    # compares equal (no false "unsaved changes").
    saved_baseline = {
        context["selection_key"]: list(dict.fromkeys(baseline_selection)),
        **_job_settings_baseline(selection_settings),
    }
    if run_mode == "analyze":
        saved_baseline["tools"] = [t for t in _analysis_tools_selection(search, settings_path) if t]
    if run_mode == "custom_freq_synthesis":
        form_freq = workspace.get_frequencies_form_values(selection_settings).get("frequencies", {})
        form_range = form_freq.get("range", {})
        saved_baseline["frequencies"] = workspace.create_custom_frequencies_settings_dict(
            form_freq.get("override", False),
            form_freq.get("list", []),
            form_range.get("from"),
            form_range.get("to"),
            form_range.get("step"),
            use_custom_freq_list=form_freq.get("use_custom_freq_list", False),
            use_custom_freq_range=form_freq.get("use_custom_freq_range", False),
        )
    if run_mode == "fmax_synthesis":
        fmax_bounds = selection_settings.get("fmax_synthesis", {})
        if not isinstance(fmax_bounds, dict):
            fmax_bounds = {}
        saved_baseline["fmax_synthesis"] = workspace.create_fmax_bounds_settings_dict(
            fmax_bounds.get("lower_bound"),
            fmax_bounds.get("upper_bound"),
            override_enabled=fmax_bounds.get("override", False),
        )

    return job_sections, context["title"], main_title, saved_baseline


@dash.callback(
    Output({"type": "param-domains-container", "arch": dash.MATCH}, "className"),
    Output({"type": "job-section", "arch": dash.MATCH}, "className"),
    Input({"type": "arch-title", "arch": dash.MATCH, "is_switch": True}, "value"),
)
def toggle_param_domains(switch_value):
    """Collapse/expand the configurations of an architecture with its switch,
    and highlight the card while it is selected to run."""
    enabled = bool(switch_value)
    return (
        "jobs-arch-body animated-section" + ("" if enabled else " hide"),
        "jobs-arch-card" + (" enabled" if enabled else ""),
    )


@dash.callback(
    Output({"type": "arch-count", "arch": dash.ALL}, "children"),
    Input({"type": "preview-config-checklist", "arch": dash.ALL}, "value"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
    State({"type": "arch-count", "arch": dash.ALL}, "id"),
    State({"type": "arch-metadata", "arch": dash.ALL}, "data"),
)
def update_arch_count(preview_values, switch_values, preview_ids, switch_ids, count_ids, metadatas):
    """Keep the "selected/total configs" badge of every architecture in sync with
    its preview checklist and its switch.

    Written with ALL rather than MATCH because architectures with too many
    combinations have no preview checklist at all: a MATCH group would then be
    incomplete and Dash would report a nonexistent object.
    """
    previews = {
        pid.get("arch"): value
        for value, pid in zip(preview_values or [], preview_ids or [])
        if isinstance(pid, dict)
    }
    enabled = {
        sid.get("arch"): bool(value)
        for value, sid in zip(switch_values or [], switch_ids or [])
        if isinstance(sid, dict)
    }
    metadata_by_arch = {
        (data or {}).get("arch_name"): (data or {})
        for data in (metadatas or [])
    }

    children = []
    for cid in count_ids or []:
        arch_name = cid.get("arch") if isinstance(cid, dict) else None
        if arch_name not in previews:
            # No preview checklist (too many combinations): nothing to recount.
            children.append(dash.no_update)
            continue
        selected = previews.get(arch_name) or []
        metadata = metadata_by_arch.get(arch_name, {})
        n_combos = metadata.get("n_combos", 0)
        if metadata.get("kind") == "pnr":
            # A source is picked whole: there is no default configuration to
            # count apart, and nothing to combine.
            children.append(
                _simulation_badge_text(n_combos, len(selected), enabled.get(arch_name, False))
            )
            continue
        default_enabled = arch_name in selected
        n_selected = len([v for v in selected if v != arch_name])
        children.append(_arch_badge_text(n_combos, n_selected, default_enabled, enabled.get(arch_name, False)))
    return children


@dash.callback(
    Output("jobs-summary", "children"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    Input({"type": "preview-config-checklist", "arch": dash.ALL}, "value"),
    Input({"type": "sim-selection", "sim": dash.ALL}, "data"),
    Input("nb_jobs", "value"),
    Input("auto-nb-jobs", "value"),
    Input(f"url_{page_path}", "search"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State({"type": "sim-selection", "sim": dash.ALL}, "id"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
)
def update_jobs_summary(
    switch_values, preview_values, sim_selection_values, nb_jobs, auto_nb_jobs, search,
    preview_ids, sim_selection_ids, switch_ids,
):
    """Live recap of what the Run button is about to launch: job type, eda tool,
    how many instances are enabled and how many configurations they add up to."""
    enabled = set()
    for value, sid in zip(switch_values or [], switch_ids or []):
        arch = sid.get("arch") if isinstance(sid, dict) else None
        if arch and value:
            enabled.add(arch)

    n_configs = 0
    for value, pid in zip(preview_values or [], preview_ids or []):
        arch = pid.get("arch") if isinstance(pid, dict) else None
        if arch in enabled:
            n_configs += len(value or [])
    for value, pid in zip(sim_selection_values or [], sim_selection_ids or []):
        sim_name = pid.get("sim") if isinstance(pid, dict) else None
        if sim_name in enabled:
            n_configs += len(value or [])

    run_mode = get_key_from_url(search, "type")
    tool = get_key_from_url(search, "tool")
    flow = get_key_from_url(search, "flow")
    until_step = get_key_from_url(search, "until")

    if _checklist_enabled(auto_nb_jobs):
        parallel = str(resolve_nb_jobs(AUTO_NB_JOBS_KEYWORD)) + " (auto)"
    else:
        parallel = str(_to_int(nb_jobs, _JOB_SETTINGS_DEFAULTS["nb_jobs"]))

    if run_mode == "workflow":
        instances_label = "workflow" if len(enabled) == 1 else "workflows"
    elif run_mode == "simulation":
        instances_label = "simulation" if len(enabled) == 1 else "simulations"
    else:
        instances_label = "architecture" if len(enabled) == 1 else "architectures"
    configs_label = "configuration selected" if n_configs == 1 else "configurations selected"

    children = [
        html.Span(RUN_MODE_LABELS.get(run_mode, "Jobs"), className="odx-tag"),
    ]
    if tool and run_mode not in ("workflow", "simulation"):
        children.append(html.Span(eda_tools.get_tool_label(tool), className="odx-tag neutral"))
        # Show the flow only when the tool has a choice to make: a single-flow
        # tool would just add noise.
        if len(eda_tools.list_flows(tool, job_type=run_mode)) > 1:
            children.append(
                html.Span(eda_tools.get_flow_label(tool, flow=flow, job_type=run_mode), className="odx-tag neutral")
            )
        # A run stopping short of the last step is worth spelling out: the rest
        # of the flow is left for a later run.
        steps = eda_tools.get_flow_step_names(tool, flow=flow, job_type=run_mode)
        if until_step in steps and until_step != steps[-1]:
            children.append(html.Span("up to " + until_step, className="odx-tag neutral"))
    children.append(html.Div(className="odx-spacer"))
    children.append(ui.stat(len(enabled), instances_label, "" if enabled else "muted"))
    children.append(ui.stat(n_configs, configs_label, "accent" if n_configs else "muted"))
    children.append(ui.stat(parallel, "in parallel"))
    return children


@dash.callback(
    Output({"type": "job-section", "arch": dash.ALL}, "style"),
    Input("jobs-arch-search", "value"),
    Input("jobs-arch-filter", "value"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    State({"type": "job-section", "arch": dash.ALL}, "id"),
)
def filter_arch_cards(search_text, filter_value, switch_values, section_ids):
    """Filter the instance cards by name and, optionally, hide the ones that are
    not selected to run."""
    needle = (search_text or "").strip().lower()
    only_enabled = "enabled" in (filter_value or [])
    styles = []
    for enabled, sid in zip(switch_values or [], section_ids or []):
        arch = sid.get("arch", "") if isinstance(sid, dict) else ""
        visible = (not needle or needle in str(arch).lower()) and (not only_enabled or bool(enabled))
        styles.append({} if visible else {"display": "none"})
    # The switch list and the card list always have the same length; if a card
    # has no switch yet (page still rendering), leave it visible.
    styles.extend([{}] * (len(section_ids or []) - len(styles)))
    return styles


@dash.callback(
    Output({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    Input("jobs-select-all", "n_clicks"),
    Input("jobs-select-none", "n_clicks"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    prevent_initial_call=True,
)
def select_all_archs(select_all_clicks, select_none_clicks, switch_values):
    """Enable / disable every instance at once."""
    if ctx.triggered_id == "jobs-select-all":
        return [[True]] * len(switch_values or [])
    if ctx.triggered_id == "jobs-select-none":
        return [[]] * len(switch_values or [])
    raise dash.exceptions.PreventUpdate


@dash.callback(
    Output("jobs-settings-body", "className"),
    Output("jobs-settings-toggle", "children"),
    Input("jobs-settings-toggle", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_job_settings(n_clicks):
    """Fold the Job Settings section away once it is set up."""
    collapsed = bool(n_clicks) and n_clicks % 2 == 1
    return (
        "animated-section" + (" hide" if collapsed else ""),
        "Show" if collapsed else "Hide",
    )



@dash.callback(
    Output({"type": "domain-selections", "arch": dash.MATCH}, "data"),
    Input({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "id"),
)
def update_domain_selections(selected_per_domain, domain_ids):
    domains_configs = {}
    for values, did in zip(selected_per_domain or [], domain_ids or []):
        domain = did.get("domain")
        if not domain:
            continue
        if values:
            domains_configs[domain] = values
    return domains_configs

@dash.callback(
    Output({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.MATCH}, "value"),
    Input({"type": "domain-config-select-all", "arch": dash.MATCH, "domain": dash.MATCH, "action": dash.ALL}, "n_clicks"),
    State({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.MATCH}, "options"),
    prevent_initial_call=True,
)
def domain_select_all(n_clicks, options):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not any(n_clicks or []):
        raise dash.exceptions.PreventUpdate
    if triggered.get("action") == "show":
        return [option["value"] for option in options or []]
    return []

@dash.callback(
    Output({"type": "preview-config-checklist", "arch": dash.MATCH}, "value", allow_duplicate=True),
    Input({"type": "preview-config-select-all", "arch": dash.MATCH, "action": dash.ALL}, "n_clicks"),
    State({"type": "preview-config-checklist", "arch": dash.MATCH}, "options"),
    prevent_initial_call=True,
)
def preview_select_all(n_clicks, options):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not any(n_clicks or []):
        raise dash.exceptions.PreventUpdate
    if triggered.get("action") == "show":
        # A disabled entry cannot run (a place & route source with no netlist
        # handed over): "Select all" must not check it.
        return [option["value"] for option in options or [] if not option.get("disabled")]
    return []

@dash.callback(
    Output({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    Input({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "id"),
    State({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    State({"type": "domain-selections", "arch": dash.MATCH}, "data"),
)
def sync_preview_values(
    selected_per_domain,
    domain_ids,
    current_preview_values,
    arch_metadata,
    prev_selections
):
    arch_name = arch_metadata.get("arch_name", "")

    # Build the current state of the domains
    current_domains = {}
    for values, did in zip(selected_per_domain or [], domain_ids or []):
        domain = did.get("domain")
        if not domain:
            continue
        if values:
            current_domains[domain] = values

    # Previous state of the domains (can be None on first call)
    prev_domains = prev_selections or {}

    # Find the domain that changed and the added/removed values
    changed_domain = None
    added_values = set()
    removed_values = set()

    # Domains present either before or now
    all_domains = set(prev_domains.keys()) | set(current_domains.keys())
    # Use a deterministic order (Dash provides domain_ids in display order).
    ordered_domains = []
    for did in (domain_ids or []):
        d = did.get("domain") if isinstance(did, dict) else None
        if d and d not in ordered_domains:
            ordered_domains.append(d)
    for d in sorted(all_domains):
        if d not in ordered_domains:
            ordered_domains.append(d)

    for domain in ordered_domains:
        prev_vals = set(prev_domains.get(domain, []))
        curr_vals = set(current_domains.get(domain, []))
        if prev_vals != curr_vals:
            changed_domain = domain
            added_values = curr_vals - prev_vals
            removed_values = prev_vals - curr_vals
            break

    # If no clear change is found, do nothing. The title is intentionally left
    # untouched: it reflects the total number of available combinations
    # (fixed at render time in update_param_domains), not how many are
    # currently checked -- recomputing it from len(current_preview_values)
    # here would show the checked count instead once any items are unchecked.
    if not changed_domain:
        return current_preview_values or []

    if (arch_metadata or {}).get("kind") == "pnr":
        return _pnr_sync_preview_values(
            arch_metadata, current_domains, current_preview_values, changed_domain, added_values, removed_values
        )

    # Start from the current preview value (including manual changes)
    preview_set = set(current_preview_values or [])

    # Helper: generate all complete combinations from current_domains. Virtual
    # parameter domains have no checklist of their own (they are generated, not
    # picked), but they still multiply every combination, exactly like in
    # _arch_config_widgets.
    all_combos = workspace.generate_config_combinations(current_domains, arch_name)
    virtual_variants = (arch_metadata or {}).get("virtual_variants") or []
    if virtual_variants:
        all_combos = [combo + list(tokens) for combo in all_combos for tokens in virtual_variants]
    all_combo_strings = {" + ".join(c) for c in all_combos}

    # Values are domain-scoped in combos as "<domain>/<cfg>" (or "<arch_name>/<cfg>" for main).
    display_domain = arch_name if changed_domain == hard_settings.main_parameter_domain else changed_domain
    added_tokens = {f"{display_domain}/{v}" for v in added_values}
    removed_tokens = {f"{display_domain}/{v}" for v in removed_values}

    # Handle added values in the modified domain
    if added_values:
        for combo in all_combos:
            combo_str = " + ".join(combo)
            # Only handle combos that contain an added value for the changed domain.
            if any(part in added_tokens for part in combo):
                preview_set.add(combo_str)

    # Handle removed values in the modified domain
    if removed_values:
        to_remove = set()
        for item in preview_set:
            # Do not touch the 'default' item
            if item == arch_name:
                continue
            parts = [p.strip() for p in str(item).split(" + ")]
            # Only remove combos that explicitly contain the removed token for the changed domain.
            if any(part in removed_tokens for part in parts):
                to_remove.add(item)
        preview_set -= to_remove

    # Keep the "default" item if it was already selected
    if current_preview_values and arch_name in current_preview_values:
        preview_set.add(arch_name)

    # Return a sorted list for display stability
    result = []
    if arch_name in preview_set:
        result.append(arch_name)
        preview_set.remove(arch_name)
    result.extend(sorted(preview_set))

    return result


@dash.callback(
    Output({"type": "preview-config-checklist", "arch": dash.MATCH}, "value", allow_duplicate=True),
    Input({"type": "default-config-checklist", "arch": dash.MATCH, "domain": "default"}, "value"),
    State({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sync_default_to_preview(default_value, preview_value, arch_metadata):
    """Mirror the 'Default Configuration' checkbox onto the default preview entry."""
    arch_name = (arch_metadata or {}).get("arch_name", "")
    default_on = arch_name in (default_value or [])
    preview_list = list(preview_value or [])
    has_default = arch_name in preview_list
    if default_on and not has_default:
        return [arch_name] + preview_list
    if not default_on and has_default:
        return [val for val in preview_list if val != arch_name]
    raise dash.exceptions.PreventUpdate


@dash.callback(
    Output({"type": "default-config-checklist", "arch": dash.MATCH, "domain": "default"}, "value"),
    Input({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sync_preview_to_default(preview_value, arch_metadata):
    """Mirror the default preview entry back onto the 'Default Configuration' checkbox."""
    arch_name = (arch_metadata or {}).get("arch_name", "")
    return [arch_name] if arch_name in (preview_value or []) else []


@dash.callback(
    Output({"type": "preview-config-title", "arch": dash.MATCH}, "children"),
    Input({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def update_preview_title(preview_value, arch_metadata):
    """Recompute the preview heading, reflecting whether the default config is selected."""
    metadata = arch_metadata or {}
    arch_name = metadata.get("arch_name", "")
    n_combos = metadata.get("n_combos", 0)
    selected = preview_value or []
    default_enabled = arch_name in selected
    n_selected = len([v for v in selected if v != arch_name])
    return _preview_title(n_combos, default_enabled, n_selected)


@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output("jobs-config-saved-selection", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    Input({"type": "preview-config-checklist", "arch": dash.ALL}, "value"),
    Input({"type": "sim-selection", "sim": dash.ALL}, "data"),
    Input("override-arch-frequencies", "value"),
    Input("use-custom-freq-list", "value"),
    Input("target_frequencies", "value"),
    Input("use-custom-freq-range", "value"),
    Input("from_frequency", "value"),
    Input("to_frequency", "value"),
    Input("step_frequency", "value"),
    Input("lower_bound", "value"),
    Input("upper_bound", "value"),
    Input("analysis-tools", "value"),
    Input("overwrite", "value"),
    Input("force_single_thread", "value"),
    Input("nb_jobs", "value"),
    Input("auto-nb-jobs", "value"),
    Input("log_size_limit", "value"),
    Input("ask_continue", "value"),
    Input("exit_when_done", "value"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State({"type": "sim-selection", "sim": dash.ALL}, "id"),
    State("jobs-config-saved-selection", "data"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_architecture_selections(
    save_n_clicks,
    switch_values,
    preview_values,
    sim_selection_values,
    override_arch_frequencies,
    use_custom_freq_list,
    target_frequencies,
    use_custom_freq_range,
    from_frequency,
    to_frequency,
    step_frequency,
    lower_bound,
    upper_bound,
    analysis_tools,
    overwrite,
    force_single_thread,
    nb_jobs,
    auto_nb_jobs,
    log_size_limit,
    ask_continue,
    exit_when_done,
    switch_ids,
    preview_ids,
    sim_selection_ids,
    saved_selection,
    search,
    page,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update

    context = _run_context(search, odatix_settings)
    run_mode = get_key_from_url(search, "type")
    selection_key = context["selection_key"]
    current_settings = _collect_run_settings(
        run_mode,
        selection_key,
        switch_values,
        switch_ids,
        preview_values,
        preview_ids,
        overwrite,
        force_single_thread,
        nb_jobs,
        auto_nb_jobs,
        log_size_limit,
        ask_continue,
        exit_when_done,
        override_arch_frequencies,
        use_custom_freq_list,
        target_frequencies,
        use_custom_freq_range,
        from_frequency,
        to_frequency,
        step_frequency,
        lower_bound,
        upper_bound,
        analysis_tools,
        sim_selection_values=sim_selection_values,
        sim_selection_ids=sim_selection_ids,
    )

    if isinstance(saved_selection, dict):
        saved_settings = saved_selection
    else:
        saved_settings = {selection_key: saved_selection or []}

    if triggered_id == {"page": page_path, "action": "save-all"}:
        try:
            settings_path = context["settings_path"]
            base_settings = workspace.load_arch_selection_settings(settings_path)
            payload = {
                **base_settings,
                **current_settings,
            }
            workspace.save_architecture_selection(settings_path, payload, run_mode=run_mode, use_custom_freq_list=use_custom_freq_list, use_custom_freq_range=use_custom_freq_range)
            return (
                "color-button disabled icon-button tooltip delay bottom small",
                "Nothing to save",
                current_settings,
            )
        except Exception:
            return (
                "color-button error-status icon-button tooltip bottom small",
                "Failed to save...",
                dash.no_update,
            )

    # The baseline is only set once update_param_domains() has finished loading
    # the page (it can be slower than init_form, which renders the form widgets
    # and triggers this callback first). Until then, do not judge/flash
    # "Unsaved changes!": leave the button untouched (it starts disabled).
    if saved_selection is None:
        return dash.no_update, dash.no_update, dash.no_update

    if saved_settings.get(selection_key, []) != current_settings.get(selection_key, []):
        return (
            "color-button warning icon-button tooltip bottom small tooltip",
            "Unsaved changes!",
            dash.no_update,
        )

    # Job Settings fields (only compare once a real baseline dict exists, i.e.
    # after the page has finished loading, to avoid a transient false positive).
    if isinstance(saved_selection, dict):
        for key in _JOB_SETTINGS_DEFAULTS:
            if saved_settings.get(key) != current_settings.get(key):
                return (
                    "color-button warning icon-button tooltip bottom small tooltip",
                    "Unsaved changes!",
                    dash.no_update,
                )

    if run_mode == "custom_freq_synthesis":
        saved_frequencies = saved_settings.get("frequencies", {})
        if saved_frequencies != current_settings.get("frequencies", {}):
            return (
                "color-button warning icon-button tooltip bottom small tooltip",
                "Unsaved changes!",
                dash.no_update,
            )

    if run_mode == "fmax_synthesis":
        if saved_settings.get("fmax_synthesis", {}) != current_settings.get("fmax_synthesis", {}):
            return (
                "color-button warning icon-button tooltip bottom small tooltip",
                "Unsaved changes!",
                dash.no_update,
            )

    if run_mode == "analyze":
        if saved_settings.get("tools", []) != current_settings.get("tools", []):
            return (
                "color-button warning icon-button tooltip bottom small tooltip",
                "Unsaved changes!",
                dash.no_update,
            )

    return (
        "color-button disabled icon-button tooltip delay bottom small",
        "Nothing to save",
        dash.no_update,
    )

######################################
# Simulation callbacks
######################################
#
# The architecture panels nested in a simulation card are the same widgets the
# other job types use, with an extra "sim" id key (see _simulation_job_sections).
# Dash matches patterns on the exact set of id keys, so they form callback groups
# of their own: the callbacks below wire them up, delegating to the very same
# implementations the architecture-keyed widgets use.


@dash.callback(
    Output({"type": "sim-arch-body", "sim": dash.MATCH, "arch": dash.MATCH}, "className"),
    Output({"type": "sim-arch-card", "sim": dash.MATCH, "arch": dash.MATCH}, "className"),
    Input({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
)
def toggle_sim_arch(switch_value):
    """Collapse/expand an architecture inside a simulation card with its switch."""
    enabled = bool(switch_value)
    return (
        "jobs-arch-body animated-section" + ("" if enabled else " hide"),
        "jobs-arch-card nested" + (" enabled" if enabled else ""),
    )


@dash.callback(
    Output({"type": "domain-selections", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
    Input({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.ALL}, "id"),
)
def sim_update_domain_selections(selected_per_domain, domain_ids):
    return update_domain_selections(selected_per_domain, domain_ids)


@dash.callback(
    Output({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.MATCH}, "value"),
    Input({"type": "domain-config-select-all", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.MATCH, "action": dash.ALL}, "n_clicks"),
    State({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.MATCH}, "options"),
    prevent_initial_call=True,
)
def sim_domain_select_all(n_clicks, options):
    return domain_select_all(n_clicks, options)


@dash.callback(
    Output({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value", allow_duplicate=True),
    Input({"type": "preview-config-select-all", "sim": dash.MATCH, "arch": dash.MATCH, "action": dash.ALL}, "n_clicks"),
    State({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "options"),
    prevent_initial_call=True,
)
def sim_preview_select_all(n_clicks, options):
    return preview_select_all(n_clicks, options)


@dash.callback(
    Output({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
    Input({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.ALL}, "id"),
    State({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
    State({"type": "domain-selections", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
)
def sim_sync_preview_values(selected_per_domain, domain_ids, current_preview_values, arch_metadata, prev_selections):
    return sync_preview_values(
        selected_per_domain, domain_ids, current_preview_values, arch_metadata, prev_selections
    )


@dash.callback(
    Output({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value", allow_duplicate=True),
    Input({"type": "default-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": "default"}, "value"),
    State({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sim_sync_default_to_preview(default_value, preview_value, arch_metadata):
    return sync_default_to_preview(default_value, preview_value, arch_metadata)


@dash.callback(
    Output({"type": "default-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": "default"}, "value"),
    Input({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sim_sync_preview_to_default(preview_value, arch_metadata):
    return sync_preview_to_default(preview_value, arch_metadata)


@dash.callback(
    Output({"type": "preview-config-title", "sim": dash.MATCH, "arch": dash.MATCH}, "children"),
    Input({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sim_update_preview_title(preview_value, arch_metadata):
    return update_preview_title(preview_value, arch_metadata)


@dash.callback(
    Output({"type": "arch-count", "sim": dash.MATCH, "arch": dash.ALL}, "children"),
    Input({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.ALL}, "value"),
    Input({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.ALL}, "value"),
    State({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "arch-count", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.ALL}, "data"),
)
def sim_update_arch_count(preview_values, switch_values, preview_ids, switch_ids, count_ids, metadatas):
    """The "selected/total configs" badge of an architecture inside a simulation.

    Written with ALL rather than MATCH on the architecture because an
    architecture with too many combinations has no preview checklist at all: a
    MATCH group would then be incomplete and Dash would report a nonexistent
    object.
    """
    return update_arch_count(preview_values, switch_values, preview_ids, switch_ids, count_ids, metadatas)


@dash.callback(
    Output({"type": "sim-selection", "sim": dash.MATCH}, "data"),
    Input({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.ALL}, "value"),
    Input({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.ALL}, "value"),
    State({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "sim-arch-extra", "sim": dash.MATCH, "arch": dash.ALL}, "data"),
    State({"type": "sim-arch-extra", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "sim-orphan-entries", "sim": dash.MATCH}, "data"),
)
def sync_simulation_selection(
    preview_values, switch_values, preview_ids, switch_ids, extra_values, extra_ids, orphan_entries
):
    """
    What a simulation runs is the union of what the architectures enabled inside
    it have checked -- not a cross product: a simulation runs each selected
    configuration once.
    """
    enabled = {
        sid.get("arch"): bool(value)
        for value, sid in zip(switch_values or [], switch_ids or [])
        if isinstance(sid, dict)
    }

    entries = []
    for values, pid in zip(preview_values or [], preview_ids or []):
        if not isinstance(pid, dict) or not enabled.get(pid.get("arch")):
            continue
        entries.extend(_sim_entry_from_combo(value) for value in (values or []) if value is not None)
    for values, eid in zip(extra_values or [], extra_ids or []):
        if not isinstance(eid, dict) or not enabled.get(eid.get("arch")):
            continue
        entries.extend(str(value) for value in (values or []) if value is not None)
    entries.extend(str(value) for value in (orphan_entries or []))
    return list(dict.fromkeys(entries))


@dash.callback(
    Output({"type": "sim-count", "sim": dash.ALL}, "children"),
    Input({"type": "sim-selection", "sim": dash.ALL}, "data"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    State({"type": "sim-selection", "sim": dash.ALL}, "id"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
    State({"type": "sim-count", "sim": dash.ALL}, "id"),
    State({"type": "sim-metadata", "sim": dash.ALL}, "data"),
)
def update_simulation_counts(selection_values, switch_values, selection_ids, switch_ids, count_ids, metadatas):
    """
    Keep every simulation's badge in sync with its selection and its switch.

    Written with ALL rather than MATCH because the switch is keyed by "arch"
    (it is the shared instance switch) while the selection is keyed by "sim": a
    single MATCH group cannot span two different wildcard key names.
    """
    selected = {
        pid.get("sim"): len(value or [])
        for value, pid in zip(selection_values or [], selection_ids or [])
        if isinstance(pid, dict)
    }
    enabled = {
        sid.get("arch"): bool(value)
        for value, sid in zip(switch_values or [], switch_ids or [])
        if isinstance(sid, dict)
    }
    n_entries_by_sim = {
        (data or {}).get("sim_name"): (data or {}).get("n_entries", 0)
        for data in (metadatas or [])
    }

    return [
        _simulation_badge_text(
            n_entries_by_sim.get(cid.get("sim"), 0),
            selected.get(cid.get("sim"), 0),
            enabled.get(cid.get("sim"), False),
        )
        for cid in (count_ids or [])
    ]


# Open run popup
@dash.callback(
    Output("run-popup", "className"),
    Output("run-popup-opened", "data"),
    Output("run-popup-title", "children"),
    Output("run-popup-render-key", "data", allow_duplicate=True),
    Input({"page": page_path, "action": "run-jobs"}, "n_clicks"),
    prevent_initial_call=True
)
def show_run_popup(n_click):
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict) or not n_click:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    return "overlay-odatix visible", True, "Checking settings...", ""

# Popup close
@dash.callback(
    Output("run-popup", "className", allow_duplicate=True),
    Output("run-popup-opened", "data", allow_duplicate=True),
    Input("run-cancel-btn", "n_clicks"),
    prevent_initial_call=True
)
def close_run_popup(n):
    return "overlay-odatix", False

@dash.callback(
    Output("jobs-config-run-status", "data"),
    Input({"page": page_path, "action": "run-jobs"}, "n_clicks"),
    State("overwrite", "value"),
    State("force_single_thread", "value"),
    State("nb_jobs", "value"),
    State("auto-nb-jobs", "value"),
    State("ask_continue", "value"),
    State("exit_when_done", "value"),
    State("log_size_limit", "value"),
    State("analysis-tools", "value"),
    # Live architecture/configuration selection and frequency fields, so the run
    # uses the current (possibly unsaved) page state (written to a temp file).
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "value"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State({"type": "sim-selection", "sim": dash.ALL}, "data"),
    State({"type": "sim-selection", "sim": dash.ALL}, "id"),
    State("override-arch-frequencies", "value"),
    State("use-custom-freq-list", "value"),
    State("target_frequencies", "value"),
    State("use-custom-freq-range", "value"),
    State("from_frequency", "value"),
    State("to_frequency", "value"),
    State("step_frequency", "value"),
    State("lower_bound", "value"),
    State("upper_bound", "value"),
    State({"page": page_path, "action": "session-dropdown"}, "value"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def run_jobs(
    n_clicks,
    overwrite,
    force_single_thread,
    nb_jobs,
    auto_nb_jobs,
    ask_continue,
    exit_when_done,
    log_size_limit,
    analysis_tools,
    switch_values,
    switch_ids,
    preview_values,
    preview_ids,
    sim_selection_values,
    sim_selection_ids,
    override_arch_frequencies,
    use_custom_freq_list,
    target_frequencies,
    use_custom_freq_range,
    from_frequency,
    to_frequency,
    step_frequency,
    lower_bound,
    upper_bound,
    selected_session,
    search,
    page,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    global _prepare_thread
    if _prepare_thread is not None and _prepare_thread.is_alive():
        return {
            "status": "running",
            "type": get_key_from_url(search, "type"),
            "tool": get_key_from_url(search, "tool") or "vivado",
        }

    settings = odatix_settings or {}
    run_mode = get_key_from_url(search, "type")
    tool = get_key_from_url(search, "tool") or "vivado"
    flow = get_key_from_url(search, "flow") or None
    # Last step to run, for a flow split into steps (see /choose_eda_tool).
    # Ignored unless it really is one of the flow's steps: an url can be edited
    # by hand, and check_settings() answers an unknown step with sys.exit().
    until_step = get_key_from_url(search, "until") or None
    if until_step is not None and until_step not in eda_tools.get_flow_step_names(
        tool, flow=flow, job_type=run_mode
    ):
        until_step = None

    # arch_path for architecture modes, workflow_path for workflow mode
    run_context = _run_context(search, odatix_settings)
    base_path = run_context["base_path"]
    target_path = settings.get("target_path", OdatixSettings.DEFAULT_TARGET_PATH)
    work_path_root = settings.get("work_path", OdatixSettings.DEFAULT_WORK_PATH)
    # Per-job export destination + options (au fil de l'eau, see prepare_* funcs).
    result_path = settings.get("result_path", OdatixSettings.DEFAULT_RESULT_PATH)
    export_use_benchmark = bool(settings.get("use_benchmark", False))
    export_benchmark_file = settings.get("benchmark_file") or None

    overwrite_enabled = _checklist_enabled(overwrite)
    ask_continue_enabled = _checklist_enabled(ask_continue)
    exit_when_done_enabled = _checklist_enabled(exit_when_done)

    if _checklist_enabled(auto_nb_jobs):
        nb_jobs_val = AUTO_NB_JOBS_KEYWORD
    else:
        try:
            nb_jobs_val = int(nb_jobs) if nb_jobs not in (None, "") else None
        except Exception:
            nb_jobs_val = None

    try:
        log_size_val = int(log_size_limit) if log_size_limit not in (None, "") else None
    except Exception:
        log_size_val = None

    noask = True
    check_eda_tool = True

    _reset_prepare_state()
    global _prepare_synth_type
    global _prepare_runtime_settings
    _prepare_synth_type = run_mode
    _prepare_runtime_settings = {
        "session": _normalize_session_selector(selected_session),
    }

    # Run with the current (possibly unsaved) page state: collect it and write it
    # to a temporary settings file, used as the run settings file below, without
    # touching the real one. Falls back to the real file if that fails.
    global _prepare_temp_settings_file
    temp_settings_file = None
    try:
        current_settings = _collect_run_settings(
            run_mode,
            run_context["selection_key"],
            switch_values,
            switch_ids,
            preview_values,
            preview_ids,
            overwrite,
            force_single_thread,
            nb_jobs,
            auto_nb_jobs,
            log_size_limit,
            ask_continue,
            exit_when_done,
            override_arch_frequencies,
            use_custom_freq_list,
            target_frequencies,
            use_custom_freq_range,
            from_frequency,
            to_frequency,
            step_frequency,
            lower_bound,
            upper_bound,
            analysis_tools,
            sim_selection_values=sim_selection_values,
            sim_selection_ids=sim_selection_ids,
        )
        temp_settings_file = _write_temp_run_settings(
            run_context["settings_path"],
            current_settings,
            run_mode,
            _checklist_enabled(use_custom_freq_list),
            _checklist_enabled(use_custom_freq_range),
        )
    except Exception:
        temp_settings_file = None
    _prepare_temp_settings_file = temp_settings_file

    if run_mode == "custom_freq_synthesis":
        run_config_settings_filename = temp_settings_file or settings.get(
            "custom_freq_synthesis_settings_file",
            OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_SETTINGS_FILE,
        )
        work_path = os.path.join(
            work_path_root,
            settings.get("custom_freq_synthesis_work_path", OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_WORK_PATH),
        )

        _prepare_runtime_settings["export"] = {
            "kind": "synthesis",
            "result_type": "custom_freq_synthesis",
            "work_path": work_path,
            "tool": tool,
            "flow": flow,
            "output_dir": result_path,
            "use_benchmark": export_use_benchmark,
            "benchmark_file": export_benchmark_file,
        }

        _prepare_thread = threading.Thread(
            target=_run_check_custom_freq_settings,
            args=(
                run_config_settings_filename,
                base_path,
                tool,
                flow,
                until_step,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                check_eda_tool,
            ),
            daemon=True,
        )
        _prepare_thread.start()
    elif run_mode == "pnr":
        run_config_settings_filename = temp_settings_file or settings.get(
            "pnr_settings_file",
            OdatixSettings.DEFAULT_PNR_SETTINGS_FILE,
        )
        work_path = os.path.join(
            work_path_root,
            settings.get("pnr_work_path", OdatixSettings.DEFAULT_PNR_WORK_PATH),
        )

        _prepare_runtime_settings["export"] = {
            "kind": "synthesis",
            "result_type": "pnr",
            "work_path": work_path,
            "tool": tool,
            "flow": flow,
            "output_dir": result_path,
            "use_benchmark": export_use_benchmark,
            "benchmark_file": export_benchmark_file,
        }

        _prepare_thread = threading.Thread(
            target=_run_check_pnr_settings,
            args=(
                run_config_settings_filename,
                # A place & route run reads the synthesis jobs from the whole
                # work tree, not from a single job type directory.
                work_path_root,
                tool,
                flow,
                until_step,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                check_eda_tool,
                {
                    job_type: {"path": settings.get(f"{job_type}_work_path") or job_type}
                    for job_type in pnr_source.SOURCE_JOB_TYPES
                },
            ),
            daemon=True,
        )
        _prepare_thread.start()
    elif run_mode == "fmax_synthesis":
        run_config_settings_filename = temp_settings_file or settings.get(
            "fmax_synthesis_settings_file",
            OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
        )
        work_path = os.path.join(
            work_path_root,
            settings.get("fmax_synthesis_work_path", OdatixSettings.DEFAULT_FMAX_SYNTHESIS_WORK_PATH),
        )

        _prepare_runtime_settings["export"] = {
            "kind": "synthesis",
            "result_type": "fmax_synthesis",
            "work_path": work_path,
            "tool": tool,
            "flow": flow,
            "output_dir": result_path,
            "use_benchmark": export_use_benchmark,
            "benchmark_file": export_benchmark_file,
        }

        continue_on_error = True

        _prepare_thread = threading.Thread(
            target=_run_check_fmax_settings,
            args=(
                run_config_settings_filename,
                base_path,
                tool,
                flow,
                until_step,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                continue_on_error,
                check_eda_tool,
            ),
            daemon=True,
        )
        _prepare_thread.start()
    elif run_mode == "workflow":
        run_config_settings_filename = temp_settings_file or settings.get(
            "workflow_settings_file",
            OdatixSettings.DEFAULT_WORKFLOW_SETTINGS_FILE,
        )
        work_path = os.path.join(
            work_path_root,
            settings.get("workflow_work_path", OdatixSettings.DEFAULT_WORKFLOW_WORK_PATH),
        )

        _prepare_runtime_settings["export"] = {
            "kind": "workflow",
            "work_root": work_path,
            "workflow_path": base_path,
            "output_dir": result_path,
        }

        _prepare_thread = threading.Thread(
            target=_run_check_workflow_settings,
            args=(
                run_config_settings_filename,
                base_path,
                work_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
            ),
            daemon=True,
        )
        _prepare_thread.start()
    elif run_mode == "simulation":
        run_config_settings_filename = temp_settings_file or settings.get(
            "simulation_settings_file",
            OdatixSettings.DEFAULT_SIMULATION_SETTINGS_FILE,
        )
        work_path = os.path.join(
            work_path_root,
            settings.get("simulation_work_path", OdatixSettings.DEFAULT_SIMULATION_WORK_PATH),
        )

        _prepare_runtime_settings["export"] = {
            "kind": "simulation",
            "work_root": work_path,
            "sim_path": base_path,
            "output_dir": result_path,
        }

        _prepare_thread = threading.Thread(
            target=_run_check_simulation_settings,
            args=(
                run_config_settings_filename,
                run_context["arch_path"],
                base_path,
                work_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
            ),
            daemon=True,
        )
        _prepare_thread.start()
    elif run_mode == "analyze":
        run_config_settings_filename = temp_settings_file or settings.get(
            "analysis_settings_file",
            OdatixSettings.DEFAULT_ANALYSIS_SETTINGS_FILE,
        )
        work_path = os.path.join(
            work_path_root,
            settings.get("analysis_work_path", OdatixSettings.DEFAULT_ANALYSIS_WORK_PATH),
        )

        _prepare_runtime_settings["export"] = {
            "kind": "analysis",
            "analysis_work_root": work_path,
            "output_dir": result_path,
        }

        # Tools selected in the "Tools" tile; fall back to the ?tool=... url tool.
        # Equivalent to 'odatix analyze --tool <analysis_tool_list>'.
        analysis_tool_list = [t for t in (analysis_tools or []) if t]
        if not analysis_tool_list:
            analysis_tool_list = [tool]

        # The flow picked on /choose_eda_tool applies to every selected tool.
        _prepare_runtime_settings["export"]["flows"] = run_analysis.parse_flow_selection(
            [flow] if flow else None, analysis_tool_list
        )

        _prepare_thread = threading.Thread(
            target=_run_check_analysis_settings,
            args=(
                run_config_settings_filename,
                base_path,
                analysis_tool_list,
                flow,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                check_eda_tool,
            ),
            daemon=True,
        )
        _prepare_thread.start()

    else:
        global _prepare_status
        message = (
            "Running this type of job from the GUI is not available yet.\n"
            "Your selection is saved: launch it from a terminal."
        )
        _prepare_log_buffer.write(message)
        _prepare_status = {"status": "error", "error": message}
        return {"status": "error", "type": run_mode, "tool": tool, "error": message}
    # else:
    #     run_config_settings_filename = settings.get(
    #         "fmax_synthesis_settings_file",
    #         OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
    #     )
    #     work_path = os.path.join(
    #         work_path_root,
    #         settings.get("fmax_synthesis_work_path", OdatixSettings.DEFAULT_FMAX_SYNTHESIS_WORK_PATH),
    #     )

    #     def _run():
    #         run_fmax_synthesis.prepare_synthesis(
    #             run_config_settings_filename,
    #             arch_path,
    #             tool,
    #             work_path,
    #             target_path,
    #             overwrite_enabled,
    #             noask,
    #             exit_when_done_enabled,
    #             log_size_val,
    #             nb_jobs_val,
    #             False,  # continue_on_error
    #             check_eda_tool,
    #             forced_fmax_lower_bound=None,
    #             forced_fmax_upper_bound=None,
    #             debug=False,
    #             keep=False,
    #         )

    # thread = threading.Thread(target=_run, daemon=True)
    # thread.start()

    return {
        "status": "checking",
        "type": run_mode,
        "tool": tool,
    }

@dash.callback(
    Output("jobs-config-run-status", "data", allow_duplicate=True),
    Output("run-popup-body", "children"),
    Output("run-popup-render-key", "data"),
    Output("run-popup-progress", "children"),
    Output("run-confirm-btn", "className"),
    Output("run-redirect", "href", allow_duplicate=True),
    Input("run-log-interval", "n_intervals"),
    State("jobs-config-run-status", "data"),
    State("run-popup-opened", "data"),
    State("run-popup-render-key", "data"),
    prevent_initial_call=True,
)
def poll_prepare_log(n_intervals, run_status, run_popup_opened, render_key):
    if not run_status or not run_popup_opened:
        raise dash.exceptions.PreventUpdate

    current_status = run_status.get("status")
    if current_status == "canceled":
        return run_status, "", "", "", "color-button disabled icon-button", dash.no_update

    if _prepare_status.get("status") and _prepare_status.get("status") != current_status:
        run_status = {**run_status, **_prepare_status}
        current_status = run_status.get("status")

    if current_status in ("checking", "checked", "preparing", "prepared", "launched", "error"):
        # The settings are checked and the plan is displayed, but the eda tool
        # check runs in the background: Start only lights up once it passed.
        tool_check = _tool_check_state()
        _report_tool_check_failures(tool_check)
        tool_ready = tool_check is None or tool_check["status"] == "passed"
        button_class = (
            "color-button success icon-button"
            if current_status == "checked" and tool_ready
            else "color-button disabled icon-button"
        )
        redirect_href = dash.no_update
        # Progress of the job-preparation phase (only meaningful once the run
        # is confirmed; the state is reset at the start of every run).
        progress_bar = _prepare_progress_bar() if current_status in ("preparing", "prepared", "launched", "error") else ""
        if current_status == "prepared" and _prepare_parallel_jobs is not None:
            global _prepare_monitor_href, _prepare_enqueued
            should_enqueue = False
            with _prepare_enqueue_lock:
                if not _prepare_enqueued and _prepare_monitor_href is None:
                    _prepare_enqueued = True
                    should_enqueue = True

            if should_enqueue:
                try:
                    session_selector = None
                    if isinstance(_prepare_runtime_settings, dict):
                        session_selector = _normalize_session_selector(_prepare_runtime_settings.get("session"))

                    state, _response = daemon_control.enqueue_parallel_jobs(
                        _prepare_parallel_jobs,
                        session=session_selector,
                    )

                    session_id = str(state.get("session_id", "")).strip()
                    session_name = str(state.get("session_name", "")).strip()
                    if session_id:
                        _prepare_monitor_href = f"/monitor?session={quote(session_id, safe='')}"
                    elif session_name:
                        _prepare_monitor_href = f"/monitor?session={quote(session_name, safe='')}"
                    else:
                        host = str(state.get("host", hard_settings.daemon_default_host))
                        port = int(state.get("port", hard_settings.daemon_default_port))
                        _prepare_monitor_href = f"/monitor?host={quote(host, safe='')}&port={port}"
                    run_status = {**run_status, "status": "launched"}
                except Exception as exc:
                    with _prepare_enqueue_lock:
                        _prepare_enqueued = False
                    run_status = {"status": "error", "error": str(exc)}
                    _prepare_messages.add("error", f"Failed to enqueue jobs in daemon session: {exc}")
                    return (
                        run_status,
                        _run_popup_body("error"),
                        _run_popup_render_key("error"),
                        progress_bar,
                        "color-button disabled icon-button",
                        dash.no_update,
                    )

            if _prepare_monitor_href is not None:
                redirect_href = _prepare_monitor_href

        # The body is rebuilt only when its content changed: it is re-rendered on
        # a timer, and replacing identical children would collapse the expanded
        # sections under the user.
        new_key = _run_popup_render_key(current_status)
        if new_key == render_key:
            body, new_key_output = dash.no_update, dash.no_update
        else:
            body = _run_popup_body(current_status)
            new_key_output = new_key
        return run_status, body, new_key_output, progress_bar, button_class, redirect_href

    raise dash.exceptions.PreventUpdate

@dash.callback(
    Output("jobs-config-run-status", "data", allow_duplicate=True),
    Output("run-popup-body", "children", allow_duplicate=True),
    Output("run-popup-render-key", "data", allow_duplicate=True),
    Output("run-confirm-btn", "className", allow_duplicate=True),
    Input("run-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def cancel_prepare_synthesis(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    _prepare_cancel_event.set()
    return {"status": "canceled"}, "", "", "color-button disabled icon-button"


@dash.callback(
    Output("jobs-config-run-status", "data", allow_duplicate=True),
    Output("run-popup-title", "children", allow_duplicate=True),
    Output("run-confirm-btn", "className", allow_duplicate=True),
    Input("run-confirm-btn", "n_clicks"),
    State("jobs-config-run-status", "data"),
    prevent_initial_call=True,
)
def confirm_prepare_jobs(n_clicks, run_status):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if not run_status or run_status.get("status") != "checked":
        raise dash.exceptions.PreventUpdate

    # The Start button is only enabled once the background eda tool check
    # passed; guard the callback too, in case it is triggered anyway.
    tool_check = _tool_check_state()
    if tool_check is not None and tool_check["status"] != "passed":
        raise dash.exceptions.PreventUpdate

    global _prepare_exec_thread
    if _prepare_exec_thread is not None and _prepare_exec_thread.is_alive():
        raise dash.exceptions.PreventUpdate

    global _prepare_status
    _prepare_status = {"status": "preparing", "error": None}

    _prepare_exec_thread = threading.Thread(
        target=_run_prepare_synthesis,
        daemon=True,
    )
    _prepare_exec_thread.start()

    return {**run_status, "status": "preparing"}, "Preparing jobs...", "color-button disabled icon-button"


# Launching a run from the popup navigates to the monitor on purpose (with the
# current, possibly unsaved, config): tell the unsaved-changes guard to skip its
# "leave without saving?" prompt for that navigation.
dash.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks) {
            window.__odatixSkipUnsavedGuard = true;
        }
        return "";
    }
    """,
    Output("unsaved-guard-bypass", "data"),
    Input("run-confirm-btn", "n_clicks"),
    prevent_initial_call=True,
)

# Restore the guard if the run does not end up navigating away (error/canceled),
# so unsaved changes are protected again.
dash.clientside_callback(
    """
    function(run_status) {
        var status = run_status && run_status.status;
        if (status === "error" || status === "canceled") {
            window.__odatixSkipUnsavedGuard = false;
        }
        return "";
    }
    """,
    Output("unsaved-guard-bypass", "data", allow_duplicate=True),
    Input("jobs-config-run-status", "data"),
    prevent_initial_call=True,
)

# Point the "Choose Targets" button to the current EDA tool
@dash.callback(
    Output({"page": page_path, "action": "choose-targets", "is_link": True}, "href"),
    Output({"page": page_path, "action": "choose-targets"}, "className"),
    Input(f"url_{page_path}", "search"),
)
def update_choose_targets_link(search):
    tool = get_key_from_url(search, "tool") or "vivado"
    run_mode = get_key_from_url(search, "type")
    if run_mode in ("fmax_synthesis", "custom_freq_synthesis", "pnr"):
        return (
            f"/select_targets?tool={quote(tool)}",
            "color-button default icon-button tooltip bottom small tooltip"
        )
    else:
        return (
            f"/select_targets?tool={quote(tool)}",
            "hidden"
        )
######################################
# Layout
######################################

title_buttons = html.Div(
    children=[
        html.Div(
            children=[
                html.Span("Session", className="odx-session-label"),
                dcc.Dropdown(
                    id={"page": page_path, "action": "session-dropdown"},
                    options=[
                        {"label": "New session...", "value": "__new_session__"},
                    ],
                    placeholder="Select a session",
                    value="__new_session__",
                    clearable=False,
                    style={"width": "155px"},
                ),
            ],
            className="odx-session",
            style={"margin-bottom": "-5px"}
        ),
        ui.icon_button(
            id={"page": page_path, "action": "choose-targets"},
            icon=icon("gear", className="icon"),
            link="/select_targets",  # href updated from the url by update_choose_targets_link
            text="Choose Targets",
            multiline=True,
            tooltip="Go to the Targets page to select targets",
            tooltip_options="bottom",
            color="default",
        ),
        ui.save_button(
            id={"page": page_path, "action": "save-all"},
            tooltip="Save all changes",
            disabled=True,
        ),
        ui.icon_button(
            id={"page": page_path, "action": "run-jobs"},
            icon=icon("play", className="icon"),
            text="Run Jobs",
            tooltip="Run all selected architecture configurations",
            tooltip_options="bottom",
            color="success",
        ),
    ],
    className="odx-header-actions",
)

page_header = html.Div(
    children=[
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.H1("Select architecture configurations to run", id="jobs-config-main-title", className="odx-title"),
                    ],
                    className="odx-header-titles",
                ),
                title_buttons,
            ],
            className="odx-header-row",
        ),
        html.Div(id="jobs-summary", className="odx-summary"),
    ],
    className="odx-header",
)

arch_section_tools = html.Div(
    children=[
        dcc.Input(
            id="jobs-arch-search",
            type="search",
            placeholder="Filter by name...",
            debounce=False,
            className="odx-search small-button",
        ),
        dcc.Checklist(
            options=[{"label": "Selected only", "value": "enabled"}],
            value=[],
            id="jobs-arch-filter",
            className="odx-chips small-button",
        ),
        html.Button("Select all", id="jobs-select-all", n_clicks=0, className="odx-mini-button small-button"),
        html.Button("Clear", id="jobs-select-none", n_clicks=0, className="odx-mini-button small-button"),
    ],
    className="odx-section-tools",
)


layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}", refresh=False),
        page_header,
        html.Div(id={"page": page_path, "type": "title-div"}),
        ui.section(
            "Job Settings",
            html.Div(
                html.Div(id="job-settings-form-container"),
                id="jobs-settings-body",
                className="animated-section",
            ),
            tools=html.Button("Hide", id="jobs-settings-toggle", n_clicks=0, className="odx-mini-button small-button"),
        ),
        dcc.Store(id="job-settings-initial-settings", data=None),
        ui.section(
            "Architectures",
            html.Div(id="job-section", className="jobs-arch-list"),
            heading_id="job-section-heading",
            tools=arch_section_tools,
        ),
        dcc.Store(id="jobs-config-saved-selection", data=None),
        dcc.Store(id="jobs-config-run-status", data=None),
        dcc.Store(id="run-popup-opened", data=False),
        dcc.Store(id="run-popup-render-key", data=""),
        dcc.Store(id="unsaved-guard-bypass", data=""),
        dcc.Location(id="run-redirect", refresh=True),
        # The run popup is polled fast; listing the daemon sessions is a much
        # slower, network-bound refresh and must not share that timer, or a slow
        # discovery delays the popup updates.
        dcc.Interval(id="run-log-interval", interval=500, n_intervals=0),
        dcc.Interval(id="session-list-interval", interval=3000, n_intervals=0),
        html.Div(
            id="run-popup",
            className="overlay-odatix",
            children=[
                html.Div([
                    html.H2("Checking settings...", id="run-popup-title", style={"textAlign": "center"}),
                    html.Div(id="run-popup-progress"),
                    html.Div(id="run-popup-body", className="jobs-plan-scroll"),
                    html.Div([
                        ui.icon_button(
                            icon=icon("cross", className="icon"),
                            color="default",
                            text="Cancel",
                            width="100px",
                            id="run-cancel-btn",
                        ),
                        ui.icon_button(
                            icon=icon("play", className="icon"),
                            color="disabled",
                            text="Start",
                            width="100px",
                            id="run-confirm-btn",
                        ),
                    ], className="jobs-popup-actions"),
                ], className="popup-odatix large")
            ]
        ),
    ],
    className="page-content odx-page jobs-page",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

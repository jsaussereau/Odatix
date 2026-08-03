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

"""The run popup: the structured run plan a check phase produced, rendered as a
foldable dashboard (headline stat cards, diagnostics, then the jobs themselves).

Reads the state of the current run from prepare_state; it never runs anything."""

import re

from dash import html

import odatix.lib.run_report as run_report
from odatix.lib.run_report import JobPlan

from odatix.gui.jobs_config import prepare_state
from odatix.gui.jobs_config.prepare_state import _tool_check_card, _tool_check_state

######################################
# Run popup: structured run plan
######################################

# Per section, beyond this many items the list is truncated: the popup must stay
# usable when a run expands to thousands of configurations.
MAX_SECTION_ITEMS = 200


def _prepare_plan():
    """
    The JobPlan built by the check phase, or None while it has not run yet.
    """
    run = prepare_state._prepare_run
    plan = run.plan if run is not None and run.was_checked else None
    return plan if isinstance(plan, JobPlan) else None


def _plan_noun():
    if prepare_state._prepare_synth_type == "workflow":
        return "workflows"
    if prepare_state._prepare_synth_type == "simulation":
        return "simulations"
    if prepare_state._prepare_synth_type == "pnr":
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

    children.append(_section("Diagnostics", _message_rows(prepare_state._prepare_messages)))
    if plan:
        children.append(_section(_plan_noun().capitalize(), _job_rows(plan)))
    elif status in ("checking", "preparing"):
        children.append(html.Div("Checking settings…", className="jobs-plan-placeholder"))
    elif not prepare_state._prepare_messages:
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
        str(len(prepare_state._prepare_messages)),
        str(tool_check.get("status")),
        str(tool_check.get("done")),
    ])

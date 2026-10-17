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
RTL analysis dashboard page of Odatix Explorer.

Unlike the chart pages, this page does not use the chart shell/sidebar: it is a
self-contained dashboard reading the "analysis" records of the shared
ResultStore (see odatix.components.export_analysis), each as the
AnalysisResult it was written from (odatix.lib.analysis). It shows, like the
terminal report of "odatix analyze":

  * how many designs ended in each status, per tool;
  * the kinds of findings, and the tools that reported them (clicking one
    keeps the designs it was reported for);
  * every design, with what needs attention first, and the expected findings
    -- those that are normal -- apart, folded.
"""

import dash
from dash import html, dcc, Input, Output, State, ALL

from odatix.explorer.core.store import STORE
import odatix.explorer.ui.components as components
import odatix.lib.analysis as analysis
from odatix.gui.page_scope import anchor, page_callback

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "explorer_analysis"

POLL_INTERVAL_MS = 2000

# Status -> (css modifier, glyph), in the order of the stat row and the list.
STATUS_ORDER = list(analysis.STATUSES)
STATUS_META = {
  analysis.STATUS_FAILED: ("failed", "✗"),
  analysis.STATUS_TOOL_FAILURE: ("tool-failure", "!"),
  analysis.STATUS_INCOMPLETE: ("incomplete", "?"),
  analysis.STATUS_WARNING: ("warning", "⚠"),
  analysis.STATUS_UNSUPPORTED: ("unsupported", "–"),
  analysis.STATUS_PASSED: ("passed", "✓"),
}

SEVERITY_LABELS = {
  "error": ("Errors", "error"),
  "critical": ("Critical warnings", "critical"),
  "warning": ("Warnings", "warning"),
  "info": ("Information", "info"),
}


######################################
# Data helpers
######################################


def _analysis_results():
  """Every analysis result across all sources."""
  results = []
  for record in STORE.records():
    meta = record.get("meta", {})
    if str(meta.get("type", "")).lower() == analysis.TYPE_ANALYSIS:
      results.append(analysis.AnalysisResult.from_record(record))
  return results


def _categories():
  return {category.name: category for category in analysis.load_categories()}


def _tool_names(results):
  return sorted({result.tool for result in results if result.tool})


def _count_by_status(results):
  counts = {status: 0 for status in STATUS_ORDER}
  for result in results:
    counts[result.status] = counts.get(result.status, 0) + 1
  return counts


def _has_category(result, category):
  return any(finding.category == category for finding in result.attention)


######################################
# UI building
######################################


def _stat_card(status, count, total, active):
  modifier, glyph = STATUS_META[status]
  percent = (100 * count / total) if total else 0
  return html.Button(
    [
      html.Div(glyph, className="xpa-stat-glyph"),
      html.Div(
        [
          html.Div(str(count), className="xpa-stat-count"),
          html.Div(analysis.STATUS_LABELS[status], className="xpa-stat-label"),
        ],
        className="xpa-stat-text",
      ),
      html.Div(f"{percent:.0f}%", className="xpa-stat-percent"),
    ],
    id={"type": "xpa-stat", "status": status},
    n_clicks=0,
    title=analysis.STATUS_DESCRIPTIONS[status],
    className="xpa-stat-card xpa-" + modifier + (" xpa-active" if active else ""),
  )


def _total_card(total):
  return html.Div(
    [
      html.Div(str(total), className="xpa-stat-count"),
      html.Div("Total", className="xpa-stat-label"),
    ],
    className="xpa-stat-card xpa-total",
  )


def _stats_row(results, active_status):
  total = len(results)
  counts = _count_by_status(results)
  cards = [_total_card(total)]
  for status in STATUS_ORDER:
    # A status no design ended in, and that is no news, takes no room.
    if counts[status] or status in (analysis.STATUS_FAILED, analysis.STATUS_WARNING, analysis.STATUS_PASSED):
      cards.append(_stat_card(status, counts[status], total, active_status == status))
  return cards


def _tool_chip(value, label, is_active):
  return html.Button(
    label,
    id={"type": "xpa-tool", "tool": value},
    n_clicks=0,
    className="xpa-tool-chip" + (" xpa-active" if is_active else ""),
  )


def _tool_filter_chips(all_tools, active):
  """Tool filter chips ("All tools" + one per tool). Empty when a single tool."""
  if len(all_tools) < 2:
    return []
  chips = [_tool_chip("all", "All tools", active in (None, "all"))]
  for tool in all_tools:
    chips.append(_tool_chip(tool, tool, active == tool))
  return chips


def _status_cell(status):
  """One matrix cell: the status glyph (or a dash when the tool has no result)."""
  if status is None:
    return html.Td(html.Span("·", className="xpa-cell-none"), className="xpa-cell")
  modifier, glyph = STATUS_META[status]
  return html.Td(
    html.Span(glyph, className="xpa-cell-glyph xpa-" + modifier),
    className="xpa-cell",
    title=analysis.STATUS_LABELS[status],
  )


def _matrix(results):
  """
  Recap table (design x tool): one row per design, one column per eda tool
  present in the data, each cell showing that tool's status.
  """
  if not results:
    return None
  tools = _tool_names(results)
  status_by_name = {}
  for result in results:
    status_by_name.setdefault(result.name, {})[result.tool] = result.status
  names = sorted(status_by_name, key=str.lower)

  header = html.Tr(
    [html.Th("Design", className="xpa-matrix-arch-head")]
    + [html.Th(tool, className="xpa-matrix-tool-head", title=tool) for tool in tools]
  )
  rows = []
  for name in names:
    cells = [html.Td(name, className="xpa-matrix-arch", title=name)]
    for tool in tools:
      cells.append(_status_cell(status_by_name[name].get(tool)))
    rows.append(html.Tr(cells, className="xpa-matrix-row"))

  table = html.Table([html.Thead(header), html.Tbody(rows)], className="xpa-matrix-table")
  return html.Details(
    [
      html.Summary("Status by tool", className="xpa-matrix-summary"),
      html.Div(table, className="xpa-matrix-scroll"),
    ],
    open=len(tools) > 1,
    className="xpa-matrix-section",
  )


def _category_table(results, active_category):
  """
  How many designs each kind of finding was reported for, by each tool.
  Clicking a kind keeps the designs it was reported for.
  """
  tools = _tool_names(results)
  designs = {}
  for result in results:
    for finding in result.attention:
      if finding.severity != "info":
        designs.setdefault((finding.category, result.tool), set()).add(result.name)
  if not designs:
    return None

  categories = [category for category in analysis.load_categories()
                if any((category.name, tool) in designs for tool in tools)]
  header = html.Tr(
    [html.Th("Finding", className="xpa-matrix-arch-head")]
    + [html.Th(tool, className="xpa-matrix-tool-head", title=tool) for tool in tools]
  )
  rows = []
  for category in categories:
    cells = [html.Td(
      html.Button(
        category.label,
        id={"type": "xpa-category", "category": category.name},
        n_clicks=0,
        title=category.description,
        className="xpa-category-button" + (" xpa-active" if active_category == category.name else ""),
      ),
      className="xpa-matrix-arch",
    )]
    for tool in tools:
      count = len(designs.get((category.name, tool), ()))
      cells.append(html.Td(
        html.Span(str(count) if count else "·", className="xpa-cell-count" if count else "xpa-cell-none"),
        className="xpa-cell",
      ))
    rows.append(html.Tr(cells, className="xpa-matrix-row"))

  table = html.Table([html.Thead(header), html.Tbody(rows)], className="xpa-matrix-table")
  return html.Details(
    [
      html.Summary("Findings by kind (designs each one was reported for)", className="xpa-matrix-summary"),
      html.Div(table, className="xpa-matrix-scroll"),
    ],
    open=True,
    className="xpa-matrix-section",
  )


def _finding_item(finding, categories):
  category = categories.get(finding.category)
  label = category.label if category else finding.category
  head = [
    html.Span(label, className="xpa-chip xpa-chip-category", title=category.description if category else ""),
    html.Span(finding.message, className="xpa-finding-message"),
  ]
  if finding.count > 1:
    head.append(html.Span("×" + str(finding.count), className="xpa-chip xpa-chip-count"))
  where = []
  if finding.location:
    where.append(html.Code(finding.location, className="xpa-log-path"))
  if finding.code:
    where.append(html.Span(finding.code, className="xpa-finding-code"))
  if finding.reason:
    where.append(html.Span(finding.reason, className="xpa-finding-reason"))
  children = [html.Div(head, className="xpa-finding-head")]
  if where:
    children.append(html.Div(where, className="xpa-finding-where"))
  if finding.detail:
    children.append(html.Pre("\n".join(finding.detail), className="xpa-finding-detail"))
  return html.Li(children, className="xpa-finding xpa-finding-" + finding.severity)


def _findings_block(title, findings, categories, modifier):
  return html.Div(
    [
      html.Div(title + " (" + str(len(findings)) + ")", className="xpa-detail-title"),
      html.Ul([_finding_item(finding, categories) for finding in findings], className="xpa-detail-list"),
    ],
    className="xpa-detail-block xpa-detail-" + modifier,
  )


def _record_row(result, categories):
  modifier, glyph = STATUS_META[result.status]

  chips = []
  for severity, css in (("error", "error"), ("critical", "critical"), ("warning", "warning")):
    count = result.count(severity)
    if count:
      label = SEVERITY_LABELS[severity][0].lower().rstrip("s")
      chips.append(html.Span(
        [str(count), " " + label + ("s" if count > 1 else "")],
        className="xpa-chip xpa-chip-" + css,
      ))
  expected_count = result.count("expected")
  if expected_count:
    chips.append(html.Span([str(expected_count), " expected"], className="xpa-chip xpa-chip-expected"))

  summary_children = [
    html.Span(glyph, className="xpa-row-badge xpa-" + modifier),
    html.Span(result.name, className="xpa-row-name"),
  ]
  if result.tool:
    summary_children.append(html.Span(result.tool, className="xpa-chip xpa-chip-tool"))
  if result.summary:
    summary_children.append(html.Span(result.summary, className="xpa-row-headline", title=result.summary))
  summary_children.append(html.Span(chips, className="xpa-row-chips"))

  body = []
  if result.note:
    body.append(html.Div(result.note, className="xpa-detail-note"))
  attention = result.attention
  for severity in analysis.SEVERITIES:
    findings = [finding for finding in attention if finding.severity == severity]
    if findings:
      body.append(_findings_block(SEVERITY_LABELS[severity][0], findings, categories, SEVERITY_LABELS[severity][1]))
  if result.omitted:
    body.append(html.Div(
      f"{result.omitted} more finding(s) not kept: see the log.", className="xpa-detail-note",
    ))
  expected = result.expected
  if expected:
    body.append(html.Details(
      [
        html.Summary("Expected (" + str(len(expected)) + "), not counted", className="xpa-expected-summary"),
        html.Ul([_finding_item(finding, categories) for finding in expected], className="xpa-detail-list"),
      ],
      className="xpa-detail-block xpa-detail-expected",
    ))
  for log in result.logs:
    body.append(html.Div(["Log: ", html.Code(str(log), className="xpa-log-path")], className="xpa-detail-note"))
  if not body:
    body.append(html.Div("Nothing reported.", className="xpa-detail-note"))

  return html.Details(
    [
      html.Summary(summary_children, className="xpa-row-summary"),
      html.Div(body, className="xpa-row-body"),
    ],
    className="xpa-row xpa-row-" + modifier,
  )


def _filtered(results, active_status, active_category, search):
  if active_status in STATUS_META:
    results = [result for result in results if result.status == active_status]
  if active_category and active_category != "all":
    results = [result for result in results if _has_category(result, active_category)]
  if search:
    needle = search.strip().lower()
    results = [result for result in results if needle in result.name.lower()]
  return results


def _list_children(all_results, results):
  if not all_results:
    return html.Div(
      [
        html.Div("No analysis results yet", className="xpa-empty-title"),
        html.Div(
          "Run an RTL analysis (odatix analyze) to populate this dashboard.",
          className="xpa-empty-subtitle",
        ),
      ],
      className="xpa-empty",
    )
  if not results:
    return html.Div(
      html.Div("No design matches the current filter.", className="xpa-empty-subtitle"),
      className="xpa-empty",
    )
  categories = _categories()
  results = sorted(results, key=lambda result: (STATUS_ORDER.index(result.status), result.name.lower(), result.tool))
  return [_record_row(result, categories) for result in results]


######################################
# Layout
######################################


def layout(**kwargs):
  return html.Div(
    [
      anchor(PAGE_SCOPE),
      dcc.Interval(id="xpa-poll", interval=POLL_INTERVAL_MS),
      dcc.Store(id="xpa-data-version", data=-1),
      dcc.Store(id="xpa-status-filter", data="all"),
      dcc.Store(id="xpa-tool-filter", data="all"),
      dcc.Store(id="xpa-category-filter", data="all"),
      html.Div(
        [
          html.Div(
            [
              html.Div(
                [
                  html.H1("RTL Analysis Dashboard", className="xpa-title"),
                  html.P(
                    "What every analysis found, design by design: what needs attention first, what is expected apart.",
                    className="xpa-subtitle",
                  ),
                ],
              ),
              html.Div(
                [
                  html.Span(id="xpa-status", className="xp-status"),
                  html.Button("↻", id="xpa-refresh", n_clicks=0, className="xp-mini-button xp-refresh", title="Reload result files now"),
                ],
                className="xpa-header-actions",
              ),
            ],
            className="xpa-header",
          ),
          html.Div(id="xpa-stats", className="xpa-stats"),
          html.Div(id="xpa-tools", className="xpa-tools"),
          dcc.Input(
            id="xpa-search",
            type="text",
            placeholder="Filter designs…",
            debounce=False,
            className="xp-text-input xpa-search",
          ),
          html.Div(id="xpa-matrix", className="xpa-matrix"),
          html.Div(id="xpa-categories", className="xpa-matrix"),
          html.Div(id="xpa-list", className="xpa-list"),
        ],
        className="xpa-dashboard",
      ),
    ],
    className="xp-page xpa-page",
  )


######################################
# Callbacks
######################################


@dash.callback(
  Output("xpa-data-version", "data"),
  Output("xpa-status", "children"),
  Input("xpa-poll", "n_intervals"),
  Input("xpa-refresh", "n_clicks"),
  Input("odatix-settings", "data"),
  State("xpa-data-version", "data"),
)
def poll(_intervals, _clicks, settings, current_version):
  """Re-point / rescan the store; bump the page data version on change."""
  if isinstance(settings, dict):
    result_path = settings.get("result_path")
    if result_path:
      STORE.configure(result_path)

  triggered = dash.callback_context.triggered_id
  STORE.poll(force=triggered in ("xpa-refresh", "odatix-settings"))
  if triggered == "xpa-refresh":
    STORE.mark_loaded()

  status = components.status_text(STORE)
  if current_version == STORE.version:
    return dash.no_update, status
  return STORE.version, status


@page_callback(PAGE_SCOPE,
  Output("xpa-status-filter", "data"),
  Input({"type": "xpa-stat", "status": ALL}, "n_clicks"),
  State("xpa-status-filter", "data"),
  prevent_initial_call=True,
)
def toggle_status_filter(_clicks, current):
  """Clicking a stat card filters the list by that status; clicking it again clears."""
  triggered = dash.callback_context.triggered_id
  if not isinstance(triggered, dict) or not any(_clicks or []):
    raise dash.exceptions.PreventUpdate
  status = triggered.get("status")
  return "all" if status == current else status


@page_callback(PAGE_SCOPE,
  Output("xpa-tool-filter", "data"),
  Input({"type": "xpa-tool", "tool": ALL}, "n_clicks"),
  State("xpa-tool-filter", "data"),
  prevent_initial_call=True,
)
def toggle_tool_filter(_clicks, current):
  """Clicking a tool chip scopes the dashboard to that tool; "All tools" clears."""
  triggered = dash.callback_context.triggered_id
  if not isinstance(triggered, dict) or not any(_clicks or []):
    raise dash.exceptions.PreventUpdate
  tool = triggered.get("tool")
  if tool == "all":
    return "all"
  return "all" if tool == current else tool


@page_callback(PAGE_SCOPE,
  Output("xpa-category-filter", "data"),
  Input({"type": "xpa-category", "category": ALL}, "n_clicks"),
  State("xpa-category-filter", "data"),
  prevent_initial_call=True,
)
def toggle_category_filter(_clicks, current):
  """Clicking a kind of finding keeps the designs it was reported for; clicking it again clears."""
  triggered = dash.callback_context.triggered_id
  if not isinstance(triggered, dict) or not any(_clicks or []):
    raise dash.exceptions.PreventUpdate
  category = triggered.get("category")
  return "all" if category == current else category


@dash.callback(
  Output("xpa-stats", "children"),
  Output("xpa-tools", "children"),
  Output("xpa-matrix", "children"),
  Output("xpa-categories", "children"),
  Output("xpa-list", "children"),
  Input("xpa-data-version", "data"),
  Input("xpa-status-filter", "data"),
  Input("xpa-tool-filter", "data"),
  Input("xpa-category-filter", "data"),
  Input("xpa-search", "value"),
)
def render(_version, active_status, tool_filter, category_filter, search):
  base = _analysis_results()
  all_tools = _tool_names(base)

  # A tool filter scopes everything below it to that tool.
  if tool_filter and tool_filter != "all":
    working = [result for result in base if result.tool == tool_filter]
  else:
    working = base

  searched = _filtered(working, None, None, search)
  return (
    _stats_row(working, active_status),
    _tool_filter_chips(all_tools, tool_filter),
    _matrix(searched),
    _category_table(searched, category_filter),
    _list_children(base, _filtered(working, active_status, category_filter, search)),
  )


dash.register_page(__name__, path="/explorer/analysis", name="Analysis", title="Odatix Explorer - Analysis", order=20, layout=layout)

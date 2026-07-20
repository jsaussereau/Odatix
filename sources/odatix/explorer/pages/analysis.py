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
self-contained dashboard that reads the "analysis" records from the shared
ResultStore (produced by odatix.components.export_analysis) and renders a clear
overview of the pass/warning/error status of every analyzed architecture, with
some statistics and an intuitive, expandable detail of the errors and warnings.
"""

import dash
from dash import html, dcc, Input, Output, State, ALL

from odatix.explorer.core.store import STORE
import odatix.explorer.ui.components as components
import odatix.components.export_analysis as export_analysis

POLL_INTERVAL_MS = 2000

# Status → (display label, css modifier, glyph). Ordered by severity for the
# stat row and the list sort.
STATUS_ORDER = ["FAILED", "WARNING", "INCOMPLETE", "PASSED"]
STATUS_META = {
  "FAILED": ("Failed", "failed", "✗"),       # ✗
  "WARNING": ("Warning", "warning", "⚠"),     # ⚠
  "INCOMPLETE": ("Incomplete", "incomplete", "/"),
  "PASSED": ("Passed", "passed", "✓"),        # ✓
}


######################################
# Data helpers
######################################


def _analysis_records():
  """Every analysis record across all sources (see export_analysis.TYPE_ANALYSIS)."""
  records = []
  for record in STORE.records():
    meta = record.get("meta", {})
    if str(meta.get("type", "")).lower() == export_analysis.TYPE_ANALYSIS:
      records.append(record)
  return records


def _record_status(record):
  status = str(record.get("meta", {}).get("_status", "")).upper()
  return status if status in STATUS_META else "INCOMPLETE"


def _record_name(record):
  meta = record.get("meta", {})
  arch = str(meta.get("architecture", ""))
  config = str(meta.get("configuration", ""))
  return arch + ("/" + config if config else "")


def _record_tool(record):
  return str(record.get("meta", {}).get("tool", ""))


def _tool_names(records):
  """Sorted list of the eda tools present in the given records."""
  return sorted({_record_tool(record) for record in records if _record_tool(record)})


def _count_by_status(records):
  counts = {status: 0 for status in STATUS_ORDER}
  for record in records:
    counts[_record_status(record)] += 1
  return counts


######################################
# UI building
######################################


def _stat_card(status, count, total, active):
  label, modifier, glyph = STATUS_META[status]
  percent = (100 * count / total) if total else 0
  return html.Button(
    [
      html.Div(glyph, className="xpa-stat-glyph"),
      html.Div(
        [
          html.Div(str(count), className="xpa-stat-count"),
          html.Div(label, className="xpa-stat-label"),
        ],
        className="xpa-stat-text",
      ),
      html.Div(f"{percent:.0f}%", className="xpa-stat-percent"),
    ],
    id={"type": "xpa-stat", "status": status},
    n_clicks=0,
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


def _stats_row(records, active_status):
  total = len(records)
  counts = _count_by_status(records)
  cards = [_total_card(total)]
  for status in STATUS_ORDER:
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
    return html.Td(html.Span("–", className="xpa-cell-none"), className="xpa-cell")
  label, modifier, glyph = STATUS_META[status]
  return html.Td(
    html.Span(glyph, className="xpa-cell-glyph xpa-" + modifier),
    className="xpa-cell",
    title=label,
  )


def _matrix(records, search):
  """
  Recap table (architecture × tool): one row per architecture/configuration,
  one column per eda tool present in the data, each cell showing that tool's
  status glyph (or a dash when the tool has no result for that architecture).
  Only tools actually present are shown, so the table stays flexible.
  """
  if not records:
    return None

  needle = search.strip().lower() if search else ""
  tools = _tool_names(records)

  status_by_name = {}
  names = []
  for record in records:
    name = _record_name(record)
    if needle and needle not in name.lower():
      continue
    if name not in status_by_name:
      status_by_name[name] = {}
      names.append(name)
    status_by_name[name][_record_tool(record)] = _record_status(record)

  if not names:
    return None
  names.sort(key=str.lower)

  header = html.Tr(
    [html.Th("Architecture", className="xpa-matrix-arch-head")]
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
      html.Summary("Summary table", className="xpa-matrix-summary"),
      html.Div(table, className="xpa-matrix-scroll"),
    ],
    open=True,
    className="xpa-matrix-section",
  )


def _detail_list(title, items, item_class):
  return html.Div(
    [
      html.Div(title, className="xpa-detail-title"),
      html.Ul([html.Li(item, className=item_class) for item in items], className="xpa-detail-list"),
    ],
    className="xpa-detail-block",
  )


def _record_row(record):
  meta = record.get("meta", {})
  metrics = record.get("metrics", {})
  status = _record_status(record)
  label, modifier, glyph = STATUS_META[status]

  errors = meta.get("_errors") or ([meta["_error_message"]] if meta.get("_error_message") else [])
  critical_warnings = meta.get("_critical_warnings") or []
  standard_warnings = int(metrics.get("standard_warning_count", 0) or 0)
  error_count = int(metrics.get("error_count", 0) or 0)
  warning_count = int(metrics.get("warning_count", 0) or 0)
  log_file = meta.get("_log_file")
  tool = str(meta.get("tool", ""))

  # Summary line: status badge, name, tool chip, counts.
  chips = []
  if error_count:
    chips.append(html.Span([str(error_count), " error" + ("s" if error_count > 1 else "")], className="xpa-chip xpa-chip-error"))
  if warning_count:
    chips.append(html.Span([str(warning_count), " warning" + ("s" if warning_count > 1 else "")], className="xpa-chip xpa-chip-warning"))

  summary_children = [
    html.Span(glyph, className="xpa-row-badge xpa-" + modifier),
    html.Span(_record_name(record), className="xpa-row-name"),
  ]
  if tool:
    summary_children.append(html.Span(tool, className="xpa-chip xpa-chip-tool"))
  summary_children.append(html.Span(chips, className="xpa-row-chips"))

  # Detail body: errors, critical warnings, standard warnings, log path.
  body = []
  if errors:
    body.append(_detail_list("Errors", errors, "xpa-detail-error"))
  if critical_warnings:
    body.append(_detail_list("Critical warnings", critical_warnings, "xpa-detail-warning"))
  if standard_warnings:
    body.append(
      html.Div(
        f"{standard_warnings} standard warning(s) not listed — see the log for details.",
        className="xpa-detail-note",
      )
    )
  if log_file:
    body.append(html.Div(["Log: ", html.Code(str(log_file), className="xpa-log-path")], className="xpa-detail-note"))
  if not body:
    body.append(html.Div("No issues detected.", className="xpa-detail-note"))

  return html.Details(
    [
      html.Summary(summary_children, className="xpa-row-summary"),
      html.Div(body, className="xpa-row-body"),
    ],
    className="xpa-row xpa-row-" + modifier,
  )


def _list_children(records, active_status, search):
  if not records:
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

  filtered = records
  if active_status in STATUS_META:
    filtered = [record for record in filtered if _record_status(record) == active_status]
  if search:
    needle = search.strip().lower()
    filtered = [record for record in filtered if needle in _record_name(record).lower()]

  filtered = sorted(filtered, key=lambda record: (STATUS_ORDER.index(_record_status(record)), _record_name(record).lower()))

  if not filtered:
    return html.Div(
      html.Div("No architecture matches the current filter.", className="xpa-empty-subtitle"),
      className="xpa-empty",
    )

  return [_record_row(record) for record in filtered]


######################################
# Layout
######################################


def layout(**kwargs):
  return html.Div(
    [
      dcc.Interval(id="xpa-poll", interval=POLL_INTERVAL_MS),
      dcc.Store(id="xpa-data-version", data=-1),
      dcc.Store(id="xpa-status-filter", data="all"),
      dcc.Store(id="xpa-tool-filter", data="all"),
      html.Div(
        [
          html.Div(
            [
              html.Div(
                [
                  html.H1("RTL Analysis Dashboard", className="xpa-title"),
                  html.P(
                    "Pass / warning / error overview of every analyzed architecture.",
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
            placeholder="Filter architectures…",
            debounce=False,
            className="xp-text-input xpa-search",
          ),
          html.Div(id="xpa-matrix", className="xpa-matrix"),
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


@dash.callback(
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


@dash.callback(
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


@dash.callback(
  Output("xpa-stats", "children"),
  Output("xpa-tools", "children"),
  Output("xpa-matrix", "children"),
  Output("xpa-list", "children"),
  Input("xpa-data-version", "data"),
  Input("xpa-status-filter", "data"),
  Input("xpa-tool-filter", "data"),
  Input("xpa-search", "value"),
)
def render(_version, active_status, tool_filter, search):
  base = _analysis_records()
  all_tools = _tool_names(base)

  # A tool filter scopes stats, the summary table and the list to that tool.
  if tool_filter and tool_filter != "all":
    working = [record for record in base if _record_tool(record) == tool_filter]
  else:
    working = base

  return (
    _stats_row(working, active_status),
    _tool_filter_chips(all_tools, tool_filter),
    _matrix(working, search),
    _list_children(working, active_status, search),
  )


dash.register_page(__name__, path="/explorer/analysis", name="Analysis", title="Odatix Explorer - Analysis", order=20, layout=layout)

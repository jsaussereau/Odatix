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
Explorer landing page: chart view cards and live data source status.
"""

import dash
from dash import dcc, html, Input, Output, State, ALL
from dash_svg import Svg, Path, Ellipse

from odatix.components import home_shared
from odatix.explorer.core.store import STORE
import odatix.explorer.core.views as views
import odatix.explorer.callbacks.views as views_callbacks
from odatix.explorer.ui.thumbnails import pictogram, section_header, view_thumbnail

_CHART_CARDS = [
  {"name": "Lines", "link": "/explorer/lines", "kind": "lines", "description": "Metric vs any dimension, point by point"},
  {"name": "Columns", "link": "/explorer/columns", "kind": "columns", "description": "Bar comparison across configurations"},
  {"name": "Scatter", "link": "/explorer/scatter", "kind": "scatter", "description": "Any metric against any other metric"},
  {"name": "Scatter 3D", "link": "/explorer/scatter3d", "kind": "scatter3d", "description": "Three metrics in one 3D view"},
  {"name": "Radar", "link": "/explorer/radar", "kind": "radar", "description": "Polar view of a metric"},
  {"name": "Parallel Coordinates", "link": "/explorer/parcoords", "kind": "parcoords", "description": "Compare several metrics across configurations"},
  {"name": "Overview", "link": "/explorer/overview", "kind": "overview", "description": "Every metric at a glance"},
  {"name": "Table", "link": "/explorer/table", "kind": "table", "description": "Sortable, filterable data table"},
]

_REPORT_CARDS = [
  {"name": "Insights", "link": "/explorer/insights", "kind": "insights", "description": "Charts Odatix suggests from your results"},
  {"name": "RTL Analysis", "link": "/explorer/analysis", "kind": "analysis", "description": "RTL analysis warnings and errors dashboard"},
  {"name": "Design Space Exploration", "link": "/explorer/dse", "kind": "dse", "description": "Pareto front and progress of a design space exploration"},
]


def _card_visual(card):
  return pictogram(card.get("kind"))

def _view_card(view):
  name = view.get("name", "?")
  created = str(view.get("created", ""))[:10]
  meta = " · ".join(part for part in [views.kind_label(view.get("kind")), ", ".join(view.get("sources") or []), created] if part)
  description = str(view.get("description") or "").strip()
  text_children = [html.Div(name, className="xp-view-card-name")]
  if description:
    text_children.append(html.Div(description, className="xp-view-card-desc", title=description))
  text_children.append(html.Div(meta, className="xp-view-card-meta", title=meta))
  return html.Button(
    [
      html.Div(view_thumbnail(view), className="xp-view-thumb-box"),
      html.Div(
        text_children,
        className="xp-view-card-text",
      ),
    ],
    id={"type": "xp-view-open", "name": name},
    n_clicks=0,
    type="button",
    className="xp-view-card",
    title="Restore this view",
  )



def _source_icon():
  """Small database-cylinder glyph for a result-file source card."""
  return Svg(
    [
      Ellipse(cx="12", cy="5.5", rx="7.5", ry="2.6"),
      Path(d="M4.5 5.5 V18 c0 1.45 3.36 2.6 7.5 2.6 s7.5 -1.15 7.5 -2.6 V5.5"),
      Path(d="M4.5 11.75 c0 1.45 3.36 2.6 7.5 2.6 s7.5 -1.15 7.5 -2.6"),
    ],
    viewBox="0 0 24 24",
    width="20",
    height="20",
    fill="none",
    stroke="currentColor",
    className="xp-source-icon",
    # stroke-width/linecap/linejoin are not Svg props: set via style so they
    # cascade to the child shapes (same pattern as gui.icons._line_icon).
    style={"strokeWidth": "1.6", "strokeLinecap": "round", "strokeLinejoin": "round"},
  )


def _source_card(source):
  """One result-file source: icon + name + record count / schema (or error)."""
  if source.error:
    detail = "⚠ " + str(source.error)
  else:
    detail = str(source.record_count) + " records · " + source.schema
  return html.Div(
    [
      html.Div(_source_icon(), className="xp-source-icon-box"),
      html.Div(
        [
          html.Div(source.name, className="xp-source-name", title=source.name),
          html.Div(detail, className="xp-source-detail", title=detail),
        ],
        className="xp-source-text",
      ),
    ],
    className="xp-source-card" + (" xp-source-error" if source.error else ""),
  )


def _empty_sources():
  """Friendly empty state when no result file was found yet."""
  return html.Div(
    [
      html.Div("No result file found yet", className="xp-source-empty-title"),
      html.Div(
        'Looked for "results_*.yml" in "' + str(STORE.result_path) + '". '
        "Run a synthesis, a workflow or an analysis — sources appear here as soon as results are written.",
        className="xp-source-empty-subtitle",
      ),
    ],
    className="xp-source-empty",
  )


def layout(**kwargs):
  return html.Div(
    [
      dcc.Interval(id="xp-home-poll", interval=3000),
      # refresh=True: full reload so the target chart page rehydrates the session
      # stores written by open_view_from_home and mounts already restored (see
      # the same note in ui/shell.py for xp-url).
      dcc.Location(id="xp-home-url", refresh=True),
      home_shared.home_header("Odatix Explorer", "Visualize, compare and explore your results."),
      section_header("Charts"),
      home_shared.home_card_grid(_CHART_CARDS, _card_visual),
      section_header("Reports"),
      home_shared.home_card_grid(_REPORT_CARDS, _card_visual),
      html.Div(id="xp-home-sources", className="xp-home-section"),
      html.Div(id="xp-home-views", className="xp-home-section"),
    ],
    className="xp-home",
  )


dash.register_page(__name__, path="/explorer", name="Explorer", title="Odatix Explorer", order=20, layout=layout)


@dash.callback(
  Output("xp-home-sources", "children"),
  Input("xp-home-poll", "n_intervals"),
  Input("odatix-settings", "data"),
)
def update_home_sources(_intervals, settings):
  if isinstance(settings, dict) and settings.get("result_path"):
    STORE.configure(settings.get("result_path"))
  STORE.poll()

  sources = STORE.sources()
  if not sources:
    return [section_header("Data sources"), _empty_sources()]

  return [
    section_header("Data sources", len(sources)),
    html.Div([_source_card(source) for source in sources], className="xp-source-grid"),
  ]


@dash.callback(
  Output("xp-home-views", "children"),
  Input("xp-home-poll", "n_intervals"),
  Input("odatix-settings", "data"),
)
def update_home_views(_intervals, settings):
  if isinstance(settings, dict) and settings.get("result_path"):
    STORE.configure(settings.get("result_path"))

  saved = views.list_views(STORE.result_path)
  if not saved:
    return None
  return [
    section_header("Saved views", len(saved)),
    html.Div([_view_card(view) for view in saved], className="xp-view-cards"),
  ]


@dash.callback(
  Output("xp-control-state", "data", allow_duplicate=True),
  Output("xp-filter-state", "data", allow_duplicate=True),
  Output("xp-rule-state", "data", allow_duplicate=True),
  Output("xp-ui-state", "data", allow_duplicate=True),
  Output("xp-home-url", "pathname"),
  Input({"type": "xp-view-open", "name": ALL}, "n_clicks"),
  State("xp-ui-state", "data"),
  prevent_initial_call=True,
)
def open_view_from_home(clicks, ui_state):
  """Restore a saved view from its home card, then navigate to its chart page.

  Only the session stores are written here: the chart page re-applies them at
  mount (update_control_options, update_sources, apply_ui_state, ...), which
  is the exact mechanism that restores state on any page swap.
  """
  triggered = dash.callback_context.triggered_id
  if not isinstance(triggered, dict) or not any(clicks or []):
    raise dash.exceptions.PreventUpdate
  try:
    payload, ui_patch, _warnings = views_callbacks.restore_payload(triggered.get("name"))
  except ValueError:
    raise dash.exceptions.PreventUpdate

  ui_state = dict(ui_state or {})
  ui_state.update(ui_patch)
  return payload["controls"], payload["filter_state"], payload["rule_state"], ui_state, "/explorer/" + payload["kind"]

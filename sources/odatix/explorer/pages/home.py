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
from dash_svg import Svg, Polyline, Rect, Circle, Polygon, Line

from odatix.components import home_shared
from odatix.explorer.core.store import STORE
import odatix.explorer.core.views as views
import odatix.explorer.charts.palettes as palettes
import odatix.explorer.callbacks.views as views_callbacks

_STROKE = "var(--theme-primary-color, #228BE6)"
_FILL = "var(--theme-text-color, #24292e)"


def _svg(children):
  return Svg(children, viewBox="0 0 48 48", width="48", height="48", fill="none", className="xp-card-pictogram")


def _pictogram(kind):
  if kind == "lines":
    return _svg([
      Polyline(points="4,38 16,24 28,30 44,10", stroke=_STROKE, strokeWidth="2.5", fill="none"),
      Circle(cx="16", cy="24", r="3", fill=_STROKE),
      Circle(cx="28", cy="30", r="3", fill=_STROKE),
    ])
  if kind == "columns":
    return _svg([
      Rect(x="6", y="24", width="8", height="18", rx="1.5", fill=_STROKE),
      Rect(x="20", y="12", width="8", height="30", rx="1.5", fill=_STROKE, opacity="0.7"),
      Rect(x="34", y="18", width="8", height="24", rx="1.5", fill=_STROKE, opacity="0.45"),
    ])
  if kind == "scatter":
    return _svg([
      Circle(cx="10", cy="34", r="3.5", fill=_STROKE),
      Circle(cx="20", cy="22", r="3.5", fill=_STROKE, opacity="0.8"),
      Circle(cx="30", cy="28", r="3.5", fill=_STROKE, opacity="0.6"),
      Circle(cx="38", cy="12", r="3.5", fill=_STROKE, opacity="0.4"),
    ])
  if kind == "scatter3d":
    return _svg([
      Line(x1="24", y1="42", x2="24", y2="20", stroke=_FILL, strokeWidth="1.5", opacity="0.5"),
      Line(x1="24", y1="42", x2="6", y2="32", stroke=_FILL, strokeWidth="1.5", opacity="0.5"),
      Line(x1="24", y1="42", x2="42", y2="32", stroke=_FILL, strokeWidth="1.5", opacity="0.5"),
      Circle(cx="16", cy="20", r="3", fill=_STROKE),
      Circle(cx="32", cy="14", r="3", fill=_STROKE, opacity="0.7"),
      Circle(cx="34", cy="26", r="3", fill=_STROKE, opacity="0.5"),
    ])
  if kind == "radar":
    return _svg([
      Polygon(points="24,4 43,18 36,42 12,42 5,18", stroke=_FILL, strokeWidth="1.5", fill="none", opacity="0.4"),
      Polygon(points="24,12 35,20 31,34 17,34 13,20", stroke=_STROKE, strokeWidth="2.5", fill=_STROKE, fillOpacity="0.15"),
    ])
  # overview
  return _svg([
    Rect(x="5", y="5", width="17", height="17", rx="2", stroke=_STROKE, strokeWidth="2", fill="none"),
    Rect(x="26", y="5", width="17", height="17", rx="2", stroke=_STROKE, strokeWidth="2", fill="none", opacity="0.7"),
    Rect(x="5", y="26", width="17", height="17", rx="2", stroke=_STROKE, strokeWidth="2", fill="none", opacity="0.7"),
    Rect(x="26", y="26", width="17", height="17", rx="2", stroke=_STROKE, strokeWidth="2", fill="none", opacity="0.4"),
  ])


_CARDS = [
  {"name": "Lines", "link": "/explorer/lines", "kind": "lines", "description": "Metric vs any dimension, point by point"},
  {"name": "Columns", "link": "/explorer/columns", "kind": "columns", "description": "Bar comparison across configurations"},
  {"name": "Scatter", "link": "/explorer/scatter", "kind": "scatter", "description": "Any metric against any other metric"},
  {"name": "Scatter 3D", "link": "/explorer/scatter3d", "kind": "scatter3d", "description": "Three metrics in one 3D view"},
  {"name": "Radar", "link": "/explorer/radar", "kind": "radar", "description": "Polar view of a metric"},
  {"name": "Overview", "link": "/explorer/overview", "kind": "overview", "description": "Every metric at a glance"},
]


def _card_visual(card):
  return _pictogram(card.get("kind"))


def _view_thumbnail(view):
  """Tiny data sketch saved inside the view file, or the kind pictogram."""
  thumb = view.get("thumb")
  palette = view.get("palette")
  if not isinstance(thumb, dict):
    return _pictogram(view.get("kind"))

  children = []
  if thumb.get("t") == "bars":
    bars = thumb.get("b") or []
    if bars:
      slot = views.THUMB_WIDTH / len(bars)
      width = max(2, round(slot * 0.7))
      for index, (color, top) in enumerate(bars):
        children.append(Rect(
          x=str(round(index * slot + (slot - width) / 2)), y=str(top),
          width=str(width), height=str(max(1, views.THUMB_HEIGHT - top)),
          rx="1", fill=palettes.get_color(color, palette),
        ))
  else:
    for serie in thumb.get("s") or []:
      color = palettes.get_color(serie.get("c", 0), palette)
      points = serie.get("p") or []
      if thumb.get("t") == "dots":
        children += [Circle(cx=str(x), cy=str(y), r="2.5", fill=color) for x, y in points]
      else:
        children.append(Polyline(
          points=" ".join(str(x) + "," + str(y) for x, y in points),
          stroke=color, strokeWidth="2.5", fill="none",
          strokeLinejoin="round", strokeLinecap="round",
        ))

  if not children:
    return _pictogram(view.get("kind"))
  viewbox = "-3 -3 " + str(views.THUMB_WIDTH + 6) + " " + str(views.THUMB_HEIGHT + 6)
  return Svg(children, viewBox=viewbox, className="xp-view-thumb", preserveAspectRatio="none")


def _view_card(view):
  name = view.get("name", "?")
  created = str(view.get("created", ""))[:10]
  meta = " · ".join(part for part in [views.kind_label(view.get("kind")), ", ".join(view.get("sources") or []), created] if part)
  return html.Button(
    [
      html.Div(_view_thumbnail(view), className="xp-view-thumb-box"),
      html.Div(
        [
          html.Div(name, className="xp-view-card-name"),
          html.Div(meta, className="xp-view-card-meta", title=meta),
        ],
        className="xp-view-card-text",
      ),
    ],
    id={"type": "xp-view-open", "name": name},
    n_clicks=0,
    type="button",
    className="xp-view-card",
    title="Restore this view",
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
      home_shared.home_card_grid(_CARDS, _card_visual),
      html.Div(id="xp-home-sources", className="xp-home-sources"),
      html.Div(id="xp-home-views", className="xp-home-views"),
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
    return html.Div(
      [
        html.Div("No result file found", className="xp-source-name"),
        html.Div('Looked for "results_*.yml" files in "' + str(STORE.result_path) + '". Run a synthesis or a workflow first — results appear here as soon as they are written.', className="xp-source-detail"),
      ],
      className="xp-source-card",
    )

  cards = []
  for source in sources:
    details = str(source.record_count) + " records · " + source.schema
    if source.error:
      details = "⚠ " + str(source.error)
    cards.append(
      html.Div(
        [
          html.Div(source.name, className="xp-source-name"),
          html.Div(details, className="xp-source-detail"),
        ],
        className="xp-source-card" + (" xp-source-error" if source.error else ""),
      )
    )
  return cards


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
    html.H2("Saved views", className="xp-home-section-title", style={"marginTop": "3em"}),
    html.Div([_view_card(view) for view in saved], className="card-matrix configs"),
  ]


@dash.callback(
  Output("xp-control-state", "data", allow_duplicate=True),
  Output("xp-filter-state", "data", allow_duplicate=True),
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
  return payload["controls"], payload["filter_state"], ui_state, "/explorer/" + payload["kind"]

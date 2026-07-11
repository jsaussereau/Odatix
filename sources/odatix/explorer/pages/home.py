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
from dash import dcc, html, Input, Output
from dash_svg import Svg, Polyline, Rect, Circle, Polygon, Line

from odatix.components import home_shared
from odatix.explorer.core.store import STORE

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


def layout(**kwargs):
  return html.Div(
    [
      dcc.Interval(id="xp-home-poll", interval=3000),
      home_shared.home_header("Odatix Explorer", "Visualize, compare and explore your results."),
      home_shared.home_card_grid(_CARDS, _card_visual),
      html.Div(id="xp-home-sources", className="xp-home-sources"),
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

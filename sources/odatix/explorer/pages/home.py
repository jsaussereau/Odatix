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
from dash_svg import Svg, Polyline, Rect, Circle, Polygon, Line, Path, Ellipse, Path

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
  if kind == "analysis":
    # Checklist with status ticks / cross: pass, warning, fail rows.
    return _svg([
        Path(d="M13 8 h14 l8 8 v24 a2 2 0 0 1-2 2 H13 a2 2 0 0 1-2-2 V10 a2 2 0 0 1 2-2 z", stroke=_FILL, strokeWidth="2", strokeOpacity="0.5", strokeLinejoin="round"),
        Line(x1="16", y1="18", x2="24", y2="18", stroke=_FILL, strokeWidth="2", strokeOpacity="0.4", strokeLinecap="round"),
        Line(x1="16", y1="23", x2="28", y2="23", stroke=_FILL, strokeWidth="2", strokeOpacity="0.4", strokeLinecap="round"),
        Circle(cx="24", cy="30", r="5", stroke=_STROKE, strokeWidth="2.5"),
        Line(x1="27.8", y1="33.8", x2="32", y2="38", stroke=_STROKE, strokeWidth="2.5", strokeLinecap="round"),
    ])
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
  if kind == "table":
    return _svg([
      Rect(x="6", y="8", width="36", height="32", rx="2.5", stroke=_FILL, strokeWidth="2", strokeOpacity="0.5", fill="none"),
      Line(x1="6", y1="18", x2="42", y2="18", stroke=_STROKE, strokeWidth="2.5"),
      Line(x1="18", y1="8", x2="18", y2="40", stroke=_FILL, strokeWidth="1.5", strokeOpacity="0.4"),
      Line(x1="30", y1="8", x2="30", y2="40", stroke=_FILL, strokeWidth="1.5", strokeOpacity="0.4"),
      Line(x1="6", y1="29", x2="42", y2="29", stroke=_FILL, strokeWidth="1.5", strokeOpacity="0.4"),
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
  {"name": "Table", "link": "/explorer/table", "kind": "table", "description": "Sortable, filterable data table"},
  {"name": "RTL Analysis", "link": "/explorer/analysis", "kind": "analysis", "description": "RTL analysis warnings and errors dashboard"},
]


def _card_visual(card):
  return _pictogram(card.get("kind"))


_HEADER_TEXT = "var(--theme-contrast-text-color, #ffffff)"
# Deterministic pill widths (fraction of a cell) so the sketch looks like real,
# varied data instead of a uniform grid.
_PILL_FRACTIONS = [0.72, 0.5, 0.62, 0.84, 0.46, 0.68, 0.56, 0.78]


def _table_thumbnail(cols, rows):
  """A neat little data-table sketch (rounded card, header, zebra rows, cells)."""
  cols = min(cols, 6)
  rows = min(rows, 5)

  width, height = 100.0, 72.0
  margin = 7.0
  radius = 6.0
  header_h = 14.0
  inner_w = width - 2 * margin
  inner_h = height - 2 * margin
  data_top = margin + header_h
  data_h = inner_h - header_h
  row_h = data_h / rows
  col_w = inner_w / cols

  def pill(x, y, w, h, fill, opacity="1"):
    return Rect(x=str(round(x, 1)), y=str(round(y, 1)), width=str(round(w, 1)), height=str(round(h, 1)),
                rx=str(round(h / 2, 1)), fill=fill, opacity=opacity)

  children = [
    # Card background
    Rect(x=str(margin), y=str(margin), width=str(inner_w), height=str(inner_h), rx=str(radius),
         fill="var(--theme-element-background-color)", stroke=_FILL, strokeWidth="1", strokeOpacity="0.18"),
  ]

  # Zebra striping on odd data rows
  for row in range(rows):
    if row % 2 == 1:
      children.append(Rect(x=str(margin + 0.5), y=str(round(data_top + row * row_h, 1)),
                           width=str(inner_w - 1), height=str(round(row_h, 1)), fill=_FILL, opacity="0.05"))

  # Header band with only the top corners rounded
  x0, y0, x1 = margin, margin, margin + inner_w
  header = ("M{} {} L{} {} Q{} {} {} {} L{} {} L{} {} L{} {} Q{} {} {} {} Z").format(
    round(x0 + radius, 1), y0, round(x1 - radius, 1), y0, x1, y0, x1, round(y0 + radius, 1),
    x1, round(y0 + header_h, 1), x0, round(y0 + header_h, 1), x0, round(y0 + radius, 1), x0, y0, round(x0 + radius, 1), y0)
  children.append(Path(d=header, fill=_STROKE, opacity="0.35"))

  # Column separators (data area only)
  for col in range(1, cols):
    x = round(margin + col * col_w, 1)
    children.append(Line(x1=str(x), y1=str(round(data_top, 1)), x2=str(x), y2=str(round(margin + inner_h, 1)),
                         stroke=_FILL, strokeWidth="1", opacity="0.12"))
  # Row separators
  for row in range(1, rows):
    y = round(data_top + row * row_h, 1)
    children.append(Line(x1=str(margin), y1=str(y), x2=str(margin + inner_w), y2=str(y),
                         stroke=_FILL, strokeWidth="1", opacity="0.12"))

  # Header label pills + data cell pills
  header_ph = 4.0
  for col in range(cols):
    cell_x = margin + col * col_w
    pad = col_w * 0.16
    max_w = col_w - 2 * pad
    children.append(pill(cell_x + pad, margin + (header_h - header_ph) / 2, max_w * 0.6, header_ph, _HEADER_TEXT, "0.9"))
    for row in range(rows):
      frac = 0.82 if col == 0 else _PILL_FRACTIONS[(row * cols + col) % len(_PILL_FRACTIONS)]
      cell_ph = min(4.2, row_h * 0.36)
      cell_y = data_top + row * row_h + (row_h - cell_ph) / 2
      children.append(pill(cell_x + pad, cell_y, max_w * frac, cell_ph, _FILL, "0.55" if col == 0 else "0.32"))

  return Svg(children, viewBox="0 0 100 72", className="xp-view-thumb", preserveAspectRatio="xMidYMid meet")


def _view_thumbnail(view):
  """Tiny data sketch saved inside the view file, or the kind pictogram."""
  thumb = view.get("thumb")
  palette = view.get("palette")
  if not isinstance(thumb, dict):
    return _pictogram(view.get("kind"))

  children = []
  if thumb.get("t") == "table":
    return _table_thumbnail(max(1, int(thumb.get("c", 3))), max(1, int(thumb.get("r", 3))))

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
          stroke=color, strokeWidth="1.5", fill="none",
          strokeLinejoin="round", strokeLinecap="round",
          vectorEffect="non-scaling-stroke",
        ))

  if not children:
    return _pictogram(view.get("kind"))
  viewbox = "-3 -3 " + str(views.THUMB_WIDTH + 6) + " " + str(views.THUMB_HEIGHT + 6)
  return Svg(children, viewBox=viewbox, className="xp-view-thumb", preserveAspectRatio="none")


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
      html.Div(_view_thumbnail(view), className="xp-view-thumb-box"),
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


def _section_header(title, count=None):
  """A left-aligned section header with an optional count pill."""
  children = [html.H2(title, className="xp-section-heading")]
  if count is not None:
    children.append(html.Span(str(count), className="xp-section-count"))
  return html.Div(children, className="xp-section-head")


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
      home_shared.home_card_grid(_CARDS, _card_visual),
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
    return [_section_header("Data sources"), _empty_sources()]

  return [
    _section_header("Data sources", len(sources)),
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
    _section_header("Saved views", len(saved)),
    html.Div([_view_card(view) for view in saved], className="xp-view-cards"),
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

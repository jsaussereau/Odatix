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
Card visuals shared by the pages showing view cards: the chart-kind
pictograms, the data sketches embedded in view files ("thumb"), and the
section headers around them.

Lives here rather than in a page module because both the landing page (saved
views) and the insights gallery (generated views) draw the same cards.
"""

from dash import html
from dash_svg import Svg, Polyline, Rect, Circle, Polygon, Line, Path, Ellipse

import odatix.explorer.core.views as views
import odatix.explorer.charts.palettes as palettes

_STROKE = "var(--theme-primary-color, #228BE6)"
_FILL = "var(--theme-text-color, #24292e)"


def _svg(children):
  return Svg(children, viewBox="0 0 48 48", width="48", height="48", fill="none", className="xp-card-pictogram")


def pictogram(kind):
  if kind == "insights":
    # A chart under a spark: the app pointing at something worth looking at.
    return _svg([
      Polyline(points="8,36 18,26 26,31 40,16", stroke=_STROKE, strokeWidth="2.5", fill="none",
               strokeLinejoin="round", strokeLinecap="round"),
      Path(d="M34 6 l1.9 4.6 L40.5 12.5 l-4.6 1.9 L34 19 l-1.9-4.6 L27.5 12.5 l4.6-1.9 z",
           fill=_STROKE, opacity="0.85"),
      Circle(cx="18", cy="26", r="2.6", fill=_FILL, opacity="0.45"),
      Circle(cx="26", cy="31", r="2.6", fill=_FILL, opacity="0.45"),
    ])
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
  if kind == "dse":
    return _svg([
      Circle(cx="14.374229", cy="11.243209", r="2.5", fill=_FILL, opacity="0.3"),
      Circle(cx="29.933266", cy="21.765116", r="2.5", fill=_FILL, opacity="0.3"),
      Circle(cx="39.465553", cy="27.08618", r="2.5", fill=_FILL, opacity="0.3"),
      Circle(cx="19.74486", cy="24.320129", r="2.5", fill=_FILL, opacity="0.3"),
      Path(
          d="M 4.1817167,9.2258967 C 4.1735767,17.225892 9.0917071,27.64385 19.36212,32.297218 c 6.402955,2.901082 19.0848,5.089128 25.750024,5.256957",
          stroke=_STROKE,
          strokeWidth="2.5",
          fill="none",
          strokeLinecap="round",
      ),
      Circle(cx="4.0877485", cy="9.763505", r="3", fill=_STROKE),
      Circle(cx="12.451153", cy="27.683771", r="3", fill=_STROKE),
      Circle(cx="26.237762", cy="34.867134", r="3", fill=_STROKE),
      Circle(cx="44.339264", cy="37.767685", r="3", fill=_STROKE),
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
  if kind == "parcoords":
    return _svg([
      Line(x1="10", y1="6", x2="10", y2="42", stroke=_FILL, strokeWidth="1.5", strokeOpacity="0.4"),
      Line(x1="24", y1="6", x2="24", y2="42", stroke=_FILL, strokeWidth="1.5", strokeOpacity="0.4"),
      Line(x1="38", y1="6", x2="38", y2="42", stroke=_FILL, strokeWidth="1.5", strokeOpacity="0.4"),
      Polyline(points="10,14 24,32 38,20", stroke=_STROKE, strokeWidth="2.5", fill="none", strokeLinejoin="round", strokeLinecap="round"),
      Polyline(points="10,30 24,12 38,36", stroke=_STROKE, strokeWidth="2.5", fill="none", strokeLinejoin="round", strokeLinecap="round", opacity="0.5"),
    ])
  # overview2 prob
  return _svg([
    Rect(x="5", y="5", width="17", height="17", rx="2", stroke=_STROKE, strokeWidth="2", fill="none"),
    Rect(x="26", y="5", width="17", height="17", rx="2", stroke=_STROKE, strokeWidth="2", fill="none", opacity="0.7"),
    Rect(x="5", y="26", width="17", height="17", rx="2", stroke=_STROKE, strokeWidth="2", fill="none", opacity="0.7"),
    Rect(x="26", y="26", width="17", height="17", rx="2", stroke=_STROKE, strokeWidth="2", fill="none", opacity="0.4"),
  ])




_HEADER_TEXT = "var(--theme-contrast-text-color, #ffffff)"
# Deterministic pill widths (fraction of a cell) so the sketch looks like real,
# varied data instead of a uniform grid.
_PILL_FRACTIONS = [0.72, 0.5, 0.62, 0.84, 0.46, 0.68, 0.56, 0.78]


def table_thumbnail(cols, rows):
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


def view_thumbnail(view):
  """Tiny data sketch saved inside the view file, or the kind pictogram."""
  thumb = view.get("thumb")
  palette = view.get("palette")
  if not isinstance(thumb, dict):
    return pictogram(view.get("kind"))

  children = []
  if thumb.get("t") == "table":
    return table_thumbnail(max(1, int(thumb.get("c", 3))), max(1, int(thumb.get("r", 3))))

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
    return pictogram(view.get("kind"))
  viewbox = "-3 -3 " + str(views.THUMB_WIDTH + 6) + " " + str(views.THUMB_HEIGHT + 6)
  return Svg(children, viewBox=viewbox, className="xp-view-thumb", preserveAspectRatio="none")


def section_header(title, count=None):
  """A left-aligned section header with an optional count pill."""
  children = [html.H2(title, className="xp-section-heading")]
  if count is not None:
    children.append(html.Span(str(count), className="xp-section-count"))
  return html.Div(children, className="xp-section-head")

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
Small reusable UI widgets of Odatix Explorer.
"""

import time

from dash import dcc, html

# Unicode glyphs matching the plotly marker symbols of charts.palettes
_SYMBOL_GLYPHS = {
  "circle": "●",
  "square": "■",
  "diamond": "◆",
  "cross": "✚",
  "x": "✖",
  "triangle-up": "▲",
  "triangle-down": "▼",
  "pentagon": "⬟",
  "star": "★",
  "circle-open": "○",
  "square-open": "□",
  "diamond-open": "◇",
}


def marker_glyph(color, symbol="circle"):
  """Colored marker glyph mirroring a trace marker, for filter/legend items."""
  return html.Span(
    _SYMBOL_GLYPHS.get(symbol, "●"),
    className="xp-glyph",
    style={"color": color},
  )


def legend_item(name, color, symbol="circle"):
  return html.Div(
    [marker_glyph(color, symbol), html.Span(name, className="xp-legend-name")],
    className="xp-legend-item",
  )


def control_row(label, control, hidden=False, tooltip=None):
  """A labeled control of the sidebar."""
  return html.Div(
    [html.Label(label, className="xp-control-label"), control],
    className="xp-control-row",
    style={"display": "none"} if hidden else None,
    title=tooltip,
  )


def section(title, children, open=True, right=None):
  """Collapsible sidebar section."""
  summary_children = [html.Span(title, className="xp-section-title")]
  if right is not None:
    summary_children.append(html.Span(right, className="xp-section-right"))
  return html.Details(
    [html.Summary(summary_children, className="xp-section-summary")] + children,
    open=open,
    className="xp-section",
  )


def status_text(store):
  """One-line data status: sources, records, last load time, errors."""
  sources = store.sources()
  if not sources:
    path = store.result_path or "?"
    return "No result file found in " + str(path)
  records = sum(source.record_count for source in sources)
  parts = [str(len(sources)) + " source" + ("s" if len(sources) > 1 else ""), str(records) + " records"]
  if store.last_load_time:
    parts.append("loaded " + time.strftime("%H:%M:%S", time.localtime(store.last_load_time)))
  errors = [source.name for source in sources if source.error]
  if errors:
    parts.append("⚠ " + ", ".join(errors))
  return " · ".join(parts)

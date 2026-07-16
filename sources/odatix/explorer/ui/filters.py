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
The filter panel: one checklist per dimension discovered in the data.

Every dimension gets its own section with show/hide-all buttons and one
checkbox per value, decorated with the color/symbol glyph of that value when
the dimension drives trace colors or symbols. Component ids are pattern-based
({"type": "xp-filter", "dim": <dimension>}), so the number of callback inputs
stays fixed whatever the data — this is what makes hot reload possible.
"""

from dash import dcc, html

import odatix.explorer.charts.palettes as palettes
from odatix.explorer.charts.spec import NONE_VALUE
import odatix.explorer.ui.components as components


def filter_checklist_id(dimension):
  return {"type": "xp-filter", "dim": dimension}


def filter_all_button_id(dimension, action):
  return {"type": "xp-filter-all", "dim": dimension, "action": action}


def build_filter_panel(dimensions, global_dimensions, filter_state, color_by, symbol_by, palette, stable_index=True):
  """
  Build the filter panel sections.

  Args:
      dimensions (dict): {dimension: values} of the current selection.
      global_dimensions (dict): {dimension: values} over all data, for stable
          glyph indices.
      filter_state (dict): {dimension: {value: bool}} remembered check states.
      color_by / symbol_by (str): dimensions driving trace colors / symbols.
      palette (str): color palette name.
      stable_index (bool): index glyph colors on the global value lists.
  """
  filter_state = filter_state or {}
  sections = []
  for dimension, values in dimensions.items():
    remembered = filter_state.get(dimension, {})
    selected = [value for value in values if remembered.get(value, True)]
    reference = global_dimensions.get(dimension, values) if stable_index else values

    options = []
    for value in values:
      label_children = []
      index = reference.index(value) if value in reference else -1
      if dimension == color_by and dimension == symbol_by:
        label_children.append(components.marker_glyph(palettes.get_color(index, palette), palettes.get_marker_symbol(index)))
      elif dimension == color_by:
        label_children.append(components.marker_glyph(palettes.get_color(index, palette)))
      elif symbol_by not in (None, NONE_VALUE) and dimension == symbol_by:
        label_children.append(components.marker_glyph("var(--theme-text-color)", palettes.get_marker_symbol(index)))
      label_children.append(html.Span(str(value), className="xp-filter-value"))
      options.append({"label": html.Span(label_children, className="xp-filter-label"), "value": value})

    buttons = html.Div(
      [
        html.Button("Select all", id=filter_all_button_id(dimension, "show"), n_clicks=0, className="xp-mini-button"),
        html.Button("Clear", id=filter_all_button_id(dimension, "hide"), n_clicks=0, className="xp-mini-button"),
      ],
      className="xp-filter-buttons",
    )

    sections.append(
      components.section(
        dimension,
        [
          buttons,
          dcc.Checklist(
            id=filter_checklist_id(dimension),
            options=options,
            value=selected,
            className="xp-filter-checklist",
          ),
        ],
        open=len(values) > 1,
      )
    )

  if not sections:
    return [html.Div("No data", className="xp-filter-empty")]
  return sections

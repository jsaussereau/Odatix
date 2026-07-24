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
Filter panel callbacks: rebuild on data/style changes while preserving the
user's selections, remember check states across pages, show/hide-all.
"""

import dash
from dash import Input, Output, State, ALL, MATCH

from odatix.explorer.core.store import STORE
import odatix.explorer.core.query as query
from odatix.explorer.charts.spec import NONE_VALUE
import odatix.explorer.ui.filters as ui_filters


def build_filters_dict(values, ids):
  """Rebuild the {dimension: allowed values} dict from pattern-matched checklists."""
  filters = {}
  for value, id in zip(values or [], ids or []):
    filters[id["dim"]] = value or []
  return filters


def register_callbacks():
  @dash.callback(
    Output("xp-filter-panel", "children"),
    Input("xp-data-version", "data"),
    Input("xp-source-select", "value"),
    Input("xp-color-by", "value"),
    Input("xp-symbol-by", "value"),
    Input("xp-palette", "value"),
    Input("xp-toggles", "value"),
    Input("xp-filter-state", "data"),
  )
  def rebuild_filter_panel(_version, sources, color_by, symbol_by, palette, toggles, filter_state):
    # Cross-filter each dimension by the others so that disabling a value (e.g.
    # an architecture or a workflow) prunes the dependent values (its
    # configurations) from the panel. Driven by xp-filter-state, updated by
    # remember_filter_state, so a rebuild settles after one pass.
    dimensions = query.cascaded_dimensions(STORE, sources, filter_state)
    full_df = STORE.dataframe()
    global_dimensions, _ = query.discover(full_df, STORE) if not full_df.empty else ({}, [])
    return ui_filters.build_filter_panel(
      dimensions,
      global_dimensions,
      filter_state,
      color_by,
      symbol_by,
      palette,
      stable_index="stable_index" in (toggles or []),
    )

  @dash.callback(
    Output("xp-filter-state", "data"),
    Input({"type": "xp-filter", "dim": ALL}, "value"),
    State({"type": "xp-filter", "dim": ALL}, "id"),
    State({"type": "xp-filter", "dim": ALL}, "options"),
    State("xp-filter-state", "data"),
    prevent_initial_call=True,
  )
  def remember_filter_state(values, ids, options, state):
    """Remember which values are unchecked, per dimension, across pages and reloads."""
    state = dict(state or {})
    for value, id, opts in zip(values or [], ids or [], options or []):
      dimension = id["dim"]
      checked = set(value or [])
      remembered = dict(state.get(dimension, {}))
      for option in opts or []:
        remembered[option["value"]] = option["value"] in checked
      state[dimension] = remembered
    return state

  @dash.callback(
    Output({"type": "xp-filter", "dim": MATCH}, "value"),
    Input({"type": "xp-filter-all", "dim": MATCH, "action": ALL}, "n_clicks"),
    State({"type": "xp-filter", "dim": MATCH}, "options"),
    prevent_initial_call=True,
  )
  def show_hide_all(_clicks, options):
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict) or not any(_clicks or []):
      raise dash.exceptions.PreventUpdate
    if triggered.get("action") == "show":
      return [option["value"] for option in options or []]
    return []

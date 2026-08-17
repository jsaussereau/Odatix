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
user's selections, remember check states across pages, show/hide-all — plus
the metric rule builder ("LUT < 1000 and Fmax > 100", see core/rules.py).
"""

import dash
from dash import Input, Output, State, ALL, MATCH

from odatix.explorer.core.store import STORE
import odatix.explorer.core.query as query
import odatix.explorer.core.rules as rules
from odatix.explorer.charts.spec import NONE_VALUE
import odatix.explorer.ui.filters as ui_filters
import odatix.explorer.ui.rules as ui_rules


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

  # ---------------------------------------------------------------- rules ---

  @dash.callback(
    Output("xp-rules-panel", "children"),
    Input("xp-data-version", "data"),
    Input("xp-source-select", "value"),
    Input("xp-rule-state", "data"),
    Input({"type": "xp-filter", "dim": ALL}, "value"),
    State({"type": "xp-filter", "dim": ALL}, "id"),
  )
  def rebuild_rules_panel(_version, sources, rule_state, filter_values, filter_ids):
    """Render the rule cards from the rule state, with a live match counter."""
    filters = build_filters_dict(filter_values, filter_ids)
    df = query.select_dataframe(STORE, sources=sources, filters=filters)
    _dimensions, metrics = query.discover(df, STORE, sources)
    matched = len(rules.apply_rules(df, rule_state)) if not df.empty else 0
    return ui_rules.build_rules_section(metrics, rule_state, STORE.units(sources), matched=matched, total=len(df))

  @dash.callback(
    Output("xp-rule-state", "data"),
    Input({"type": "xp-rule-field", "id": ALL, "field": ALL}, "value"),
    Input({"type": "xp-rule-remove", "id": ALL}, "n_clicks"),
    Input({"type": "xp-rule-action", "action": ALL, "group": ALL}, "n_clicks"),
    Input({"type": "xp-rule-match", "group": ALL, "index": ALL}, "n_clicks"),
    Input({"type": "xp-rule-operand", "id": ALL}, "n_clicks"),
    State({"type": "xp-rule-field", "id": ALL, "field": ALL}, "id"),
    State("xp-rule-state", "data"),
    prevent_initial_call=True,
  )
  def edit_rules(
    field_values, _remove_clicks, _action_clicks, _match_clicks, _operand_clicks, field_ids, rule_state
  ):
    """
    Single entry point for every rule edit: field changes, add rule, add group,
    remove, clear, the and/or chips and the constant/metric switch. The panel is
    rebuilt from the resulting state, which also re-mounts the fields and fires
    this callback back with their values — returning no_update on an unchanged
    state is what settles that loop.
    """
    state = rules.normalize(rule_state)
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict):
      raise dash.exceptions.PreventUpdate

    kind = triggered.get("type")
    # Rebuilding the panel remounts the buttons, which fires this callback with
    # n_clicks back to 0: only a real click (non-zero) is an edit.
    if kind != "xp-rule-field" and not dash.callback_context.triggered[0].get("value"):
      raise dash.exceptions.PreventUpdate

    if kind == "xp-rule-action":
      action = triggered.get("action")
      group_id = triggered.get("group", rules.ROOT_ID)
      if action == "add_rule":
        rules.add_child(state, group_id, rules.new_rule(state))
      elif action == "add_group":
        rules.add_child(state, group_id, rules.new_group(state))
      elif action == "clear":
        rules.remove(state, group_id)
      else:
        raise dash.exceptions.PreventUpdate
    elif kind == "xp-rule-remove":
      rules.remove(state, triggered.get("id"))
    elif kind == "xp-rule-match":
      rules.toggle_match(state, triggered.get("group", rules.ROOT_ID))
    elif kind == "xp-rule-operand":
      rule = rules.find(state, triggered.get("id"))
      operand = rules.OPERAND_VALUE if rule and rule.get("operand") == rules.OPERAND_METRIC else rules.OPERAND_METRIC
      rules.set_field(state, triggered.get("id"), "operand", operand)
    elif kind == "xp-rule-field":
      # Apply the live field values to the rules they belong to. Fields of a
      # rule that is no longer in the state (a stale panel about to be replaced)
      # are ignored.
      for value, id in zip(field_values or [], field_ids or []):
        rules.set_field(state, id["id"], id["field"], value)
    else:
      raise dash.exceptions.PreventUpdate

    if state == rules.normalize(rule_state):
      raise dash.exceptions.PreventUpdate
    return state

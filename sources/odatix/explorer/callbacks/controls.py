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
Axis and style dropdowns: options discovered from the data, current values
repaired when they disappear from the selection.
"""

import dash
from dash import Input, Output, State

from odatix.explorer.core.store import STORE
import odatix.explorer.core.query as query
import odatix.explorer.core.schema as schema
from odatix.explorer.charts.spec import CAPABILITIES, FigureSpec, NONE_VALUE, resolve_defaults


def _options(names):
  return [{"label": schema.metric_display_name(name) if name not in (NONE_VALUE,) else name, "value": name} for name in names]


def _dimension_options(dimensions, include_none=True):
  names = ([NONE_VALUE] if include_none else []) + list(dimensions)
  return [{"label": "None" if name == NONE_VALUE else name, "value": name} for name in names]


def _merge_control_state(state, kind, x, y, z, color_by, symbol_by, legend_group_by, dissociate):
  """Store only controls supported by the current chart kind.

  The sidebar keeps all dropdowns mounted so figure callbacks have stable
  inputs. A hidden axis therefore reports ``None`` on a chart kind that does
  not use it (for example, ``z`` on a 2D scatter). That transient value must
  not overwrite the saved value used when returning to a compatible chart.
  """
  state = dict(state or {})
  axes = CAPABILITIES.get(kind, {}).get("axes", ())
  for axis, value in (("x", x), ("y", y), ("z", z)):
    if axis in axes:
      state[axis] = value
  state.update(
    color_by=color_by,
    symbol_by=symbol_by,
    legend_group_by=legend_group_by,
    dissociate=dissociate,
  )
  return state


_TAB_KEYS = ("data", "filters", "export")


def register_callbacks():
  # Sidebar tabs, entirely client-side so every control stays mounted (the figure
  # callbacks need a stable set of inputs). A click stores the active tab; the
  # active tab then toggles a class on the sidebar content, which CSS uses to show
  # the matching panel and highlight the active button.
  dash.clientside_callback(
    dash.ClientsideFunction(namespace="xp_tabs", function_name="select"),
    Output("xp-active-tab", "data"),
    [Input("xp-tab-btn-" + key, "n_clicks") for key in _TAB_KEYS],
    prevent_initial_call=True,
  )

  dash.clientside_callback(
    dash.ClientsideFunction(namespace="xp_tabs", function_name="apply"),
    Output("xp-sidebar-content", "className"),
    [Output("xp-tab-btn-" + key, "className") for key in _TAB_KEYS],
    Input("xp-active-tab", "data"),
  )

  @dash.callback(
    Output("xp-axis-x", "options"),
    Output("xp-axis-x", "value"),
    Output("xp-axis-y", "options"),
    Output("xp-axis-y", "value"),
    Output("xp-axis-z", "options"),
    Output("xp-axis-z", "value"),
    Output("xp-color-by", "options"),
    Output("xp-color-by", "value"),
    Output("xp-symbol-by", "options"),
    Output("xp-symbol-by", "value"),
    Output("xp-legend-group-by", "options"),
    Output("xp-legend-group-by", "value"),
    Output("xp-dissociate-by", "options"),
    Output("xp-dissociate-by", "value"),
    Input("xp-data-version", "data"),
    Input("xp-source-select", "value"),
    State("xp-axis-x", "value"),
    State("xp-axis-y", "value"),
    State("xp-axis-z", "value"),
    State("xp-color-by", "value"),
    State("xp-symbol-by", "value"),
    State("xp-legend-group-by", "value"),
    State("xp-dissociate-by", "value"),
    State("xp-control-state", "data"),
    State("xp-chart-kind", "data"),
  )
  def update_control_options(_version, sources, x, y, z, color_by, symbol_by, legend_group_by, dissociate, stored, kind):
    # Values chosen on any chart page are remembered in xp-control-state (session
    # storage) so they survive switching chart kinds. On a fresh page the live
    # component values are empty (Dash persistence drops them while options are
    # still unpopulated), so the store is the source of truth when present.
    stored = stored or {}
    x = stored.get("x", x)
    y = stored.get("y", y)
    z = stored.get("z", z)
    color_by = stored.get("color_by", color_by)
    symbol_by = stored.get("symbol_by", symbol_by)
    legend_group_by = stored.get("legend_group_by", legend_group_by)
    dissociate = stored.get("dissociate", dissociate)

    df = query.select_dataframe(STORE, sources=sources)
    dimensions, metrics = query.discover(df, STORE, sources)

    # Repair values that no longer exist through the generic defaults
    spec = FigureSpec(
      kind=kind if kind != "overview" else "lines",
      x=x, y=y, z=z,
      color_by=color_by, symbol_by=symbol_by, legend_group_by=legend_group_by,
      dissociate=None if dissociate in (None, NONE_VALUE) else dissociate,
    )
    resolve_defaults(spec, dimensions, metrics)

    if kind in ("scatter", "scatter3d"):
      # Scatter axes accept metrics or any dimension (meta), metrics first.
      axis_options = _options(metrics) + _dimension_options([dim for dim in dimensions if dim not in metrics], include_none=False)
      x_options = axis_options
      y_options = axis_options
      z_options = axis_options
    else:
      x_options = _dimension_options(dimensions, include_none=False) + _options([metric for metric in metrics if metric not in dimensions])
      y_options = _options(metrics)
      z_options = _options(metrics)

    dim_options = _dimension_options(dimensions)

    return (
      x_options, spec.x,
      y_options, spec.y,
      z_options, spec.z,
      dim_options, spec.color_by,
      dim_options, spec.symbol_by,
      dim_options, spec.legend_group_by,
      dim_options, spec.dissociate if spec.dissociate else NONE_VALUE,
    )

  @dash.callback(
    Output("xp-control-state", "data"),
    Input("xp-axis-x", "value"),
    Input("xp-axis-y", "value"),
    Input("xp-axis-z", "value"),
    Input("xp-color-by", "value"),
    Input("xp-symbol-by", "value"),
    Input("xp-legend-group-by", "value"),
    Input("xp-dissociate-by", "value"),
    State("xp-control-state", "data"),
    State("xp-chart-kind", "data"),
    prevent_initial_call=True,
  )
  def remember_control_state(x, y, z, color_by, symbol_by, legend_group_by, dissociate, state, kind):
    """Remember the data-dependent control values across chart pages and reloads."""
    if x is None:
      # Transient state right after a page swap: the axis dropdowns are not
      # clearable, so a genuine user edit never produces x=None — only the
      # fresh page's default does, before update_control_options restores it.
      # Ignore it so it can't race ahead and clobber the remembered values.
      raise dash.exceptions.PreventUpdate
    return _merge_control_state(
      state, kind, x, y, z,
      color_by, symbol_by, legend_group_by, dissociate,
    )

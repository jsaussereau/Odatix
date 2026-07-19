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
Figure rendering callbacks: the single generic figure callback shared by all
chart pages, the overview grid, and the CSV export of the displayed data.
"""

from dataclasses import replace

import dash
from dash import dcc, html, Input, Output, State, ALL
import plotly.graph_objects as go

import odatix.gui.content_lib as content_lib

from odatix.explorer.core.store import STORE
import odatix.explorer.core.query as query
import odatix.explorer.core.schema as schema
from odatix.explorer.charts.spec import FigureSpec, NONE_VALUE, OVERVIEW_LAYOUTS, resolve_defaults
import odatix.explorer.charts.builder as builder
import odatix.explorer.charts.app_theme_bridge as app_theme_bridge
import odatix.explorer.ui.components as components
from odatix.explorer.callbacks.filters import build_filters_dict

# Shared dependency list of the figure and overview callbacks. Order matters:
# the callback signatures follow it.
_FIGURE_DEPS = [
  Input("xp-data-version", "data"),
  Input("xp-source-select", "value"),
  Input("xp-axis-x", "value"),
  Input("xp-axis-y", "value"),
  Input("xp-axis-z", "value"),
  Input("xp-color-by", "value"),
  Input("xp-symbol-by", "value"),
  Input("xp-legend-group-by", "value"),
  Input("xp-dissociate-by", "value"),
  Input("xp-palette", "value"),
  Input("xp-plot-theme", "value"),
  Input("xp-toggles", "value"),
  Input({"type": "xp-filter", "dim": ALL}, "value"),
  State({"type": "xp-filter", "dim": ALL}, "id"),
  Input("theme-dropdown", "value"),
  Input("xp-dl-format", "value"),
  Input("xp-dl-background", "value"),
  State("xp-chart-kind", "data"),
]


def _selection(sources, filter_values, filter_ids):
  filters = build_filters_dict(filter_values, filter_ids)
  df = query.select_dataframe(STORE, sources=sources, filters=filters)
  dimensions, metrics = query.discover(df, STORE, sources)
  full_df = STORE.dataframe()
  global_dimensions, _ = query.discover(full_df, STORE) if not full_df.empty else ({}, [])
  return df, dimensions, metrics, global_dimensions


def _make_spec(kind, x, y, z, color_by, symbol_by, legend_group_by, dissociate, toggles, dimensions, metrics):
  spec = FigureSpec(
    kind=kind,
    x=x, y=y, z=z,
    color_by=color_by,
    symbol_by=symbol_by,
    legend_group_by=legend_group_by,
    dissociate=None if dissociate in (None, NONE_VALUE) else dissociate,
    stable_index="stable_index" in (toggles or []),
    toggles=tuple(toggles or []),
  )
  return resolve_defaults(spec, dimensions, metrics)


def _apply_export_background(fig, dl_background):
  if dl_background == "white":
    fig.update_layout(paper_bgcolor="white")
  elif dl_background == "transparent":
    fig.update_layout(paper_bgcolor=builder.TRANSPARENT)
  return fig


def _graph_config(sources, kind, metric, dl_format):
  filename = "Odatix-" + "-".join((sources or ["results"])[:3] + [str(kind), str(metric)])
  return {
    "toImageButtonOptions": {"format": dl_format or "svg", "filename": filename, "scale": 3},
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "displaylogo": False,
    "scrollZoom": kind not in ("scatter3d",),
  }


def register_callbacks():
  @dash.callback(
    Output("xp-graph", "figure"),
    Output("xp-graph", "config"),
    Output("xp-error", "children"),
    *_FIGURE_DEPS,
  )
  def update_figure(version, sources, x, y, z, color_by, symbol_by, legend_group_by, dissociate,
                    palette, plot_theme, toggles, filter_values, filter_ids, app_theme,
                    dl_format, dl_background, kind):
    if kind in (None, "overview"):
      raise dash.exceptions.PreventUpdate
    try:
      df, dimensions, metrics, global_dimensions = _selection(sources, filter_values, filter_ids)
      spec = _make_spec(kind, x, y, z, color_by, symbol_by, legend_group_by, dissociate, toggles, dimensions, metrics)
      chrome = app_theme_bridge.get_chrome(app_theme)
      units = STORE.units(sources)
      fig = builder.build_figure(
        df, spec, dimensions, metrics, units, chrome,
        global_dimensions=global_dimensions, palette=palette, plot_theme=plot_theme,
      )
      _apply_export_background(fig, dl_background)
      return fig, _graph_config(sources, kind, spec.y, dl_format), None
    except Exception as e:
      return dash.no_update, dash.no_update, content_lib.generate_error_div(e)

  @dash.callback(
    Output("xp-overview-area", "children"),
    Input("xp-overview-chart-type", "value"),
    Input("xp-overview-layout", "value"),
    *_FIGURE_DEPS,
  )
  def update_overview(chart_type, layout, version, sources, x, y, z, color_by, symbol_by, legend_group_by,
                      dissociate, palette, plot_theme, toggles, filter_values, filter_ids, app_theme,
                      dl_format, dl_background, kind):
    if kind != "overview":
      raise dash.exceptions.PreventUpdate
    try:
      df, dimensions, metrics, global_dimensions = _selection(sources, filter_values, filter_ids)
      spec = _make_spec(chart_type or "lines", x, y, z, color_by, symbol_by, legend_group_by, dissociate, toggles, dimensions, metrics)
      spec = replace(spec, toggles=tuple(toggle for toggle in spec.toggles if toggle != "legend"))
      chrome = app_theme_bridge.get_chrome(app_theme)
      units = STORE.units(sources)

      width, height = OVERVIEW_LAYOUTS.get(layout, OVERVIEW_LAYOUTS["default"])
      figures = builder.build_overview_figures(
        df, spec, dimensions, metrics, units, chrome,
        global_dimensions=global_dimensions, size=(width, height), palette=palette, plot_theme=plot_theme,
      )

      children = []
      if "legend" in (toggles or []):
        entries = builder.legend_entries(df, spec, dimensions, global_dimensions, palette)
        children.append(html.Div([components.legend_item(*entry) for entry in entries], className="xp-shared-legend"))

      grid = []
      for metric, fig in figures:
        _apply_export_background(fig, dl_background)
        grid.append(
          dcc.Graph(
            figure=fig,
            config=_graph_config(sources, "overview", metric, dl_format),
            className="xp-overview-graph",
            style={"width": str(width) + "px" if width else "100%", "height": str(height) + "px"},
          )
        )
      children.append(html.Div(grid, className="xp-overview-grid"))
      return children
    except Exception as e:
      return content_lib.generate_error_div(e)

  @dash.callback(
    Output("xp-download", "data"),
    Input("xp-download-tex", "n_clicks"),
    Input("xp-download-csv", "n_clicks"),
    State("xp-source-select", "value"),
    State({"type": "xp-filter", "dim": ALL}, "value"),
    State({"type": "xp-filter", "dim": ALL}, "id"),
    State("xp-chart-kind", "data"),
    State("xp-graph", "figure"),
    prevent_initial_call=True,
  )
  def download_data(tex_clicks, csv_clicks, sources, filter_values, filter_ids, kind, figure_data):
    ctx = getattr(dash, "ctx", None)
    if ctx is not None:
      trigger = ctx.triggered_id
    else:
      callback_ctx = dash.callback_context
      trigger = callback_ctx.triggered[0]["prop_id"].split(".")[0] if callback_ctx.triggered else None

    if trigger not in ("xp-download-csv", "xp-download-tex"):
      raise dash.exceptions.PreventUpdate

    if trigger == "xp-download-tex":
      if kind in (None, "overview"):
        raise dash.exceptions.PreventUpdate
      if not figure_data:
        raise dash.exceptions.PreventUpdate

      try:
        import tikzplotly
      except Exception as e:
        raise RuntimeError("tikzplotly is required for LaTeX export. Install it in the active environment.") from e

      fig = go.Figure(figure_data)
      tikz_code = tikzplotly.get_tikz_code(fig)
      filename = "Odatix-" + "-".join((sources or ["results"])[:3] + [str(kind)]) + ".tex"
      return dict(content=tikz_code, filename=filename, type="text/plain")

    if not csv_clicks:
      raise dash.exceptions.PreventUpdate

    filters = build_filters_dict(filter_values, filter_ids)
    df = query.select_dataframe(STORE, sources=sources, filters=filters)
    filename = "Odatix-" + "-".join((sources or ["results"])[:3] + [str(kind)]) + ".csv"
    return dcc.send_data_frame(df.to_csv, filename, index=False)

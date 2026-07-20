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
from dash import dcc, html, dash_table, Input, Output, State, ALL

import pandas as pd

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


def _ordered_table_columns(dimensions, metrics):
  """Column order for the table view: reserved dimensions first, then the other
  dimensions, then the metrics (mirrors the natural reading order of a result)."""
  dims = list(dimensions)
  ordered = [column for column in schema.RESERVED_DIMENSION_ORDER if column in dims]
  ordered += [column for column in dims if column not in ordered]
  ordered += [metric for metric in metrics if metric not in ordered]
  return ordered


def _table_header(column, metric_set, units):
  """Display header of a table column: metric display name plus unit when known."""
  if column in metric_set:
    name = schema.metric_display_name(column)
    unit = str((units or {}).get(column, "") or "")
    return name + " (" + unit + ")" if unit else name
  return column


def build_data_table(df, selected, dimensions, metrics, units):
  """A sortable/filterable DataTable of the current selection.

  ``selected`` is the user-picked column subset (empty/None = every column).
  Metrics are coerced to numbers so the table sorts and filters them
  numerically; everything else stays textual.
  """
  available = _ordered_table_columns(dimensions, metrics)
  if selected:
    columns_ids = [column for column in selected if column in available]
  else:
    columns_ids = available
  if df is None or df.empty or not columns_ids:
    return html.Div("No data for the current selection.", className="xp-table-empty")

  metric_set = set(metrics)
  data_df = df[columns_ids].copy()
  for column in columns_ids:
    if column in metric_set:
      data_df[column] = pd.to_numeric(data_df[column], errors="coerce")
  data_df = data_df.where(pd.notnull(data_df), None)

  columns = []
  for column in columns_ids:
    spec = {"name": _table_header(column, metric_set, units), "id": column}
    if column in metric_set:
      spec["type"] = "numeric"
    columns.append(spec)

  table = dash_table.DataTable(
    id="xp-datatable",
    columns=columns,
    data=data_df.to_dict("records"),
    sort_action="native",
    filter_action="native",
    # No pagination: render every row and let the table scroll through the whole
    # selection. virtualization keeps that cheap for large data by only mounting
    # the rows currently in view, and fixed_rows keeps the header pinned while
    # scrolling.
    page_action="none",
    virtualization=True,
    fixed_rows={"headers": True},
    style_table={"height": "100%", "overflowX": "auto", "overflowY": "auto"},
    style_header={
      "backgroundColor": "var(--theme-contrast-background-color)",
      "color": "var(--theme-contrast-text-color)",
      "fontWeight": "600",
      "border": "1px solid var(--theme-border-color)",
    },
    style_filter={
      "backgroundColor": "var(--theme-element-background-color)",
      "color": "var(--theme-text-color)",
    },
    style_cell={
      "backgroundColor": "var(--theme-background-color)",
      "color": "var(--theme-text-color)",
      "border": "1px solid var(--theme-border-color)",
      "textAlign": "left",
      "padding": "4px 10px",
      "fontFamily": "var(--theme-font-family)",
      "fontSize": "var(--theme-small-font-size)",
      # Fixed widths: virtualization remounts rows as you scroll, and without a
      # pinned width each batch would re-measure and make columns jitter.
      "minWidth": "120px",
      "width": "160px",
      "maxWidth": "320px",
      "overflow": "hidden",
      "textOverflow": "ellipsis",
    },
    style_data_conditional=[
      {"if": {"row_index": "odd"}, "backgroundColor": "var(--theme-element-background-color)"},
    ],
    css=[
      {"selector": ".dash-filter input", "rule": "color: var(--theme-text-color) !important; text-align: left !important;"},
      {"selector": ".dash-spreadsheet-menu", "rule": "color: var(--theme-text-color);"},
    ],
  )
  return html.Div(table, className="xp-datatable")


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
    Output("xp-table-columns", "options"),
    Output("xp-table-columns", "value"),
    Input("xp-data-version", "data"),
    Input("xp-source-select", "value"),
    State("xp-table-columns", "value"),
  )
  def update_table_columns(_version, sources, current):
    """Populate the column picker from the current selection, keeping any still-valid
    user choice (the dropdown persists it across visits) and dropping vanished columns."""
    df = query.select_dataframe(STORE, sources=sources)
    dimensions, metrics = query.discover(df, STORE, sources)
    available = _ordered_table_columns(dimensions, metrics)
    metric_set = set(metrics)
    units = STORE.units(sources)
    options = [{"label": _table_header(column, metric_set, units), "value": column} for column in available]
    kept = [column for column in (current or []) if column in available]
    # Pre-fill every column when nothing is selected yet (first visit, or the
    # very first callback firing before the data is loaded left an empty value),
    # so the user just removes the unwanted ones. A non-empty user choice is kept
    # (and persisted by the dropdown).
    value = kept if kept else available
    return options, value

  @dash.callback(
    Output("xp-table-area", "children"),
    Input("xp-table-columns", "value"),
    Input("xp-data-version", "data"),
    Input("xp-source-select", "value"),
    Input({"type": "xp-filter", "dim": ALL}, "value"),
    State({"type": "xp-filter", "dim": ALL}, "id"),
    Input("theme-dropdown", "value"),
    State("xp-chart-kind", "data"),
  )
  def update_table(columns, _version, sources, filter_values, filter_ids, _app_theme, kind):
    if kind != "table":
      raise dash.exceptions.PreventUpdate
    try:
      df, dimensions, metrics, _global_dimensions = _selection(sources, filter_values, filter_ids)
      return build_data_table(df, columns, dimensions, metrics, STORE.units(sources))
    except Exception as e:
      return content_lib.generate_error_div(e)

  @dash.callback(
    Output("xp-download", "data"),
    Input("xp-download-csv", "n_clicks"),
    State("xp-source-select", "value"),
    State({"type": "xp-filter", "dim": ALL}, "value"),
    State({"type": "xp-filter", "dim": ALL}, "id"),
    State("xp-chart-kind", "data"),
    prevent_initial_call=True,
  )
  def download_csv(n_clicks, sources, filter_values, filter_ids, kind):
    if not n_clicks:
      raise dash.exceptions.PreventUpdate
    filters = build_filters_dict(filter_values, filter_ids)
    df = query.select_dataframe(STORE, sources=sources, filters=filters)
    filename = "Odatix-" + "-".join((sources or ["results"])[:3] + [str(kind)]) + ".csv"
    return dcc.send_data_frame(df.to_csv, filename, index=False)

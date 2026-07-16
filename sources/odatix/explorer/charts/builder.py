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
The generic chart engine behind every Odatix Explorer page.

build_figure() turns a filtered selection (tidy DataFrame) and a FigureSpec
into a Plotly figure. Rows are grouped into traces by the dimensions that
vary in the selection; color, symbol, legend group and point labels are all
driven by arbitrary dimensions, so any data can be plotted against anything.
"""

import pandas as pd
import plotly.graph_objects as go

import odatix.explorer.core.schema as schema
import odatix.explorer.charts.palettes as palettes
import odatix.explorer.charts.plot_themes as plot_themes
from odatix.explorer.charts.spec import NONE_VALUE

TRANSPARENT = "rgba(0,0,0,0)"

# Reserved dimensions used for automatic trace grouping. Configuration and
# free dimensions (parameter domains) are excluded on purpose: they identify
# points, not traces — unless explicitly requested through color/symbol/
# dissociate.
AUTO_GROUP_DIMENSIONS = [schema.COL_SOURCE, schema.COL_TYPE, schema.COL_TARGET, schema.COL_ARCHITECTURE, schema.COL_WORKFLOW, schema.COL_FREQUENCY]


######################################
# Trace grouping
######################################


def _dimension_series(df, dimension):
  return df[dimension].fillna(schema.MISSING_VALUE).astype(str)


def identity_dimensions(spec, dimensions):
  """Dimensions splitting the selection into traces."""
  identity = [dim for dim in AUTO_GROUP_DIMENSIONS if dim in dimensions and len(dimensions[dim]) > 1]
  for extra in (spec.color_by, spec.symbol_by, spec.legend_group_by, spec.dissociate):
    if extra and extra != NONE_VALUE and extra in dimensions and extra not in identity:
      identity.append(extra)
  # The x axis and point-label dimensions vary inside a trace
  excluded = {spec.x}
  if spec.kind in ("scatter", "scatter3d"):
    excluded.add(spec.label_by)
  return [dim for dim in identity if dim not in excluded]


def group_traces(df, spec, dimensions):
  """
  Split the selection into traces.

  Returns:
      list of (info dict {dimension: value}, sub DataFrame), sorted.
  """
  identity = identity_dimensions(spec, dimensions)
  if not identity:
    return [({}, df)]

  keys = df[identity].fillna(schema.MISSING_VALUE).astype(str)
  groups = []
  for key, sub_df in df.groupby([keys[dim] for dim in identity], sort=False):
    if not isinstance(key, tuple):
      key = (key,)
    groups.append((dict(zip(identity, key)), sub_df))

  groups.sort(key=lambda group: tuple(schema.sort_key(group[0][dim]) for dim in identity))
  return groups


def trace_name(info, dimensions, spec, units):
  """Human-readable trace name from the dimension values identifying it."""
  parts = []
  for dim, value in info.items():
    if dim in dimensions and len(dimensions[dim]) <= 1:
      continue  # constant over the selection: no need to repeat it
    if str(value) == schema.MISSING_VALUE:
      continue  # dimension absent from this trace's records
    if dim == spec.dissociate:
      parts.append("[" + str(dim) + ": " + str(value) + "]")
    elif dim == schema.COL_FREQUENCY:
      if value == schema.FMAX_FREQUENCY_VALUE:
        continue  # the result type ("Fmax") already says it
      unit = units.get(schema.COL_FREQUENCY, "MHz") if units else "MHz"
      parts.append("@ " + str(value) + " " + unit)
    else:
      parts.append(str(value))
  return " ".join(parts) if parts else "all"


######################################
# Style indices
######################################


def _value_index(value, values):
  try:
    return values.index(str(value))
  except (ValueError, AttributeError):
    return -1


def style_indices(info, spec, dimensions, global_dimensions):
  """(color index, symbol index) of a trace, from its dimension values."""
  reference = global_dimensions if spec.stable_index else dimensions

  color_index = 0
  if spec.color_by and spec.color_by != NONE_VALUE:
    if spec.color_by in info:
      color_index = _value_index(info[spec.color_by], reference.get(spec.color_by, []))
    else:
      color_index = -1 if spec.color_by not in dimensions else 0

  symbol_index = 0
  if spec.symbol_by and spec.symbol_by != NONE_VALUE and spec.symbol_by in info:
    symbol_index = max(_value_index(info[spec.symbol_by], reference.get(spec.symbol_by, [])), 0)

  return color_index, symbol_index


######################################
# Hover
######################################


def _hover_header(info):
  lines = ["<b>" + str(dim) + ":</b> " + str(value) for dim, value in info.items()]
  return "<br>".join(lines)


def _metric_hover_line(metric, axis, units):
  unit = schema.unit_to_html(units.get(metric, "")) if units else ""
  return "<b>" + schema.metric_display_name(metric) + ":</b> %{" + axis + "}" + ((" " + unit) if unit else "")


######################################
# Figure construction
######################################


def build_figure(df, spec, dimensions, metrics, units, chrome, global_dimensions=None, height=None, palette=palettes.DEFAULT_PALETTE, plot_theme=plot_themes.AUTO):
  """
  Build a Plotly figure from a selection.

  Args:
      df: filtered selection (tidy DataFrame).
      spec (FigureSpec): what to plot (fields already resolved).
      dimensions (dict): {dimension: values} discovered on the selection.
      metrics (list): metrics discovered on the selection.
      units (dict): metric units.
      chrome (dict): app-theme plot chrome (see app_theme_bridge).
      global_dimensions (dict): {dimension: values} over the full store, used
          for stable color/symbol indices.
      height (int | None): figure height (px).
      palette (str): trace color palette name.
      plot_theme (str): plot theme name ("auto" follows the app theme).

  Returns:
      go.Figure
  """
  if global_dimensions is None:
    global_dimensions = dimensions

  fig = go.Figure()

  if df.empty or spec.y is None:
    _apply_layout(fig, spec, [], units, chrome, height, plot_theme)
    return fig

  x_is_metric = spec.kind in ("scatter", "scatter3d") or (spec.x in metrics and spec.x not in dimensions)
  categories = [] if x_is_metric else _x_categories(df, spec)

  for info, sub_df in group_traces(df, spec, dimensions):
    color_index, symbol_index = style_indices(info, spec, dimensions, global_dimensions)
    color = palettes.get_color(color_index, palette)
    name = trace_name(info, dimensions, spec, units)
    legend_group = None
    if spec.has("legend_groups") and spec.legend_group_by and spec.legend_group_by != NONE_VALUE:
      legend_group = info.get(spec.legend_group_by)

    common = dict(
      name=name,
      legendgroup=legend_group,
      legendgrouptitle_text=legend_group,
    )

    hover_header = _hover_header(info)

    if spec.kind in ("scatter", "scatter3d"):
      fig.add_trace(_scatter_trace(sub_df, spec, units, color, symbol_index, hover_header, common))
    elif spec.kind == "columns":
      fig.add_trace(_bar_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common))
    elif spec.kind == "radar":
      fig.add_trace(_radar_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common))
    else:
      fig.add_trace(_line_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common, x_is_metric))

  _apply_layout(fig, spec, categories, units, chrome, height, plot_theme)
  return fig


def _x_categories(df, spec):
  values = _dimension_series(df, spec.x).unique() if spec.x in df.columns else []
  return schema.sort_values(values)


def _x_label(category, spec):
  if spec.dissociate and spec.x == schema.COL_CONFIGURATION:
    return schema.clean_configuration_name(category, spec.dissociate)
  return str(category)


def _categorical_xy(sub_df, spec, categories):
  """Align a trace on the shared x categories (None where a category has no value)."""
  series = pd.to_numeric(sub_df[spec.y], errors="coerce") if spec.y in sub_df.columns else pd.Series(dtype=float)
  by_category = {}
  if spec.x in sub_df.columns:
    x_values = _dimension_series(sub_df, spec.x)
    for x_value, y_value in zip(x_values, series):
      if pd.notna(y_value):
        by_category[x_value] = y_value
  x = [_x_label(category, spec) for category in categories]
  y = [by_category.get(category) for category in categories]
  return x, y


def _line_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common, x_is_metric):
  if x_is_metric:
    points = sub_df[[spec.x, spec.y]].apply(pd.to_numeric, errors="coerce").dropna().sort_values(spec.x)
    x, y = points[spec.x].tolist(), points[spec.y].tolist()
    hover_x = _metric_hover_line(spec.x, "x", units)
  else:
    x, y = _categorical_xy(sub_df, spec, categories)
    hover_x = "<b>" + str(spec.x) + ":</b> %{x}"
  return go.Scatter(
    x=x,
    y=y,
    mode="lines+markers" if spec.has("lines") else "markers",
    line=dict(dash="dot", color=color),
    marker=dict(symbol=palettes.get_marker_symbol(symbol_index), color=color),
    connectgaps=spec.has("connect_gaps"),
    hovertemplate=hover_header + ("<br>" if hover_header else "") + hover_x + "<br>" + _metric_hover_line(spec.y, "y", units) + "<extra></extra>",
    **common,
  )


def _bar_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common):
  x, y = _categorical_xy(sub_df, spec, categories)
  return go.Bar(
    x=x,
    y=y,
    marker=dict(color=color, pattern_shape=palettes.get_bar_pattern(symbol_index)),
    hovertemplate=hover_header + ("<br>" if hover_header else "") + "<b>" + str(spec.x) + ":</b> %{x}<br>" + _metric_hover_line(spec.y, "y", units) + "<extra></extra>",
    **common,
  )


def _radar_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common):
  theta, r = _categorical_xy(sub_df, spec, categories)
  if spec.has("close_line") and len(theta) > 0:
    theta = theta + [theta[0]]
    r = r + [r[0]]
  return go.Scatterpolar(
    theta=theta,
    r=r,
    mode="lines+markers",
    line=dict(dash="dot", color=color),
    marker=dict(symbol=palettes.get_marker_symbol(symbol_index), color=color),
    connectgaps=spec.has("connect_gaps"),
    hovertemplate=hover_header + ("<br>" if hover_header else "") + "<b>" + str(spec.x) + ":</b> %{theta}<br>" + _metric_hover_line(spec.y, "r", units) + "<extra></extra>",
    **common,
  )


def _scatter_trace(sub_df, spec, units, color, symbol_index, hover_header, common):
  axes = [spec.x, spec.y] + ([spec.z] if spec.kind == "scatter3d" else [])
  points = sub_df[axes].apply(pd.to_numeric, errors="coerce")
  keep = points.notna().all(axis=1)
  points = points[keep]

  labels = None
  if spec.label_by and spec.label_by in sub_df.columns:
    labels = _dimension_series(sub_df[keep], spec.label_by).tolist()
    if spec.dissociate and spec.label_by == schema.COL_CONFIGURATION:
      labels = [schema.clean_configuration_name(label, spec.dissociate) for label in labels]

  mode = "markers"
  if spec.has("scatter_lines"):
    mode += "+lines"
    points = points.sort_values(spec.x)
  if spec.has("labels") and labels is not None:
    mode += "+text"

  hover_lines = [_metric_hover_line(axis_metric, axis_name, units) for axis_metric, axis_name in zip(axes, ["x", "y", "z"])]
  if labels is not None:
    hover_lines.insert(0, "<b>" + str(spec.label_by) + ":</b> %{text}")
  hovertemplate = hover_header + ("<br>" if hover_header else "") + "<br>".join(hover_lines) + "<extra></extra>"

  if spec.kind == "scatter3d":
    return go.Scatter3d(
      x=points[spec.x],
      y=points[spec.y],
      z=points[spec.z],
      mode=mode,
      text=labels,
      line=dict(dash="dot", color=color),
      marker=dict(symbol=palettes.get_marker_symbol_3d(symbol_index), color=color, size=4),
      hovertemplate=hovertemplate,
      **common,
    )
  return go.Scatter(
    x=points[spec.x],
    y=points[spec.y],
    mode=mode,
    text=labels,
    textposition="top center",
    line=dict(dash="dot", color=color),
    marker=dict(symbol=palettes.get_marker_symbol(symbol_index), color=color),
    connectgaps=True,
    hovertemplate=hovertemplate,
    **common,
  )


######################################
# Layout
######################################


def _figure_title(spec, units):
  if spec.kind in ("scatter", "scatter3d"):
    title = schema.metric_display_name(spec.y) + " vs " + schema.metric_display_name(spec.x)
    if spec.kind == "scatter3d" and spec.z:
      title += " vs " + schema.metric_display_name(spec.z)
    return title
  return schema.axis_title(spec.y, units)


def _apply_axis_scale(axis, log_on, zero_on):
  """Apply a log or start-at-zero scale to a numeric axis dict (log wins).

  A log axis cannot include zero, so "start at zero" is ignored when log is on.
  """
  if log_on:
    axis["type"] = "log"
  elif zero_on:
    axis["rangemode"] = "tozero"
  return axis


def _apply_layout(fig, spec, categories, units, chrome, height, plot_theme):
  template = plot_themes.get_template(plot_theme)
  auto = template is None

  layout = dict(
    template=template if not auto else ("plotly_dark" if chrome.get("dark") else "plotly"),
    showlegend=spec.has("legend"),
    uirevision=":".join(str(part) for part in (spec.kind, spec.x, spec.y, spec.z)),
    margin=dict(l=60, r=30, t=60 if spec.has("title") else 30, b=50),
    modebar=dict(bgcolor=TRANSPARENT),
  )
  if height is not None:
    layout["height"] = height
  if spec.has("title"):
    layout["title"] = dict(text=_figure_title(spec, units), x=0.5)

  if auto:
    layout.update(
      paper_bgcolor=TRANSPARENT,
      plot_bgcolor=TRANSPARENT,
      font_color=chrome.get("text_color"),
      modebar=dict(bgcolor=TRANSPARENT, color=chrome.get("text_color"), activecolor=chrome.get("text_color")),
    )

  grid = dict(gridcolor=chrome.get("grid_color"), zerolinecolor=chrome.get("zeroline_color")) if auto else {}

  if spec.kind == "radar":
    polar_grid = dict(gridcolor=chrome.get("grid_color")) if auto else {}
    radialaxis = dict(**polar_grid)
    if spec.has("log_y"):
      radialaxis["type"] = "log"
    layout["polar"] = dict(
      radialaxis=radialaxis,
      angularaxis=dict(**polar_grid),
    )
    if auto:
      layout["polar"]["bgcolor"] = TRANSPARENT
  elif spec.kind == "scatter3d":
    axis_defaults = dict(**grid)
    if auto:
      axis_defaults["backgroundcolor"] = TRANSPARENT
    zero = spec.has("zero_axis")
    layout["scene"] = dict(
      xaxis=_apply_axis_scale(dict(title=schema.axis_title(spec.x, units), **axis_defaults), spec.has("log_x"), zero),
      yaxis=_apply_axis_scale(dict(title=schema.axis_title(spec.y, units), **axis_defaults), spec.has("log_y"), zero),
      zaxis=_apply_axis_scale(dict(title=schema.axis_title(spec.z, units), **axis_defaults), spec.has("log_z"), zero),
      camera=dict(eye=dict(x=1.6, y=1.6, z=0.6)),
    )
    layout["legend"] = dict(itemsizing="constant")
  else:
    # Categorical x: title is the dimension name; numeric x: metric title with unit
    xaxis = dict(title=str(spec.x) if categories else schema.axis_title(spec.x, units), **grid)
    if categories:
      xaxis["categoryorder"] = "array"
      xaxis["categoryarray"] = [_x_label(category, spec) for category in categories]
    else:
      # Numeric x axis only: log scale / start-at-zero (ignored for categorical x).
      zero_x = spec.has("zero_x") or (spec.kind != "scatter" and spec.has("zero_y"))
      _apply_axis_scale(xaxis, spec.has("log_x"), zero_x)
    yaxis = _apply_axis_scale(dict(title=schema.axis_title(spec.y, units), **grid), spec.has("log_y"), spec.has("zero_y"))
    layout["xaxis"] = xaxis
    layout["yaxis"] = yaxis

  fig.update_layout(**layout)


######################################
# Overview & legend helpers
######################################


def build_overview_figures(df, spec, dimensions, metrics, units, chrome, global_dimensions=None, size=(475, 475), palette=palettes.DEFAULT_PALETTE, plot_theme=plot_themes.AUTO):
  """One figure per metric of the selection (same spec otherwise)."""
  from dataclasses import replace

  figures = []
  for metric in metrics:
    metric_spec = replace(spec, y=metric)
    fig = build_figure(
      df, metric_spec, dimensions, metrics, units, chrome,
      global_dimensions=global_dimensions, height=size[1], palette=palette, plot_theme=plot_theme,
    )
    figures.append((metric, fig))
  return figures


def legend_entries(df, spec, dimensions, global_dimensions=None, palette=palettes.DEFAULT_PALETTE):
  """
  Legend entries of a selection: list of (name, color, symbol name), mirroring
  the trace naming/coloring of build_figure. Used for the shared HTML legend
  of the overview page.
  """
  if global_dimensions is None:
    global_dimensions = dimensions
  entries = []
  for info, _ in group_traces(df, spec, dimensions):
    color_index, symbol_index = style_indices(info, spec, dimensions, global_dimensions)
    entries.append((trace_name(info, dimensions, spec, {}), palettes.get_color(color_index, palette), palettes.get_marker_symbol(symbol_index)))
  return entries

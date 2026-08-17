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
from odatix.explorer.charts.spec import NONE_VALUE, x_is_symbolic

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


def _auto_line_color_dimension(spec, dimensions):
  """
  The configuration, when a line chart would otherwise draw every configuration
  as a single trace.

  On a line chart the x axis is swept (a metric or a parameter), so several
  configurations sharing the same x values collapse into one zigzagging trace.
  Splitting and coloring them by configuration is what was meant. It is not done
  for the other chart kinds: on a scatter, the configuration is the point
  identity, and grouping by it would make one trace per point.

  Returns None as soon as the user picked any explicit grouping: that choice is
  theirs, and a second grouping behind their back is not.
  """
  if spec.kind != "lines":
    return None
  if spec.color_by or spec.symbol_by or spec.dissociate:
    return None
  if spec.legend_group_by and spec.legend_group_by != NONE_VALUE:
    return None
  dimension = schema.COL_CONFIGURATION
  if dimension == spec.x or len(dimensions.get(dimension, [])) <= 1:
    return None
  return dimension


def identity_dimensions(spec, dimensions):
  """Dimensions splitting the selection into traces."""
  identity = [dim for dim in AUTO_GROUP_DIMENSIONS if dim in dimensions and len(dimensions[dim]) > 1]
  auto_line = _auto_line_color_dimension(spec, dimensions)
  if auto_line and auto_line not in identity:
    identity.append(auto_line)
  extras = list(spec.color_by or ()) + list(spec.symbol_by or ()) + list(spec.dissociate or ()) + list(spec.sort_by or ()) + [spec.legend_group_by]
  for extra in extras:
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

  sort_by = [dim for dim in (spec.sort_by or ()) if dim in identity]
  sort_order = sort_by + [dim for dim in identity if dim not in sort_by]

  groups.sort(key=lambda group: tuple(schema.sort_key(group[0][dim]) for dim in sort_order))
  return groups


def trace_name(info, dimensions, spec, units):
  """Human-readable trace name from the dimension values identifying it."""
  parts = []
  for dim, value in info.items():
    if dim in dimensions and len(dimensions[dim]) <= 1:
      continue  # constant over the selection: no need to repeat it
    if str(value) == schema.MISSING_VALUE:
      continue  # dimension absent from this trace's records
    if dim == spec.legend_group_by:
      continue  # already shown as the legend group title
    if dim in (spec.dissociate or ()):
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


def _combination_index(info, by_dimensions, reference, dimensions):
  """Index of a trace among all value combinations of ``by_dimensions``.

  Mixed-radix number over the dimensions' value lists, so every combination
  gets its own index (and its own color / symbol). The first dimension is the
  most significant one: neighboring values of the last dimension end up on
  neighboring palette entries.

  Returns -1 when a dimension is absent from the selection altogether (the
  caller's palette then falls back), as the single-dimension code did.
  """
  index = 0
  for dimension in by_dimensions:
    values = reference.get(dimension, [])
    if dimension in info:
      position = max(_value_index(info[dimension], values), 0)
    elif dimension not in dimensions:
      return -1
    else:
      position = 0
    index = index * max(len(values), 1) + position
  return index


def style_indices(info, spec, dimensions, global_dimensions, color_by=None):
  """(color index, symbol index) of a trace, from its dimension values.

  ``color_by`` overrides spec.color_by, for the dimension a line chart colors by
  on its own when nothing explicit was picked (see _auto_line_color_dimension).
  """
  reference = global_dimensions if spec.stable_index else dimensions

  if color_by:
    color_by = (color_by,) if isinstance(color_by, str) else tuple(color_by)
  else:
    color_by = spec.color_by or ()

  color_index = _combination_index(info, color_by, reference, dimensions) if color_by else 0
  symbol_index = max(_combination_index(info, spec.symbol_by or (), reference, dimensions), 0)

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

  if spec.kind == "parcoords":
    if not df.empty and spec.y_metrics:
      fig.add_trace(_parcoords_trace(df, spec, units, palette))
    _apply_layout(fig, spec, [], units, chrome, height, plot_theme)
    return fig

  if df.empty or spec.y is None:
    _apply_layout(fig, spec, [], units, chrome, height, plot_theme)
    return fig

  x_is_metric = not x_is_symbolic(spec.kind, spec.x, dimensions, metrics)
  categories = [] if x_is_metric else _x_categories(df, spec)

  auto_color_by = _auto_line_color_dimension(spec, dimensions)

  for info, sub_df in group_traces(df, spec, dimensions):
    color_index, symbol_index = style_indices(info, spec, dimensions, global_dimensions, color_by=auto_color_by)
    color = palettes.get_color(color_index, palette)
    name = trace_name(info, dimensions, spec, units)
    legend_group = None
    if spec.has("legend_groups") and spec.legend_group_by and spec.legend_group_by != NONE_VALUE:
      group_value = info.get(spec.legend_group_by)
      if group_value is not None:
        legend_group = str(spec.legend_group_by) + ": " + str(group_value)

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
  """Order of the categories of a symbolic x axis.

  By default the values are ordered naturally (numeric-aware). "Sort X by"
  dimensions take priority over that, in the order picked, exactly as "Sort by"
  does for traces; the x order then decides the last key (the value itself, or
  its y value) and whether the whole order is reversed.
  """
  if spec.x not in df.columns:
    return []
  values = _dimension_series(df, spec.x)
  categories = schema.sort_values(values.unique())

  order = spec.sort_x_order or "natural"
  sort_dims = [dim for dim in (spec.sort_x_by or ()) if dim in df.columns and dim != spec.x]
  by_y = order in ("y_asc", "y_desc")
  if not sort_dims and not by_y and order != "reverse":
    return categories

  frame = pd.DataFrame({dim: _dimension_series(df, dim) for dim in sort_dims})
  frame["__x"] = values
  if by_y:
    frame["__y"] = pd.to_numeric(df[spec.y], errors="coerce") if spec.y in df.columns else float("nan")

  natural_rank = {category: rank for rank, category in enumerate(categories)}
  keys = {}
  for category, sub in frame.groupby("__x", sort=False):
    # A category can span several rows: rank it by its first dimension values
    # and by its mean y, so the order stays defined whatever the traces are.
    dim_key = tuple(min(schema.sort_key(value) for value in sub[dim]) for dim in sort_dims)
    if by_y:
      mean = sub["__y"].mean()
      last = (1, 0.0) if pd.isna(mean) else (0, float(mean))  # missing y goes last
    else:
      last = (0, natural_rank.get(category, 0))
    keys[category] = (dim_key, last)

  ordered = sorted(categories, key=lambda category: keys[category])
  if order in ("reverse", "y_desc"):
    ordered.reverse()
  return ordered


def _x_label(category, spec):
  if spec.dissociate and spec.x == schema.COL_CONFIGURATION:
    return schema.clean_configuration_name(category, spec.dissociate)
  return str(category)


def _x_labels(categories, spec):
  """The x axis labels, in order and without duplicates.

  Dissociated dimensions are stripped from the labels, so several categories
  ("...+partition_none", "...+partition_cyclic") collapse into a single label:
  that is exactly the point of dissociating, each trace then holding one point
  per label instead of one point and holes where the other traces sit.
  """
  return list(dict.fromkeys(_x_label(category, spec) for category in categories))


def _categorical_xy(sub_df, spec, categories):
  """Align a trace on the shared x labels (None where a label has no value)."""
  series = pd.to_numeric(sub_df[spec.y], errors="coerce") if spec.y in sub_df.columns else pd.Series(dtype=float)
  by_label = {}
  if spec.x in sub_df.columns:
    x_values = _dimension_series(sub_df, spec.x)
    for x_value, y_value in zip(x_values, series):
      if pd.notna(y_value):
        by_label[_x_label(x_value, spec)] = y_value
  x = _x_labels(categories, spec)
  y = [by_label.get(label) for label in x]
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


def _parcoords_trace(df, spec, units, palette):
  """One parallel-coordinates axis per metric of spec.y_metrics.

  Unlike the other kinds, this is a single trace over the whole selection
  (parcoords has no notion of separate traces): lines are colored by the first
  "Color by" dimension when it holds numeric values, one solid color otherwise.
  """
  dimensions = []
  for metric in spec.y_metrics:
    if metric not in df.columns:
      continue
    series = pd.to_numeric(df[metric], errors="coerce")
    dimensions.append(dict(
      label=schema.axis_title(metric, units),
      values=series.fillna(series.mean() if series.notna().any() else 0).tolist(),
    ))

  line = dict(color=palettes.get_color(0, palette))
  if spec.color_by:
    color_column = spec.color_by[0]
    if color_column in df.columns:
      color_series = pd.to_numeric(df[color_column], errors="coerce")
      if color_series.notna().any():
        line = dict(
          color=color_series.fillna(color_series.mean()).tolist(),
          colorscale="Viridis",
          showscale=True,
          colorbar=dict(title=schema.metric_display_name(color_column)),
        )
      else:
        line = _parcoords_categorical_line(df[color_column], color_column, palette)

  return go.Parcoords(dimensions=dimensions, line=line)


def _parcoords_categorical_line(series, color_column, palette):
  """Line spec coloring parcoords lines by a non-numeric column's distinct values."""
  categories = series.astype(str).fillna("").tolist()
  uniques = sorted(set(categories))
  codes = [uniques.index(v) for v in categories]
  n = len(uniques)

  if n <= 1:
    return dict(color=palettes.get_color(0, palette))

  colors = [palettes.get_color(i, palette) for i in range(n)]
  colorscale = []
  for i, c in enumerate(colors):
    colorscale.append([i / n, c])
    colorscale.append([(i + 1) / n, c])

  tickvals = [i + 0.5 for i in range(n)]

  return dict(
    color=codes,
    colorscale=colorscale,
    cmin=0,
    cmax=n,
    showscale=True,
    colorbar=dict(
      title=schema.metric_display_name(color_column),
      tickvals=tickvals,
      ticktext=uniques,
    ),
  )


def _scatter_axis_series(sub_df, column):
  """Values for a scatter axis: numeric when the column holds any numeric value,
  otherwise the categorical (string) values, so a meta dimension can be plotted
  on an axis instead of only metrics."""
  numeric = pd.to_numeric(sub_df[column], errors="coerce")
  if numeric.notna().any():
    return numeric
  return _dimension_series(sub_df, column)


def _scatter_trace(sub_df, spec, units, color, symbol_index, hover_header, common):
  axes = [spec.x, spec.y] + ([spec.z] if spec.kind == "scatter3d" else [])
  points = pd.DataFrame({axis: _scatter_axis_series(sub_df, axis) for axis in axes})
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
  if spec.kind == "parcoords":
    return ", ".join(schema.metric_display_name(metric) for metric in (spec.y_metrics or ()))
  return schema.axis_title(spec.y, units)


def _apply_axis_scale(axis, log_on, zero_on):
  """Apply a log or start-at-zero scale to a numeric axis dict (log wins).

  A log axis cannot include zero, so "start at zero" is ignored when log is on.
  """
  if log_on:
    axis["type"] = "log"
    axis["dtick"] = 1
    axis["minor"] = dict(
      showgrid=axis.get("showgrid", True),
      gridcolor=axis.get("gridcolor"),
      griddash="dot",
      ticks="",
    )
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
  elif spec.kind == "parcoords":
    pass  # no cartesian/polar/scene axes: the dimensions carry their own labels/ranges
  else:
    # Categorical x: title is the dimension name; numeric x: metric title with unit
    xaxis = dict(title=str(spec.x) if categories else schema.axis_title(spec.x, units), **grid)
    if categories:
      xaxis["categoryorder"] = "array"
      xaxis["categoryarray"] = _x_labels(categories, spec)
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
  auto_color_by = _auto_line_color_dimension(spec, dimensions)
  for info, _ in group_traces(df, spec, dimensions):
    color_index, symbol_index = style_indices(info, spec, dimensions, global_dimensions, color_by=auto_color_by)
    entries.append((trace_name(info, dimensions, spec, {}), palettes.get_color(color_index, palette), palettes.get_marker_symbol(symbol_index)))
  return entries

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

# Notes about what a chart leaves out ("3 records ... not drawn") sit just
# above the plot area, under the title: below it they ended up printed over
# the x axis title, whose position depends on the length of the tick labels.
NOTE_SHIFT = 4

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


def identity_dimensions(spec, dimensions, split=()):
  """Dimensions splitting the selection into traces.

  ``split`` are the extra dimensions found by split_dimensions(), which keep
  several records of one trace from landing on the same x.
  """
  identity = [dim for dim in AUTO_GROUP_DIMENSIONS if dim in dimensions and len(dimensions[dim]) > 1]
  auto_line = _auto_line_color_dimension(spec, dimensions)
  if auto_line and auto_line not in identity:
    identity.append(auto_line)
  extras = list(spec.color_by or ()) + list(spec.symbol_by or ()) + list(spec.dissociate or ()) + list(spec.sort_by or ()) + [spec.legend_group_by]
  for extra in extras + list(split or ()):
    if extra and extra != NONE_VALUE and extra in dimensions and extra not in identity:
      identity.append(extra)
  # The x axis and point-label dimensions vary inside a trace
  excluded = {spec.x}
  if spec.kind in ("scatter", "scatter3d"):
    excluded.add(spec.label_by)
  return [dim for dim in identity if dim not in excluded]


# Chart kinds drawing one value per x and per trace: a second record of the
# same trace at the same x would hide the first one.
ONE_POINT_PER_X_KINDS = ("lines", "columns", "radar")


def _x_keys(df, spec, dimensions):
  """The x position of each row, as the trace aligns it (label or number)."""
  if spec.x in dimensions:
    return _dimension_series(df, spec.x).map(lambda value: _x_label(value, spec))
  return pd.to_numeric(df[spec.x], errors="coerce")


def _hidden_count(frame):
  return int(len(frame) - len(frame.drop_duplicates()))


def split_dimensions(df, spec, dimensions):
  """
  Dimensions to split the traces by so that no record is hidden.

  Lines, columns and radar charts draw one value per x in each trace. When
  several records of a trace share an x (one record per step of a job, one
  record per row of a ``multiple`` metric, ...), all but one would silently
  vanish. The dimensions telling those records apart are added to the trace
  identity instead, so every record is drawn: the fewest dimensions that do the
  job, picked greedily (the one leaving the fewest records hidden first, then
  the one with the fewest values).

  Returns:
      tuple: (list of dimensions, number of records still hidden). Records are
      still hidden only when no dimension tells them apart.
  """
  if spec.kind not in ONE_POINT_PER_X_KINDS or df.empty:
    return [], 0
  if spec.x not in df.columns or spec.y not in df.columns:
    return [], 0
  drawn = df[pd.to_numeric(df[spec.y], errors="coerce").notna()]
  if drawn.empty:
    return [], 0

  identity = identity_dimensions(spec, dimensions)
  frame = pd.DataFrame({dim: _dimension_series(drawn, dim) for dim in identity if dim in drawn.columns})
  frame["__x"] = _x_keys(drawn, spec, dimensions).astype(str)
  hidden = _hidden_count(frame)

  candidates = [
    dim for dim in dimensions
    if dim in drawn.columns and dim not in identity and dim != spec.x and len(dimensions[dim]) > 1
  ]
  if schema.COL_STEP in candidates and schema.COL_STEP_SCOPE in candidates:
    # The step scope only summarizes the step: the step itself says more
    candidates.remove(schema.COL_STEP_SCOPE)
  chosen = []
  while hidden and candidates:
    best = None
    for dim in candidates:
      trial = frame.copy()
      trial[dim] = _dimension_series(drawn, dim)
      remaining = _hidden_count(trial)
      if remaining >= hidden:
        continue
      if best is None or remaining < best[0] or (remaining == best[0] and len(dimensions[dim]) < len(dimensions[best[1]])):
        best = (remaining, dim)
    if best is None:
      break
    hidden, dim = best
    chosen.append(dim)
    candidates.remove(dim)
    frame[dim] = _dimension_series(drawn, dim)
  return chosen, hidden


def auto_style_dimensions(spec, dimensions, split=()):
  """
  (color_by, symbol_by) a chart uses on its own, None where the spec decides.

  A line chart colors by configuration when nothing explicit was picked (see
  _auto_line_color_dimension). The dimensions of ``split`` (split_dimensions)
  must be told apart too: they join the automatic colors, or take the symbols
  when the user already chose the colors.
  """
  auto_line = _auto_line_color_dimension(spec, dimensions)
  split = [dim for dim in (split or ()) if dim != auto_line]
  if not spec.color_by:
    color_by = ([auto_line] if auto_line else []) + split
    return (tuple(color_by) or None), None
  if split and not spec.symbol_by:
    return None, tuple(split)
  return None, None


def group_traces(df, spec, dimensions, split=()):
  """
  Split the selection into traces.

  ``split``: extra identity dimensions, see split_dimensions().

  Returns:
      list of (info dict {dimension: value}, sub DataFrame), sorted.
  """
  identity = identity_dimensions(spec, dimensions, split)
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


def trace_name(info, dimensions, spec, units, split=()):
  """Human-readable trace name from the dimension values identifying it.

  The dimensions of ``split`` were added behind the user's back
  (split_dimensions), so their name is spelled out next to their value.
  """
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
    elif dim in (split or ()):
      parts.append(str(dim) + ": " + str(value))
    elif dim == schema.COL_FREQUENCY:
      if value == schema.FMAX_FREQUENCY_VALUE:
        continue  # the result type ("Fmax") already says it
      parts.append("@ " + _frequency_text(value, units))
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


def style_indices(info, spec, dimensions, global_dimensions, color_by=None, symbol_by=None):
  """(color index, symbol index) of a trace, from its dimension values.

  ``color_by`` and ``symbol_by`` override spec.color_by and spec.symbol_by, for
  the dimensions a chart styles by on its own (see auto_style_dimensions).
  """
  reference = global_dimensions if spec.stable_index else dimensions

  if color_by:
    color_by = (color_by,) if isinstance(color_by, str) else tuple(color_by)
  else:
    color_by = spec.color_by or ()
  if symbol_by:
    symbol_by = (symbol_by,) if isinstance(symbol_by, str) else tuple(symbol_by)
  else:
    symbol_by = spec.symbol_by or ()

  color_index = _combination_index(info, color_by, reference, dimensions) if color_by else 0
  symbol_index = max(_combination_index(info, symbol_by, reference, dimensions), 0)

  return color_index, symbol_index


def _as_dims(value):
  if not value:
    return ()
  return (value,) if isinstance(value, str) else tuple(value)


def _drawn_style(style, palette):
  """What a (color index, symbol index) pair looks like once drawn: indices
  past the end of the palette or of the symbol list wrap around."""
  color_index, symbol_index = style
  return palettes.get_color(color_index, palette), palettes.get_marker_symbol(symbol_index)


def trace_styles(groups, spec, dimensions, global_dimensions=None, split=(), palette=palettes.DEFAULT_PALETTE):
  """
  (color index, symbol index) of every trace of group_traces(), in order.

  Two different series must never look the same. Color by and Symbol by do
  not always tell every trace apart: traces also split by the dimensions
  varying in the selection (two frequencies of one architecture, two targets,
  the flow of split_dimensions...). When two traces would be drawn with the
  same color and the same symbol, the dimensions telling them apart join the
  symbol dimensions -- for every trace, so one value keeps one symbol across
  the chart.
  """
  if global_dimensions is None:
    global_dimensions = dimensions
  color_by, symbol_by = auto_style_dimensions(spec, dimensions, split)

  def styles_for(symbol_dims):
    return [
      style_indices(info, spec, dimensions, global_dimensions, color_by=color_by, symbol_by=symbol_dims)
      for info, _sub_df in groups
    ]

  styles = styles_for(symbol_by)
  drawn = [_drawn_style(style, palette) for style in styles]
  if len(set(drawn)) == len(drawn):
    return styles

  color_dims = _as_dims(color_by) or tuple(spec.color_by or ())
  symbol_dims = _as_dims(symbol_by) or tuple(spec.symbol_by or ())
  residual = []
  for info, _sub_df in groups:
    for dimension in info:
      if dimension in color_dims or dimension in symbol_dims or dimension in residual:
        continue
      if len(set(str(other.get(dimension)) for other, _ in groups)) > 1:
        residual.append(dimension)
  if not residual:
    return styles
  return styles_for(symbol_dims + tuple(residual))


######################################
# Hover
######################################


def _frequency_text(value, units):
  """A frequency value as read: "100 MHz", or "Fmax search" for the rows of
  an fmax synthesis (which have no fixed frequency)."""
  if str(value) == schema.FMAX_FREQUENCY_VALUE:
    return "Fmax search"
  unit = units.get(schema.COL_FREQUENCY, "MHz") if units else "MHz"
  return str(value) + " " + unit


def _hover_header(info, units=None, skip=()):
  """The dimension values identifying a trace, one per hover line.

  ``skip``: dimensions the hover already shows on a line of their own (the
  point label of a scatter), so they are not listed twice.
  """
  lines = []
  for dim, value in info.items():
    if dim in skip or str(value) == schema.MISSING_VALUE:
      continue
    if dim == schema.COL_FREQUENCY:
      value = _frequency_text(value, units)
    lines.append("<b>" + str(dim) + ":</b> " + str(value))
  return "<br>".join(lines)


def _metric_hover_line(metric, axis, units):
  unit = schema.unit_to_html(units.get(metric, "")) if units else ""
  return "<b>" + schema.metric_display_name(metric) + ":</b> %{" + axis + "}" + ((" " + unit) if unit else "")


######################################
# Figure construction
######################################


def build_figure(df, spec, dimensions, metrics, units, chrome, global_dimensions=None, height=None, palette=palettes.DEFAULT_PALETTE, plot_theme=plot_themes.AUTO, empty_text=None, as_dict=False):
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
      empty_text (str | None): what an empty selection says in place of the
          chart (a generic sentence by default).
      as_dict (bool): return the plain {"data", "layout"} dict, which Dash
          sends as is, rather than wrapping it into a go.Figure.

  Returns:
      go.Figure (built from plain dicts, see make_figure), or a dict
  """
  if global_dimensions is None:
    global_dimensions = dimensions

  traces = []
  layout = {}

  if spec.kind == "parcoords":
    excluded = 0
    if not df.empty and spec.y_metrics:
      df, excluded = _parcoords_rows(df, spec)
      if not df.empty:
        traces.append(_parcoords_trace(df, spec, units, palette, global_dimensions if spec.stable_index else dimensions))
    _apply_layout(layout, spec, [], units, chrome, height, plot_theme)
    if excluded:
      _add_note(layout, str(excluded) + (" design" if excluded == 1 else " designs") + " without a value excluded", below=True)
    if not traces:
      _add_empty_message(layout, df, spec, chrome, empty_text)
    return make_figure(traces, layout, as_dict)

  if df.empty or spec.y is None:
    _apply_layout(layout, spec, [], units, chrome, height, plot_theme)
    _add_empty_message(layout, df, spec, chrome, empty_text)
    return make_figure(traces, layout, as_dict)

  x_is_metric = not x_is_symbolic(spec.kind, spec.x, dimensions, metrics)
  categories = [] if x_is_metric else _x_categories(df, spec)
  axis_categories = _scatter_axis_categories(df, spec) if spec.kind in ("scatter", "scatter3d") else {}

  split, hidden = split_dimensions(df, spec, dimensions)
  groups = group_traces(df, spec, dimensions, split)
  styles = trace_styles(groups, spec, dimensions, global_dimensions, split, palette)

  columns = _ColumnCache(df, spec)
  empty_traces = 0
  for (info, sub_df), (color_index, symbol_index) in zip(groups, styles):
    color = palettes.get_color(color_index, palette)
    name = trace_name(info, dimensions, spec, units, split)
    common = dict(name=name)
    if spec.has("legend_groups") and spec.legend_group_by and spec.legend_group_by != NONE_VALUE:
      group_value = info.get(spec.legend_group_by)
      if group_value is not None:
        legend_group = str(spec.legend_group_by) + ": " + str(group_value)
        common.update(legendgroup=legend_group, legendgrouptitle=dict(text=legend_group))

    hover_header = _hover_header(info, units, skip=(spec.label_by,) if spec.kind in ("scatter", "scatter3d") else ())

    if spec.kind in ("scatter", "scatter3d"):
      trace = _scatter_trace(sub_df, spec, units, color, symbol_index, hover_header, common, axis_categories)
    elif spec.kind == "columns":
      trace = _bar_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common, columns)
    elif spec.kind == "radar":
      trace = _radar_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common, columns)
    else:
      trace = _line_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common, x_is_metric, columns)
    if not _has_value(trace):
      # Nothing to draw: a legend entry with no line or point behind it only
      # says "there is nothing here" in a confusing way. Counted instead.
      empty_traces += 1
      continue
    traces.append(trace)

  _apply_layout(layout, spec, categories, units, chrome, height, plot_theme, axis_categories)
  notes = []
  if hidden:
    # Nothing tells these records apart from another one at the same x: say
    # so rather than drop them silently.
    notes.append(
      str(hidden) + (" record shares" if hidden == 1 else " records share") + " an x value with another record of the same trace and "
      + ("is" if hidden == 1 else "are") + " not drawn (see Table)"
    )
  if empty_traces and traces:
    notes.append(
      str(empty_traces) + (" series has" if empty_traces == 1 else " series have") + " no value for "
      + schema.metric_display_name(spec.y) + " and " + ("is" if empty_traces == 1 else "are") + " left out"
    )
  if notes:
    _add_note(layout, " · ".join(notes))
  if not traces:
    _add_empty_message(layout, df, spec, chrome, empty_text)
  return make_figure(traces, layout, as_dict)


def make_figure(traces, layout, as_dict=False):
  """
  Wrap plain trace and layout dicts into a figure, without Plotly's property
  validation.

  Validating every property of every trace is what made the charts slow: on a
  few hundred records it took 90 % of the build time (a chart page waited
  seconds, the home page thumbnails tens of seconds). The dicts written here
  only use plain plotly.js attributes, spelled out in full (``title=dict(text=
  ...)``, never the ``title_text`` shorthand only the validator expands), so
  skipping the validation changes nothing in what the browser receives.
  """
  if as_dict:
    return dict(data=traces, layout=layout)
  return go.Figure(dict(data=traces, layout=layout), _validate=False)


def _add_note(layout, text, below=False):
  """A small line above the plot area (below it on a parcoords, whose axis
  labels take the top)."""
  layout.setdefault("annotations", []).append(dict(
    text=text, xref="paper", yref="paper", x=0, xanchor="left",
    y=0 if below else 1, yanchor="top" if below else "bottom",
    yshift=-25 if below else NOTE_SHIFT, showarrow=False, font=dict(size=11), opacity=0.7,
  ))


def _has_value(trace):
  """Whether a trace holds at least one value it can draw."""
  values = trace.get("r") if trace.get("type") == "scatterpolar" else trace.get("y")
  return any(value is not None and value == value for value in (values or ()))


def _add_empty_message(layout, df, spec, chrome, empty_text=None):
  """Say why the chart is empty, in the middle of the plot, with no axes."""
  if df is None or df.empty:
    text = empty_text or "Nothing to plot: no record matches the selected sources and filters."
  elif spec.kind == "parcoords" and not spec.y_metrics:
    text = "Pick the metrics to compare in Axes → Metrics."
  elif spec.y is None:
    text = "These results hold no numeric metric to plot."
  else:
    text = "No value of " + schema.metric_display_name(spec.y) + " in this selection."
  layout.pop("title", None)
  for axis in ("xaxis", "yaxis"):
    layout[axis] = dict(visible=False)
  layout.setdefault("annotations", []).append(dict(
    text=text, xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
    font=dict(size=14, color=chrome.get("text_color")),
  ))


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
      # Missing y goes last in both directions: descending negates the mean
      # instead of reversing, which would bring the blanks to the front.
      if pd.isna(mean):
        last = (1, 0.0)
      else:
        last = (0, -float(mean) if order == "y_desc" else float(mean))
    else:
      last = (0, natural_rank.get(category, 0))
    keys[category] = (dim_key, last)

  ordered = sorted(categories, key=lambda category: keys[category])
  if order == "reverse":
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


class _ColumnCache(object):
  """The x labels and numeric y values of a whole selection, computed once
  rather than once per trace (a chart can hold hundreds of traces)."""

  def __init__(self, df, spec):
    # Traces look their rows up by index label, which needs unique labels
    self.aligned = df.index.is_unique
    # {row index: (x label, y value)} of the rows holding a y value
    self.points = {}
    if spec.x in df.columns and spec.y in df.columns:
      y_values = pd.to_numeric(df[spec.y], errors="coerce")
      x_values = _dimension_series(df, spec.x)
      labels = {value: _x_label(value, spec) for value in x_values.unique()}
      for index, x_value, y_value in zip(df.index, x_values, y_values):
        if pd.notna(y_value):
          self.points[index] = (labels[x_value], float(y_value))


def _categorical_xy(sub_df, spec, categories, columns=None):
  """Align a trace on the shared x labels (None where a label has no value)."""
  if columns is None or not columns.aligned:
    columns = _ColumnCache(sub_df, spec)
  by_label = {}
  for index in sub_df.index:
    point = columns.points.get(index)
    if point is not None:
      by_label[point[0]] = point[1]
  x = _x_labels(categories, spec)
  y = [by_label.get(label) for label in x]
  return x, y


def _line_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common, x_is_metric, columns=None):
  if x_is_metric:
    points = sub_df[[spec.x, spec.y]].apply(pd.to_numeric, errors="coerce").dropna().sort_values(spec.x)
    x, y = points[spec.x].tolist(), points[spec.y].tolist()
    hover_x = _metric_hover_line(spec.x, "x", units)
  else:
    x, y = _categorical_xy(sub_df, spec, categories, columns)
    hover_x = "<b>" + str(spec.x) + ":</b> %{x}"
  return dict(
    type="scatter",
    x=x,
    y=y,
    mode="lines+markers" if spec.has("lines") else "markers",
    line=dict(dash="dot", color=color),
    marker=dict(symbol=palettes.get_marker_symbol(symbol_index), color=color),
    connectgaps=spec.has("connect_gaps"),
    hovertemplate=hover_header + ("<br>" if hover_header else "") + hover_x + "<br>" + _metric_hover_line(spec.y, "y", units) + "<extra></extra>",
    **common
  )


def _bar_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common, columns=None):
  x, y = _categorical_xy(sub_df, spec, categories, columns)
  return dict(
    type="bar",
    x=x,
    y=y,
    marker=dict(color=color, pattern=dict(shape=palettes.get_bar_pattern(symbol_index))),
    hovertemplate=hover_header + ("<br>" if hover_header else "") + "<b>" + str(spec.x) + ":</b> %{x}<br>" + _metric_hover_line(spec.y, "y", units) + "<extra></extra>",
    **common
  )


def _radar_trace(sub_df, spec, categories, units, color, symbol_index, hover_header, common, columns=None):
  theta, r = _categorical_xy(sub_df, spec, categories, columns)
  if spec.has("close_line") and len(theta) > 0:
    theta = theta + [theta[0]]
    r = r + [r[0]]
  # Shortened labels around the circle, the full one in the hover. Only when
  # shortening keeps every label distinct, or two categories would merge.
  labels = _x_labels(categories, spec)
  full = theta
  if len(set(short_label(label) for label in labels)) == len(labels):
    theta = [short_label(label) for label in theta]
  return dict(
    type="scatterpolar",
    theta=theta,
    customdata=full,
    r=r,
    mode="lines+markers",
    line=dict(dash="dot", color=color),
    marker=dict(symbol=palettes.get_marker_symbol(symbol_index), color=color),
    connectgaps=spec.has("connect_gaps"),
    hovertemplate=hover_header + ("<br>" if hover_header else "") + "<b>" + str(spec.x) + ":</b> %{customdata}<br>" + _metric_hover_line(spec.y, "r", units) + "<extra></extra>",
    **common
  )


def _parcoords_numeric_color(df, spec):
  """The numeric "Color by" column of a parcoords, or None (solid/categorical)."""
  if not spec.color_by or spec.color_by[0] not in df.columns:
    return None
  column = spec.color_by[0]
  return column if pd.to_numeric(df[column], errors="coerce").notna().any() else None


def _parcoords_rows(df, spec):
  """
  The rows a parcoords can draw honestly, and how many were left out.

  ``go.Parcoords`` has no notion of a missing value (and no hover to say so):
  any filler -- the mean, zero -- draws a line through a value that was never
  measured. A row missing one of the charted metrics, or the numeric color, is
  dropped instead, and the caller says how many.
  """
  columns = [metric for metric in spec.y_metrics if metric in df.columns]
  color_column = _parcoords_numeric_color(df, spec)
  if color_column is not None and color_column not in columns:
    columns.append(color_column)
  if not columns:
    return df, 0
  present = pd.DataFrame({column: pd.to_numeric(df[column], errors="coerce") for column in columns}).notna().all(axis=1)
  return df[present], int((~present).sum())


def _parcoords_trace(df, spec, units, palette, reference=None):
  """One parallel-coordinates axis per metric of spec.y_metrics.

  Unlike the other kinds, this is a single trace over the whole selection
  (parcoords has no notion of separate traces): lines are colored by the first
  "Color by" dimension when it holds numeric values, one solid color otherwise.
  Rows with a missing value are expected to be gone already (_parcoords_rows).
  """
  dimensions = []
  for metric in spec.y_metrics:
    if metric not in df.columns:
      continue
    series = pd.to_numeric(df[metric], errors="coerce")
    dimensions.append(dict(
      label=schema.axis_title(metric, units),
      values=series.tolist(),
    ))

  line = dict(color=palettes.get_color(0, palette))
  if spec.color_by:
    color_column = spec.color_by[0]
    if color_column in df.columns:
      color_series = pd.to_numeric(df[color_column], errors="coerce")
      if color_series.notna().any():
        line = dict(
          color=color_series.tolist(),
          colorscale="Viridis",
          showscale=True,
          colorbar=dict(title=dict(text=schema.metric_display_name(color_column))),
        )
      else:
        line = _parcoords_categorical_line(df[color_column], color_column, palette, (reference or {}).get(color_column))

  return dict(type="parcoords", dimensions=dimensions, line=line)


def _parcoords_categorical_line(series, color_column, palette, reference=None):
  """Line spec coloring parcoords lines by a non-numeric column's distinct values.

  ``reference``: the values of the dimension the other charts index their
  colors on, so one architecture keeps the same color on every chart.
  """
  categories = series.fillna(schema.MISSING_VALUE).astype(str).tolist()
  uniques = schema.sort_values(set(categories))
  codes = [uniques.index(v) for v in categories]
  n = len(uniques)
  reference = [str(value) for value in (reference or ())]

  def color_of(index, value):
    return palettes.get_color(reference.index(value) if value in reference else index, palette)

  if n <= 1:
    return dict(color=color_of(0, uniques[0] if uniques else ""))

  colors = [color_of(i, value) for i, value in enumerate(uniques)]
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
      title=dict(text=schema.metric_display_name(color_column)),
      tickvals=tickvals,
      ticktext=uniques,
    ),
  )


def _scatter_axes(spec):
  return [spec.x, spec.y] + ([spec.z] if spec.kind == "scatter3d" else [])


def _scatter_axis_categories(df, spec):
  """Sorted categories of each categorical scatter axis, {axis: [values]}.

  An axis is numeric when its column holds any numeric value over the whole
  data, otherwise categorical, so a meta dimension can be plotted on an axis
  instead of only metrics. Deciding on the whole data (not per trace) keeps a
  trace whose values are all missing from turning a numeric axis categorical.
  Missing values are left out: they have no place on an axis.
  """
  categories = {}
  for axis in _scatter_axes(spec):
    if axis not in df.columns or pd.to_numeric(df[axis], errors="coerce").notna().any():
      continue
    categories[axis] = schema.sort_values(str(value) for value in df[axis].dropna().unique())
  return categories


def _scatter_axis_series(sub_df, column, categorical):
  """Values for a scatter axis, NaN where missing (see _scatter_axis_categories)."""
  if categorical:
    return sub_df[column].where(sub_df[column].isna(), sub_df[column].astype(str))
  return pd.to_numeric(sub_df[column], errors="coerce")


def _scatter_trace(sub_df, spec, units, color, symbol_index, hover_header, common, axis_categories):
  axes = _scatter_axes(spec)
  points = pd.DataFrame({axis: _scatter_axis_series(sub_df, axis, axis in axis_categories) for axis in axes})
  keep = points.notna().all(axis=1)
  points = points[keep]
  kept_df = sub_df[keep]

  mode = "markers"
  if spec.has("scatter_lines"):
    mode += "+lines"
    if spec.x in axis_categories:
      rank = {category: index for index, category in enumerate(axis_categories[spec.x])}
      order = points[spec.x].map(rank).to_numpy().argsort(kind="stable")
    else:
      order = points[spec.x].to_numpy().argsort(kind="stable")
    points = points.iloc[order]
    kept_df = kept_df.iloc[order]

  labels = None
  if spec.label_by and spec.label_by in sub_df.columns:
    labels = _dimension_series(kept_df, spec.label_by).tolist()
    if spec.dissociate and spec.label_by == schema.COL_CONFIGURATION:
      labels = [schema.clean_configuration_name(label, spec.dissociate) for label in labels]

  if spec.has("labels") and labels is not None:
    mode += "+text"

  hover_lines = [_metric_hover_line(axis_metric, axis_name, units) for axis_metric, axis_name in zip(axes, ["x", "y", "z"])]
  if labels is not None:
    hover_lines.insert(0, "<b>" + str(spec.label_by) + ":</b> %{text}")
  hovertemplate = hover_header + ("<br>" if hover_header else "") + "<br>".join(hover_lines) + "<extra></extra>"

  if labels is not None:
    common = dict(common, text=labels)
  if spec.kind == "scatter3d":
    return dict(
      type="scatter3d",
      x=points[spec.x].tolist(),
      y=points[spec.y].tolist(),
      z=points[spec.z].tolist(),
      mode=mode,
      line=dict(dash="dot", color=color),
      marker=dict(symbol=palettes.get_marker_symbol_3d(symbol_index), color=color, size=4),
      hovertemplate=hovertemplate,
      **common
    )
  return dict(
    type="scatter",
    x=points[spec.x].tolist(),
    y=points[spec.y].tolist(),
    mode=mode,
    textposition="top center",
    line=dict(dash="dot", color=color),
    marker=dict(symbol=palettes.get_marker_symbol(symbol_index), color=color),
    connectgaps=True,
    hovertemplate=hovertemplate,
    **common
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


def _apply_category_order(axis_layout, axis, axis_categories):
  """Natural order for a categorical scatter axis (plotly keeps first-seen order)."""
  if axis_categories and axis in axis_categories:
    axis_layout["type"] = "category"
    axis_layout["categoryorder"] = "array"
    axis_layout["categoryarray"] = axis_categories[axis]


def _title(text):
  """A title as plotly.js reads it (the bare string form is the validator's
  shorthand, not a plotly.js attribute)."""
  return dict(text=text)


def _parse_color(color):
  """(r, g, b, alpha) of a "#rrggbb", "#rgb" or "rgb[a](...)" color, or None."""
  text = str(color or "").strip().lower()
  try:
    if text.startswith("#"):
      digits = text[1:]
      if len(digits) == 3:
        digits = "".join(char * 2 for char in digits)
      return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16), 1.0
    if text.startswith("rgb"):
      parts = [part.strip() for part in text[text.index("(") + 1:text.rindex(")")].split(",")]
      alpha = float(parts[3]) if len(parts) > 3 else 1.0
      return int(float(parts[0])), int(float(parts[1])), int(float(parts[2])), alpha
  except (ValueError, IndexError):
    pass
  return None


def opaque_grid_color(color, dark, strength=2.0):
  """
  An opaque version of a translucent grid color, for the 3D scene.

  The WebGL renderer of the 3D scene ignores the alpha of a grid color: the
  "rgba(240, 240, 240, 0.15)" of a dark theme was drawn as solid white lines,
  and the light theme's grid nearly vanished. The color is premixed instead
  over the usual page background of the theme, a bit stronger than on 2D
  charts since the 3D lines are thinner.
  """
  parsed = _parse_color(color)
  if parsed is None:
    return color
  red, green, blue, alpha = parsed
  alpha = min(1.0, alpha * strength)
  base = (36, 41, 46) if dark else (255, 255, 255)
  mixed = [int(round(channel * alpha + background * (1 - alpha))) for channel, background in zip((red, green, blue), base)]
  return "#%02x%02x%02x" % tuple(mixed)


# Angular labels of a radar chart longer than this are shortened in the middle
# (the full label stays in the hover): long configuration names were cut by
# the edge of the chart and printed over the legend.
RADAR_LABEL_LENGTH = 24


def short_label(label, length=RADAR_LABEL_LENGTH):
  """A label shortened in the middle, keeping its start and its end (where
  the parameter values of a configuration name usually are)."""
  label = str(label)
  if len(label) <= length:
    return label
  head = (length - 1) // 2
  tail = length - 1 - head
  return label[:head] + "…" + label[-tail:]


def _apply_layout(layout, spec, categories, units, chrome, height, plot_theme, axis_categories=None):
  """Fill the ``layout`` dict of a figure (plain plotly.js attributes)."""
  template = plot_themes.get_template(plot_theme)
  auto = template is None
  dark = bool(chrome.get("dark"))

  layout.update(
    template=plot_themes.template_dict(template if not auto else ("plotly_dark" if dark else "plotly")),
    showlegend=spec.has("legend"),
    uirevision=":".join(str(part) for part in (spec.kind, spec.x, spec.y, spec.z)),
    margin=dict(l=60, r=30, t=60 if spec.has("title") else 30, b=50),
    modebar=dict(bgcolor=TRANSPARENT),
    # Marks a figure drawn by the chart engine, as opposed to the empty
    # placeholder a chart page starts with (see explorer_tabs.js).
    meta=dict(odatix=True),
  )
  if height is not None:
    layout["height"] = height
  if spec.has("title"):
    layout["title"] = dict(text=_figure_title(spec, units), x=0.5)

  if auto:
    layout.update(
      paper_bgcolor=TRANSPARENT,
      plot_bgcolor=TRANSPARENT,
      font=dict(color=chrome.get("text_color")),
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
      # Room around the circle for the angular labels, which plotly.js draws
      # outside the polar domain without reserving any margin for them.
      domain=dict(x=[0.1, 0.9], y=[0.04, 0.96]),
    )
    if auto:
      layout["polar"]["bgcolor"] = TRANSPARENT
  elif spec.kind == "scatter3d":
    axis_defaults = {}
    if auto:
      axis_defaults = dict(
        gridcolor=opaque_grid_color(chrome.get("grid_color"), dark),
        zerolinecolor=opaque_grid_color(chrome.get("zeroline_color"), dark, strength=1.0),
        showbackground=False,
        backgroundcolor=TRANSPARENT,
      )
    zero = spec.has("zero_axis")
    layout["scene"] = dict(
      xaxis=_apply_axis_scale(dict(title=_title(schema.axis_title(spec.x, units)), **axis_defaults), spec.has("log_x"), zero),
      yaxis=_apply_axis_scale(dict(title=_title(schema.axis_title(spec.y, units)), **axis_defaults), spec.has("log_y"), zero),
      zaxis=_apply_axis_scale(dict(title=_title(schema.axis_title(spec.z, units)), **axis_defaults), spec.has("log_z"), zero),
      camera=dict(eye=dict(x=1.6, y=1.6, z=0.6)),
    )
    layout["legend"] = dict(itemsizing="constant")
    for name, axis in (("xaxis", spec.x), ("yaxis", spec.y), ("zaxis", spec.z)):
      _apply_category_order(layout["scene"][name], axis, axis_categories)
  elif spec.kind == "parcoords":
    # No cartesian/polar/scene axes: the dimensions carry their own labels and
    # ranges. Their labels sit above the plot area and are centered on the
    # first and last axes, which stand on its edges: the margins make room
    # for them, under the title.
    layout["margin"].update(l=90, r=90, t=120 if spec.has("title") else 70)
  else:
    # Categorical x: title is the dimension name; numeric x: metric title with unit
    xaxis = dict(title=_title(str(spec.x) if categories else schema.axis_title(spec.x, units)), **grid)
    if categories:
      xaxis["categoryorder"] = "array"
      xaxis["categoryarray"] = _x_labels(categories, spec)
    else:
      # Numeric x axis only: log scale / start-at-zero (ignored for categorical x).
      zero_x = spec.has("zero_x") or (spec.kind != "scatter" and spec.has("zero_y"))
      _apply_axis_scale(xaxis, spec.has("log_x"), zero_x)
    yaxis = _apply_axis_scale(dict(title=_title(schema.axis_title(spec.y, units)), **grid), spec.has("log_y"), spec.has("zero_y"))
    if spec.kind == "scatter":
      _apply_category_order(xaxis, spec.x, axis_categories)
      _apply_category_order(yaxis, spec.y, axis_categories)
    layout["xaxis"] = xaxis
    layout["yaxis"] = yaxis


######################################
# Overview & legend helpers
######################################


def build_overview_figures(df, spec, dimensions, metrics, units, chrome, global_dimensions=None, size=(475, 475), palette=palettes.DEFAULT_PALETTE, plot_theme=plot_themes.AUTO, as_dict=False):
  """One figure per metric of the selection (same spec otherwise)."""
  from dataclasses import replace

  figures = []
  for metric in metrics:
    metric_spec = replace(spec, y=metric)
    fig = build_figure(
      df, metric_spec, dimensions, metrics, units, chrome,
      global_dimensions=global_dimensions, height=size[1], palette=palette, plot_theme=plot_theme,
      as_dict=as_dict,
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
  split, _hidden = split_dimensions(df, spec, dimensions)
  groups = group_traces(df, spec, dimensions, split)
  styles = trace_styles(groups, spec, dimensions, global_dimensions, split, palette)
  for (info, _), (color_index, symbol_index) in zip(groups, styles):
    entries.append((trace_name(info, dimensions, spec, {}, split), palettes.get_color(color_index, palette), palettes.get_marker_symbol(symbol_index)))
  return entries

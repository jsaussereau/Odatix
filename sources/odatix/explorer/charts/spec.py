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
Figure specification: what to plot and how, independent from any chart type.

A FigureSpec is built from the UI controls and handed to the chart engine
(charts.builder). Every "by" field accepts ANY dimension discovered in the
data — nothing is hardcoded to architectures, targets or any other concept.
"""

from dataclasses import dataclass, field

import odatix.explorer.core.schema as schema

NONE_VALUE = "none"

# Controls accepting several dimensions at once (multi dropdowns). Their spec
# fields hold a tuple of dimensions: () means "none", None means "not set yet"
# (resolve_defaults then picks a default).
MULTI_CONTROLS = ("color_by", "symbol_by", "sort_by", "sort_x_by", "dissociate", "y_metrics")

# Ordering of a categorical (symbolic) x axis. "natural" is the numeric-aware
# ordering of the values themselves; the y orders rank the categories by their
# y value (mean over the selection).
X_ORDERS = ("natural", "reverse", "y_asc", "y_desc")
X_ORDER_LABELS = {
  "natural": "Natural",
  "reverse": "Reversed",
  "y_asc": "Y ascending",
  "y_desc": "Y descending",
}
DEFAULT_X_ORDER = "natural"

KINDS = ["lines", "columns", "scatter", "scatter3d", "radar", "parcoords"]

KIND_LABELS = {
  "lines": "Lines",
  "columns": "Columns",
  "scatter": "Scatter",
  "scatter3d": "Scatter 3D",
  "radar": "Radar",
  "parcoords": "Parallel Coordinates",
  "overview": "Overview",
  "table": "Table",
}

# Minimum number of metrics to preselect by default on a fresh parallel
# coordinates chart (fewer than that and the plot is not very useful, more and
# it gets cluttered, so the user is left to add more explicitly).
PARCOORDS_DEFAULT_METRICS = 4

# Which controls make sense for each chart kind. Drives the sidebar control
# visibility; "axes" lists the axis selectors to show ("x" of lines, columns
# and radar accepts any dimension or metric, "x"/"y"/"z" of scatter kinds are
# metrics).
CAPABILITIES = {
  "lines": dict(axes=("x", "y"), toggles=("legend", "legend_groups", "title", "lines", "connect_gaps", "zero_y", "log_x", "log_y")),
  "columns": dict(axes=("x", "y"), toggles=("legend", "legend_groups", "title", "zero_y", "log_y")),
  "scatter": dict(axes=("x", "y"), toggles=("legend", "legend_groups", "title", "scatter_lines", "labels", "zero_x", "zero_y", "log_x", "log_y")),
  "scatter3d": dict(axes=("x", "y", "z"), toggles=("legend", "legend_groups", "title", "scatter_lines", "labels", "zero_axis", "log_x", "log_y", "log_z")),
  "radar": dict(axes=("x", "y"), toggles=("legend", "legend_groups", "title", "close_line", "connect_gaps", "log_y")),
  # No x/y/z axis selectors: the metrics shown are picked with their own
  # multi-select ("xp-parcoords-metrics"), one axis per metric.
  "parcoords": dict(axes=(), toggles=("title",)),
  "overview": dict(axes=(), toggles=("legend", "legend_groups", "title", "lines", "connect_gaps", "close_line", "zero_y", "log_x", "log_y")),
  # The table view has no axes or chart toggles: columns are chosen in its own
  # "Columns" sidebar section, and sorting/filtering happen in the table itself.
  "table": dict(axes=(), toggles=()),
}

TOGGLE_LABELS = {
  "legend": "Show legend",
  "legend_groups": "Group legend",
  "title": "Show title",
  "lines": "Show lines",
  "scatter_lines": "Connect points",
  "connect_gaps": "Connect gaps",
  "close_line": "Close lines",
  "labels": "Show labels",
  "zero_x": "X axis starts at zero",
  "zero_y": "Y axis starts at zero",
  "zero_axis": "Axes start at zero",
  "log_x": "Log scale X axis",
  "log_y": "Log scale Y axis",
  "log_z": "Log scale Z axis",
  "stable_index": "Stable colors and symbols",
}

DEFAULT_TOGGLES = ["legend", "legend_groups", "title", "lines", "connect_gaps", "close_line", "labels", "zero_x", "zero_y", "zero_axis"]

# Overview grid layouts: name -> (chart width, chart height)
OVERVIEW_LAYOUTS = {
  "default": (475, 475),
  "large": (760, 475),
  "tall": (475, 760),
  "large tall": (760, 760),
  "page wide": (None, 475),  # full row width
}


@dataclass
class FigureSpec:
  kind: str = "lines"
  x: str = None                 # x dimension or metric (theta for radar)
  y: str = None                 # y metric (r for radar)
  z: str = None                 # z metric (scatter3d)
  color_by: tuple = None        # dimensions, one color per value combination
  symbol_by: tuple = None       # dimensions, one symbol per value combination
  legend_group_by: str = None   # any dimension, or NONE_VALUE
  sort_by: tuple = None          # dimensions taking priority when ordering traces, in priority order
  sort_x_by: tuple = None       # dimensions taking priority when ordering a categorical x axis
  sort_x_order: str = None      # ordering of a categorical x axis (see X_ORDERS)
  dissociate: tuple = None      # dimensions pulled out of x labels into trace identity
  y_metrics: tuple = None       # metrics, one parcoords axis each (parcoords only)
  label_by: str = None          # dimension used for point labels (scatter kinds)
  stable_index: bool = False    # color/symbol indices computed over all values (stable across filters)
  toggles: tuple = field(default_factory=tuple)

  def has(self, toggle):
    return toggle in self.toggles


def x_is_symbolic(kind, x, dimensions, metrics):
  """Whether the x axis holds categories rather than numbers.

  Scatter kinds always plot metrics on x; elsewhere x accepts any dimension, and
  is numeric only when the chosen name is a metric and nothing else.
  """
  if kind in ("scatter", "scatter3d"):
    return False
  return not (x in metrics and x not in dimensions)


def normalize_dims(value, dimensions=None):
  """
  Normalize a multi-dimension control value into a tuple of dimensions.

  Accepts what the UI and the saved views may hold: a list (multi dropdown), a
  single dimension name (legacy single dropdown or saved view), NONE_VALUE or
  None. Returns None when unset (so resolve_defaults can pick a default), and
  an empty tuple when explicitly set to nothing. Values missing from
  ``dimensions`` are dropped when it is given.
  """
  if value is None:
    return None
  values = list(value) if isinstance(value, (list, tuple)) else [value]
  values = [str(item) for item in values if item not in (None, NONE_VALUE)]
  if dimensions is not None:
    values = [item for item in values if item in dimensions]
  return tuple(dict.fromkeys(values))  # de-duplicated, order preserved


def normalize_metrics(value, metrics=None):
  """Same as ``normalize_dims``, but for controls holding metrics (parcoords'
  Y metrics) rather than dimensions."""
  if value is None:
    return None
  values = list(value) if isinstance(value, (list, tuple)) else [value]
  values = [str(item) for item in values if item not in (None, NONE_VALUE)]
  if metrics is not None:
    values = [item for item in values if item in metrics]
  return tuple(dict.fromkeys(values))


def resolve_defaults(spec, dimensions, metrics):
  """
  Fill unset spec fields with sensible defaults based on the discovered
  dimensions ({name: [values]}) and metrics of the current selection.
  """
  multi = [dim for dim, values in dimensions.items() if len(values) > 1]

  def pick(candidates, fallback=None):
    for candidate in candidates:
      if candidate in dimensions:
        return candidate
    return fallback

  if spec.kind == "parcoords":
    spec.x = None
    spec.y = metrics[0] if metrics else None
  elif spec.kind in ("scatter", "scatter3d"):
    # Scatter axes accept metrics or any dimension (meta), metrics preferred.
    axis_choices = list(metrics) + [dim for dim in dimensions if dim not in metrics]
    if spec.x not in axis_choices:
      spec.x = axis_choices[0] if axis_choices else None
    if spec.label_by is None:
      spec.label_by = pick([schema.COL_CONFIGURATION], multi[0] if multi else None)
    if spec.y not in axis_choices:
      spec.y = next((choice for choice in axis_choices if choice != spec.x), axis_choices[0] if axis_choices else None)
    if spec.kind == "scatter3d" and spec.z not in axis_choices:
      spec.z = next((choice for choice in axis_choices if choice not in (spec.x, spec.y)), spec.y)
  else:
    if spec.x is None or (spec.x not in dimensions and spec.x not in metrics):
      spec.x = pick([schema.COL_CONFIGURATION], multi[0] if multi else (next(iter(dimensions), None)))
    if spec.y not in metrics:
      spec.y = next((metric for metric in metrics if metric != spec.x), metrics[0] if metrics else None)

  def resolve_multi(value, default):
    """Keep the still-existing dimensions of a multi control; fall back to the
    default when it is unset, or when every dimension it named disappeared."""
    requested = normalize_dims(value)
    kept = normalize_dims(value, dimensions)
    if requested and not kept:
      kept = None  # everything vanished from the data: default again
    if kept is not None:
      return kept
    default = default() if callable(default) else default
    return () if default in (None, NONE_VALUE) else (default,)

  spec.color_by = resolve_multi(spec.color_by, lambda: pick([schema.COL_ARCHITECTURE, schema.COL_WORKFLOW, schema.COL_SOURCE], pick(multi)))
  spec.symbol_by = resolve_multi(spec.symbol_by, lambda: pick([schema.COL_TARGET]))
  if spec.legend_group_by is None or (spec.legend_group_by != NONE_VALUE and spec.legend_group_by not in dimensions):
    spec.legend_group_by = pick([schema.COL_TARGET, schema.COL_SOURCE], NONE_VALUE)
  spec.sort_by = resolve_multi(spec.sort_by, None)
  spec.sort_x_by = resolve_multi(spec.sort_x_by, None)
  if spec.sort_x_order not in X_ORDERS:
    spec.sort_x_order = DEFAULT_X_ORDER
  spec.dissociate = resolve_multi(spec.dissociate, None)

  requested_y_metrics = normalize_metrics(spec.y_metrics)
  kept_y_metrics = normalize_metrics(spec.y_metrics, metrics)
  if requested_y_metrics and not kept_y_metrics:
    kept_y_metrics = None  # every requested metric vanished from the data: default again
  spec.y_metrics = kept_y_metrics if kept_y_metrics is not None else tuple(metrics[:PARCOORDS_DEFAULT_METRICS])

  return spec

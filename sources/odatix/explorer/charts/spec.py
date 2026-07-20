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

KINDS = ["lines", "columns", "scatter", "scatter3d", "radar"]

KIND_LABELS = {
  "lines": "Lines",
  "columns": "Columns",
  "scatter": "Scatter",
  "scatter3d": "Scatter 3D",
  "radar": "Radar",
  "overview": "Overview",
  "table": "Table",
}

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
  color_by: str = None          # any dimension
  symbol_by: str = None         # any dimension, or NONE_VALUE
  legend_group_by: str = None   # any dimension, or NONE_VALUE
  dissociate: str = None        # dimension pulled out of x labels into trace identity
  label_by: str = None          # dimension used for point labels (scatter kinds)
  stable_index: bool = True     # color/symbol indices computed over all values (stable across filters)
  toggles: tuple = field(default_factory=tuple)

  def has(self, toggle):
    return toggle in self.toggles


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

  if spec.kind in ("scatter", "scatter3d"):
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

  if spec.color_by is None or (spec.color_by != NONE_VALUE and spec.color_by not in dimensions):
    spec.color_by = pick([schema.COL_ARCHITECTURE, schema.COL_WORKFLOW, schema.COL_SOURCE], pick(multi))
  if spec.symbol_by is None or (spec.symbol_by != NONE_VALUE and spec.symbol_by not in dimensions):
    spec.symbol_by = pick([schema.COL_TARGET], NONE_VALUE)
  if spec.legend_group_by is None or (spec.legend_group_by != NONE_VALUE and spec.legend_group_by not in dimensions):
    spec.legend_group_by = pick([schema.COL_TARGET, schema.COL_SOURCE], NONE_VALUE)
  if spec.dissociate is not None and spec.dissociate not in dimensions:
    spec.dissociate = None

  return spec

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
Column naming and classification rules of the Odatix Explorer data model.

Result records (see odatix.lib.results_schema) are flattened into a tidy
DataFrame: one column per meta key (dimensions) plus one column per metric.
Nothing here is specific to hardware architectures: any meta key found in the
data becomes a dimension, any metric key becomes a metric.
"""

import re

import odatix.lib.results_schema as results_schema

# Display column names for reserved meta keys
COL_SOURCE = "Source"
COL_TYPE = "Type"
COL_TARGET = "Target"
COL_ARCHITECTURE = "Architecture"
COL_CONFIGURATION = "Configuration"
COL_FREQUENCY = "Frequency"
COL_WORKFLOW = "Workflow"
COL_TIMESTAMP = "Timestamp"

RESERVED_META_COLUMNS = {
  results_schema.META_TYPE: COL_TYPE,
  results_schema.META_TARGET: COL_TARGET,
  results_schema.META_ARCHITECTURE: COL_ARCHITECTURE,
  results_schema.META_CONFIGURATION: COL_CONFIGURATION,
  results_schema.META_FREQUENCY: COL_FREQUENCY,
  results_schema.META_WORKFLOW: COL_WORKFLOW,
  results_schema.META_TIMESTAMP: COL_TIMESTAMP,
}

# Preferred display order for the reserved dimension columns
RESERVED_DIMENSION_ORDER = [COL_SOURCE, COL_TYPE, COL_TARGET, COL_FREQUENCY, COL_ARCHITECTURE, COL_WORKFLOW, COL_CONFIGURATION]

# Result type display names ("type" meta values)
TYPE_DISPLAY_NAMES = {
  results_schema.TYPE_FMAX: "Fmax",
  results_schema.TYPE_CUSTOM_FREQ: "Custom Freq",
  results_schema.TYPE_WORKFLOW: "Workflow",
}

# Frequency value used for fmax synthesis rows (no fixed frequency)
FMAX_FREQUENCY_VALUE = "fmax"

# Value used to represent missing dimension values in filters
MISSING_VALUE = "None"


def type_display_name(type_value):
  """Display name of a result type meta value (e.g. "fmax_synthesis" -> "Fmax")."""
  return TYPE_DISPLAY_NAMES.get(str(type_value), str(type_value))


def is_info_column(column):
  """Informational columns are kept for hover/CSV but are not dimensions."""
  return str(column).startswith("_") or column == COL_TIMESTAMP


def sort_key(value):
  """
  Sort key for mixed dimension values: numbers first in numeric order, then
  strings in natural order (embedded numbers compared numerically, so
  "2MHz" < "10MHz" and "cfg2" < "cfg10").
  """
  text = str(value)
  try:
    return (0, float(text), "")
  except ValueError:
    parts = re.split(r"(\d+)", text.lower())
    natural = tuple((int(part), "") if part.isdigit() else (float("inf"), part) for part in parts if part != "")
    return (1, 0.0, natural)


def sort_values(values):
  """Sort a list of mixed dimension values (numeric-aware)."""
  return sorted(values, key=sort_key)


def unit_to_html(unit):
  """Render "^n" as superscript and "_n" as subscript in a unit string."""
  if not unit:
    return ""
  html_unit = re.sub(r"\^(-?\d+)", r"<sup>\1</sup>", str(unit))
  return re.sub(r"\_(-?\d+)", r"<sub>\1</sub>", html_unit)


def metric_display_name(metric):
  """Display name of a metric column (underscores read as spaces)."""
  return str(metric).replace("_", " ")


def axis_title(metric, units):
  """Axis title of a metric: display name plus its unit if known."""
  title = metric_display_name(metric)
  unit = unit_to_html(units.get(metric, "")) if units else ""
  if unit != "":
    title += " (" + unit + ")"
  return title


def clean_configuration_name(configuration, dissociated_dimension):
  """
  Remove the "+dimension/value" (or legacy "+dimension_value") segment of a
  configuration name when that dimension is dissociated into separate traces.
  """
  if not dissociated_dimension:
    return configuration
  parts = str(configuration).split("+")
  kept = [part for part in parts if not (part.startswith(dissociated_dimension + "/") or part.startswith(dissociated_dimension + "_"))]
  return "+".join(kept)

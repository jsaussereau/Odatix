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
Selection and discovery helpers over the result store DataFrame.
"""

import pandas as pd

import odatix.explorer.core.schema as schema


def dimension_values(df, dimension):
  """Distinct values of a dimension in a DataFrame, sorted (missing -> "None")."""
  if dimension not in df.columns:
    return []
  values = df[dimension].fillna(schema.MISSING_VALUE).astype(str).unique()
  return schema.sort_values(values)


def select_dataframe(store, sources=None, filters=None):
  """
  Select rows of the store DataFrame.

  Args:
      store: the ResultStore.
      sources (list | None): source names to keep (None = all).
      filters (dict | None): {dimension: list of allowed values (as strings)}.
          Dimensions absent from the DataFrame are ignored. Missing values
          match "None".

  Returns:
      pd.DataFrame: the filtered selection (a copy-on-filter view).
  """
  df = store.dataframe()
  if df.empty:
    return df

  if sources is not None:
    df = df[df[schema.COL_SOURCE].isin(sources)]

  if filters:
    for dimension, allowed in filters.items():
      if dimension not in df.columns or allowed is None:
        continue
      column = df[dimension].fillna(schema.MISSING_VALUE).astype(str)
      df = df[column.isin([str(value) for value in allowed])]

  # Drop columns that are empty on this selection
  if not df.empty:
    df = df.dropna(axis=1, how="all")

  return df


def discover(df, store, sources=None):
  """
  Discover the dimensions (with their values) and metrics of a selection.

  Returns:
      tuple: (dimensions dict {name: [values]}, metrics list)
  """
  dimensions = {}
  for dimension in store.dimension_columns(sources):
    if dimension in df.columns:
      values = dimension_values(df, dimension)
      if len(values) > 0:
        dimensions[dimension] = values

  metrics = []
  for metric in store.metric_columns(sources):
    if metric in df.columns and pd.to_numeric(df[metric], errors="coerce").notna().any():
      metrics.append(metric)

  return dimensions, metrics

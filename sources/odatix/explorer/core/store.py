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
In-memory result store of Odatix Explorer, with hot reload.

The store watches a directory of result files. poll() rescans the directory
(cheap mtime/size comparison, throttled) and reloads only the files that
changed; the tidy DataFrame is then rebuilt and the store version is bumped,
which lets the UI refresh only when something actually changed.

The store is a process-wide singleton (STORE) shared by all Dash callbacks;
loads happen under a lock and the DataFrame is swapped atomically (never
mutated in place), so readers always get a consistent snapshot.
"""

import os
import time
import threading

import pandas as pd

import odatix.lib.results_schema as results_schema
import odatix.explorer.core.schema as schema

DEFAULT_PREFIX = "results_"
MIN_SCAN_INTERVAL = 1.0  # seconds between two directory scans


class SourceInfo:
  """State of one result file."""

  def __init__(self, name, path):
    self.name = name          # display name (file name without prefix/extension)
    self.path = path
    self.mtime = None
    self.size = None
    self.schema = results_schema.FORMAT_UNKNOWN
    self.record_count = 0
    self.error = None         # parse error message, or None


class ResultStore:
  def __init__(self):
    self._lock = threading.RLock()
    self._result_path = None
    self._prefix = DEFAULT_PREFIX
    self._sources = {}        # display name -> SourceInfo
    self._files = {}          # display name -> ResultsFile
    self._df = pd.DataFrame()
    self._dimension_columns = {}  # display name -> list of dimension columns
    self._metric_columns = {}     # display name -> list of metric columns
    self._version = 0
    self._last_scan = 0.0
    self.last_load_time = None

  ######################################
  # Configuration
  ######################################

  def configure(self, result_path, prefix=DEFAULT_PREFIX):
    """
    Point the store at a result directory. Idempotent: nothing happens if the
    path does not change; otherwise the store is reset and reloaded.
    """
    result_path = os.path.realpath(str(result_path)) if result_path else None
    with self._lock:
      if result_path == self._result_path and prefix == self._prefix:
        return False
      self._result_path = result_path
      self._prefix = prefix
      self._sources = {}
      self._files = {}
      self._df = pd.DataFrame()
      self._dimension_columns = {}
      self._metric_columns = {}
      self._last_scan = 0.0
      self.poll(force=True)
      return True

  @property
  def result_path(self):
    return self._result_path

  @property
  def version(self):
    return self._version

  ######################################
  # Hot reload
  ######################################

  def poll(self, force=False):
    """
    Rescan the result directory and reload any file that changed.

    Returns:
        bool: True if the data changed (store version was bumped).
    """
    with self._lock:
      now = time.monotonic()
      if not force and now - self._last_scan < MIN_SCAN_INTERVAL:
        return False
      self._last_scan = now

      found = self._scan_files()

      changed = False

      # Remove sources whose file disappeared
      for name in list(self._sources):
        if name not in found:
          del self._sources[name]
          self._files.pop(name, None)
          self._dimension_columns.pop(name, None)
          self._metric_columns.pop(name, None)
          changed = True

      # Load new files and reload changed ones
      for name, (path, mtime, size) in found.items():
        source = self._sources.get(name)
        if source is not None and source.mtime == mtime and source.size == size:
          continue
        if source is None:
          source = SourceInfo(name, path)
          self._sources[name] = source
        source.path = path
        source.mtime = mtime
        source.size = size
        self._load_source(source)
        changed = True

      if changed:
        self._rebuild()
        self._version += 1
        self.last_load_time = time.time()

      return changed

  def mark_loaded(self):
    """
    Record the current time as the last load time even when nothing changed on
    disk. Used for a manual reload (the "Reload" button), so the displayed
    timestamp reflects the user's explicit refresh; a background poll that finds
    no change leaves the timestamp untouched.
    """
    with self._lock:
      self.last_load_time = time.time()

  def _scan_files(self):
    """List result files in the configured directory as {name: (path, mtime, size)}."""
    found = {}
    if self._result_path is None or not os.path.isdir(self._result_path):
      return found
    try:
      entries = sorted(os.scandir(self._result_path), key=lambda entry: entry.name)
    except OSError:
      return found
    for entry in entries:
      if not entry.is_file():
        continue
      if not entry.name.endswith((".yml", ".yaml")):
        continue
      if self._prefix and not entry.name.startswith(self._prefix):
        continue
      name = entry.name[len(self._prefix):] if self._prefix else entry.name
      name = os.path.splitext(name)[0]
      try:
        stat = entry.stat()
      except OSError:
        continue
      found[name] = (entry.path, stat.st_mtime, stat.st_size)
    return found

  def _load_source(self, source):
    """(Re)load one result file. On failure, keep the last good data and flag the error."""
    try:
      results_file = results_schema.load_results_file(source.path)
    except Exception as e:
      source.error = str(e)
      return
    source.error = None
    source.schema = results_file.schema_detected
    source.record_count = len(results_file.records)
    if results_file.schema_detected == results_schema.FORMAT_UNKNOWN and not results_file.records:
      source.error = "unrecognized results format"
    self._files[source.name] = results_file

  ######################################
  # DataFrame construction
  ######################################

  def _rebuild(self):
    rows = []
    dimension_columns = {}
    metric_columns = {}

    for name in self._files:
      results_file = self._files[name]
      source_dimensions = [schema.COL_SOURCE]
      source_metrics = []
      for record in results_file.records:
        meta = record.get("meta", {})
        metrics = record.get("metrics", {})
        row = {schema.COL_SOURCE: name}

        for key, value in meta.items():
          key = str(key)
          if key.startswith("_"):
            row[key] = value
            continue
          column = schema.RESERVED_META_COLUMNS.get(key, key)
          if column == schema.COL_TYPE:
            value = schema.type_display_name(value)
          if column == schema.COL_FREQUENCY:
            row[column] = value  # keep numeric for axis use
          else:
            row[column] = str(value)
          if column != schema.COL_TIMESTAMP and column not in source_dimensions:
            source_dimensions.append(column)

        # Fmax rows have no fixed frequency: use a sentinel dimension value
        if schema.COL_FREQUENCY not in row and str(meta.get(results_schema.META_TYPE, "")) == results_schema.TYPE_FMAX:
          row[schema.COL_FREQUENCY] = schema.FMAX_FREQUENCY_VALUE
          if schema.COL_FREQUENCY not in source_dimensions:
            source_dimensions.append(schema.COL_FREQUENCY)

        for key, value in metrics.items():
          key = str(key)
          row[key] = value
          if key not in source_metrics:
            source_metrics.append(key)

        rows.append(row)

      dimension_columns[name] = source_dimensions
      metric_columns[name] = source_metrics

    df = pd.DataFrame(rows)
    if not df.empty:
      ordered = self._ordered_columns(df.columns, dimension_columns, metric_columns)
      df = df[ordered]

    self._df = df
    self._dimension_columns = dimension_columns
    self._metric_columns = metric_columns

  def _ordered_columns(self, columns, dimension_columns, metric_columns):
    """Stable column order: reserved dimensions, free dimensions, metrics, info."""
    columns = list(columns)
    ordered = [column for column in schema.RESERVED_DIMENSION_ORDER if column in columns]
    for source_dimensions in dimension_columns.values():
      ordered += [column for column in source_dimensions if column not in ordered and column in columns]
    for source_metrics in metric_columns.values():
      ordered += [column for column in source_metrics if column not in ordered and column in columns]
    ordered += [column for column in columns if column not in ordered]
    return ordered

  ######################################
  # Accessors (return consistent snapshots)
  ######################################

  def sources(self):
    """List of SourceInfo, sorted by name."""
    with self._lock:
      return [self._sources[name] for name in sorted(self._sources)]

  def source_names(self):
    with self._lock:
      return sorted(self._sources)

  def dataframe(self):
    """The full tidy DataFrame (all sources). Never mutated in place."""
    return self._df

  def dimension_columns(self, sources=None):
    """Dimension columns of the given sources (all sources if None), in display order."""
    with self._lock:
      selected = self._selected(sources, self._dimension_columns)
      reserved = [column for column in schema.RESERVED_DIMENSION_ORDER if any(column in columns for columns in selected)]
      # Show parameter domains (the non-reserved dimensions) before Configuration
      split = reserved.index(schema.COL_CONFIGURATION) if schema.COL_CONFIGURATION in reserved else len(reserved)
      ordered = reserved[:split]
      for columns in selected:
        ordered += [column for column in columns if column not in reserved and column not in ordered]
      ordered += reserved[split:]
      return ordered

  def metric_columns(self, sources=None):
    """Metric columns of the given sources (all sources if None), in display order."""
    with self._lock:
      ordered = []
      for columns in self._selected(sources, self._metric_columns):
        ordered += [column for column in columns if column not in ordered]
      return ordered

  def _selected(self, sources, per_source):
    if sources is None:
      return [per_source[name] for name in sorted(per_source)]
    return [per_source[name] for name in sources if name in per_source]

  def units(self, sources=None):
    """Merged units of the given sources (all sources if None)."""
    with self._lock:
      merged = {}
      names = sorted(self._files) if sources is None else [name for name in sources if name in self._files]
      for name in names:
        merged.update(self._files[name].units)
      return merged


STORE = ResultStore()

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
Saved explorer views: the whole display state (chart kind, sources, axes,
style, filters, ...) serialized to a JSON file so it can be restored later or
shared with other users.

View files live in "<result directory>/explorer_views/*.json" and are fully
self-contained (schema version, metadata, an embedded thumbnail), so sharing a
view is just copying its file next to the result files of another user.

Because the data a view is restored against may differ from the data it was
saved with (other result files, renamed metrics, ...), loading never trusts
the file: sanitize_view() checks every field against the live store, repairs
what it can and reports what was dropped.
"""

import datetime
import json
import os
import re

import pandas as pd

import odatix.explorer.core.query as query
import odatix.explorer.core.schema as schema
import odatix.explorer.charts.palettes as palettes
import odatix.explorer.charts.plot_themes as plot_themes
from odatix.explorer.charts.spec import (
  CAPABILITIES,
  KIND_LABELS,
  NONE_VALUE,
  OVERVIEW_LAYOUTS,
  TOGGLE_LABELS,
)

VIEWS_DIRNAME = "explorer_views"
VIEW_SCHEMA_KEY = "odatix_explorer_view"
VIEW_SCHEMA_VERSION = 1

CONTROL_KEYS = ("x", "y", "z", "color_by", "symbol_by", "legend_group_by", "dissociate")
EXPORT_FORMATS = ("svg", "png", "jpeg", "webp")
EXPORT_BACKGROUNDS = ("transparent", "white", "theme")
OVERVIEW_CHART_TYPES = ("lines", "columns", "radar")

# Thumbnail geometry (SVG viewBox units) and size caps
THUMB_WIDTH = 100
THUMB_HEIGHT = 44
THUMB_MAX_SERIES = 4
THUMB_MAX_POINTS = 16
THUMB_MAX_BARS = 12
THUMB_TABLE_MAX_COLS = 5
THUMB_TABLE_MAX_ROWS = 4


######################################
# File access
######################################


def views_dir(result_path):
  """Directory holding the saved view files, or None when unconfigured."""
  if not result_path:
    return None
  return os.path.join(str(result_path), VIEWS_DIRNAME)


def slugify(name):
  """Safe file name from a user-chosen view name (also kills path traversal)."""
  name = re.sub(r"[^\w\-. ]+", "", str(name or "")).strip().replace(" ", "_")
  return name.strip("._")


def list_views(result_path):
  """
  List saved views as dicts (the parsed files plus "name" and "mtime"),
  newest first. Unreadable files are skipped.
  """
  directory = views_dir(result_path)
  if directory is None or not os.path.isdir(directory):
    return []
  views = []
  for entry in sorted(os.scandir(directory), key=lambda entry: entry.name):
    if not entry.is_file() or not entry.name.endswith(".json"):
      continue
    try:
      with open(entry.path, "r") as f:
        view = json.load(f)
      if not isinstance(view, dict) or VIEW_SCHEMA_KEY not in view:
        continue
      view["name"] = os.path.splitext(entry.name)[0]
      view["mtime"] = entry.stat().st_mtime
      views.append(view)
    except (OSError, ValueError):
      continue
  views.sort(key=lambda view: view.get("mtime", 0), reverse=True)
  return views


def save_view(result_path, name, view):
  """Write a view file; returns the slugged view name. Raises on I/O errors."""
  slug = slugify(name)
  if not slug:
    raise ValueError("invalid view name")
  directory = views_dir(result_path)
  if directory is None:
    raise ValueError("no result directory configured")
  os.makedirs(directory, exist_ok=True)
  view = dict(view)
  view[VIEW_SCHEMA_KEY] = VIEW_SCHEMA_VERSION
  view["created"] = datetime.datetime.now().isoformat(timespec="seconds")
  with open(os.path.join(directory, slug + ".json"), "w") as f:
    json.dump(view, f, indent=1)
  return slug


def load_view(result_path, name):
  """Read one view file by name. Raises ValueError on a missing or bad file."""
  directory = views_dir(result_path)
  slug = slugify(name)
  if directory is None or not slug:
    raise ValueError("unknown view " + str(name))
  path = os.path.join(directory, slug + ".json")
  try:
    with open(path, "r") as f:
      view = json.load(f)
  except OSError:
    raise ValueError('view file not found: "' + slug + '.json"')
  except ValueError:
    raise ValueError('"' + slug + '.json" is not a valid JSON file')
  if not isinstance(view, dict):
    raise ValueError('"' + slug + '.json" is not an explorer view file')
  view.setdefault("name", slug)
  return view


######################################
# Validation against the live data
######################################


def sanitize_view(view, store):
  """
  Check a loaded view against the current store content, repairing anything
  the data cannot honor (missing sources, unknown metrics, ...).

  Returns:
      tuple: (payload dict ready for the restore callbacks, list of warnings)
  """
  warnings = []
  schema_version = view.get(VIEW_SCHEMA_KEY)
  if schema_version != VIEW_SCHEMA_VERSION:
    raise ValueError("unsupported view file version: " + str(schema_version))

  kind = view.get("kind")
  if kind not in CAPABILITIES:
    raise ValueError("unknown chart kind: " + str(kind))

  # --- Sources ---
  available = store.source_names()
  saved_sources = [str(source) for source in view.get("sources") or []]
  sources = [source for source in saved_sources if source in available]
  missing = [source for source in saved_sources if source not in available]
  if missing:
    warnings.append("Missing data sources: " + ", ".join(missing))
  if not sources:
    sources = available[:1]
    if saved_sources:
      warnings.append("None of the saved sources exist here; falling back to the first available source")

  df = query.select_dataframe(store, sources=sources)
  dimensions, metrics = query.discover(df, store, sources)

  # --- Axis and style controls ---
  # Dropped values are repaired downstream by the generic defaults
  # (resolve_defaults), exactly as for stale session state.
  saved_controls = view.get("controls") or {}
  axis_choices = set(metrics) | set(dimensions)  # x always accepts both
  metric_only = set(metrics)
  dim_choices = set(dimensions) | {NONE_VALUE}

  allowed = {
    "x": axis_choices,
    "y": metric_only if kind not in ("scatter", "scatter3d") else axis_choices,
    "z": metric_only if kind not in ("scatter", "scatter3d") else axis_choices,
    "color_by": dim_choices,
    "symbol_by": dim_choices,
    "legend_group_by": dim_choices,
    "dissociate": dim_choices,
  }
  controls = {}
  for key in CONTROL_KEYS:
    if key not in saved_controls or saved_controls[key] is None:
      continue
    value = str(saved_controls[key])
    if value in allowed[key]:
      controls[key] = value
    else:
      warnings.append('"' + value + '" (' + key.replace("_", " ") + ") does not exist in this data")

  # --- Filters (saved as hidden values per dimension) ---
  filter_state = {}
  for dimension, hidden in (view.get("filters") or {}).items():
    dimension = str(dimension)
    if dimension not in dimensions:
      warnings.append('Filter dimension "' + dimension + '" does not exist in this data')
      continue
    known = [str(value) for value in hidden or [] if str(value) in dimensions[dimension]]
    unknown = [str(value) for value in hidden or [] if str(value) not in dimensions[dimension]]
    if unknown:
      warnings.append('Filtered-out values missing from "' + dimension + '": ' + ", ".join(unknown))
    if known:
      filter_state[dimension] = {value: False for value in known}

  # --- Style / display / export ---
  palette = view.get("palette")
  if palette not in palettes.PALETTES:
    if palette is not None:
      warnings.append('Unknown palette "' + str(palette) + '"; using the default')
    palette = palettes.DEFAULT_PALETTE

  plot_theme = view.get("plot_theme")
  if plot_theme not in plot_themes.plot_theme_names():
    if plot_theme is not None:
      warnings.append('Unknown plot theme "' + str(plot_theme) + '"; using the default')
    plot_theme = plot_themes.DEFAULT_PLOT_THEME

  known_toggles = set(TOGGLE_LABELS) | {"stable_index"}
  toggles = [str(toggle) for toggle in view.get("toggles") or [] if str(toggle) in known_toggles]

  overview = view.get("overview") or {}
  overview_chart_type = overview.get("chart_type")
  if overview_chart_type not in OVERVIEW_CHART_TYPES:
    overview_chart_type = "lines"
  overview_layout = overview.get("layout")
  if overview_layout not in OVERVIEW_LAYOUTS:
    overview_layout = "default"

  export = view.get("export") or {}
  dl_format = export.get("format") if export.get("format") in EXPORT_FORMATS else "svg"
  dl_background = export.get("background") if export.get("background") in EXPORT_BACKGROUNDS else "transparent"

  payload = {
    "name": view.get("name"),
    "kind": kind,
    "sources": sources,
    "controls": controls,
    "filter_state": filter_state,
    "palette": palette,
    "plot_theme": plot_theme,
    "toggles": toggles,
    "overview_chart_type": overview_chart_type,
    "overview_layout": overview_layout,
    "dl_format": dl_format,
    "dl_background": dl_background,
  }
  return payload, warnings


def filters_to_hidden(filter_state, dimensions):
  """
  Convert the session filter state ({dim: {value: bool}}) into the saved form:
  {dim: [hidden values]}, restricted to what currently exists in the data so
  the file stays clean and shareable.
  """
  hidden = {}
  for dimension, values in (dimensions or {}).items():
    remembered = (filter_state or {}).get(dimension, {})
    off = [value for value in values if remembered.get(value, True) is False]
    if off:
      hidden[dimension] = off
  return hidden


######################################
# Thumbnails
######################################


def make_table_thumbnail(df):
  """
  Sketch of a data table for the home-page card: a grid of a few rows and
  columns with a highlighted header, sized from the actual selection. Returns
  None on empty data (the card then falls back to the table pictogram).
  """
  if df is None or df.empty:
    return None
  columns = [column for column in df.columns if not schema.is_info_column(column)]
  cols = max(1, min(THUMB_TABLE_MAX_COLS, len(columns)))
  rows = max(1, min(THUMB_TABLE_MAX_ROWS, len(df)))
  return {"t": "table", "c": cols, "r": rows}


def make_thumbnail(df, kind, x, y, color_by, dimensions):
  """
  Build a tiny data sketch of the current figure for the home page cards:
  a handful of normalized polylines / dots / bars in a 100x44 viewBox,
  embedded in the view file (so it travels with it). Returns None when the
  data does not lend itself to a sketch (the card then falls back to the
  chart-kind pictogram).
  """
  if kind == "table":
    return make_table_thumbnail(df)

  if df is None or df.empty or not y or y not in df.columns:
    return None

  if color_by in df.columns and color_by in (dimensions or {}):
    values = dimensions[color_by]
    column = df[color_by].astype(str)
    groups = [(index, df[column == value]) for index, value in enumerate(values)]
    groups = [(index, sub) for index, sub in groups if not sub.empty][:THUMB_MAX_SERIES]
  else:
    groups = [(0, df)]

  scatter = kind in ("scatter", "scatter3d")
  series = []
  for color_index, sub in groups:
    y_values = pd.to_numeric(sub[y], errors="coerce")
    if scatter and x in sub.columns:
      x_values = pd.to_numeric(sub[x], errors="coerce")
    else:
      x_values = pd.Series(range(len(sub)), index=sub.index, dtype=float)
    points = [(float(px), float(py)) for px, py in zip(x_values, y_values) if pd.notna(px) and pd.notna(py)]
    if not points:
      continue
    if not scatter:
      points.sort(key=lambda point: point[0])
    step = max(1, len(points) // THUMB_MAX_POINTS)
    series.append({"c": color_index, "p": points[::step][:THUMB_MAX_POINTS]})

  if not series:
    return None

  # Normalize all series into the viewBox (y grows downwards in SVG)
  xs = [px for serie in series for px, _ in serie["p"]]
  ys = [py for serie in series for _, py in serie["p"]]
  x_min, x_max = min(xs), max(xs)
  y_min, y_max = min(ys), max(ys)
  x_span = (x_max - x_min) or 1.0
  y_span = (y_max - y_min) or 1.0
  for serie in series:
    serie["p"] = [
      [round((px - x_min) / x_span * THUMB_WIDTH), round(THUMB_HEIGHT - (py - y_min) / y_span * THUMB_HEIGHT)]
      for px, py in serie["p"]
    ]

  if kind == "columns":
    # Interleave the series' bars so multi-source views stay recognizable
    bars = []
    for offset in range(THUMB_MAX_POINTS):
      for serie in series:
        if offset < len(serie["p"]):
          bars.append([serie["c"], serie["p"][offset][1]])
    return {"t": "bars", "b": bars[:THUMB_MAX_BARS]}

  return {"t": "dots" if scatter else "lines", "s": series}


def kind_label(kind):
  return KIND_LABELS.get(kind, str(kind))

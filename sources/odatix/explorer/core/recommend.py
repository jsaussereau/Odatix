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
Recommended charts: propose ready-made views that say something about the data.

A recommendation is nothing more than a *generated view* (see core.views): the
same JSON payload a user would have saved by hand, so opening one lands on the
regular chart page with every control filled in and editable.

The engine is data-driven, not concept-driven. It measures the selection --
how much each metric varies, how many values each dimension takes, how metrics
correlate with one another -- and hands those measurements to a list of
recipes. A recipe says whether it applies, how interesting it is here, and what
view to build. Nothing is hardcoded to hardware: metric names only ever feed a
best-effort "is lower better?" guess that degrades to "unknown" silently.

Typical use::

    ctx = build_context(store, sources, filters, rule_state)
    for reco in recommend(ctx, intent={"metrics": ["Fmax"]}):
        print(reco.title, reco.why, reco.view)
"""

import math
import re

import pandas as pd

import odatix.explorer.core.query as query
import odatix.explorer.core.rules as rules
import odatix.explorer.core.schema as schema
import odatix.explorer.core.views as views
import odatix.explorer.charts.palettes as palettes
import odatix.explorer.charts.plot_themes as plot_themes
from odatix.explorer.charts.spec import DEFAULT_TOGGLES, NONE_VALUE

# Default number of recommendations returned to the gallery.
DEFAULT_LIMIT = 12

# A dimension is a good color/symbol carrier around this many values: enough to
# compare, few enough to still tell the traces apart in a legend.
IDEAL_CARDINALITY = 4
MAX_USEFUL_CARDINALITY = 12

# Below this coefficient of variation a metric is flat enough to be boring.
FLAT_CV = 0.02

# A metric measured on less than this share of the selection makes a sparse,
# misleading chart.
MIN_COVERAGE = 0.25

# Two metrics need at least this many rows holding *both* before they can be
# put on the same scatter: metrics coming from different result types (an fmax
# search and a fixed-frequency synthesis, say) coexist in the data without ever
# sharing a row, and plotting one against the other draws nothing.
MIN_PAIRED_ROWS = 8

# Dimensions describing how a result was produced rather than what was
# explored. They still make legitimate axes, but a chart split by them says
# less than one split by an actual design parameter, so they are ranked below.
_STRUCTURAL_WEIGHT = 0.45
_STRUCTURAL_DIMENSIONS = (
  schema.COL_SOURCE, schema.COL_TYPE, schema.COL_STEP, schema.COL_STEP_SCOPE, schema.COL_TIMESTAMP,
)

# How much a candidate is held back for each higher-ranked chart already built
# on the same metric. A gallery repeating one metric four ways is less useful
# than one covering four metrics, but a second reading of a genuinely dominant
# metric is still worth offering -- hence a penalty, not a filter.
DIVERSITY_PENALTY = 0.85

# Dimensions that say *what design* a row is about. A chart insisting on a
# parameter that only some architectures declare must not drag the others in:
# they would show up in the filter panel with nothing to draw.
_SCOPE_DIMENSIONS = (schema.COL_ARCHITECTURE, schema.COL_WORKFLOW)

# How many values a description spells out before it just counts them.
NAMED_VALUES = 3

# A cross-source chart is only honest when the sources really ran the same
# thing: at least this many identical (architecture, configuration) designs.
MIN_SHARED_DESIGNS = 2

# Sources measured on their own before the gallery stops widening. A workspace
# with twenty result files would otherwise spend its time re-measuring.
MAX_SCOPE_SOURCES = 6

# How many times the gallery may draw the same chart shape (same kind, same
# axes) on different scopes. Once as a comparison and once on its own source is
# informative; six times is the same chart six times.
MAX_SHAPE_REPEATS = 2

# What a chart comparing sources is worth over the same chart inside a single
# source: it answers a question no per-source chart can.
CROSS_SOURCE_BONUS = 0.2

# How strongly the user's stated interest reorders the results. High enough to
# float a named metric to the top, low enough that a truly flat metric stays
# down where it belongs.
INTENT_BOOST = 1.6

MAXIMIZE = 1
MINIMIZE = -1
UNKNOWN = 0

# Best-effort direction guess. These are *tokens* looked up in the metric name,
# not a closed list of metrics: an unrecognized name is UNKNOWN, which every
# recipe must tolerate.
_LOWER_IS_BETTER_TOKENS = (
  "area", "power", "energy", "cost", "delay", "latency", "slack_violation",
  "count", "cells", "wirelength", "leakage", "error", "loss", "size",
)
_HIGHER_IS_BETTER_TOKENS = (
  "fmax", "freq", "frequency", "throughput", "bandwidth", "speed", "score",
  "accuracy", "efficiency", "margin", "slack",
)

# Units that are unambiguous enough to override the name-token guess.
_UNIT_DIRECTIONS = {
  "w": MINIMIZE, "mw": MINIMIZE, "uw": MINIMIZE, "nw": MINIMIZE,
  "j": MINIMIZE, "mj": MINIMIZE, "uj": MINIMIZE, "nj": MINIMIZE,
  "s": MINIMIZE, "ms": MINIMIZE, "us": MINIMIZE, "ns": MINIMIZE, "ps": MINIMIZE,
  "hz": MAXIMIZE, "khz": MAXIMIZE, "mhz": MAXIMIZE, "ghz": MAXIMIZE,
}


def metric_direction(metric, units=None):
  """
  Guess whether a metric is better low (MINIMIZE), better high (MAXIMIZE) or
  cannot be told (UNKNOWN).

  The unit wins when it is unambiguous (a duration is always better short), the
  name tokens decide otherwise. Callers must treat UNKNOWN as "no opinion" and
  never as a default direction.
  """
  unit = str((units or {}).get(metric, "")).strip().lower()
  if unit in _UNIT_DIRECTIONS:
    return _UNIT_DIRECTIONS[unit]

  name = str(metric).lower()
  # Longest match wins so "slack_violation" is not read as "slack".
  best = (0, UNKNOWN)
  for token in _HIGHER_IS_BETTER_TOKENS:
    if token in name and len(token) > best[0]:
      best = (len(token), MAXIMIZE)
  for token in _LOWER_IS_BETTER_TOKENS:
    if token in name and len(token) > best[0]:
      best = (len(token), MINIMIZE)
  return best[1]


######################################
# Measuring the selection
######################################


class MetricStat(object):
  """What is known about one metric over the current selection."""

  def __init__(self, metric, series, direction):
    self.metric = metric
    self.direction = direction
    numeric = pd.to_numeric(series, errors="coerce")
    self.count = int(numeric.notna().sum())
    self.coverage = self.count / float(len(series)) if len(series) else 0.0
    self.distinct = int(numeric.nunique())
    if self.count:
      self.min = float(numeric.min())
      self.max = float(numeric.max())
      mean = float(numeric.mean())
      std = float(numeric.std()) if self.count > 1 else 0.0
      # Coefficient of variation: scale-free, so a power in watts and a LUT
      # count are comparable. Guard the zero-mean case.
      self.cv = abs(std / mean) if mean else (1.0 if std else 0.0)
      self.ratio = (self.max / self.min) if self.min > 0 else None
    else:
      self.min = self.max = self.cv = None
      self.ratio = None

  @property
  def is_flat(self):
    """True when the metric barely moves: charting it teaches nothing."""
    return self.distinct < 2 or (self.cv is not None and self.cv < FLAT_CV)

  @property
  def interest(self):
    """0..1 -- how much this metric is worth putting on an axis."""
    if not self.count or self.is_flat or self.coverage < MIN_COVERAGE:
      return 0.0
    # Saturating on the spread: a 2x spread is already plenty, and a wild
    # outlier must not outrank a metric that varies meaningfully everywhere.
    spread = min(1.0, math.log1p(self.cv * 10) / math.log1p(10))
    return 0.35 + 0.5 * spread + 0.15 * min(1.0, self.coverage)


class DimensionStat(object):
  """What is known about one dimension over the current selection."""

  def __init__(self, dimension, values):
    self.dimension = dimension
    # Missing values are a marker, not a value: they must not make an
    # otherwise numeric parameter look categorical, nor inflate cardinality.
    self.values = [value for value in values if str(value) != schema.MISSING_VALUE]
    self.cardinality = len(self.values)
    self.numbers = _ordinal_values(self.values)
    self.numeric = self.numbers is not None
    self.structural = dimension in _STRUCTURAL_DIMENSIONS

  @property
  def interest(self):
    """0..1 -- how well this dimension separates traces without cluttering."""
    if self.cardinality < 2:
      return 0.0
    if self.cardinality > MAX_USEFUL_CARDINALITY:
      # Still usable (as an x axis), just never a good color carrier.
      score = 0.2
    else:
      # Peaks at IDEAL_CARDINALITY, decays gently on both sides.
      distance = abs(self.cardinality - IDEAL_CARDINALITY)
      score = max(0.3, 1.0 - 0.12 * distance)
    return score * (_STRUCTURAL_WEIGHT if self.structural else 1.0)


_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def _ordinal_values(values):
  """
  The numbers behind a dimension's values, or None when it is not ordinal.

  A parameter is ordinal when every value carries exactly one number and they
  are all distinct, so "8taps" < "16taps" and "4" < "12" both scale, while
  "xc7a100t-csg324-1" does not.
  """
  numbers = []
  for value in values:
    found = _NUMBER_PATTERN.findall(str(value))
    if len(found) != 1:
      return None
    numbers.append(float(found[0]))
  if len(numbers) < 2 or len(set(numbers)) != len(numbers):
    return None
  return numbers


class Context(object):
  """
  Everything the recipes are allowed to look at: the current selection, its
  dimensions and metrics, and the measurements taken over them.
  """

  def __init__(self, store, sources, df, dimensions, metrics, units,
               filters=None, rule_state=None, base_dimensions=None, intent=None):
    self.store = store
    self.sources = list(sources or [])
    self.df = df
    self.dimensions = dimensions
    # Dimensions before the filters were applied: a filtered-out value is
    # absent from ``dimensions``, yet it is exactly what a view must record as
    # hidden.
    self.base_dimensions = base_dimensions if base_dimensions is not None else dimensions
    self.intent = intent or {}
    self.metrics = list(metrics)
    self.units = units or {}
    self.filters = filters or {}
    self.rule_state = rule_state
    # Set by the gallery: the dimension whose values this selection exists to
    # compare (Source, when the scope holds designs several tools both ran),
    # and a short human name for the scope, quoted in the descriptions.
    self.compare_by = None
    self.label = ""
    self.rows = len(df)
    self.metric_stats = dict(
      (metric, MetricStat(metric, df[metric], metric_direction(metric, self.units)))
      for metric in self.metrics if metric in df.columns
    )
    self.dimension_stats = dict(
      (dimension, DimensionStat(dimension, values)) for dimension, values in dimensions.items()
    )
    self._correlations = None

  ######################################
  # Ranked shortlists the recipes build on
  ######################################

  def _preference(self, name, key):
    """How much the user's stated interest lifts one metric or dimension in the
    shortlists. Named things come first, so a recipe actually builds on them
    instead of merely being re-ranked afterwards."""
    return 1.0 if str(name) in set(str(item) for item in (self.intent.get(key) or [])) else 0.0

  def ranked_metrics(self, direction=None, minimum=0.0):
    """Metrics worth charting, most interesting first, optionally of one direction."""
    candidates = [
      stat for stat in self.metric_stats.values()
      if stat.interest > minimum and (direction is None or stat.direction == direction)
    ]
    candidates.sort(key=lambda stat: (-self._preference(stat.metric, "metrics"), -stat.interest, stat.metric))
    return [stat.metric for stat in candidates]

  def ranked_dimensions(self, numeric=None, minimum=0.0, exclude=()):
    """Dimensions worth splitting on, most interesting first."""
    candidates = [
      stat for stat in self.dimension_stats.values()
      if stat.interest > minimum and stat.dimension not in exclude
      and (numeric is None or stat.numeric == numeric)
    ]
    candidates.sort(key=lambda stat: (-self._preference(stat.dimension, "dimensions"), -stat.interest, stat.dimension))
    return [stat.dimension for stat in candidates]

  def color_candidates(self, exclude=(), minimum=0.25):
    """Dimensions worth coloring by, the comparison axis first when there is one.

    A scope built to compare tools is pointless if the chart colors by
    something else: the whole point is one trace per tool.
    """
    ranked = self.ranked_dimensions(minimum=minimum, exclude=exclude)
    if self.compare_by and self.compare_by not in exclude and self.compare_by in self.dimensions:
      ranked = [self.compare_by] + [dimension for dimension in ranked if dimension != self.compare_by]
    return ranked

  def supporting_rows(self, requires=(), metric=None):
    """Mask of the rows that actually carry every named dimension and metric."""
    mask = pd.Series(True, index=self.df.index)
    for dimension in requires:
      if dimension in self.df.columns:
        column = self.df[dimension].fillna(schema.MISSING_VALUE).astype(str)
        mask = mask & (column != schema.MISSING_VALUE) & (column != "")
    if metric and metric in self.df.columns:
      mask = mask & pd.to_numeric(self.df[metric], errors="coerce").notna()
    return mask

  def restrict_to(self, requires=(), metric=None):
    """
    Which architectures and workflows a chart should keep once it insists on
    those dimensions and that metric.

    A parameter domain rarely spans the whole workspace: charting it while
    every architecture stays checked leaves the user unchecking the ones that
    were never concerned in the first place.
    """
    mask = self.supporting_rows(requires, metric)
    if not mask.any():
      return {}
    restrict = {}
    for dimension in _SCOPE_DIMENSIONS:
      if dimension not in self.dimensions or dimension not in self.df.columns:
        continue
      present = set(self.df.loc[mask, dimension].fillna(schema.MISSING_VALUE).astype(str))
      kept = [value for value in self.dimensions[dimension] if str(value) in present]
      if kept and len(kept) < len(self.dimensions[dimension]):
        restrict[dimension] = kept
    return restrict

  def paired_rows(self, left, right):
    """How many rows hold a value for both metrics -- i.e. how many points a
    scatter of one against the other would actually draw."""
    if left not in self.df.columns or right not in self.df.columns:
      return 0
    both = self.df[[left, right]].apply(pd.to_numeric, errors="coerce")
    return int(both.notna().all(axis=1).sum())

  def measured_values(self, dimension, metric):
    """
    The values of a dimension for which a metric was actually measured.

    A dimension and a metric can perfectly well coexist in the selection
    without ever meeting on a row -- a simulation parameter and a synthesis
    metric, say -- and a chart crossing them would come out empty.
    """
    if dimension not in self.df.columns or metric not in self.df.columns:
      return []
    measured = self.df[pd.to_numeric(self.df[metric], errors="coerce").notna()]
    if measured.empty:
      return []
    values = set(measured[dimension].fillna(schema.MISSING_VALUE).astype(str))
    return [value for value in self.dimensions.get(dimension, []) if str(value) in values]

  def correlation(self, left, right):
    """
    Pearson correlation between two metrics over the rows where both exist,
    or None when they never co-occur often enough to mean anything.
    """
    if self._correlations is None:
      usable = [metric for metric, stat in self.metric_stats.items() if stat.count > 2]
      numeric = self.df[usable].apply(pd.to_numeric, errors="coerce") if usable else pd.DataFrame()
      self._correlations = numeric.corr() if not numeric.empty else pd.DataFrame()
    table = self._correlations
    if left not in table.columns or right not in table.columns:
      return None
    value = table.at[left, right]
    return None if pd.isna(value) else float(value)


def build_context(store, sources=None, filters=None, rule_state=None):
  """Measure the current selection, ready to be handed to ``recommend``."""
  sources = list(sources) if sources else store.source_names()
  df = query.select_dataframe(store, sources=sources, filters=filters, rule_state=rule_state)
  dimensions, metrics = query.discover(df, store, sources)

  if filters or rule_state:
    base_df = query.select_dataframe(store, sources=sources)
    base_dimensions, _ = query.discover(base_df, store, sources)
  else:
    base_dimensions = dimensions

  return Context(
    store, sources, df, dimensions, metrics, store.units(sources),
    filters=filters, rule_state=rule_state, base_dimensions=base_dimensions,
  )


######################################
# Building the view a recommendation opens
######################################


def make_view(ctx, kind, controls=None, toggles=None, name=None, description="", restrict=None):
  """
  Assemble a view payload identical in shape to a hand-saved one, so it can go
  straight through ``views.sanitize_view`` and the restore callbacks.

  The current filters and rules are carried over: a recommendation describes
  what the user is looking at, never a silently widened selection. ``restrict``
  narrows it further -- typically to the architectures that declare the
  parameter being charted (see ``Context.restrict_to``).
  """
  controls = dict(controls or {})
  for key in ("x", "y", "z", "color_by", "symbol_by", "legend_group_by",
              "sort_by", "sort_x_by", "sort_x_order", "dissociate", "y_metrics"):
    controls.setdefault(key, None)

  effective = dict(ctx.filters or {})
  for dimension, allowed in (restrict or {}).items():
    current = effective.get(dimension)
    if current is None:
      effective[dimension] = list(allowed)
    else:
      kept = set(str(value) for value in allowed)
      effective[dimension] = [value for value in current if str(value) in kept]

  hidden = {}
  for dimension, allowed in effective.items():
    if dimension not in ctx.base_dimensions or allowed is None:
      continue
    kept = set(str(value) for value in allowed)
    dropped = [value for value in ctx.base_dimensions[dimension] if str(value) not in kept]
    if dropped:
      hidden[dimension] = dropped

  return {
    views.VIEW_SCHEMA_KEY: views.VIEW_SCHEMA_VERSION,
    "name": name or "",
    "description": description,
    "kind": kind,
    "sources": list(ctx.sources),
    "controls": controls,
    "filters": hidden,
    "rules": rules.normalize(ctx.rule_state),
    "palette": palettes.DEFAULT_PALETTE,
    "plot_theme": plot_themes.DEFAULT_PLOT_THEME,
    "toggles": list(toggles) if toggles is not None else list(DEFAULT_TOGGLES),
    "overview": {"chart_type": "lines", "layout": "default"},
    "export": {"format": "svg", "background": "transparent"},
    # Filled in by recommend(), which knows which chart kind to draw for it.
    "thumb": None,
  }


class Recommendation(object):
  """One proposed chart: what it is, why it is worth a look, and its view."""

  def __init__(self, recipe_id, title, why, score, view, scope=""):
    self.id = recipe_id
    self.title = title
    self.why = why
    self.score = score
    self.view = view
    # Which slice of the workspace it was measured on ("" when the gallery did
    # not split the workspace at all). Shown on the card.
    self.scope = scope

  @property
  def signature(self):
    """What makes two recommendations redundant: same chart of the same axes
    over the same slice -- the very same chart on two different tools is two
    different answers, so the sources are part of the identity."""
    controls = self.view.get("controls") or {}
    return (
      self.view.get("kind"),
      tuple(self.view.get("sources") or ()),
      controls.get("x"),
      controls.get("y"),
      controls.get("z"),
      tuple(controls.get("y_metrics") or ()),
      tuple(controls.get("color_by") or ()),
    )

  def __repr__(self):
    return "<Recommendation " + str(self.id) + " " + str(round(self.score, 3)) + " " + str(self.title) + ">"


######################################
# Recipes
######################################


class Recipe(object):
  """
  A candidate chart the engine knows how to propose.

  ``build`` returns a list of ``(title, why, score, view)`` -- empty when,
  having looked closer, the recipe has nothing to offer on this data.
  """

  def __init__(self, recipe_id, label, build):
    self.id = recipe_id
    self.label = label
    self.build = build


def _display(name):
  return schema.metric_display_name(name)


def _with_unit(ctx, metric, value, decimals=3):
  unit = str(ctx.units.get(metric, "")).strip()
  text = ("%." + str(decimals) + "g") % value
  return text + (" " + unit if unit else "")


def _join(values):
  """"alu", "alu and mult", "alu, mult and fir"."""
  if len(values) == 1:
    return values[0]
  return ", ".join(values[:-1]) + " and " + values[-1]


def _listing(values, singular, plural):
  """"architecture alu", "architectures alu and mult", "5 architectures"."""
  values = [str(value) for value in (values or []) if str(value) != schema.MISSING_VALUE]
  if not values:
    return ""
  if len(values) > NAMED_VALUES:
    return str(len(values)) + " " + plural
  return (singular if len(values) == 1 else plural) + " " + _join(values)


def _involved(ctx, restrict=None):
  """
  A sentence naming what the chart is actually measured on.

  "Fmax vs width" is true of any workspace; naming the architectures and the
  tool is what tells the user whether this particular card is about their
  current problem.
  """
  pieces = []
  for dimension, singular, plural in (
    (schema.COL_ARCHITECTURE, "architecture", "architectures"),
    (schema.COL_WORKFLOW, "workflow", "workflows"),
  ):
    values = (restrict or {}).get(dimension) or ctx.dimensions.get(dimension)
    listing = _listing(values, singular, plural)
    if listing:
      pieces.append(listing)

  if ctx.compare_by == schema.COL_SOURCE and len(ctx.sources) > 1:
    # The point of the scope is the comparison: say so rather than quoting a
    # scope name the user has no reason to recognize.
    where = " Compared across " + (
      _join(ctx.sources) if len(ctx.sources) <= NAMED_VALUES else str(len(ctx.sources)) + " sources"
    )
  elif ctx.label:
    where = " In " + ctx.label
  else:
    where = ""

  if pieces:
    return " Measured on " + " / ".join(pieces) + "." + (where + "." if where else "")
  return where + "." if where else ""


def _color_for(ctx, metric, exclude=()):
  """Dimensions that can color a chart of ``metric`` without drawing blanks."""
  return [
    dimension for dimension in ctx.color_candidates(exclude=exclude)
    if len(ctx.measured_values(dimension, metric)) >= 2
  ]


def _pareto_recipe(ctx):
  """
  Cost against performance: the trade-off chart, the one people open first.

  Needs a metric to minimize and one to maximize; the pairs whose values fight
  each other the most (most negative correlation) are the interesting ones,
  since two metrics that rise together tell you nothing about a compromise.
  One chart per worthwhile pair, so a workspace measuring area *and* power
  against Fmax gets both readings instead of an arbitrary one.
  """
  costs = ctx.ranked_metrics(direction=MINIMIZE)
  gains = ctx.ranked_metrics(direction=MAXIMIZE)
  if not costs or not gains:
    return []

  pairs = []
  for cost in costs[:5]:
    for gain in gains[:5]:
      # Metrics that never share a row cannot be plotted against each other,
      # however interesting each one is on its own.
      paired = ctx.paired_rows(cost, gain)
      if paired < MIN_PAIRED_ROWS:
        continue
      correlation = ctx.correlation(cost, gain)
      # Unknown correlation is treated as neutral rather than disqualifying:
      # sparse data still deserves a trade-off chart.
      tension = 0.5 if correlation is None else (1.0 - correlation) / 2.0
      quality = ctx.metric_stats[cost].interest * ctx.metric_stats[gain].interest
      pairs.append((0.55 + 0.3 * tension + 0.15 * quality, cost, gain, correlation, paired))
  pairs.sort(key=lambda pair: (-pair[0], pair[1], pair[2]))

  built = []
  for score, cost, gain, correlation, paired in pairs[:3]:
    restrict = ctx.restrict_to(metric=gain)
    color_by = _color_for(ctx, gain)

    why = "How much " + _display(cost) + " each point of " + _display(gain) + " costs, over " + str(paired) + " designs."
    if correlation is not None and correlation < -0.3:
      why += " They pull against each other here, so the compromise is real."
    elif correlation is not None and correlation > 0.5:
      why += " They rise together on this data, so there is little to arbitrate."
      score -= 0.15
    why += _involved(ctx, restrict)

    view = make_view(
      ctx, "scatter",
      controls={
        "x": cost, "y": gain,
        "color_by": color_by[:1],
        "symbol_by": [schema.COL_TARGET] if schema.COL_TARGET in ctx.dimensions else [],
      },
      description=why, restrict=restrict,
    )
    built.append((_display(gain) + " vs " + _display(cost), why, score, view))
  return built


def _scaling_recipe(ctx):
  """
  A metric plotted against a numeric parameter: how the design scales.

  Only worth proposing when the parameter takes enough distinct values to draw
  a trend rather than two disconnected dots. Every (parameter, metric) couple
  that meets is a separate, specific question -- "area vs width" and "power vs
  taps" are not interchangeable -- so each gets its own card.
  """
  parameters = [
    dimension for dimension in ctx.ranked_dimensions(numeric=True)
    if ctx.dimension_stats[dimension].cardinality >= 3
  ]
  # Configuration names often embed their parameter ("w8", "16bits"), which
  # makes them look ordinal. They are a fallback axis, never the preferred one:
  # a chart against the parameter itself is what says how the design scales.
  named = [dimension for dimension in parameters if dimension != schema.COL_CONFIGURATION]
  parameters = named or parameters

  metrics = ctx.ranked_metrics()
  if not parameters or not metrics:
    return []

  built = []
  for parameter in parameters[:3]:
    for metric in metrics[:4]:
      # Enough distinct x values carrying a measurement to draw a trend rather
      # than a dot.
      if len(ctx.measured_values(parameter, metric)) < 3:
        continue
      stat = ctx.metric_stats[metric]
      restrict = ctx.restrict_to(requires=(parameter,), metric=metric)

      why = "How " + _display(metric) + " evolves with " + _display(parameter) + "."
      if stat.ratio is not None and stat.ratio >= 1.5:
        why += " It spans " + ("%.1f" % stat.ratio) + "x across the selection."
      why += _involved(ctx, restrict)

      score = 0.5 + 0.3 * ctx.dimension_stats[parameter].interest + 0.2 * stat.interest
      others = _color_for(ctx, metric, exclude=(parameter,))

      view = make_view(
        ctx, "lines",
        controls={
          "x": parameter, "y": metric,
          "color_by": others[:1],
          "dissociate": [parameter],
          "sort_x_order": "natural",
        },
        description=why, restrict=restrict,
      )
      built.append((_display(metric) + " vs " + _display(parameter), why, score, view))
      if len(built) >= 4:
        return built
  return built


def _comparison_recipe(ctx):
  """
  Side-by-side bars: the same metric across the values of a dimension.

  Reads best when the compared dimension is small (one color per value) and the
  x axis carries whatever else varies.
  """
  splits = [
    dimension for dimension in ctx.color_candidates(minimum=0.3)
    if 2 <= ctx.dimension_stats[dimension].cardinality <= 8
  ]
  metrics = ctx.ranked_metrics()
  if not splits or not metrics:
    return []

  built = []
  for split in splits[:3]:
    for metric in metrics[:4]:
      # The compared dimension must hold the metric on at least two of its
      # values, otherwise the chart is a single lonely bar.
      compared = ctx.measured_values(split, metric)
      if len(compared) < 2:
        continue
      axis = [
        dimension for dimension in ctx.ranked_dimensions(exclude=(split,))
        if len(ctx.measured_values(dimension, metric)) >= 2
      ]
      if not axis:
        continue
      restrict = ctx.restrict_to(requires=(split, axis[0]), metric=metric)

      why = (_display(metric) + " compared across the " + str(len(compared)) + " values of "
             + _display(split) + ", one group per " + _display(axis[0]) + ".")
      why += _involved(ctx, restrict)
      score = 0.45 + 0.3 * ctx.dimension_stats[split].interest + 0.25 * ctx.metric_stats[metric].interest

      toggles = [toggle for toggle in DEFAULT_TOGGLES]
      if "zero_y" not in toggles:
        toggles.append("zero_y")  # bar lengths only compare honestly from zero

      view = make_view(
        ctx, "columns",
        controls={"x": axis[0], "y": metric, "color_by": [split], "sort_x_order": "y_desc"},
        toggles=toggles, description=why, restrict=restrict,
      )
      built.append((_display(metric) + " by " + _display(split), why, score, view))
      if len(built) >= 3:
        return built
  return built


def _parcoords_recipe(ctx):
  """
  Every metric at once: parallel coordinates, to read a whole design space in
  one picture. Needs enough distinct metrics to be worth the density.
  """
  metrics = ctx.ranked_metrics()
  if len(metrics) < 3:
    return []

  chosen = metrics[:5]
  why = "All " + str(len(chosen)) + " varying metrics on one picture: follow a line to read a whole design."
  restrict = ctx.restrict_to(metric=chosen[0])
  why += _involved(ctx, restrict)
  score = 0.4 + 0.1 * min(4, len(chosen))

  view = make_view(
    ctx, "parcoords",
    controls={"y_metrics": chosen, "color_by": ctx.color_candidates()[:1]},
    description=why, restrict=restrict,
  )
  return [("Design space profile", why, score, view)]


def _overview_recipe(ctx):
  """
  The grid of small charts: one per interesting metric, same x axis, to spot
  which metric is worth opening on its own.
  """
  metrics = ctx.ranked_metrics()
  if len(metrics) < 2:
    return []

  axis = [
    dimension for dimension in ctx.ranked_dimensions()
    if len(ctx.measured_values(dimension, metrics[0])) >= 2
  ]
  if not axis:
    return []

  restrict = ctx.restrict_to(requires=(axis[0],), metric=metrics[0])
  why = "One chart per metric on a shared " + _display(axis[0]) + " axis, to see at a glance where the variation is."
  why += _involved(ctx, restrict)
  score = 0.42 + 0.05 * min(4, len(metrics))

  view = make_view(
    ctx, "overview",
    controls={"x": axis[0], "color_by": ctx.color_candidates(exclude=(axis[0],))[:1]},
    description=why, restrict=restrict,
  )
  return [("Overview of every metric", why, score, view)]


#: Recipes tried, in declaration order. Adding one is adding an entry here.
#: ``build`` returns a list of ``(title, why, score, view)``: a recipe that has
#: several specific questions to ask about the data asks them all.
RECIPES = [
  Recipe("pareto", "Trade-off", _pareto_recipe),
  Recipe("scaling", "Scaling", _scaling_recipe),
  Recipe("comparison", "Comparison", _comparison_recipe),
  Recipe("parcoords", "Design space profile", _parcoords_recipe),
  Recipe("overview", "Overview", _overview_recipe),
]


######################################
# The engine
######################################


def _intent_boost(view, intent):
  """
  How much the user's stated interest lifts a candidate: the share of the
  named metrics and dimensions this chart actually puts on screen.
  """
  if not intent:
    return 1.0
  controls = view.get("controls") or {}
  used = set()
  for key, value in controls.items():
    if value is None:
      continue
    if isinstance(value, (list, tuple)):
      used.update(str(item) for item in value)
    else:
      used.add(str(value))

  wanted = [str(item) for item in (intent.get("metrics") or [])] + \
           [str(item) for item in (intent.get("dimensions") or [])]
  if not wanted:
    return 1.0
  matched = sum(1 for item in wanted if item in used)
  return 1.0 + (INTENT_BOOST - 1.0) * (matched / float(len(wanted)))


def recommend(ctx, intent=None, limit=DEFAULT_LIMIT):
  """
  Rank the recipes over a measured selection.

  Args:
      ctx (Context): from ``build_context``.
      intent (dict | None): {"metrics": [...], "dimensions": [...]} -- what the
          user said they care about. It only reweights the ranking; every
          recipe still runs, so the gallery is never empty because of it.
      limit (int): how many recommendations to return.

  Returns:
      list: Recommendation objects, best first, free of redundant duplicates.
  """
  if ctx.df.empty or not ctx.metrics:
    return []

  # The recipes read the intent through the ranked shortlists, so a metric the
  # user named is *built on*, not just promoted after the fact.
  ctx.intent = intent or {}

  candidates = []
  for recipe in RECIPES:
    try:
      built = recipe.build(ctx)
    except (KeyError, IndexError, ValueError, TypeError):
      # A recipe misreading unusual data must not take the whole gallery down.
      continue
    for title, why, score, view in built or []:
      view["name"] = title
      thumb_kind = "lines" if view["kind"] == "overview" else view["kind"]
      controls = view.get("controls") or {}
      view["thumb"] = views.make_thumbnail(
        ctx.df, thumb_kind, controls.get("x"), controls.get("y"),
        (controls.get("color_by") or [None])[0] if isinstance(controls.get("color_by"), (list, tuple)) else controls.get("color_by"),
        ctx.dimensions,
      )
      candidates.append(
        Recommendation(recipe.id, title, why, score * _intent_boost(view, intent), view, scope=ctx.label)
      )

  candidates.sort(key=lambda reco: (-reco.score, reco.id))

  # Spread the gallery over several metrics rather than several readings of the
  # same one. Done after the intent boost, so a metric the user asked for is
  # allowed to appear more than once.
  used_metrics = {}
  for candidate in candidates:
    controls = candidate.view.get("controls") or {}
    charted = [controls.get("y")] + list(controls.get("y_metrics") or [])
    charted = [metric for metric in charted if metric]
    if not charted:
      continue
    seen_before = max(used_metrics.get(metric, 0) for metric in charted)
    candidate.score *= DIVERSITY_PENALTY ** seen_before
    for metric in charted:
      used_metrics[metric] = used_metrics.get(metric, 0) + 1
  candidates.sort(key=lambda reco: (-reco.score, reco.id))

  seen = set()
  kept = []
  for candidate in candidates:
    if candidate.signature in seen:
      continue
    seen.add(candidate.signature)
    kept.append(candidate)
    if len(kept) >= limit:
      break
  return kept


######################################
# Splitting the workspace into comparable scopes
######################################


class Scope(object):
  """
  One slice of the workspace the recipes are run over as if it were the whole
  data: its own sources, its own restriction, its own label.

  Mixing every source into a single measurement is what made the gallery
  generic: the loudest source decided which metrics existed, and every card
  spoke about "10 sources" without any of them holding the same designs.
  """

  def __init__(self, key, label, sources, filters, compare_by=None, bonus=0.0):
    self.key = key
    self.label = label
    self.sources = list(sources)
    self.filters = filters
    self.compare_by = compare_by
    self.bonus = bonus


#: Separator joining the columns that identify a design. Chosen not to occur in
#: an architecture or configuration name.
_DESIGN_SEPARATOR = " :: "


def _design_keys(df):
  """One "architecture :: configuration" key per row, or None when unavailable."""
  if schema.COL_SOURCE not in df.columns:
    return None
  columns = [column for column in (schema.COL_ARCHITECTURE, schema.COL_CONFIGURATION) if column in df.columns]
  if not columns:
    return None
  named = df
  if schema.COL_ARCHITECTURE in df.columns:
    # A row with no architecture names no design: two sources both holding a
    # handful of nameless rows are not two tools that ran the same thing.
    architecture = df[schema.COL_ARCHITECTURE].fillna(schema.MISSING_VALUE).astype(str)
    named = df[(architecture != schema.MISSING_VALUE) & (architecture != "")]
  if named.empty:
    return None
  keys = named[columns].fillna(schema.MISSING_VALUE).astype(str).agg(_DESIGN_SEPARATOR.join, axis=1)
  return named[schema.COL_SOURCE].astype(str), keys, named


def _designs_per_source(df):
  """The (architecture, configuration) designs each source actually holds."""
  keyed = _design_keys(df)
  if keyed is None:
    return {}
  sources, keys, _named = keyed
  designs = {}
  for source, key in zip(sources, keys):
    designs.setdefault(source, set()).add(key)
  return designs


def _metrics_measured_on(df, metrics):
  """A ``(source, designs) -> metrics`` lookup over the given selection.

  Sharing a metric name workspace-wide is not enough: what makes two tools
  comparable is measuring the same thing *on the designs they both ran*.
  """
  keyed = _design_keys(df)
  columns = [metric for metric in metrics if metric in df.columns]
  if keyed is None or not columns:
    return lambda source, designs: set()
  sources, keys, named = keyed

  def measured(source, designs):
    rows = named[(sources == source).values & keys.isin(designs).values]
    if rows.empty:
      return set()
    return set(
      metric for metric in columns
      if pd.to_numeric(rows[metric], errors="coerce").notna().any()
    )

  return measured


def comparable_sources(designs, measured=None):
  """
  The largest group of sources that ran the *same* designs, and those designs.

  Comparing two tools only means something on the designs they both
  implemented *and* measured the same way; anything else is two unrelated
  charts drawn on one canvas -- a simulation and a synthesis of the same
  counter share every configuration and not one metric. So a cross-source scope
  exists only when such a common ground is found, and it is restricted to it.
  """
  measured = measured or {}
  order = sorted(designs, key=lambda name: (-len(designs[name]), name))
  best = None
  for anchor in order[:4]:
    group = [anchor]
    shared = set(designs[anchor])
    for name in order:
      if name == anchor:
        continue
      merged = shared & designs[name]
      if len(merged) < MIN_SHARED_DESIGNS:
        continue
      if measured is not None:
        common = measured(anchor, merged)
        for member in group[1:] + [name]:
          common = common & measured(member, merged)
        if not common:
          continue
      group.append(name)
      shared = merged
    if len(group) < 2:
      continue
    if best is None or (len(group), len(shared)) > (len(best[0]), len(best[1])):
      best = (sorted(group), shared)
  return best


def _shared_filters(df, designs):
  """Turn a set of shared designs back into per-dimension allowed values."""
  filters = {}
  columns = [column for column in (schema.COL_ARCHITECTURE, schema.COL_CONFIGURATION) if column in df.columns]
  for index, column in enumerate(columns):
    filters[column] = sorted(set(key.split(_DESIGN_SEPARATOR)[index] for key in designs))
  return filters


def plan_scopes(store, sources, filters=None, rule_state=None):
  """
  How the gallery should carve up the workspace before recommending anything.

  One scope per source (each measured on its own terms), plus -- when some of
  them implemented the same designs -- one scope comparing those tools on that
  common ground.
  """
  sources = list(sources or [])
  if len(sources) < 2:
    return [Scope("all", "", sources, filters)]

  df = query.select_dataframe(store, sources=sources, filters=filters, rule_state=rule_state)
  _dimensions, metrics = query.discover(df, store, sources)
  designs = _designs_per_source(df)
  measured = _metrics_measured_on(df, metrics)

  # Busiest sources first: a file holding three rows has little to say, and
  # measuring twenty sources for one gallery is wasted work.
  ordered = sorted(sources, key=lambda name: (-len(designs.get(name, ())), name))
  scopes = []
  for name in ordered[:MAX_SCOPE_SOURCES]:
    scopes.append(Scope("source:" + name, name, [name], filters))

  group = comparable_sources(designs, measured)
  if group:
    members, shared = group
    combined = dict(filters or {})
    combined.update(_shared_filters(df, shared))
    # Naming the tools is what makes the card recognizable; past a few, the
    # count is all that fits.
    label = " vs ".join(members) if len(members) <= 3 else str(len(members)) + " sources compared"
    scopes.insert(0, Scope("cross", label, members, combined,
                           compare_by=schema.COL_SOURCE, bonus=CROSS_SOURCE_BONUS))
  return scopes


def _interleave(ranked, limit):
  """
  Take from each scope in turn, best first.

  Round-robin rather than a global sort: one prolific source would otherwise
  fill the whole gallery, which is the very thing scopes exist to avoid.
  """
  kept = []
  seen = set()
  shapes = {}
  depth = 0
  while len(kept) < limit:
    progressed = False
    for group in ranked:
      if depth >= len(group):
        continue
      progressed = True
      candidate = group[depth]
      if candidate.signature in seen:
        continue
      # Same chart, different scope: worth showing twice (the comparison and
      # one source on its own), never once per source.
      shape = candidate.signature[:1] + candidate.signature[2:6]
      if shapes.get(shape, 0) >= MAX_SHAPE_REPEATS:
        continue
      shapes[shape] = shapes.get(shape, 0) + 1
      seen.add(candidate.signature)
      kept.append(candidate)
      if len(kept) >= limit:
        break
    if not progressed:
      break
    depth += 1
  return kept


def recommend_gallery(store, sources=None, filters=None, rule_state=None, intent=None, limit=DEFAULT_LIMIT):
  """
  The gallery's entry point: recommend over every comparable scope at once.

  Same contract as ``recommend``, but the returned charts are each measured on
  a slice that holds together, and carry the name of that slice in ``scope``.
  """
  sources = list(sources) if sources else store.source_names()
  if not sources:
    return []

  ranked = []
  for scope in plan_scopes(store, sources, filters, rule_state):
    context = build_context(store, sources=scope.sources, filters=scope.filters, rule_state=rule_state)
    context.compare_by = scope.compare_by
    context.label = scope.label
    found = recommend(context, intent=intent, limit=limit)
    for recommendation in found:
      recommendation.score += scope.bonus
    if found:
      ranked.append(found)
  return _interleave(ranked, limit)

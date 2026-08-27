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
What the designs of a campaign are made of, and what each part of them did to
the numbers.

An exploration archive says which designs were evaluated and what they
measured. It also says, for every one of them, *what it was made of*: which
configuration each parameter domain contributed (``source``), what value every
individual parameter took (``parameters``), and what it was run at (frequency,
toolchain). This module reads a campaign as that table -- one row per design,
one column per **factor** -- and answers the question a front alone cannot:
which of those choices actually moved the metric, and which way.

Two things are computed here, and they answer different questions:

- **impact**: how much of the spread of a metric a factor accounts for. This is
  a variance ratio over the levels of the factor, corrected for the number of
  levels (:func:`_omega_squared`) -- a parameter with thirty values would
  otherwise "explain" everything simply by having a group per design.
- **enrichment**: how much more often a level appears on the front than it does
  in the space that was searched. A factor can barely move a metric on average
  and still be the one every good design agrees on.

Neither is a causal claim: a search does not sample its space uniformly -- that
is the whole point of one -- so a level that only ever appeared next to other
good choices will look good here. The numbers say what the designs that were
evaluated have in common, which is what a reader wants to know before spending
another campaign.
"""

import math

__all__ = [
  "Factor", "factors", "value_of", "metrics", "impacts", "impact_of", "levels_of",
  "DOMAIN", "PARAMETER", "RUN",
]

#: A factor is one of three things, and they are worth telling apart: a domain
#: is a whole configuration swapped in, a parameter is one number inside one,
#: and a run factor is not part of the design at all.
DOMAIN = "domain"
PARAMETER = "parameter"
RUN = "run"

KIND_LABEL = {
  DOMAIN: "parameter domain",
  PARAMETER: "parameter",
  RUN: "run",
}

#: Keys of a result record's meta that name the run rather than a parameter
#: domain of the architecture. Everything else in there is a domain.
RESERVED_META = frozenset([
  "type", "architecture", "configuration", "step", "timestamp",
  "frequency", "tool", "flow", "target", "start_time", "end_time",
])

#: The main parameter domain of an architecture is written under its own meta
#: key rather than under its name (see odatix.lib.results_schema), and it is a
#: parameter domain like any other: it is the one most campaigns vary first.
MAIN_DOMAIN_META_KEY = "main"
MAIN_DOMAIN_LABEL = "main parameter domain"

#: Meta keys that do name the run, and are worth offering as factors of their
#: own when a campaign varied them -- a search that chooses its toolchain is
#: comparing tools, and "which tool got there" is then the first question.
RUN_META = ("tool", "flow", "target")

#: Past this many distinct values a factor is drawn as a cloud rather than as
#: one box per level: forty boxes side by side are not read, they are counted.
MANY_LEVELS = 12


class Factor(object):
  """One column of the table a campaign makes: a choice the designs differ by."""

  def __init__(self, key, label, kind, source, numeric=False):
    #: How the value is fetched back out of a record.
    self.key = key
    self.label = label
    self.kind = kind
    #: ``"source"``, ``"parameters"``, ``"record"`` or ``"configuration"``.
    self.source = source
    #: Whether its values are numbers, which decides how it is charted: a
    #: number gets an axis it can be read along, a name gets a box per level.
    self.numeric = numeric
    #: Every value seen, in the order they should be drawn.
    self.levels = []

  @property
  def kind_label(self):
    return KIND_LABEL.get(self.kind, self.kind)

  @property
  def many_levels(self):
    return len(self.levels) > MANY_LEVELS

  def __repr__(self):
    return "<Factor {0} ({1}, {2} levels)>".format(self.label, self.kind, len(self.levels))


######################################
# Reading values out of a record
######################################

def _as_number(value):
  """
  The value as a number, or None when it is a name.

  A string of digits written by a config generator is a number and is read as
  one -- but not one that was padded ("007", "1001101"): a leading zero is how
  an encoding is written down, and reading it as an integer would sort designs
  along a scale that means nothing.
  """
  if isinstance(value, bool) or value is None:
    return None
  if isinstance(value, (int, float)):
    return float(value)
  if isinstance(value, str):
    text = value.strip()
    if not text:
      return None
    body = text[1:] if text[0] in "+-" else text
    if len(body) > 1 and body[0] == "0" and body[1] not in ".eE":
      return None
    try:
      return float(text)
    except ValueError:
      return None
  return None


def _domains_of(record):
  """
  Which configuration each parameter domain contributed to a design.

  Taken from the meta of the result the design was measured as, which is where
  a domain and its configuration are written down. An archive of a campaign
  that ran before that meta was kept has none, and the configuration name is
  read instead: it is built out of exactly those choices
  (``arch+Domain/Config+...``).
  """
  source = record.get("source")
  if isinstance(source, dict) and source:
    return dict(
      (key, value) for key, value in source.items()
      if not str(key).startswith("_") and str(key) not in RESERVED_META
      and isinstance(value, (str, int, float)) and not isinstance(value, bool)
    )

  parts = str(record.get("configuration") or "").split("+")
  domains = {}
  # The head of the name is the configuration of the main domain, which is
  # written down nowhere else in an archive that predates the meta above.
  if parts and parts[0]:
    domains[MAIN_DOMAIN_META_KEY] = parts[0]
  for part in parts[1:]:
    name, separator, configuration = part.partition("/")
    if separator and name:
      domains[name] = configuration
  return domains


def value_of(record, factor):
  """What a design chose for a factor, or None when the factor did not apply."""
  if factor.source == "parameters":
    value = (record.get("parameters") or {}).get(factor.key)
  elif factor.source == "source":
    value = _domains_of(record).get(factor.key)
  elif factor.source == "configuration":
    value = _domains_of(record).get(factor.key)
  elif factor.key == "toolchain":
    toolchain = record.get("toolchain")
    if not isinstance(toolchain, dict):
      return None
    value = " ".join(
      str(toolchain[part]) for part in ("tool", "flow", "target") if toolchain.get(part)
    ) or None
  elif factor.key in RUN_META:
    source = record.get("source")
    value = source.get(factor.key) if isinstance(source, dict) else None
  else:
    value = record.get(factor.key)
  if value is None:
    return None
  if factor.numeric:
    return _as_number(value)
  return str(value)


######################################
# What a campaign varied
######################################

def _levels(values, numeric):
  """The distinct values of a factor, in the order a chart should draw them."""
  distinct = set(values)
  if numeric:
    return sorted(distinct)
  return sorted(distinct, key=lambda value: (len(str(value)), str(value)))


def factors(campaign):
  """
  Every choice the designs of a campaign differ by, most telling first.

  A factor that never changed is left out: a column with one value in it
  explains nothing and only makes the ones that do harder to find. Domains come
  before the parameters inside them, and what the run chose comes last -- which
  is the order the questions get asked in.

  Failed designs count here: they were made of choices too, and "every design
  with this parameter failed to build" is exactly what the reader is looking
  for.
  """
  records = campaign.evaluations
  if not records:
    return []

  seen = {}   # (source, key) -> list of raw values
  order = []

  def collect(source, key, value):
    if value is None:
      return
    slot = (source, key)
    if slot not in seen:
      seen[slot] = []
      order.append(slot)
    seen[slot].append(value)

  for record in records:
    for name, value in _domains_of(record).items():
      collect("source", name, value)
    for name, value in (record.get("parameters") or {}).items():
      collect("parameters", name, value)
    if record.get("frequency") is not None:
      collect("record", "frequency", record.get("frequency"))
    if isinstance(record.get("toolchain"), dict):
      collect("record", "toolchain", record.get("toolchain"))
    source = record.get("source")
    if isinstance(source, dict):
      for name in RUN_META:
        collect("record", name, source.get(name))

  parameter_keys = set(key for source, key in order if source == "parameters")

  built = []
  for source, key in order:
    values = seen[(source, key)]
    # A domain that is also a parameter is the same choice written twice --
    # which is what a single-variable domain looks like from here.
    if source == "source" and key in parameter_keys:
      continue
    if key == "toolchain":
      numeric = False
      values = [
        " ".join(str(value[part]) for part in ("tool", "flow", "target") if value.get(part))
        for value in values
      ]
    else:
      numbers = [_as_number(value) for value in values]
      numeric = all(number is not None for number in numbers)
      values = numbers if numeric else [str(value) for value in values]

    levels = _levels(values, numeric)
    if len(levels) < 2:
      # It never changed: it is part of what the campaign is, not of what it
      # searched, and belongs in the header of the page rather than here.
      continue

    if source == "parameters":
      kind, label = PARAMETER, key
    elif source == "source":
      kind = DOMAIN
      label = MAIN_DOMAIN_LABEL if key == MAIN_DOMAIN_META_KEY else key
    else:
      kind, label = RUN, key

    factor = Factor(key, label, kind, source, numeric=numeric)
    factor.levels = levels
    built.append(factor)

  rank = {DOMAIN: 0, PARAMETER: 1, RUN: 2}
  built.sort(key=lambda factor: (rank.get(factor.kind, 3), factor.label))
  return built


def metrics(campaign):
  """
  Every metric that can be looked at, the objectives of the campaign first.

  What was optimized for is what the reader came for, but a campaign measures a
  great deal more than it optimizes -- and "what did this parameter do to the
  power, which nothing was steering" is the question this page exists for.
  """
  ordered = []
  for objective in campaign.objectives:
    if objective["metric"] not in ordered:
      ordered.append(objective["metric"])
  for constraint in campaign.constraints:
    metric = str(constraint.get("metric", ""))
    if metric and metric not in ordered:
      ordered.append(metric)

  rest = set()
  for record in campaign.evaluations:
    for name, value in (record.get("metrics") or {}).items():
      if isinstance(value, bool) or not isinstance(value, (int, float)):
        continue
      if name not in ordered:
        rest.add(name)
  return ordered + sorted(rest)


def metric_of(record, metric):
  """What a record says a metric is worth, or None when it was not measured."""
  values = record.get("metrics") or {}
  if metric in values:
    value = values.get(metric)
  elif metric == "frequency" and record.get("frequency") is not None:
    value = record.get("frequency")
  else:
    return None
  if isinstance(value, bool) or not isinstance(value, (int, float)):
    return None
  if isinstance(value, float) and value != value:  # NaN
    return None
  return float(value)


######################################
# How much a factor moved a metric
######################################

def _omega_squared(groups):
  """
  How much of the spread of a metric the grouping accounts for, from 0 to 1.

  The plain variance ratio -- the between-group share of the total -- rises
  simply because a factor has many levels, and would rank a parameter with one
  design per value above one that actually decides the metric. This is the
  ratio with that bias taken out (omega squared): what is left is roughly the
  share a *new* design's metric could be guessed from this factor alone.

  Args:
      groups (list): the metric values of each level, one list per level.

  Returns:
      float: 0 when the factor explains nothing more than chance.
  """
  groups = [group for group in groups if group]
  total = sum(len(group) for group in groups)
  if len(groups) < 2 or total <= len(groups):
    return 0.0

  grand = sum(sum(group) for group in groups) / float(total)
  between = sum(len(group) * (sum(group) / float(len(group)) - grand) ** 2 for group in groups)
  within = sum(sum((value - sum(group) / float(len(group))) ** 2 for value in group)
               for group in groups)
  if between + within <= 0:
    return 0.0

  within_mean = within / float(total - len(groups))
  corrected = between - (len(groups) - 1) * within_mean
  return max(0.0, corrected / (between + within + within_mean))


def _spearman(pairs):
  """
  Whether a numeric factor and a metric move together, from -1 to 1.

  Ranks rather than values, so that "twice the taps, four times the area" reads
  as the perfect agreement it is rather than as a curve that fits badly.
  """
  if len(pairs) < 3:
    return None

  def ranks(values):
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    index = 0
    while index < len(order):
      stop = index
      while stop + 1 < len(order) and values[order[stop + 1]] == values[order[index]]:
        stop += 1
      # Ties share the average of the ranks they span, or a factor with a
      # handful of values would correlate with the order they were listed in.
      shared = (index + stop) / 2.0 + 1
      for position in range(index, stop + 1):
        result[order[position]] = shared
      index = stop + 1
    return result

  x_ranks = ranks([pair[0] for pair in pairs])
  y_ranks = ranks([pair[1] for pair in pairs])
  count = float(len(pairs))
  x_mean = sum(x_ranks) / count
  y_mean = sum(y_ranks) / count
  covariance = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_ranks, y_ranks))
  x_spread = math.sqrt(sum((x - x_mean) ** 2 for x in x_ranks))
  y_spread = math.sqrt(sum((y - y_mean) ** 2 for y in y_ranks))
  if x_spread <= 0 or y_spread <= 0:
    return None
  return covariance / (x_spread * y_spread)


def levels_of(campaign, factor, metric, records=None, front_keys=None, key_of=None):
  """
  What each level of a factor is worth, level by level.

  This is the table behind every chart of the factor: how many designs took
  that value, how many of them failed to build, what the metric came out at,
  and how much of the front they ended up on.

  Args:
      campaign (Campaign): the archive.
      factor (Factor): the choice to break the designs down by.
      metric (str): the metric to summarize, or None for the counts alone.
      records (list): the designs to consider, or None for all of them.
      front_keys (set): the identity of the designs on the front.
      key_of (callable): how a design is named, matching ``front_keys``.

  Returns:
      list: one dict per level, in the order the factor draws them.
  """
  records = campaign.evaluations if records is None else records
  front_keys = front_keys or set()

  buckets = {}
  for record in records:
    value = value_of(record, factor)
    if value is None:
      continue
    bucket = buckets.setdefault(value, {"level": value, "designs": 0, "failed": 0,
                                        "values": [], "front": 0})
    bucket["designs"] += 1
    if record.get("failed"):
      bucket["failed"] += 1
      continue
    if key_of is not None and key_of(record) in front_keys:
      bucket["front"] += 1
    if metric:
      value_of_metric = metric_of(record, metric)
      if value_of_metric is not None:
        bucket["values"].append(value_of_metric)

  measured = sum(bucket["designs"] - bucket["failed"] for bucket in buckets.values())
  on_front = sum(bucket["front"] for bucket in buckets.values())

  rows = []
  for level in factor.levels:
    bucket = buckets.get(level)
    if bucket is None:
      continue
    values = bucket["values"]
    kept = bucket["designs"] - bucket["failed"]
    row = {
      "level": level,
      "designs": bucket["designs"],
      "failed": bucket["failed"],
      "front": bucket["front"],
      "mean": sum(values) / float(len(values)) if values else None,
      "best": None,
      "worst": None,
      "values": values,
      # How much more of the front this level took than its share of the
      # designs: 2 means it is twice as common among the answers as among the
      # designs that were tried, which is the sense in which the search
      # "preferred" it.
      "enrichment": None,
    }
    if values:
      goal = _goal_of(campaign, metric)
      maximizing = bool(goal) and goal.startswith("max")
      row["best"] = max(values) if maximizing else min(values)
      # What the level cost at its worst: a level whose average is good but
      # whose worst design is terrible is a gamble, not a finding.
      row["worst"] = min(values) if maximizing else max(values)
    if on_front and measured and kept:
      row["enrichment"] = (bucket["front"] / float(on_front)) / (kept / float(measured))
    rows.append(row)
  return rows


def _goal_of(campaign, metric):
  for objective in campaign.objectives:
    if objective["metric"] == metric:
      return objective["goal"]
  return None


def is_the_metric(factor, metric):
  """
  Whether a factor *is* the metric being broken down.

  A campaign that optimizes the frequency it runs at chose that frequency, so
  it is both a factor and a metric -- and "the frequency accounts for 100% of
  the spread of the frequency" is true, useless, and top of the ranking.
  """
  return bool(metric) and factor.label == metric


def impact_of(campaign, factor, metric, records=None):
  """
  What one factor did to one metric.

  Returns:
      dict: ``impact`` (0..1, the share of the spread it accounts for),
      ``direction`` (the rank correlation, for a numeric factor), ``spread``
      (how far apart the best and worst level averages are, in the unit of the
      metric), ``best`` / ``worst`` (the levels those are), ``designs`` and
      ``levels``. None when nothing was measured for it.
  """
  records = campaign.evaluations if records is None else records
  if is_the_metric(factor, metric):
    return None

  groups = {}
  pairs = []
  for record in records:
    if record.get("failed"):
      continue
    value = value_of(record, factor)
    if value is None:
      continue
    measured = metric_of(record, metric)
    if measured is None:
      continue
    groups.setdefault(value, []).append(measured)
    if factor.numeric:
      pairs.append((value, measured))

  if len(groups) < 2:
    return None

  means = dict((level, sum(values) / float(len(values))) for level, values in groups.items())
  goal = _goal_of(campaign, metric)
  better = max if (goal and goal.startswith("max")) else min
  best = better(means, key=lambda level: means[level])
  worst = (min if better is max else max)(means, key=lambda level: means[level])

  return {
    "factor": factor,
    "metric": metric,
    "impact": _omega_squared(list(groups.values())),
    "direction": _spearman(pairs) if factor.numeric else None,
    "spread": max(means.values()) - min(means.values()),
    "best": best,
    "best_mean": means[best],
    "worst": worst,
    "worst_mean": means[worst],
    "designs": sum(len(values) for values in groups.values()),
    "levels": len(groups),
  }


def impacts(campaign, metric, records=None, kinds=None):
  """
  Every factor of a campaign, ranked by how much it moved a metric.

  Args:
      kinds (tuple): which kinds of factor to keep (:data:`DOMAIN`,
          :data:`PARAMETER`, :data:`RUN`), or None for all of them.
  """
  ranked = []
  for factor in factors(campaign):
    if kinds and factor.kind not in kinds:
      continue
    result = impact_of(campaign, factor, metric, records)
    if result is not None:
      ranked.append(result)
  ranked.sort(key=lambda result: (result["impact"], abs(result["direction"] or 0)), reverse=True)
  return ranked

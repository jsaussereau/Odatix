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
Derived metrics: metrics a record does not hold itself, but gets from *another*
record.

A simulation tells how many cycles a benchmark takes; a synthesis tells at which
frequency the design closes timing. Neither record can express "runtime in
microseconds" on its own. A derived metric bridges the two: it copies a metric
from a matching record of another kind ("import"), or computes an expression
over metrics the record already has ("operation").

They are declared in a single workspace file (``derived_metrics.yml``)::

    groups:
      cpus: ["AsteRISC/*", "Ibex/*"]

    derived_metrics:
      Cycles:
        from: simulation
        for: "@cpus"
        match:
          pin: {MEM: 1024I_1024D}
      Runtime:
        type: operation
        op: "Cycles / Frequency"
        for: "@cpus"
        unit: us

Derived metrics are *not* computed at export time: the record they need may not
exist yet when a job finishes (a synthesis can complete before the simulation it
borrows from has run). They are recomputed from scratch over the whole result
set, every time odatix.components.export_derived_metrics runs, which is why
applying them twice is a no-op rather than a duplication.

How a source record is matched
------------------------------

Records of every kind share one flat namespace of meta keys (see
odatix.lib.results_schema), so matching is an equality test on the dimensions
the two records *have in common*: architecture, configuration, and every
parameter domain. A domain only one of them carries is not a constraint, which
is what makes an invariant domain (see the "invariant_domains" setting of a
simulation) broadcast over every value of that domain without anything to
declare here.

That default is refined per metric by ``match``:

  * ``keys``:   join on exactly these dimensions, and nothing else;
  * ``ignore``: drop these dimensions from the join;
  * ``pin``:    require a fixed value on the source side, and drop the
                dimension from the join;
  * ``map``:    the same dimension is not named the same on both sides.

Steps
-----

A flow split into steps yields one record per step, so a job is several source
records rather than one. By default a metric reads the *last* step each job
reached — the finished result — and ``step`` says otherwise::

    derived_metrics:
      Reg_count_after_synthesis:
        metric: Reg_count
        from: synthesis
        step: synthesis     # a step name, a list of them, or "@group"
      Anything:
        from: synthesis
        step: any           # every step, values aggregated per "on_multiple"

The step of the records that *receive* a metric is not restricted: every step
record in scope gets it. Use ``where: {step: ...}`` to narrow that side.

Groups
------

``groups`` maps a name to a list of patterns, and ``"@name"`` stands for that
list anywhere patterns are accepted. A group is just a named pattern list: it is
not tied to architectures, and the same mechanism names sets of simulations,
workflows, targets or parameter values.
"""

import os
import fnmatch

import yaml

import odatix.lib.printc as printc
import odatix.lib.results_schema as results_schema

script_name = os.path.basename(__file__)

DERIVED_METRICS_FILENAME = "derived_metrics.yml"

# Top-level keys of a derived metrics file.
GROUPS_KEY = "groups"
DERIVED_METRICS_KEY = "derived_metrics"

# Meta key holding the names of the metrics a record got from this module. It is
# "_"-prefixed, so it stays out of the record identity and of the dimensions a
# join runs on. It is what makes recomputation idempotent: those metrics are
# dropped before anything is derived again.
DERIVED_META_KEY = "_derived"

KIND_IMPORT = "import"
KIND_OPERATION = "operation"

# "from"/"apply_to" accept a record type, one of these aliases, or a list of both.
TYPE_ALIASES = {
  "synthesis": (results_schema.TYPE_FMAX, results_schema.TYPE_CUSTOM_FREQ),
  "fmax": (results_schema.TYPE_FMAX,),
  "custom_freq": (results_schema.TYPE_CUSTOM_FREQ,),
  "any": (),  # empty tuple means "no type restriction"
  "all": (),
  "*": (),
}

ON_MULTIPLE_CHOICES = ("error", "first", "last", "skip", "mean", "min", "max", "sum")

# "step" values lifting the default restriction to the last step of a job.
ANY_STEP_VALUES = ("any", "all", "*")

# The dimensions a join runs on, on top of every free (parameter domain) meta
# key. "configuration" is normalized first, see join_dimensions.
JOIN_RESERVED_KEYS = (results_schema.META_ARCHITECTURE, results_schema.META_CONFIGURATION)

# Reserved meta keys that never take part in a join: they describe how a job ran,
# not which design point it ran on.
NON_JOIN_RESERVED_KEYS = tuple(
  key for key in results_schema.RESERVED_META_KEYS if key not in JOIN_RESERVED_KEYS
)


######################################
# Groups and patterns
######################################


def _as_list(value):
  """Accept a scalar, a list, or nothing, and always return a list."""
  if value is None or value is False:
    return []
  if isinstance(value, (list, tuple)):
    return [item for item in value if item is not None]
  return [value]


class GroupResolver:
  """
  Resolves "@name" references against the ``groups`` section.

  A group may reference another group; a cycle resolves to an empty list and is
  reported once, rather than recursing forever.
  """

  def __init__(self, groups=None):
    self.groups = {}
    if isinstance(groups, dict):
      for name, patterns in groups.items():
        self.groups[str(name)] = [str(pattern) for pattern in _as_list(patterns)]
    self.unknown_reported = set()

  def resolve(self, patterns, _seen=None):
    """Expand every "@group" reference of a pattern list into plain patterns."""
    resolved = []
    seen = set() if _seen is None else _seen
    for pattern in _as_list(patterns):
      pattern = str(pattern)
      if not pattern.startswith("@"):
        resolved.append(pattern)
        continue

      name = pattern[1:]
      if name in seen:
        printc.warning('Circular group reference "@' + name + '" in derived metrics', script_name)
        continue
      if name not in self.groups:
        if name not in self.unknown_reported:
          self.unknown_reported.add(name)
          printc.warning('Unknown group "@' + name + '" referenced in derived metrics', script_name)
        continue
      resolved.extend(self.resolve(self.groups[name], seen | {name}))
    return resolved


def matches_any(value, patterns):
  """
  True when a value matches at least one glob pattern. An empty pattern list
  means "no restriction", so it matches.
  """
  if not patterns:
    return True
  if value is None:
    return False
  value = str(value)
  return any(fnmatch.fnmatchcase(value, str(pattern)) for pattern in patterns)


######################################
# Record dimensions
######################################


def base_configuration(meta):
  """
  The configuration a record was produced for, without its "+domain/value"
  segments.

  Synthesis records carry the full work-directory configuration name plus a
  "main" key holding the base configuration, while simulation and workflow
  records carry the base name directly under "configuration". Both are reduced
  to the same value here, so that a synthesis and a simulation of the same
  design point join.
  """
  if not isinstance(meta, dict):
    return None

  main = meta.get(results_schema.MAIN_DOMAIN_META_KEY)
  if isinstance(main, str) and main != "":
    return main

  configuration = meta.get(results_schema.META_CONFIGURATION)
  if not isinstance(configuration, str):
    return configuration
  return configuration.split("+")[0]


def join_dimensions(meta):
  """
  The dimensions of a record a join may run on: which design point it is, and
  nothing about how the job that produced it ran.

  Returns:
      dict: dimension name -> value (as a string).
  """
  dimensions = {}
  if not isinstance(meta, dict):
    return dimensions

  for key, value in meta.items():
    key = str(key)
    if key.startswith("_") or key in NON_JOIN_RESERVED_KEYS:
      continue
    if key in (results_schema.META_CONFIGURATION, results_schema.MAIN_DOMAIN_META_KEY):
      continue
    dimensions[key] = str(value)

  configuration = base_configuration(meta)
  if configuration is not None:
    dimensions[results_schema.META_CONFIGURATION] = str(configuration)

  return dimensions


def instance_names(meta):
  """
  Every name a record may be designated by in a ``for`` scope: its architecture
  (alone and with its configuration), its workflow, and its simulation.

  A scope pattern is tested against all of them, which is what lets one group
  name architectures, another name simulations, and both be written the same
  way.
  """
  names = []
  if not isinstance(meta, dict):
    return names

  architecture = meta.get(results_schema.META_ARCHITECTURE)
  if isinstance(architecture, str) and architecture != "":
    names.append(architecture)
    configuration = base_configuration(meta)
    if isinstance(configuration, str) and configuration != "":
      names.append(architecture + "/" + configuration)

  for key in (results_schema.META_WORKFLOW, results_schema.META_SIMULATION):
    value = meta.get(key)
    if isinstance(value, str) and value != "":
      names.append(value)

  return names


def record_types(value, resolver=None):
  """
  Expand a "from"/"apply_to" value into a set of record types. An empty set
  means "any type".
  """
  types = set()
  for item in _as_list(value):
    item = str(item)
    if item in TYPE_ALIASES:
      expanded = TYPE_ALIASES[item]
      if not expanded:
        return set()  # an "any" alias makes the whole restriction vanish
      types.update(expanded)
    else:
      types.add(item)
  return types


######################################
# Definitions
######################################


class DerivedMetric:
  """One entry of the ``derived_metrics`` section."""

  def __init__(self, name, definition, resolver, source_file=""):
    self.name = str(name)
    self.source_file = source_file
    self.valid = True

    if not isinstance(definition, dict):
      self._invalid('Definition of derived metric "' + self.name + '" is not a dictionary')
      return

    self.kind = str(definition.get("type", "")).strip().lower()
    self.op = definition.get("op")
    self.source_metric = str(definition.get("metric", self.name))
    self.unit = definition.get("unit")
    self.overwrite = bool(definition.get("overwrite", False))
    self.optional = bool(definition.get("optional", False))

    self.from_types = record_types(definition.get("from"))
    self.apply_to_types = record_types(definition.get("apply_to", "synthesis"))

    # Which step of the source job to read from. A flow split into steps has one
    # record per step (see odatix.lib.results_schema), so without this a source
    # would be found as many times as the job has steps. Left unset, only the
    # last step of each job is read, which is the finished result; "step: any"
    # opens it to all of them, and a name (or a list, or a group) picks them.
    self.source_step = definition.get("step")
    self.any_step = str(self.source_step).strip().lower() in ANY_STEP_VALUES if self.source_step is not None else False
    self.source_step_patterns = [] if self.source_step is None else resolver.resolve(self.source_step)

    if self.kind == "":
      self.kind = KIND_OPERATION if self.op is not None else KIND_IMPORT
    if self.kind not in (KIND_IMPORT, KIND_OPERATION):
      self._invalid('Unsupported type "' + self.kind + '" for derived metric "' + self.name + '"')
      return
    if self.kind == KIND_OPERATION and not isinstance(self.op, str):
      self._invalid('Derived metric "' + self.name + '" is an operation but has no "op" expression')
      return
    if self.kind == KIND_IMPORT and not definition.get("from"):
      self._invalid('Derived metric "' + self.name + '" has no "from" telling which records to read')
      return

    # Scopes
    self.scope = resolver.resolve(definition.get("for", []))
    self.where = self._resolve_conditions(definition.get("where"), resolver)
    self.source_where = self._resolve_conditions(definition.get("source_where"), resolver)

    # Join rule
    match = definition.get("match")
    match = match if isinstance(match, dict) else {}
    # "keys", not "on": YAML reads a bare "on" key as the boolean True, so a
    # field named that way would silently never be found. A file written with
    # "on:" anyway is still honoured, through the True key it actually parses to.
    match_keys = match.get("keys")
    if match_keys is None:
      match_keys = match.get(True)
    self.match_on = [str(key) for key in _as_list(match_keys)]
    self.match_ignore = set(str(key) for key in _as_list(match.get("ignore")))
    self.match_pin = {}
    if isinstance(match.get("pin"), dict):
      self.match_pin = {str(key): str(value) for key, value in match["pin"].items()}
    self.match_map = {}
    if isinstance(match.get("map"), dict):
      # Written source-side name -> target-side name.
      self.match_map = {str(key): str(value) for key, value in match["map"].items()}

    self.on_multiple = str(definition.get("on_multiple", "error")).strip().lower()
    if self.on_multiple not in ON_MULTIPLE_CHOICES:
      printc.warning(
        'Unsupported "on_multiple" value "' + self.on_multiple + '" for derived metric "'
        + self.name + '", falling back to "error"',
        script_name,
      )
      self.on_multiple = "error"

  def _invalid(self, message):
    printc.error(message + ' in "' + self.source_file + '"', script_name)
    self.valid = False

  @staticmethod
  def _resolve_conditions(conditions, resolver):
    """Turn a {meta key: patterns} mapping into {meta key: resolved pattern list}."""
    resolved = {}
    if isinstance(conditions, dict):
      for key, patterns in conditions.items():
        resolved[str(key)] = resolver.resolve(patterns)
    return resolved

  def applies_to(self, meta):
    """Whether a record is in the scope of this metric, i.e. may receive it."""
    if self.apply_to_types and str(meta.get(results_schema.META_TYPE, "")) not in self.apply_to_types:
      return False
    if self.scope and not any(matches_any(name, self.scope) for name in instance_names(meta)):
      return False
    return self._satisfies(meta, self.where)

  def source_candidate(self, meta):
    """Whether a record may be read as a source for this metric."""
    if self.from_types and str(meta.get(results_schema.META_TYPE, "")) not in self.from_types:
      return False
    if not self._step_allowed(meta):
      return False
    return self._satisfies(meta, self.source_where)

  def _step_allowed(self, meta):
    """
    Whether the step a source record holds is one this metric reads.

    A record that belongs to no step (a job whose flow has none) always is. The
    default, for the others, is the last step the job reached: reading every
    step would silently turn one source into several and trip "on_multiple".
    """
    if results_schema.META_STEP not in meta:
      return True
    if self.any_step:
      return True
    if self.source_step is not None:
      return matches_any(meta.get(results_schema.META_STEP), self.source_step_patterns)
    if results_schema.META_STEP in self.source_where:
      return True  # the step is picked by "source_where" instead
    return bool(meta.get(results_schema.META_LAST_STEP, True))

  @staticmethod
  def _satisfies(meta, conditions):
    for key, patterns in conditions.items():
      if not matches_any(meta.get(key), patterns):
        return False
    return True

  def source_dimensions(self, meta):
    """
    The join dimensions of a source record, renamed to the target-side naming.
    """
    dimensions = join_dimensions(meta)
    if not self.match_map:
      return dimensions
    renamed = {}
    for key, value in dimensions.items():
      renamed[self.match_map.get(key, key)] = value
    return renamed

  def pin_satisfied(self, source_dimensions):
    """Whether a source record holds the values ``match.pin`` requires."""
    for key, value in self.match_pin.items():
      key = self.match_map.get(key, key)
      if source_dimensions.get(key) != value:
        return False
    return True

  def join_keys(self, target_dimensions, source_dimensions):
    """
    The dimensions this pair of records must agree on.

    Without an explicit ``match.keys``, that is the dimensions they have in
    common: one that only the target carries (a domain the source is invariant
    to) does not constrain the match.
    """
    if self.match_on:
      keys = set(self.match_on)
    else:
      keys = set(target_dimensions) & set(source_dimensions)

    pinned = set(self.match_map.get(key, key) for key in self.match_pin)
    return keys - self.match_ignore - pinned


######################################
# Configuration file
######################################


class DerivedMetricsConfig:
  """The content of a derived metrics file."""

  def __init__(self, path="", metrics=None, resolver=None):
    self.path = path
    self.metrics = metrics if metrics is not None else []
    self.resolver = resolver if resolver is not None else GroupResolver()

  def __bool__(self):
    return len(self.metrics) > 0

  @property
  def names(self):
    return [metric.name for metric in self.metrics]


def default_derived_metrics_file(settings=None):
  """
  Where the derived metrics of a workspace are declared. The path comes from the
  workspace settings when they are available, and falls back to the default
  location relative to the current directory.
  """
  path = getattr(settings, "derived_metrics_file", None)
  if isinstance(path, str) and path.strip() != "":
    return path
  from odatix.lib.settings import OdatixSettings

  return OdatixSettings.DEFAULT_DERIVED_METRICS_FILE


def load_derived_metrics(path):
  """
  Load a derived metrics file.

  A missing file is not an error: a workspace that derives nothing simply has
  none. An unparsable one is, and yields an empty configuration.

  Returns:
      DerivedMetricsConfig
  """
  if path is None or not os.path.isfile(path):
    return DerivedMetricsConfig(path=str(path or ""))

  try:
    with open(path, "r") as f:
      data = yaml.safe_load(f)
  except Exception as e:
    printc.error('Derived metrics file "' + path + '" is not a valid YAML file', script_name)
    printc.cyan("error details: ", end="", script_name=script_name)
    print(str(e))
    return DerivedMetricsConfig(path=path)

  if data is None:
    return DerivedMetricsConfig(path=path)
  if not isinstance(data, dict):
    printc.error('Derived metrics file "' + path + '" must contain a dictionary', script_name)
    return DerivedMetricsConfig(path=path)

  resolver = GroupResolver(data.get(GROUPS_KEY))

  definitions = data.get(DERIVED_METRICS_KEY)
  if definitions is None:
    return DerivedMetricsConfig(path=path, resolver=resolver)
  if not isinstance(definitions, dict):
    printc.error('"' + DERIVED_METRICS_KEY + '" must be a dictionary in "' + path + '"', script_name)
    return DerivedMetricsConfig(path=path, resolver=resolver)

  metrics = []
  for name, definition in definitions.items():
    if definition is None:
      continue  # a metric mapped to nothing is disabled, like in metrics files
    metric = DerivedMetric(name, definition, resolver, source_file=path)
    if metric.valid:
      metrics.append(metric)

  return DerivedMetricsConfig(path=path, metrics=metrics, resolver=resolver)


######################################
# Aggregation
######################################


def _numeric(values):
  numbers = []
  for value in values:
    if isinstance(value, bool):
      continue
    if isinstance(value, (int, float)):
      numbers.append(value)
  return numbers


def aggregate(values, how, metric_name="", error_prefix=""):
  """
  Reduce the values of every matching source record to one, following
  ``on_multiple``. Returns (value, ok): ok is False when the ambiguity could not
  be resolved and nothing should be written.
  """
  if len(values) == 1:
    return values[0], True

  if how == "first":
    return values[0], True
  if how == "last":
    return values[-1], True
  if how == "skip":
    return None, False
  if how == "error":
    printc.error(
      error_prefix + str(len(values)) + ' records match derived metric "' + metric_name
      + '". Refine "match" or set "on_multiple" to tell which value to use.',
      script_name,
    )
    return None, False

  numbers = _numeric(values)
  if len(numbers) == 0:
    printc.error(
      error_prefix + 'Cannot apply "' + how + '" to the non-numeric values of derived metric "'
      + metric_name + '"',
      script_name,
    )
    return None, False

  if how == "mean":
    return sum(numbers) / len(numbers), True
  if how == "min":
    return min(numbers), True
  if how == "max":
    return max(numbers), True
  if how == "sum":
    return sum(numbers), True

  return None, False


######################################
# Engine
######################################


def _clear_previous(record):
  """
  Drop the metrics a previous run derived, so that deriving again recomputes
  them instead of leaving a stale value behind when a definition changes or a
  source record disappears.
  """
  meta = record.get("meta")
  if not isinstance(meta, dict):
    return False

  previous = meta.pop(DERIVED_META_KEY, None)
  if not isinstance(previous, list):
    return False

  metrics = record.get("metrics")
  changed = False
  if isinstance(metrics, dict):
    for name in previous:
      if metrics.pop(str(name), None) is not None:
        changed = True
  return changed


def _evaluate_operation(op, metrics, error_prefix=""):
  from odatix.components.export_common import calculate_operation

  return calculate_operation(op, metrics, error_if_missing=False, error_prefix=error_prefix)


def _record_label(meta):
  """A short "who is this record" prefix for error messages."""
  parts = []
  for key in (
    results_schema.META_TYPE,
    results_schema.META_SIMULATION,
    results_schema.META_WORKFLOW,
    results_schema.META_ARCHITECTURE,
  ):
    value = meta.get(key)
    if isinstance(value, str) and value != "":
      parts.append(value)
  configuration = base_configuration(meta)
  if isinstance(configuration, str) and configuration != "":
    parts.append(configuration)
  return " => ".join(parts) + " => " if parts else ""


def apply_derived_metrics(config, records, units=None):
  """
  Compute every derived metric over a pool of records, in place.

  The pool must hold *all* the records of a workspace, whichever file they come
  from: a derived metric reads records the target's own file does not contain.
  Metrics are computed in declaration order, so an ``operation`` may use a value
  an earlier ``import`` brought in.

  Args:
      config (DerivedMetricsConfig): The loaded definitions.
      records (list): Every v2 record of the workspace.
      units (dict|None): Updated with the unit of each derived metric.

  Returns:
      set: The indices of the records that changed.
  """
  changed = set()

  # A previous run's values go first, whether or not anything is derived now.
  for index, record in enumerate(records):
    if isinstance(record, dict) and _clear_previous(record):
      changed.add(index)

  if not config or not config.metrics:
    return changed

  valid = [(index, record) for index, record in enumerate(records) if isinstance(record, dict) and isinstance(record.get("meta"), dict)]

  for metric in config.metrics:
    if metric.kind == KIND_IMPORT:
      sources = []
      for _, record in valid:
        meta = record["meta"]
        if not metric.source_candidate(meta):
          continue
        dimensions = metric.source_dimensions(meta)
        if not metric.pin_satisfied(dimensions):
          continue
        value = record.get("metrics", {}).get(metric.source_metric)
        if value is None:
          continue
        sources.append((dimensions, value))
    else:
      sources = None

    missing = []

    for index, record in valid:
      meta = record["meta"]
      if not metric.applies_to(meta):
        continue

      metrics = record.setdefault("metrics", {})
      if metric.name in metrics and not metric.overwrite:
        continue

      if metric.kind == KIND_IMPORT:
        target_dimensions = join_dimensions(meta)
        matched = []
        for source_dimensions, value in sources:
          keys = metric.join_keys(target_dimensions, source_dimensions)
          if all(target_dimensions.get(key) == source_dimensions.get(key) for key in keys):
            matched.append(value)

        if len(matched) == 0:
          missing.append(_record_label(meta).rstrip(" =>"))
          continue

        value, ok = aggregate(matched, metric.on_multiple, metric.name, _record_label(meta))
        if not ok:
          continue
      else:
        value = _evaluate_operation(metric.op, metrics, _record_label(meta))
        if value is None:
          continue

      metrics[metric.name] = value
      meta.setdefault(DERIVED_META_KEY, [])
      if metric.name not in meta[DERIVED_META_KEY]:
        meta[DERIVED_META_KEY].append(metric.name)
      changed.add(index)

      if units is not None and metric.unit is not None:
        units[metric.name] = metric.unit

    # Reported once per metric rather than once per record: a metric nothing was
    # simulated for would otherwise drown every other message.
    if missing and not metric.optional:
      printc.warning(
        'No source record found for derived metric "' + metric.name + '" on '
        + str(len(missing)) + " record" + ("s" if len(missing) > 1 else "")
        + " (" + ", ".join(sorted(set(missing))[:3])
        + (", ..." if len(set(missing)) > 3 else "") + ")",
        script_name,
      )

  return changed

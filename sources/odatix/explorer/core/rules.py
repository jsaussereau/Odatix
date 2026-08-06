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
Metric rules: value conditions on the numeric columns, e.g. "LUT < 1000" or
"Fmax > 100 and FF < 2000".

A rule set is a plain dict, session-storable and view-serializable::

    {"match": "all" | "any", "rules": [{"id", "metric", "op", "value"}, ...]}

Rules complement the dimension checkboxes: the checkboxes say *which* points
exist, the rules say *which values* are acceptable. Incomplete rules (no metric
or no value yet, e.g. a row just added) are simply ignored, so the chart stays
usable while a rule is being written.
"""

import operator

import pandas as pd

# (value, label) — the value is the serialized form, the label what the user sees
OPERATORS = (
  ("<", "<"),
  ("<=", "≤"),
  (">", ">"),
  (">=", "≥"),
  ("==", "="),
  ("!=", "≠"),
)
OPERATOR_LABELS = dict(OPERATORS)
DEFAULT_OPERATOR = "<"

_OPERATOR_FUNCTIONS = {
  "<": operator.lt,
  "<=": operator.le,
  ">": operator.gt,
  ">=": operator.ge,
  "==": operator.eq,
  "!=": operator.ne,
}

MATCH_ALL = "all"
MATCH_ANY = "any"
DEFAULT_MATCH = MATCH_ALL

# Word used between two rules in the human-readable form
MATCH_JOINER = {MATCH_ALL: "and", MATCH_ANY: "or"}


def empty_state():
  return {"match": DEFAULT_MATCH, "rules": []}


def _number(value):
  """The rule threshold as a float, or None when not (yet) a number."""
  if value is None or value == "":
    return None
  try:
    return float(value)
  except (TypeError, ValueError):
    return None


def normalize(rule_state):
  """Coerce any stored/loaded payload into a well-formed rule set."""
  state = rule_state if isinstance(rule_state, dict) else {}
  match = state.get("match")
  if match not in (MATCH_ALL, MATCH_ANY):
    match = DEFAULT_MATCH

  rules = []
  for index, rule in enumerate(state.get("rules") or []):
    if not isinstance(rule, dict):
      continue
    metric = rule.get("metric")
    op = rule.get("op")
    rules.append({
      "id": str(rule.get("id") or index),
      "metric": str(metric) if metric else None,
      "op": op if op in _OPERATOR_FUNCTIONS else DEFAULT_OPERATOR,
      "value": rule.get("value"),
    })
  return {"match": match, "rules": rules}


def new_rule(rule_state, metric=None):
  """A blank rule with an id unique in ``rule_state``."""
  used = {rule["id"] for rule in normalize(rule_state)["rules"]}
  index = 0
  while str(index) in used:
    index += 1
  return {"id": str(index), "metric": metric, "op": DEFAULT_OPERATOR, "value": None}


def is_complete(rule):
  """A rule is applied only once it names a metric and a numeric threshold."""
  return bool(rule.get("metric")) and _number(rule.get("value")) is not None


def applicable_rules(rule_state, columns=None):
  """The complete rules of a set, restricted to the columns of a selection."""
  rules = [rule for rule in normalize(rule_state)["rules"] if is_complete(rule)]
  if columns is None:
    return rules
  return [rule for rule in rules if rule["metric"] in columns]


def apply_rules(df, rule_state):
  """
  Keep the rows of ``df`` satisfying the rule set (all of them, or any of them,
  per ``match``). Rows where a compared metric is not a number never match:
  "LUT < 1000" cannot be true of a missing LUT count.
  """
  if df is None or df.empty:
    return df
  state = normalize(rule_state)
  rules = applicable_rules(state, df.columns)
  if not rules:
    return df

  mask = None
  for rule in rules:
    column = pd.to_numeric(df[rule["metric"]], errors="coerce")
    rule_mask = _OPERATOR_FUNCTIONS[rule["op"]](column, _number(rule["value"])) & column.notna()
    if mask is None:
      mask = rule_mask
    elif state["match"] == MATCH_ALL:
      mask = mask & rule_mask
    else:
      mask = mask | rule_mask
  return df[mask]


def describe(rule_state, columns=None):
  """The rule set as a readable expression, e.g. "Fmax > 100 and FF < 2000"."""
  state = normalize(rule_state)
  rules = applicable_rules(state, columns)
  if not rules:
    return ""
  joiner = " " + MATCH_JOINER[state["match"]] + " "
  return joiner.join(
    str(rule["metric"]) + " " + OPERATOR_LABELS[rule["op"]] + " " + _format_number(rule["value"])
    for rule in rules
  )


def _format_number(value):
  number = _number(value)
  if number is None:
    return str(value)
  if number == int(number):
    return str(int(number))
  return str(number)

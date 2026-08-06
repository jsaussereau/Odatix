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
Metric rules: value conditions on the numeric columns, e.g. "LUT < 1000",
"Fmax > 100 and FF < 2000" or "(Fmax > 2) or (Fmax > 1 and LUT < 4)".

A rule set is a tree of plain dicts, session-storable and view-serializable.
The state itself is the root group::

    group = {"id", "kind": "group", "match": "all" | "any", "children": [node]}
    rule  = {"id", "kind": "rule", "metric", "op",
             "operand": "value" | "metric", "value", "other"}

A group joins its children with a single "and" (match all) or "or" (match any);
nesting groups is what expresses mixed expressions. A rule compares a metric
either to a constant (``operand == "value"``, threshold in ``value``) or to
another metric (``operand == "metric"``, named by ``other``).

Rules complement the dimension checkboxes: the checkboxes say *which* points
exist, the rules say *which values* are acceptable. Incomplete rules (no metric
or no threshold yet, e.g. a card just added) are simply ignored, so the chart
stays usable while a rule is being written.
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

# Word used between two children in the human-readable form
MATCH_JOINER = {MATCH_ALL: "and", MATCH_ANY: "or"}

# Right-hand side of a comparison: a constant, or another metric of the same row
OPERAND_VALUE = "value"
OPERAND_METRIC = "metric"
DEFAULT_OPERAND = OPERAND_VALUE

ROOT_ID = "root"

# Nesting is bounded so the panel stays readable in the sidebar
MAX_DEPTH = 4


def empty_state():
  return {"id": ROOT_ID, "kind": "group", "match": DEFAULT_MATCH, "children": []}


def _number(value):
  """The rule threshold as a float, or None when not (yet) a number."""
  if value is None or value == "":
    return None
  try:
    return float(value)
  except (TypeError, ValueError):
    return None


def _text(value):
  return str(value) if value else None


# --------------------------------------------------------------- normalize ---


def normalize(rule_state):
  """
  Coerce any stored/loaded payload into a well-formed rule tree.

  Also upgrades the flat shape used before nested groups existed
  ({"match", "rules": [...]}), so views and sessions saved then still load.
  """
  state = rule_state if isinstance(rule_state, dict) else {}
  if "children" not in state and "rules" in state:
    state = {"kind": "group", "match": state.get("match"), "children": state.get("rules")}
  root = _normalize_group(state, ROOT_ID)
  root["id"] = ROOT_ID
  return root


def _normalize_group(node, fallback_id, depth=0):
  match = node.get("match")
  if match not in (MATCH_ALL, MATCH_ANY):
    match = DEFAULT_MATCH
  children = []
  for index, child in enumerate(node.get("children") or []):
    if not isinstance(child, dict):
      continue
    child_id = str(child.get("id") or (str(fallback_id) + "." + str(index)))
    if child.get("kind") == "group" or "children" in child:
      if depth >= MAX_DEPTH:
        continue
      children.append(_normalize_group(child, child_id, depth + 1))
    else:
      children.append(_normalize_rule(child, child_id))
  return {"id": str(node.get("id") or fallback_id), "kind": "group", "match": match, "children": children}


def _normalize_rule(node, fallback_id):
  op = node.get("op")
  operand = node.get("operand")
  return {
    "id": str(node.get("id") or fallback_id),
    "kind": "rule",
    "metric": _text(node.get("metric")),
    "op": op if op in _OPERATOR_FUNCTIONS else DEFAULT_OPERATOR,
    "operand": operand if operand in (OPERAND_VALUE, OPERAND_METRIC) else DEFAULT_OPERAND,
    "value": node.get("value"),
    "other": _text(node.get("other")),
  }


# ------------------------------------------------------------------ lookup ---


def iter_nodes(node, depth=0, parent=None):
  """Yield (node, depth, parent) for the whole tree, root first."""
  yield node, depth, parent
  if node.get("kind") == "group":
    for child in node.get("children") or []:
      for item in iter_nodes(child, depth + 1, node):
        yield item


def find(state, node_id):
  """The node with this id, or None."""
  for node, _depth, _parent in iter_nodes(state):
    if node["id"] == str(node_id):
      return node
  return None


def depth_of(state, node_id):
  for node, depth, _parent in iter_nodes(state):
    if node["id"] == str(node_id):
      return depth
  return 0


def _new_id(state, taken=()):
  """An id unique in the whole tree (ids must survive a panel rebuild)."""
  used = {node["id"] for node, _depth, _parent in iter_nodes(state)} | set(taken)
  index = 0
  while str(index) in used:
    index += 1
  return str(index)


# ----------------------------------------------------------------- editing ---


def new_rule(state, metric=None, taken=()):
  return {
    "id": _new_id(state, taken),
    "kind": "rule",
    "metric": metric,
    "op": DEFAULT_OPERATOR,
    "operand": DEFAULT_OPERAND,
    "value": None,
    "other": None,
  }


def new_group(state):
  """
  A nested group, pre-filled with one blank rule so it is never empty. Its
  default is "any": a group inside the usual match-all root is what expresses
  "... and (this or that)", the case nesting exists for.
  """
  group_id = _new_id(state)
  return {
    "id": group_id,
    "kind": "group",
    "match": MATCH_ANY,
    "children": [new_rule(state, taken=(group_id,))],
  }


def add_child(state, group_id, child):
  """Append a node to a group, ignored if the group would be nested too deep."""
  group = find(state, group_id)
  if group is None or group.get("kind") != "group":
    return state
  if depth_of(state, group_id) >= MAX_DEPTH:
    return state
  group["children"].append(child)
  return state


def remove(state, node_id):
  """Drop a node (and its subtree). The root is emptied rather than removed."""
  if str(node_id) == ROOT_ID:
    state["children"] = []
    return state
  for node, _depth, _parent in iter_nodes(state):
    if node.get("kind") != "group":
      continue
    kept = [child for child in node["children"] if child["id"] != str(node_id)]
    if len(kept) != len(node["children"]):
      node["children"] = kept
      break
  return state


def toggle_match(state, group_id):
  group = find(state, group_id)
  if group is not None and group.get("kind") == "group":
    group["match"] = MATCH_ANY if group["match"] == MATCH_ALL else MATCH_ALL
  return state


def set_field(state, node_id, field, value):
  node = find(state, node_id)
  if node is None or node.get("kind") != "rule":
    return state
  # The unused operand is kept around, so switching back restores what was typed
  node[field] = value
  return state


# ---------------------------------------------------------------- applying ---


def is_complete(rule):
  """A rule applies once it names a metric and a right-hand side."""
  if not rule.get("metric"):
    return False
  if rule.get("operand") == OPERAND_METRIC:
    return bool(rule.get("other"))
  return _number(rule.get("value")) is not None


def _rule_applies(rule, columns):
  if not is_complete(rule):
    return False
  if columns is None:
    return True
  if rule["metric"] not in columns:
    return False
  if rule.get("operand") == OPERAND_METRIC and rule.get("other") not in columns:
    return False
  return True


def _group_applies(group, columns):
  return any(applies(child, columns) for child in group.get("children") or [])


def applies(node, columns=None):
  """Whether a node contributes to the selection (complete, columns present)."""
  if node.get("kind") == "group":
    return _group_applies(node, columns)
  return _rule_applies(node, columns)


def count_rules(state, columns=None):
  """How many individual rules are currently applied."""
  return sum(
    1 for node, _depth, _parent in iter_nodes(normalize(state)) if node.get("kind") == "rule" and applies(node, columns)
  )


def _rule_mask(df, rule):
  column = pd.to_numeric(df[rule["metric"]], errors="coerce")
  if rule.get("operand") == OPERAND_METRIC:
    other = pd.to_numeric(df[rule["other"]], errors="coerce")
    return _OPERATOR_FUNCTIONS[rule["op"]](column, other) & column.notna() & other.notna()
  return _OPERATOR_FUNCTIONS[rule["op"]](column, _number(rule["value"])) & column.notna()


def _mask(df, node):
  """The boolean mask of a node, or None when it applies to nothing."""
  if node.get("kind") != "group":
    return _rule_mask(df, node) if _rule_applies(node, df.columns) else None

  mask = None
  for child in node.get("children") or []:
    child_mask = _mask(df, child)
    if child_mask is None:
      continue
    if mask is None:
      mask = child_mask
    elif node["match"] == MATCH_ALL:
      mask = mask & child_mask
    else:
      mask = mask | child_mask
  return mask


def apply_rules(df, rule_state):
  """
  Keep the rows of ``df`` satisfying the rule tree. Rows where a compared metric
  is not a number never match: "LUT < 1000" cannot be true of a missing LUT
  count, and neither can "Fmax > Frequency" of a missing frequency.
  """
  if df is None or df.empty:
    return df
  mask = _mask(df, normalize(rule_state))
  return df if mask is None else df[mask]


# --------------------------------------------------------------- describing ---


def describe(rule_state, columns=None):
  """
  The rule tree as a readable expression, e.g.
  "(Fmax > 2) or (Fmax > 1 and LUT < 4)". Only nested groups are parenthesized.
  """
  return _describe(normalize(rule_state), columns, root=True)


def _describe(node, columns, root=False):
  if node.get("kind") != "group":
    return _describe_rule(node)

  parts = [_describe(child, columns) for child in node.get("children") or [] if applies(child, columns)]
  if not parts:
    return ""
  text = (" " + MATCH_JOINER[node["match"]] + " ").join(parts)
  if root or len(parts) == 1:
    return text
  return "(" + text + ")"


def _describe_rule(rule):
  right = str(rule["other"]) if rule.get("operand") == OPERAND_METRIC else _format_number(rule["value"])
  return str(rule["metric"]) + " " + OPERATOR_LABELS[rule["op"]] + " " + right


def _format_number(value):
  number = _number(value)
  if number is None:
    return str(value)
  if number == int(number):
    return str(int(number))
  return str(number)

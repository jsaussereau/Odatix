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
The rule builder: value conditions on metrics ("LUT < 1000", "Fmax > 100 and
FF < 2000", "(Fmax > 2) or (Fmax > 1 and LUT < 4)", "Fmax > Frequency"), shown
above the dimension checkboxes in the Filters tab.

One card per rule (metric, operator, then either a constant or another metric),
joined by clickable "and"/"or" chips that flip their group between match-all and
match-any. Groups nest, which is what expresses a mixed expression: each nested
group is a framed block with its own chips and its own add buttons.

Like the filter checklists, every id is pattern-based
({"type": "xp-rule-field", "id": ...}), so the panel can be rebuilt from the
rule state without changing the callback signature — and a missing panel (other
tab, no data) simply matches nothing.
"""

from dash import dcc, html

import odatix.explorer.core.rules as rules
import odatix.explorer.core.schema as schema
import odatix.explorer.ui.components as components


def rule_field_id(rule_id, field):
  return {"type": "xp-rule-field", "id": rule_id, "field": field}


def rule_remove_id(node_id):
  return {"type": "xp-rule-remove", "id": node_id}


def rule_action_id(action, group_id=rules.ROOT_ID):
  return {"type": "xp-rule-action", "action": action, "group": group_id}


def rule_match_id(group_id, index):
  return {"type": "xp-rule-match", "group": group_id, "index": index}


def rule_operand_id(rule_id):
  return {"type": "xp-rule-operand", "id": rule_id}


def _metric_label(metric, units):
  """Metric name plus its unit, as in the table headers."""
  name = schema.metric_display_name(metric)
  unit = str((units or {}).get(metric, "") or "")
  return name + " (" + unit + ")" if unit else name


def _right_operand(rule, metric_options, units):
  """The right-hand side of the comparison: a constant, or another metric."""
  if rule.get("operand") == rules.OPERAND_METRIC:
    return dcc.Dropdown(
      id=rule_field_id(rule["id"], "other"),
      options=metric_options,
      value=rule.get("other"),
      placeholder="Metric...",
      clearable=False,
      className="xp-dropdown xp-rule-other",
    )
  unit = str((units or {}).get(rule.get("metric"), "") or "") if rule.get("metric") else ""
  return html.Div(
    [
      dcc.Input(
        id=rule_field_id(rule["id"], "value"),
        type="number",
        value=rule.get("value"),
        placeholder="value",
        # Committed on Enter/blur only: the panel re-renders from the rule
        # state, and re-rendering on every keystroke would steal the focus.
        debounce=True,
        className="xp-text-input xp-rule-value",
      ),
      html.Span(unit, className="xp-rule-unit"),
    ],
    className="xp-rule-constant",
  )


def _operand_toggle(rule):
  """Switch the right-hand side between a constant and another metric."""
  to_metric = rule.get("operand") != rules.OPERAND_METRIC
  return html.Button(
    "123" if to_metric else "metric",
    id=rule_operand_id(rule["id"]),
    n_clicks=0,
    className="xp-rule-operand",
    title=(
      "Compared to a constant — click to compare to another metric"
      if to_metric
      else "Compared to another metric — click to compare to a constant"
    ),
  )


def _rule_card(rule, metric_options, units):
  """One rule: metric picker on top, operator + right-hand side below."""
  return html.Div(
    [
      html.Div(
        [
          dcc.Dropdown(
            id=rule_field_id(rule["id"], "metric"),
            options=metric_options,
            value=rule.get("metric"),
            placeholder="Metric...",
            clearable=False,
            className="xp-dropdown xp-rule-metric",
          ),
          html.Button(
            "✕",
            id=rule_remove_id(rule["id"]),
            n_clicks=0,
            className="xp-rule-remove",
            title="Remove this rule",
          ),
        ],
        className="xp-rule-head",
      ),
      html.Div(
        [
          dcc.Dropdown(
            id=rule_field_id(rule["id"], "op"),
            options=[{"label": label, "value": value} for value, label in rules.OPERATORS],
            value=rule.get("op", rules.DEFAULT_OPERATOR),
            clearable=False,
            searchable=False,
            className="xp-dropdown xp-rule-op",
          ),
          _right_operand(rule, metric_options, units),
          _operand_toggle(rule),
        ],
        className="xp-rule-body",
      ),
    ],
    className="xp-rule",
  )


def _match_chip(group, index):
  """The clickable "and"/"or" joiner between two children of a group."""
  match = group["match"]
  other = rules.MATCH_ANY if match == rules.MATCH_ALL else rules.MATCH_ALL
  return html.Div(
    html.Button(
      rules.MATCH_JOINER[match],
      id=rule_match_id(group["id"], index),
      n_clicks=0,
      className="xp-rule-match",
      title="Match " + match + " of these — click to switch to " + rules.MATCH_JOINER[other],
    ),
    className="xp-rule-match-row",
  )


def _group_actions(group, depth, can_clear):
  """"+ Rule" / "+ Group" (and "Clear" at the root) for one group."""
  buttons = [
    html.Button(
      "+ Rule",
      id=rule_action_id("add_rule", group["id"]),
      n_clicks=0,
      className="xp-mini-button xp-rule-add",
    )
  ]
  # Below the depth limit only: past it the sidebar becomes unreadable
  if depth < rules.MAX_DEPTH - 1:
    buttons.append(
      html.Button(
        "+ Group",
        id=rule_action_id("add_group", group["id"]),
        n_clicks=0,
        className="xp-mini-button xp-rule-add-group",
        title="A nested group, to mix and/or — e.g. A > 2 or (A > 1 and B < 4)",
      )
    )
  if depth == 0:
    buttons.append(
      html.Button(
        "Clear",
        id=rule_action_id("clear", group["id"]),
        n_clicks=0,
        className="xp-mini-button",
        disabled=not can_clear,
      )
    )
  return html.Div(buttons, className="xp-filter-buttons xp-rule-actions")


def _group_children(group, metric_options, units, depth):
  """The children of a group, with a match chip between each pair."""
  children = []
  for index, node in enumerate(group["children"]):
    if index:
      children.append(_match_chip(group, index))
    if node.get("kind") == "group":
      children.append(_group_card(node, metric_options, units, depth + 1))
    else:
      children.append(_rule_card(node, metric_options, units))
  return children


def _group_card(group, metric_options, units, depth):
  """A nested group: a framed block of rules with its own and/or and buttons."""
  return html.Div(
    [
      html.Div(
        [
          html.Span("Group", className="xp-rule-group-title"),
          html.Button(
            "✕",
            id=rule_remove_id(group["id"]),
            n_clicks=0,
            className="xp-rule-remove",
            title="Remove this group and its rules",
          ),
        ],
        className="xp-rule-group-head",
      ),
      html.Div(_group_children(group, metric_options, units, depth), className="xp-rule-group-body"),
      _group_actions(group, depth, can_clear=True),
    ],
    className="xp-rule-group",
  )


def build_rules_section(metrics, rule_state, units, matched=None, total=None):
  """
  Build the "Rules" section of the Filters tab.

  Args:
      metrics (list): numeric metrics of the current selection.
      rule_state (dict): the rule tree (see core.rules).
      units (dict): {metric: unit} of the current selection.
      matched / total (int | None): records kept by the rules, out of the
          records the dimension filters leave — shown as a live counter.
  """
  state = rules.normalize(rule_state)
  metric_options = [{"label": _metric_label(metric, units), "value": metric} for metric in metrics or []]

  children = []
  if not metrics:
    children.append(html.Div("No numeric metric in the current selection.", className="xp-filter-empty"))
  else:
    children.extend(_group_children(state, metric_options, units, depth=0))

    if not state["children"]:
      children.append(
        html.Div('No rule yet — e.g. "LUT < 1000" to hide the designs that do not fit.', className="xp-rule-empty")
      )

    children.append(_group_actions(state, depth=0, can_clear=bool(state["children"])))

    expression = rules.describe(state, metrics)
    if expression:
      children.append(html.Div(expression, className="xp-rule-expression", title="Rules currently applied"))

  right = None
  active = rules.count_rules(state, metrics)
  if active:
    right = html.Span(str(active), className="xp-rule-badge", title=str(active) + " active rule(s)")

  if active and matched is not None and total is not None:
    children.append(
      html.Div(
        "Keeps " + str(matched) + " of " + str(total) + " records",
        className="xp-rule-count" + (" xp-rule-count-empty" if matched == 0 else ""),
      )
    )

  return components.section("Rules", children, open=True, right=right)

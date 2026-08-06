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
FF < 2000"), shown above the dimension checkboxes in the Filters tab.

One card per rule (metric, operator, threshold), joined by clickable "and"/"or"
chips that flip the whole set between match-all and match-any. Like the filter
checklists, every id is pattern-based ({"type": "xp-rule-field", "id": ...}),
so the panel can be rebuilt from the rule state without changing the callback
signature — and a missing panel (other tab, no data) simply matches nothing.
"""

from dash import dcc, html

import odatix.explorer.core.rules as rules
import odatix.explorer.core.schema as schema
import odatix.explorer.ui.components as components


def rule_field_id(rule_id, field):
  return {"type": "xp-rule-field", "id": rule_id, "field": field}


def rule_remove_id(rule_id):
  return {"type": "xp-rule-remove", "id": rule_id}


def rule_action_id(action):
  return {"type": "xp-rule-action", "action": action}


def rule_match_id(index):
  return {"type": "xp-rule-match", "index": index}


def _metric_label(metric, units):
  """Metric name plus its unit, as in the table headers."""
  name = schema.metric_display_name(metric)
  unit = str((units or {}).get(metric, "") or "")
  return name + " (" + unit + ")" if unit else name


def _rule_card(rule, metric_options, units):
  """One rule: metric picker on top, operator + threshold below."""
  unit = str((units or {}).get(rule.get("metric"), "") or "") if rule.get("metric") else ""
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
        className="xp-rule-body",
      ),
    ],
    className="xp-rule",
  )


def _match_chip(index, match):
  """The clickable "and"/"or" joiner between two rules."""
  other = rules.MATCH_ANY if match == rules.MATCH_ALL else rules.MATCH_ALL
  return html.Div(
    html.Button(
      rules.MATCH_JOINER[match],
      id=rule_match_id(index),
      n_clicks=0,
      className="xp-rule-match",
      title="Match " + match + " the rules — click to switch to " + rules.MATCH_JOINER[other],
    ),
    className="xp-rule-match-row",
  )


def build_rules_section(metrics, rule_state, units, matched=None, total=None):
  """
  Build the "Rules" section of the Filters tab.

  Args:
      metrics (list): numeric metrics of the current selection.
      rule_state (dict): the rule set (see core.rules).
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
    for index, rule in enumerate(state["rules"]):
      if index:
        children.append(_match_chip(index, state["match"]))
      children.append(_rule_card(rule, metric_options, units))

    if not state["rules"]:
      children.append(
        html.Div('No rule yet — e.g. "LUT < 1000" to hide the designs that do not fit.', className="xp-rule-empty")
      )

    children.append(
      html.Div(
        [
          html.Button("+ Add rule", id=rule_action_id("add"), n_clicks=0, className="xp-mini-button xp-rule-add"),
          html.Button(
            "Clear",
            id=rule_action_id("clear"),
            n_clicks=0,
            className="xp-mini-button",
            disabled=not state["rules"],
          ),
        ],
        className="xp-filter-buttons xp-rule-actions",
      )
    )

    expression = rules.describe(state, metrics)
    if expression:
      children.append(html.Div(expression, className="xp-rule-expression", title="Rules currently applied"))

  right = None
  active = len(rules.applicable_rules(state, metrics))
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

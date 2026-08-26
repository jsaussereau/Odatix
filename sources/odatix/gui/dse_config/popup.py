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
What the popup shows before an exploration starts: what it is about to spend,
campaign by campaign, and whatever the check had to say.

It is the same plan the terminal prints when "odatix dse" asks "Continue?",
rendered rather than parsed -- what it shows comes from the campaigns
themselves (see :mod:`odatix.gui.dse_config.exploration`).
"""

from dash import html

import odatix.gui.ui_components as ui
from odatix.gui.dse_config import exploration

#: The severities the check reports, worst first.
SEVERITIES = ("error", "warning", "tip", "note")


def render_key(status):
    """
    What the body depends on. The popup is polled on a timer and its body is
    only replaced when this changes, or the sections the user opened would
    collapse under them.
    """
    return "{0}|{1}|{2}".format(
        status, len(exploration.plan), len(exploration.messages),
    )


def body(status):
    """The popup body for the current phase of the exploration."""
    if status == "checking" and not exploration.plan:
        return html.Div("Working out what the exploration would do...", className="dse-plan-waiting")

    children = [_totals()]
    messages = _messages()
    if messages is not None:
        children.append(messages)
    if exploration.plan:
        children.append(html.Div(
            [_campaign_card(entry) for entry in exploration.plan],
            className="dse-plan-body",
        ))
    return html.Div(children, className="dse-plan")


def _totals():
    """The one number an exploration is really about: how many designs it runs."""
    designs = sum(entry.get("budget", 0) for entry in exploration.plan)
    space = sum(entry.get("space", 0) for entry in exploration.plan)
    return html.Div(
        children=[
            ui.stat(len(exploration.plan), "campaign" if len(exploration.plan) == 1 else "campaigns"),
            ui.stat(designs, "designs to evaluate"),
            ui.stat(space, "designs in the space"),
        ],
        className="dse-plan-stats",
    )


def _messages():
    if not len(exploration.messages):
        return None
    rows = []
    for severity in SEVERITIES:
        for message in exploration.messages.of_level(severity):
            rows.append(html.Div(
                children=[
                    ui.badge(severity, color=_badge_color(severity)),
                    html.Span(message["message"]),
                    ui.badge("x{0}".format(message["count"])) if message["count"] > 1 else html.Span(),
                ],
                className="dse-plan-message {0}".format(severity),
            ))
    if not rows:
        return None
    return html.Div(rows, className="dse-plan-messages")


def _badge_color(severity):
    if severity == "error":
        return "caution"
    if severity == "warning":
        return "warning"
    return ""


def _campaign_card(entry):
    badges = [
        ui.badge(entry.get("strategy", ""), color="primary"),
        ui.badge("batches of {0}".format(entry.get("batch", 0))),
    ]
    if entry.get("mode") == "async":
        badges.append(ui.badge("continuous"))
    for label in entry.get("toolchains", [])[:3]:
        badges.append(ui.badge(label))
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Span(entry.get("name", ""), className="dse-plan-name"),
                    ui.badge(
                        "{0}/{1} designs".format(entry.get("budget", 0), entry.get("space", 0)),
                        color="success",
                    ),
                ],
                className="dse-plan-head",
            ),
            html.Div(badges, className="dse-plan-badges"),
            html.Div("Looking for: {0}.".format(entry.get("objectives", "")), className="dse-plan-objectives"),
            html.Div(entry.get("description", ""), className="dse-plan-description"),
        ],
        className="dse-plan-card",
    )

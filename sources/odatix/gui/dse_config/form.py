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
The rows of the campaign editor: the objectives, the constraints and the
architectures.

They are the three lists a campaign is really made of, and they are built here
rather than in the page because they are also rebuilt by it -- adding a row is
rendering the list again with one more, keeping what every other row holds.
"""

from dash import dcc, html

import odatix.gui.ui_components as ui
from odatix.gui.icons import icon

from odatix.gui.dse_config.common import GOAL_OPTIONS

METRIC_DATALIST = "dse-metric-names"


######################################
# One row
######################################

def _row(children, className=""):
    return html.Div(children, className=("dse-row " + className).strip())


def _delete(id):
    return ui.icon_button(
        icon=icon("delete", className="icon"),
        color="caution",
        id=id,
        tooltip="Remove",
        tooltip_options="bottom small",
    )


def _metric_input(id, value, placeholder="metric"):
    """A metric is a name in a results file: suggested, never imposed."""
    return dcc.Input(
        id=id,
        value=value or "",
        type="text",
        placeholder=placeholder,
        list=METRIC_DATALIST,
        className="dse-metric-input",
        autoComplete="off",
    )


def objective_row(index, metric="", goal="min"):
    return _row([
        _metric_input({"type": "dse-obj-metric", "index": index}, metric),
        dcc.Dropdown(
            id={"type": "dse-obj-goal", "index": index},
            options=GOAL_OPTIONS,
            value=goal if goal in ("min", "max") else "min",
            clearable=False,
            className="dse-row-dropdown",
        ),
        _delete({"type": "dse-obj-delete", "index": index}),
    ], "objective")


def constraint_row(index, metric="", minimum=None, maximum=None):
    return _row([
        _metric_input({"type": "dse-con-metric", "index": index}, metric),
        html.Span("\u2265", className="dse-bound-sign", title="at least"),
        dcc.Input(
            id={"type": "dse-con-min", "index": index},
            value="" if minimum is None else str(minimum),
            type="number",
            placeholder="min",
            className="dse-bound-input",
        ),
        html.Span("\u2264", className="dse-bound-sign", title="at most"),
        dcc.Input(
            id={"type": "dse-con-max", "index": index},
            value="" if maximum is None else str(maximum),
            type="number",
            placeholder="max",
            className="dse-bound-input",
        ),
        _delete({"type": "dse-con-delete", "index": index}),
    ], "constraint")


def architecture_row(index, name="", selection="", options=None):
    return _row([
        dcc.Dropdown(
            id={"type": "dse-arch-name", "index": index},
            options=options or [],
            value=name or None,
            placeholder="architecture",
            clearable=False,
            className="dse-row-dropdown wide",
        ),
        dcc.Input(
            id={"type": "dse-arch-selection", "index": index},
            value=selection or "",
            type="text",
            placeholder="every domain searched",
            className="dse-selection-input",
            autoComplete="off",
        ),
        _delete({"type": "dse-arch-delete", "index": index}),
    ], "architecture")


######################################
# The lists
######################################

def objective_rows(entries):
    if not entries:
        return [ui.empty_state("No objective yet: a search with nothing to look for cannot tell one design from another.")]
    return [objective_row(index, metric, goal) for index, (metric, goal) in enumerate(entries)]


def constraint_rows(entries):
    if not entries:
        return [ui.empty_state("No constraint: every design counts, whatever it measures.")]
    return [constraint_row(index, metric, minimum, maximum) for index, (metric, minimum, maximum) in enumerate(entries)]


def architecture_rows(entries, options):
    if not entries:
        return [ui.empty_state("No architecture: name at least one for the search to have a space to look in.")]
    return [architecture_row(index, name, selection, options) for index, (name, selection) in enumerate(entries)]


######################################
# Reading them back
######################################

def collect_objectives(metrics, goals):
    entries = []
    for metric, goal in zip(metrics or [], goals or []):
        metric = str(metric or "").strip()
        if not metric:
            continue
        entries.append({"metric": metric, "goal": goal if goal in ("min", "max") else "min"})
    return entries


def collect_constraints(metrics, minimums, maximums):
    from odatix.gui.dse_config.common import to_float

    entries = []
    for metric, minimum, maximum in zip(metrics or [], minimums or [], maximums or []):
        metric = str(metric or "").strip()
        if not metric:
            continue
        entry = {"metric": metric}
        low = to_float(minimum)
        high = to_float(maximum)
        if low is not None:
            entry["min"] = int(low) if float(low).is_integer() else low
        if high is not None:
            entry["max"] = int(high) if float(high).is_integer() else high
        if len(entry) == 1:
            # A constraint without a bound is not one: it would be refused when
            # the exploration reads it back, so it is dropped here instead.
            continue
        entries.append(entry)
    return entries


def collect_architectures(names, selections):
    from odatix.gui.dse_config.common import architecture_entry_text

    entries = []
    for name, selection in zip(names or [], selections or []):
        entry = architecture_entry_text(name, selection)
        if entry:
            entries.append(entry)
    return entries


def metric_datalist(names):
    """The suggestions every metric field of the page shares."""
    return html.Datalist(
        id=METRIC_DATALIST,
        children=[html.Option(value=name) for name in names],
    )

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
Derived Metrics Editor page (/derived_metrics).

Edits the workspace "derived_metrics.yml" (see odatix.lib.derived_metrics): the
metrics a result does not hold itself, but gets from another result. It is what
links simulation results to synthesis results -- a simulation knows how many
cycles a benchmark takes, a synthesis knows at which frequency the design runs,
and neither can give a runtime on its own.

Unlike the Exported Metrics Editor (/metric_editor), which says how a value is
read out of a run directory, this page says which *other result* a value comes
from. Both sections of the page are stored in the same file:

  - Groups: named lists of patterns, referenced as "@name" anywhere patterns are
    accepted. A group is not tied to architectures: the same mechanism names
    sets of simulations, workflows or targets.
  - Derived metrics: one card per metric, either imported from another kind of
    result ("from") or computed from the metrics a result already has
    ("operation").

The card layout follows the shared style of the Exported Metrics Editor: a title
input, a type dropdown that shows the fields of that type, and an expandable area
for the fields most metrics do not need.
"""

import dash
from dash import html, dcc, Input, Output, State, ctx

from odatix.gui.utils import get_workspace
import odatix.lib.derived_metrics as derived_metrics_lib
from odatix.gui.icons import icon
from odatix.gui.css_helper import Style
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
from odatix.gui.page_scope import page_callback, scoped

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "derived_metrics"

page_path = "/derived_metrics"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Derived Metrics Editor",
    name="Derived Metrics Editor",
    order=8,
)

METRIC_PREFIX = "dm"
GROUP_PREFIX = "dmgroup"

KIND_OPTIONS = [
    {"label": "Import from another result", "value": derived_metrics_lib.KIND_IMPORT},
    {"label": "Operation on other metrics", "value": derived_metrics_lib.KIND_OPERATION},
]

# "from" and "apply_to" both name kinds of results, so they share the options.
RESULT_TYPE_OPTIONS = [
    {"label": "Simulation", "value": "simulation"},
    {"label": "Workflow", "value": "workflow"},
    {"label": "Synthesis (any)", "value": "synthesis"},
    {"label": "Fmax synthesis", "value": "fmax_synthesis"},
    {"label": "Custom frequency synthesis", "value": "custom_freq_synthesis"},
    {"label": "Any", "value": "any"},
]

ON_MULTIPLE_OPTIONS = [{"label": choice, "value": choice} for choice in derived_metrics_lib.ON_MULTIPLE_CHOICES]

PAGE_TOOLTIP = (
    "Metrics a result gets from another result. Recomputed over the whole result set every "
    'time results are exported, and by "odatix res_derived".'
)
GROUP_TOOLTIP = (
    'A named list of patterns, used as "@name" in any pattern field of this page. Groups are not '
    "tied to architectures: the same group mechanism names sets of simulations, workflows or targets."
)


######################################
# Value <-> text conversions
######################################

def split_patterns(text):
    """A comma-separated pattern field into a list."""
    return [item.strip() for item in str(text or "").split(",") if item.strip() != ""]


def join_patterns(value):
    """A pattern list (or a single pattern) back into its comma-separated form."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value if item is not None)
    return str(value)


def split_mapping(text):
    """
    A "key: value, key: value" field into a dict. Used by the fields that are
    mappings in the file (match.pin, match.map).
    """
    mapping = {}
    for item in str(text or "").split(","):
        item = item.strip()
        if item == "" or ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip()
        if key != "":
            mapping[key] = value.strip()
    return mapping


def join_mapping(value):
    """A mapping back into its "key: value, key: value" form."""
    if not isinstance(value, dict):
        return ""
    return ", ".join(str(key) + ": " + str(item) for key, item in value.items())


def split_conditions(text):
    """
    A "key: pattern|pattern, key: pattern" field into a {key: [patterns]} dict.
    Used by the fields whose values are pattern lists (where, source_where).
    """
    conditions = {}
    for key, value in split_mapping(text).items():
        patterns = [pattern.strip() for pattern in str(value).split("|") if pattern.strip() != ""]
        if patterns:
            conditions[key] = patterns if len(patterns) > 1 else patterns[0]
    return conditions


def join_conditions(value):
    """A {key: patterns} mapping back into its "key: pattern|pattern" form."""
    if not isinstance(value, dict):
        return ""
    parts = []
    for key, patterns in value.items():
        if isinstance(patterns, (list, tuple)):
            parts.append(str(key) + ": " + "|".join(str(pattern) for pattern in patterns))
        else:
            parts.append(str(key) + ": " + str(patterns))
    return ", ".join(parts)


def as_type_list(value):
    """A "from"/"apply_to" value as the list the multi-dropdown holds."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def pack_type_list(values):
    """
    A multi-dropdown value back into what the file holds: a plain string when a
    single kind is selected, so the file stays as readable as it is hand-written.
    """
    values = [str(value) for value in (values or []) if value]
    if len(values) == 0:
        return None
    if len(values) == 1:
        return values[0]
    return values


######################################
# Definitions <-> card fields
######################################

def card_fields_of(definition):
    """The card field values of a derived metric definition."""
    definition = definition if isinstance(definition, dict) else {}

    kind = str(definition.get("type", "")).strip().lower()
    if kind not in (derived_metrics_lib.KIND_IMPORT, derived_metrics_lib.KIND_OPERATION):
        kind = (
            derived_metrics_lib.KIND_OPERATION
            if definition.get("op") is not None
            else derived_metrics_lib.KIND_IMPORT
        )

    match = definition.get("match")
    match = match if isinstance(match, dict) else {}

    return {
        "kind_value": kind,
        "from_value": as_type_list(definition.get("from")),
        "metric_value": str(definition.get("metric", "") or ""),
        "op_value": str(definition.get("op", "") or ""),
        "for_value": join_patterns(definition.get("for")),
        "apply_to_value": as_type_list(definition.get("apply_to", "synthesis")),
        "unit_value": str(definition.get("unit", "") or ""),
        "pin_value": join_mapping(match.get("pin")),
        "ignore_value": join_patterns(match.get("ignore")),
        "map_value": join_mapping(match.get("map")),
        "on_value": join_patterns(match.get("keys", match.get(True))),
        "on_multiple_value": str(definition.get("on_multiple", "error") or "error"),
        "where_value": join_conditions(definition.get("where")),
        "source_where_value": join_conditions(definition.get("source_where")),
        "optional_value": bool(definition.get("optional", False)),
        "overwrite_value": bool(definition.get("overwrite", False)),
    }


def build_metric_definition(
    kind, from_value, metric_value, op_value, for_value, apply_to_value, unit_value,
    pin_value, ignore_value, map_value, on_value, on_multiple_value,
    where_value, source_where_value, optional_value, overwrite_value,
):
    """
    Build one derived metric definition from its card fields.

    Only what the user actually set is written: a field left at its default is
    left out, so the file stays as short as the same definition written by hand.
    """
    definition = {"type": kind}

    if kind == derived_metrics_lib.KIND_IMPORT:
        source_types = pack_type_list(from_value)
        if source_types is not None:
            definition["from"] = source_types
        if str(metric_value or "").strip() != "":
            definition["metric"] = str(metric_value).strip()
    else:
        definition["op"] = str(op_value or "").strip()

    for_patterns = split_patterns(for_value)
    if for_patterns:
        definition["for"] = for_patterns if len(for_patterns) > 1 else for_patterns[0]

    apply_to = pack_type_list(apply_to_value)
    if apply_to is not None and apply_to != "synthesis":
        definition["apply_to"] = apply_to

    if str(unit_value or "").strip() != "":
        definition["unit"] = str(unit_value).strip()

    if kind == derived_metrics_lib.KIND_IMPORT:
        match = {}
        pin = split_mapping(pin_value)
        if pin:
            match["pin"] = pin
        ignore = split_patterns(ignore_value)
        if ignore:
            match["ignore"] = ignore
        mapping = split_mapping(map_value)
        if mapping:
            match["map"] = mapping
        on = split_patterns(on_value)
        if on:
            # "keys", not "on": YAML would read a bare "on" key as a boolean.
            match["keys"] = on
        if match:
            definition["match"] = match

        on_multiple = str(on_multiple_value or "error")
        if on_multiple != "error":
            definition["on_multiple"] = on_multiple

        source_where = split_conditions(source_where_value)
        if source_where:
            definition["source_where"] = source_where

    where = split_conditions(where_value)
    if where:
        definition["where"] = where

    if optional_value:
        definition["optional"] = True
    if overwrite_value:
        definition["overwrite"] = True

    return definition


def build_metrics_dict(
    names, kinds, from_vals, metric_vals, op_vals, for_vals, apply_to_vals, unit_vals,
    pin_vals, ignore_vals, map_vals, on_vals, on_multiple_vals,
    where_vals, source_where_vals, optional_vals, overwrite_vals,
):
    """Build the whole "derived_metrics" section from the card field values."""
    metrics = {}
    nb = len(names) if isinstance(names, list) else 0

    def value_at(values, idx, default=""):
        if isinstance(values, list) and idx < len(values) and values[idx] is not None:
            return values[idx]
        return default

    for idx in range(nb):
        name = str(names[idx]).strip() if names[idx] is not None else ""
        if name == "":
            continue
        metrics[name] = build_metric_definition(
            kind=str(value_at(kinds, idx, derived_metrics_lib.KIND_IMPORT)),
            from_value=value_at(from_vals, idx, []),
            metric_value=value_at(metric_vals, idx),
            op_value=value_at(op_vals, idx),
            for_value=value_at(for_vals, idx),
            apply_to_value=value_at(apply_to_vals, idx, []),
            unit_value=value_at(unit_vals, idx),
            pin_value=value_at(pin_vals, idx),
            ignore_value=value_at(ignore_vals, idx),
            map_value=value_at(map_vals, idx),
            on_value=value_at(on_vals, idx),
            on_multiple_value=value_at(on_multiple_vals, idx, "error"),
            where_value=value_at(where_vals, idx),
            source_where_value=value_at(source_where_vals, idx),
            optional_value=bool(value_at(optional_vals, idx, [])),
            overwrite_value=bool(value_at(overwrite_vals, idx, [])),
        )
    return metrics


def normalize_metrics(metrics):
    """
    Put the definitions read from the file through the same card round-trip the
    editor writes them back with.

    Without it, a definition the file leaves implicit (a missing "type", a single
    pattern written as a string) would differ from the one the cards rebuild, and
    the page would claim unsaved changes the moment it opens.
    """
    normalized = {}
    for name, definition in (metrics or {}).items():
        fields = card_fields_of(definition)
        normalized[str(name)] = build_metric_definition(
            kind=fields["kind_value"],
            from_value=fields["from_value"],
            metric_value=fields["metric_value"],
            op_value=fields["op_value"],
            for_value=fields["for_value"],
            apply_to_value=fields["apply_to_value"],
            unit_value=fields["unit_value"],
            pin_value=fields["pin_value"],
            ignore_value=fields["ignore_value"],
            map_value=fields["map_value"],
            on_value=fields["on_value"],
            on_multiple_value=fields["on_multiple_value"],
            where_value=fields["where_value"],
            source_where_value=fields["source_where_value"],
            optional_value=fields["optional_value"],
            overwrite_value=fields["overwrite_value"],
        )
    return normalized


def build_groups_dict(names, patterns_vals):
    """Build the "groups" section from the group card field values."""
    groups = {}
    nb = len(names) if isinstance(names, list) else 0
    for idx in range(nb):
        name = str(names[idx]).strip() if names[idx] is not None else ""
        if name == "":
            continue
        patterns = patterns_vals[idx] if isinstance(patterns_vals, list) and idx < len(patterns_vals) else ""
        groups[name] = split_patterns(patterns)
    return groups


######################################
# UI Components
######################################

def page_title():
    return html.Div(
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                html.H3("Derived Metrics", style={"marginBottom": "0px", "display": "inline-block"}),
                                ui.tooltip_icon(PAGE_TOOLTIP),
                            ],
                        ),
                        html.Div(
                            ui.save_button(
                                id={"page": page_path, "action": "save-all"},
                                tooltip="Save all changes",
                                disabled=True,
                            ),
                            className="inline-flex-buttons",
                        ),
                    ],
                    className="title-tile-flex",
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "padding": "0px",
                        "justifyContent": "space-between",
                    },
                ),
                ui.back_button(link="/workspace"),
            ],
            className="tile title",
            style={"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "0px", "marginBottom": "10px"},
    )


def card_field(name, field, label, value="", placeholder="", tooltip="", default_style=Style.visible, type="text"):
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Label(label, style={"fontWeight": "bold", "fontSize": "1em"}),
                    ui.tooltip_icon(tooltip) if tooltip else None,
                    dcc.Input(
                        value=value,
                        type=type,
                        placeholder=placeholder,
                        id={"type": f"{METRIC_PREFIX}-field-{field}", "name": name},
                        className="value-input",
                        style={
                            "width": "calc(100% - 10px)",
                            "marginLeft": "5px",
                            "marginRight": "5px",
                            "marginBottom": "5px",
                            "fontSize": "0.9em",
                            "height": "10px",
                            "zIndex": "900",
                            "padding": "15px 10px",
                        },
                    ),
                ],
                style={"marginTop": "5px", "width": "100%"},
            ),
        ],
        id={"type": f"{METRIC_PREFIX}-field-{field}-div", "name": name},
        style=default_style,
    )


def card_dropdown(name, field, label, options, value=None, multi=False, tooltip="", default_style=Style.visible, placeholder=""):
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Label(label, style={"fontWeight": "bold", "fontSize": "1em"}),
                    ui.tooltip_icon(tooltip) if tooltip else None,
                    dcc.Dropdown(
                        id={"type": f"{METRIC_PREFIX}-field-{field}", "name": name},
                        options=options,
                        value=value,
                        multi=multi,
                        clearable=multi,
                        placeholder=placeholder,
                        style={"fontSize": "0.95em", "zIndex": "900", "width": "100%"},
                    ),
                ],
                style={"marginTop": "5px", "width": "100%"},
            ),
        ],
        id={"type": f"{METRIC_PREFIX}-field-{field}-div", "name": name},
        style=default_style,
    )


def card_switch(name, field, label, checked=False, tooltip=""):
    return html.Div(
        children=[
            dcc.Checklist(
                options=[{"label": label, "value": True}],
                value=[True] if checked else [],
                id={"type": f"{METRIC_PREFIX}-field-{field}", "name": name},
                className="checklist-switch",
                style={"marginBottom": "4px", "display": "inline-block"},
            ),
            ui.tooltip_icon(tooltip) if tooltip else None,
        ],
    )


def metric_card(
    name,
    kind_value=derived_metrics_lib.KIND_IMPORT,
    from_value=None,
    metric_value="",
    op_value="",
    for_value="",
    apply_to_value=None,
    unit_value="",
    pin_value="",
    ignore_value="",
    map_value="",
    on_value="",
    on_multiple_value="error",
    where_value="",
    source_where_value="",
    optional_value=False,
    overwrite_value=False,
):
    """
    One derived metric card. The type dropdown decides which fields are shown:
    an imported metric needs to know which results to read, a computed one needs
    an expression.
    """
    is_import = kind_value == derived_metrics_lib.KIND_IMPORT
    import_style = Style.visible if is_import else Style.hidden
    operation_style = Style.hidden if is_import else Style.visible

    return html.Div([
        html.Div([
            dcc.Input(
                value=name,
                type="text",
                id={"type": f"{METRIC_PREFIX}-title", "name": name},
                className="title-input",
                style={
                    "width": "calc(100% - 20px)",
                    "marginLeft": "5px",
                    "marginRight": "5px",
                    "marginTop": "-5px",
                    "marginBottom": "2px",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "height": "10px",
                    "textAlign": "center",
                },
            ),
            dcc.Dropdown(
                id={"type": f"{METRIC_PREFIX}-kind", "name": name},
                options=KIND_OPTIONS,
                value=kind_value,
                clearable=False,
                style={"width": "100%"},
            ),
            html.Div(
                children=[
                    card_dropdown(
                        name, "from", "From", RESULT_TYPE_OPTIONS, value=from_value or [], multi=True,
                        default_style=import_style, placeholder="simulation",
                        tooltip="Which kind of result the value is read from.",
                    ),
                    card_field(
                        name, "metric", "Source Metric", value=metric_value, default_style=import_style,
                        placeholder="same name",
                        tooltip="Metric to read in the source result. Defaults to the name of this metric. Use \"meta.<key>\" (for instance \"meta.frequency\") to read a meta field instead of a metric.",
                    ),
                    card_field(
                        name, "op", "Operation", value=op_value, default_style=operation_style,
                        placeholder="Cycles / Frequency",
                        tooltip="Expression evaluated from the metrics the result already has, imported ones included. \"meta.<key>\" (for instance \"meta.frequency\") reads a meta field of the result.",
                    ),
                    card_field(
                        name, "for", "For", value=for_value, placeholder="* or @cpus",
                        tooltip=(
                            "Which results get this metric: a pattern, a comma-separated list, or "
                            '"@group". Matched against the architecture (alone and as '
                            '"architecture/configuration"), the workflow and the simulation. Empty means all.'
                        ),
                    ),
                    card_field(
                        name, "pin", "Pin", value=pin_value, default_style=import_style,
                        placeholder="MEM: 1024I_1024D",
                        tooltip=(
                            "Read this exact value of a parameter domain in the source, whatever the value of "
                            "the result getting the metric. Not needed when the simulation declares the domain "
                            "invariant."
                        ),
                    ),
                    html.Div(
                        children=[
                            card_dropdown(
                                name, "apply_to", "Apply To", RESULT_TYPE_OPTIONS,
                                value=apply_to_value if apply_to_value is not None else ["synthesis"],
                                multi=True, placeholder="synthesis",
                                tooltip="Which kinds of result get this metric (default: synthesis).",
                            ),
                            card_field(
                                name, "unit", "Unit", value=unit_value, placeholder="us",
                                tooltip="Optional unit recorded with the metric.",
                            ),
                            card_field(
                                name, "ignore", "Ignore Domains", value=ignore_value, default_style=import_style,
                                placeholder="Voltage, Corner",
                                tooltip="Parameter domains the match must not constrain at all.",
                            ),
                            card_field(
                                name, "map", "Map Domains", value=map_value, default_style=import_style,
                                placeholder="MEM: Cache",
                                tooltip='Domains named differently on each side, written "source: target".',
                            ),
                            card_field(
                                name, "on", "Match On", value=on_value, default_style=import_style,
                                placeholder="architecture, configuration",
                                tooltip=(
                                    "Match on exactly these dimensions and nothing else. Empty (the default) "
                                    "matches on every dimension the two results have in common."
                                ),
                            ),
                            card_dropdown(
                                name, "on_multiple", "On Multiple Matches", ON_MULTIPLE_OPTIONS,
                                value=on_multiple_value, default_style=import_style,
                                tooltip="What to do when several source results match.",
                            ),
                            card_field(
                                name, "where", "Where", value=where_value,
                                placeholder="target: xc7a100t*",
                                tooltip=(
                                    "Extra condition on the results that get this metric, written "
                                    '"meta key: pattern". Several patterns are separated by "|".'
                                ),
                            ),
                            card_field(
                                name, "source_where", "Source Where", value=source_where_value,
                                default_style=import_style, placeholder="simulation: @benchmarks",
                                tooltip="Same, but on the results the value is read from.",
                            ),
                            card_switch(
                                name, "optional", "Optional", checked=optional_value,
                                tooltip="Do not warn when no source result matches.",
                            ),
                            card_switch(
                                name, "overwrite", "Overwrite", checked=overwrite_value,
                                tooltip="Replace the value even when the result already has a metric of that name.",
                            ),
                        ],
                        id={"type": f"{METRIC_PREFIX}-more-field-div", "name": name},
                        className="expandable-area",
                        style=Style.hidden,
                    ),
                ],
            ),
        ]),
        html.Div([
            html.Div([
                ui.icon_button(
                    icon=icon("more", className="icon normal rotate", id={"type": f"{METRIC_PREFIX}-more-fields-icon", "name": name}),
                    color="default",
                    id={"type": f"{METRIC_PREFIX}-more-fields", "name": name},
                    tooltip="Show/Hide extra fields",
                    tooltip_options="bottom small",
                )
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": f"{METRIC_PREFIX}-duplicate", "name": name}),
                ui.delete_button(id={"type": f"{METRIC_PREFIX}-delete", "name": name}),
            ], style={"display": "flex", "flexDirection": "horizontal", "alignItems": "center", "gap": "5px"}),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
    ],
    className="card configs",
    id={"type": f"{METRIC_PREFIX}-card", "name": name},
    style={
        "padding": "10px",
        "margin": "5px",
        "display": "inline-block",
        "verticalAlign": "top",
    })


def metric_card_from_def(name, definition):
    return metric_card(name, **card_fields_of(definition))


def group_card(name, patterns_value=""):
    """One group card: a name and the patterns it stands for."""
    return html.Div([
        html.Div([
            dcc.Input(
                value=name,
                type="text",
                id={"type": f"{GROUP_PREFIX}-title", "name": name},
                className="title-input",
                style={
                    "width": "calc(100% - 20px)",
                    "marginLeft": "5px",
                    "marginRight": "5px",
                    "marginTop": "-5px",
                    "marginBottom": "2px",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "height": "10px",
                    "textAlign": "center",
                },
            ),
            html.Div(
                children=[
                    html.Label("Patterns", style={"fontWeight": "bold", "fontSize": "1em"}),
                    ui.tooltip_icon(
                        'Comma-separated glob patterns, e.g. "AsteRISC/*, Ibex/*". A group may reference '
                        'another one with "@name".'
                    ),
                    dcc.Input(
                        value=patterns_value,
                        type="text",
                        placeholder="AsteRISC/*, Ibex/*",
                        id={"type": f"{GROUP_PREFIX}-field-patterns", "name": name},
                        className="value-input",
                        style={
                            "width": "calc(100% - 10px)",
                            "marginLeft": "5px",
                            "marginRight": "5px",
                            "marginBottom": "5px",
                            "fontSize": "0.9em",
                            "height": "10px",
                            "padding": "15px 10px",
                        },
                    ),
                ],
                style={"marginTop": "5px", "width": "100%"},
            ),
        ]),
        html.Div([
            html.Div(),
            html.Div([
                ui.duplicate_button(id={"type": f"{GROUP_PREFIX}-duplicate", "name": name}),
                ui.delete_button(id={"type": f"{GROUP_PREFIX}-delete", "name": name}),
            ], style={"display": "flex", "flexDirection": "horizontal", "alignItems": "center", "gap": "5px"}),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
    ],
    className="card configs",
    id={"type": f"{GROUP_PREFIX}-card", "name": name},
    style={
        "padding": "10px",
        "margin": "5px",
        "display": "inline-block",
        "verticalAlign": "top",
    })


def add_card(prefix, text):
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "paddingTop": "20px"}),
                    html.Div("+", style={"fontSize": "2.5em", "lineHeight": "80px", "height": "80px"}),
                ],
                style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
            ),
            id=f"{prefix}-new",
            n_clicks=0,
            style={"textDecoration": "none", "height": "100%"},
        ),
        className="card configs add hover",
        id=f"{prefix}-add-card",
        style={
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box",
        },
    )


def metric_cards(metrics):
    cards = [metric_card_from_def(name, definition) for name, definition in (metrics or {}).items()]
    cards.append(add_card(METRIC_PREFIX, "Add new derived metric"))
    return cards


def group_cards(groups):
    cards = [group_card(name, join_patterns(patterns)) for name, patterns in (groups or {}).items()]
    cards.append(add_card(GROUP_PREFIX, "Add new group"))
    return cards


def card_id_of(card):
    return card.get("props", {}).get("id") if isinstance(card, dict) else None


def unique_name(existing, stem):
    if stem not in existing:
        return stem
    idx = 1
    while f"{stem}{idx}" in existing:
        idx += 1
    return f"{stem}{idx}"


######################################
# Callbacks
######################################

@dash.callback(
    Output(f"{METRIC_PREFIX}-cards-row", "children", allow_duplicate=True),
    Input(f"{METRIC_PREFIX}-new", "n_clicks"),
    Input({"type": f"{METRIC_PREFIX}-duplicate", "name": dash.ALL}, "n_clicks"),
    Input({"type": f"{METRIC_PREFIX}-delete", "name": dash.ALL}, "n_clicks"),
    State(f"{METRIC_PREFIX}-cards-row", "children"),
    State({"type": f"{METRIC_PREFIX}-title", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-kind", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-from", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-metric", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-op", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-for", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-apply_to", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-unit", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-pin", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-ignore", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-map", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-on", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-on_multiple", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-where", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-source_where", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-optional", "name": dash.ALL}, "value"),
    State({"type": f"{METRIC_PREFIX}-field-overwrite", "name": dash.ALL}, "value"),
    prevent_initial_call=True,
)
def update_metric_cards(
    new_click, duplicate_clicks, delete_clicks, cards,
    names, kinds, from_vals, metric_vals, op_vals, for_vals, apply_to_vals, unit_vals,
    pin_vals, ignore_vals, map_vals, on_vals, on_multiple_vals,
    where_vals, source_where_vals, optional_vals, overwrite_vals,
):
    trigger_id = ctx.triggered_id
    cards = [card for card in (cards or []) if card_id_of(card) != f"{METRIC_PREFIX}-add-card"]

    definitions = build_metrics_dict(
        names, kinds, from_vals, metric_vals, op_vals, for_vals, apply_to_vals, unit_vals,
        pin_vals, ignore_vals, map_vals, on_vals, on_multiple_vals,
        where_vals, source_where_vals, optional_vals, overwrite_vals,
    )
    existing = list(definitions.keys())

    if trigger_id == f"{METRIC_PREFIX}-new" and new_click:
        definitions[unique_name(existing, "new_metric")] = {"type": derived_metrics_lib.KIND_IMPORT}
        return metric_cards(definitions)

    if isinstance(trigger_id, dict):
        trig_type = trigger_id.get("type")
        trig_name = trigger_id.get("name")

        idx = None
        for i, card in enumerate(cards):
            cid = card_id_of(card)
            if isinstance(cid, dict) and cid.get("name") == trig_name:
                idx = i
                break

        if trig_type == f"{METRIC_PREFIX}-delete" and idx is not None and idx < len(delete_clicks) and delete_clicks[idx]:
            definitions.pop(trig_name, None)
            return metric_cards(definitions)

        if trig_type == f"{METRIC_PREFIX}-duplicate" and idx is not None and idx < len(duplicate_clicks) and duplicate_clicks[idx]:
            source = definitions.get(trig_name, {})
            definitions[unique_name(existing, f"{trig_name}_copy")] = dict(source)
            return metric_cards(definitions)

    return dash.no_update


@dash.callback(
    Output(f"{GROUP_PREFIX}-cards-row", "children", allow_duplicate=True),
    Input(f"{GROUP_PREFIX}-new", "n_clicks"),
    Input({"type": f"{GROUP_PREFIX}-duplicate", "name": dash.ALL}, "n_clicks"),
    Input({"type": f"{GROUP_PREFIX}-delete", "name": dash.ALL}, "n_clicks"),
    State(f"{GROUP_PREFIX}-cards-row", "children"),
    State({"type": f"{GROUP_PREFIX}-title", "name": dash.ALL}, "value"),
    State({"type": f"{GROUP_PREFIX}-field-patterns", "name": dash.ALL}, "value"),
    prevent_initial_call=True,
)
def update_group_cards(new_click, duplicate_clicks, delete_clicks, cards, names, patterns_vals):
    trigger_id = ctx.triggered_id
    cards = [card for card in (cards or []) if card_id_of(card) != f"{GROUP_PREFIX}-add-card"]

    groups = build_groups_dict(names, patterns_vals)
    existing = list(groups.keys())

    if trigger_id == f"{GROUP_PREFIX}-new" and new_click:
        groups[unique_name(existing, "new_group")] = []
        return group_cards(groups)

    if isinstance(trigger_id, dict):
        trig_type = trigger_id.get("type")
        trig_name = trigger_id.get("name")

        idx = None
        for i, card in enumerate(cards):
            cid = card_id_of(card)
            if isinstance(cid, dict) and cid.get("name") == trig_name:
                idx = i
                break

        if trig_type == f"{GROUP_PREFIX}-delete" and idx is not None and idx < len(delete_clicks) and delete_clicks[idx]:
            groups.pop(trig_name, None)
            return group_cards(groups)

        if trig_type == f"{GROUP_PREFIX}-duplicate" and idx is not None and idx < len(duplicate_clicks) and duplicate_clicks[idx]:
            groups[unique_name(existing, f"{trig_name}_copy")] = list(groups.get(trig_name, []))
            return group_cards(groups)

    return dash.no_update


@page_callback(PAGE_SCOPE,
    Output({"type": f"{METRIC_PREFIX}-field-from-div", "name": dash.MATCH}, "style"),
    Output({"type": f"{METRIC_PREFIX}-field-metric-div", "name": dash.MATCH}, "style"),
    Output({"type": f"{METRIC_PREFIX}-field-op-div", "name": dash.MATCH}, "style"),
    Output({"type": f"{METRIC_PREFIX}-field-pin-div", "name": dash.MATCH}, "style"),
    Output({"type": f"{METRIC_PREFIX}-field-ignore-div", "name": dash.MATCH}, "style"),
    Output({"type": f"{METRIC_PREFIX}-field-map-div", "name": dash.MATCH}, "style"),
    Output({"type": f"{METRIC_PREFIX}-field-on-div", "name": dash.MATCH}, "style"),
    Output({"type": f"{METRIC_PREFIX}-field-on_multiple-div", "name": dash.MATCH}, "style"),
    Output({"type": f"{METRIC_PREFIX}-field-source_where-div", "name": dash.MATCH}, "style"),
    Input({"type": f"{METRIC_PREFIX}-kind", "name": dash.MATCH}, "value"),
)
def toggle_kind_fields(kind):
    """Only the fields of the selected kind are shown: what an imported metric
    needs to find its source is meaningless for a computed one, and the other
    way round."""
    is_import = kind == derived_metrics_lib.KIND_IMPORT
    import_style = Style.visible if is_import else Style.hidden
    operation_style = Style.hidden if is_import else Style.visible
    return (
        import_style, import_style, operation_style,
        import_style, import_style, import_style, import_style, import_style, import_style,
    )


# Folding the extra fields away is done on the client, on the document, by the
# handler in assets/folds.js: nothing outside the browser reads whether a fold
# is open, and a fold answered by Dash costs a walk over every pattern-matched
# component of the page.


@dash.callback(
    Output(f"{METRIC_PREFIX}-cards-row", "children"),
    Output(f"{GROUP_PREFIX}-cards-row", "children"),
    Output("dm-initial", "data"),
    Input(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_page(page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update, dash.no_update

    derived = get_workspace(odatix_settings).derived_metrics
    groups, metrics = derived.groups, derived.metrics
    initial = {
        "groups": build_groups_dict(list(groups.keys()), [join_patterns(v) for v in groups.values()]),
        "metrics": normalize_metrics(metrics),
    }
    return metric_cards(metrics), group_cards(groups), initial


@page_callback(PAGE_SCOPE,
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output("dm-saved", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input({"type": f"{METRIC_PREFIX}-title", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-kind", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-from", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-metric", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-op", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-for", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-apply_to", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-unit", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-pin", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-ignore", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-map", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-on", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-on_multiple", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-where", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-source_where", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-optional", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-overwrite", "name": dash.ALL}, "value"),
    Input({"type": f"{GROUP_PREFIX}-title", "name": dash.ALL}, "value"),
    Input({"type": f"{GROUP_PREFIX}-field-patterns", "name": dash.ALL}, "value"),
    State(f"url_{page_path}", "pathname"),
    State("dm-initial", "data"),
    State("dm-saved", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(
    n_clicks,
    names, kinds, from_vals, metric_vals, op_vals, for_vals, apply_to_vals, unit_vals,
    pin_vals, ignore_vals, map_vals, on_vals, on_multiple_vals,
    where_vals, source_where_vals, optional_vals, overwrite_vals,
    group_names, group_patterns,
    page, initial, saved, odatix_settings,
):
    if page != page_path:
        return dash.no_update, dash.no_update, dash.no_update

    disabled = ("color-button disabled icon-button tooltip delay bottom small", "Nothing to save")
    warning = ("color-button warning icon-button tooltip bottom small", "Unsaved changes!")
    error = "color-button error-status icon-button tooltip bottom small"

    current = {
        "groups": build_groups_dict(group_names, group_patterns),
        "metrics": build_metrics_dict(
            names, kinds, from_vals, metric_vals, op_vals, for_vals, apply_to_vals, unit_vals,
            pin_vals, ignore_vals, map_vals, on_vals, on_multiple_vals,
            where_vals, source_where_vals, optional_vals, overwrite_vals,
        ),
    }
    reference = saved if isinstance(saved, dict) else initial

    if ctx.triggered_id == {"page": page_path, "action": "save-all"}:
        try:
            derived = get_workspace(odatix_settings).derived_metrics
            derived.groups = current["groups"]
            derived.metrics = current["metrics"]
            derived.save()
            return disabled[0], disabled[1], current
        except Exception:
            return error, "Failed to save...", dash.no_update

    if not isinstance(reference, dict) or current != reference:
        return warning[0], warning[1], dash.no_update

    return disabled[0], disabled[1], dash.no_update


######################################
# Layout
######################################

METRIC_SECTION_TOOLTIP = (
    "One card per derived metric. An imported metric copies a value from another kind of "
    "result; an operation computes one from the metrics a result already has."
)


def _section_block(prefix, title, tooltip, add_text):
    """One editable section: its title tile + its cards row, as in /metric_editor."""
    return html.Div(
        children=[
            ui.title_tile(text=title, id=f"{prefix}-section-title", tooltip=tooltip),
            html.Div([
                html.Div(
                    id=f"{prefix}-cards-row",
                    children=[add_card(prefix, add_text)],
                    className="card-matrix configs",
                    style={"marginBottom": "30px"},
                ),
            ]),
        ],
        id=f"{prefix}-section-wrapper",
    )


layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        html.Div(page_title(), style={"marginTop": "20px"}),
        _section_block(GROUP_PREFIX, "Groups", GROUP_TOOLTIP, "Add new group"),
        _section_block(METRIC_PREFIX, "Derived Metrics", METRIC_SECTION_TOOLTIP, "Add new derived metric"),
        dcc.Store(id="dm-initial", data={"groups": {}, "metrics": {}}),
        dcc.Store(id="dm-saved", data=None),
    ],
    className="page-content",
    style={
        "padding": "0 16%",
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

# Anchor of PAGE_SCOPE: makes this page the only one dispatching its callbacks.
layout = scoped(PAGE_SCOPE, layout)

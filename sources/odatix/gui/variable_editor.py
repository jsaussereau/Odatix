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
Shared configuration-variable editor used by both the Configuration Generator
page and the Workflow Editor page.

Every page renders the same variable cards (a type dropdown plus the fields of
that type) and turns them into a ``generate_configurations_settings.variables``
dict. The only thing that differs between the two pages is the id namespace, so
every component id is built from a ``prefix`` argument ("" for the configuration
generator, "wf-" for the workflow editor). Keeping this in one module means a
change to the variable model (e.g. adding the "group"/pairing field) applies to
both pages at once.
"""

from typing import Optional

from dash import html, dcc

import odatix.gui.ui_components as ui
from odatix.gui.css_helper import Style
from odatix.gui.icons import icon
import odatix.components.workspace as workspace

# Type dropdown options, shared by every variable card.
VARIABLE_TYPE_OPTIONS = [
    {"label": "Boolean", "value": "bool"},
    {"label": "List", "value": "list"},
    {"label": "Range", "value": "range"},
    {"label": "Power of 2", "value": "power_of_two"},
    {"label": "Multiples", "value": "multiples"},
    {"label": "Function", "value": "function"},
    {"label": "Conversion", "value": "conversion"},
    {"label": "Format", "value": "format"},
    {"label": "Union", "value": "union"},
    {"label": "Disjunctive Union", "value": "disjunctive_union"},
    {"label": "Intersection", "value": "intersection"},
    {"label": "Difference", "value": "difference"},
]

# Every optional field a variable card can display, in render order.
VARIABLE_FIELDS = [
    "from", "to", "from_2_pow", "to_2_pow", "from_type", "to_type",
    "base", "step", "op", "list", "source", "sources", "format", "group",
]

# Which fields are shown for each variable type. "group" (pairing) is offered
# for every type that produces a dimension of values (i.e. not the computed
# combo types: function/conversion/format).
FIELD_VISIBILITY = {
    "bool":              {"format", "group"},
    "list":              {"list", "format", "group"},
    "range":             {"from", "to", "step", "format", "group"},
    "power_of_two":      {"from_2_pow", "to_2_pow", "format", "group"},
    "multiples":         {"base", "from", "to", "format", "group"},
    "function":          {"op", "format"},
    "conversion":        {"from_type", "to_type", "source", "format"},
    "format":            {"source", "format"},
    "union":             {"sources", "format", "group"},
    "disjunctive_union": {"sources", "format", "group"},
    "intersection":      {"sources", "format", "group"},
    "difference":        {"sources", "format", "group"},
}


######################################
# Pure logic (namespace-independent)
######################################

def field_styles_for_types(types):
    """
    Compute the per-field visibility styles for a list of variable types.

    Returns:
        dict: field name -> list of styles (one per variable card), matching the
        order of VARIABLE_FIELDS. Feed each list to the matching Output of the
        page's field-visibility callback.
    """
    styles_by_field = {field: [] for field in VARIABLE_FIELDS}
    for variable_type in types:
        visible = FIELD_VISIBILITY.get(variable_type, set())
        for field in VARIABLE_FIELDS:
            styles_by_field[field].append(Style.visible if field in visible else Style.hidden)
    return styles_by_field


def build_variables_dict(
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals,
    from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals,
    sources_vals, format_vals, group_vals,
):
    """
    Build a ``generate_configurations_settings.variables`` dict from the values
    of the variable card fields (one entry per index).
    """
    variables = {}
    for idx, title in enumerate(titles):
        variable_type = types[idx]
        settings = {}
        var_format = format_vals[idx] if format_vals[idx] else None
        if variable_type == "range":
            settings["from"] = int(from_vals[idx]) if from_vals[idx] else 0
            settings["to"] = int(to_vals[idx]) if to_vals[idx] else 0
            settings["step"] = int(step_vals[idx]) if step_vals[idx] else 1
        elif variable_type == "power_of_two":
            settings["from_2^"] = int(from_2_pow_vals[idx]) if from_2_pow_vals[idx] else 0
            settings["to_2^"] = int(to_2_pow_vals[idx]) if to_2_pow_vals[idx] else 0
        elif variable_type == "list":
            settings["list"] = [x.strip() for x in list_vals[idx].split(",") if x.strip()] if list_vals[idx] else []
        elif variable_type == "multiples":
            settings["base"] = int(base_vals[idx]) if base_vals[idx] else 1
            settings["from"] = int(from_vals[idx]) if from_vals[idx] else 0
            settings["to"] = int(to_vals[idx]) if to_vals[idx] else 0
        elif variable_type == "function":
            settings["op"] = op_vals[idx] if op_vals[idx] else ""
        elif variable_type == "conversion":
            settings["from"] = from_type_vals[idx] if from_type_vals[idx] else 0
            settings["to"] = to_type_vals[idx] if to_type_vals[idx] else 0
            settings["source"] = source_vals[idx] if source_vals[idx] else ""
        elif variable_type == "format":
            settings["source"] = source_vals[idx] if source_vals[idx] else ""
        elif variable_type in {"union", "disjunctive_union", "intersection", "difference"}:
            settings["sources"] = [x.strip() for x in sources_vals[idx].split(",") if x.strip()] if sources_vals[idx] else []
        group = group_vals[idx] if group_vals[idx] else None
        variable = workspace.create_config_gen_variable_dict(name=title, type=variable_type, settings=settings, format=var_format, group=group)
        variables.update(variable)
    return variables


def field_value_changed(current, reference):
    """
    Compare a live field value with the value stored in the variable metadata.
    Empty inputs are reported as None by Dash (number inputs in particular),
    while the metadata holds an empty string, so both are normalized first.
    """
    def normalize(value):
        return "" if value is None else str(value).strip()

    return normalize(current) != normalize(reference)


def toggle_more_fields(n_clicks, expandable_area_styles, icon_classes, names, trigger_name):
    """
    Toggle the "more fields" expandable area of the card whose name matches
    trigger_name, returning the updated (styles, icon classes) lists.
    """
    index = None
    for i, current_name in enumerate(names):
        if trigger_name == current_name:
            index = i
            break

    new_expandable_area_styles = list(expandable_area_styles)
    new_icon_classes = list(icon_classes)
    if index is not None:
        if n_clicks[index] % 2 == 0:
            new_expandable_area_styles[index] = Style.hidden
            new_icon_classes[index] = "icon normal rotate"
        else:
            new_expandable_area_styles[index] = Style.visible
            new_icon_classes[index] = "icon normal rotate rotated"
    return new_expandable_area_styles, new_icon_classes


######################################
# Components (namespaced by prefix)
######################################

def variable_field(
    prefix: str,
    var: str,
    name: str = "",
    label: Optional[str] = None,
    type="text",
    options: Optional[list] = None,
    value: str = "",
    placeholder: str = "",
    default_style: dict = Style.hidden,
    tooltip: str = "",
    tooltip_options: str = "secondary",
):
    """One labelled field of a variable card (input or dropdown)."""
    if label is None:
        label = name
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Label(label, style={"fontWeight": "bold", "fontSize": "1em"}),
                    ui.tooltip_icon(tooltip, tooltip_options) if tooltip else None,
                    dcc.Input(
                        value=value,
                        type=type,
                        placeholder=placeholder,
                        id={"type": f"{prefix}variable-field-{name}", "name": var},
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
                    ) if options is None else dcc.Dropdown(
                        id={"type": f"{prefix}variable-field-{name}", "name": var},
                        options=options,
                        value=value,
                        clearable=False,
                        style={
                            "fontSize": "0.95em",
                            "zIndex": "900",
                            "width": "100%",
                        },
                    ),
                ],
                style={"marginTop": "5px", "width": "100%"},
            ),
        ],
        id={"type": f"{prefix}variable-field-{name}-div", "name": var},
        style=default_style,
    )


def variable_card(
    prefix: str,
    name,
    type_value="list",
    base_value="", from_value="", to_value="",
    from_2_pow_value="", to_2_pow_value="", step_value="1",
    from_type_value="dec", to_type_value="hex",
    op_value="", list_value="", source_value="", sources_value="", format_value="", group_value="",
):
    """A full variable definition card (title, type dropdown, fields, actions)."""
    return html.Div([
        html.Div([
            dcc.Input(
                value=name,
                type="text",
                id={"type": f"{prefix}variable-title", "name": name},
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
                id={"type": f"{prefix}variable-type", "name": name},
                options=VARIABLE_TYPE_OPTIONS,
                value=type_value,
                clearable=False,
                style={"width": "100%"},
            ),
            html.Div(
                children=[
                    variable_field(prefix, var=name, name="from", label="From", type="number", value=from_value),
                    variable_field(prefix, var=name, name="to", label="To", type="number", value=to_value),
                    variable_field(prefix, var=name, name="from_2_pow", label="From 2^", type="number", value=from_2_pow_value),
                    variable_field(prefix, var=name, name="to_2_pow", label="To 2^", type="number", value=to_2_pow_value),
                    variable_field(prefix, var=name, name="from_type", label="From type", type="text", options=[{"label": "Bin", "value": "bin"}, {"label": "Dec", "value": "dec"}, {"label": "Hex", "value": "hex"}], value=from_type_value),
                    variable_field(prefix, var=name, name="to_type", label="To type", type="text", options=[{"label": "Bin", "value": "bin"}, {"label": "Dec", "value": "dec"}, {"label": "Hex", "value": "hex"}], value=to_type_value),
                    variable_field(prefix, var=name, name="base", label="Base", type="number", value=base_value),
                    variable_field(prefix, var=name, name="step", label="Step", type="number", value=step_value),
                    variable_field(prefix, var=name, name="op", label="Op", type="text", value=op_value),
                    variable_field(prefix, var=name, name="list", label="List", type="text", placeholder="Comma-separated values", default_style=Style.visible, value=list_value),
                    variable_field(prefix, var=name, name="source", label="Source", type="text", value=source_value),
                    variable_field(prefix, var=name, name="sources", label="Sources", type="text", placeholder="Comma-separated values", value=sources_value),
                    html.Div(
                        children=[
                            variable_field(prefix, var=name, name="format", label="Format", type="text", value=format_value),
                            variable_field(
                                prefix, var=name, name="group", label="Variable group", type="text",
                                placeholder="Zip with same-group variables", value=group_value,
                                tooltip="Variables sharing the same group name are paired: their values are matched "
                                        "position by position (like zip) instead of being combined with every other value. "
                                        "Paired variables must have the same number of values. Leave empty for no pairing.",
                            ),
                        ],
                        id={"type": f"{prefix}more-variable-field-div", "name": name},
                        className="expandable-area",
                        style=Style.hidden,
                    ),
                ],
                id="variable-fields-container",
            ),
        ]),
        html.Div([
            html.Div([
                ui.icon_button(
                    icon=icon("more", className="icon normal rotate", id={"type": f"{prefix}more-fields-icon", "name": name}),
                    color="default",
                    id={"type": f"{prefix}more-fields", "name": name},
                    tooltip="Show/Hide extra fields",
                    tooltip_options="bottom small",
                )
            ], id={"type": f"{prefix}more-fields-div", "name": name}, style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": f"{prefix}duplicate-var", "name": name}),
                ui.delete_button(id={"type": f"{prefix}delete-var", "name": name}),
            ], style={"display": "flex", "flexDirection": "hotizontal", "alignItems": "center", "gap": "5px"}),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
        dcc.Store(id={"type": f"{prefix}variable-metadata", "name": name}, data={"name": name, "type": type_value, "base_value": base_value, "from_value": from_value, "to_value": to_value, "from_2_pow_value": from_2_pow_value, "to_2_pow_value": to_2_pow_value, "from_type_value": from_type_value, "to_type_value": to_type_value, "step_value": step_value, "op_value": op_value, "list_value": list_value, "source_value": source_value, "sources_value": sources_value, "format_value": format_value, "group_value": group_value}),
    ],
    className="card configs",
    id={"type": f"{prefix}variable-card", "name": name},
    style={
        "padding": "10px",
        "margin": "5px",
        "display": "inline-block",
        "verticalAlign": "top",
    })


def variable_card_from_config(prefix: str, var_name, var_keys):
    """Build a variable card from a single ``variables`` dict entry."""
    def field(source, key, default=""):
        """Field value as a string, treating a missing and a None value alike."""
        value = source.get(key) if isinstance(source, dict) else None
        return default if value is None else str(value)

    var_settings = var_keys.get("settings", {}) if isinstance(var_keys, dict) else {}
    variable_type = field(var_keys, "type", "list")

    # "from" and "to" hold numeric bounds for range-like types, but conversion type
    # names for the "conversion" type: only fill the fields the type actually uses,
    # otherwise the unused component rejects the value and reports back a dirty state.
    if variable_type == "conversion":
        from_value = to_value = ""
        from_type_value = field(var_settings, "from", "dec")
        to_type_value = field(var_settings, "to", "hex")
    else:
        from_value = field(var_settings, "from")
        to_value = field(var_settings, "to")
        from_type_value = "dec"
        to_type_value = "hex"

    return variable_card(
        prefix,
        name=var_name,
        type_value=variable_type,
        base_value=field(var_settings, "base"),
        from_value=from_value,
        to_value=to_value,
        from_2_pow_value=field(var_settings, "from_2^"),
        to_2_pow_value=field(var_settings, "to_2^"),
        step_value=field(var_settings, "step"),
        from_type_value=from_type_value,
        to_type_value=to_type_value,
        op_value=field(var_settings, "op"),
        list_value=", ".join(map(str, var_settings.get("list", []) or [])),
        source_value=field(var_settings, "source"),
        sources_value=", ".join(map(str, var_settings.get("sources", []) or [])),
        format_value=field(var_keys, "format"),
        group_value=field(var_keys, "group"),
    )


def variable_cards_from_dict(prefix: str, variables):
    """Build the list of variable cards for a ``variables`` dict (no add card)."""
    cards = []
    if isinstance(variables, dict):
        for var_name, var_keys in variables.items():
            cards.append(variable_card_from_config(prefix, var_name, var_keys))
    return cards

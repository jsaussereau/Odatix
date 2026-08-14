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
that type) and turns them into a ``variables``
dict. The only thing that differs between the two pages is the id namespace, so
every component id is built from a ``prefix`` argument ("cfg-" for the
configuration editor, "wf-" for the workflow editor). Keeping this in one module
means a change to the variable model (e.g. adding the "group"/pairing field)
applies to both pages at once.

A page rendering several independent sets of variables at once -- the
configuration editor, which shows the rules of every parameter domain of an
architecture -- passes a ``scope`` dict that is merged into every id, so the
same variable name in two domains stays two different components.
"""

from typing import Optional

from dash import html, dcc

import odatix.gui.ui_components as ui
from odatix.gui.css_helper import Style
from odatix.gui.icons import icon
from odatix.workspace.configs import variable_definition

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


def number(text):
    """
    A list entry as the settings file spells it: a number when it reads as
    one, the text itself otherwise. A field hands back text, while a file holds
    ``[8, 16]`` -- writing back ``["8", "16"]`` would rewrite every list of a
    workspace the first time it was opened, and never stop showing as edited.
    """
    for cast in (int, float):
        try:
            return cast(text)
        except (TypeError, ValueError):
            continue
    return text


def build_variables_dict(
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals,
    from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals,
    sources_vals, format_vals, group_vals,
):
    """
    Build a ``variables`` dict from the values
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
            settings["list"] = [number(x.strip()) for x in list_vals[idx].split(",") if x.strip()] if list_vals[idx] else []
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
            # This type's format string belongs to its settings: that is where
            # the generator reads it (see ConfigGenerator.format_value_map).
            if var_format:
                settings["format"] = var_format
            var_format = None
        elif variable_type in {"union", "disjunctive_union", "intersection", "difference"}:
            settings["sources"] = [x.strip() for x in sources_vals[idx].split(",") if x.strip()] if sources_vals[idx] else []
        group = group_vals[idx] if group_vals[idx] else None
        variable = variable_definition(title, variable_type, settings, format=var_format, group=group)
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


######################################
# Components (namespaced by prefix)
######################################

def component_id(prefix: str, kind: str, name: str, scope: Optional[dict] = None):
    """
    Id of one component of a variable card. ``scope`` is merged in as-is, which
    is how a page showing several sets of variables at once tells them apart.
    """
    identifier = {"type": prefix + kind, "name": name}
    if scope:
        identifier.update(scope)
    return identifier


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
    scope: Optional[dict] = None,
):
    """One labelled field of a variable card (input or dropdown)."""
    if label is None:
        label = name
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Label(label),
                    ui.tooltip_icon(tooltip, tooltip_options) if tooltip else None,
                    dcc.Input(
                        value=value,
                        type=type,
                        placeholder=placeholder,
                        id=component_id(prefix, f"variable-field-{name}", var, scope),
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
                        id=component_id(prefix, f"variable-field-{name}", var, scope),
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
        id=component_id(prefix, f"variable-field-{name}-div", var, scope),
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
    scope: Optional[dict] = None,
    collapsible: bool = False, collapsed: bool = False,
):
    """
    A full variable definition card (title, type dropdown, fields, actions).

    A page holding many of them at once may ask for ``collapsible`` cards. The
    card is then a row rather than a tile: name, type, and the values the
    variable takes on one line, with its fields folded away underneath. Folded
    is the resting state -- a row says what the variable *is* without being
    opened, which is what makes showing every variable at once bearable. The
    fields are hidden, not removed: every id is still there, and still hands its
    value back.
    """
    title_input = dcc.Input(
        value=name,
        type="text",
        id=component_id(prefix, "variable-title", name, scope),
        className="title-input" + (" odx-variable-name" if collapsible else ""),
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
        } if not collapsible else {
            "width": "100%",
            "margin": "0px",
            "fontWeight": "bold",
            "fontSize": "1em",
            "height": "10px",
            "textAlign": "left",
        },
    )
    type_dropdown = dcc.Dropdown(
        id=component_id(prefix, "variable-type", name, scope),
        options=VARIABLE_TYPE_OPTIONS,
        value=type_value,
        clearable=False,
        style={"width": "100%"},
    )
    collapse_button = ui.icon_button(
        icon=icon(
            "more",
            className="icon normal rotate" if collapsed else "icon normal rotate rotated",
            id=component_id(prefix, "variable-collapse-icon", name, scope),
        ),
        color="default",
        id=component_id(prefix, "variable-collapse", name, scope),
        tooltip="Show/Hide this variable's fields",
        tooltip_options="bottom small",
    ) if collapsible else None
    duplicate_button = ui.duplicate_button(id=component_id(prefix, "duplicate-var", name, scope))
    delete_button = ui.delete_button(id=component_id(prefix, "delete-var", name, scope))

    if collapsible:
        # What the variable is, on one line: its name, its type, and -- filled in
        # by the page that owns it -- the values it currently takes. Read left to
        # right, that is the whole variable; the fields below are only how it is
        # obtained.
        head = html.Div(
            children=[
                collapse_button,
                html.Div(title_input, className="odx-variable-name-cell"),
                html.Div(type_dropdown, className="odx-variable-type-cell"),
                html.Div(
                    id=component_id(prefix, "variable-values", name, scope),
                    className="odx-variable-values",
                ),
                html.Div([duplicate_button, delete_button], className="odx-variable-actions"),
            ],
            className="odx-variable-head",
        )
    else:
        head = html.Div([title_input, type_dropdown])

    fields = html.Div(
        children=[
                    variable_field(prefix, var=name, name="from", label="From", type="number", value=from_value, scope=scope),
                    variable_field(prefix, var=name, name="to", label="To", type="number", value=to_value, scope=scope),
                    variable_field(prefix, var=name, name="from_2_pow", label="From 2^", type="number", value=from_2_pow_value, scope=scope),
                    variable_field(prefix, var=name, name="to_2_pow", label="To 2^", type="number", value=to_2_pow_value, scope=scope),
                    variable_field(prefix, var=name, name="from_type", label="From type", type="text", options=[{"label": "Bin", "value": "bin"}, {"label": "Dec", "value": "dec"}, {"label": "Hex", "value": "hex"}], value=from_type_value, scope=scope),
                    variable_field(prefix, var=name, name="to_type", label="To type", type="text", options=[{"label": "Bin", "value": "bin"}, {"label": "Dec", "value": "dec"}, {"label": "Hex", "value": "hex"}], value=to_type_value, scope=scope),
                    variable_field(prefix, var=name, name="base", label="Base", type="number", value=base_value, scope=scope),
                    variable_field(prefix, var=name, name="step", label="Step", type="number", value=step_value, scope=scope),
                    variable_field(prefix, var=name, name="op", label="Op", type="text", value=op_value, scope=scope),
                    variable_field(prefix, var=name, name="list", label="List", type="text", placeholder="Comma-separated values", default_style=Style.visible, value=list_value, scope=scope),
                    variable_field(prefix, var=name, name="source", label="Source", type="text", value=source_value, scope=scope),
                    variable_field(prefix, var=name, name="sources", label="Sources", type="text", placeholder="Comma-separated values", value=sources_value, scope=scope),
                    # Not behind a fold of their own: they are fields of the
                    # variable like any other, shown whenever its type uses them
                    # and laid out on the same line when there is room.
                    variable_field(prefix, var=name, name="format", label="Format", type="text", value=format_value, scope=scope),
                    variable_field(prefix, var=name, name="group", label="Variable group", type="text",
                        placeholder="Zip with same-group variables", value=group_value, scope=scope,
                        tooltip="Variables sharing the same group name are paired: their values are matched "
                                "position by position (like zip) instead of being combined with every other value. "
                                "Paired variables must have the same number of values. Leave empty for no pairing.",
                    ),
                ],
        id=component_id(prefix, "variable-fields-container", name, scope),
        className="odx-variable-fields-grid odx-variable-fields" if collapsible else "odx-variable-fields-grid",
        style=Style.hidden if (collapsible and collapsed) else {},
    )

    if collapsible:
        # Everything that is not the one-line summary lives inside the fold: an
        # open row is the editor, a closed one is the statement of what the
        # variable holds.
        body = [head, fields]
    else:
        body = [
            html.Div([head, fields]),
            html.Div([
                html.Div([
                    duplicate_button,
                    delete_button,
                ], style={"display": "flex", "flexDirection": "hotizontal", "alignItems": "center", "gap": "5px"}),
            ], style={
                "marginTop": "8px",
                "display": "flex",
                "flexDirection": "row",
                "width": "100%",
                "justifyContent": "flex-end",
            }),
        ]

    return html.Div(body + [
        dcc.Store(id=component_id(prefix, "variable-metadata", name, scope), data={"name": name, "type": type_value, "base_value": base_value, "from_value": from_value, "to_value": to_value, "from_2_pow_value": from_2_pow_value, "to_2_pow_value": to_2_pow_value, "from_type_value": from_type_value, "to_type_value": to_type_value, "step_value": step_value, "op_value": op_value, "list_value": list_value, "source_value": source_value, "sources_value": sources_value, "format_value": format_value, "group_value": group_value}),
    ],
    className="card configs" + (" odx-variable-row" if collapsible else ""),
    id=component_id(prefix, "variable-card", name, scope),
    style={
        "padding": "10px 12px",
        "margin": "4px 0px",
        "display": "block",
        "width": "auto",
    } if collapsible else {
        "padding": "10px",
        "margin": "5px",
        "display": "inline-block",
        "verticalAlign": "top",
    })


def card_field_values(var_keys):
    """
    What every field of a card shows for one ``variables`` dict entry, as the
    strings the components hold. The counterpart of
    :func:`build_variables_dict`, which reads those same fields back.
    """
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

    return {
        "type_value": variable_type,
        "base_value": field(var_settings, "base"),
        "from_value": from_value,
        "to_value": to_value,
        "from_2_pow_value": field(var_settings, "from_2^"),
        "to_2_pow_value": field(var_settings, "to_2^"),
        "step_value": field(var_settings, "step"),
        "from_type_value": from_type_value,
        "to_type_value": to_type_value,
        "op_value": field(var_settings, "op"),
        "list_value": ", ".join(map(str, var_settings.get("list", []) or [])),
        "source_value": field(var_settings, "source"),
        "sources_value": ", ".join(map(str, var_settings.get("sources", []) or [])),
        # A "format" variable *is* a format applied to a source, and holds its
        # format string in its settings; any other variable may carry one as an
        # extra key. One field either way, read where its type puts it.
        "format_value": field(var_settings if variable_type == "format" else var_keys, "format"),
        "group_value": field(var_keys, "group"),
    }


def variable_card_from_config(prefix: str, var_name, var_keys, scope: Optional[dict] = None,
                              collapsible: bool = False, collapsed: bool = False):
    """Build a variable card from a single ``variables`` dict entry."""
    return variable_card(prefix, name=var_name, scope=scope, collapsible=collapsible, collapsed=collapsed,
                         **card_field_values(var_keys))


def variable_cards_from_dict(prefix: str, variables, scope: Optional[dict] = None, collapsible: bool = False):
    """
    Build the list of variable cards for a ``variables`` dict (no add card).

    Collapsible cards are built folded: a row already says the name, the type
    and the values of its variable, so opening it is for changing it.
    """
    cards = []
    if isinstance(variables, dict):
        for var_name, var_keys in variables.items():
            cards.append(variable_card_from_config(prefix, var_name, var_keys, scope,
                                                   collapsible=collapsible, collapsed=collapsible))
    return cards


#: The card field each argument of :func:`build_variables_dict` comes from.
_BUILD_ORDER = [
    "type_value", "base_value", "from_value", "to_value",
    "from_2_pow_value", "to_2_pow_value", "from_type_value", "to_type_value",
    "step_value", "op_value", "list_value", "source_value", "sources_value",
    "format_value", "group_value",
]


def normalized_variables(variables):
    """
    The same variables, as the cards editing them would hand them back.

    A settings file and a form do not spell the same thing identically: a list
    of numbers comes back as text, a range with no step comes back with the
    step the field defaults to. Comparing what a form holds with what a file
    says therefore needs the file to go through the form first, or every
    editor would open already dirty.
    """
    if not isinstance(variables, dict) or not variables:
        return {}
    names = list(variables)
    rows = [card_field_values(variables[name]) for name in names]
    columns = [[row[key] for row in rows] for key in _BUILD_ORDER]
    return build_variables_dict(names, *columns)

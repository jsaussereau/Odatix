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

import os
import dash
from dash import html, dcc, Input, Output, State, ctx
from typing import Optional, Literal

import odatix.gui.navigation as navigation
import odatix.gui.ui_components as ui
from odatix.gui.css_helper import Style
from odatix.gui.utils import get_key_from_url
from odatix.gui.icons import icon
from odatix.lib.settings import OdatixSettings 
import odatix.lib.hard_settings as hard_settings
from odatix.lib.config_generator import ConfigGenerator
import odatix.components.workspace as workspace

verbose = False

page_path = "/config_generator"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Configuration Generator',
    name='Configuration Generator',
    order=5,
)

######################################
# Conversion Functions
######################################

def get_gen_settings(
    name, template,
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals
):
    """
    Get the configuration generation settings from the UI inputs.
    Args:
        name (str): The name of the configuration.
        template (str): The template for the configuration.
        titles (list): List of variable names.
        types (list): List of variable types.
        base_vals (list): List of base values for "multiples" type.
        from_vals (list): List of from values for "range" and "multiples" types.
        to_vals (list): List of to values for "range" and "multiples" types.
        from_2_pow_vals (list): List of from 2^ values for "power_of_two" type.
        to_2_pow_vals (list): List of to 2^ values for "power_of_two" type.
        from_type_vals (list): List of from values for "conversion" type.
        to_type_vals (list): List of to values for "conversion" type.
        step_vals (list): List of step values for "range" type.
        op_vals (list): List of operation strings for "function" type.
        list_vals (list): List of comma-separated values for "list" type.
        source_vals (str): Dource variable name for "conversion" type.
        sources_vals (list): List of comma-separated source variable names for set operations.
        format_vals (list): List of format strings.
    Returns:
        dict: Configuration generation settings.
    """
    variables = {}
    for idx, title in enumerate(titles):
        type = types[idx]
        settings = {}
        format = format_vals[idx] if format_vals[idx] else None
        if type == "range":
            settings["from"] = int(from_vals[idx]) if from_vals[idx] else 0
            settings["to"] = int(to_vals[idx]) if to_vals[idx] else 0
            settings["step"] = int(step_vals[idx]) if step_vals[idx] else 1
        elif type == "power_of_two":
            settings["from_2^"] = int(from_2_pow_vals[idx]) if from_2_pow_vals[idx] else 0
            settings["to_2^"] = int(to_2_pow_vals[idx]) if to_2_pow_vals[idx] else 0
        elif type == "list":
            settings["list"] = [x.strip() for x in list_vals[idx].split(",") if x.strip()] if list_vals[idx] else []
        elif type == "multiples":
            settings["base"] = int(base_vals[idx]) if base_vals[idx] else 1
            settings["from"] = int(from_vals[idx]) if from_vals[idx] else 0
            settings["to"] = int(to_vals[idx]) if to_vals[idx] else 0
        elif type == "function":
            settings["op"] = op_vals[idx] if op_vals[idx] else ""
        elif type == "conversion":
            settings["from"] = from_type_vals[idx] if from_type_vals[idx] else 0
            settings["to"] = to_type_vals[idx] if to_type_vals[idx] else 0
            settings["source"] = source_vals[idx] if source_vals[idx] else ""
        elif type == "format":
            settings["source"] = source_vals[idx] if source_vals[idx] else ""
        elif type in {"union", "disjunctive_union", "intersection", "difference"}:
            settings["sources"] = [x.strip() for x in sources_vals[idx].split(",") if x.strip()] if sources_vals[idx] else []
        variable = workspace.create_config_gen_variable_dict(name=title, type=type, settings=settings, format=format)
        variables.update(variable)
    gen_settings = workspace.create_config_gen_dict(name=name, template=template, variables=variables)
    return gen_settings

######################################
# UI Components
######################################

def config_parameters_form(settings):
    defval = lambda k, v=None: settings.get(k, v)
    return html.Div(
        children=[
            html.H3(f"Configuration Generation Settings"),
            html.Div([
                html.Label("Configuration name"),
                dcc.Input(
                    id="generator-name",
                    value=defval("name", "config_${var}"),
                    type="text",
                    style={"width": "100%", "fontSize": "1em", "fontFamily": "monospace", "fontWeight": "500"}
                ),
            ], style={"marginBottom": "12px"}),
            html.Div([
                html.Label("Content template"),
                dcc.Textarea(
                    id="generator-template",
                    value=defval("template", "parameter VALUE = ${var};"),
                    className="auto-resize-textarea",
                    style={"width": "100%", "resize": "none", "fontSize": "1em", "fontFamily": "monospace", "fontWeight": "500"},
                ),
            ], style={"marginBottom": "12px"}),
            dcc.Store(id="generator-initial-settings", data=settings),
            dcc.Store(id="generator-saved-settings", data=None),
        ],
        id="config-parameters",
        className="tile config",
    )

def variable_field(
    var: str,
    type: Literal['text', 'number', 'password', 'email', 'range', 'search', 'tel', 'url', 'hidden'] = "text",
    name: str = "",
    label: Optional[str] = None,
    options: Optional[list] = None,
    value: str = "",
    placeholder: str = "",
    default_style: dict = Style.hidden
):
    if label is None:
        label = name
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Label(label, style={"fontWeight": "bold", "fontSize": "1em"}),
                    dcc.Input(
                        value=value,
                        type=type,
                        placeholder=placeholder,
                        id={"type": f"variable-field-{name}", "name": var},
                        className="value-input",
                        style={
                            "width": "calc(100% - 20px)",
                            "marginLeft": "5px",
                            "marginRight": "5px",
                            "marginBottom": "5px",
                            "fontSize": "0.9em",
                            "height": "10px",
                            "z-index": "900",
                        },
                    ) if options is None else dcc.Dropdown(
                        id={"type": f"variable-field-{name}", "name": var},
                        options=options,
                        value=value,
                        clearable=False,
                        style={
                            "fontSize": "0.95em",
                            "z-index": "900",
                        },
                    ),
                ], 
                style={"marginTop": "5px"}
            ),
        ],
        id={"type": f"variable-field-{name}-div", "name": var},
        style=default_style
    )

def variable_card(
        name, var_layout="normal",
        type_value="list",
        base_value="", from_value="", to_value="",
        from_2_pow_value="", to_2_pow_value="", step_value="1",
        from_type_value="dec", to_type_value="hex",
        op_value="", list_value="", source_value="", sources_value="", format_value="",
    ):
    save_class =  "color-button disabled"
    return html.Div([
        html.Div([
            dcc.Input(
                value=name,
                type="text",
                id={"type": "variable-title", "name": name},
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
                id={"type": "variable-type", "name": name},
                options=[
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
                ],
                value=type_value,
                clearable=False,
            ),
            html.Div(
                children=[ 
                    variable_field(var=name, name="from", label="From", type="number", value=from_value),
                    variable_field(var=name, name="to", label="To", type="number", value=to_value),
                    variable_field(var=name, name="from_2_pow", label="From 2^", type="number", value=from_2_pow_value),
                    variable_field(var=name, name="to_2_pow", label="To 2^", type="number", value=to_2_pow_value),
                    variable_field(var=name, name="from_type", label="From type", type="text", options=[{"label": "Bin", "value": "bin"}, {"label": "Dec", "value": "dec"}, {"label": "Hex", "value": "hex"}], value=from_type_value),
                    variable_field(var=name, name="to_type", label="To type", type="text", options=[{"label": "Bin", "value": "bin"}, {"label": "Dec", "value": "dec"}, {"label": "Hex", "value": "hex"}], value=to_type_value),
                    variable_field(var=name, name="base", label="Base", type="number", value=base_value),
                    variable_field(var=name, name="step", label="Step", type="number", value=step_value),
                    variable_field(var=name, name="op", label="Op", type="text", value=op_value),
                    variable_field(var=name, name="list", label="List", type="text", placeholder="Comma-separated values", default_style=Style.visible, value=list_value),
                    variable_field(var=name, name="source", label="Source", type="text", value=source_value),
                    variable_field(var=name, name="sources", label="Sources", type="text", placeholder="Comma-separated values", value=sources_value),
                    html.Div(
                        children=[
                            variable_field(var=name, name="format", label="Format", type="text", value=format_value),
                        ],
                        id={"type": "more-variable-field-div", "name": name},
                        className="expandable-area",
                        style=Style.hidden
                    )
                ],
                id="variable-fields-container",
            ),
        ]),
        html.Div([
            html.Div([
                ui.icon_button(
                    icon=icon("more", className="icon normal rotate", id={"type": "more-fields-icon", "name": name}),
                    color="normal",
                    id={"type": "more-fields", "name": name},
                )
            ], id={"type": "more-fields-div", "name": name}, style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": "duplicate-var", "name": name}),
                ui.delete_button(id={"type": "delete-var", "name": name}),
            ]),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
        dcc.Store(id={"type": "variable-metadata", "name": name}, data={"name": name, "type": type_value, "base_value": base_value, "from_value": from_value, "to_value": to_value, "from_2_pow_value": from_2_pow_value, "to_2_pow_value": to_2_pow_value, "from_type_value": from_type_value, "to_type_value": to_type_value, "step_value": step_value, "op_value": op_value, "list_value": list_value, "source_value": source_value, "sources_value": sources_value, "format_value": format_value}),
    ], 
    className="card configs", 
    id={"type": "variable-card", "name": name},
    style={
        "padding": "10px", 
        "margin": "5px", 
        "display": "inline-block", 
        "verticalAlign": "top"
    })

def add_card(text: str = "Add new variable"):
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "paddingTop": "20px"}),
                    html.Div(
                        "+",
                        style={
                            "fontSize": "2.5em",
                            "lineHeight": "80px",
                            "height": "80px",
                        }
                    ),
                ], 
                style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
            ),
            id="new-variable",
            n_clicks=0,
            style={"text-decoration": "none", "height": "100%"},
        ),
        className=f"card configs add hover",
        id="add-config-card",
        style={
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box"
        },
    )

def config_card(filename, content, config_layout="normal", ellipsis=False):
    display_name = filename[:-4] if filename.endswith(".txt") else filename
    return html.Div([
        html.Div([
            dcc.Input(
                value=f"{display_name}",
                type="text",
                id={"type": "config-title", "filename": filename},
                className="title-input preview",
                readOnly=True,
                style={
                    "width": "calc(100% - 20px)",
                    "marginLeft": "5px",
                    "marginRight": "5px",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "height": "10px",
                    "marginTop": "-5px",
                    "marginBottom": "2px",
                    "textAlign": "center",
                },
            )
        ]) if not ellipsis else html.Div(style={"height": "24px"}),
        dcc.Textarea(
            id={"type": "config-content", "filename": filename},
            value=content,
            className="auto-resize-textarea" if config_layout != "compact" else "",
            readOnly=True,
            style={
                "width": "calc(100% - 20px)",
                "marginLeft": "5px",
                "marginRight": "5px",
                "resize": "none" if config_layout != "compact" else "vertical",
                "minHeight": "none" if config_layout != "compact" else "45px",
                "height": "none" if config_layout != "compact" else "45px",
                "fieldSizing": "border-box",
                "fontFamily": "monospace",
                "fontSize": "0.9em",
                "fontWeight": "normal",
            },
        ) if not ellipsis else html.Div(
            children=[
                html.Span('[...]', style={"margin": "0", "padding": "0"}),
                html.H4(content, style={"margin": "0", "padding": "0"}), 
            ],
            style={
                "display": "flex",
                "flexDirection": "column",
                "alignItems": "center",
                "justifyContent": "center",
                "height": "45px",
                "gap": "0px",
            },        
        ), 
    ],
    className="card configs", 
    id={"type": "config-card", "filename": filename},
    style={
        "padding": "10px", 
        "margin": "5px", 
        "display": "inline-block", 
        "border": "1px dashed #bbb" if ellipsis else "",
        "verticalAlign": "top"
    })


######################################
# Callbacks
######################################

@dash.callback(
    [
        Output({"type": "variable-field-from-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-to-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-from_2_pow-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-to_2_pow-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-from_type-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-to_type-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-base-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-step-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-op-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-list-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-source-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-sources-div", "name": dash.ALL}, "style"),
        Output({"type": "variable-field-format-div", "name": dash.ALL}, "style"),
    ],
    Input({"type": "variable-type", "name": dash.ALL}, "value"),
)
def update_variable_fields_visibility(types):
    # Required fields for each type
    mapping = {
        "bool":              {"format"},
        "list":              {"list", "format"},
        "range":             {"from", "to", "step", "format"},
        "power_of_two":      {"from_2_pow", "to_2_pow", "format"},
        "multiples":         {"base", "from", "to", "format"},
        "function":          {"op", "format"},
        "conversion":        {"from_type", "to_type", "source", "format"},
        "format":            {"source", "format"},
        "union":             {"sources", "format"},
        "disjunctive_union": {"sources", "format"},
        "intersection":      {"sources", "format"},
        "difference":        {"sources", "format"},
    }
    all_fields = ["from", "to", "from_2_pow", "to_2_pow", "from_type", "to_type", "base", "step", "op", "list", "source", "sources", "format"]

    styles_by_field = {field: [] for field in all_fields}
    for t in types:
        visible = mapping.get(t, set())
        for field in all_fields:
            styles_by_field[field].append(Style.visible if field in visible else Style.hidden)

    return (
        styles_by_field["from"],
        styles_by_field["to"],
        styles_by_field["from_2_pow"],
        styles_by_field["to_2_pow"],
        styles_by_field["from_type"],
        styles_by_field["to_type"],
        styles_by_field["base"],
        styles_by_field["step"],
        styles_by_field["op"],
        styles_by_field["list"],
        styles_by_field["source"],
        styles_by_field["sources"],
        styles_by_field["format"],
    )

@dash.callback(
    Output({"type": "variable-cards-row"}, "children"),
    Output("generator-name", "value"),
    Output("generator-template", "value"),
    Output("generator-initial-settings", "data"),
    Input("url", "search"),
    Input("url", "pathname"),
    Input("new-variable", "n_clicks"),
    Input({"type": "duplicate-var", "name": dash.ALL}, "n_clicks"),
    Input({"type": "delete-var", "name": dash.ALL}, "n_clicks"),
    State({"type": "variable-cards-row"}, "children"),
    State({"type": "variable-type", "name": dash.ALL}, "value"),
    State({"type": "variable-field-base", "name": dash.ALL}, "value"),
    State({"type": "variable-field-from", "name": dash.ALL}, "value"),
    State({"type": "variable-field-to", "name": dash.ALL}, "value"),
    State({"type": "variable-field-from_2_pow", "name": dash.ALL}, "value"),
    State({"type": "variable-field-to_2_pow", "name": dash.ALL}, "value"),
    State({"type": "variable-field-from_type", "name": dash.ALL}, "value"),
    State({"type": "variable-field-to_type", "name": dash.ALL}, "value"),
    State({"type": "variable-field-step", "name": dash.ALL}, "value"),
    State({"type": "variable-field-op", "name": dash.ALL}, "value"),
    State({"type": "variable-field-list", "name": dash.ALL}, "value"),
    State({"type": "variable-field-source", "name": dash.ALL}, "value"),
    State({"type": "variable-field-sources", "name": dash.ALL}, "value"),
    State({"type": "variable-field-format", "name": dash.ALL}, "value"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_form_and_variable_cards(
    search, page, new_click, duplicate_clicks, delete_clicks, cards,
    types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals,
    odatix_settings
):
    trigger_id = ctx.triggered_id

    if trigger_id == "url":
        if page != page_path:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update

        arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
        arch_name = get_key_from_url(search, "arch")
        domain = get_key_from_url(search, "domain")
        if not domain: 
            domain = hard_settings.main_parameter_domain
        if not arch_name:
            return [], dash.no_update, dash.no_update, dash.no_update

        settings = workspace.load_architecture_settings(arch_path, arch_name, domain)
        variables = {}

        generator_name = ""
        generator_template = ""
        gen_settings = {}
        if "generate_configurations_settings" in settings:
            gen_settings = settings["generate_configurations_settings"]
            variables = gen_settings.get("variables", {})
            generator_name = gen_settings.get("name", "")
            generator_template = gen_settings.get("template", "")
            if isinstance(generator_template, list):
                generator_template = "\n".join(generator_template)
        
        cards = []
        # Create cards from existing variables
        for var_name, var_keys in variables.items():
            type_value = var_keys.get("type", "list")
            var_settings = var_keys.get("settings", {})
            card_kwargs = {
                "name": var_name,
                "type_value": type_value,
                "base_value": str(var_settings.get("base", "")),
                "from_value": str(var_settings.get("from", "")),
                "to_value": str(var_settings.get("to", "")),
                "from_2_pow_value": str(var_settings.get("from_2^", "")),
                "to_2_pow_value": str(var_settings.get("to_2^", "")),
                "step_value": str(var_settings.get("step", "")),
                "from_type_value": str(var_settings.get("from", "")),
                "to_type_value": str(var_settings.get("to", "")),
                "op_value": str(var_settings.get("op", "")),
                "list_value": ", ".join(map(str, var_settings.get("list", []))),
                "source_value": str(var_settings.get("source", "")),
                "sources_value": ", ".join(map(str, var_settings.get("sources", []))),
                "format_value": str(var_keys.get("format", "")),
            }
            cards.append(variable_card(**card_kwargs))
        
        # Append Add card
        cards.append(add_card())
        return cards, generator_name, generator_template, gen_settings

    if cards is None:
        cards = []

    # Remove the Add card if present
    if cards and isinstance(cards[-1], dict) and cards[-1].get('props', {}).get('id') == "add-config-card":
        cards = cards[:-1]

    # Add new variable
    if trigger_id == "new-variable" and new_click:
        existing_names = [card.get('props', {}).get('id', {}).get('name', '') for card in cards if isinstance(card.get('props', {}).get('id', {}), dict)]
        var_idx = 1
        while f"var{var_idx}" in existing_names:
            var_idx += 1
        new_name = f"var{var_idx}"
        cards.append(variable_card(new_name))

    if isinstance(trigger_id, dict):
        trig_type = trigger_id.get("type")
        trig_name = trigger_id.get("name")

        # Delete
        if trig_type == "delete-var":
            cards = [
                card for card in cards
                if not (
                    isinstance(card.get('props', {}).get('id', {}), dict)
                    and card.get('props', {}).get('id', {}).get("type") == "variable-card"
                    and card.get('props', {}).get('id', {}).get("name") == trig_name
                )
            ]
        # Duplicate
        else:
            idx = None
            for i, card in enumerate(cards):
                card_id = card.get('props', {}).get('id', {})
                if isinstance(card_id, dict) and card_id.get("type") == "variable-card" and card_id.get("name") == trig_name:
                    idx = i
                    break

            if trig_type == "duplicate-var":

                # Find a unique name for the duplicated variable
                existing_names = [card.get('props', {}).get('id', {}).get('name', '') for card in cards if isinstance(card.get('props', {}).get('id', {}), dict)]
                copy_idx = 1
                while f"{trig_name}_copy{copy_idx}" in existing_names:
                    copy_idx += 1
                new_name = f"{trig_name}_copy{copy_idx}"

                if idx is not None:
                    cards.append(variable_card(
                        name=new_name,
                        type_value=types[idx],
                        base_value=base_vals[idx],
                        from_value=from_vals[idx],
                        to_value=to_vals[idx],
                        from_2_pow_value=from_2_pow_vals[idx],
                        to_2_pow_value=to_2_pow_vals[idx],
                        from_type_value=from_vals[idx],
                        to_type_value=to_vals[idx],
                        step_value=step_vals[idx],
                        op_value=op_vals[idx],
                        list_value=list_vals[idx],
                        source_value=sources_vals[idx],
                        sources_value=sources_vals[idx],
                    ))

    # Append Add card
    cards.append(add_card())
    return cards, dash.no_update, dash.no_update, dash.no_update

@dash.callback(
    Output({"type": "config-cards-row"}, "children"),
    Output("variable-preview", "children"),
    Output("gen-preview", "children"),
    Input("url", "search"),
    Input("url", "pathname"),
    Input({"action": "save-all"}, "n_clicks"),
    Input({"action": "generate-all"}, "n_clicks"),
    Input("generator-name", "value"),
    Input("generator-template", "value"),
    Input({"type": "variable-title", "name": dash.ALL}, "value"),
    Input({"type": "variable-type", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-base", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-from", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-to", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-from_2_pow", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-to_2_pow", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-from_type", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-to_type", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-step", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-op", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-list", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-source", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-sources", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-format", "name": dash.ALL}, "value"),
    State({"type": "variable-metadata", "name": dash.ALL}, "data"),
    State("odatix-settings", "data"),
)
def update_generation(
    search, page, n_click_save, n_click_gen,
    name, template,
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals,
    metadata, odatix_settings
):  
    trigger_id = ctx.triggered_id

    if trigger_id == "url":
        if page != page_path:
            return dash.no_update, dash.no_update, dash.no_update
    
    nb_vars = len(titles)
    if not (name and template and nb_vars > 0):
        return [], [], "0 configurations to be generated"
    
    gen_settings = get_gen_settings(
        name, template,
        titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals
    )

    generator = ConfigGenerator(data=gen_settings)
    generated_params, variables = generator.generate()
    
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_key_from_url(search, "arch")
    domain = get_key_from_url(search, "domain")
    if not domain:
        domain = hard_settings.main_parameter_domain
    if trigger_id == {"action": "save-all"} or trigger_id == {"action": "generate-all"}:
        if domain and arch_name:
            workspace.update_domain_settings(
                arch_path=arch_path,
                arch_name=arch_name, 
                domain=domain, 
                settings_to_update=gen_settings,
            )
            if trigger_id == {"action": "save-all"}:
                return dash.no_update, dash.no_update, dash.no_update
    
    if trigger_id == {"action": "generate-all"}:
        for config_name, config_content in generated_params.items():
            arch_domain_path = workspace.get_arch_domain_path(arch_path, arch_name, domain)
            config_file_path = os.path.join(arch_domain_path, f"{config_name}.txt")
            try:
                with open(config_file_path, "w") as config_file:
                    config_file.write(config_content)
            except Exception as e:
                pass
        return dash.no_update, dash.no_update, dash.no_update
        
    # Limit the number of previewed configurations
    if len(generated_params) > hard_settings.max_preview_values:
        preview_params = dict(list(generated_params.items())[:hard_settings.max_preview_values-2])
        ellipsis = True
        hidden_count = len(generated_params) - len(preview_params) - 1
    else:
        preview_params = generated_params
        ellipsis = False
        hidden_count = 0

    # Create config cards
    config_cards = []
    for config_name, config_content in preview_params.items():
        config_cards.append(config_card(
            filename=f"{config_name}.txt",
            content=config_content,
        ))
    
    if ellipsis:
        config_cards.append(config_card(
            filename="",
            content=f"{hidden_count} more configurations",
            ellipsis=True,
        ))
        config_name, config_content = list(generated_params.items())[-1]
        config_cards.append(config_card(
            filename=f"{config_name}.txt",
            content=config_content,
        ))

    variables_preview = []

    for var, values in variables.items():
        if len(values) > hard_settings.max_preview_values:
            values = list(values)[:hard_settings.max_preview_values-2] + ["[...]"] + [list(values)[-1]]
        variables_preview.append(
            html.Div(
                children=[
                    html.B(var),
                    html.Span(f": "),
                    html.Pre(
                        children=f"{', '.join(map(str, values))}",
                        style={"display": "inline", "paddingLeft": "5px", "paddingRight": "5px", "whiteSpace": "pre-wrap", "wordBreak": "break-word"},
                    ),
                ],
                style={"marginBottom": "5px"},
            )
        )
    
    title = f"{len(generated_params)} configurations to be generated"

    return config_cards, variables_preview, title

@dash.callback(
    Output("main-title-config-gen", "children"),
    Input("url", "search"),
    State("url", "pathname"),
    preview_initial_call=True
)
def update_main_domain_title(search, page):
    if page != page_path:
        return dash.no_update, dash.no_update, dash.no_update
    arch_name = get_key_from_url(search, "arch")
    domain = get_key_from_url(search, "domain")
    if not domain:
        domain = hard_settings.main_parameter_domain
        if not domain: domain = hard_settings.main_parameter_domain

    if not arch_name:
        return "No architecture selected."
    
    if domain == hard_settings.main_parameter_domain:
        title = f"{arch_name} - Main parameter domain"
    else:
        title = f"{arch_name} - {domain}"
    return title

@dash.callback(
    Output({"type": "more-variable-field-div", "name": dash.ALL}, "style"),
    Output({"type": "more-fields-icon", "name": dash.ALL}, "className"),
    Input({"type": "more-fields", "name": dash.ALL}, "n_clicks"),
    State({"type": "more-variable-field-div", "name": dash.ALL}, "style"),
    State({"type": "more-fields-icon", "name": dash.ALL}, "className"),
    State({"type": "variable-metadata", "name": dash.ALL}, "data"),
)
def toggle_more_fields(n_clicks, expandable_area_styles, icon_classes, metadata):
    # Get the button that triggered the callback
    trigger_id = ctx.triggered_id
    if not isinstance(trigger_id, dict) or "name" not in trigger_id:
        return [dash.no_update] * len(n_clicks), [dash.no_update] * len(n_clicks)

    # Update only the relevant variable card
    index = None
    for i, clicks in enumerate(n_clicks):
        current_name = metadata[i].get("name") if metadata and i < len(metadata) else {}
        if trigger_id.get("name") == current_name:
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

@dash.callback(
    Output({"action": "save-all"}, "className"),
    Output("generator-saved-settings", "data"),
    Input({"action": "save-all"}, "n_clicks"),
    Input({"action": "generate-all"}, "n_clicks"),
    Input("generator-name", "value"),
    Input("generator-template", "value"),
    Input({"type": "variable-title", "name": dash.ALL}, "value"),
    Input({"type": "variable-type", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-base", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-from", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-to", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-from_2_pow", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-to_2_pow", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-from_type", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-to_type", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-step", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-op", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-list", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-source", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-sources", "name": dash.ALL}, "value"),
    Input({"type": "variable-field-format", "name": dash.ALL}, "value"),
    State("generator-initial-settings", "data"),
    State("generator-saved-settings", "data"),
    State({"type": "variable-metadata", "name": dash.ALL}, "data"),
    prevent_initial_call=True
)
def update_save_button(
    save_n_clicks, generate_n_clicks, name, template, 
    title_values, type_values, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals,
    initial_settings, saved_settings, metadata
):
    button_disabled = "color-button disabled icon-button"
    button_enabled = "color-button orange icon-button"

    trigger_id = ctx.triggered_id

    if trigger_id == {"action": "save-all"} or trigger_id == {"action": "generate-all"}:
        return button_disabled, {
            "name": name,
            "template": template,
        }

    if saved_settings is None:
        settings = initial_settings
    else:
        settings = saved_settings

    old_name = settings.get("name", "") if settings else ""
    old_template = settings.get("template", "") if settings else ""

    if name != old_name or template != old_template:
        return button_enabled, dash.no_update
    
    for i, _ in enumerate(title_values):
        if str(title_values[i]) != str(metadata[i].get("name")):
            return button_enabled, dash.no_update
        if str(type_values[i]) != str(metadata[i].get("type")):
            return button_enabled, dash.no_update
        if str(base_vals[i]) != str(metadata[i].get("base_value")):
            return button_enabled, dash.no_update
        if str(from_vals[i]) != str(metadata[i].get("from_value")):
            return button_enabled, dash.no_update
        if str(to_vals[i]) != str(metadata[i].get("to_value")):
            return button_enabled, dash.no_update
        if str(from_2_pow_vals[i]) != str(metadata[i].get("from_2_pow_value")):
            return button_enabled, dash.no_update
        if str(to_2_pow_vals[i]) != str(metadata[i].get("to_2_pow_value")):
            return button_enabled, dash.no_update
        if str(from_type_vals[i]) != str(metadata[i].get("from_type_value")):
            return button_enabled, dash.no_update
        if str(to_type_vals[i]) != str(metadata[i].get("to_type_value")):
            return button_enabled, dash.no_update
        if str(step_vals[i]) != str(metadata[i].get("step_value")):
            return button_enabled, dash.no_update
        if str(op_vals[i]) != str(metadata[i].get("op_value")):
            return button_enabled, dash.no_update
        if str(list_vals[i]) != str(metadata[i].get("list_value")):
            return button_enabled, dash.no_update
        if str(source_vals[i]) != str(metadata[i].get("source_value")):
            return button_enabled, dash.no_update
        if str(sources_vals[i]) != str(metadata[i].get("sources_value")):
            return button_enabled, dash.no_update
        if str(format_vals[i]) != str(metadata[i].get("format_value")):
            return button_enabled, dash.no_update

    return button_disabled, dash.no_update

@dash.callback(
    Input({"action": "clean-all"}, "n_clicks"),
    State("url", "search"),
    State("odatix-settings", "data"),
)
def clean_all_configs(n_clicks, search, odatix_settings):    
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_key_from_url(search, "arch")
    domain = get_key_from_url(search, "domain")
    if not domain:
        domain = hard_settings.main_parameter_domain
    
    trigger_id = ctx.triggered_id
    if trigger_id == {"action": "clean-all"} and n_clicks:
        workspace.delete_all_config_files(arch_path, arch_name, domain)

@dash.callback(
    Output("config-gen-back-button", "href"),
    Input("url", "search"),
)
def update_back_button_link(search):
    arch_name = get_key_from_url(search, "arch")
    return f"/config_editor?arch={arch_name}"


######################################
# Layout
######################################

variable_title_tile_buttons = html.Div(
    children=[
        ui.save_button(
            id={"action": "save-all"},
        ),
    ],
    className="inline-flex-buttons",
)
preview_title_tile_buttons = html.Div(
    children=[
        ui.icon_button(
            icon=icon("generate", className="icon blue"),
            color="blue",
            text="Generate", 
            id={"action": "generate-all"},
        ),
        ui.icon_button(
            icon=icon("clean", className="icon red"),
            color="red",
            text="Clean Existing", 
            multiline=True,
            id={"action": "clean-all"},
        ),
    ],
    className="inline-flex-buttons",
)


layout = html.Div(
    children=[
        dcc.Location(id="url"),
        html.Div(style={"marginTop": "10px"}),
        ui.title_tile(id="main-title-config-gen", buttons=variable_title_tile_buttons, back_button_link="/config_editor", back_button_id="config-gen-back-button"),
        html.Div(
            children=[
                config_parameters_form({}),
                html.Div(
                    children=[
                        html.H3(f"Variable Preview"),
                        html.Div(id="variable-preview")
                    ],
                    id="preview-pane",
                    className="tile config"
                ),
            ], 
            className="card-matrix config",
        ),
        ui.title_tile(text="Variable Definition", id="variable-title"),
        html.Div([ 
            html.Div(
                children=[
                    variable_card(name="var", type_value="range", from_value="1", to_value="10", step_value="1"),
                    add_card(),
                ],
                id={"type": "variable-cards-row"},
                className=f"card-matrix configs", 
                style={"marginLeft": "13px"},
            ),
        ]),
        ui.title_tile(text="Generation Preview", id="gen-preview", buttons=preview_title_tile_buttons),
        html.Div([ 
            html.Div(
                id={"type": "config-cards-row"},
                className=f"card-matrix configs", 
                style={"marginLeft": "13px"},
            ),
        ]),
        dcc.Store(id={"type": "update_url", "id": page_path}),
    ],
    className="page-content",
    style={
        "padding": "0 16%",
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    }
)

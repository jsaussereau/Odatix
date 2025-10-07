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
import uuid
import dash
from dash import html, dcc, Input, Output, State, ctx
from typing import Optional, Literal

import odatix.gui.ui_components as ui
from odatix.gui.css_helper import Style
from odatix.gui.utils import get_key_from_url
from odatix.gui.icons import icon
from odatix.lib.settings import OdatixSettings 
import odatix.lib.hard_settings as hard_settings
from odatix.lib.config_generator import ConfigGenerator
import odatix.components.config_handler as config_handler
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
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals
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
    Returns:
        dict: Configuration generation settings.
    """
    variables = {}
    for idx, title in enumerate(titles):
        type = types[idx]
        settings = {}
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
        elif type in {"union", "disjunctive_union", "intersection", "difference"}:
            settings["sources"] = [x.strip() for x in sources_vals[idx].split(",") if x.strip()] if sources_vals[idx] else []
        variable = config_handler.create_config_gen_variable_dict(name=title, type=type, settings=settings)
        variables.update(variable)
    gen_settings = config_handler.create_config_gen_dict(name=name, template=template, variables=variables)
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
                            "fontSize": "1em",
                            "height": "10px",
                            "z-index": "900",
                        },
                    ) if options is None else dcc.Dropdown(
                        id={"type": f"variable-field-{name}", "name": var},
                        options=options,
                        value=value,
                        clearable=False,
                        style={
                            "fontSize": "1em",
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
        op_value="", list_value="", source_value="", sources_value=""
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
                    {"label": "List", "value": "list"},
                    {"label": "Range", "value": "range"},
                    {"label": "Power of 2", "value": "power_of_two"},
                    {"label": "Multiples", "value": "multiples"},
                    {"label": "Function", "value": "function"},
                    {"label": "Conversion", "value": "conversion"},
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
                ],
                id="variable-fields-container",
            ),
        ]),
        html.Div([
            html.Div([
                # html.Button("Save", id={"type": "save-var", "name": name}, n_clicks=0, className=save_class, style={"marginRight": "8px", "marginLeft": "5px"}),
                # html.Button("TEST", id={"type": "test-var", "name": name}, n_clicks=0, className=save_class, style={"marginRight": "8px", "marginLeft": "5px"}),
                # html.Div(status_text, id={"type": "save-status", "name": filename}, className=status_class, style={"marginLeft": "0px", "textwrap": "wrap", "width": "80px", "font-size": "13px", "font-weight": "515"}),
            ], style={"display": "flex", "alignItems": "center"}),
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
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "color": "black", "paddingTop": "20px"}),
                    html.Div(
                        "+",
                        style={
                            "fontSize": "2.5em",
                            "color": "#888",
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
            "backgroundColor": "rgba(255, 255, 255, 0.31)",
            "border": "1px dashed #bbb",
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
    ],
    Input({"type": "variable-type", "name": dash.ALL}, "value"),
)
def update_variable_fields_visibility(types):
    # Required fields for each type
    mapping = {
        "list":              {"list"},
        "range":             {"from", "to", "step"},
        "power_of_two":      {"from_2_pow", "to_2_pow"},
        "multiples":         {"base", "from", "to"},
        "function":          {"op"},
        "conversion":        {"from_type", "to_type", "source"},
        "union":             {"sources"},
        "disjunctive_union": {"sources"},
        "intersection":      {"sources"},
        "difference":        {"sources"},
    }
    all_fields = ["from", "to", "from_2_pow", "to_2_pow", "from_type", "to_type", "base", "step", "op", "list", "source", "sources"]

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
    )

@dash.callback(
    Output({"type": "variable-cards-row"}, "children"),
    Output("generator-name", "value"),
    Output("generator-template", "value"),
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
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_form_and_variable_cards(
    search, page, new_click, duplicate_clicks, delete_clicks, cards,
    types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals,
    odatix_settings
):
    trigger_id = ctx.triggered_id

    if trigger_id == "url":
        if page != page_path:
            return dash.no_update, dash.no_update, dash.no_update

        arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
        arch_name = get_key_from_url(search, "arch")
        domain = get_key_from_url(search, "domain")
        if not domain: 
            domain = hard_settings.main_parameter_domain
        if not arch_name:
            return [], dash.no_update, dash.no_update

        settings = config_handler.load_settings(arch_path, arch_name, domain)
        variables = {}

        generator_name = ""
        generator_template = ""
        if "generate_configurations_settings" in settings:
            gen_settings = settings["generate_configurations_settings"]
            variables = gen_settings.get("variables", {})
            generator_name = gen_settings.get("name", "")
            generator_template = gen_settings.get("template", "")
            if isinstance(generator_template, list):
                generator_template = "\n".join(generator_template)
        
        cards = []
        # Create cards from existing variables
        for var_name, var_settings in variables.items():
            type_value = var_settings.get("type", "list")
            settings = var_settings.get("settings", {})
            card_kwargs = {
                "name": var_name,
                "type_value": type_value,
                "base_value": str(settings.get("base", "")),
                "from_value": str(settings.get("from", "")),
                "to_value": str(settings.get("to", "")),
                "from_2_pow_value": str(settings.get("from_2^", "")),
                "to_2_pow_value": str(settings.get("to_2^", "")),
                "step_value": str(settings.get("step", "")),
                "from_type_value": str(settings.get("from", "")),
                "to_type_value": str(settings.get("to", "")),
                "op_value": str(settings.get("op", "")),
                "list_value": ", ".join(map(str, settings.get("list", []))),
                "source_value": str(settings.get("source", "")),
                "sources_value": ", ".join(map(str, settings.get("sources", []))),
            }
            cards.append(variable_card(**card_kwargs))
        
        # Append Add card
        cards.append(add_card())
        return cards, generator_name, generator_template

    if cards is None:
        cards = []

    # Remove the Add card if present
    if cards and isinstance(cards[-1], dict) and cards[-1].get('props', {}).get('id') == "add-config-card":
        cards = cards[:-1]

    # Add new variable
    if trigger_id == "new-variable" and new_click:
        new_name = f"var_{uuid.uuid4().hex[:8]}"
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

                if idx is not None:
                    new_name = f"var_{uuid.uuid4().hex[:8]}"
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
    return cards, dash.no_update, dash.no_update

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
    State("odatix-settings", "data"),
)
def update_generation(
    search, page, n_click_save, n_click_gen,
    name, template,
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals,
    odatix_settings
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
        titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals
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
            config_handler.update_domain_settings(
                arch_path=arch_path,
                arch_name=arch_name, 
                domain=domain, 
                settings_to_update=gen_settings,
            )
            if trigger_id == {"action": "save-all"}:
                return dash.no_update, dash.no_update, dash.no_update
    
    if trigger_id == {"action": "generate-all"}:
        for config_name, config_content in generated_params.items():
            arch_domain_path = config_handler.get_arch_domain_path(arch_path, arch_name, domain)
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

######################################
# Layout
######################################

variable_title_tile_buttons = html.Div(
    children=[
        ui.save_button(
            id={"action": "save-all"},
            large=True
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
        )
    ],
    className="inline-flex-buttons",
)


layout = html.Div([
    dcc.Location(id="url"),
    ui.title_tile(id="main-title-config-gen", buttons=variable_title_tile_buttons),
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
        ),
    ]),
    ui.title_tile(text="Generation Preview", id="gen-preview", buttons=preview_title_tile_buttons),
    html.Div([ 
        html.Div(
            id={"type": "config-cards-row"},
            className=f"card-matrix configs", 
            style={"marginLeft": "13px"}
        ),
    ]),
], style={
    "background-color": "#f6f8fa",
    "padding": "20px 16%",
    "minHeight": "100vh"
})

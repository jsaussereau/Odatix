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
from typing import Optional#, Literal

import odatix.gui.navigation as navigation
import odatix.gui.ui_components as ui
from odatix.gui.css_helper import Style
from odatix.gui.utils import get_key_from_url, get_instance_mode, get_instance_context
from odatix.gui.icons import icon
import odatix.lib.hard_settings as hard_settings
from odatix.lib.config_generator import ConfigGenerator
import odatix.components.workspace as workspace
import odatix.gui.variable_editor as ve

# Variable-editor id namespace for this page (no prefix).
VE_PREFIX = ""

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
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals, group_vals
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
        group_vals (list): List of pairing group labels. Variables sharing a group are zipped together.
    Returns:
        dict: Configuration generation settings.
    """
    variables = ve.build_variables_dict(
        titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals,
        from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals,
        format_vals, group_vals,
    )
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
                ui.tooltip_icon("The name template for the configurations to be generated. The extension '.txt' is not required. Use variable names enclosed in curly braces, prefixed by a dollar sign (e.g., ${variable_name}) to indicate where variable values should be inserted."),
                dcc.Input(
                    id="generator-name",
                    value=defval("name", ""),
                    type="text",
                    style={"width": "100%", "fontFamily": "monospace", "fontWeight": "500"}
                ),
            ], style={"marginBottom": "12px"}),
            html.Div([
                html.Label("Content template"),
                ui.tooltip_icon("The content template for the configurations to be generated. Use variable names enclosed in curly braces, prefixed by a dollar sign (e.g., ${variable_name}) to indicate where variable values should be inserted."),
                dcc.Textarea(
                    id="generator-template",
                    value=defval("template", ""),
                    className="auto-resize-textarea",
                    style={"width": "100%", "resize": "none", "fontFamily": "monospace", "fontWeight": "500"},
                ),
            ], style={"marginBottom": "12px"}),
            dcc.Store(id="generator-initial-settings", data=settings),
            dcc.Store(id="generator-saved-settings", data=None),
        ],
        id="config-parameters",
        className="tile config",
    )

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
            style={"textDecoration": "none", "height": "100%"},
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
        Output({"type": "variable-field-group-div", "name": dash.ALL}, "style"),
    ],
    Input({"type": "variable-type", "name": dash.ALL}, "value"),
)
def update_variable_fields_visibility(types):
    styles_by_field = ve.field_styles_for_types(types)
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
        styles_by_field["group"],
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
    State({"type": "variable-field-group", "name": dash.ALL}, "value"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_form_and_variable_cards(
    search, page, new_click, duplicate_clicks, delete_clicks, cards,
    types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals, group_vals,
    odatix_settings
):
    trigger_id = ctx.triggered_id

    if trigger_id == "url":
        if page != page_path:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update

        mode, instance_name, base_path = get_instance_context(search, odatix_settings)
        domain = get_key_from_url(search, "domain")
        if not domain:
            domain = hard_settings.main_parameter_domain
        if not instance_name:
            return [], dash.no_update, dash.no_update, dash.no_update

        settings = workspace.load_instance_domain_settings(base_path, instance_name, domain, kind=mode)
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
                gen_settings = dict(gen_settings, template=generator_template)
        else:
            # Default template
            generator_name = "config_${var1}${var2}"
            generator_template = "parameter VALUE1 = ${var1};\nparameter VALUE2 = ${var2};"
            variables = {
                "var1": {"type": "range", "settings": {"from": 1, "to": 3, "step": 1}},
                "var2": {"type": "list", "settings": {"list": ["A", "B", "C", "D"]}},
            }
            # The defaults are what the form shows, so they are the reference the
            # save button compares against: nothing is modified yet.
            gen_settings = {
                "name": generator_name,
                "template": generator_template,
                "variables": variables,
            }


        # Create cards from existing variables, plus the Add card
        cards = ve.variable_cards_from_dict(VE_PREFIX, variables)
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
        cards.append(ve.variable_card(VE_PREFIX, new_name))

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
                    cards.append(ve.variable_card(
                        VE_PREFIX,
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
                        group_value=group_vals[idx],
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
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
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
    Input({"type": "variable-field-group", "name": dash.ALL}, "value"),
    State({"type": "variable-metadata", "name": dash.ALL}, "data"),
    State("odatix-settings", "data"),
)
def update_generation(
    search, page, n_click_save, n_click_gen,
    name, template,
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals, group_vals,
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
        titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals, group_vals
    )

    generator = ConfigGenerator(data=gen_settings)
    generated_params, variables = generator.generate()
    
    mode, instance_name, base_path = get_instance_context(search, odatix_settings)
    domain = get_key_from_url(search, "domain")
    if not domain:
        domain = hard_settings.main_parameter_domain
    if trigger_id == {"page": page_path, "action": "save-all"} or trigger_id == {"action": "generate-all"}:
        if domain and instance_name:
            workspace.update_instance_domain_settings(
                path=base_path,
                name=instance_name,
                domain=domain,
                settings_to_update=gen_settings,
                kind=mode,
            )
            if trigger_id == {"page": page_path, "action": "save-all"}:
                return dash.no_update, dash.no_update, dash.no_update

    if trigger_id == {"action": "generate-all"}:
        for config_name, config_content in generated_params.items():
            instance_domain_path = workspace.get_arch_domain_path(base_path, instance_name, domain)
            config_file_path = os.path.join(instance_domain_path, f"{config_name}.txt")
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
    mode, instance_name = get_instance_mode(search)
    domain = get_key_from_url(search, "domain")
    if not domain:
        domain = hard_settings.main_parameter_domain

    if not instance_name:
        return "No architecture or workflow selected."

    if domain == hard_settings.main_parameter_domain:
        title = f"{instance_name} - Main parameter domain"
    else:
        title = f"{instance_name} - {domain}"
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
    trigger_id = ctx.triggered_id
    if not isinstance(trigger_id, dict) or "name" not in trigger_id:
        return [dash.no_update] * len(n_clicks), [dash.no_update] * len(n_clicks)
    names = [m.get("name") if isinstance(m, dict) else None for m in (metadata or [])]
    return ve.toggle_more_fields(n_clicks, expandable_area_styles, icon_classes, names, trigger_id.get("name"))

@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output("generator-saved-settings", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
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
    Input({"type": "variable-field-group", "name": dash.ALL}, "value"),
    State("generator-initial-settings", "data"),
    State("generator-saved-settings", "data"),
    State({"type": "variable-metadata", "name": dash.ALL}, "data"),
    prevent_initial_call=True
)
def update_save_button(
    save_n_clicks, generate_n_clicks, name, template,
    title_values, type_values, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals, group_vals,
    initial_settings, saved_settings, metadata
):
    button_disabled = "color-button disabled icon-button"
    button_enabled = "color-button warning icon-button tooltip delay bottom small"

    trigger_id = ctx.triggered_id

    if trigger_id == {"page": page_path, "action": "save-all"} or trigger_id == {"action": "generate-all"}:
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

    if ve.field_value_changed(name, old_name) or ve.field_value_changed(template, old_template):
        print(f"Name or template changed, enabling save button : {name} != {old_name} or {template} != {old_template}")
        return button_enabled, dash.no_update

    fields = [
        ("name", title_values),
        ("type", type_values),
        ("base_value", base_vals),
        ("from_value", from_vals),
        ("to_value", to_vals),
        ("from_2_pow_value", from_2_pow_vals),
        ("to_2_pow_value", to_2_pow_vals),
        ("from_type_value", from_type_vals),
        ("to_type_value", to_type_vals),
        ("step_value", step_vals),
        ("op_value", op_vals),
        ("list_value", list_vals),
        ("source_value", source_vals),
        ("sources_value", sources_vals),
        ("format_value", format_vals),
        ("group_value", group_vals),
    ]
    for key, values in fields:
        for i, value in enumerate(values):
            if ve.field_value_changed(value, metadata[i].get(key)):
                print(f"Field '{key}' changed for variable {metadata[i].get('name')}, enabling save button.")
                return button_enabled, dash.no_update

    return button_disabled, dash.no_update

@dash.callback(
    Output(f"{page_path}-dummy1", "data"), # For older versions of Dash that do not support no_output
    Input({"action": "clean-all"}, "n_clicks"),
    State("url", "search"),
    State("odatix-settings", "data"),
)
def clean_all_configs(n_clicks, search, odatix_settings):
    mode, instance_name, base_path = get_instance_context(search, odatix_settings)
    domain = get_key_from_url(search, "domain")
    if not domain:
        domain = hard_settings.main_parameter_domain

    trigger_id = ctx.triggered_id
    if trigger_id == {"action": "clean-all"} and n_clicks:
        workspace.delete_all_config_files(base_path, instance_name, domain)

    return dash.no_update

@dash.callback(
    Output("config-gen-back-button", "href"),
    Input("url", "search"),
)
def update_back_button_link(search):
    mode, instance_name = get_instance_mode(search)
    key = "workflow" if mode == "workflow" else "arch"
    return f"/config_editor?{key}={instance_name}"


######################################
# Layout
######################################

variable_title_tile_buttons = html.Div(
    children=[
        ui.save_button(
            id={"page": page_path, "action": "save-all"},
            tooltip="Save all changes",
            disabled=True,
        ),
    ],
    className="inline-flex-buttons",
)
preview_title_tile_buttons = html.Div(
    children=[
        ui.icon_button(
            icon=icon("clean", className="icon red"),
            color="caution",
            id={"action": "clean-all"},
            tooltip="Delete all existing configuration files in this parameter domain",
        ),
        ui.icon_button(
            icon=icon("generate", className="icon blue"),
            color="secondary",
            text="Generate", 
            id={"action": "generate-all"},
            tooltip="Generate all previewed configurations",
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
                    ve.variable_card(VE_PREFIX, name="var", type_value="range", from_value="1", to_value="10", step_value="1"),
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
                style={"marginBottom": "30px"},
            ),
        ]),
        dcc.Store(id={"type": "update_url", "id": page_path}),
        dcc.Store(id=f"{page_path}-dummy1"),
    ],
    className="page-content",
    style={
        "padding": "0 16%",
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    }
)

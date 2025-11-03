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
import uuid
import random

import odatix.gui.ui_components as ui
from odatix.gui.utils import get_key_from_url
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings
import odatix.components.replace_params as replace_params
import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.css_helper import Style

verbose = False

page_path = "/config_editor"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Configuration Editor',
    name='Configuration Editor',
    order=4,
)

######################################
# Helper Functions
######################################

def split_by_domain(flat_list, lengths):
    result = []
    idx = 0
    for l in lengths:
        result.append(flat_list[idx:idx+l])
        idx += l
    return result

def get_index_from_trigger(trig_domain_uuid, trig_filename, metadata):
    index = next(
        (i for i, data in enumerate(metadata)
        if data.get("domain_uuid") == trig_domain_uuid and data.get("filename") == trig_filename),
        -1
    )
    return index

def get_uuid():
    return str(uuid.uuid4())

def generate_config_link(arch_name: str = "", domain_name: str = "") -> str:
    if domain_name:
        return f"/config_generator?arch={arch_name}&domain={domain_name}"
    else:
        return f"/config_generator?arch={arch_name}"

######################################
# UI Components
######################################

def config_card(domain_uuid, filename, content, initial_content, config_layout="normal"):
    display_name = filename[:-4] if filename.endswith(".txt") else filename

    save_class =  "color-button disabled"
    status_text = ""
    status_class = "status"
    return html.Div([
        html.Div([
            dcc.Input(
                value=f"{display_name}",
                type="text",
                id={"type": "config-title", "domain_uuid": domain_uuid, "filename": filename},
                className="title-input",
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
        ]),
        dcc.Textarea(
            id={"type": "config-content", "domain_uuid": domain_uuid, "filename": filename},
            value=content,
            className="auto-resize-textarea" if config_layout != "compact" else "",
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
        ),
        dcc.Store(id={"type": "config-metadata", "domain_uuid": domain_uuid, "filename": filename}, data={"domain_uuid": domain_uuid, "filename": filename}),
        html.Div([
            html.Div([
                html.Div([ui.icon_button(
                    icon=icon("save", className="icon", id={"type": "save-config-icon", "domain_uuid": domain_uuid, "filename": filename}),
                    color="disabled",
                    text="Save", 
                    width="78px",
                    id={"type": "save-config", "domain_uuid": domain_uuid, "filename": filename},
                ),], style={"marginLeft": "5px"}),
                html.Div(status_text, id={"type": "save-status", "domain_uuid": domain_uuid, "filename": filename}, className=status_class, style={"marginLeft": "0px", "textwrap": "wrap", "width": "70px", "font-size": "13px", "font-weight": "515"}),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": "duplicate-config", "domain_uuid": domain_uuid, "filename": filename}),
                ui.delete_button(id={"type": "delete-config", "domain_uuid": domain_uuid, "filename": filename}),
            ]),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
        dcc.Store(id={"type": "initial-title", "domain_uuid": domain_uuid, "filename": filename}, data=display_name),
        dcc.Store(id={"type": "initial-content", "domain_uuid": domain_uuid, "filename": filename}, data=initial_content),
    ], 
    className="card configs", 
    id={"type": "config-card", "domain_uuid": domain_uuid, "filename": filename},
    style={
        "padding": "10px", 
        "margin": "5px", 
        "display": "inline-block", 
        "verticalAlign": "top"
    })

def add_card(text: str = "Add design configuration", domain_uuid: str = hard_settings.main_parameter_domain):
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
                style={"textAlign": "center"}
            ),
            id={"type": "new-config", "domain_uuid": domain_uuid},
            n_clicks=0,
            style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
        ),
        className=f"card configs add hover",
        id={"type": "add-config-card", "domain_uuid": domain_uuid},
        style={
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box"
        },
    )

def architecture_title(arch_name:str=""):
    title_content = html.Div(
        children=[
            html.H3(arch_name, id=f"main_title", style={"marginBottom": "0px"}),
            html.Div(
                children=[
                    ui.icon_button(
                        id=f"button-open-config-editor",
                        icon=icon("gear", className="icon"),
                        text="Architecture Settings",
                        color="default",
                        link=f"/arch_editor?arch={arch_name}",
                        multiline=True,
                        width="135px",
                    ),
                    dcc.Dropdown(
                        id="config-layout-dropdown", 
                        options=[
                            {"label": "Compact Layout", "value": "compact"},
                            {"label": "Normal Layout", "value": "normal"},
                            {"label": "Wide Layout", "value": "wide"},
                        ],
                        value="normal",
                        clearable=False,
                        style={"width": "155px"},
                    ),
                ],
                className="inline-flex-buttons",
            )
        ],
        className="title-tile-flex",
        style={
            "display": "flex",
            "alignItems": "center",
            "padding": "0px",
            "justifyContent": "space-between",
        }
    )
    back_btn = ui.back_button(link="/architectures")
    return html.Div([
        html.Div(style={"display": "none"}),
        html.Div(style={"display": "none"}),
        html.Div(style={"display": "none"}),
        html.Div(
            children=[
                back_btn,
                title_content
            ],
            className="tile title",
            style={"position": "relative"},
        )],
        className="card-matrix config",
        style={"marginLeft": "-13px", "marginBottom": "0px"},
    )

def parameter_domain_title(domain_name:str=hard_settings.main_parameter_domain, domain_uuid:str=hard_settings.main_parameter_domain, arch_name:str=""):
    if domain_uuid == hard_settings.main_parameter_domain:
        text = "Main parameter domain"
        buttons = html.Div(
            children=[
                ui.icon_button(
                    # id={"type": "generate-config", "domain_uuid": domain_uuid},
                    icon=icon("generate", className="icon"),
                    text="Config Generator",
                    color="default",
                    link=generate_config_link(arch_name=arch_name),
                    multiline=True,
                    tooltip="Generate multiple design configurations",
                ),
                ui.duplicate_button(
                    id={"action": "duplicate-domain", "domain_uuid": domain_uuid},
                    tooltip="Duplicate as a new domain",
                ),
                # ui.icon_button(
                #     id={"action": "duplicate-domain", "domain_uuid": domain_uuid},
                #     icon=icon("duplicate", className="icon"),
                #     text="Duplicate as Domain",
                #     color="secondary",
                #     multiline=True,
                #     width="140px",
                #     tooltip="Duplicate the main parameter domain as a new domain",
                # ),
            ],
            className="inline-flex-buttons",
        )
        tooltip = "The main parameter domain is the default domain used for parameter replacement. Several parameter domains can be created to manage different sets of parameters for different design configurations or scenarios. It mainly serves as a convenient way to organize design configurations and to easily run combinations of design configurations across multiple domains."

        return ui.title_tile(text=text, id=f"domain_title_{domain_uuid}", buttons=buttons, tooltip=tooltip)
    else:
        buttons = html.Div(
            children=[
                ui.icon_button(
                    id={"type": "generate-config", "domain_uuid": domain_uuid},
                    icon=icon("generate", className="icon"),
                    text="Config Generator",
                    color="default",
                    link=generate_config_link(arch_name=arch_name, domain_name=domain_name),
                    multiline=True,
                    tooltip="Generate multiple design configurations",
                ),
                ui.duplicate_button(
                    id={"action": "duplicate-domain", "domain_uuid": domain_uuid},
                    tooltip="Duplicate domain",
                ),
                ui.delete_button(
                    id={"action": "delete-domain", "domain_uuid": domain_uuid},
                    large=False,
                    tooltip="Delete domain",
                )
            ],
            className="inline-flex-buttons param-domain-title",
        )
        title_content = html.Div([
            html.Div([
                html.H3("Parameter domain:", style={"display": "inline-block", "marginBottom": "0px", "marginRight": "10px"}),
                dcc.Input(
                    value=domain_name,
                    type="text",
                    id={"type": "domain-title-input", "domain_uuid": domain_uuid},
                    className="title-input domain",
                    style={
                        "marginBottom": "0",
                        "marginTop": "0",
                        "marginRight": "5px",
                        "verticalAlign": "middle",
                        "position": "relative",
                        "top": "-4px",
                    }
                ),
                ui.icon_button(
                    id={"type": "save-domain-title", "domain_uuid": domain_uuid},
                    icon=icon("check", className="icon invisible"),
                    color="invisible",
                    style={"transform": "translateY(6px)"},
                ),
            ],
            style={
                "justifyContent": "flex-start"
            }),
            buttons,
        ],
        className="title-tile-flex",
        style={
            "display": "flex",
            "alignItems": "center",
            "padding": "0px",
            "justifyContent": "space-between",
        }) 
    return html.Div(
        [title_content],
        id={"type": "param-domain-title", "domain_uuid": domain_uuid}, 
        className="tile title",
        style={"marginTop": "50px"} if domain_uuid != hard_settings.main_parameter_domain else {}
    )

def add_parameter_domain_button(text:str="Main parameter domain"):
    return html.Div(
        [
            html.H3(text, style={"marginBottom": "0px"})
        ], 
        id={"type": "button", "action": "add-domain"}, 
        n_clicks=0,
        className="tile title add hover",
        style={
            "marginTop": "50px",
            "textAlign": "center",
            "border": "1px dashed #bbb",
        },
    )

def config_parameters_form(domain_uuid, settings):
    defval = lambda k, v=None: settings.get(k, v)

    save_button = html.Div(
        children=[
            ui.icon_button(
                icon=icon("save", className="icon", id={"type": "save-params-icon", "domain_uuid": domain_uuid}),
                color="disabled",
                text="Save", 
                width="78px",
                id={"type": "save-params-btn", "domain_uuid": domain_uuid},
            ),
        ],
        style={"marginBottom": "10px"},
        className="inline-flex-buttons",
    )
    use_parameters = defval("use_parameters", True)
    return html.Div(
        children=[
            ui.subtitle_div(text="Configuration Parameters", buttons=save_button),
            dcc.Checklist(
                options=[{"label": "Enable parameter replacement", "value": True}],
                value=[True] if use_parameters else [],
                id={"type": "use_parameters", "domain_uuid": domain_uuid},
                className="checklist-switch",
                style={"marginBottom": "12px", "marginTop": "5px"},
            ),
            html.Div(
                children=[
                    html.Div([
                        html.Label("Param Target File"),
                        ui.tooltip_icon("The file used as the target for parameter replacement. This is typically the top-level design file or a design configuration file."),
                        dcc.Input(id={"type": "param_target_file", "domain_uuid": domain_uuid}, value=defval("param_target_file", ""), type="text", placeholder="Top level file used by default", style={"width": "95%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Start Delimiter"),
                        ui.tooltip_icon("The delimiter that marks the beginning of a section to be replaced in the target file."),
                        dcc.Input(id={"type": "start_delimiter", "domain_uuid": domain_uuid}, value=defval("start_delimiter", ""), type="text", style={"width": "95%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Stop Delimiter"),
                        ui.tooltip_icon("The delimiter that marks the end of a section to be replaced in the target file."),
                        dcc.Input(id={"type": "stop_delimiter", "domain_uuid": domain_uuid}, value=defval("stop_delimiter", ""), type="text", style={"width": "95%"}),
                    ], style={"marginBottom": "12px"}),
                ],
                id={"type": "params-config-fields", "domain_uuid": domain_uuid}, className="animated-section" if use_parameters else "animated-section hide",
            ),
            html.Div(id={"type": "save-params-status", "domain_uuid": domain_uuid}, className="status", style={"marginLeft": "16px"}),
        ]
    )

def preview_pane(domain_uuid:str, settings: dict, domain_settings: dict, replacement_text: str):
    use_parameters = domain_settings.get("use_parameters", True)
    if not use_parameters:
        return preview_div(html.Div("Parameter replacement disabled.", style={"color": "#888"}))
    param_target_file = domain_settings.get("param_target_file", "")
    generate_rtl = settings.get("generate_rtl", False)
    generate_rtl = True if generate_rtl else False # Convert from [True]/[] to True/False
    if generate_rtl:
        base_path = settings.get("design_path", "")
        if not base_path:
            return preview_div(html.Div("No design path specified in architecture settings. Unable to preview.", className="error"))
        if param_target_file == "":
            param_target_file = settings.get("top_level_file", "")
    else:
        rtl_path = settings.get("rtl_path", "")
        if not rtl_path:
            return preview_div(html.Div("No RTL path specified in architecture settings. Unable to preview.", className="error"))
        base_path = rtl_path
        if param_target_file == "":
            param_target_file = os.path.join(settings.get("top_level_file", ""))
    param_target_file = os.path.join(base_path, param_target_file)
    if os.path.exists(param_target_file):
        base_text = replace_params.read_file(param_target_file)
        start_delimiter = domain_settings.get("start_delimiter", "")
        stop_delimiter = domain_settings.get("stop_delimiter", "")
        new_content, match_found = replace_params.replace_content(
            base_text=base_text,
            replacement_text=replacement_text,
            start_delim=start_delimiter, 
            stop_delim=stop_delimiter, 
            replace_all_occurrences=False,
        )
        if not match_found:
            preview_components=html.Span(base_text, style={"whiteSpace": "pre-wrap", "color": "#FA5252", "fontWeight": "800"}) 
        else:
            start_line, start_charater = replace_params.get_first_appearance(new_content, start_delimiter)
            stop_line, stop_charater = replace_params.get_first_appearance(new_content, stop_delimiter, start_line=start_line, start_char=start_charater+len(start_delimiter)+1)
            lines = new_content.splitlines()
            preview_start = 0
            preview_stop = len(lines)
            preview_lines = lines[preview_start:preview_stop]
            preview_components = []
            # preview_components.append(html.Span("[...]\n", style={"color": "#888"}))
            for idx, line in enumerate(preview_lines):
                line_idx = preview_start + idx
                line_parts = []

                # Case where start and stop are on the same line
                if start_line == stop_line and line_idx == start_line - 1:
                    s_idx = start_charater
                    e_idx = stop_charater
                    if s_idx > 0:
                        line_parts.append(line[:s_idx])
                    line_parts.append(html.Span(start_delimiter, className="text-highlight primary"))
                    line_parts.append(html.Span(line[s_idx+len(start_delimiter):e_idx], className="text-highlight secondary"))
                    line_parts.append(html.Span(stop_delimiter, className="text-highlight primary"))
                    if e_idx + len(stop_delimiter) < len(line):
                        line_parts.append(line[e_idx+len(stop_delimiter):])
                # Start delimiter line
                elif line_idx == start_line - 1:
                    if start_charater != -1:
                        if start_charater > 0:
                            line_parts.append(line[:start_charater])
                        line_parts.append(html.Span(start_delimiter, className="text-highlight primary"))
                        line_parts.append(html.Span(line[start_charater+len(start_delimiter):], className="text-highlight secondary"))
                    else:
                        line_parts.append(line)
                # Stop delimiter line
                elif line_idx == stop_line - 1:
                    if stop_charater != -1:
                        if stop_charater > 0:
                            line_parts.append(html.Span(line[:stop_charater], className="text-highlight secondary"))
                        line_parts.append(html.Span(stop_delimiter, className="text-highlight primary"))
                        if stop_charater + len(stop_delimiter) < len(line):
                            line_parts.append(line[stop_charater+len(stop_delimiter):])
                    else:
                        line_parts.append(line)
                # Replaced content lines
                elif start_line-1 < line_idx < stop_line-1:
                    line_parts.append(html.Span(line, className="text-highlight secondary"))
                else:
                    line_parts.append(line)
                preview_components.extend(line_parts)
                preview_components.append(html.Br())
            # preview_components.append(html.Span("[...]", style={"color": "#888"}))

        pane_content = html.Pre(
            children=preview_components,
            id={"type": "preview-pre", "domain_uuid": domain_uuid},
            className="preview-pane",
            style={
                "width": "95%",
                "max-width": "600px",
                "height": "235px",
                "min-height": "235px",
                "fontFamily": "monospace",
                "fontSize": "0.9em",
                "fontWeight": "normal",
                "padding": "5px",
                "overflow": "auto",
                "whiteSpace": "pre-wrap",
                "resize": "vertical",
            }
        )
    else:
        if base_path == "" or param_target_file == "":
            text = f"Invalid architecture settings. Unable to preview."
        elif settings == {}:
            text = f"No settings found."
        else:
            text = f"Preview file '{os.path.realpath(param_target_file)}' not found. Unable to preview."
        pane_content = html.Div(text, className="error")
    return preview_div(pane_content)

def preview_div(content):
    return html.Div(
        children=[
            html.H3("Preview Pane"),
            content,
        ], 
    )

def domain_section(domain: str, arch_name: str = "", settings: dict = {}):
    # Generate a unique UUID for non-main domains
    domain_uuid = get_uuid() if domain != hard_settings.main_parameter_domain else domain
    
    # Hidden divs for better animations
    hidden_count = random.randint(4, 7)
    title_hidden_divs = [html.Div(style={"display": "none"}) for _ in range(hidden_count)]
    hidden_count = random.randint(8, 12)
    content_hidden_divs = [html.Div(style={"display": "none"}) for _ in range(hidden_count)]
    
    # Domain Section
    return html.Div(
        children=[
            html.Div(
                children=[
                    *title_hidden_divs,
                    parameter_domain_title(domain_name=domain, domain_uuid=domain_uuid, arch_name=arch_name)
                ], 
                id=f"param-domain-title-div-{domain_uuid}",
                className="card-matrix config",
                style={"marginLeft": "-13px"},
            ),
            html.Div(
                children=[
                    *content_hidden_divs,
                    html.Div(
                        children=[
                            config_parameters_form(domain_uuid, settings),
                        ],
                        id={"type": "config-parameters", "domain_uuid": domain_uuid}, 
                        className="tile config"),
                    html.Div(id={"type": "preview-pane", "domain_uuid": domain_uuid}, className="tile config"),
                ], 
                className="card-matrix config",
                style={"marginLeft": "-13px"},
            ),
            html.Div([
                html.Div(
                    id={"type": "config-cards-row", "domain_uuid": domain_uuid},
                    className=f"card-matrix configs", 
                ),
            ]),
            dcc.Store(id={"type": "config-files-store", "domain_uuid": domain_uuid}),
            dcc.Store(id={"type": "config-params-store", "domain_uuid": domain_uuid}, data=settings),
            dcc.Store(id={"type": "initial-configs-store", "domain_uuid": domain_uuid}),
            dcc.Store(id={"type": "domain-metadata", "domain_uuid": domain_uuid}, data={"domain_name": domain, "domain_uuid": domain_uuid}),
        ],
        id = {"type": "param-domain-section", "domain_uuid": domain_uuid},
    )


######################################
# Callbacks
######################################

@dash.callback(
    Output(f"param-domain-title-div-{hard_settings.main_parameter_domain}", "children"),
    Input("param-domains-section", "children"),
    State("url", "search"),
    preview_initial_call=True
)
def update_main_domain_title(_, search):
    arch_name = get_key_from_url(search, "arch")
    if not arch_name:
        return "No architecture selected.", dash.no_update
    return parameter_domain_title(domain_uuid=hard_settings.main_parameter_domain, arch_name=arch_name)

@dash.callback(
    Output("param-domains-section", "children"),
    Input("url", "search"),
    State("url", "pathname"),
    Input({"action": "add-domain", "type": dash.ALL}, "n_clicks"),
    Input({"action": "duplicate-domain", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"action": "delete-domain", "domain_uuid": dash.ALL}, "n_clicks"),
    State("odatix-settings", "data"),
    State("param-domains-section", "children"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    prevent_initial_call=True
)
def update_param_domains(
    search, page, add_domain_click, duplicate_domain_click, delete_domain_click,
    odatix_settings, domain_sections, metadata
):
    triggered_id = ctx.triggered_id
    if triggered_id == "url":
        if page != page_path:
            return dash.no_update

    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_key_from_url(search, "arch")
    if not arch_name:
        return html.Div(
            children=[
                html.Div("No architecture selected.", className="error")
            ],
            className="card-matrix config",
            style={"marginLeft": "-13px"},
        )

    add_domain_div = html.Div(
        children=[
            add_parameter_domain_button("Add new parameter domain")
        ],
        className="card-matrix config",
        style={"marginLeft": "-13px"},
    )

    if not workspace.architecture_exists(arch_path, arch_name):
        domain_sections = []
        domain_sections.append(domain_section(hard_settings.main_parameter_domain, arch_name, settings={}))
        domain_sections.append(add_domain_div)
        return domain_sections

    domains = workspace.get_param_domains(arch_path, arch_name)

    # Generate domain sections
    if triggered_id == "url":
        domain_sections = []
        settings = workspace.load_architecture_settings(arch_path, arch_name, hard_settings.main_parameter_domain)
        domain_sections.append(domain_section(hard_settings.main_parameter_domain, settings=settings))
        for domain in domains:
            settings = workspace.load_architecture_settings(arch_path, arch_name, domain)
            settings["arch_name"] = arch_name
            domain_sections.append(domain_section(domain, arch_name, settings=settings))
        domain_sections.append(add_domain_div)
        return domain_sections
    
    elif isinstance(triggered_id, dict):
        trigger_action = triggered_id.get("action", "")
        # Add a new domain
        if trigger_action == "add-domain":
            base_name = "new_domain"
            suffix = 1
            new_domain = f"{base_name}{suffix}"
            while new_domain in domains:
                suffix += 1
                new_domain = f"{base_name}{suffix}"
            workspace.create_parameter_domain(arch_path, arch_name, new_domain)
            
            # Insert new domain section before the add domain button
            domain_sections = domain_sections[:-1] if isinstance(domain_sections, list) else []
            domain_sections.append(domain_section(new_domain, arch_name, settings={}))
            domain_sections.append(add_domain_div)
            return domain_sections

        # Duplicate domain
        elif trigger_action == "duplicate-domain":
            domain_to_duplicate_uuid  = triggered_id.get("domain_uuid", "")

            # Check if button was actually clicked
            domain_to_duplicate = None
            domain_to_duplicate_idx = None
            for i, data in enumerate(metadata):
                domain_uuid = data.get("domain_uuid", "")
                domain_name = data.get("domain_name", "")
                if domain_uuid == domain_to_duplicate_uuid:
                    domain_to_duplicate = domain_name
                    domain_to_duplicate_idx = i - 1 # -1 to account for main domain
                    break
            if duplicate_domain_click[domain_to_duplicate_idx] == 0:
                return dash.no_update
            
            if domain_to_duplicate_uuid :
                if domain_to_duplicate_uuid  == hard_settings.main_parameter_domain:
                    base_name = "main_copy"
                else:
                    base_name = f"{domain_to_duplicate}_copy"
                suffix = 1
                new_domain = f"{base_name}{suffix}"
                while new_domain in domains:
                    suffix += 1
                    new_domain = f"{base_name}{suffix}"
                workspace.duplicate_parameter_domain(
                    arch_path, arch_name, arch_name, domain_to_duplicate, new_domain
                )

                # Insert new domain section before the add domain button
                domain_sections = domain_sections[:-1] if isinstance(domain_sections, list) else []
                domain_sections.append(domain_section(new_domain, arch_name, settings={}))
                domain_sections.append(add_domain_div)
                return domain_sections

        # Delete domain
        elif trigger_action == "delete-domain":
            domain_to_delete_uuid = triggered_id.get("domain_uuid", "")

            # Check if button was actually clicked
            domain_to_delete = None
            domain_to_delete_idx = None
            for i, data in enumerate(metadata):
                domain_uuid = data.get("domain_uuid", "")
                domain_name = data.get("domain_name", "")
                if domain_uuid == domain_to_delete_uuid:
                    domain_to_delete = domain_name
                    domain_to_delete_idx = i - 1 # -1 to account for main domain
                    break
            if domain_to_delete_idx and delete_domain_click[domain_to_delete_idx] == 0:
                return dash.no_update
            
            if domain_to_delete and domain_to_delete != hard_settings.main_parameter_domain:
                workspace.delete_parameter_domain(arch_path, arch_name, domain_to_delete)
                if isinstance(domain_sections, list):
                    for i, section in enumerate(domain_sections):
                        domain = section.get("props", {}).get("id", {}).get("domain_uuid", "")
                        if domain == domain_to_delete_uuid:
                            domain_sections.pop(i)
                            return domain_sections

    return dash.no_update

@dash.callback(
    Output({"type": "config-cards-row", "domain_uuid": dash.ALL}, "children"),
    Output({"type": "config-files-store", "domain_uuid": dash.ALL}, "data"),
    Output({"type": "initial-configs-store", "domain_uuid": dash.ALL}, "data"),
    State("url", "search"),
    Input("param-domains-section", "children"),
    Input("config-layout-dropdown", "value"),
    Input({"type": "new-config", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "save-config", "domain_uuid": dash.ALL, "filename": dash.ALL}, "n_clicks"),
    Input({"type": "delete-config", "domain_uuid": dash.ALL, "filename": dash.ALL}, "n_clicks"),
    Input({"type": "duplicate-config", "domain_uuid": dash.ALL, "filename": dash.ALL}, "n_clicks"),
    State({"type": "config-title", "domain_uuid": dash.ALL, "filename": dash.ALL}, "value"),
    State({"type": "config-content", "domain_uuid": dash.ALL, "filename": dash.ALL}, "value"),
    State({"type": "config-metadata", "domain_uuid": dash.ALL, "filename": dash.ALL}, "data"),
    State({"type": "config-files-store", "domain_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_config_cards(
    search, param_domains_section,
    config_layout, add_click, save_clicks, delete_clicks, duplicate_clicks,
    title_values, contents, config_metadata, configs_list, domain_metadata, odatix_settings
):
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_key_from_url(search, "arch")
    if not arch_name:
        return [html.Div("No architecture selected.", className="error")], [{}], [{}]

    triggered_id = ctx.triggered_id
    if not isinstance(triggered_id, dict):
        domains = {}
        for data in domain_metadata:
            domain_name = data.get("domain_name", "")
            domain_uuid = data.get("domain_uuid", "")
            domains[domain_uuid] = domain_name
    else:
        domains = {}
        trig_type = triggered_id.get("type", None)
        trig_domain_uuid = triggered_id.get("domain_uuid", hard_settings.main_parameter_domain)
        trig_domain_name = ""

        # Get domain from metadata
        trig_domain_idx = -1
        for i, data in enumerate(domain_metadata):
            domain_name = data.get("domain_name", "")
            domain_uuid = data.get("domain_uuid", "")
            domains[domain_uuid] = domain_name
            if domain_uuid == trig_domain_uuid:
                trig_domain_name = domain_name
                trig_domain_idx = i

        if trig_type == "new-config" and add_click:
            for idx in range(1, 1001):
                new_filename = f"new_config{idx}.txt"
                if new_filename not in configs_list[trig_domain_idx]:
                    workspace.save_config_file(arch_path, arch_name, trig_domain_name, new_filename, "")
                    configs_list[trig_domain_idx][new_filename] = ""
                    break
            else:
                error_msg = "Too many config creation fails (1000 max)."

        elif trig_type in ["save-config", "delete-config", "duplicate-config"]:         

            trig_filename = triggered_id.get("filename", "")
            
            # Save config (and handle rename)
            if trig_type == "save-config":
                config_index = get_index_from_trigger(trig_domain_uuid, trig_filename, config_metadata)
                config_new_title = title_values[config_index] if config_index >= 0 and config_index < len(title_values) else ""
                config_old_title = trig_filename
                config_content = contents[config_index] if config_index >= 0 and config_index < len(contents) else ""
                
                if not config_new_title.endswith(".txt"):
                    config_new_title = config_new_title + ".txt"
                if config_new_title != config_old_title:
                    if config_new_title in configs_list[trig_domain_idx]:
                        if verbose:
                            print(f"File '{config_new_title}' already exists.")
                    else:
                        path = workspace.get_arch_domain_path(arch_path, arch_name, trig_domain_name)
                        old_path = os.path.join(path, config_old_title)
                        new_path = os.path.join(path, config_new_title)
                        if verbose:
                            print(f"Renaming {old_path} to {new_path}")
                        os.rename(old_path, new_path)
                        configs_list[trig_domain_idx][config_new_title] = config_content
                        configs_list[trig_domain_idx].pop(config_old_title)
                        config_old_title = config_new_title
                if verbose:
                    print(f"Saving config '{config_old_title}' in domain '{trig_domain_name}'")
                workspace.save_config_file(arch_path, arch_name, trig_domain_name, config_new_title, config_content)
                configs_list[trig_domain_idx][config_old_title] = config_content

            # Delete config
            if trig_type == "delete-config":
                workspace.delete_config_file(arch_path, arch_name, trig_domain_name, trig_filename)
                configs_list[trig_domain_idx].pop(trig_filename)

            # Duplicate config
            if trig_type == "duplicate-config":
                base = trig_filename[:-4] if trig_filename.endswith(".txt") else trig_filename
                suffix = 1
                new_filename = f"{base}_copy{suffix}.txt"
                while new_filename in configs_list[trig_domain_idx]:
                    suffix += 1
                    new_filename = f"{base}_copy{suffix}.txt"
                workspace.save_config_file(arch_path, arch_name, trig_domain_name, new_filename, configs_list[trig_domain_idx][trig_filename])
                configs_list[trig_domain_idx][new_filename] = configs_list[trig_domain_idx][trig_filename]

    all_cards = []
    all_configs = []
    all_initial_configs = []

    for idx, (domain_uuid, domain_name) in enumerate(domains.items()):
        if True:
            files = workspace.get_config_files(arch_path, arch_name, domain_name)
            configs = {f: workspace.load_config_file(arch_path, arch_name, domain_name, f) for f in files}
        initial_configs = configs.copy()

        cards = [config_card(domain_uuid, f, configs[f], initial_configs.get(f, ""), config_layout) for f in configs]
        cards.append(add_card(domain_uuid=domain_uuid))

        all_cards.append(cards)
        all_configs.append(configs)
        all_initial_configs.append(initial_configs)
    return all_cards, all_configs, all_initial_configs

@dash.callback(
    Output({"type": "preview-pane", "domain_uuid": dash.ALL}, "children"),
    State("url", "search"),
    Input({"type": "config-cards-row", "domain_uuid": dash.ALL}, "children"),
    Input({"type": "use_parameters", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "param_target_file", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "start_delimiter", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "stop_delimiter", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "config-params-store", "domain_uuid": dash.ALL}, "data"),
    Input({"type": "config-content", "domain_uuid": dash.ALL, "filename": dash.ALL}, "value"),
    State({"type": "config-files-store", "domain_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_preview_all(search, config_cards_rows, params_enables, target_files, start_delims, stop_delims, settings_list, config_contents_list, configs_list, domain_metadata, odatix_settings):
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_key_from_url(search, "arch")
    if not workspace.architecture_exists(arch_path, arch_name):
        return [
            html.Div([
                html.Div("Architecture is not created yet."),
                html.Div("Edit settings, then save or add a new config to create it."),
            ], className="error warning")
        ] * len(config_cards_rows)

    triggered = ctx.triggered_id
    if isinstance(triggered, dict):
        if configs_list:
            filenames_per_domain = [list(configs.keys()) for configs in configs_list if configs is not None]
        else:
            filenames_per_domain = []
        lengths = [len(filenames) for filenames in filenames_per_domain]

        contents_by_domain = split_by_domain(config_contents_list, lengths)

        results = []
        for i, domain in enumerate(domain_metadata):
            domain_uuid = domain.get("domain_uuid", "")
            config_contents_list = contents_by_domain[i] if i < len(contents_by_domain) else []
            settings = settings_list[0] if 0 < len(settings_list) and settings_list[0] is not None else {}
            domain_settings = settings_list[i] if i < len(settings_list) and settings_list[i] is not None else {}
            domain_settings["use_parameters"] = params_enables[i] if i < len(params_enables) else ""
            domain_settings["param_target_file"] = target_files[i] if i < len(target_files) else ""
            domain_settings["start_delimiter"] = start_delims[i] if i < len(start_delims) else ""
            domain_settings["stop_delimiter"] = stop_delims[i] if i < len(stop_delims) else ""
            replacement_text = config_contents_list[0] if config_contents_list else ""
            results.append(preview_pane(domain_uuid, settings, domain_settings, replacement_text))
        return results
    return dash.no_update

@dash.callback(
    Output({"type": "save-config", "domain_uuid": dash.ALL, "filename": dash.ALL}, "className"),
    Output({"type": "save-status", "domain_uuid": dash.ALL, "filename": dash.ALL}, "className"),
    Output({"type": "save-status", "domain_uuid": dash.ALL, "filename": dash.ALL}, "children"),
    Input("param-domains-section", "children"),
    Input({"type": "config-title", "domain_uuid": dash.ALL, "filename": dash.ALL}, "value"),
    Input({"type": "config-content", "domain_uuid": dash.ALL, "filename": dash.ALL}, "value"),
    Input({"type": "initial-title", "domain_uuid": dash.ALL, "filename": dash.ALL}, "data"),
    Input({"type": "initial-content", "domain_uuid": dash.ALL, "filename": dash.ALL}, "data"),
    State({"type": "save-config", "domain_uuid": dash.ALL, "filename": dash.ALL}, "className"),
)
def update_save_status(param_domains_section, title_values, content_values, initial_titles, initial_contents, save_config):
    save_classes = []
    status_classes = []
    status_texts = []
    for title, content, initial_title, initial_content in zip(title_values, content_values, initial_titles, initial_contents):
        if title != initial_title or content != initial_content:
            save_classes.append("color-button warning icon-button")
            status_classes.append("status warning")
            status_texts.append("Unsaved changes!")
        else:
            save_classes.append("color-button disabled icon-button")
            status_classes.append("status")
            status_texts.append("")
    return save_classes, status_classes, status_texts

@dash.callback(
    Output({"type": "save-params-btn", "domain_uuid": dash.ALL}, "className"),
    Input({"type": "use_parameters", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "param_target_file", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "start_delimiter", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "stop_delimiter", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "config-params-store", "domain_uuid": dash.ALL}, "data"),
)
def update_params_save_button(params_enables, target_files, start_delims, stop_delims, settings_list):
    save_classes = []
    disabled_class = "color-button disabled icon-button"
    enabled_class = "color-button warning icon-button"

    for use_parameters, param_target_file, start_delimiter, stop_delimiter, domain_settings in zip(params_enables, target_files, start_delims, stop_delims, settings_list):
        if domain_settings is None:
            domain_settings = {}
        use_parameters = True if use_parameters else False # Convert from [True]/[] to True/False
        if use_parameters != domain_settings.get("use_parameters", True):
            save_classes.append(enabled_class)
        elif param_target_file != domain_settings.get("param_target_file", ""):
            save_classes.append(enabled_class)
        elif start_delimiter != domain_settings.get("start_delimiter", ""):
            save_classes.append(enabled_class)
        elif stop_delimiter != domain_settings.get("stop_delimiter", ""):
            save_classes.append(enabled_class)
        else:
            save_classes.append(disabled_class)
    return save_classes

@dash.callback(
    Output({"type": "config-card", "domain_uuid": dash.ALL, "filename": dash.ALL}, "className"),
    Output({"type": "add-config-card", "domain_uuid": dash.ALL}, "className"),
    Output({"type": "config-cards-row", "domain_uuid": dash.ALL}, "className"),
    Input("config-layout-dropdown", "value"),
    State({"type": "config-card", "domain_uuid": dash.ALL, "filename": dash.ALL}, "className"),
    State({"type": "add-config-card", "domain_uuid": dash.ALL}, "className"),
    State({"type": "config-cards-row", "domain_uuid": dash.ALL}, "className"),
)
def update_layout_style(layout_value, config_card_classes, add_card_classes, config_row_classes):
    if layout_value == "wide":
        config_card_classes = ["card configs wide" for _ in range(len(config_card_classes))]
        add_card_classes = ["card configs add wide hover" for _ in range(len(add_card_classes))]
        config_row_classes = ["card-matrix configs wide" for _ in range(len(config_row_classes))]
    else:
        config_card_classes = ["card configs" for _ in range(len(config_card_classes))]
        add_card_classes = ["card configs add hover" for _ in range(len(add_card_classes))]
        config_row_classes = ["card-matrix configs" for _ in range(len(config_row_classes))]
    return config_card_classes, add_card_classes, config_row_classes

@dash.callback(
    Output({"type": "config-params-store", "domain_uuid": dash.ALL}, "data"),
    Input({"type": "save-params-btn", "domain_uuid": dash.ALL}, "n_clicks"),
    State({"type": "use_parameters", "domain_uuid": dash.ALL}, "value"),
    State({"type": "param_target_file", "domain_uuid": dash.ALL}, "value"),
    State({"type": "start_delimiter", "domain_uuid": dash.ALL}, "value"),
    State({"type": "stop_delimiter", "domain_uuid": dash.ALL}, "value"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State("url", "search"),
    State("odatix-settings", "data"),
)
def save_config_parameters(
    n_clicks, 
    use_parameters, param_target_files, start_delimiters, stop_delimiters, domain_metadata,
    search, odatix_settings
):
    arch_name = get_key_from_url(search, "arch")
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)

    triggered = ctx.triggered_id
    if isinstance(triggered, dict):        
        trig_domain_uuid = triggered.get("domain", hard_settings.main_parameter_domain)
        trig_domain_name = trig_domain_uuid
        
        # Get domain from metadata
        for data in domain_metadata:
            domain_name = data.get("domain_name", "")
            domain_uuid = data.get("domain_uuid", "")
            if domain_uuid == trig_domain_uuid :
                trig_domain_name = domain_name
                break

        idx = next((i for i, data in enumerate(domain_metadata) if data.get("domain_uuid") == trig_domain_uuid), -1)
        if idx != -1:
            use_parameters = use_parameters[idx] if idx < len(use_parameters) else False
            use_parameters = True if use_parameters else False # Convert from [True]/[] to True/False
            param_target_file = param_target_files[idx] if idx < len(param_target_files) else ""
            start_delimiter = start_delimiters[idx] if idx < len(start_delimiters) else ""
            stop_delimiter = stop_delimiters[idx] if idx < len(stop_delimiters) else ""
            settings = {
                "use_parameters": use_parameters,
                "param_target_file": param_target_file,
                "start_delimiter": start_delimiter,
                "stop_delimiter": stop_delimiter,
            }
            workspace.update_domain_settings(arch_path, arch_name, trig_domain_name, settings)
            return [settings if i == idx else dash.no_update for i in range(len(domain_metadata))]
    return [dash.no_update for _ in range(len(domain_metadata))]

@dash.callback(
    Output({"type": "params-config-fields", "domain_uuid": dash.ALL}, "className"),
    Output({"type": "config-cards-row", "domain_uuid": dash.ALL}, "style"),
    Input ({"type": "use_parameters", "domain_uuid": dash.ALL}, "value"),
)
def toggle_params_fields(enabled_values):
    styles = []
    classes = []
    for value in enabled_values:
        if value:
            styles.append({})
            classes.append("animated-section")
        else:
            styles.append(Style.hidden)
            classes.append("animated-section hide")
    return classes, styles

@dash.callback(
    Output({"page": page_path, "type": "architecture-title-div"}, "children"),
    Input("url", "search"),
)
def update_architecture_title(search):
    arch_name = get_key_from_url(search, "arch")
    if not arch_name:
        arch_name = "New_Architecture"
    return architecture_title(arch_name)

@dash.callback(
    Output({"type": "save-domain-title", "domain_uuid": dash.ALL}, "className"),
    Output({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    Output({"type": "generate-config", "domain_uuid": dash.ALL, "is_link": True}, "href"),
    Input({"type": "save-domain-title", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "domain-title-input", "domain_uuid": dash.ALL}, "value"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State("url", "search"),
    State("odatix-settings", "data"),
)
def update_params_title_save_button(_, title_input, domain_metadata, search, odatix_settings):
    save_classes = []
    disabled_class = "color-button invisible icon-button"
    enabled_class = "color-button warning icon-button"
    error_class = "color-button disabled icon-button error-status"
    new_metadata = []
    new_hrefs = []

    triggered_id = ctx.triggered_id if isinstance(ctx.triggered_id, dict) else {}
    triggered_type = triggered_id.get("type", "")
    triggered_domain_uuid = triggered_id.get("domain_uuid", "")
    
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_key_from_url(search, "arch")
    if not arch_name:
        raise dash.exceptions.PreventUpdate

    domain_metadata = domain_metadata[1:] # Remove main domain entry
    new_metadata.append(dash.no_update)  # Placeholder for main domain
    for new_domain_name, metadata in zip(title_input, domain_metadata):
        domain_name = metadata.get("domain_name", "")
        domain_uuid = metadata.get("domain_uuid", "")

        # Save button clicked for this domain
        if triggered_type == "save-domain-title" and domain_uuid == triggered_domain_uuid:
            if new_domain_name != domain_name and new_domain_name != "":
                workspace.rename_parameter_domain(arch_path, arch_name, domain_name, new_domain_name)

                domain_name = new_domain_name
                save_classes.append(disabled_class)
                metadata["domain_name"] = new_domain_name
                new_metadata.append(metadata)
                new_link = generate_config_link(arch_name, new_domain_name)
                new_hrefs.append(new_link)
            else:
                new_metadata.append(dash.no_update)
                new_hrefs.append(dash.no_update)
                save_classes.append(dash.no_update)

        # No save button clicked, just check for changes
        else:
            new_metadata.append(dash.no_update)
            new_hrefs.append(dash.no_update)
            if new_domain_name != domain_name:
                if new_domain_name == "" or " " in new_domain_name or workspace.parameter_domain_exists(arch_path, arch_name, new_domain_name):
                    save_classes.append(error_class)
                else:
                    save_classes.append(enabled_class)
            else:
                save_classes.append(disabled_class)
    return save_classes, new_metadata, new_hrefs


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id="url"),
        html.Div(id={"page": page_path, "type": "architecture-title-div"}, style={"marginTop": "20px"}),
        html.Div(id="param-domains-section", style={"marginBottom": "10px"}),
    ],
    className="page-content",
    style={
        "padding": "0 16%",
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

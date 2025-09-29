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
import urllib.parse
import odatix.gui.ui_components as ui
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings
import odatix.components.replace_params as replace_params
import odatix.components.config_handler as config_handler

verbose = False

dash.register_page(
    __name__,
    path='/config_editor',
    title='Odatix - Configuration Editor',
    name='Configuration Editor',
    order=4,
)

def get_arch_name_from_url(search):
    if not search:
        return None
    params = urllib.parse.parse_qs(search.lstrip("?"))
    return params.get("arch", [None])[0]

def split_by_domain(flat_list, lengths):
    result = []
    idx = 0
    for l in lengths:
        result.append(flat_list[idx:idx+l])
        idx += l
    return result

def get_index_from_trigger(trig_domain, trig_filename, metadata):
    index = next(
        (i for i, data in enumerate(metadata)
        if data.get("domain") == trig_domain and data.get("filename") == trig_filename),
        -1
    )
    return index

def config_card(domain, filename, content, initial_content, config_layout="normal"):
    display_name = filename[:-4] if filename.endswith(".txt") else filename

    save_class =  "color-button disabled"
    status_text = ""
    status_class = "status"
    return html.Div([
        html.Div([
            dcc.Input(
                value=f"{display_name}",
                type="text",
                id={"type": "config-title", "domain": domain, "filename": filename},
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
            id={"type": "config-content", "domain": domain, "filename": filename},
            value=content,
            className="auto-resize-textarea" if config_layout != "compact" else "",
            style={
                "width": "calc(100% - 20px)",
                "marginLeft": "5px",
                "marginRight": "5px",
                "resize": "none" if config_layout != "compact" else "vertical",
                "minHeight": "none" if config_layout != "compact" else "50px",
                "height": "none" if config_layout != "compact" else "50px",
                "fieldSizing": "border-box",
                "fontFamily": "monospace",
                "fontSize": "0.9em",
                "fontWeight": "normal",
            },
        ),
        dcc.Store(id={"type": "config-metadata", "domain": domain, "filename": filename}, data={"domain": domain, "filename": filename}),
        html.Div([
            html.Div([
                html.Button("Save", id={"type": "save-config", "domain": domain, "filename": filename}, n_clicks=0, className=save_class, style={"marginRight": "8px", "marginLeft": "5px"}),
                html.Div(status_text, id={"type": "save-status", "domain": domain, "filename": filename}, className=status_class, style={"marginLeft": "0px", "textwrap": "wrap", "width": "80px", "font-size": "13px", "font-weight": "515"}),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": "duplicate-config", "domain": domain, "filename": filename}),
                ui.delete_button(id={"type": "delete-config", "domain": domain, "filename": filename}),
            ]),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
        dcc.Store(id={"type": "initial-title", "domain": domain, "filename": filename}, data=display_name),
        dcc.Store(id={"type": "initial-content", "domain": domain, "filename": filename}, data=initial_content),
    ], 
    className="card configs", 
    id={"type": "config-card", "domain": domain, "filename": filename},
    style={
        "padding": "10px", 
        "margin": "5px", 
        "display": "inline-block", 
        "verticalAlign": "top"
    })

def add_card(text: str = "Add new config", domain: str = hard_settings.main_parameter_domain):
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
                style={"textAlign": "center"}
            ),
            id={"type": "new-config", "domain": domain},
            n_clicks=0,
            style={"text-decoration": "none", "color": "black"},
        ),
        className=f"card configs add hover",
        id={"type": "add-config-card", "domain": domain},
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

def architecture_title(arch_name:str=""):
    title_content = html.Div([
        html.H3(arch_name, id=f"main_title", style={"marginBottom": "0px"}),
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
        )
    ],
    style={
        "display": "flex",
        "alignItems": "center",
        "padding": "0px",
        "justifyContent": "space-between",
    })
    return html.Div(
        html.Div(
            [title_content],
            className="tile title",
        ),
        className="card-matrix config",
        style={"marginLeft": "-13px", "marginBottom": "10px"},
    )

def parameter_domain_title(domain:str=hard_settings.main_parameter_domain, arch_name:str=""):
    if domain == hard_settings.main_parameter_domain:
        text = ""
        if arch_name:
            text = text + f"{arch_name} - "
        text = text + "Main parameter domain"
        title_content = html.H3(text, id=f"domain_title_{domain}", style={"marginBottom": "0px"})
    else:
        title_content = html.Div([
            html.Div([
                html.H3("Parameter domain:", style={"display": "inline-block", "marginBottom": "0px", "marginRight": "10px"}),
                dcc.Input(
                    value=domain,
                    type="text",
                    id={"type": "domain-title-input", "domain": domain},
                    className="title-input",
                    style={
                        "marginBottom": "0",
                        "marginTop": "0",
                        "verticalAlign": "middle",
                        "max-width": "250px",
                        "position": "relative",
                        "top": "-4px",
                    }
                ),
            ],
            style={
                "justifyContent": "flex-start"
            }),
            html.Div([
                ui.duplicate_button(id={"action": "duplicate-domain", "domain": domain}),
                ui.delete_button(id={"action": "delete-domain", "domain": domain}),
            ],
            style={
                "display": "inline-flex",
                "marginLeft": "16px",
                "verticalAlign": "middle",
                "marginRight": "0",
                "justifyContent": "flex-end",
                "width": "100px",
            }),
        ],
        style={
            "display": "flex",
            "alignItems": "center",
            "padding": "0px",
            "justifyContent": "space-between",
        }) 
    return html.Div(
        [title_content],
        id={"type": "param-domain-title", "domain": domain}, 
        className="tile title",
        style={"marginTop": "50px"} if domain != hard_settings.main_parameter_domain else {}
    )

def add_parameter_domain_button(text:str="Main parameter domain"):
    return html.Div(
        [
            html.H3(text, style={"marginBottom": "0px"})
        ], 
        id={"type": "button", "action": "add-domain"}, 
        n_clicks=0,
        className="tile title hover",
        style={
            "marginTop": "50px",
            "backgroundColor": "rgba(255, 255, 255, 0.31)",
            "textAlign": "center",
            "border": "1px dashed #bbb",
        },
    )

def config_parameters_form(domain, settings):
    defval = lambda k, v=None: settings.get(k, v)
    return html.Div([
        html.H3(f"Configuration Parameters"),
        html.Div([
            html.Label("Param Target File"),
            dcc.Input(id={"type": "param_target_file", "domain": domain}, value=defval("param_target_file", ""), type="text", placeholder="Top level file used by default", style={"width": "100%"}),
        ], style={"marginBottom": "12px"}),
        html.Div([
            html.Label("Start Delimiter"),
            dcc.Input(id={"type": "start_delimiter", "domain": domain}, value=defval("start_delimiter", ""), type="text", style={"width": "100%"}),
        ], style={"marginBottom": "12px"}),
        html.Div([
            html.Label("Stop Delimiter"),
            dcc.Input(id={"type": "stop_delimiter", "domain": domain}, value=defval("stop_delimiter", ""), type="text", style={"width": "100%"}),
        ], style={"marginBottom": "12px"}),
        html.Button("Save", id={"type": "save-params-btn", "domain": domain}, n_clicks=0, className="save-button", style={"marginTop": "8px"}),
        html.Div(id={"type": "save-params-status", "domain": domain}, className="status", style={"marginLeft": "16px"}),
    ])

def preview_pane(domain:str, settings: dict, domain_settings: dict, replacement_text: str):
    param_target_file = domain_settings.get("param_target_file", "")
    generate_rtl = settings.get("generate_rtl", False)
    if generate_rtl:
        base_path = settings.get("design_path", "")
        if param_target_file == "":
            param_target_file = settings.get("top_level_file", "")
    else:
        base_path = os.path.dirname(settings.get("rtl_path", ""))
        if param_target_file == "":
            param_target_file = os.path.join("rtl", settings.get("top_level_file", ""))
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
                    line_parts.append(html.Span(start_delimiter, className="text-highlight yellow"))
                    line_parts.append(html.Span(line[s_idx+len(start_delimiter):e_idx], className="text-highlight green"))
                    line_parts.append(html.Span(stop_delimiter, className="text-highlight yellow"))
                    if e_idx + len(stop_delimiter) < len(line):
                        line_parts.append(line[e_idx+len(stop_delimiter):])
                # Start delimiter line
                elif line_idx == start_line - 1:
                    if start_charater != -1:
                        if start_charater > 0:
                            line_parts.append(line[:start_charater])
                        line_parts.append(html.Span(start_delimiter, className="text-highlight yellow"))
                        line_parts.append(html.Span(line[start_charater+len(start_delimiter):], className="text-highlight green"))
                    else:
                        line_parts.append(line)
                # Stop delimiter line
                elif line_idx == stop_line - 1:
                    if stop_charater != -1:
                        if stop_charater > 0:
                            line_parts.append(html.Span(line[:stop_charater], className="text-highlight green"))
                        line_parts.append(html.Span(stop_delimiter, className="text-highlight yellow"))
                        if stop_charater + len(stop_delimiter) < len(line):
                            line_parts.append(line[stop_charater+len(stop_delimiter):])
                    else:
                        line_parts.append(line)
                # Replaced content lines
                elif start_line-1 < line_idx < stop_line-1:
                    line_parts.append(html.Span(line, className="text-highlight green"))
                else:
                    line_parts.append(line)
                preview_components.extend(line_parts)
                preview_components.append(html.Br())
            # preview_components.append(html.Span("[...]", style={"color": "#888"}))

        preview_div = html.Pre(
            children=preview_components,
            id={"type": "preview-pre", "domain": domain},
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
        preview_div = html.Div(text, className="error")
    return html.Div(
        children=[
            html.H3("Preview Pane"),
            preview_div,
        ], 
    )

def domain_section(domain: str, arch_name: str = ""):
    return html.Div([
        html.Div(
            children=[
                parameter_domain_title(domain, arch_name)
            ], 
            className="card-matrix config",
            style={"marginLeft": "-13px"},
        ),
        html.Div(
            children=[
                html.Div(id={"type": "config-parameters", "domain": domain}, className="tile config"),
                html.Div(id={"type": "preview-pane", "domain": domain}, className="tile config"),
            ], 
            className="card-matrix config",
            style={"marginLeft": "-13px"},
        ),
        html.Div([
            html.Div(
                id={"type": "config-cards-row", "domain": domain},
                className=f"card-matrix configs", 
            ),
        ]),
        dcc.Store({"type": "config-files-store", "domain": domain}),
        dcc.Store({"type": "config-params-store", "domain": domain}),
        dcc.Store({"type": "initial-configs-store", "domain": domain}),
    ])

layout = html.Div([
    dcc.Location(id="url"),
    architecture_title(),
    domain_section(hard_settings.main_parameter_domain),
    html.Div(id="param-domains-section"),
], style={
    "background-color": "#f6f8fa",
    "padding": "20px 16%",
    "minHeight": "100vh"
})


@dash.callback(
    # Output(f"domain_title_{hard_settings.main_parameter_domain}", "children"),
    Output("main_title", "children"),
    Input("param-domains-section", "children"),
    State("url", "search"),
    preview_initial_call=True
)
def update_main_domain_title(_, search):
    arch_name = get_arch_name_from_url(search)
    if not arch_name:
        return "No architecture selected."
    return arch_name

@dash.callback(
    Output("param-domains-section", "children"),
    Input("url", "search"),
    Input({"action": "add-domain", "type": dash.ALL}, "n_clicks"),
    Input({"action": "duplicate-domain", "domain": dash.ALL}, "n_clicks"),
    Input({"action": "delete-domain", "domain": dash.ALL}, "n_clicks"),
    State("odatix-settings", "data"),
    State("param-domains-section", "children"),
    prevent_initial_call=True
)
def update_param_domains(
    search, add_domain_click, duplicate_domain_click, delete_domain_click,
    odatix_settings, current_domains
):
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_arch_name_from_url(search)
    if not arch_name:
        return html.Div("No architecture selected.", className="error")

    triggered = ctx.triggered_id
    domains = config_handler.get_param_domains(arch_path, arch_name)

    if isinstance(triggered, dict):
        trigger_action = triggered.get("action", "")
        # Add a new domain
        if trigger_action == "add-domain":
            base_name = "new_domain"
            suffix = 1
            new_domain = f"{base_name}{suffix}"
            while new_domain in domains:
                suffix += 1
                new_domain = f"{base_name}{suffix}"
            config_handler.create_parameter_domain(arch_path, arch_name, new_domain)
            domains = config_handler.get_param_domains(arch_path, arch_name)

        # Duplicate domain
        elif trigger_action == "duplicate-domain":
            domain_to_duplicate = triggered.get("domain", "")
            if domain_to_duplicate and domain_to_duplicate != hard_settings.main_parameter_domain:
                base_name = f"{domain_to_duplicate}_copy"
                suffix = 1
                new_domain = f"{base_name}{suffix}"
                while new_domain in domains:
                    suffix += 1
                    new_domain = f"{base_name}{suffix}"
                config_handler.duplicate_parameter_domain(
                    arch_path, arch_name, arch_name, domain_to_duplicate, new_domain
                )
                domains = config_handler.get_param_domains(arch_path, arch_name)

        # Delete domain
        elif trigger_action == "delete-domain":
            domain_to_delete = triggered.get("domain", "")
            if domain_to_delete and domain_to_delete != hard_settings.main_parameter_domain:
                config_handler.delete_parameter_domain(arch_path, arch_name, domain_to_delete)
                domains = config_handler.get_param_domains(arch_path, arch_name)

    # Generate domain sections
    domain_blocks = []
    for domain in domains:
        settings = config_handler.load_settings(arch_path, arch_name, domain)
        settings["arch_name"] = arch_name
        domain_blocks.append(domain_section(domain, arch_name))
    domain_blocks.append(
        html.Div(
            children=[
                add_parameter_domain_button("Add new parameter domain")
            ],
            className="card-matrix config",
            style={"marginLeft": "-13px"},
        ),
    )
    return domain_blocks

@dash.callback(
    Output({"type": "config-cards-row", "domain": dash.ALL}, "children"),
    Output({"type": "config-files-store", "domain": dash.ALL}, "data"),
    Output({"type": "initial-configs-store", "domain": dash.ALL}, "data"),
    State("url", "search"),
    Input("param-domains-section", "children"),
    Input("config-layout-dropdown", "value"),
    Input({"type": "new-config", "domain": dash.ALL}, "n_clicks"),
    Input({"type": "save-config", "domain": dash.ALL, "filename": dash.ALL}, "n_clicks"),
    Input({"type": "delete-config", "domain": dash.ALL, "filename": dash.ALL}, "n_clicks"),
    Input({"type": "duplicate-config", "domain": dash.ALL, "filename": dash.ALL}, "n_clicks"),
    State({"type": "config-title", "domain": dash.ALL, "filename": dash.ALL}, "value"),
    State({"type": "config-content", "domain": dash.ALL, "filename": dash.ALL}, "value"),
    State({"type": "config-metadata", "domain": dash.ALL, "filename": dash.ALL}, "data"),
    State({"type": "config-files-store", "domain": dash.ALL}, "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_config_cards(
    search, param_domains_section,
    config_layout, add_click, save_clicks, delete_clicks, duplicate_clicks,
    title_values, contents, metadata, configs_list, odatix_settings
):
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_arch_name_from_url(search)
    if not arch_name:
        return [html.Div("No architecture selected.", className="error")], {}, ""

    domains = [hard_settings.main_parameter_domain] + config_handler.get_param_domains(arch_path, arch_name)

    triggered = ctx.triggered_id
    if isinstance(triggered, dict):
        trig_type = triggered.get("type", None)
        trig_domain = triggered.get("domain", hard_settings.main_parameter_domain)
        trig_domain_idx = domains.index(trig_domain) if trig_domain in domains else -1

        if trig_type == "new-config" and add_click:
            for idx in range(1, 1001):
                new_filename = f"new_config{idx}.txt"
                if new_filename not in configs_list[trig_domain_idx]:
                    config_handler.save_config_file(arch_path, arch_name, trig_domain, new_filename, "")
                    configs_list[trig_domain_idx][new_filename] = ""
                    break
            else:
                error_msg = "Too many config creation fails (1000 max)."

        elif trig_type in ["save-config", "delete-config", "duplicate-config"]:         

            trig_filename = triggered.get("filename", "")
            

            # Save config (and handle rename)
            if trig_type == "save-config":
                config_index = get_index_from_trigger(trig_domain, trig_filename, metadata)
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
                        path = config_handler.get_arch_domain_path(arch_path, arch_name, trig_domain)
                        old_path = os.path.join(path, config_old_title)
                        new_path = os.path.join(path, config_new_title)
                        if verbose:
                            print(f"Renaming {old_path} to {new_path}")
                        os.rename(old_path, new_path)
                        configs_list[trig_domain_idx][config_new_title] = config_content
                        configs_list[trig_domain_idx].pop(config_old_title)
                        config_old_title = config_new_title
                if verbose:
                    print(f"Saving config '{config_old_title}' in domain '{trig_domain}'")
                config_handler.save_config_file(arch_path, arch_name, trig_domain, config_new_title, config_content)
                configs_list[trig_domain_idx][config_old_title] = config_content

            # Delete config
            if trig_type == "delete-config":
                config_handler.delete_config_file(arch_path, arch_name, trig_domain, trig_filename)
                configs_list[trig_domain_idx].pop(trig_filename)

            # Duplicate config
            if trig_type == "duplicate-config":
                base = trig_filename[:-4] if trig_filename.endswith(".txt") else trig_filename
                suffix = 1
                new_filename = f"{base}_copy{suffix}.txt"
                while new_filename in configs_list[trig_domain_idx]:
                    suffix += 1
                    new_filename = f"{base}_copy{suffix}.txt"
                config_handler.save_config_file(arch_path, arch_name, trig_domain, new_filename, configs_list[trig_domain_idx][trig_filename])
                configs_list[trig_domain_idx][new_filename] = configs_list[trig_domain_idx][trig_filename]

    all_cards = []
    all_configs = []
    all_initial_configs = []

    for idx, domain in enumerate(domains):
        if True:
            files = config_handler.get_config_files(arch_path, arch_name, domain)
            configs = {f: config_handler.load_config_file(arch_path, arch_name, domain, f) for f in files}
        initial_configs = configs.copy()

        cards = [config_card(domain, f, configs[f], initial_configs.get(f, ""), config_layout) for f in configs]
        cards.append(add_card(domain=domain))

        all_cards.append(cards)
        all_configs.append(configs)
        all_initial_configs.append(initial_configs)
    return all_cards, all_configs, all_initial_configs

@dash.callback(
    Output({"type": "preview-pane", "domain": dash.ALL}, "children"),
    State("url", "search"),
    Input({"type": "config-cards-row", "domain": dash.ALL}, "children"),
    Input({"type": "param_target_file", "domain": dash.ALL}, "value"),
    Input({"type": "start_delimiter", "domain": dash.ALL}, "value"),
    Input({"type": "stop_delimiter", "domain": dash.ALL}, "value"),
    Input({"type": "config-params-store", "domain": dash.ALL}, "data"),
    Input({"type": "config-content", "domain": dash.ALL, "filename": dash.ALL}, "value"),
    State({"type": "config-files-store", "domain": dash.ALL}, "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_preview_all(search, config_cards_rows, target_files, start_delims, stop_delims, settings_list, config_contents_list, configs_list, odatix_settings):
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_arch_name_from_url(search)
    domains = [hard_settings.main_parameter_domain] + config_handler.get_param_domains(arch_path, arch_name)

    triggered = ctx.triggered_id
    if isinstance(triggered, dict):
        filenames_per_domain = [list(configs.keys()) for configs in configs_list]
        lengths = [len(filenames) for filenames in filenames_per_domain]

        contents_by_domain = split_by_domain(config_contents_list, lengths)

        results = []
        for i, domain in enumerate(domains):
            config_contents_list = contents_by_domain[i] if i < len(contents_by_domain) else []
            settings = settings_list[0] if 0 < len(settings_list) and settings_list[0] is not None else {}
            domain_settings = settings_list[i] if i < len(settings_list) and settings_list[i] is not None else {}
            domain_settings["param_target_file"] = target_files[i] if i < len(target_files) else ""
            domain_settings["start_delimiter"] = start_delims[i] if i < len(start_delims) else ""
            domain_settings["stop_delimiter"] = stop_delims[i] if i < len(stop_delims) else ""
            replacement_text = config_contents_list[0] if config_contents_list else ""
            results.append(preview_pane(domain, settings, domain_settings, replacement_text))
        return results
    return dash.no_update

@dash.callback(
    Output({"type": "config-parameters", "domain": dash.ALL}, "children"),
    Output({"type": "config-params-store", "domain": dash.ALL}, "data"),
    State("url", "search"),
    Input({"type": "config-cards-row", "domain": dash.ALL}, "children"),
    State("odatix-settings", "data"),

    prevent_initial_call=True
)
def update_config_parameters_all(search, config_cards_rows, odatix_settings):
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_arch_name_from_url(search)
    if not arch_name:
        return [html.Div("No architecture selected.", className="error")], [{}]
    domains = [hard_settings.main_parameter_domain] + config_handler.get_param_domains(arch_path, arch_name)
    children = []
    stores = []
    for domain in domains:
        settings = config_handler.load_settings(arch_path, arch_name, domain)
        children.append(config_parameters_form(domain, settings))
        stores.append(settings)
    return children, stores

@dash.callback(
    Output({"type": "save-config", "domain": dash.ALL, "filename": dash.ALL}, "className"),
    Output({"type": "save-status", "domain": dash.ALL, "filename": dash.ALL}, "className"),
    Output({"type": "save-status", "domain": dash.ALL, "filename": dash.ALL}, "children"),
    Input("param-domains-section", "children"),
    Input({"type": "config-title", "domain": dash.ALL, "filename": dash.ALL}, "value"),
    Input({"type": "config-content", "domain": dash.ALL, "filename": dash.ALL}, "value"),
    Input({"type": "initial-title", "domain": dash.ALL, "filename": dash.ALL}, "data"),
    Input({"type": "initial-content", "domain": dash.ALL, "filename": dash.ALL}, "data"),
    State({"type": "save-config", "domain": dash.ALL, "filename": dash.ALL}, "className"),
)
def update_save_status(param_domains_section, title_values, content_values, initial_titles, initial_contents, save_config):
    save_classes = []
    status_classes = []
    status_texts = []
    for title, content, initial_title, initial_content in zip(title_values, content_values, initial_titles, initial_contents):
        if title != initial_title or content != initial_content:
            save_classes.append("color-button orange")
            status_classes.append("status warning")
            status_texts.append("Unsaved changes!")
        else:
            save_classes.append("color-button disabled")
            status_classes.append("status")
            status_texts.append("")
    return save_classes, status_classes, status_texts

@dash.callback(
    Output({"type": "config-card", "domain": dash.ALL, "filename": dash.ALL}, "className"),
    Output({"type": "add-config-card", "domain": dash.ALL}, "className"),
    Output({"type": "config-cards-row", "domain": dash.ALL}, "className"),
    Input("config-layout-dropdown", "value"),
    State({"type": "config-card", "domain": dash.ALL, "filename": dash.ALL}, "className"),
    State({"type": "add-config-card", "domain": dash.ALL}, "className"),
    State({"type": "config-cards-row", "domain": dash.ALL}, "className"),
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

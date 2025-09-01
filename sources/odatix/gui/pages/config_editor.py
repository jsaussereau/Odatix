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
import yaml
import odatix.gui.ui_components as ui
import odatix.components.replace_params as replace_params

dash.register_page(
    __name__,
    path='/config_editor',
    title='Odatix - Configuration Editor',
    name='Configuration Editor',
    order=4,
)

ARCH_ROOT = "odatix_userconfig/architectures"

def get_arch_name_from_url(search):
    if not search:
        return None
    params = urllib.parse.parse_qs(search.lstrip("?"))
    return params.get("arch", [None])[0]

def get_config_files(arch_name):
    folder = os.path.join(ARCH_ROOT, arch_name)
    if not os.path.isdir(folder):
        return []
    return sorted([
        f for f in os.listdir(folder)
        if f.endswith(".txt") and os.path.isfile(os.path.join(folder, f))
    ])

def load_config_file(arch_name, filename):
    path = os.path.join(ARCH_ROOT, arch_name, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()

def save_config_file(arch_name, filename, content):
    path = os.path.join(ARCH_ROOT, arch_name, filename)
    with open(path, "w") as f:
        f.write(content)

def delete_config_file(arch_name, filename):
    path = os.path.join(ARCH_ROOT, arch_name, filename)
    if os.path.exists(path):
        os.remove(path)

def load_settings(arch_name):
    path = os.path.join(ARCH_ROOT, arch_name, "_settings.yml")
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def save_settings(arch_name, settings):
    path = os.path.join(ARCH_ROOT, arch_name, "_settings.yml")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(settings, f, sort_keys=False)

def config_card(filename, content, initial_content):
    display_name = filename[:-4] if filename.endswith(".txt") else filename

    save_class =  "color-button disabled"
    status_text = ""
    status_class = "status"
    return html.Div([
        html.Div([
            dcc.Input(
                value=f"{display_name}",
                type="text",
                id={"type": "config-title", "filename": filename},
                className="title-input",
                style={
                    "width": "243px",
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
            id={"type": "config-content", "filename": filename},
            value=content,
            style={
                "width": "243px",
                "height": "50px",
                "resize": "vertical",
                "minHeight": "50px",
                "fontFamily": "monospace",
                "fontSize": "0.9em",
                "fontWeight": "normal",
            },
        ),
        html.Div([
            html.Div([
                html.Button("Save", id={"type": "save-config", "filename": filename}, n_clicks=0, className=save_class, style={"marginRight": "8px"}),
                html.Div(status_text, id={"type": "save-status", "filename": filename}, className=status_class, style={"marginLeft": "0px", "textwrap": "wrap", "width": "80px", "font-size": "13px", "font-weight": "515"}),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": "duplicate-config", "filename": filename}),
                ui.delete_button(id={"type": "delete-config", "filename": filename}),
            ]),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
        dcc.Store(id={"type": "initial-title", "filename": filename}, data=display_name),
        dcc.Store(id={"type": "initial-content", "filename": filename}, data=initial_content),
    ], className="card", style={
        "width": "256px", 
        "padding": "10px", 
        "margin": "5px", 
        "display": "inline-block", 
        "verticalAlign": "top"
    })

def add_card(text: str = "Add new config"):
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
            id={"type": "new", "filename": "new"},
            n_clicks=0,
            style={"text-decoration": "none", "color": "black"},
        ),
        className="card hover",
        style={
            "backgroundColor": "rgba(255, 255, 255, 0.31)",
            "border": "1px dashed #bbb",
            "width": "277px",
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "height": "170px",
            "boxSizing": "border-box"
        },
    )

def config_parameters_form(settings):
    defval = lambda k, v=None: settings.get(k, v)
    use_parameters = True if str(defval("use_parameters", "No")).lower() in ["yes", "true"] else False
    return html.Div([
        html.H3("Configuration Parameters"),
        html.Div([
            html.Label("Param Target File"),
            dcc.Input(id="param_target_file", value=defval("param_target_file", ""), type="text", placeholder="Top level file used by default", style={"width": "100%"}),
        ], style={"marginBottom": "12px"}),
        html.Div([
            html.Label("Start Delimiter"),
            dcc.Input(id="start_delimiter", value=defval("start_delimiter", ""), type="text", style={"width": "100%"}),
        ], style={"marginBottom": "12px"}),
        html.Div([
            html.Label("Stop Delimiter"),
            dcc.Input(id="stop_delimiter", value=defval("stop_delimiter", ""), type="text", style={"width": "100%"}),
        ], style={"marginBottom": "12px"}),
        html.Button("Save", id="save-params-btn", n_clicks=0, className="save-button", style={"marginTop": "8px"}),
        html.Div(id="save-params-status", className="status", style={"marginLeft": "16px"}),
    ])


def preview_pane(settings: dict, replacement_text: str):
    param_target_file = settings.get("param_target_file", "")
    if param_target_file == "":
        param_target_file = settings.get("top_level_file", "")
    generate_rtl = settings.get("generate_rtl", False)
    if generate_rtl:
        param_target_file = os.path.join(settings.get("design_path", ""), param_target_file)
    else:
        param_target_file = os.path.join(settings.get("rtl_path", ""), param_target_file)
    if os.path.exists(param_target_file):
        base_text = replace_params.read_file(param_target_file)
        start_delimiter = settings.get("start_delimiter", "")
        stop_delimiter = settings.get("stop_delimiter", "")
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
            id="preview-pre",
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
        preview_div = html.Div("No preview available.", className="error")
    return html.Div(
        children=[
            html.H3("Preview Pane"),
            preview_div,
        ], 
    )

layout = html.Div([
    dcc.Location(id="url"),
    html.Div(
        children=[
            html.Div(id="config-parameters", className="tile config"),
            html.Div(id="preview-pane", className="tile config"),
        ], 
        className="card-matrix config",
        style={"marginLeft": "-13px"},
    ),
    html.Div([
        html.Div(
            id="config-cards-row",
            className="card-matrix configs", 
        ),
    ]),
    dcc.Store(id="config-files-store"),
    dcc.Store(id="config-params-store"),
    dcc.Store(id="initial-configs-store"),
], style={
    "background-color": "#f6f8fa",
    "padding": "20px 16%",
    "minHeight": "100vh"
})


@dash.callback(
    Output("preview-pane", "children"),
    Input("url", "search"),
    Input("param_target_file", "value"),
    Input("start_delimiter", "value"),
    Input("stop_delimiter", "value"),
    Input("config-params-store", "data"),
    Input({"type": "config-content", "filename": dash.ALL}, "value"),
)
def update_preview(search, target_file, start_delim, stop_delim, settings, config_contents):
    settings["param_target_file"] = target_file
    settings["start_delimiter"] = start_delim
    settings["stop_delimiter"] = stop_delim
    replacement_text = config_contents[0] if config_contents else ""
    return preview_pane(settings, replacement_text)

@dash.callback(
    Output("config-parameters", "children"),
    Output("config-params-store", "data"),
    Input("url", "search"),
)
def update_config_parameters(search):
    arch_name = get_arch_name_from_url(search)
    if not arch_name:
        return html.Div("No architecture selected.", className="error"), {}
    settings = load_settings(arch_name) if arch_name else {}
    return config_parameters_form(settings), settings

@dash.callback(
    Output("config-cards-row", "children"),
    Output("config-files-store", "data"),
    Output("initial-configs-store", "data"),
    Input("url", "search"),
    Input({"type": "new", "filename": dash.ALL}, "n_clicks"),
    Input({"type": "save-config", "filename": dash.ALL}, "n_clicks"),
    Input({"type": "delete-config", "filename": dash.ALL}, "n_clicks"),
    Input({"type": "duplicate-config", "filename": dash.ALL}, "n_clicks"),
    State({"type": "config-title", "filename": dash.ALL}, "value"),
    State({"type": "config-content", "filename": dash.ALL}, "value"),
    State("config-files-store", "data"),
)
def update_config_cards(
    search, add_click, save_clicks, delete_clicks, duplicate_clicks,
    title_values, contents, configs
):
    arch_name = get_arch_name_from_url(search)
    error_msg = ""
    if not arch_name:
        return [html.Div("No architecture selected.", className="error")], {}, ""

    # Load files if not in store
    if not configs:
        files = get_config_files(arch_name)
        configs = {f: load_config_file(arch_name, f) for f in files}
    initial_configs = configs.copy()

    triggered = ctx.triggered_id

    # Add new config
    if triggered == {'filename': 'new', 'type': 'new'} and add_click:
        for idx in range(1, 1001):
            new_filename = f"new_config{idx}.txt"
            if new_filename not in configs:
                save_config_file(arch_name, new_filename, "")
                configs[new_filename] = ""
                break
        else:
            error_msg = "Too many config creation fails (1000 max)."

    # Save config (and handle rename)
    if isinstance(triggered, dict) and triggered.get("type") == "save-config":
        filenames = list(configs.keys())
        for i, filename in enumerate(filenames):
            new_title = title_values[i]
            if not new_title.endswith(".txt"):
                new_title = new_title + ".txt"
            if new_title != filename:
                if new_title in configs:
                    error_msg = f"File '{new_title}' already exists."
                else:
                    old_path = os.path.join(ARCH_ROOT, arch_name, filename)
                    new_path = os.path.join(ARCH_ROOT, arch_name, new_title)
                    os.rename(old_path, new_path)
                    configs[new_title] = contents[i]
                    configs.pop(filename)
                    filename = new_title
            save_config_file(arch_name, filename, contents[i])
            configs[filename] = contents[i]

    # Delete config
    if isinstance(triggered, dict) and triggered.get("type") == "delete-config":
        filenames = list(configs.keys())
        for i, filename in enumerate(filenames):
            if delete_clicks[i]:
                delete_config_file(arch_name, filename)
                configs.pop(filename)

    # Duplicate config
    if isinstance(triggered, dict) and triggered.get("type") == "duplicate-config":
        filenames = list(configs.keys())
        for i, filename in enumerate(filenames):
            if duplicate_clicks[i]:
                base = filename[:-4] if filename.endswith(".txt") else filename
                suffix = 1
                new_filename = f"{base}_copy{suffix}.txt"
                while new_filename in configs:
                    suffix += 1
                    new_filename = f"{base}_copy{suffix}.txt"
                save_config_file(arch_name, new_filename, configs[filename])
                configs[new_filename] = configs[filename]

    initial_configs = configs.copy()

    cards = [config_card(f, configs[f], initial_configs.get(f, "")) for f in configs] + [add_card()]
    return cards, configs, initial_configs

@dash.callback(
    Output({"type": "save-config", "filename": dash.ALL}, "className"),
    Output({"type": "save-status", "filename": dash.ALL}, "className"),
    Output({"type": "save-status", "filename": dash.ALL}, "children"),
    Input({"type": "config-title", "filename": dash.ALL}, "value"),
    Input({"type": "config-content", "filename": dash.ALL}, "value"),
    Input({"type": "initial-title", "filename": dash.ALL}, "data"),
    Input({"type": "initial-content", "filename": dash.ALL}, "data"),
    State({"type": "save-config", "filename": dash.ALL}, "className"),
)
def update_save_status(title_values, content_values, initial_titles, initial_contents, save_config):
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

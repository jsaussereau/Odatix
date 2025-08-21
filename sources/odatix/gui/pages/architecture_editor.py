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
from dash import html, dcc, Input, Output, State, callback, ctx
import dash.exceptions
import urllib.parse
import yaml
from dash.exceptions import PreventUpdate
import shutil

dash.register_page(
    __name__,
    path='/arch_editor',
    title='Odatix - Architecture Editor',
    name='Architecture Editor',
    order=3,
)

ARCH_ROOT = "odatix_userconfig/architectures"

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

def get_arch_name_from_url(search):
    if not search:
        return None
    params = urllib.parse.parse_qs(search.lstrip("?"))
    return params.get("arch", [None])[0]

def architecture_form(settings, arch_name=""):
    defval = lambda k, v=None: settings.get(k, v)
    generate_rtl = True if str(defval("generate_rtl", "No")).lower() in ["yes", "true"] else False
    return html.Div(
        children=[
            html.Div([
                html.Div(
                    id="arch-title-container",
                    children=[
                        dcc.Input(
                            value=f"{arch_name}",
                            type="text",
                            id="arch-title",
                            className="title-input",
                            style={"width": "100%"},
                        )
                    ],
                ),
                html.Div([
                    html.Button(
                        "Save",
                        id="save-btn",
                        n_clicks=0,
                        className="save-button",
                        style={"marginTop": "5px", "width": "120px"},
                        disabled=True,
                    ),
                    html.Div(id="save-status", className="status"),
                ], style={"display": "flex", "justifyContent": "start", "alignItems": "center"}),
            ], className="tile", style={"margin-top": "0px"}),
            html.Div([
                html.H3("RTL Generation"),
                html.Div([
                    html.Label("Generate RTL"),
                    dcc.Dropdown(
                        id="generate_rtl",
                        options=[{"label": "Yes", "value": True}, {"label": "No", "value": False}],
                        value=generate_rtl,
                        clearable=False,
                        style={"width": "100%"}
                    ),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    html.Div([
                        html.Label("Design Path"),
                        dcc.Input(id="design_path", value=defval("design_path", ""), type="text", style={"width": "100%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Design Path Whitelist"),
                        dcc.Input(id="design_path_whitelist", value=",".join(defval("design_path_whitelist", [])), type="text", style={"width": "100%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Design Path Blacklist"),
                        dcc.Input(id="design_path_blacklist", value=",".join(defval("design_path_blacklist", [])), type="text", style={"width": "100%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Generate Command"),
                        dcc.Input(id="generate_command", value=defval("generate_command", ""), type="text", style={"width": "100%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Generate Output"),
                        dcc.Input(id="generate_output", value=defval("generate_output", ""), type="text", style={"width": "100%"}),
                    ], style={"marginBottom": "12px"}),
                ], id="generate-settings", className="animated-section" + ("" if generate_rtl else " hide")),
            ], className="tile"),
            html.Div([
                html.H3("Top Level Settings"),
                html.Div([
                    html.Label("Top Level File"),
                    dcc.Input(id="top_level_file", value=defval("top_level_file", ""), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    html.Label("Top Level Module"),
                    dcc.Input(id="top_level_module", value=defval("top_level_module", ""), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    html.Label("Clock Signal"),
                    dcc.Input(id="clock_signal", value=defval("clock_signal", ""), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    html.Label("Reset Signal"),
                    dcc.Input(id="reset_signal", value=defval("reset_signal", ""), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
            ], className="tile"),
            html.Div([
                html.H3("Synthesis Settings"),
                html.H4("Fmax Synthesis (MHz)"),
                html.Div([
                    html.Label("Lower Bound"),
                    dcc.Input(id="fmax_synthesis_lower", value=defval("fmax_synthesis", {}).get("lower_bound", ""), type="number", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    html.Label("Upper Bound"),
                    dcc.Input(id="fmax_synthesis_upper", value=defval("fmax_synthesis", {}).get("upper_bound", ""), type="number", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
                html.H4("Custom Freq Synthesis (MHz)"),
                html.Div([
                    html.Label("List"),
                    dcc.Input(id="custom_freq_synthesis_list", value=",".join(map(str, defval("custom_freq_synthesis", {}).get("list", []))), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
            ], className="tile"),
        ], className="tiles-container",
    )
    

layout = html.Div(
    [
        dcc.Location(id="url"),
        html.Div(id="arch-form-container"),
        dcc.Store(id="save-state", data=""),
        dcc.Store(id="initial-form-state", data={}),
        dcc.Store(id="previous-form-state", data={}), 
    ],
    style={
        "background-color": "#f6f8fa",
        "padding": "20px",
        "minHeight": "100vh"
    },
)

@callback(
    Output("arch-form-container", "children"),
    Output("initial-form-state", "data"),
    Input("url", "search"),
)
def update_form(search):
    arch_name = get_arch_name_from_url(search)
    if not arch_name:
        arch_name = "New Architecture"
    settings = load_settings(arch_name) if arch_name else {}
    return architecture_form(settings, arch_name), settings

@callback(
    Output("save-btn", "className"),
    Output("save-status", "children"),
    Output("save-status", "className"),
    Output("save-state", "data"),
    Output("url", "search"),
    Output("save-btn", "disabled"),
    Output("previous-form-state", "data"),
    [
        Input("save-btn", "n_clicks"),
        Input("arch-title", "value"),
        Input("design_path", "value"),
        Input("design_path_whitelist", "value"),
        Input("design_path_blacklist", "value"),
        Input("generate_rtl", "value"),
        Input("generate_command", "value"),
        Input("generate_output", "value"),
        Input("top_level_file", "value"),
        Input("top_level_module", "value"),
        Input("clock_signal", "value"),
        Input("reset_signal", "value"),
        Input("fmax_synthesis_lower", "value"),
        Input("fmax_synthesis_upper", "value"),
        Input("custom_freq_synthesis_list", "value"),
    ],
    State("url", "search"),
    State("save-state", "data"),
    State("initial-form-state", "data"),
    State("previous-form-state", "data"),
    prevent_initial_call=False
)
def save_and_status(
    n_clicks, arch_title, design_path, whitelist, blacklist, generate_rtl, generate_command, generate_output,
    top_level_file, top_level_module, clock_signal, reset_signal, 
    fmax_lower, fmax_upper, custom_freq_list, search, save_state, initial_state, previous_state
):
    triggered = ctx.triggered_id if hasattr(ctx, "triggered_id") else dash.callback_context.triggered[0]["prop_id"].split(".")[0]

    current_settings = {
        "design_path": design_path,
        "design_path_whitelist": [x.strip() for x in whitelist.split(",") if x.strip()],
        "design_path_blacklist": [x.strip() for x in blacklist.split(",") if x.strip()],
        "generate_rtl": "Yes" if generate_rtl else "No",
        "generate_command": generate_command,
        "generate_output": generate_output,
        "top_level_file": top_level_file,
        "top_level_module": top_level_module,
        "clock_signal": clock_signal,
        "reset_signal": reset_signal,
        "use_parameters": initial_state.get("use_parameters", False),
        "param_target_file": initial_state.get("param_target_file", top_level_file),
        "start_delimiter": initial_state.get("start_delimiter", ""),
        "stop_delimiter": initial_state.get("stop_delimiter", ""),
        "fmax_synthesis": {
            "lower_bound": fmax_lower,
            "upper_bound": fmax_upper,
        },
        "custom_freq_synthesis": {
            "list": [int(x.strip()) for x in custom_freq_list.split(",") if x.strip()],
        }
    }

    if previous_state == {}:
        return "save-button", "", "status", "clean", dash.no_update, True, initial_state

    if triggered != "save-btn":
        if current_settings != previous_state:
            return "save-button unsaved", "Unsaved changes!", "status warning", "dirty", dash.no_update, False, previous_state
        else:
            return "save-button", "", "status", "clean", dash.no_update, True, previous_state

    arch_name = get_arch_name_from_url(search)
    new_search = dash.no_update
    if not arch_name:
        return "save-button", "No architecture name in URL.", "status error", "error", new_search, True, previous_state

    if arch_title and arch_title != arch_name:
        old_path = os.path.join(ARCH_ROOT, arch_name)
        new_path = os.path.join(ARCH_ROOT, arch_title)
        if os.path.exists(new_path):
            return "save-button", f"Error: '{arch_title}' already exists.", "status error", "error", new_search, True, previous_state
        try:
            shutil.move(old_path, new_path)
            arch_name = arch_title
            new_search = f"?arch={arch_title}"
        except Exception as e:
            return "save-button", f"Rename failed: {e}", "status error", "error", new_search, True, previous_state

    try:
        save_settings(arch_name, current_settings)
        return "save-button", "Saved!", "status valid", "saved", new_search, True, current_settings
    except Exception as e:
        return "save-button", f"Save failed: {e}", "status error", "error", new_search, True, previous_state

@callback(
    Output("generate-settings", "className"),
    Input("generate_rtl", "value"),
)
def toggle_generate_settings(generate_rtl):
    return "animated-section" if generate_rtl else "animated-section hide"

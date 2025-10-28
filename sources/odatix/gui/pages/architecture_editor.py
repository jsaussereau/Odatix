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
import shutil

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings

page_path = "/arch_editor"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Architecture Editor',
    name='Architecture Editor',
    order=3,
)

######################################
# UI Components
######################################

def architecture_title(arch_name):
    variable_title_tile_buttons = html.Div(
        children=[
            ui.icon_button(
                id=f"button-open-config-editor",
                icon=icon("edit", className="icon blue"),
                text="Edit Configs",
                color="blue",
                link=f"/config_editor?arch={arch_name}",
                multiline=False,
                width="135px",
            ),
            ui.save_button(
                id={"page": page_path, "action": "save-all"},
                disabled=True,
            ),
        ],
        className="inline-flex-buttons",
    )
    back_btn = ui.back_button(link="/architectures")
    
    return html.Div(
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                dcc.Input(
                                    value=f"{arch_name}",
                                    type="text",
                                    id="arch-title",
                                    className="title-input",
                                    style={"width": "100%"},
                                )
                            ],
                            id="arch-title-container",
                        ),
                        html.Div(
                            [variable_title_tile_buttons],
                        ),
                    ],
                    className="title-tile-flex",
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "padding": "0px",
                        "justifyContent": "space-between",
                    }
                ),
                back_btn,
            ],
            className="tile title",
            style={"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "0px", "marginBottom": "10px", "marginLeft": "-13px"},
    )

def architecture_form(settings):
    defval = lambda k, v=None: settings.get(k, v)
    generate_rtl = True if str(defval("generate_rtl", "No")).lower() in ["yes", "true"] else False

    return html.Div(
        children=[
            html.Div([
                html.H3("RTL Generation"),
                html.Div([
                    dcc.Checklist(
                        options=[{"label": "Enable RTL Generation", "value": True}],
                        value=[True] if generate_rtl else [],
                        id="generate_rtl",
                        className="checklist-switch",
                        style={"marginBottom": "12px", "marginTop": "5px"},
                    ),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    html.Div([
                        html.Label("Design Path", className="dropdown-label"),
                        dcc.Input(id="design_path", value=defval("design_path", ""), type="text", style={"width": "95%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Design Path Whitelist", className="dropdown-label"),
                        dcc.Input(id="design_path_whitelist", value=", ".join(defval("design_path_whitelist", [])), type="text", style={"width": "95%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Design Path Blacklist", className="dropdown-label"),
                        dcc.Input(id="design_path_blacklist", value=", ".join(defval("design_path_blacklist", [])), type="text", style={"width": "95%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Generate Command", className="dropdown-label"),
                        dcc.Input(id="generate_command", value=defval("generate_command", ""), type="text", style={"width": "95%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Generate Output", className="dropdown-label"),
                        dcc.Input(id="generate_output", value=defval("generate_output", ""), type="text", style={"width": "95%"}),
                    ], style={"marginBottom": "12px"}),
                ], id="generate-settings", className="animated-section" + ("" if generate_rtl else " hide")),
            ], className="tile config"),
            html.Div([
                html.H3("Top Level Settings"),
                html.Div([
                    html.Label("RTL Path", className="dropdown-label"), 
                    dcc.Input(id="rtl_path", value=defval("rtl_path", ""), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}, id="rtl-path-container", className="animated-section" + ("" if not generate_rtl else " hide")),
                html.Div([
                    html.Label("Top Level File", className="dropdown-label"),
                    dcc.Input(id="top_level_file", value=defval("top_level_file", ""), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    html.Label("Top Level Module", className="dropdown-label"), 
                    dcc.Input(id="top_level_module", value=defval("top_level_module", ""), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    html.Label("Clock Signal", className="dropdown-label"), 
                    dcc.Input(id="clock_signal", value=defval("clock_signal", ""), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    html.Label("Reset Signal", className="dropdown-label"), 
                    dcc.Input(id="reset_signal", value=defval("reset_signal", ""), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
            ], className="tile config"),
            html.Div([
                html.H3("Synthesis Settings"),
                html.H4("Fmax Synthesis (MHz)"),
                html.Div([
                    html.Label("Lower Bound", className="dropdown-label"),
                    dcc.Input(id="fmax_synthesis_lower", value=defval("fmax_synthesis", {}).get("lower_bound", ""), type="number", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    html.Label("Upper Bound", className="dropdown-label"),
                    dcc.Input(id="fmax_synthesis_upper", value=defval("fmax_synthesis", {}).get("upper_bound", ""), type="number", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
                html.H4("Custom Freq Synthesis (MHz)"),
                html.Div([
                    html.Label("List", className="dropdown-label"),
                    dcc.Input(id="custom_freq_synthesis_list", value=", ".join(map(str, defval("custom_freq_synthesis", {}).get("list", []))), type="text", style={"width": "100%"}),
                ], style={"marginBottom": "12px"}),
            ], className="tile config"),
        ], className="tiles-container config", style={"marginTop": "-10px", "marginBottom": "20px"},
    )


######################################
# Callbacks
######################################

@dash.callback(
    Output("arch-form-container", "children"),
    Output("architecture-initial-settings", "data"),
    Input("url", "search"),
    State("url", "pathname"),
    State("odatix-settings", "data"),
)
def init_form(search, page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update

    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_key_from_url(search, "arch")
    if not arch_name:
        return architecture_form({}), {}

    if arch_name:
        full_settings = workspace.load_architecture_settings(arch_path, arch_name, hard_settings.main_parameter_domain)
        settings ={
            "generate_rtl": full_settings.get("generate_rtl", False),
            "design_path": full_settings.get("design_path", ""),
            "design_path_whitelist": full_settings.get("design_path_whitelist", []),
            "design_path_blacklist": full_settings.get("design_path_blacklist", []),
            "generate_command": full_settings.get("generate_command", ""),
            "generate_output": full_settings.get("generate_output", ""),

            "rtl_path": full_settings.get("rtl_path", ""),
            "top_level_file": full_settings.get("top_level_file", ""),
            "top_level_module": full_settings.get("top_level_module", ""),
            "clock_signal": full_settings.get("clock_signal", ""),
            "reset_signal": full_settings.get("reset_signal", ""),

            "fmax_synthesis": full_settings.get("fmax_synthesis", {}),
            "custom_freq_synthesis": full_settings.get("custom_freq_synthesis", {}),
        }
    else:
        settings = {}
    return architecture_form(settings), settings

@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output("url", "search"),
    Output("architecture-saved-settings", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input("arch-title", "value"),
    Input("design_path", "value"),
    Input("design_path_whitelist", "value"),
    Input("design_path_blacklist", "value"),
    Input("generate_rtl", "value"),
    Input("generate_command", "value"),
    Input("generate_output", "value"),
    Input("rtl_path", "value"),
    Input("top_level_file", "value"),
    Input("top_level_module", "value"),
    Input("clock_signal", "value"),
    Input("reset_signal", "value"),
    Input("fmax_synthesis_lower", "value"),
    Input("fmax_synthesis_upper", "value"),
    Input("custom_freq_synthesis_list", "value"),
    State("url", "search"),
    State("architecture-initial-settings", "data"),
    State("architecture-saved-settings", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(
    n_clicks, arch_title, design_path, whitelist, blacklist, generate_rtl, generate_command, generate_output,
    rtl_path, top_level_file, top_level_module, clock_signal, reset_signal, 
    fmax_lower, fmax_upper, custom_freq_list, search, initial_settings, saved_settings,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    arch_name = get_key_from_url(search, "arch")

    if saved_settings is None:
        settings = initial_settings
    else:
        settings = saved_settings

    if fmax_lower is None:
        fmax_lower = ""
    if fmax_upper is None:
        fmax_upper = ""
    if custom_freq_list is None:
        custom_freq_list = ""

    current_settings = {
        "generate_rtl": True if generate_rtl else False,
        "design_path": design_path,
        "design_path_whitelist": [x.strip() for x in whitelist.split(",") if x.strip()],
        "design_path_blacklist": [x.strip() for x in blacklist.split(",") if x.strip()],
        "generate_command": generate_command,
        "generate_output": generate_output,
        "rtl_path": rtl_path,
        "top_level_file": top_level_file,
        "top_level_module": top_level_module,
        "clock_signal": clock_signal,
        "reset_signal": reset_signal,
        "fmax_synthesis": {
            "lower_bound": fmax_lower,
            "upper_bound": fmax_upper,
        } if fmax_lower != "" or fmax_upper != "" else {},
        "custom_freq_synthesis": {
            "list": [int(x.strip()) for x in custom_freq_list.split(",") if x.strip()],
        } if custom_freq_list != "" else {},
    }

    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_key_from_url(search, "arch")

    if not arch_title:
        return "color-button disabled icon-button error-status", dash.no_update, saved_settings

    if triggered_id == {"page": page_path, "action": "save-all"}:
        # Rename architecture if needed
        new_search = dash.no_update
        if arch_title != arch_name:
            old_name = arch_name
            new_name = arch_title
            try:
                workspace.rename_architecture(arch_path, old_name, new_name)
                arch_name = new_name
                new_search = f"?arch={new_name}"
            except Exception as e:
                return "color-button disabled icon-button error-status", dash.no_update, dash.no_update
        
        # Create architecture if it does not exist yet
        if not workspace.architecture_exists(arch_path, arch_name):
            workspace.create_architecture(arch_path, arch_name)

        # Save settings
        try:
            workspace.save_architecture_settings(arch_path, arch_name, current_settings)
            return "color-button disabled icon-button", new_search, current_settings
        except Exception as e:
            return "color-button disabled icon-button error-status", dash.no_update, dash.no_update
    else:
        if current_settings != settings or arch_title != arch_name:
            return "color-button orange icon-button", dash.no_update, dash.no_update

    return "color-button disabled icon-button", dash.no_update, saved_settings

@dash.callback(
    Output("generate-settings", "className"),
    Output("rtl-path-container", "className"),
    Input("generate_rtl", "value"),
)
def toggle_generate_settings(generate_rtl):
    generate_settings_class = "animated-section" if generate_rtl else "animated-section hide"
    rtl_path_style = "animated-section" if not generate_rtl else "animated-section hide"
    return generate_settings_class, rtl_path_style

@dash.callback(
    Output({"page": page_path, "type": "architecture-title-div"}, "children"),
    Input("url", "search"),
)
def update_architecture_title(search):
    arch_name = get_key_from_url(search, "arch")
    if not arch_name:
        arch_name = ""
    return architecture_title(arch_name)


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id="url"),
        html.Div(id={"page": page_path, "type": "architecture-title-div"}, style={"marginTop": "20px"}),
        html.Div(id="arch-form-container"),
        dcc.Store(id="save-state", data=""),
        dcc.Store(id="architecture-initial-settings", data=None),
        dcc.Store(id="architecture-saved-settings", data=None), 
    ],
    className="page-content",
    style={
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

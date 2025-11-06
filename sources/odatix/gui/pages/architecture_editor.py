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
from typing import Optional#, Literal

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings
from odatix.gui.css_helper import Style

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
                tooltip="Open the Configuration Editor for this architecture",
                tooltip_options="bottom delay",
                color="default",
                link=f"/config_editor?arch={arch_name}",
                multiline=False,
                width="135px",
            ),
            ui.save_button(
                id={"page": page_path, "action": "save-all"},
                tooltip="Save all changes",
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
                                    placeholder="Architecture Name...",
                                    className="title-input",
                                    style={"width": "100%", "transform": "translate(-5px, 5px)"},
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

def architecture_form_field(
    label: str,
    id: str,
    value: str="",
    tooltip: str="",
    placeholder: str="",
    tooltip_options: str="secondary",
    # type: Optional[Literal["text", "number", "password", "email", "range", "search", "tel", "url", "hidden"]] = None,
    type = None,
):
    return html.Div(
        children=[
            html.Label(label),
            ui.tooltip_icon(tooltip, tooltip_options),
            dcc.Input(id=id, value=value, type=type, placeholder=placeholder, style={"width": "100%"}),
        ],
        style={"marginBottom": "12px"}
    )

def architecture_form(settings):
    defval = lambda k, v=None: settings.get(k, v)
    generate_rtl = True if str(defval("generate_rtl", "No")).lower() in ["yes", "true"] else False
    expand_design_path_filters = True if defval("design_path_whitelist", []) or defval("design_path_blacklist", []) else False

    return html.Div(
        children=[
            html.Div(style={"display": "none"}),
            html.Div([
                html.H3("RTL Generation"),
                html.Div([
                    dcc.Checklist(
                        options=[{"label": "Enable RTL Generation", "value": True}],
                        value=[True] if generate_rtl else [],
                        id="generate_rtl",
                        className="checklist-switch",
                        style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                    ),
                    ui.tooltip_icon("You can generate the RTL files from a higher-level design description like Chisel, HLS or any other tool using a custom command."),
                ], style={"marginBottom": "12px"}),
                html.Div(
                    children=[
                        architecture_form_field(
                            label="Design Path",
                            id="design_path",
                            value=defval("design_path", ""),
                            tooltip="Path to the design files needed for RTL generation. The whole path will be copied for each configuration, so use white/blacklists below to filter files if needed.",
                        ),
                        html.Div(
                            children=[
                                architecture_form_field(
                                    label="Design Path Whitelist",
                                    id="design_path_whitelist",
                                    value=", ".join(defval("design_path_whitelist", [])),
                                    placeholder="src, project, build.sbt",
                                    tooltip="Comma-separated list of patterns to include files from the design path. Only files matching these patterns will be included. Leave empty to include all files.",
                                ),
                                architecture_form_field(
                                    label="Design Path Blacklist",
                                    id="design_path_blacklist",
                                    value=", ".join(defval("design_path_blacklist", [])),
                                    placeholder="*.txt, docs/, tmp/",
                                    tooltip="Comma-separated list of patterns to exclude files from the design path. Files matching these patterns will be excluded. Leave empty to exclude no files. Note that you can use both whitelist and blacklist together.",
                                ),
                            ],
                            id="more-fields-design-path-filters",
                            className="animated-section" + ("" if expand_design_path_filters else " hide"),
                        ),
                        architecture_form_field(
                            label="Generation Command",
                            id="generate_command",
                            value=defval("generate_command", ""),
                            tooltip="Command to generate the RTL files. This command will be executed in each copy of the design path directory. Make sure all files needed for this command to succeed are included in the design path.",
                        ),
                        architecture_form_field(
                            label="Generation Output",
                            id="generate_output",
                            value=defval("generate_output", ""),
                            tooltip="Path to the generated RTL files relative to the design path.",
                        ),
                        ui.icon_button(
                            icon=icon(
                                "more",
                                className="icon normal rotate" + (" rotated" if expand_design_path_filters else ""),
                                id="more-fields-design-path-filters-toggle-icon"
                            ),
                            color="default",
                            id="more-fields-design-path-filters-toggle",
                            tooltip="Show/Hide whitelist and blacklist fields",
                        ),
                    ],
                    id="generate-settings",
                    className="animated-section" + ("" if generate_rtl else " hide"),
                    style={"overflow": "visible"},
                ),
            ], className="tile config"),
            html.Div([
                html.H3("Top Level Settings"),
                html.Div(
                    children=[
                        architecture_form_field(
                            label="RTL Path",
                            id="rtl_path",
                            value=defval("rtl_path", ""),
                            tooltip="The path to the directory containing the RTL source files.",
                        )
                    ],
                    id="rtl-path-container",
                    className="animated-section" + ("" if not generate_rtl else " hide"),
                    style={"overflow": "visible"},
                ),
                architecture_form_field(
                    label="Top Level File",
                    id="top_level_file",
                    value=defval("top_level_file", ""),
                    tooltip="The path of the file containing the top level (main) module/entity definition. This path is relative to the RTL path.",
                ),
                architecture_form_field(
                    label="Top Level Module",
                    id="top_level_module",
                    value=defval("top_level_module", ""),
                    tooltip="The name of the top level module/entity in your top level file.",
                ),
                architecture_form_field(
                    label="Clock Signal",
                    id="clock_signal",
                    value=defval("clock_signal", ""),
                    tooltip="The name of the clock signal in your top level module/entity.",
                ),
                architecture_form_field(
                    label="Reset Signal",
                    id="reset_signal",
                    value=defval("reset_signal", ""),
                    tooltip="The name of the reset signal in your top level module/entity.",
                ),
            ], className="tile config"),
            html.Div([
                html.H3("Synthesis Settings"),
                html.H4("Fmax Synthesis (MHz)"),
                architecture_form_field(
                    label="Lower Bound",
                    id="fmax_synthesis_lower",
                    value=defval("fmax_synthesis", {}).get("lower_bound", ""),
                    tooltip="The lower bound for the synthesis maximum operating frequency binary search ('odatix fmax' command). This value can be overriden by the argument --from (ex: 'odatix fmax --from 50 --to 200').",
                    tooltip_options="secondary large",
                    type="number",
                ),
                architecture_form_field(
                    label="Upper Bound",
                    id="fmax_synthesis_upper",
                    value=defval("fmax_synthesis", {}).get("upper_bound", ""),
                    tooltip="The upper bound for the synthesis maximum operating frequency binary search ('odatix fmax' command). This value can be overriden by the argument --to (ex: 'odatix fmax --from 50 --to 200')",
                    tooltip_options="secondary large",
                    type="number",
                ),
                html.H4("Custom Freq Synthesis (MHz)"),
                architecture_form_field(
                    label="List",
                    id="custom_freq_synthesis_list",
                    value=", ".join(map(str, defval("custom_freq_synthesis", {}).get("list", []))),
                    tooltip="Comma-separated list of custom frequencies for synthesis (in MHz). The synthesis will be run for each frequency in this list ('odatix freq' command). Theses values can be overriden by the argument --at (ex: 'odatix freq --at 50 --at 100') or --from, --to and --step (ex: 'odatix freq --from 50 --to 200 --step 10').",
                    tooltip_options="secondary large",
                    type="text",
                ),
            ], className="tile config"),
        ], className="tiles-container config", style={"marginTop": "-10px", "marginBottom": "20px"},
    )


######################################
# Callbacks
######################################

@dash.callback(
    Output("arch-form-container", "children"),
    Output("architecture-initial-settings", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
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
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output(f"url_{page_path}", "search"),
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
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("architecture-initial-settings", "data"),
    State("architecture-saved-settings", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(
    n_clicks, arch_title, design_path, whitelist, blacklist, generate_rtl, generate_command, generate_output,
    rtl_path, top_level_file, top_level_module, clock_signal, reset_signal, 
    fmax_lower, fmax_upper, custom_freq_list, search, page, initial_settings, saved_settings,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update

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

    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    arch_name = get_key_from_url(search, "arch")
    
    current_settings_subset = {
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
            "list": [int(x.strip()) for x in custom_freq_list.split(", ") if x.strip()],
        } if custom_freq_list != "" else {},
    }

    if arch_name:
        current_settings = workspace.update_raw_settings(
            arch_path=arch_path,
            arch_name=arch_name,
            domain=hard_settings.main_parameter_domain,
            settings_to_update=current_settings_subset
        )
    else: 
        current_settings = current_settings_subset

    if not arch_title:
        return "color-button error-status icon-button tooltip bottom", "Architecture name cannot be empty", dash.no_update, saved_settings
    
    for c in hard_settings.invalid_filename_characters:
        if c in arch_title:
            c = "' ' (space)" if c == " " else f"'{c}'"
            return "color-button error-status icon-button tooltip bottom", f"Unauthorized character in architecture name: {c}", dash.no_update, saved_settings

    if triggered_id == {"page": page_path, "action": "save-all"}:
        # Rename architecture if needed
        new_search = dash.no_update
        if arch_title != arch_name:
            old_name = arch_name
            new_name = arch_title
            if workspace.architecture_exists(arch_path, new_name):
                return "color-button error-status icon-button tooltip bottom", f"'{new_name}' already exists", dash.no_update, dash.no_update
            try:
                workspace.rename_architecture(arch_path, old_name, new_name)
                arch_name = new_name
                new_search = f"?arch={new_name}"
            except Exception as e:
                return "color-button error-status icon-button tooltip bottom", "Failed renaming architecture", dash.no_update, dash.no_update
        
        # Create architecture if it does not exist yet
        if not workspace.architecture_exists(arch_path, arch_name):
            workspace.create_architecture(arch_path, arch_name)

        # Save settings
        try:
            workspace.save_architecture_settings(arch_path, arch_name, current_settings)
            return "color-button disabled icon-button tooltip delay bottom small", "Nothing to save", new_search, current_settings
        except Exception as e:
            return "color-button error-status icon-button tooltip bottom small", "Failed to save...", dash.no_update, dash.no_update
    else:
        if current_settings_subset != settings or arch_title != arch_name:
            return "color-button warning icon-button tooltip bottom small tooltip", "Unsaved changes!", dash.no_update, dash.no_update

    return "color-button disabled icon-button tooltip delay bottom small", "Nothing to save", dash.no_update, saved_settings

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
    Input(f"url_{page_path}", "search"),
)
def update_architecture_title(search):
    arch_name = get_key_from_url(search, "arch")
    if not arch_name:
        arch_name = ""
    return architecture_title(arch_name)

@dash.callback(
    Output("more-fields-design-path-filters", "className"),
    Output("more-fields-design-path-filters-toggle-icon", "className"),
    Input("more-fields-design-path-filters-toggle", "n_clicks"),
    State("more-fields-design-path-filters", "className"),
    prevent_initial_call=True,
)
def toggle_more_fields(n_clicks, expandable_area_class ):
    if "hide" in expandable_area_class:
        new_expandable_area_class = "animated-section"
        new_icon_class = "icon normal rotate rotated"
    else:
        new_expandable_area_class = "animated-section hide"
        new_icon_class = "icon normal rotate"
    return new_expandable_area_class, new_icon_class


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
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

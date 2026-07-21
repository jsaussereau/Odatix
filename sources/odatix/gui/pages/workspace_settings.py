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

import dash
from dash import html, dcc, Input, Output, State, ctx
from typing import Optional#, Literal

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings

page_path = "/workspace"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Workspace Settings',
    name='Workspace',
    order=10,
)

######################################
# UI Components
######################################

def workspace_form(settings):
    defval = lambda k, v=None: settings.get(k, v)
    use_benchmark = defval("use_benchmark", "")

    return ui.grid(
        children=[
            ui.panel(body=[
                ui.caption("Main paths"),
                ui.form_field(
                    label="Architecture directory",
                    id="arch_path",
                    value=defval("arch_path", ""),
                    placeholder=OdatixSettings.DEFAULT_ARCH_PATH,
                    tooltip="The path to the architecture directory where all architectures definitions are stored.",
                ),
                ui.form_field(
                    label="Simulation directory",
                    id="sim_path",
                    value=defval("sim_path", ""),
                    placeholder=OdatixSettings.DEFAULT_SIM_PATH,
                    tooltip="The path to the architecture directory where all simulations definitions are stored.",
                ),
                ui.form_field(
                    label="Target Definition directory",
                    id="target_path",
                    value=defval("target_path", ""),
                    placeholder=OdatixSettings.DEFAULT_TARGET_PATH,
                    tooltip="The path where target definitions for all tools are stored.",
                ),
            ]),
            ui.panel(body=[
                ui.caption("Settings files"),
                ui.form_field(
                    label="Clean settings",
                    id="clean_settings_file",
                    value=defval("clean_settings_file", ""),
                    placeholder=OdatixSettings.DEFAULT_CLEAN_SETTINGS_FILE,
                    tooltip="The path to the clean rules file used by 'odatix clean' command.",
                ),
                ui.form_field(
                    label="Simulation settings",
                    id="simulation_settings_file",
                    value=defval("simulation_settings_file", ""),
                    placeholder=OdatixSettings.DEFAULT_SIMULATION_SETTINGS_FILE,
                    tooltip="The path to the settings file used by 'odatix sim' command.",
                ),
                ui.form_field(
                    label="Fmax synthesis settings",
                    id="fmax_synthesis_settings_file",
                    value=defval("fmax_synthesis_settings_file", ""),
                    placeholder=OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
                    tooltip="The path to the settings file used by 'odatix fmax' command.",
                ),
                ui.form_field(
                    label="Custom synthesis settings",
                    id="custom_freq_synthesis_settings_file",
                    value=defval("custom_freq_synthesis_settings_file", ""),
                    placeholder=OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_SETTINGS_FILE,
                    tooltip="The path to the settings file used by 'odatix freq' command.",
                ),
            ]),
            ui.panel(body=[
                ui.caption("Work directory"),
                ui.form_field(
                    label="Main work path",
                    id="work_path",
                    value=defval("work_path", ""),
                    placeholder=OdatixSettings.DEFAULT_WORK_PATH,
                    tooltip="The path where all temporary files will be stored during synthesis and simulation.",
                ),
                ui.form_field(
                    label="Simulation work path",
                    id="simulation_work_path",
                    value=defval("simulation_work_path", ""),
                    placeholder=OdatixSettings.DEFAULT_SIMULATION_WORK_PATH,
                    tooltip="The path where temporary files will be stored during simulations, relative to the main work path.",
                ),
                ui.form_field(
                    label="Fmax synthesis work path",
                    id="fmax_synthesis_work_path",
                    value=defval("fmax_synthesis_work_path", ""),
                    placeholder=OdatixSettings.DEFAULT_FMAX_SYNTHESIS_WORK_PATH,
                    tooltip="The path where temporary files will be stored during Fmax synthesis, relative to the main work path.",
                ),
                ui.form_field(
                    label="Custom synthesis work path",
                    id="custom_freq_synthesis_work_path",
                    value=defval("custom_freq_synthesis_work_path", ""),
                    placeholder=OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_WORK_PATH,
                    tooltip="The path where temporary files will be stored during custom frequency synthesis, relative to the main work path.",
                ),
            ]),
            ui.panel(body=[
                ui.caption("Results"),
                ui.form_field(
                    label="Result path",
                    id="result_path",
                    value=defval("result_path", ""),
                    placeholder=OdatixSettings.DEFAULT_RESULT_PATH,
                    tooltip="The path where all results files will be stored after synthesis and simulation.",
                ),
                ui.form_dropdown(
                    label="Use benchmark results",
                    id="use_benchmark",
                    placeholder=f"{'Yes' if OdatixSettings.DEFAULT_USE_BENCHMARK else 'No'}",
                    options=[
                        {"label": "Yes", "value": True},
                        {"label": "No", "value": False},
                    ],
                    value=use_benchmark,
                    tooltip="Include benchmark results in synthesis results.",
                ),
                html.Div(
                    children=[
                        ui.form_field(
                            label="Benchmark file",
                            id="benchmark_file",
                            value=defval("benchmark_file", ""),
                            placeholder=OdatixSettings.DEFAULT_BENCHMARK_FILE,
                            tooltip="The path to the benchmark file.",
                        ),
                    ],
                    id="benchmark-file-container",
                    className="animated-section" + (" hide" if not use_benchmark else ""),
                    style={"overflow": "visible"},
                ),
            ]),
        ],
    )


######################################
# Callbacks
######################################

@dash.callback(
    Output("workspace-form-container", "children"),
    Output("workspace-initial-settings", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
)
def init_form(search, page):
    if page != page_path:
        return dash.no_update, dash.no_update

    settings = OdatixSettings.get_settings_file_dict()
    if settings is None:
        settings = {}
    return workspace_form(settings), settings

@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output("odatix-settings", "data", allow_duplicate=True),
    Output("workspace-saved-settings", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input("arch_path", "value"),
    Input("sim_path", "value"),
    Input("target_path", "value"),
    Input("clean_settings_file", "value"),
    Input("simulation_settings_file", "value"),
    Input("fmax_synthesis_settings_file", "value"),
    Input("custom_freq_synthesis_settings_file", "value"),
    Input("work_path", "value"),
    Input("simulation_work_path", "value"),
    Input("fmax_synthesis_work_path", "value"),
    Input("custom_freq_synthesis_work_path", "value"),
    Input("result_path", "value"),
    Input("use_benchmark", "value"),
    Input("benchmark_file", "value"),
    State(f"url_{page_path}", "pathname"),
    State("workspace-initial-settings", "data"),
    State("workspace-saved-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(
    save_n_clicks, arch_path, sim_path, target_path,
    clean_settings_file, simulation_settings_file, fmax_synthesis_settings_file,
    custom_freq_synthesis_settings_file, work_path, simulation_work_path,
    fmax_synthesis_work_path, custom_freq_synthesis_work_path, result_path,
    use_benchmark, benchmark_file,
    page, initial_settings, saved_settings
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    current_settings_subset = {
        "arch_path": arch_path,
        "sim_path": sim_path,
        "target_path": target_path,
        "clean_settings_file": clean_settings_file,
        "simulation_settings_file": simulation_settings_file,
        "fmax_synthesis_settings_file": fmax_synthesis_settings_file,
        "custom_freq_synthesis_settings_file": custom_freq_synthesis_settings_file,
        "work_path": work_path,
        "simulation_work_path": simulation_work_path,
        "fmax_synthesis_work_path": fmax_synthesis_work_path,
        "custom_freq_synthesis_work_path": custom_freq_synthesis_work_path,
        "result_path": result_path,
        "use_benchmark": "" if use_benchmark is None else use_benchmark,
        "benchmark_file": benchmark_file,
    }
    
    current_settings = current_settings_subset

    if triggered_id == {"page": page_path, "action": "save-all"}:
        # Save settings
        try:
            OdatixSettings.save_dict_to_file(current_settings)
            current_settings = OdatixSettings().to_dict()
            return "color-button disabled icon-button tooltip delay bottom small", "Nothing to save", current_settings, current_settings_subset
        except Exception as e:
            return "color-button error-status icon-button tooltip bottom small", "Failed to save...", dash.no_update, dash.no_update

    else:
        # Compare against what the settings file actually holds (the store
        # written by init_form, or the last save), not against the settings
        # template: every blank field means "use the default", which the
        # template spells out, so the page used to always look dirty.
        reference = saved_settings if saved_settings is not None else (initial_settings or {})
        saved_subset = {key: reference.get(key, "") for key in current_settings_subset}
        if current_settings_subset != saved_subset:
            return "color-button warning icon-button tooltip bottom small tooltip", "Unsaved changes!", dash.no_update, dash.no_update

    return "color-button disabled icon-button tooltip delay bottom small", "Nothing to save", dash.no_update, dash.no_update


@dash.callback(
    Output("arch_path", "value"),
    Output("sim_path", "value"),
    Output("target_path", "value"),
    Output("clean_settings_file", "value"),
    Output("simulation_settings_file", "value"),
    Output("fmax_synthesis_settings_file", "value"),
    Output("custom_freq_synthesis_settings_file", "value"),
    Output("work_path", "value"),
    Output("simulation_work_path", "value"),
    Output("fmax_synthesis_work_path", "value"),
    Output("custom_freq_synthesis_work_path", "value"),
    Output("result_path", "value"),
    Output("use_benchmark", "value"),
    Output("benchmark_file", "value"),
    Input({"page": page_path, "action": "reset-defaults"}, "n_clicks"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("workspace-initial-settings", "data"),
    State("workspace-saved-settings", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def reset_to_defaults(
     reset_n_clicks,
    search, page, initial_settings, saved_settings,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return [dash.no_update] * 14
    
    if triggered_id == {"page": page_path, "action": "reset-defaults"}:
        # Reset to defaults
        return [""] * 14
    return [dash.no_update] * 14

@dash.callback(
    Output("benchmark-file-container", "className"),
    Input("use_benchmark", "value"),
)
def toggle_generate_settings(use_benchmark):
    return "animated-section" if use_benchmark else "animated-section hide"

######################################
# Layout
######################################

title_buttons = html.Div(
    children=[
        ui.icon_button(
            id={"page": page_path, "action": "reset-defaults"},
            icon=icon("reset", className="icon"),
            tooltip="Restore default workspace settings",
            tooltip_options="bottom",
            color="caution",
        ),
        ui.save_button(
            id={"page": page_path, "action": "save-all"},
            tooltip="Save all changes",
            disabled=True,
        ),
    ],
    className="odx-header-actions",
)

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        html.Div(
            ui.page_bar(
                "Workspace Settings",
                actions=title_buttons,
                back_link="/",
                extra=html.Div(
                    "Every path is relative to the workspace. Leave a field blank to use its default value.",
                    className="odx-summary odx-status",
                ),
            ),
            id={"page": page_path, "type": "workspace-title-div"},
        ),
        html.Div(id="workspace-form-container"),
        dcc.Store(id="save-state", data=""),
        dcc.Store(id="workspace-initial-settings", data=None),
        dcc.Store(id="workspace-saved-settings", data=None),
    ],
    className="page-content odx-page",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

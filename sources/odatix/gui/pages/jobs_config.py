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
from typing import Optional, Sequence#, Literal

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings

page_path = "/jobs_config"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Job Selection',
    name='Jobs',
    order=3,
)

######################################
# UI Components
######################################


######################################
# Callbacks
######################################

@dash.callback(
    Output("job-section", "children"),
    Input("url", "search"),
    State("url", "pathname"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_param_domains(
    search, page, odatix_settings
):
    triggered_id = ctx.triggered_id

    if triggered_id == "url":
        if page != page_path:
            return dash.no_update, dash.no_update

    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    architectures = workspace.get_architectures(arch_path)
    job_sections = []
    for arch_name in architectures:     
        domains_configs = {}
        domains = [hard_settings.main_parameter_domain] + workspace.get_param_domains(arch_path, arch_name)
        domain_tiles = []
        for domain in domains:
            if not workspace.check_parameter_domain_use_parameters(arch_path, arch_name, domain):
                continue
            configurations = workspace.get_config_files(arch_path, arch_name, domain)
            if not configurations:
                continue
            configurations = [cfg[:-4] if cfg.endswith('.txt') else cfg for cfg in configurations] # Remove .txt extension
            domains_configs[domain] = configurations
            checklist = dcc.Checklist(
                options=[{"label": cfg, "value": cfg} for cfg in configurations],
                id={"type": "config-checklist", "arch": arch_name, "domain": domain},
                value=configurations,
                style={"marginTop": "10px", "marginLeft": "5px"},
            )
            domain_tile = html.Div(
                children=[
                    html.Div(
                        children=[
                            html.H3(domain if domain != hard_settings.main_parameter_domain else "Main Parameter Domain"),
                            checklist,
                        ],
                        className="config-domain-content",
                    )
                ],
                className="tile config",
            )
            domain_tiles.append(domain_tile)

        no_valid_domain = not domain_tiles

        # Default configuration tile
        domain_tiles.append(
             html.Div(
                children=[
                    html.Div(
                        children=[
                            html.H3("Default Configuration"),
                            dcc.Checklist(
                                options=[{"label": f"{arch_name} (default)", "value": arch_name}],
                                id={"type": "config-checklist", "arch": arch_name, "domain": "default"},
                                value=["default"],
                                style={"marginTop": "10px", "marginLeft": "5px"},
                            ),
                        ],
                        className="config-domain-content",
                    )
                ],
                className="tile config",
            )
        )
        all_combinations = [[f"{arch_name}"]] + workspace.generate_config_combinations(domains_configs, arch_name)
        formatted_combinations = [{"label": " + ".join(comb), "value": " + ".join(comb)} for comb in all_combinations]
        # Preview tile
        domain_tiles.append(
            html.Div(
                children=[
                    html.Div(
                        children=[
                            html.H3("Preview"),
                            dcc.Checklist(
                                options=formatted_combinations,
                                id={"type": "config-preview-checklist", "arch": arch_name},
                                value=[" + ".join(comb) for comb in all_combinations],
                                style={"marginTop": "10px", "marginLeft": "5px"},
                            )
                        ],
                        className="config-domain-content",
                    )
                ],
                className="tile config",
            )
        )
        arch_buttons = html.Div(
            children=[
                ui.icon_button(
                    icon=icon("gear", className="icon"),
                    text="Architecture Settings",
                    color="default",
                    link=f"/arch_editor?arch={arch_name}",
                    multiline=True,
                    width="135px",
                ),
                ui.icon_button(
                    icon=icon("edit", className="icon blue"),
                    text="Edit Configs",
                    tooltip="Open the Configuration Editor for this architecture",
                    tooltip_options="bottom delay",
                    color="default",
                    link=f"/config_editor?arch={arch_name}",
                    multiline=False,
                    width="135px",
                ),
            ],
            className="inline-flex-buttons",
        )            
        job_section = html.Div(
            children=[
                html.Div(
                    children=[
                        ui.title_tile(arch_name, buttons=arch_buttons, id={"type": "arch-title", "arch": arch_name}, switch=False, style={"scale": "1.01"}),
                    ], 
                    id=f"param-domain-title-div-{arch_name}",
                    className="card-matrix config",
                    style={"marginLeft": "-13px"},
                ),
                html.Div(
                    children=domain_tiles,
                    id={"type": "param-domains-container", "arch": arch_name},
                    className="tiles-container config animated-section hide no-margin", 
                    style={"marginBottom": "17px"},
                ),
                dcc.Store(
                    id={"type": "arch-metadata", "arch": arch_name},
                    data={"arch_name": arch_name},
                ),
            ],
            id = {"type": "job-section", "arch": arch_name},
        )
        job_sections.append(job_section)
    return job_sections


@dash.callback(
    Output({"type": "param-domains-container", "arch": dash.ALL}, "className"),                    
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    State({"type": "arch-metadata", "arch": dash.ALL}, "data"),
)
def toggle_param_domains(selected_archs, arch_metadatas):
    triggered_id = ctx.triggered_id
    if not isinstance(triggered_id, dict):
        return [dash.no_update] * len(selected_archs)
    triggered_arch = triggered_id.get("arch", "")
    updated_classes = []
    for toggled, metadata in zip(selected_archs, arch_metadatas):
        arch_name = metadata.get("arch_name", "")
        if triggered_arch == arch_name:
            if toggled:
                updated_classes.append("tiles-container config animated-section")
            else:
                updated_classes.append("tiles-container config animated-section hide no-margin")
        else:
            updated_classes.append(dash.no_update)
    return updated_classes
    

######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id=f"url"),
        html.Div(id={"page": page_path, "type": "architecture-title-div"}, style={"marginTop": "20px"}),
        html.Div(id="job-section", style={"marginBottom": "10px"}),
    ],
    className="page-content",
    style={
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

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
            return dash.no_update

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
                id={"type": "domain-config-checklist", "arch": arch_name, "domain": domain},
                value=configurations,
                style={"width": "max-content", "marginTop": "10px", "marginLeft": "5px", "marginBottom": "10px"},
            )
            domain_tile = html.Div(
                children=[
                    html.Div(
                        children=[
                            html.H3(domain if domain != hard_settings.main_parameter_domain else "Main Parameter Domain", style={"marginBottom": "0px"}),
                            html.Div(
                                children=checklist,
                                style={"overflowX": "scroll", "marginBottom": "-10px"},
                            )
                        ],
                        className="config-domain-content",
                    )
                ],
                className="tile config",
            )
            domain_tiles.append(domain_tile)

        # Default configuration tile
        domain_tiles.append(
             html.Div(
                children=[
                    html.Div(
                        children=[
                            html.H3("Default Configuration", style={"marginBottom": "0px"}),
                            html.Div(
                                children=[
                                    dcc.Checklist(
                                        options=[{"label": f"{arch_name} (default)", "value": arch_name}],
                                        id={"type": "default-config-checklist", "arch": arch_name, "domain": "default"},
                                        value=["default"],
                                        style={"width": "max-content", "marginTop": "10px", "marginLeft": "5px", "marginBottom": "10px"},
                                    ),
                                ],
                                style={"overflowX": "scroll", "marginBottom": "-10px"},
                            )
                        ],
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
                            html.H3("Preview", style={"marginBottom": "0px"}),
                            html.Div(
                                children=[
                                    dcc.Checklist(
                                        options=formatted_combinations,
                                        id={"type": "preview-config-checklist", "arch": arch_name},
                                        value=[" + ".join(comb) for comb in all_combinations],
                                        style={"width": "max-content", "marginTop": "10px", "marginLeft": "5px", "marginBottom": "10px"},
                                    )
                                ],
                                style={"overflowX": "scroll", "marginBottom": "-10px"},
                            )
                        ],
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
                dcc.Store(
                    id={"type": "domain-selections", "arch": arch_name},
                    data=domains_configs,
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
    

@dash.callback(
    Output({"type": "domain-selections", "arch": dash.MATCH}, "data"),
    Input({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "id"),
)
def update_domain_selections(selected_per_domain, domain_ids):
    domains_configs = {}
    for values, did in zip(selected_per_domain or [], domain_ids or []):
        domain = did.get("domain")
        if not domain:
            continue
        if values:
            domains_configs[domain] = values
    return domains_configs

@dash.callback(
    Output({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    Input({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "id"),
    State({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    State({"type": "domain-selections", "arch": dash.MATCH}, "data"),
)
def sync_preview_values(
    selected_per_domain,
    domain_ids,
    current_preview_values,
    arch_metadata,
    prev_selections
):
    arch_name = arch_metadata.get("arch_name", "")

    # Build the current state of the domains
    current_domains = {}
    for values, did in zip(selected_per_domain or [], domain_ids or []):
        domain = did.get("domain")
        if not domain:
            continue
        if values:
            current_domains[domain] = values

    # Previous state of the domains (can be None on first call)
    prev_domains = prev_selections or {}

    # Find the domain that changed and the added/removed values
    changed_domain = None
    added_values = set()
    removed_values = set()

    # Domains present either before or now
    all_domains = set(prev_domains.keys()) | set(current_domains.keys())
    for domain in all_domains:
        prev_vals = set(prev_domains.get(domain, []))
        curr_vals = set(current_domains.get(domain, []))
        if prev_vals != curr_vals:
            changed_domain = domain
            added_values = curr_vals - prev_vals
            removed_values = prev_vals - curr_vals
            break

    # If no clear change is found, do nothing
    if not changed_domain:
        return current_preview_values or []

    # Start from the current preview value (including manual changes)
    preview_set = set(current_preview_values or [])

    # Helper: generate all complete combinations from current_domains
    all_combos = workspace.generate_config_combinations(current_domains, arch_name)
    all_combo_strings = {" + ".join(c) for c in all_combos}

    # Handle added values in the modified domain
    if added_values:
        for combo in all_combos:
            combo_str = " + ".join(combo)
            # Only handle combos that contain at least one added value
            if any(val in combo_str for val in added_values):
                preview_set.add(combo_str)

    # Handle removed values in the modified domain
    if removed_values:
        to_remove = set()
        for item in preview_set:
            # Do not touch the 'default' item
            if item == arch_name:
                continue
            # If the item is no longer a valid combo, only handle it
            # if it included a removed value from the concerned domain.
            # Simply check if it contains one of the removed values.
            if any(val in item for val in removed_values):
                to_remove.add(item)
        preview_set -= to_remove

    # Keep the "default" item if it was already selected
    if current_preview_values and arch_name in current_preview_values:
        preview_set.add(arch_name)

    # Return a sorted list for display stability
    result = []
    if arch_name in preview_set:
        result.append(arch_name)
        preview_set.remove(arch_name)
    result.extend(sorted(preview_set))

    return result


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

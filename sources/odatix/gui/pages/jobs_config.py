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
    name='Run jobs',
    order=3,
)

MAX_PREVIEW_COMBINATIONS = 10000

######################################
# UI Components
######################################

def job_settings_form_field(
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

def job_settings_form(settings):
    defval = lambda k, v=None: settings.get(k, v)

    return html.Div(
        children=[
            html.Div(style={"display": "none"}),
            html.Div([
                html.H3("Job Execution Settings"),
                html.Div([
                    dcc.Checklist(
                        options=[{"label": "Overwrite existing result", "value": True}],
                        value=[True] if True else [],
                        id="overwrite",
                        className="checklist-switch",
                        style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                    ),
                    ui.tooltip_icon("If enabled, previous results will be overwritten. (overridden by -o / --overwrite)"),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    dcc.Checklist(
                        options=[{"label": "Force single threading", "value": True}],
                        value=[True] if True else [],
                        id="force_single_thread",
                        className="checklist-switch",
                        style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                    ),
                    ui.tooltip_icon("If enabled, each job will run using a single thread."),
                ], style={"marginBottom": "12px"}),
                job_settings_form_field(
                    label="Maximum number of parallel jobs",
                    id="nb_jobs",
                    value=str(defval("nb_jobs", 8)),
                    tooltip="Maximum number of jobs to run in parallel. (overridden by -j / --jobs)",
                ),
            ], className="tile config"),
            html.Div([
                html.H3("Monitor Settings"),
                job_settings_form_field(
                    label="Prompt 'Continue? (Y/n)' after settings checks",
                    id="ask_continue",
                    value="Yes" if defval("ask_continue", False) else "No",
                    tooltip="Ask for confirmation after checking settings. (overridden by -y / --noask)",
                ),
                job_settings_form_field(
                    label="Exit monitor when all jobs are done",
                    id="exit_when_done",
                    value="Yes" if defval("exit_when_done", False) else "No",
                    tooltip="Exit the monitor automatically when all jobs are finished. (overridden by -E / --exit)",
                ),
                job_settings_form_field(
                    label="Size of the log history per job in the monitor",
                    id="log_size_limit",
                    value=str(defval("log_size_limit", 300)),
                    tooltip="Number of log lines to keep per job. (overridden by --logsize)",
                ),
            ], className="tile config"),
        ], className="tiles-container config", style={"marginTop": "-10px", "marginBottom": "20px"},
    )

######################################
# Callbacks
######################################

@dash.callback(
    Output("job-settings-form-container", "children"),
    Output("job-settings-initial-settings", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
)
def init_form(search, page):
    if page != page_path:
        return dash.no_update, dash.no_update

    settings = {}
    if settings is None:
        settings = {}
    return job_settings_form(settings), settings

@dash.callback(
    Output("job-section", "children"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
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

        n_combos = workspace.count_combinations(domains_configs)
        if n_combos > MAX_PREVIEW_COMBINATIONS:
            domain_tiles.append(
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                html.H3(f"Preview ({n_combos} combinations)", id={"type": "preview-config-title", "arch": arch_name}, style={"marginBottom": "0px"}),
                                f"Too many combinations to display (> {MAX_PREVIEW_COMBINATIONS})."
                            ],
                        )
                    ],
                    className="tile config",
                )
            )
        else:
            all_combinations = [[f"{arch_name}"]] + workspace.generate_config_combinations(domains_configs, arch_name)
            if len(all_combinations) > MAX_PREVIEW_COMBINATIONS:
                all_combinations = [{comb[0]} for comb in all_combinations]  # Only show default if too many combinations
            formatted_combinations = [{"label": " + ".join(comb), "value": " + ".join(comb)} for comb in all_combinations]
            # Preview tile
            domain_tiles.append(
                html.Div(
                    children=[
                        html.H3(f"Preview ({n_combos} combinations)", id={"type": "preview-config-title", "arch": arch_name}, style={"marginBottom": "0px"}),
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
    Output({"type": "preview-config-title", "arch": dash.MATCH}, "children"),
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
    # Use a deterministic order (Dash provides domain_ids in display order).
    ordered_domains = []
    for did in (domain_ids or []):
        d = did.get("domain") if isinstance(did, dict) else None
        if d and d not in ordered_domains:
            ordered_domains.append(d)
    for d in sorted(all_domains):
        if d not in ordered_domains:
            ordered_domains.append(d)

    for domain in ordered_domains:
        prev_vals = set(prev_domains.get(domain, []))
        curr_vals = set(current_domains.get(domain, []))
        if prev_vals != curr_vals:
            changed_domain = domain
            added_values = curr_vals - prev_vals
            removed_values = prev_vals - curr_vals
            break

    # If no clear change is found, do nothing
    if not changed_domain:
        n_combos = 0
        if current_preview_values:
            n_combos = len(current_preview_values)
        return current_preview_values or [], f"Preview ({n_combos} combinations)"

    # Start from the current preview value (including manual changes)
    preview_set = set(current_preview_values or [])

    # Helper: generate all complete combinations from current_domains
    all_combos = workspace.generate_config_combinations(current_domains, arch_name)
    all_combo_strings = {" + ".join(c) for c in all_combos}

    # Values are domain-scoped in combos as "<domain>/<cfg>" (or "<arch_name>/<cfg>" for main).
    display_domain = arch_name if changed_domain == hard_settings.main_parameter_domain else changed_domain
    added_tokens = {f"{display_domain}/{v}" for v in added_values}
    removed_tokens = {f"{display_domain}/{v}" for v in removed_values}

    # Handle added values in the modified domain
    if added_values:
        for combo in all_combos:
            combo_str = " + ".join(combo)
            # Only handle combos that contain an added value for the changed domain.
            if any(part in added_tokens for part in combo):
                preview_set.add(combo_str)

    # Handle removed values in the modified domain
    if removed_values:
        to_remove = set()
        for item in preview_set:
            # Do not touch the 'default' item
            if item == arch_name:
                continue
            parts = [p.strip() for p in str(item).split(" + ")]
            # Only remove combos that explicitly contain the removed token for the changed domain.
            if any(part in removed_tokens for part in parts):
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

    n_combos = len(result)
    return result, f"Preview ({n_combos} combinations)"

######################################
# Layout
######################################

title_buttons = html.Div(
    children=[
        ui.icon_button(
            id={"page": page_path, "action": "reset-defaults"},
            icon=icon("gear", className="icon"),
            text="Choose Targets",
            multiline=True,
            tooltip="Go to the Targets page to select targets",
            tooltip_options="bottom",
            color="default",
        ),
        ui.save_button(
            id={"page": page_path, "action": "save-all"},
            tooltip="Save all changes",
            disabled=True,
        ),
        ui.icon_button(
            id={"page": page_path, "action": "run-jobs"},
            icon=icon("play", className="icon"),
            text="Run Jobs",
            multiline=True,
            tooltip="Run all selected architecture configurations",
            tooltip_options="bottom",
            color="success",
        ),
    ],
    className="inline-flex-buttons",
)


layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}", refresh=False),
        html.Div(id={"page": page_path, "type": "title-div"}, style={"marginTop": "20px"}),
        # html.H2("Synthesis settings", style={"textAlign": "center"}),
        # html.Div(id="job-settings-form-container", style={"marginBottom": "10px"}),
        # dcc.Store(id="job-settings-initial-settings", data=None),
        ui.title_tile("Select architecture configurations to run", buttons=title_buttons, style={"marginTop": "10px", "marginBottom": "20px"}),
        # html.H2("Targets", style={"textAlign": "center"}),
        # html.Div(id="target-section", style={"marginBottom": "10px"}),
        html.H2("Architectures", style={"textAlign": "center"}),
        html.Div(id="job-section", style={"marginBottom": "10px"}),
    ],
    className="page-content",
    style={
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

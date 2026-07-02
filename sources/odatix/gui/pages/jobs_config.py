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
import threading
import io
import contextlib
from urllib.parse import quote
import dash
from dash import html, dcc, Input, Output, State, ctx
from typing import Optional, Sequence#, Literal

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url, ansi_to_html_spans
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings
import odatix.components.run_fmax_synthesis as run_fmax_synthesis
import odatix.components.run_range_synthesis as run_range_synthesis
from odatix.lib.parallel_job_handler import daemon_control

page_path = "/jobs_config"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Job Selection',
    name='Run jobs',
    order=3,
)

MAX_PREVIEW_COMBINATIONS = 10000

class _ThreadSafeBuffer(io.StringIO):
    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()

    def write(self, s):
        with self._lock:
            return super().write(s)

    def getvalue(self):
        with self._lock:
            return super().getvalue()

    def flush(self):
        with self._lock:
            return super().flush()

_prepare_thread = None
_prepare_cancel_event = threading.Event()
_prepare_log_buffer = _ThreadSafeBuffer()
_prepare_status = {"status": "idle", "error": None}
_prepare_parallel_jobs = None
_prepare_monitor_href = None
_prepare_check_data = None
_prepare_runtime_settings = None
_prepare_exec_thread = None
_prepare_synth_type = None
_prepare_enqueued = False
_prepare_enqueue_lock = threading.Lock()

def _reset_prepare_state():
    global _prepare_cancel_event, _prepare_log_buffer, _prepare_status, _prepare_parallel_jobs, _prepare_monitor_href
    global _prepare_check_data, _prepare_runtime_settings, _prepare_exec_thread, _prepare_synth_type, _prepare_enqueued
    _prepare_cancel_event = threading.Event()
    _prepare_log_buffer = _ThreadSafeBuffer()
    _prepare_status = {"status": "checking", "error": None}
    _prepare_parallel_jobs = None
    _prepare_monitor_href = None
    _prepare_check_data = None
    _prepare_runtime_settings = None
    _prepare_exec_thread = None
    _prepare_synth_type = None
    _prepare_enqueued = False


def _normalize_session_selector(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text == "__new_session__":
        return None
    return text


def _session_option(daemon: dict) -> dict:
    host = str(daemon.get("host", hard_settings.daemon_default_host))
    port = int(daemon.get("port", hard_settings.daemon_default_port))
    session_id = str(daemon.get("session_id", "")).strip()
    session_name = str(daemon.get("session_name", "")).strip()

    value = session_id or session_name or f"{host}:{port}"
    label = session_id or session_name or f"{host}:{port}"
    return {
        "label": label,
        "value": value,
        "title": f"{host}:{port}",
    }

def _run_check_custom_freq_settings(
    run_config_settings_filename,
    arch_path,
    tool,
    work_path,
    target_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
    check_eda_tool,
    custom_freq_list=None,
):
    global _prepare_status, _prepare_check_data
    if custom_freq_list is None:
        custom_freq_list = []
    try:
        with contextlib.redirect_stdout(_prepare_log_buffer):
            _prepare_check_data = run_range_synthesis.check_settings(
                run_config_settings_filename,
                arch_path,
                tool,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                check_eda_tool,
                custom_freq_list=custom_freq_list,
                debug=False,
                keep=False,
                cancel_event=_prepare_cancel_event,
            )
        _prepare_status = {"status": "checked", "error": None}
    except run_range_synthesis.SynthesisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _run_check_fmax_settings(
    run_config_settings_filename,
    arch_path,
    tool,
    work_path,
    target_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
    continue_on_error,
    check_eda_tool,
):
    global _prepare_status, _prepare_check_data
    try:
        with contextlib.redirect_stdout(_prepare_log_buffer):
            _prepare_check_data = run_fmax_synthesis.check_settings(
                run_config_settings_filename,
                arch_path,
                tool,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                continue_on_error,
                check_eda_tool,
                forced_fmax_lower_bound=None,
                forced_fmax_upper_bound=None,
                debug=False,
                keep=False,
                cancel_event=_prepare_cancel_event,
            )
        _prepare_status = {"status": "checked", "error": None}
    except run_fmax_synthesis.SynthesisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _run_prepare_synthesis():
    global _prepare_status, _prepare_parallel_jobs
    try:
        if not _prepare_check_data:
            raise RuntimeError("Missing preparation settings")
        (
            architecture_instances,
            prepare_job,
            job_list,
            tool_settings_file,
            arch_handler,
            exit_when_done,
            log_size_limit,
            nb_jobs,
        ) = _prepare_check_data
        with contextlib.redirect_stdout(_prepare_log_buffer):
            if _prepare_synth_type == "fmax_synthesis":
                _prepare_parallel_jobs = run_fmax_synthesis.prepare_synthesis(
                    architecture_instances=architecture_instances,
                    prepare_job=prepare_job,
                    job_list=job_list,
                    tool_settings_file=tool_settings_file,
                    arch_handler=arch_handler,
                    exit_when_done=exit_when_done,
                    log_size_limit=log_size_limit,
                    nb_jobs=nb_jobs,
                    cancel_event=_prepare_cancel_event,
                )
            else:
                _prepare_parallel_jobs = run_range_synthesis.prepare_synthesis(
                    architecture_instances=architecture_instances,
                    prepare_job=prepare_job,
                    job_list=job_list,
                    tool_settings_file=tool_settings_file,
                    arch_handler=arch_handler,
                    exit_when_done=exit_when_done,
                    log_size_limit=log_size_limit,
                    nb_jobs=nb_jobs,
                    cancel_event=_prepare_cancel_event,
                )
        _prepare_status = {"status": "prepared", "error": None}
    except run_range_synthesis.SynthesisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except run_fmax_synthesis.SynthesisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _checklist_enabled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return True in value or len(value) > 0
    return bool(value)

def _get_synth_settings_path(search: str, odatix_settings: dict) -> str:
    run_mode = get_key_from_url(search, "type")
    if run_mode == "custom_freq_synthesis":
        return odatix_settings.get(
            "custom_freq_synthesis_settings_file",
            OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_SETTINGS_FILE,
        )
    if run_mode == "fmax_synthesis":
        return odatix_settings.get(
            "fmax_synthesis_settings_file",
            OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
        )
    return odatix_settings.get(
        "fmax_synthesis_settings_file",
        OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
    )

def _arch_name_from_entry(entry: str) -> str:
    first_part = str(entry).split(" + ")[0].strip()
    if "/" in first_part:
        return first_part.split("/")[0].strip()
    return first_part

def _group_arch_selections(architectures_setting) -> dict:
    if not architectures_setting:
        return {}
    if isinstance(architectures_setting, dict):
        architectures = list(architectures_setting)
    else:
        architectures = list(architectures_setting)
    grouped = {}
    for entry in architectures:
        if entry is None:
            continue
        arch_name = _arch_name_from_entry(entry)
        if not arch_name:
            continue
        grouped.setdefault(arch_name, []).append(str(entry))
    return grouped

def _extract_domain_values(arch_name: str, selections) -> dict:
    """Return mapping of domain -> set(values) found in preview selection strings."""
    values_by_domain = {}
    for entry in selections or []:
        if entry is None:
            continue
        parts = [p.strip() for p in str(entry).split(" + ") if p.strip()]
        for part in parts:
            if "/" not in part:
                continue
            domain, value = part.split("/", 1)
            if domain == arch_name:
                domain = hard_settings.main_parameter_domain
            if not domain or value == "":
                continue
            values_by_domain.setdefault(domain, set()).add(value)
    return values_by_domain

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
    style: Optional[dict]=None,
    # type: Optional[Literal["text", "number", "password", "email", "range", "search", "tel", "url", "hidden"]] = None,
    type = None,
):
    return html.Div(
        children=[
            html.Label(label),
            ui.tooltip_icon(tooltip, tooltip_options),
            dcc.Input(id=id, value=value, type=type, placeholder=placeholder, style={"width": "100%"}),
        ],
        style={"marginBottom": "12px", **(style or {})},
    )

def job_settings_form(settings, run_mode="default"):
    frequencies = settings.get("frequencies", {})
    range = frequencies.get("range", {})

    return html.Div(
        children=[
            html.Div(style={"display": "none"}),
            html.Div([
                html.H3("Job Execution Settings"),
                html.Div([
                    dcc.Checklist(
                        options=[{"label": "Overwrite existing result", "value": True}],
                        value=[True] if settings.get("overwrite", False) else [],
                        id="overwrite",
                        className="checklist-switch",
                        style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                    ),
                    ui.tooltip_icon("If enabled, previous results will be overwritten. (overridden by -o / --overwrite)."),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    dcc.Checklist(
                        options=[{"label": "Force single threading", "value": True}],
                        value=[True] if settings.get("force_single_thread", True) else [],
                        id="force_single_thread",
                        className="checklist-switch",
                        style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                    ),
                    ui.tooltip_icon("If enabled, each job will run using a single thread."),
                ], style={"marginBottom": "12px"}),
                job_settings_form_field(
                    label="Maximum number of parallel jobs",
                    id="nb_jobs",
                    type="number",
                    value=str(settings.get("nb_jobs", 8)),
                    tooltip="Maximum number of jobs to run in parallel. (overridden by -j / --jobs)",
                ),
            ], className="tile config"),
            html.Div([
                html.H3("Monitor Settings"),
                job_settings_form_field(
                    label="Size of the log history per job in the monitor",
                    id="log_size_limit",
                    type="number",
                    value=str(settings.get("log_size_limit", 300)),
                    tooltip="Number of log lines to keep per job. (overridden by --logsize)",
                ),
                html.H3("CLI Settings"),
                html.Div([
                    dcc.Checklist(
                        options=[{"label": "Ask for confirmation after checking settings", "value": True}],
                        value=[True] if True else [],
                        id="ask_continue",
                        className="checklist-switch",
                        style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                    ),
                    ui.tooltip_icon("Prompt 'Continue? (Y/n)' after settings checks. (overridden by -y / --noask)."),
                ], style={"marginBottom": "12px"}),
                html.Div([
                    dcc.Checklist(
                        options=[{"label": "Exit terminal monitor when all jobs are done", "value": True}],
                        value=[True] if True else [],
                        id="exit_when_done",
                        className="checklist-switch",
                        style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                    ),
                    ui.tooltip_icon("Exit the monitor automatically when all jobs are finished. (overridden by -E / --exit)."),
                ], style={"marginBottom": "12px"}),
            ], className="tile config"),
            html.Div([
                html.H3("Custom Frequency Synthesis Settings"),
                dcc.Checklist(
                    options=[{"label": "Override frequencies", "value": True}],
                    value=[True] if frequencies.get("override", False) else [],
                    id="override-arch-frequencies",
                    className="checklist-switch",
                    style={"marginBottom": "15px", "display": "inline-block"},
                ),
                ui.tooltip_icon("Override architecture-specific frequencies."),
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                html.Label("List", style={"marginTop": "2px", "marginBottom": "-2px"}),
                                dcc.Checklist(
                                    options=[{"label": "", "value": True}],
                                    value=[True] if frequencies.get("use_custom_freq_list", False) else [],
                                    id="use-custom-freq-list",
                                    className="checklist-switch",
                                    style={"marginBottom": "-12px", "marginTop": "5px", "display": "inline-block"},
                                ),
                            ],
                            style={"display": "flex", "flexDirection": "column", "gap": "10px"},
                        ),
                        job_settings_form_field(
                            label="Target frequencies (MHz)",
                            id="target_frequencies",
                            type="text",
                            value=", ".join(str(f) for f in frequencies.get("list", [])),
                            tooltip="Comma-separated target frequencies for the synthesis.",
                            style={"width": "100%"},
                        ),
                    ],
                    style={"display": "flex", "flexDirection": "row", "gap": "25px"},
                ),
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                html.Label("Range", style={"marginTop": "2px", "marginBottom": "-2px"}),
                                dcc.Checklist(
                                    options=[{"label": "", "value": True}],
                                    value=[True] if frequencies.get("use_custom_freq_range", False) else [],
                                    id="use-custom-freq-range",
                                    className="checklist-switch",
                                    style={"marginBottom": "-12px", "marginTop": "5px", "display": "inline-block"},
                                ),
                            ],
                            style={"display": "flex", "flexDirection": "column", "gap": "10px"}
                        ),
                        job_settings_form_field(
                            label="From (MHz)",
                            id="from_frequency",
                            type="number",
                            value=str(range.get("from", "")),
                            tooltip="Lower frequency for the synthesis.",
                        ),
                        job_settings_form_field(
                            label="To (MHz)",
                            id="to_frequency",
                            type="number",
                            value=str(range.get("to", "")),
                            tooltip="Upper frequency for the synthesis.",
                        ),
                        job_settings_form_field(
                            label="Step (MHz)",
                            id="step_frequency",
                            type="number",
                            value=str(range.get("step", "")),
                            tooltip="Frequency step for the synthesis.",
                        ),
                    ],
                    style={"display": "flex", "flexDirection": "row", "gap": "25px"},
                )
            ], className="tile config", style={"display": "none" if run_mode != "custom_freq_synthesis" else "block"}),
        ], className="tiles-container config flex-tiles-container", style={"marginTop": "-10px", "marginBottom": "20px"},
    )

######################################
# Callbacks
######################################

@dash.callback(
    Output({"page": page_path, "action": "session-dropdown"}, "options"),
    Output({"page": page_path, "action": "session-dropdown"}, "value"),
    Input(f"url_{page_path}", "search"),
    Input("run-log-interval", "n_intervals"),
    State({"page": page_path, "action": "session-dropdown"}, "value"),
)
def update_session_dropdown(_search, _n, current_value):
    options = [{"label": "New session...", "value": "__new_session__", "title": "Run jobs in a new session"}]
    try:
        daemons = daemon_control.list_daemons()
    except Exception:
        daemons = []

    options.extend(_session_option(daemon) for daemon in daemons)

    values = {option.get("value") for option in options}
    selected = str(current_value).strip() if current_value is not None else "__new_session__"
    if selected not in values:
        selected = "__new_session__"

    return options, selected

@dash.callback(
    Output("job-settings-form-container", "children"),
    Output("job-settings-initial-settings", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_form(search, page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update

    run_mode = get_key_from_url(search, "type")
    settings_path = _get_synth_settings_path(search, odatix_settings or {})
    
    settings = workspace.load_arch_selection_settings(settings_path)
    if run_mode == "custom_freq_synthesis":
        settings = workspace.get_frequencies_form_values(settings)
    if settings is None:
        settings = {}
    return job_settings_form(settings, run_mode), settings

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

    settings_path = _get_synth_settings_path(search, odatix_settings or {})
    selection_settings = workspace.load_arch_selection_settings(settings_path)
    selection_map = _group_arch_selections(selection_settings.get("architectures", []))
    job_sections = []
    for arch_name in architectures:     
        domains_configs = {}
        domains = [hard_settings.main_parameter_domain] + workspace.get_param_domains(arch_path, arch_name)
        domain_tiles = []
        arch_enabled = arch_name in selection_map
        selected_domain_values = _extract_domain_values(arch_name, selection_map.get(arch_name, [])) if arch_enabled else {}
        for domain in domains:
            if not workspace.check_parameter_domain_use_parameters(arch_path, arch_name, domain):
                continue
            configurations = workspace.get_config_files(arch_path, arch_name, domain)
            if not configurations:
                continue
            configurations = [cfg[:-4] if cfg.endswith('.txt') else cfg for cfg in configurations] # Remove .txt extension
            domains_configs[domain] = configurations
            if arch_enabled:
                domain_selected = selected_domain_values.get(domain, set())
                checklist_values = [cfg for cfg in configurations if cfg in domain_selected]
            else:
                checklist_values = configurations
            checklist = dcc.Checklist(
                options=[{"label": cfg, "value": cfg} for cfg in configurations],
                id={"type": "domain-config-checklist", "arch": arch_name, "domain": domain},
                value=checklist_values,
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
            available_values = [opt.get("value") for opt in formatted_combinations]
            selected_values = selection_map.get(arch_name, [])
            filtered_selected = [val for val in selected_values if val in available_values]
            # Select all combinations for disabled architectures
            if arch_name not in selection_map:
                filtered_selected = [" + ".join(comb) for comb in all_combinations]
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
                                    value=filtered_selected,
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
                        ui.title_tile(
                            arch_name,
                            buttons=arch_buttons,
                            id={"type": "arch-title", "arch": arch_name},
                            switch=arch_enabled,
                            style={"scale": "1.01"}
                        ),
                    ], 
                    id=f"param-domain-title-div-{arch_name}",
                    className="card-matrix config",
                    style={"marginLeft": "-13px"},
                ),
                html.Div(
                    children=domain_tiles,
                    id={"type": "param-domains-container", "arch": arch_name},
                    className="tiles-container config animated-section" + ("" if arch_enabled else " hide no-margin"),
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


@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output("jobs-config-saved-selection", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    Input({"type": "preview-config-checklist", "arch": dash.ALL}, "value"),
    Input("override-arch-frequencies", "value"),
    Input("use-custom-freq-list", "value"),
    Input("target_frequencies", "value"),
    Input("use-custom-freq-range", "value"),
    Input("from_frequency", "value"),
    Input("to_frequency", "value"),
    Input("step_frequency", "value"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State("jobs-config-saved-selection", "data"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_architecture_selections(
    save_n_clicks,
    switch_values,
    preview_values,
    override_arch_frequencies,
    use_custom_freq_list,
    target_frequencies,
    use_custom_freq_range,
    from_frequency,
    to_frequency,
    step_frequency,
    switch_ids,
    preview_ids,
    saved_selection,
    search,
    page,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update

    preview_by_arch = {}
    for val, pid in zip(preview_values or [], preview_ids or []):
        arch = pid.get("arch") if isinstance(pid, dict) else None
        if arch:
            preview_by_arch[arch] = list(val or [])

    enabled_archs = []
    for val, sid in zip(switch_values or [], switch_ids or []):
        arch = sid.get("arch") if isinstance(sid, dict) else None
        is_enabled = bool(val)
        if arch and is_enabled:
            enabled_archs.append(arch)

    architectures = []
    for arch in enabled_archs:
        selections = preview_by_arch.get(arch, [])
        for item in selections:
            if item is None:
                continue
            architectures.append(str(item))

    # Remove duplicates but keep order
    architectures = list(dict.fromkeys(architectures))

    run_mode = get_key_from_url(search, "type")
    current_settings = {
        "architectures": architectures,
    }
    if run_mode == "custom_freq_synthesis":
        current_settings["frequencies"] = workspace.create_custom_frequencies_settings_dict(
            _checklist_enabled(override_arch_frequencies),
            target_frequencies,
            from_frequency,
            to_frequency,
            step_frequency,
        )

    if isinstance(saved_selection, dict):
        saved_settings = saved_selection
    else:
        saved_settings = {"architectures": saved_selection or []}

    if triggered_id == {"page": page_path, "action": "save-all"}:
        try:
            settings_path = _get_synth_settings_path(search, odatix_settings or {})
            base_settings = workspace.load_arch_selection_settings(settings_path)
            payload = {
                **base_settings,
                **current_settings,
            }
            workspace.save_architecture_selection(settings_path, payload, run_mode=run_mode, use_custom_freq_list=use_custom_freq_list, use_custom_freq_range=use_custom_freq_range)
            return (
                "color-button disabled icon-button tooltip delay bottom small",
                "Nothing to save",
                current_settings,
            )
        except Exception:
            return (
                "color-button error-status icon-button tooltip bottom small",
                "Failed to save...",
                dash.no_update,
            )

    if saved_settings.get("architectures", []) != current_settings.get("architectures", []):
        return (
            "color-button warning icon-button tooltip bottom small tooltip",
            "Unsaved changes!",
            dash.no_update,
        )

    if run_mode == "custom_freq_synthesis":
        saved_frequencies = saved_settings.get("frequencies", {})
        if saved_frequencies != current_settings.get("frequencies", {}):
            return (
                "color-button warning icon-button tooltip bottom small tooltip",
                "Unsaved changes!",
                dash.no_update,
            )

    return (
        "color-button disabled icon-button tooltip delay bottom small",
        "Nothing to save",
        dash.no_update,
    )

# Open run popup
@dash.callback(
    Output("run-popup", "className"),
    Output("run-popup-opened", "data"),
    Output("run-popup-title", "children"),
    Input({"page": page_path, "action": "run-jobs"}, "n_clicks"),
    prevent_initial_call=True
)
def show_run_popup(n_click):
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict) or not n_click:
        return dash.no_update, dash.no_update, dash.no_update
    
    return "overlay-odatix visible", True, "Checking settings..."

# Popup close
@dash.callback(
    Output("run-popup", "className", allow_duplicate=True),
    Output("run-popup-opened", "data", allow_duplicate=True),
    Input("run-cancel-btn", "n_clicks"),
    prevent_initial_call=True
)
def close_run_popup(n):
    return "overlay-odatix", False

@dash.callback(
    Output("jobs-config-run-status", "data"),
    Input({"page": page_path, "action": "run-jobs"}, "n_clicks"),
    State("overwrite", "value"),
    State("force_single_thread", "value"),
    State("nb_jobs", "value"),
    State("ask_continue", "value"),
    State("exit_when_done", "value"),
    State("log_size_limit", "value"),
    State({"page": page_path, "action": "session-dropdown"}, "value"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def run_jobs(
    n_clicks,
    overwrite,
    force_single_thread,
    nb_jobs,
    ask_continue,
    exit_when_done,
    log_size_limit,
    selected_session,
    search,
    page,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    global _prepare_thread
    if _prepare_thread is not None and _prepare_thread.is_alive():
        return {
            "status": "running",
            "type": get_key_from_url(search, "type"),
            "tool": get_key_from_url(search, "tool") or "vivado",
        }

    settings = odatix_settings or {}
    run_mode = get_key_from_url(search, "type")
    tool = get_key_from_url(search, "tool") or "vivado"

    arch_path = settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    target_path = settings.get("target_path", OdatixSettings.DEFAULT_TARGET_PATH)
    work_path_root = settings.get("work_path", OdatixSettings.DEFAULT_WORK_PATH)

    overwrite_enabled = _checklist_enabled(overwrite)
    ask_continue_enabled = _checklist_enabled(ask_continue)
    exit_when_done_enabled = _checklist_enabled(exit_when_done)

    try:
        nb_jobs_val = int(nb_jobs) if nb_jobs not in (None, "") else None
    except Exception:
        nb_jobs_val = None

    try:
        log_size_val = int(log_size_limit) if log_size_limit not in (None, "") else None
    except Exception:
        log_size_val = None

    noask = True
    check_eda_tool = True

    _reset_prepare_state()
    global _prepare_synth_type
    global _prepare_runtime_settings
    _prepare_synth_type = run_mode
    _prepare_runtime_settings = {
        "session": _normalize_session_selector(selected_session),
    }
    if run_mode == "custom_freq_synthesis":
        run_config_settings_filename = settings.get(
            "custom_freq_synthesis_settings_file",
            OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_SETTINGS_FILE,
        )
        work_path = os.path.join(
            work_path_root,
            settings.get("custom_freq_synthesis_work_path", OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_WORK_PATH),
        )

        _prepare_thread = threading.Thread(
            target=_run_check_custom_freq_settings,
            args=(
                run_config_settings_filename,
                arch_path,
                tool,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                check_eda_tool,
            ),
            daemon=True,
        )
        _prepare_thread.start()
    elif run_mode == "fmax_synthesis":
        run_config_settings_filename = settings.get(
            "fmax_synthesis_settings_file",
            OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
        )
        work_path = os.path.join(
            work_path_root,
            settings.get("fmax_synthesis_work_path", OdatixSettings.DEFAULT_FMAX_SYNTHESIS_WORK_PATH),
        )

        continue_on_error = True

        _prepare_thread = threading.Thread(
            target=_run_check_fmax_settings,
            args=(
                run_config_settings_filename,
                arch_path,
                tool,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                continue_on_error,
                check_eda_tool,
            ),
            daemon=True,
        )
        _prepare_thread.start()
    # else:
    #     run_config_settings_filename = settings.get(
    #         "fmax_synthesis_settings_file",
    #         OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
    #     )
    #     work_path = os.path.join(
    #         work_path_root,
    #         settings.get("fmax_synthesis_work_path", OdatixSettings.DEFAULT_FMAX_SYNTHESIS_WORK_PATH),
    #     )

    #     def _run():
    #         run_fmax_synthesis.prepare_synthesis(
    #             run_config_settings_filename,
    #             arch_path,
    #             tool,
    #             work_path,
    #             target_path,
    #             overwrite_enabled,
    #             noask,
    #             exit_when_done_enabled,
    #             log_size_val,
    #             nb_jobs_val,
    #             False,  # continue_on_error
    #             check_eda_tool,
    #             forced_fmax_lower_bound=None,
    #             forced_fmax_upper_bound=None,
    #             debug=False,
    #             keep=False,
    #         )

    # thread = threading.Thread(target=_run, daemon=True)
    # thread.start()

    return {
        "status": "checking",
        "type": run_mode,
        "tool": tool,
    }

@dash.callback(
    Output("jobs-config-run-status", "data", allow_duplicate=True),
    Output("run-popup-pre", "children"),
    Output("run-confirm-btn", "className"),
    Output("run-redirect", "href", allow_duplicate=True),
    Input("run-log-interval", "n_intervals"),
    State("jobs-config-run-status", "data"),
    State("run-popup-opened", "data"),
    prevent_initial_call=True,
)
def poll_prepare_log(n_intervals, run_status, run_popup_opened):
    if not run_status or not run_popup_opened:
        raise dash.exceptions.PreventUpdate

    current_status = run_status.get("status")
    if current_status == "canceled":
        return run_status, "", "color-button disabled icon-button", dash.no_update

    if _prepare_status.get("status") and _prepare_status.get("status") != current_status:
        run_status = {**run_status, **_prepare_status}
        current_status = run_status.get("status")

    if current_status in ("checking", "checked", "preparing", "prepared", "launched", "error"):
        log_output = _prepare_log_buffer.getvalue()
        button_class = "color-button success icon-button" if current_status == "checked" else "color-button disabled icon-button"
        redirect_href = dash.no_update
        if current_status == "prepared" and _prepare_parallel_jobs is not None:
            global _prepare_monitor_href, _prepare_enqueued
            should_enqueue = False
            with _prepare_enqueue_lock:
                if not _prepare_enqueued and _prepare_monitor_href is None:
                    _prepare_enqueued = True
                    should_enqueue = True

            if should_enqueue:
                try:
                    session_selector = None
                    if isinstance(_prepare_runtime_settings, dict):
                        session_selector = _normalize_session_selector(_prepare_runtime_settings.get("session"))

                    state, _response = daemon_control.enqueue_parallel_jobs(
                        _prepare_parallel_jobs,
                        session=session_selector,
                    )

                    session_id = str(state.get("session_id", "")).strip()
                    session_name = str(state.get("session_name", "")).strip()
                    if session_id:
                        _prepare_monitor_href = f"/monitor?session={quote(session_id, safe='')}"
                    elif session_name:
                        _prepare_monitor_href = f"/monitor?session={quote(session_name, safe='')}"
                    else:
                        host = str(state.get("host", hard_settings.daemon_default_host))
                        port = int(state.get("port", hard_settings.daemon_default_port))
                        _prepare_monitor_href = f"/monitor?host={quote(host, safe='')}&port={port}"
                    run_status = {**run_status, "status": "launched"}
                except Exception as exc:
                    with _prepare_enqueue_lock:
                        _prepare_enqueued = False
                    run_status = {"status": "error", "error": str(exc)}
                    if log_output:
                        log_output = log_output + "\n\n"
                    log_output = log_output + f"Failed to enqueue jobs in daemon session: {exc}"
                    return run_status, ansi_to_html_spans(log_output), "color-button disabled icon-button", dash.no_update

            if _prepare_monitor_href is not None:
                redirect_href = _prepare_monitor_href
        return run_status, ansi_to_html_spans(log_output) if log_output else "", button_class, redirect_href

    raise dash.exceptions.PreventUpdate

@dash.callback(
    Output("jobs-config-run-status", "data", allow_duplicate=True),
    Output("run-popup-pre", "children", allow_duplicate=True),
    Output("run-confirm-btn", "className", allow_duplicate=True),
    Input("run-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def cancel_prepare_synthesis(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    _prepare_cancel_event.set()
    return {"status": "canceled"}, "", "color-button disabled icon-button"

@dash.callback(
    Output("jobs-config-run-status", "data", allow_duplicate=True),
    Output("run-popup-title", "children", allow_duplicate=True),
    Output("run-confirm-btn", "className", allow_duplicate=True),
    Input("run-confirm-btn", "n_clicks"),
    State("jobs-config-run-status", "data"),
    prevent_initial_call=True,
)
def confirm_prepare_jobs(n_clicks, run_status):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if not run_status or run_status.get("status") != "checked":
        raise dash.exceptions.PreventUpdate

    global _prepare_exec_thread
    if _prepare_exec_thread is not None and _prepare_exec_thread.is_alive():
        raise dash.exceptions.PreventUpdate

    global _prepare_status
    _prepare_status = {"status": "preparing", "error": None}

    _prepare_exec_thread = threading.Thread(
        target=_run_prepare_synthesis,
        daemon=True,
    )
    _prepare_exec_thread.start()

    return {**run_status, "status": "preparing"}, "Preparing jobs...", "color-button disabled icon-button"

######################################
# Layout
######################################

title_buttons = html.Div(
    children=[
        dcc.Dropdown(
            id={"page": page_path, "action": "session-dropdown"},
            options=[
                {"label": "New session...", "value": "__new_session__"},
            ],
            placeholder="Select a session",
            value="__new_session__",
            clearable=False,
            style={"width": "155px", "marginRight": "10px"},
        ),
        ui.icon_button(
            id={"page": page_path, "action": "reset-defaults"},
            icon=icon("gear", className="icon"),
            link="/select_targets?tool=vivado",
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
        ui.title_tile("Select architecture configurations to run", buttons=title_buttons, style={"marginLeft": "-13px", "marginTop": "10px", "marginBottom": "10px"}),
        html.Div(id={"page": page_path, "type": "title-div"}, style={"marginTop": "20px"}),
        html.H2("Job Settings", style={"textAlign": "center", "marginBottom": "30px"}),
        html.Div(id="job-settings-form-container", style={"marginBottom": "10px"}),
        dcc.Store(id="job-settings-initial-settings", data=None),
        # html.H2("Targets", style={"textAlign": "center"}),
        # html.Div(id="target-section", style={"marginBottom": "10px"}),
        html.H2("Architectures", style={"textAlign": "center"}),
        html.Div(id="job-section", style={"marginBottom": "10px"}),
        dcc.Store(id="jobs-config-saved-selection", data=None),
        dcc.Store(id="jobs-config-run-status", data=None),
        dcc.Store(id="run-popup-opened", data=False),
        dcc.Location(id="run-redirect", refresh=True),
        dcc.Interval(id="run-log-interval", interval=500, n_intervals=0),
        html.Div(
            id="run-popup",
            className="overlay-odatix",
            children=[
                html.Div([
                    html.H2("Checking settings...", id="run-popup-title", style={"textAlign": "center"}),
                    html.Pre(id="run-popup-pre", className="run-popup-pre"),
                    html.Div([
                        html.Button("Cancel", id="run-cancel-btn", n_clicks=0, style={"marginLeft": "10px", "width": "90px"}),
                        ui.icon_button(
                            icon=icon("play", className="icon"),
                            color="disabled", 
                            text="Start", 
                            width="90px",
                            id="run-confirm-btn",
                        ),
                    ], style={"marginTop": "18px", "display": "flex", "justifyContent": "center"}),
                ], className="popup-odatix large")
            ]
        ),
    ],
    className="page-content",
    style={
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

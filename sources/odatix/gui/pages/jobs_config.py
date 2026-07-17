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
import itertools
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
import odatix.components.run_workflow as run_workflow
import odatix.components.run_analysis as run_analysis
from odatix.lib.parallel_job_handler import daemon_control

page_path = "/run_jobs"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Job Selection',
    name='Run jobs',
    order=3,
)

MAX_PREVIEW_COMBINATIONS = 10000

# Display labels for the eda tools that can run RTL analysis (analyze flow).
# The values must match hard_settings.default_supported_tools (used both by the
# CLI and by run_analysis.check_settings).
ANALYSIS_TOOL_LABELS = {
    "vivado": "Vivado",
    "design_compiler": "Design Compiler",
    "genus": "Genus",
    "openlane": "OpenLane",
    "verilator": "Verilator",
}

def _analysis_tool_options():
    """Checklist options for the analysis 'Tools' tile, ordered like
    hard_settings.default_supported_tools."""
    return [
        {"label": ANALYSIS_TOOL_LABELS.get(tool, tool), "value": tool}
        for tool in hard_settings.default_supported_tools
    ]

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

def _run_check_analysis_settings(
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
):
    global _prepare_status, _prepare_check_data
    try:
        with contextlib.redirect_stdout(_prepare_log_buffer):
            _prepare_check_data = run_analysis.check_settings(
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
                debug=False,
                keep=False,
                cancel_event=_prepare_cancel_event,
            )
        _prepare_status = {"status": "checked", "error": None}
    except run_analysis.AnalysisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except SystemExit:
        # check_settings() calls sys.exit(-1) when there is no valid architecture
        # to analyze: turn that into a normal error status.
        _prepare_status = {"status": "error", "error": "No valid architecture to analyze. See log above for details."}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _run_check_workflow_settings(
    run_config_settings_filename,
    workflow_path,
    work_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
):
    global _prepare_status, _prepare_check_data
    try:
        with contextlib.redirect_stdout(_prepare_log_buffer):
            _prepare_check_data = run_workflow.check_settings(
                run_config_settings_filename,
                workflow_path,
                work_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                debug=False,
                keep=False,
            )
        _prepare_status = {"status": "checked", "error": None}
    except SystemExit:
        # check_settings() calls sys.exit(-1) on invalid workflow settings
        # instead of raising: turn that into a normal error status.
        _prepare_status = {"status": "error", "error": "Invalid workflow settings. See log above for details."}
    except Exception as exc:
        _prepare_status = {"status": "error", "error": str(exc)}

def _run_prepare_synthesis():
    global _prepare_status, _prepare_parallel_jobs
    try:
        if not _prepare_check_data:
            raise RuntimeError("Missing preparation settings")
        with contextlib.redirect_stdout(_prepare_log_buffer):
            if _prepare_synth_type == "workflow":
                (
                    workflow_instances,
                    prepare_job,
                    job_list,
                    exit_when_done,
                    log_size_limit,
                    nb_jobs,
                ) = _prepare_check_data
                _prepare_parallel_jobs = run_workflow.prepare_workflows(
                    workflow_instances=workflow_instances,
                    prepare_job=prepare_job,
                    job_list=job_list,
                    exit_when_done=exit_when_done,
                    log_size_limit=log_size_limit,
                    nb_jobs=nb_jobs,
                )
            else:
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
                elif _prepare_synth_type == "analyze":
                    _prepare_parallel_jobs = run_analysis.prepare_synthesis(
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
    except run_analysis.AnalysisCancelled:
        _prepare_status = {"status": "canceled", "error": None}
    except SystemExit:
        # abort_if_empty_job_list() calls sys.exit(-1) when every selected job
        # failed while being built (e.g. a missing design_path): turn that into
        # a normal error status instead of silently launching an empty session.
        _prepare_status = {"status": "error", "error": "None of the selected jobs could be prepared. See log above for details."}
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
    if run_mode == "analyze":
        return odatix_settings.get(
            "analysis_settings_file",
            OdatixSettings.DEFAULT_ANALYSIS_SETTINGS_FILE,
        )
    return odatix_settings.get(
        "fmax_synthesis_settings_file",
        OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
    )

def _run_context(search, odatix_settings) -> dict:
    """
    Resolve everything that differs between job types (architectures vs
    workflows) from the ?type=... url parameter.

    Returns a dict with:
        mode           : "workflow" or "arch"
        base_path      : architectures / workflows directory
        settings_path  : the selection settings file to read/write
        selection_key  : the yaml key holding the selection ("workflows" / "architectures")
        instances      : list of instance names to display
        settings_link  : lambda name -> settings editor url
        config_link    : lambda name -> config editor url
        settings_text  : label of the settings button
        title          : plural heading of the instance section
    """
    settings = odatix_settings or {}
    run_mode = get_key_from_url(search, "type")
    if run_mode == "workflow":
        base_path = settings.get("workflow_path", OdatixSettings.DEFAULT_WORKFLOW_PATH)
        return {
            "mode": "workflow",
            "base_path": base_path,
            "settings_path": settings.get("workflow_settings_file", OdatixSettings.DEFAULT_WORKFLOW_SETTINGS_FILE),
            "selection_key": "workflows",
            "instances": workspace.get_workflows(base_path),
            "settings_link": lambda name: f"/workflow_editor?workflow={name}",
            "config_link": lambda name: f"/config_editor?workflow={name}",
            "settings_text": "Workflow Settings",
            "title": "Workflows",
        }
    base_path = settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    return {
        "mode": "arch",
        "base_path": base_path,
        "settings_path": _get_synth_settings_path(search, settings),
        "selection_key": "architectures",
        "instances": workspace.get_architectures(base_path),
        "settings_link": lambda name: f"/arch_editor?arch={name}",
        "config_link": lambda name: f"/config_editor?arch={name}",
        "settings_text": "Architecture Settings",
        "title": "Architectures",
    }

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

def _workflow_virtual_variant_combos(base_path, workflow_name):
    """
    Resolve the virtual parameter domains of a workflow (command-placeholder
    variables defined under "generate_configurations_settings.variables" in
    its _settings.yml, see run_workflow.py), by reusing the exact generation
    logic run_workflow.check_settings() uses at run time.

    Returns:
        combos        : list of [workflow_name, "domain/value", ...], one per
                         generated variant (empty if the workflow has none).
        domain_values : dict domain name -> sorted list of distinct values
                        seen across combos (for display only).
        error         : error message if the variable settings are invalid,
                         else None.
    """
    settings = workspace.load_workflow_settings(base_path, workflow_name)
    virtual_domain_names = run_workflow.get_workflow_virtual_domain_names(settings)
    if not virtual_domain_names:
        return [], {}, None

    settings_file = workspace.get_workflow_settings_path(base_path, workflow_name)
    variants = run_workflow.build_workflow_virtual_param_domain_variants(settings, settings_file, debug=False)
    if variants is None:
        return [], {}, "Invalid workflow variable settings. Check the workflow settings file."

    combos = [[workflow_name] + variant["requested_param_domains"] for variant in variants]
    domain_values = {}
    for combo in combos:
        for token in combo[1:]:
            domain, _, value = token.partition("/")
            domain_values.setdefault(domain, set()).add(value)
    domain_values = {domain: sorted(values) for domain, values in domain_values.items()}
    return combos, domain_values, None

def _select_all_buttons(button_type: str, id_keys: dict) -> html.Div:
    """Build a 'Select all' / 'Clear' button pair for a checklist.

    button_type is the pattern-matching id "type"; id_keys holds the other
    wildcard keys identifying the target checklist (e.g. arch/domain).
    """
    return html.Div(
        children=[
            html.Button("Select all", id={"type": button_type, "action": "show", **id_keys}, n_clicks=0, className="xp-mini-button"),
            html.Button("Clear", id={"type": button_type, "action": "hide", **id_keys}, n_clicks=0, className="xp-mini-button"),
        ],
        className="xp-filter-buttons",
    )

def _preview_title(n_combos: int, default_enabled: bool, n_selected: int = 0) -> str:
    """Format the preview tile heading, accounting for the default config.

    n_combos is the total number of non-default combinations and n_selected how
    many of them are currently checked, shown as "n_selected/n_combos". The
    default config is counted separately: "+1 default" when it is enabled
    alongside other combos, or "1 default" when it is the only selected entry.
    """
    if n_combos <= 0:
        return "Preview (1 default)" if default_enabled else "Preview (0 combinations)"
    word = "combination" if n_combos == 1 else "combinations"
    suffix = " +1 default" if default_enabled else ""
    return f"Preview ({n_selected}/{n_combos} {word}{suffix})"

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

def _expand_wildcard_selection(entry: str, domains_configs: dict, arch_name: str) -> list:
    """
    Expand a saved selection entry that uses a domain-value wildcard (e.g.
    "Arch + addr/* + data/5", or the bare main-domain form "Arch/*"), mirroring
    the wildcard syntax ArchitectureHandler.configuration_wildcard() understands
    at run time, into every concrete "arch + domain/value + ..." combo string it
    represents (the exact format produced by workspace.generate_config_combinations).

    Returns [entry] unchanged if it uses no wildcard ("*") value.
    """
    parts = [p.strip() for p in str(entry).split(" + ") if p.strip()]
    if not parts:
        return []

    constraints = {}
    order = []
    for part in parts:
        if "/" not in part:
            continue
        domain, value = part.split("/", 1)
        if domain == arch_name:
            domain = hard_settings.main_parameter_domain
        constraints[domain] = value
        order.append(domain)

    if "*" not in constraints.values():
        return [entry]

    value_lists = [
        domains_configs.get(domain, []) if constraints[domain] == "*" else [constraints[domain]]
        for domain in order
    ]

    expanded = []
    for combo_values in itertools.product(*value_lists):
        replaced_parts = [
            f"{arch_name if domain == hard_settings.main_parameter_domain else domain}/{value}"
            for domain, value in zip(order, combo_values)
        ]
        if order and order[0] != hard_settings.main_parameter_domain:
            combo = [arch_name] + replaced_parts
        else:
            combo = replaced_parts
        expanded.append(" + ".join(combo))
    return expanded

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

def job_settings_form(settings, run_mode="default", selected_tools=None):
    frequencies = settings.get("frequencies", {})
    range = frequencies.get("range", {})

    if selected_tools is None:
        selected_tools = settings.get("tools", [])
    selected_tools = [tool for tool in selected_tools if tool in ANALYSIS_TOOL_LABELS]

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
                html.H3("Tools"),
                html.Div([
                    html.Label("EDA tools to run the analysis with", style={"marginBottom": "8px", "display": "inline-block"}),
                    ui.tooltip_icon("Select every eda tool the RTL analysis should run with (saved as the 'tools' list of the analysis settings file, overridden by -t / --tool). The jobs of all selected tools run together in a single monitor session."),
                    dcc.Checklist(
                        options=_analysis_tool_options(),
                        value=selected_tools,
                        id="analysis-tools",
                        className="checklist-switch list",
                        style={"marginTop": "5px"},
                    ),
                ]),
            ], className="tile config", style={"display": "block" if run_mode == "analyze" else "none"}),
            html.Div([
                html.H3("Synthesis Constraints"),
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

    selected_tools = None
    if run_mode == "analyze":
        # Pre-check the "tools" list saved in the analysis settings file, plus
        # the tool selected on the "Choose EDA Tool" page (?tool=...).
        saved_tools = workspace.load_analysis_tools(settings_path)
        selected_tools = list(saved_tools)
        url_tool = get_key_from_url(search, "tool")
        if url_tool and url_tool not in selected_tools:
            selected_tools.append(url_tool)

    return job_settings_form(settings, run_mode, selected_tools=selected_tools), settings

@dash.callback(
    Output("job-section", "children"),
    Output("job-section-heading", "children"),
    Output("jobs-config-main-title", "children"),
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
            return dash.no_update, dash.no_update, dash.no_update

    context = _run_context(search, odatix_settings)
    arch_path = context["base_path"]
    architectures = context["instances"]

    settings_path = context["settings_path"]
    selection_settings = workspace.load_arch_selection_settings(settings_path)
    selection_map = _group_arch_selections(selection_settings.get(context["selection_key"], []))
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
                if "*" in domain_selected:
                    # Wildcard ("domain/*" or the bare "arch_name/*" main-domain
                    # form): select every configuration in this domain, like
                    # ArchitectureHandler.configuration_wildcard() does at run time.
                    checklist_values = list(configurations)
                else:
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
                            _select_all_buttons("domain-config-select-all", {"arch": arch_name, "domain": domain}),
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

        # Virtual parameter domains (workflow command-placeholder variables)
        virtual_combos = []
        if context["mode"] == "workflow":
            virtual_combos, virtual_domain_values, virtual_error = _workflow_virtual_variant_combos(arch_path, arch_name)
            if virtual_error:
                domain_tiles.append(
                    html.Div(
                        html.Div(virtual_error, className="error-message"),
                        className="tile config",
                    )
                )
            elif virtual_domain_values:
                domain_tiles.append(
                    html.Div(
                        children=[
                            html.H3("Workflow Variables", style={"marginBottom": "0px"}),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span(f"{domain}: ", style={"fontWeight": "bold"}),
                                            html.Span(", ".join(values)),
                                        ],
                                        style={"marginTop": "4px"},
                                    )
                                    for domain, values in virtual_domain_values.items()
                                ],
                                style={"marginTop": "10px", "marginLeft": "5px", "marginBottom": "10px"},
                            ),
                        ],
                        className="tile config",
                    )
                )

        # Compute the preview data up-front so the "Default Configuration" tile
        # and the preview stay consistent about whether the default config
        # (the bare "<arch_name>" entry) is selected. n_combos counts the
        # non-default combinations only; the default config is counted apart.
        n_combos = workspace.count_combinations(domains_configs) + len(virtual_combos)
        too_many = n_combos > MAX_PREVIEW_COMBINATIONS
        formatted_combinations = []
        filtered_selected = []
        if not too_many:
            all_combinations = [[f"{arch_name}"]] + workspace.generate_config_combinations(domains_configs, arch_name) + virtual_combos
            if len(all_combinations) > MAX_PREVIEW_COMBINATIONS:
                all_combinations = [{comb[0]} for comb in all_combinations]  # Only show default if too many combinations
            formatted_combinations = [{"label": " + ".join(comb), "value": " + ".join(comb)} for comb in all_combinations]
            available_values = [opt.get("value") for opt in formatted_combinations]
            selected_values = selection_map.get(arch_name, [])
            # Expand domain-value wildcards ("domain/*", or the bare "arch/*"
            # main-domain form) into every concrete combo they represent before
            # matching against the available combinations: a raw wildcard entry
            # never matches literally, which used to silently drop it from the
            # preview (and from what gets saved back on the next Save).
            expanded_selected = []
            for entry in selected_values:
                expanded_selected.extend(_expand_wildcard_selection(entry, domains_configs, arch_name))
            filtered_selected = [val for val in expanded_selected if val in available_values]
            # Select all combinations for disabled architectures
            if arch_name not in selection_map:
                filtered_selected = [" + ".join(comb) for comb in all_combinations]
            default_selected = arch_name in filtered_selected
            n_selected = len([v for v in filtered_selected if v != arch_name])
        else:
            default_selected = (arch_name not in selection_map) or (arch_name in selection_map.get(arch_name, []))
            n_selected = 0

        # Default configuration tile. Its checkbox is kept in sync with the
        # default "<arch_name>" entry of the preview checklist (both directions),
        # see sync_default_to_preview / sync_preview_to_default.
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
                                        value=[arch_name] if default_selected else [],
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

        if too_many:
            domain_tiles.append(
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                html.H3(_preview_title(n_combos, default_selected, n_selected), id={"type": "preview-config-title", "arch": arch_name}, style={"marginBottom": "0px"}),
                                f"Too many combinations to display (> {MAX_PREVIEW_COMBINATIONS})."
                            ],
                        )
                    ],
                    className="tile config",
                )
            )
        else:
            # Preview tile
            domain_tiles.append(
                html.Div(
                    children=[
                        html.H3(_preview_title(n_combos, default_selected, n_selected), id={"type": "preview-config-title", "arch": arch_name}, style={"marginBottom": "0px"}),
                        _select_all_buttons("preview-config-select-all", {"arch": arch_name}),
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
                    text=context["settings_text"],
                    color="default",
                    link=context["settings_link"](arch_name),
                    multiline=True,
                    width="135px",
                ),
                ui.icon_button(
                    icon=icon("edit", className="icon blue"),
                    text="Edit Configs",
                    tooltip=f"Open the Configuration Editor for this {context['mode']}",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["config_link"](arch_name),
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
                ),
                html.Div(
                    children=domain_tiles,
                    id={"type": "param-domains-container", "arch": arch_name},
                    className="tiles-container config animated-section" + ("" if arch_enabled else " hide no-margin"),
                    style={"marginBottom": "17px"},
                ),
                dcc.Store(
                    id={"type": "arch-metadata", "arch": arch_name},
                    data={"arch_name": arch_name, "n_combos": n_combos},
                ),
                dcc.Store(
                    id={"type": "domain-selections", "arch": arch_name},
                    data=domains_configs,
                ),
            ],
            id = {"type": "job-section", "arch": arch_name},
        )
        job_sections.append(job_section)
    main_title = f"Select {context['mode'] if context['mode'] == 'workflow' else 'architecture'} configurations to run"
    return job_sections, context["title"], main_title


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
    Output({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.MATCH}, "value"),
    Input({"type": "domain-config-select-all", "arch": dash.MATCH, "domain": dash.MATCH, "action": dash.ALL}, "n_clicks"),
    State({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.MATCH}, "options"),
    prevent_initial_call=True,
)
def domain_select_all(n_clicks, options):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not any(n_clicks or []):
        raise dash.exceptions.PreventUpdate
    if triggered.get("action") == "show":
        return [option["value"] for option in options or []]
    return []

@dash.callback(
    Output({"type": "preview-config-checklist", "arch": dash.MATCH}, "value", allow_duplicate=True),
    Input({"type": "preview-config-select-all", "arch": dash.MATCH, "action": dash.ALL}, "n_clicks"),
    State({"type": "preview-config-checklist", "arch": dash.MATCH}, "options"),
    prevent_initial_call=True,
)
def preview_select_all(n_clicks, options):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not any(n_clicks or []):
        raise dash.exceptions.PreventUpdate
    if triggered.get("action") == "show":
        return [option["value"] for option in options or []]
    return []

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

    # If no clear change is found, do nothing. The title is intentionally left
    # untouched: it reflects the total number of available combinations
    # (fixed at render time in update_param_domains), not how many are
    # currently checked -- recomputing it from len(current_preview_values)
    # here would show the checked count instead once any items are unchecked.
    if not changed_domain:
        return current_preview_values or []

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

    return result


@dash.callback(
    Output({"type": "preview-config-checklist", "arch": dash.MATCH}, "value", allow_duplicate=True),
    Input({"type": "default-config-checklist", "arch": dash.MATCH, "domain": "default"}, "value"),
    State({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sync_default_to_preview(default_value, preview_value, arch_metadata):
    """Mirror the 'Default Configuration' checkbox onto the default preview entry."""
    arch_name = (arch_metadata or {}).get("arch_name", "")
    default_on = arch_name in (default_value or [])
    preview_list = list(preview_value or [])
    has_default = arch_name in preview_list
    if default_on and not has_default:
        return [arch_name] + preview_list
    if not default_on and has_default:
        return [val for val in preview_list if val != arch_name]
    raise dash.exceptions.PreventUpdate


@dash.callback(
    Output({"type": "default-config-checklist", "arch": dash.MATCH, "domain": "default"}, "value"),
    Input({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sync_preview_to_default(preview_value, arch_metadata):
    """Mirror the default preview entry back onto the 'Default Configuration' checkbox."""
    arch_name = (arch_metadata or {}).get("arch_name", "")
    return [arch_name] if arch_name in (preview_value or []) else []


@dash.callback(
    Output({"type": "preview-config-title", "arch": dash.MATCH}, "children"),
    Input({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def update_preview_title(preview_value, arch_metadata):
    """Recompute the preview heading, reflecting whether the default config is selected."""
    metadata = arch_metadata or {}
    arch_name = metadata.get("arch_name", "")
    n_combos = metadata.get("n_combos", 0)
    selected = preview_value or []
    default_enabled = arch_name in selected
    n_selected = len([v for v in selected if v != arch_name])
    return _preview_title(n_combos, default_enabled, n_selected)


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
    Input("analysis-tools", "value"),
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
    analysis_tools,
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

    context = _run_context(search, odatix_settings)
    run_mode = get_key_from_url(search, "type")
    selection_key = context["selection_key"]
    current_settings = {
        selection_key: architectures,
    }
    if run_mode == "custom_freq_synthesis":
        current_settings["frequencies"] = workspace.create_custom_frequencies_settings_dict(
            _checklist_enabled(override_arch_frequencies),
            target_frequencies,
            from_frequency,
            to_frequency,
            step_frequency,
        )
    if run_mode == "analyze":
        current_settings["tools"] = [tool for tool in (analysis_tools or []) if tool]

    if isinstance(saved_selection, dict):
        saved_settings = saved_selection
    else:
        saved_settings = {selection_key: saved_selection or []}

    if triggered_id == {"page": page_path, "action": "save-all"}:
        try:
            settings_path = context["settings_path"]
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

    if saved_settings.get(selection_key, []) != current_settings.get(selection_key, []):
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

    if run_mode == "analyze":
        if saved_settings.get("tools", []) != current_settings.get("tools", []):
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
    State("analysis-tools", "value"),
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
    analysis_tools,
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

    # arch_path for architecture modes, workflow_path for workflow mode
    base_path = _run_context(search, odatix_settings)["base_path"]
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
                base_path,
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
                base_path,
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
    elif run_mode == "workflow":
        run_config_settings_filename = settings.get(
            "workflow_settings_file",
            OdatixSettings.DEFAULT_WORKFLOW_SETTINGS_FILE,
        )
        work_path = os.path.join(
            work_path_root,
            settings.get("workflow_work_path", OdatixSettings.DEFAULT_WORKFLOW_WORK_PATH),
        )

        _prepare_thread = threading.Thread(
            target=_run_check_workflow_settings,
            args=(
                run_config_settings_filename,
                base_path,
                work_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
            ),
            daemon=True,
        )
        _prepare_thread.start()
    elif run_mode == "analyze":
        run_config_settings_filename = settings.get(
            "analysis_settings_file",
            OdatixSettings.DEFAULT_ANALYSIS_SETTINGS_FILE,
        )
        work_path = os.path.join(
            work_path_root,
            settings.get("analysis_work_path", OdatixSettings.DEFAULT_ANALYSIS_WORK_PATH),
        )

        # Tools selected in the "Tools" tile; fall back to the ?tool=... url tool.
        # Equivalent to 'odatix analyze --tool <analysis_tool_list>'.
        analysis_tool_list = [t for t in (analysis_tools or []) if t]
        if not analysis_tool_list:
            analysis_tool_list = [tool]

        _prepare_thread = threading.Thread(
            target=_run_check_analysis_settings,
            args=(
                run_config_settings_filename,
                base_path,
                analysis_tool_list,
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

    else:
        global _prepare_status
        message = (
            "Running this type of job from the GUI is not available yet.\n"
            "Your selection is saved: launch it from a terminal."
        )
        _prepare_log_buffer.write(message)
        _prepare_status = {"status": "error", "error": message}
        return {"status": "error", "type": run_mode, "tool": tool, "error": message}
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

# Point the "Choose Targets" button to the current EDA tool
@dash.callback(
    Output({"page": page_path, "action": "choose-targets", "is_link": True}, "href"),
    Output({"page": page_path, "action": "choose-targets"}, "className"),
    Input(f"url_{page_path}", "search"),
)
def update_choose_targets_link(search):
    tool = get_key_from_url(search, "tool") or "vivado"
    run_mode = get_key_from_url(search, "type")
    if run_mode == "analyze":
        return (
            f"/select_targets?tool={quote(tool)}",
            "hidden"
        )
    return (
        f"/select_targets?tool={quote(tool)}",
        "color-button default icon-button tooltip bottom small tooltip"
    )

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
            id={"page": page_path, "action": "choose-targets"},
            icon=icon("gear", className="icon"),
            link="/select_targets",  # href updated from the url by update_choose_targets_link
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
        ui.title_tile("Select architecture configurations to run", id="jobs-config-main-title", buttons=title_buttons, style={"marginTop": "10px", "marginBottom": "10px"}),
        html.Div(id={"page": page_path, "type": "title-div"}, style={"marginTop": "20px"}),
        html.H2("Job Settings", style={"textAlign": "center", "marginBottom": "30px"}),
        html.Div(id="job-settings-form-container", style={"marginBottom": "10px"}),
        dcc.Store(id="job-settings-initial-settings", data=None),
        # html.H2("Targets", style={"textAlign": "center"}),
        # html.Div(id="target-section", style={"marginBottom": "10px"}),
        html.H2("Architectures", id="job-section-heading", style={"textAlign": "center"}),
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

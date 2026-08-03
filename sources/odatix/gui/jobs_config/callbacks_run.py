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

"""Callbacks that actually launch a run: the popup, the background check phase, the
confirmation that prepares the jobs, and the hand-over to the monitor."""

import os
import threading
from urllib.parse import quote

import dash
from dash import ctx, Input, Output, State

import odatix.lib.eda_tools as eda_tools
import odatix.lib.hard_settings as hard_settings
import odatix.lib.pnr_source as pnr_source
from odatix.gui.utils import get_key_from_url, get_workspace
from odatix.lib.parallel_job_handler import daemon_control
from odatix.lib.settings import OdatixSettings
from odatix.lib.utils import AUTO_NB_JOBS_KEYWORD

from odatix.gui.jobs_config import prepare_state
from odatix.gui.jobs_config.checks import start_check, start_prepare
from odatix.gui.jobs_config.common import (
    _checklist_enabled,
    _normalize_session_selector,
    page_path,
)
from odatix.gui.jobs_config.context import _run_context
from odatix.gui.jobs_config.prepare_state import (
    _prepare_progress_bar,
    _report_tool_check_failures,
    _reset_prepare_state,
    _tool_check_state,
)
from odatix.gui.jobs_config.run_popup import _run_popup_body, _run_popup_render_key
from odatix.gui.jobs_config.settings_io import _collect_run_settings, _write_temp_run_settings

#: What the page can run. Every other job type is configured here but started
#: from a terminal.
RUNNABLE_MODES = ("fmax_synthesis", "custom_freq_synthesis", "pnr", "analyze", "simulation", "workflow")

# Open run popup
@dash.callback(
    Output("run-popup", "className"),
    Output("run-popup-opened", "data"),
    Output("run-popup-title", "children"),
    Output("run-popup-render-key", "data", allow_duplicate=True),
    Input({"page": page_path, "action": "run-jobs"}, "n_clicks"),
    prevent_initial_call=True
)
def show_run_popup(n_click):
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict) or not n_click:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    return "overlay-odatix visible", True, "Checking settings...", ""

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
    State("auto-nb-jobs", "value"),
    State("ask_continue", "value"),
    State("exit_when_done", "value"),
    State("log_size_limit", "value"),
    State("analysis-tools", "value"),
    # Live architecture/configuration selection and frequency fields, so the run
    # uses the current (possibly unsaved) page state (written to a temp file).
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "value"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State({"type": "sim-selection", "sim": dash.ALL}, "data"),
    State({"type": "sim-selection", "sim": dash.ALL}, "id"),
    State("override-arch-frequencies", "value"),
    State("use-custom-freq-list", "value"),
    State("target_frequencies", "value"),
    State("use-custom-freq-range", "value"),
    State("from_frequency", "value"),
    State("to_frequency", "value"),
    State("step_frequency", "value"),
    State("lower_bound", "value"),
    State("upper_bound", "value"),
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
    auto_nb_jobs,
    ask_continue,
    exit_when_done,
    log_size_limit,
    analysis_tools,
    switch_values,
    switch_ids,
    preview_values,
    preview_ids,
    sim_selection_values,
    sim_selection_ids,
    override_arch_frequencies,
    use_custom_freq_list,
    target_frequencies,
    use_custom_freq_range,
    from_frequency,
    to_frequency,
    step_frequency,
    lower_bound,
    upper_bound,
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

    if prepare_state._prepare_thread is not None and prepare_state._prepare_thread.is_alive():
        return {
            "status": "running",
            "type": get_key_from_url(search, "type"),
            "tool": get_key_from_url(search, "tool") or "vivado",
        }

    settings = odatix_settings or {}
    run_mode = get_key_from_url(search, "type")
    tool = get_key_from_url(search, "tool") or "vivado"
    flow = get_key_from_url(search, "flow") or None
    # Last step to run, for a flow split into steps (see /choose_eda_tool).
    # Ignored unless it really is one of the flow's steps: an url can be edited
    # by hand, and check_settings() answers an unknown step with sys.exit().
    until_step = get_key_from_url(search, "until") or None
    if until_step is not None and until_step not in eda_tools.get_flow_step_names(
        tool, flow=flow, job_type=run_mode
    ):
        until_step = None

    # arch_path for architecture modes, workflow_path for workflow mode
    run_context = _run_context(search, odatix_settings)
    base_path = run_context["base_path"]
    target_path = settings.get("target_path", OdatixSettings.DEFAULT_TARGET_PATH)
    work_path_root = settings.get("work_path", OdatixSettings.DEFAULT_WORK_PATH)
    # Per-job export destination + options (au fil de l'eau, see prepare_* funcs).
    result_path = settings.get("result_path", OdatixSettings.DEFAULT_RESULT_PATH)
    export_use_benchmark = bool(settings.get("use_benchmark", False))
    export_benchmark_file = settings.get("benchmark_file") or None

    overwrite_enabled = _checklist_enabled(overwrite)
    ask_continue_enabled = _checklist_enabled(ask_continue)
    exit_when_done_enabled = _checklist_enabled(exit_when_done)

    if _checklist_enabled(auto_nb_jobs):
        nb_jobs_val = AUTO_NB_JOBS_KEYWORD
    else:
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
    prepare_state._prepare_synth_type = run_mode
    prepare_state._prepare_runtime_settings = {
        "session": _normalize_session_selector(selected_session),
    }

    # Run with the current (possibly unsaved) page state: collect it and write it
    # to a temporary settings file, used as the run settings file below, without
    # touching the real one. Falls back to the real file if that fails.
    temp_settings_file = None
    try:
        current_settings = _collect_run_settings(
            run_mode,
            run_context["selection_key"],
            switch_values,
            switch_ids,
            preview_values,
            preview_ids,
            overwrite,
            force_single_thread,
            nb_jobs,
            auto_nb_jobs,
            log_size_limit,
            ask_continue,
            exit_when_done,
            override_arch_frequencies,
            use_custom_freq_list,
            target_frequencies,
            use_custom_freq_range,
            from_frequency,
            to_frequency,
            step_frequency,
            lower_bound,
            upper_bound,
            analysis_tools,
            sim_selection_values=sim_selection_values,
            sim_selection_ids=sim_selection_ids,
        )
        temp_settings_file = _write_temp_run_settings(
            run_context["settings_path"],
            current_settings,
            run_mode,
            _checklist_enabled(use_custom_freq_list),
            _checklist_enabled(use_custom_freq_range),
        )
    except Exception:
        temp_settings_file = None
    prepare_state._prepare_temp_settings_file = temp_settings_file

    if run_mode not in RUNNABLE_MODES:
        message = (
            "Running this type of job from the GUI is not available yet.\n"
            "Your selection is saved: launch it from a terminal."
        )
        prepare_state._prepare_log_buffer.write(message)
        prepare_state._prepare_status = {"status": "error", "error": message}
        return {"status": "error", "type": run_mode, "tool": tool, "error": message}

    # Everywhere a path is needed, the workspace knows it: only what this run
    # does differently from what it says is passed here.
    run_options = dict(
        settings_file=temp_settings_file,
        tool=tool,
        flow=flow,
        until=until_step,
        overwrite=overwrite_enabled,
        noask=noask,
        exit_when_done=exit_when_done_enabled,
        log_size_limit=log_size_val,
        nb_jobs=nb_jobs_val,
        check_eda_tool=check_eda_tool,
    )

    if run_mode == "fmax_synthesis":
        run_options["continue_on_error"] = True
    elif run_mode == "pnr":
        # Where each kind of job a place & route can start from keeps its
        # results, under the work directory.
        run_options["source_result_types"] = {
            job_type: {"path": settings.get(f"{job_type}_work_path") or job_type}
            for job_type in pnr_source.SOURCE_JOB_TYPES
        }
    elif run_mode == "analyze":
        # Tools selected in the "Tools" tile; fall back to the ?tool=... url
        # tool. Equivalent to 'odatix analyze --tool <analysis_tool_list>'.
        run_options["tool"] = [t for t in (analysis_tools or []) if t] or [tool]
        # The flow picked on /choose_eda_tool applies to every selected tool.
        run_options["flow"] = [flow] if flow else None

    prepare_state._prepare_thread = threading.Thread(
        target=start_check,
        args=(run_mode, get_workspace(settings)),
        kwargs=run_options,
        daemon=True,
    )
    prepare_state._prepare_thread.start()

    return {
        "status": "checking",
        "type": run_mode,
        "tool": tool,
    }

@dash.callback(
    Output("jobs-config-run-status", "data", allow_duplicate=True),
    Output("run-popup-body", "children"),
    Output("run-popup-render-key", "data"),
    Output("run-popup-progress", "children"),
    Output("run-confirm-btn", "className"),
    Output("run-redirect", "href", allow_duplicate=True),
    Input("run-log-interval", "n_intervals"),
    State("jobs-config-run-status", "data"),
    State("run-popup-opened", "data"),
    State("run-popup-render-key", "data"),
    prevent_initial_call=True,
)
def poll_prepare_log(n_intervals, run_status, run_popup_opened, render_key):
    if not run_status or not run_popup_opened:
        raise dash.exceptions.PreventUpdate

    current_status = run_status.get("status")
    if current_status == "canceled":
        return run_status, "", "", "", "color-button disabled icon-button", dash.no_update

    if prepare_state._prepare_status.get("status") and prepare_state._prepare_status.get("status") != current_status:
        run_status = {**run_status, **prepare_state._prepare_status}
        current_status = run_status.get("status")

    if current_status in ("checking", "checked", "preparing", "prepared", "launched", "error"):
        # The settings are checked and the plan is displayed, but the eda tool
        # check runs in the background: Start only lights up once it passed.
        tool_check = _tool_check_state()
        _report_tool_check_failures(tool_check)
        tool_ready = tool_check is None or tool_check["status"] == "passed"
        button_class = (
            "color-button success icon-button"
            if current_status == "checked" and tool_ready
            else "color-button disabled icon-button"
        )
        redirect_href = dash.no_update
        # Progress of the job-preparation phase (only meaningful once the run
        # is confirmed; the state is reset at the start of every run).
        progress_bar = _prepare_progress_bar() if current_status in ("preparing", "prepared", "launched", "error") else ""
        if current_status == "prepared" and prepare_state._prepare_parallel_jobs is not None:
            should_enqueue = False
            with prepare_state._prepare_enqueue_lock:
                if not prepare_state._prepare_enqueued and prepare_state._prepare_monitor_href is None:
                    prepare_state._prepare_enqueued = True
                    should_enqueue = True

            if should_enqueue:
                try:
                    session_selector = None
                    if isinstance(prepare_state._prepare_runtime_settings, dict):
                        session_selector = _normalize_session_selector(prepare_state._prepare_runtime_settings.get("session"))

                    state, _response = daemon_control.enqueue_parallel_jobs(
                        prepare_state._prepare_parallel_jobs,
                        session=session_selector,
                    )

                    session_id = str(state.get("session_id", "")).strip()
                    session_name = str(state.get("session_name", "")).strip()
                    if session_id:
                        prepare_state._prepare_monitor_href = f"/monitor?session={quote(session_id, safe='')}"
                    elif session_name:
                        prepare_state._prepare_monitor_href = f"/monitor?session={quote(session_name, safe='')}"
                    else:
                        host = str(state.get("host", hard_settings.daemon_default_host))
                        port = int(state.get("port", hard_settings.daemon_default_port))
                        prepare_state._prepare_monitor_href = f"/monitor?host={quote(host, safe='')}&port={port}"
                    run_status = {**run_status, "status": "launched"}
                except Exception as exc:
                    with prepare_state._prepare_enqueue_lock:
                        prepare_state._prepare_enqueued = False
                    run_status = {"status": "error", "error": str(exc)}
                    prepare_state._prepare_messages.add("error", f"Failed to enqueue jobs in daemon session: {exc}")
                    return (
                        run_status,
                        _run_popup_body("error"),
                        _run_popup_render_key("error"),
                        progress_bar,
                        "color-button disabled icon-button",
                        dash.no_update,
                    )

            if prepare_state._prepare_monitor_href is not None:
                redirect_href = prepare_state._prepare_monitor_href

        # The body is rebuilt only when its content changed: it is re-rendered on
        # a timer, and replacing identical children would collapse the expanded
        # sections under the user.
        new_key = _run_popup_render_key(current_status)
        if new_key == render_key:
            body, new_key_output = dash.no_update, dash.no_update
        else:
            body = _run_popup_body(current_status)
            new_key_output = new_key
        return run_status, body, new_key_output, progress_bar, button_class, redirect_href

    raise dash.exceptions.PreventUpdate

@dash.callback(
    Output("jobs-config-run-status", "data", allow_duplicate=True),
    Output("run-popup-body", "children", allow_duplicate=True),
    Output("run-popup-render-key", "data", allow_duplicate=True),
    Output("run-confirm-btn", "className", allow_duplicate=True),
    Input("run-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def cancel_prepare_synthesis(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    prepare_state._prepare_cancel_event.set()
    return {"status": "canceled"}, "", "", "color-button disabled icon-button"


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

    # The Start button is only enabled once the background eda tool check
    # passed; guard the callback too, in case it is triggered anyway.
    tool_check = _tool_check_state()
    if tool_check is not None and tool_check["status"] != "passed":
        raise dash.exceptions.PreventUpdate

    if prepare_state._prepare_exec_thread is not None and prepare_state._prepare_exec_thread.is_alive():
        raise dash.exceptions.PreventUpdate

    prepare_state._prepare_status = {"status": "preparing", "error": None}

    prepare_state._prepare_exec_thread = threading.Thread(
        target=start_prepare,
        daemon=True,
    )
    prepare_state._prepare_exec_thread.start()

    return {**run_status, "status": "preparing"}, "Preparing jobs...", "color-button disabled icon-button"


# Launching a run from the popup navigates to the monitor on purpose (with the
# current, possibly unsaved, config): tell the unsaved-changes guard to skip its
# "leave without saving?" prompt for that navigation.
dash.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks) {
            window.__odatixSkipUnsavedGuard = true;
        }
        return "";
    }
    """,
    Output("unsaved-guard-bypass", "data"),
    Input("run-confirm-btn", "n_clicks"),
    prevent_initial_call=True,
)

# Restore the guard if the run does not end up navigating away (error/canceled),
# so unsaved changes are protected again.
dash.clientside_callback(
    """
    function(run_status) {
        var status = run_status && run_status.status;
        if (status === "error" || status === "canceled") {
            window.__odatixSkipUnsavedGuard = false;
        }
        return "";
    }
    """,
    Output("unsaved-guard-bypass", "data", allow_duplicate=True),
    Input("jobs-config-run-status", "data"),
    prevent_initial_call=True,
)

# Point the "Choose Targets" button to the current EDA tool
@dash.callback(
    Output({"page": page_path, "action": "choose-targets", "is_link": True}, "href"),
    Output({"page": page_path, "action": "choose-targets"}, "className"),
    Input(f"url_{page_path}", "search"),
)
def update_choose_targets_link(search):
    tool = get_key_from_url(search, "tool") or "vivado"
    run_mode = get_key_from_url(search, "type")
    if run_mode in ("fmax_synthesis", "custom_freq_synthesis", "pnr"):
        return (
            f"/select_targets?tool={quote(tool)}",
            "color-button default icon-button tooltip bottom small tooltip"
        )
    else:
        return (
            f"/select_targets?tool={quote(tool)}",
            "hidden"
        )

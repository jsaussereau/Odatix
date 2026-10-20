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
from dash import ctx, html, Input, Output, State

import odatix.lib.eda_tools as eda_tools
from odatix.gui.utils import get_key_from_url, get_workspace
from odatix.lib.utils import AUTO_NB_JOBS_KEYWORD

from odatix.gui.jobs_config import prepare_state
from odatix.gui.jobs_config.checks import start_check, start_prepare
from odatix.gui.jobs_config.common import (
    _checklist_enabled,
    _normalize_session_selector,
    page_path,
    rerun_step_names,
)
from odatix.gui.jobs_config.context import _run_context
from odatix.gui.jobs_config.prepare_state import (
    _prepare_progress_bar,
    _report_tool_check_failures,
    _reset_prepare_state,
    _tool_check_state,
)
from odatix.gui.jobs_config.callbacks_config import run_scope_tags
from odatix.gui.jobs_config.run_popup import (
    TITLE_CHECKING,
    _can_start,
    _popup_context,
    _popup_title,
    _run_popup_body,
    _run_popup_render_key,
)
from odatix.run.flows import flow_for
from odatix.gui.jobs_config.settings_io import _collect_run_settings, _write_temp_run_settings
from odatix.gui.page_scope import page_callback

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "jobs_config"

#: What the page can run. Every other job type is configured here but started
#: from a terminal.
RUNNABLE_MODES = ("fmax_synthesis", "custom_freq_synthesis", "pnr", "analyze", "simulation", "workflow")

# Open run popup
@page_callback(PAGE_SCOPE,
    Output("run-popup", "className"),
    Output("run-popup-opened", "data"),
    Output("run-popup-title", "children"),
    Output("run-popup-render-key", "data", allow_duplicate=True),
    Output("run-log-interval", "disabled"),
    Output("run-popup-context", "children"),
    Output("run-popup-body", "children", allow_duplicate=True),
    Output("run-confirm-btn", "className", allow_duplicate=True),
    Input({"page": page_path, "action": "run-jobs"}, "n_clicks"),
    State(f"url_{page_path}", "search"),
    State("analysis-tools", "value"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def show_run_popup(n_click, search, analysis_tools, odatix_settings):
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict) or not n_click:
        raise dash.exceptions.PreventUpdate

    # The popup is polled only while it is open. What a previous run left in
    # it is cleared rather than shown again under the new title.
    return (
        "overlay-odatix visible", True, TITLE_CHECKING, "", False,
        _popup_context(run_context_tags(search, analysis_tools, odatix_settings)),
        html.Div(html.Div("Checking settings…", className="jobs-plan-placeholder"), className="jobs-plan"),
        "color-button disabled icon-button",
    )

# Popup close
@dash.callback(
    Output("run-popup", "className", allow_duplicate=True),
    Output("run-popup-opened", "data", allow_duplicate=True),
    Output("run-log-interval", "disabled", allow_duplicate=True),
    Input("run-cancel-btn", "n_clicks"),
    prevent_initial_call=True
)
def close_run_popup(n):
    return "overlay-odatix", False, True


def run_context_tags(search, analysis_tools=None, odatix_settings=None):
    """
    What the run popup says the run runs with, under its title: the eda tool,
    its flow and the step it stops at (as the summary strip says them), the
    targets, and the directory the jobs work in.
    """
    run_mode = get_key_from_url(search, "type")
    tags = []
    if run_mode == "analyze":
        tools = [tool for tool in (analysis_tools or []) if tool] or [get_key_from_url(search, "tool")]
        tags.append(", ".join(eda_tools.get_tool_label(tool) for tool in tools if tool))
        tags.extend(run_scope_tags(search)[1:])
    else:
        tags.extend(run_scope_tags(search))
    try:
        workspace = get_workspace(odatix_settings or {})
    except Exception:
        return tags
    tool = get_key_from_url(search, "tool")
    if tool and run_mode in ("fmax_synthesis", "custom_freq_synthesis", "pnr"):
        try:
            targets = list(workspace.targets.get(tool).enabled_names())
        except Exception:
            targets = []
        if len(targets) == 1:
            tags.append("target " + targets[0])
        elif targets:
            tags.append("{0} targets".format(len(targets)))
    try:
        work_path = flow_for(run_mode).work_path(workspace)
        root = getattr(workspace, "root", None) or os.getcwd()
        relative = os.path.relpath(os.path.realpath(work_path), os.path.realpath(root))
        tags.append("in " + (work_path if relative.startswith("..") else relative))
    except Exception:
        pass
    return tags

@page_callback(PAGE_SCOPE,
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
    State("rerun-from", "value"),
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
    State({"page": page_path, "action": "session-access"}, "value"),
    State({"page": page_path, "action": "session-name"}, "value"),
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
    rerun_from,
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
    session_access,
    session_name,
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
    # First step to do again even where it is done ("--rerun-from"), checked the
    # same way: only a step this run goes through can be re-run.
    rerun_from = rerun_from or None
    if rerun_from is not None and rerun_from not in rerun_step_names(search):
        rerun_from = None

    run_context = _run_context(search, odatix_settings)

    overwrite_enabled = _checklist_enabled(overwrite)
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
        # A new session takes the name typed for it, if any: enqueueing into
        # a session that does not exist starts it under that name (as -S does).
        "session": _normalize_session_selector(selected_session) or _normalize_session_selector(session_name),
        "session_access": session_access or None,
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
        rerun_from=rerun_from,
        overwrite=overwrite_enabled,
        noask=noask,
        exit_when_done=exit_when_done_enabled,
        log_size_limit=log_size_val,
        nb_jobs=nb_jobs_val,
        check_eda_tool=check_eda_tool,
    )

    # Where a place & route finds its sources is the workspace's business: the
    # run works it out (see odatix.run.flows.PnrFlow), as it does for a command.
    # An fmax search stops at its first failed synthesis, as "odatix fmax" does
    # without --continue-on-error: the interface runs what the command runs.
    if run_mode == "analyze":
        # Tools selected in the "Tools" tile; fall back to the ?tool=... url
        # tool. Equivalent to 'odatix analyze --tool <analysis_tool_list>'.
        run_options["tool"] = [t for t in (analysis_tools or []) if t] or [tool]
        # The flow picked on /choose_eda_tool is a flow of the tool it was
        # picked for ("odatix analyze --flow tool:flow"), the other selected
        # tools running their default flow.
        if flow and tool in run_options["tool"]:
            run_options["flow"] = [tool + ":" + flow]
        else:
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
    Output("run-popup-title", "children", allow_duplicate=True),
    Output("run-log-interval", "disabled", allow_duplicate=True),
    Input("run-log-interval", "n_intervals"),
    State("jobs-config-run-status", "data"),
    State("run-popup-opened", "data"),
    State("run-popup-render-key", "data"),
    State("run-popup-title", "children"),
    prevent_initial_call=True,
)
def poll_prepare_log(n_intervals, run_status, run_popup_opened, render_key, title):
    if not run_status or not run_popup_opened:
        raise dash.exceptions.PreventUpdate

    def new_title(status):
        text = _popup_title(status)
        return dash.no_update if text == title else text

    current_status = run_status.get("status")
    if current_status == "canceled":
        return run_status, "", "", "", "color-button disabled icon-button", dash.no_update, dash.no_update, dash.no_update

    # D-07: this click was refused, a check started earlier still running. What
    # that check reports is about another click: saying it here showed "No job
    # found" for a selection that holds some.
    if current_status == "running":
        new_key = _run_popup_render_key(current_status)
        if new_key == render_key:
            raise dash.exceptions.PreventUpdate
        return (
            run_status, _run_popup_body(current_status), new_key, "",
            "color-button disabled icon-button", dash.no_update, new_title(current_status), dash.no_update,
        )

    if prepare_state._prepare_status.get("status") and prepare_state._prepare_status.get("status") != current_status:
        run_status = {**run_status, **prepare_state._prepare_status}
        current_status = run_status.get("status")

    if current_status not in ("checking", "checked", "nothing", "preparing", "prepared", "launched", "error"):
        raise dash.exceptions.PreventUpdate

    # The settings are checked and the plan is displayed, but the eda tool
    # check runs in the background: Start only lights up once it passed, and
    # only when there is something to start.
    _report_tool_check_failures(_tool_check_state())
    button_class = (
        "color-button success icon-button"
        if _can_start(current_status)
        else "color-button disabled icon-button"
    )
    # Progress of the job-preparation phase (only meaningful once the run
    # is confirmed; the state is reset at the start of every run).
    progress_bar = _prepare_progress_bar() if current_status in ("preparing", "prepared", "launched", "error") else ""

    # The jobs are in a session (see checks.start_prepare): off to the
    # monitor, and the popup stops being polled.
    redirect_href = dash.no_update
    stop_polling = dash.no_update
    if current_status == "launched" and prepare_state._prepare_monitor_href is not None:
        redirect_href = prepare_state._prepare_monitor_href
        stop_polling = True

    # The body is rebuilt only when its content changed: it is re-rendered on
    # a timer, and replacing identical children would collapse the expanded
    # sections under the user.
    new_key = _run_popup_render_key(current_status)
    if new_key == render_key:
        body, new_key_output = dash.no_update, dash.no_update
    else:
        body = _run_popup_body(current_status)
        new_key_output = new_key
    return (
        run_status, body, new_key_output, progress_bar, button_class, redirect_href,
        new_title(current_status), stop_polling,
    )

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
    # passed, and when there is something to run; guard the callback too, in
    # case it is triggered anyway (the keyboard reaches a disabled-looking button).
    if not _can_start("checked"):
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


# Point the "Choose Targets" button to the current EDA tool, and the back arrow
# to the page this one was opened from.
@dash.callback(
    Output({"page": page_path, "action": "choose-targets", "is_link": True}, "href"),
    Output({"page": page_path, "action": "choose-targets"}, "className"),
    Output("jobs-config-back", "href"),
    Input(f"url_{page_path}", "search"),
)
def update_choose_targets_link(search):
    tool = get_key_from_url(search, "tool") or "vivado"
    run_mode = get_key_from_url(search, "type")
    # The targets page leads back here, with the same job type, tool, flow
    # and step, rather than to the choice of a job type.
    targets_href = "/select_targets?tool={0}&back={1}".format(
        quote(tool, safe=""), quote(page_path + (search or ""), safe="")
    )
    if run_mode in ("fmax_synthesis", "custom_freq_synthesis", "pnr"):
        return (
            targets_href,
            "color-button default icon-button tooltip bottom small tooltip",
            back_href(search),
        )
    else:
        return (
            targets_href,
            "hidden",
            back_href(search),
        )


def back_href(search):
    """
    Where the back arrow of the page leads: the choice of a tool for the job
    types that run one (where the tool, flow and step were picked), the choice
    of a job type otherwise.
    """
    run_mode = get_key_from_url(search, "type")
    if run_mode in ("fmax_synthesis", "custom_freq_synthesis", "pnr", "analyze"):
        return "/choose_eda_tool?type=" + quote(run_mode, safe="")
    return "/choose_job_type"

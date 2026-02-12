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
from dash import html, dcc, Input, Output, State, ctx, ALL
from typing import Optional#, Literal
import requests
from dash.exceptions import PreventUpdate
from dash import no_update

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url, ansi_to_html_spans
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings

page_path = "/monitor"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Monitor',
    update_title='Odatix - Monitor',
    name='monitor',
    order=6,
)

######################################
# API requests
######################################

DEFAULT_PORT = 8000
DEFAULT_API_URL = f"http://127.0.0.1:{DEFAULT_PORT}"

def _base_url(url: Optional[str]) -> str:
    if not url:
        return DEFAULT_API_URL
    return str(url).rstrip("/")

def _api_get(url: str, path: str):
    r = requests.get(_base_url(url) + path, timeout=0.4)
    r.raise_for_status()
    return r.json()

def _api_get_slow(url: str, path: str, timeout: float = 2.0):
    r = requests.get(_base_url(url) + path, timeout=float(timeout))
    r.raise_for_status()
    return r.json()

def _api_post(url: str, path: str, params: Optional[dict] = None):
    r = requests.post(_base_url(url) + path, params=params or {}, timeout=0.6)
    r.raise_for_status()
    if r.headers.get("content-type", "").startswith("application/json"):
        return r.json()
    return {"ok": True}


######################################
# UI Components
######################################

def monitor_task(
    name: str,
    status: str,
    runtime: str,
    progress: int,
    task_id: int = 0,
    selected: bool = False,
):
    status_norm = str(status).lower().strip()

    return html.Div(
        className="monitor-task-container" + (" selected" if selected else ""),
        id={"type": "task-container", "task_id": task_id},
        children=[
            html.Div(
                className="monitor-task " + status,
                id={"type": "task-row", "task_id": task_id},
                children=[
                    html.Div(
                        f"{name}",
                        className="monitor-task-name",
                        id={"type": "task-select", "task_id": task_id},
                        n_clicks=0,
                    ),
                    html.Div(
                        children=[
                            html.Div(
                                id={"type": "task-progress-bar", "task_id": task_id},
                                style={"width": f"{progress}%"},
                                className="monitor-task-progress-bar",
                            ),
                        ],
                        className="monitor-task-progress",
                    ),
                    html.Div(
                        f"{progress} %",
                        id={"type": "task-progress-text", "task_id": task_id},
                        className="monitor-task-progress-text",
                    ),
                    html.Div(
                        f"{runtime}",
                        id={"type": "task-runtime", "task_id": task_id},
                        className=f"monitor-task-runtime",
                    ),
                    html.Div(
                        f"{status}",
                        id={"type": "task-status", "task_id": task_id},
                        className=f"monitor-task-status {status}",
                    ),
                    html.Div(
                        children=[
                            html.Div(
                                id={"type": "task-start-wrap", "task_id": task_id},
                                children=[
                                    ui.icon_button(
                                        id={"type": "task-start", "task_id": task_id},
                                        icon=icon("play", className="icon", offset=True),
                                        color="success",
                                        multiline=True,
                                        tooltip="Start task",
                                        tooltip_options="top small",
                                    ),
                                ],
                            ),
                            html.Div(
                                id={"type": "task-pause-wrap", "task_id": task_id},
                                children=[
                                    ui.icon_button(
                                        id={"type": "task-pause", "task_id": task_id},
                                        icon=icon("pause", className="icon"),
                                        color="primary",
                                        multiline=True,
                                        tooltip="Pause task",
                                        tooltip_options="top small",
                                    ),
                                ],
                            ),
                            html.Div(
                                id={"type": "task-stop-wrap", "task_id": task_id},
                                children=[
                                    ui.icon_button(
                                        id={"type": "task-stop", "task_id": task_id},
                                        icon=icon("cross", className="icon"),
                                        color="caution",
                                        multiline=True,
                                        tooltip="Kill task",
                                        tooltip_options="top small",
                                    ),
                                ],
                            ),
                        ],
                        className="monitor-task-button-container",
                    )
                ]
            ),
        ]
    )


######################################
# Callbacks
######################################

@dash.callback(
    Output("monitor-snapshot", "data"),
    Output("monitor-logs", "data", allow_duplicate=True),
    Output("monitor-error", "data"),
    Input("monitor-refresh", "n_intervals"),
    State("monitor-snapshot", "data"),
    State("monitor-selected-job", "data"),
    State("monitor-logs", "data"),
    prevent_initial_call=True,
)
def _poll_status(_n, previous_snapshot, selected_job_id, logs_state):
    try:
        # 1 request per tick: jobs + optional log deltas for selected job.
        path = "/status"

        job_id = None
        try:
            if selected_job_id is not None:
                job_id = int(selected_job_id)
        except Exception:
            job_id = None

        offset_i = None
        if job_id is not None and isinstance(logs_state, dict) and logs_state.get("job_id") == job_id:
            offset = logs_state.get("total_lines", 0)
            try:
                offset_i = max(0, int(offset))
            except Exception:
                offset_i = 0

        if job_id is not None and offset_i is not None:
            path = f"/status?logs_job_id={job_id}&logs_offset={offset_i}&logs_limit=500"

        snap = _api_get(DEFAULT_API_URL, path)

        # Merge returned deltas into the log store.
        new_logs_state = no_update
        if job_id is not None and offset_i is not None and isinstance(snap, dict):
            logs_any = snap.get("logs")
            logs = logs_any if isinstance(logs_any, dict) else {}
            new_lines_any = logs.get("lines")
            new_lines = new_lines_any if isinstance(new_lines_any, list) else []
            if new_lines:
                total = logs.get("total_lines", offset_i + len(new_lines))
                try:
                    total_i = int(total)
                except Exception:
                    total_i = offset_i + len(new_lines)

                merged = list((logs_state or {}).get("lines") or []) + list(map(str, new_lines))
                new_logs_state = {"job_id": job_id, "lines": merged, "total_lines": total_i}

        return snap, new_logs_state, ""
    except Exception as e:
        # Keep the last known state so the UI does not flicker
        if previous_snapshot is None:
            return {}, no_update, str(e)
        return previous_snapshot, no_update, str(e)


@dash.callback(
    Output("monitor-container", "children"),
    Output("monitor-job-ids", "data"),
    Input("monitor-snapshot", "data"),
    State("monitor-job-ids", "data"),
    State("monitor-selected-job", "data"),
)   
def _sync_job_list(snapshot, previous_job_ids, selected_job):
    if not isinstance(snapshot, dict):
        raise PreventUpdate

    jobs = snapshot.get("jobs")
    if not isinstance(jobs, list):
        raise PreventUpdate

    job_ids = []
    for job in jobs:
        if isinstance(job, dict):
            job_ids.append(job.get("id"))

    # Only rebuild the task components if the job list changed.
    if isinstance(previous_job_ids, list) and job_ids == previous_job_ids:
        return no_update, no_update

    children = []
    for job in jobs:
        if not isinstance(job, dict):
            continue

        name = job.get("display_name") or f"job{job.get('id', '')}"
        status = str(job.get("status") or "unknown")

        progress_val = job.get("progress", 0)
        try:
            progress = int(round(float(progress_val)))
        except Exception:
            progress = 0
        progress = max(0, min(100, progress))
        runtime = str(job.get("elapsed_time") or "--:--:--")
        task_id = job.get("id", 0)
        children.append(
            monitor_task(
                name=name, 
                status=status,
                runtime=runtime,
                progress=progress,
                task_id=task_id,
                selected=(task_id == selected_job)
            )
        )

    return children, job_ids


@dash.callback(
    Output("monitor-selected-job", "data"),
    Input({"type": "task-select", "task_id": ALL}, "n_clicks"),
    State("monitor-selected-job", "data"),
    prevent_initial_call=True,
)
def _select_job_from_click(_row_clicks, selected_job):
    if not ctx.triggered:
        raise PreventUpdate

    # Ignore triggers caused by re-render/component list changes.
    prop_id = ctx.triggered[0].get("prop_id")
    if not prop_id:
        raise PreventUpdate
    triggered_value = ctx.inputs.get(prop_id)
    try:
        if triggered_value is None or int(triggered_value) <= 0:
            raise PreventUpdate
    except PreventUpdate:
        raise
    except Exception:
        raise PreventUpdate

    # If the user clicked the task name, select that job for the Dash view.
    triggered = ctx.triggered_id
    if isinstance(triggered, dict) and triggered.get("type") == "task-select":
        task_id = triggered.get("task_id")
        if task_id is None:
            raise PreventUpdate
        try:
            return int(task_id)
        except Exception:
            raise PreventUpdate

    # Fallback: keep current selection
    raise PreventUpdate


@dash.callback(
    Output({"type": "task-container", "task_id": ALL}, "className"),
    Input("monitor-selected-job", "data"),
    State("monitor-job-ids", "data"),
    prevent_initial_call=True,
)
def _highlight_selected(selected_job, job_ids):
    if not isinstance(job_ids, list):
        raise PreventUpdate
    try:
        selected_i = int(selected_job) if selected_job is not None else None
    except Exception:
        selected_i = None

    class_names = []
    for job_id in job_ids:
        is_selected = selected_i is not None and job_id == selected_i
        class_names.append("monitor-task-container" + (" selected" if is_selected else ""))
    return class_names


@dash.callback(
    Output({"type": "task-row", "task_id": ALL}, "className"),
    Output({"type": "task-progress-bar", "task_id": ALL}, "style"),
    Output({"type": "task-progress-text", "task_id": ALL}, "children"),
    Output({"type": "task-runtime", "task_id": ALL}, "children"),
    Output({"type": "task-status", "task_id": ALL}, "children"),
    Output({"type": "task-status", "task_id": ALL}, "className"),
    Output({"type": "task-start-wrap", "task_id": ALL}, "style"),
    Output({"type": "task-pause-wrap", "task_id": ALL}, "style"),
    Output({"type": "task-stop-wrap", "task_id": ALL}, "style"),
    Input("monitor-snapshot", "data"),
    State("monitor-job-ids", "data"),
)
def _update_tasks(snapshot, job_ids):
    if not isinstance(snapshot, dict):
        raise PreventUpdate
    if not isinstance(job_ids, list) or not job_ids:
        raise PreventUpdate

    jobs = snapshot.get("jobs")
    if not isinstance(jobs, list):
        raise PreventUpdate

    by_id = {}
    for job in jobs:
        if isinstance(job, dict) and "id" in job:
            by_id[job["id"]] = job

    row_class = []
    bar_style = []
    progress_text = []
    runtime_text = []
    status_text = []
    status_class = []
    start_style = []
    pause_style = []
    stop_style = []

    for job_id in job_ids:
        job = by_id.get(job_id, {})
        status = str(job.get("status") or "unknown")
        status_norm = status.lower().strip()

        progress_val = job.get("progress", 0)
        try:
            progress = int(round(float(progress_val)))
        except Exception:
            progress = 0
        progress = max(0, min(100, progress))

        runtime = str(job.get("elapsed_time") or "--:--:--")

        row_class.append("monitor-task " + status)
        bar_style.append({"width": f"{progress}%"})
        progress_text.append(f"{progress} %")
        runtime_text.append(runtime)
        status_text.append(status)
        status_class.append(f"monitor-task-status {status}")

        # Button visibility rules
        show_start = status_norm in ("queued", "paused")
        show_pause = status_norm in ("running", "starting")
        show_stop = status_norm in ("queued", "paused", "running", "starting")

        start_style.append({"display": "block"} if show_start else {"display": "none"})
        pause_style.append({"display": "block"} if show_pause else {"display": "none"})
        stop_style.append({"display": "block"} if show_stop else {"display": "none"})

    return (
        row_class,
        bar_style,
        progress_text,
        runtime_text,
        status_text,
        status_class,
        start_style,
        pause_style,
        stop_style,
    )


@dash.callback(
    Output("monitor-selected-job", "data", allow_duplicate=True),
    Input("monitor-snapshot", "data"),
    State("monitor-selected-job", "data"),
    prevent_initial_call=True,
)
def _init_selected_job(snapshot, selected_job):
    # Pick a default only once; afterwards Dash selection is independent.
    if selected_job is not None:
        raise PreventUpdate
    if not isinstance(snapshot, dict):
        raise PreventUpdate

    handler = snapshot.get("handler")
    if not isinstance(handler, dict):
        raise PreventUpdate

    idx = handler.get("selected_job_index")
    if idx is None:
        raise PreventUpdate
    try:
        return int(idx)
    except Exception:
        raise PreventUpdate


@dash.callback(
    Output("monitor-logs", "data"),
    Input("monitor-selected-job", "data"),
    State("monitor-logs", "data"),
    prevent_initial_call=False,
)
def _fetch_full_log_on_selection(selected_job_id, current_logs):
    if selected_job_id is None:
        raise PreventUpdate

    try:
        job_id = int(selected_job_id)
    except Exception:
        raise PreventUpdate

    # Full log for this job (server supports logs_limit=-1)
    snap = _api_get_slow(DEFAULT_API_URL, f"/status?logs_job_id={job_id}&logs_offset=0&logs_limit=-1")
    logs_any = snap.get("logs") if isinstance(snap, dict) else None
    logs = logs_any if isinstance(logs_any, dict) else {}
    lines_any = logs.get("lines")
    lines = lines_any if isinstance(lines_any, list) else []
    total = logs.get("total_lines", len(lines))
    try:
        total_i = int(total)
    except Exception:
        total_i = len(lines)

    return {
        "job_id": job_id,
        "lines": list(map(str, lines)),
        "total_lines": total_i,
    }

@dash.callback(
    Output("monitor-log-container", "className"),
    Output("monitor-container", "className"),
    Input("config-layout-dropdown", "value"),
)
def _update_log_layout(layout_value):
    log_classes = "tile title monitor-log-container"
    container_classes = "tile title monitor-container"
    if layout_value == "split":
        log_classes += " split"
        container_classes += " split"
    elif layout_value == "log_view":
        log_classes += " log_view"
        container_classes += " log_view"
    else:
        log_classes += " normal"
        container_classes += " normal"
    return log_classes, container_classes

@dash.callback(
    Output("monitor-log", "children"),
    Output("monitor-status", "children"),
    Output("monitor-main-container", "className"),
    Output("monitor-error-container", "className"),
    Input("monitor-logs", "data"),
    Input("monitor-error", "data"),
    State(f"url_{page_path}", "search"),
)
def _render_logs(logs_state, error_message, search):
    if not isinstance(logs_state, dict):
        logs_state = {}
    lines_any = logs_state.get("lines")
    lines = lines_any if isinstance(lines_any, list) else []
    lines = [str(line).rstrip("\n") for line in lines]

    text = "\n".join(lines)
    status = ""
    main_class_name = "visible"
    error_class_name = "hidden"

    if error_message: 
        text = ""
        # status = f"API error: {error_message}\n\n" + text$
        port = get_key_from_url(search, "port")
        if not port:
            port = DEFAULT_PORT
        status = f"Could not find any job monitor running on port {port}"
        main_class_name = "hidden"
        error_class_name = "visible"
    return ansi_to_html_spans(text), status, main_class_name, error_class_name


@dash.callback(
    Output("monitor-last-action", "data"),
    Input({"type": "task-start", "task_id": ALL}, "n_clicks"),
    Input({"type": "task-pause", "task_id": ALL}, "n_clicks"),
    Input({"type": "task-stop", "task_id": ALL}, "n_clicks"),
    Input("monitor-stop-all", "n_clicks"),
    prevent_initial_call=True,
)
def _task_action(_start_clicks, _pause_clicks, _stop_clicks, stop_all_clicks):
    if not ctx.triggered:
        raise PreventUpdate

    # Dash will also trigger this callback when components are added/removed
    # during polling refreshes. Only treat it as an action on a real click.
    prop_id = ctx.triggered[0].get("prop_id")
    if not prop_id:
        raise PreventUpdate
    triggered_value = ctx.inputs.get(prop_id)
    try:
        if triggered_value is None or int(triggered_value) <= 0:
            raise PreventUpdate
    except PreventUpdate:
        raise
    except Exception:
        raise PreventUpdate

    triggered = ctx.triggered_id
    if triggered == "monitor-stop-all":
        try:
            _api_post(DEFAULT_API_URL, "/shutdown")
            return {"ok": True, "action": "shutdown"}
        except Exception as e:
            return {"ok": False, "action": "shutdown", "error": str(e)}

    if not isinstance(triggered, dict):
        raise PreventUpdate

    action_type = triggered.get("type")
    task_id = triggered.get("task_id")
    if task_id is None:
        return {"ok": False, "error": "Missing task_id"}
    try:
        job_id = int(task_id)
    except Exception:
        return {"ok": False, "error": f"Invalid task_id: {task_id}"}

    try:
        if action_type == "task-start":
            _api_post(DEFAULT_API_URL, f"/jobs/{job_id}/start")
            return {"ok": True, "action": "start", "job_id": job_id}
        if action_type == "task-pause":
            _api_post(DEFAULT_API_URL, f"/jobs/{job_id}/pause")
            return {"ok": True, "action": "pause", "job_id": job_id}
        if action_type == "task-stop":
            _api_post(DEFAULT_API_URL, f"/jobs/{job_id}/kill")
            return {"ok": True, "action": "kill", "job_id": job_id}

        return {"ok": False, "error": f"Unknown action type: {action_type}"}
    except Exception as e:
        return {"ok": False, "action": action_type, "job_id": job_id, "error": str(e)}



######################################
# Layout
######################################

title_buttons = html.Div(
    children=[
        dcc.Dropdown(
            id="config-layout-dropdown", 
            options=[
                {"label": "Normal Layout", "value": "normal"},
                {"label": "Split Layout", "value": "split"},
                {"label": "Log View Layout", "value": "log_view"},
            ],
            value="normal",
            clearable=False,
            style={"width": "155px", "marginRight": "10px"},
        ),
        ui.icon_button(
            id="monitor-stop-all",
            icon=icon("cross", className="icon"),
            color="caution",
            multiline=True,
            tooltip="Kill all tasks and exit monitor",
        ),
    ],
    className="inline-flex-buttons",
)         

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        html.Div(
            ui.title_tile(text="Monitor", buttons=title_buttons, tooltip="Pilot ParallelJobHandler via REST API"),
            style={"marginTop": "20px", "marginLeft": "-13px", "marginBottom": "10px"},
        ),
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(
                            children=[],
                            id="monitor-status",
                            className="tile title error-message ",
                        ),

                    ],
                    className="tiles-container config",
                ),
            ],
            id="monitor-error-container",
            className="hidden",
        ),
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(),
                        html.Div(
                            children=[],
                            id="monitor-container",
                            className="tile title",
                        ),

                    ],
                    className="tiles-container config",
                ),
                html.Div(
                    children=[
                        html.Div(),
                        html.Div(),
                        html.Div(
                            children=[
                                html.H3("Log output"),
                                html.Pre(id="monitor-log", className="monitor-log"),
                            ],
                            className="tile title monitor-log-container",
                            id="monitor-log-container",
                        ),
                    ],
                    className="tiles-container config",
                ),
            ],
            id="monitor-main-container",
            className="hidden",
        ),
        dcc.Interval(id="monitor-refresh", interval=500, n_intervals=0),
        dcc.Store(id="monitor-snapshot", data=None),
        dcc.Store(id="monitor-error", data=""),
        dcc.Store(id="monitor-last-action", data=None),
        dcc.Store(id="monitor-selected-job", data=0),
        dcc.Store(id="monitor-logs", data=None),
        dcc.Store(id="monitor-job-ids", data=[]),
    ],
    className="page-content",
    style={
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

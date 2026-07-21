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
import socket
from dash.exceptions import PreventUpdate
from dash import no_update

from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url, ansi_to_html_spans
import odatix.gui.ui_components as ui
import odatix.lib.hard_settings as hard_settings
from odatix.lib.parallel_job_handler import daemon_control

page_path = "/monitor"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Monitor',
    update_title='Odatix - Monitor',
    name='Monitor',
    order=6,
)

######################################
# API requests
######################################

DEFAULT_HOST = hard_settings.daemon_default_host
DEFAULT_PORT = hard_settings.daemon_default_port

# Status buckets, shared by filtering, KPI counting and sorting.
RUNNING_STATUSES = ("running", "starting", "exporting")
QUEUED_STATUSES = ("queued", "paused")
DONE_STATUSES = ("success",)
FAILED_STATUSES = ("failed", "killed", "canceled")

# Sort priority when sorting by status (most "active" first).
_STATUS_SORT_PRIORITY = {
    "running": 0,
    "starting": 1,
    "exporting": 2,
    "paused": 3,
    "queued": 4,
    "success": 5,
    "failed": 6,
    "killed": 7,
    "canceled": 8,
}


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return text


def _parse_optional_port(value: Optional[str]) -> Optional[int]:
    value = _normalize_optional_str(value)
    if value is None:
        return None
    try:
        port = int(value)
    except Exception as e:
        raise ValueError(f"Invalid port: {value}") from e
    if port <= 0 or port > 65535:
        raise ValueError(f"Invalid port: {value}")
    return port


def _monitor_query(search: Optional[str]) -> dict:
    host = _normalize_optional_str(get_key_from_url(search, "host"))
    session = _normalize_optional_str(get_key_from_url(search, "session"))
    if session is None:
        # CLI compatibility: `-S` short option represented in URL.
        session = _normalize_optional_str(get_key_from_url(search, "S"))

    # Backward compatibility: old monitor links only provided `?port=...`.
    port = _parse_optional_port(get_key_from_url(search, "port"))

    return {
        "host": host,
        "port": port,
        "session": session,
    }


def _pick_session_value(daemons, selector: Optional[str]) -> Optional[str]:
    selector = _normalize_optional_str(selector)
    if selector is None:
        return None

    def _value_from_daemon(entry):
        session_id = _normalize_optional_str(entry.get("session_id"))
        if session_id is not None:
            return session_id
        session_name = _normalize_optional_str(entry.get("session_name"))
        if session_name is not None:
            return session_name
        return None

    exact = []
    prefix = []
    for daemon in daemons:
        value = _value_from_daemon(daemon)
        if value is None:
            continue

        value_lower = value.lower()
        selector_lower = selector.lower()
        if value_lower == selector_lower:
            exact.append(value)
        elif value_lower.startswith(selector_lower):
            prefix.append(value)

    if len(exact) == 1:
        return exact[0]
    if len(prefix) == 1:
        return prefix[0]
    return None


def _query_key(query: dict) -> str:
    host = query.get("host")
    port = query.get("port")
    session = query.get("session")
    return f"host={host}|port={port}|session={session}"


def _resolve_daemon_target(
    search: Optional[str],
    current_daemon_state: Optional[dict] = None,
    session_override: Optional[str] = None,
) -> dict:
    query = _monitor_query(search)

    session_override = _normalize_optional_str(session_override)
    if session_override is not None:
        # When dropdown selection is explicit, use session resolution mode.
        query["session"] = session_override
        query["host"] = None
        query["port"] = None

    key = _query_key(query)

    if isinstance(current_daemon_state, dict):
        if current_daemon_state.get("query_key") == key and current_daemon_state.get("base_url"):
            return current_daemon_state

    try:
        state = daemon_control._resolve_state_for_attach_or_stop(
            host=query.get("host"),
            port=query.get("port"),
            session=query.get("session"),
        )
    except daemon_control.MultipleDaemonsError:
        # Default monitor behavior in GUI: when several sessions exist and no
        # explicit selector is provided, attach to the first discovered one.
        if query.get("session") is None and query.get("host") is None and query.get("port") is None:
            daemons = daemon_control.list_daemons()
            if len(daemons) == 0:
                raise
            state = daemons[0]
        else:
            raise

    host = str(state.get("host", query.get("host") or DEFAULT_HOST))
    port = int(state.get("port", query.get("port") or DEFAULT_PORT))
    session = (
        state.get("session")
        or state.get("session_id")
        or state.get("session_name")
        or query.get("session")
        or ""
    )

    return {
        "query_key": key,
        "host": host,
        "port": port,
        "session": str(session),
        "session_name": str(state.get("session_name", "")),
        "session_id": str(state.get("session_id", "")),
        "base_url": f"http://{host}:{port}",
    }


def _local_addresses():
    """Return the set of IP addresses that refer to the local machine."""
    addresses = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}
    try:
        hostname = socket.gethostname()
        addresses.add(hostname)
        for info in socket.getaddrinfo(hostname, None):
            addresses.add(info[4][0])
    except Exception:
        pass
    return addresses


def _is_local_host(host) -> bool:
    """Whether `host` points at the local machine (so its directories are openable)."""
    if host is None:
        return False
    host = str(host).strip().lower()
    if host == "":
        return False
    return host in _local_addresses()


def _format_monitor_error(error, daemon_state: Optional[dict] = None):
    if isinstance(error, ValueError):
        return str(error)

    if isinstance(error, daemon_control.MultipleDaemonsError):
        return str(error) + " (add ?session=<session_name_or_prefix> to the monitor URL)"

    if isinstance(error, daemon_control.DaemonControlError):
        return str(error)

    if isinstance(error, requests.RequestException):
        if isinstance(daemon_state, dict):
            host = daemon_state.get("host", DEFAULT_HOST)
            port = daemon_state.get("port", DEFAULT_PORT)
            session_id = str(daemon_state.get("session_id", "")).strip()
            if session_id != "":
                return f"Could not reach daemon session '{session_id}' on {host}:{port}"
            return f"Could not reach daemon on {host}:{port}"
        return "Could not reach daemon API"

    return str(error)


def _session_option(daemon):
    host = str(daemon.get("host", DEFAULT_HOST))
    port = int(daemon.get("port", DEFAULT_PORT))
    session_id = str(daemon.get("session_id", "")).strip()
    session_name = str(daemon.get("session_name", "")).strip()

    value = session_id or session_name or f"{host}:{port}"
    hover_text = f"{host}:{port}"
    if session_id:
        label = f"{session_id}"
    else:
        label = f"{host}:{port}"
    return {
        "label": label,
        "value": value,
        "title": hover_text,
    }

def _options_signature(options):
    """Comparable form of a dropdown options list, order and keys independent."""
    return sorted(
        (str(option.get("value", "")), str(option.get("label", "")), str(option.get("title", "")))
        for option in (options or [])
        if isinstance(option, dict)
    )

def _api_get(base_url: str, path: str):
    r = requests.get(str(base_url).rstrip("/") + path, timeout=0.4)
    r.raise_for_status()
    return r.json()

def _api_get_slow(base_url: str, path: str, timeout: float = 2.0):
    r = requests.get(str(base_url).rstrip("/") + path, timeout=float(timeout))
    r.raise_for_status()
    return r.json()

def _api_post(base_url: str, path: str, params: Optional[dict] = None):
    r = requests.post(str(base_url).rstrip("/") + path, params=params or {}, timeout=0.6)
    r.raise_for_status()
    if r.headers.get("content-type", "").startswith("application/json"):
        return r.json()
    return {"ok": True}


######################################
# Small helpers
######################################

def _job_progress(job) -> int:
    progress_val = job.get("progress", 0) if isinstance(job, dict) else 0
    try:
        progress = int(round(float(progress_val)))
    except Exception:
        progress = 0
    return max(0, min(100, progress))


def _elapsed_seconds(job) -> int:
    elapsed = str(job.get("elapsed_time") or "") if isinstance(job, dict) else ""
    parts = elapsed.split(":")
    if len(parts) != 3:
        return 0
    try:
        return max(0, int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
    except Exception:
        return 0


def _job_matches_filter(status_norm: str, filter_value: str) -> bool:
    if filter_value in (None, "", "all"):
        return True
    if filter_value == "running":
        return status_norm in RUNNING_STATUSES
    if filter_value == "queued":
        return status_norm in QUEUED_STATUSES
    if filter_value == "done":
        return status_norm in DONE_STATUSES
    if filter_value == "failed":
        return status_norm in FAILED_STATUSES
    return True


def _sort_key(job, sort_value: str):
    status_norm = str(job.get("status") or "").lower().strip()
    name = str(job.get("display_name") or "").lower()
    job_id = job.get("id", 0)
    try:
        job_id = int(job_id)
    except Exception:
        job_id = 0

    if sort_value == "name":
        return (name, job_id)
    if sort_value == "status":
        return (_STATUS_SORT_PRIORITY.get(status_norm, 99), name, job_id)
    if sort_value == "progress":
        return (-_job_progress(job), job_id)
    if sort_value == "runtime":
        return (-_elapsed_seconds(job), job_id)
    # default: by id
    return (job_id,)


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
        n_clicks=0,
        children=[
            html.Div(
                className="monitor-task " + status,
                id={"type": "task-row", "task_id": task_id},
                children=[
                    html.Div(
                        className="monitor-task-dot",
                        id={"type": "task-dot", "task_id": task_id},
                    ),
                    html.Div(
                        f"{name}",
                        className="monitor-task-name",
                        id={"type": "task-display-name", "task_id": task_id},
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
                                        icon=icon("play_solid", className="icon solid", offset=True),
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
                                        icon=icon("pause_solid", className="icon solid"),
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
                                        icon=icon("cross_solid", className="icon solid"),
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


def _stat(value_id: str, label: str, kind: str):
    return html.Div(
        className=f"monitor-stat {kind}",
        children=[
            html.Span("0", id=value_id, className="monitor-stat-value"),
            html.Span(label, className="monitor-stat-label"),
        ],
    )


def _mode_button(id, label, tooltip):
    return html.Button(
        label,
        id=id,
        n_clicks=0,
        className="monitor-mode-button tooltip top small",
        **{"data-tooltip": tooltip},
    )


######################################
# Callbacks
######################################

@dash.callback(
    Output("session-dropdown", "options"),
    Output("session-dropdown", "value"),
    Input("monitor-refresh", "n_intervals"),
    Input("monitor-last-action", "data"),
    State(f"url_{page_path}", "search"),
    State("session-dropdown", "value"),
    State("monitor-daemon", "data"),
    State("session-dropdown-open", "data"),
    State("session-dropdown", "options"),
)
def _update_session_dropdown(_n, last_action, search, current_value, daemon_state, dropdown_open, current_options):
    # A session that was just shut down must disappear from the list, whether or
    # not the dropdown is open. One-shot: the store keeps its value afterwards,
    # so gate on the trigger, not on the value.
    session_stopped = (
        ctx.triggered_id == "monitor-last-action"
        and isinstance(last_action, dict)
        and last_action.get("action") == "shutdown"
        and last_action.get("ok")
    )

    # Rescanning daemons is expensive (scans /proc and HTTP-pings each candidate).
    # Only do it while the user has the dropdown open, except keep trying at startup
    # until an initial session is selected so default monitoring still works.
    has_selection = _normalize_optional_str(current_value) is not None
    if not dropdown_open and has_selection and not session_stopped:
        raise PreventUpdate

    try:
        daemons = daemon_control.list_daemons()
    except Exception:
        daemons = []

    options = [_session_option(daemon) for daemon in daemons]
    values = {option.get("value") for option in options}

    selected = _normalize_optional_str(current_value)
    if selected not in values:
        selected = None

    query_session = _monitor_query(search).get("session")
    if selected is None:
        selected = _pick_session_value(daemons, query_session)

    if selected is None and isinstance(daemon_state, dict):
        state_session = _normalize_optional_str(daemon_state.get("session_id"))
        if state_session is None:
            state_session = _normalize_optional_str(daemon_state.get("session_name"))
        if state_session in values:
            selected = state_session

    if selected is None and len(options) > 0:
        selected = options[0].get("value")

    # Prevent update if neither the selection nor the available sessions changed:
    # rewriting the props while the user has the menu open would close it under
    # the pointer. Compare on a normalized signature, since the options coming
    # back from the browser are not necessarily identical dicts.
    if selected == current_value and _options_signature(options) == _options_signature(current_options):
        raise PreventUpdate
    return options, selected

@dash.callback(
    Output("monitor-snapshot", "data"),
    Output("monitor-logs", "data", allow_duplicate=True),
    Output("monitor-error", "data"),
    Output("monitor-daemon", "data"),
    Input("monitor-refresh", "n_intervals"),
    State("monitor-snapshot", "data"),
    State("monitor-selected-job", "data"),
    State("monitor-logs", "data"),
    State("monitor-daemon", "data"),
    State(f"url_{page_path}", "search"),
    State("session-dropdown", "value"),
    prevent_initial_call=True,
)
def _poll_status(_n, previous_snapshot, selected_job_id, logs_state, daemon_state, search, selected_session):
    try:
        resolved_daemon = _resolve_daemon_target(search, daemon_state, session_override=selected_session)
        base_url = resolved_daemon.get("base_url")

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

        snap = _api_get(base_url, path)

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

        return snap, new_logs_state, "", resolved_daemon
    except Exception as e:
        # Keep the last known state so the UI does not flicker
        err = _format_monitor_error(e, daemon_state)
        if previous_snapshot is None:
            return {}, no_update, err, None
        return previous_snapshot, no_update, err, None


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

    # Keep a stable ascending-by-id order. Dash aligns pattern-matching ALL
    # outputs by sorted id, so the DOM order, `monitor-job-ids`, and the
    # per-task update callbacks must all agree on this ordering. Visual
    # sorting is applied on top of this via CSS `order` (see _apply_filter_sort).
    jobs = [job for job in jobs if isinstance(job, dict)]
    jobs.sort(key=lambda job: (int(job.get("id", 0)) if str(job.get("id", "")).lstrip("-").isdigit() else 0))

    job_ids = [job.get("id") for job in jobs]

    # Only rebuild the task components if the job list changed.
    if isinstance(previous_job_ids, list) and job_ids == previous_job_ids:
        return no_update, no_update

    children = []
    for job in jobs:
        name = job.get("display_name") or f"job{job.get('id', '')}"
        status = str(job.get("status") or "unknown")
        progress = _job_progress(job)
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
    Output("monitor-sort-reverse", "data"),
    Output("monitor-sort-dir", "className"),
    Input("monitor-sort-dir", "n_clicks"),
    State("monitor-sort-reverse", "data"),
)
def _toggle_sort_direction(n_clicks, reverse):
    """Toggle the ascending/descending sort direction on each button click."""
    reverse = bool(reverse)
    if n_clicks:
        reverse = not reverse
    base = "color-button secondary icon-button icon-only tooltip bottom"
    return reverse, f"{base} active" if reverse else base


@dash.callback(
    Output({"type": "task-container", "task_id": ALL}, "style"),
    Input("monitor-snapshot", "data"),
    Input("monitor-filter", "value"),
    Input("monitor-sort", "value"),
    Input("monitor-sort-reverse", "data"),
    State("monitor-job-ids", "data"),
)
def _apply_filter_sort(snapshot, filter_value, sort_value, sort_reverse, job_ids):
    """Filter (hide non-matching) and sort (CSS `order`) task rows without a DOM rebuild."""
    if not isinstance(job_ids, list) or not job_ids:
        raise PreventUpdate

    jobs = snapshot.get("jobs") if isinstance(snapshot, dict) else None
    by_id = {}
    if isinstance(jobs, list):
        for job in jobs:
            if isinstance(job, dict) and "id" in job:
                by_id[job["id"]] = job

    # Compute visual order ranks from the chosen sort criterion.
    visible_ids = [jid for jid in job_ids if _job_matches_filter(
        str(by_id.get(jid, {}).get("status") or "").lower().strip(), filter_value)]
    ranked = sorted(visible_ids, key=lambda jid: _sort_key(by_id.get(jid, {"id": jid}), sort_value))
    if sort_reverse:
        ranked.reverse()
    order_by_id = {jid: rank for rank, jid in enumerate(ranked)}

    styles = []
    for jid in job_ids:
        status_norm = str(by_id.get(jid, {}).get("status") or "").lower().strip()
        if not _job_matches_filter(status_norm, filter_value):
            styles.append({"display": "none"})
        else:
            styles.append({"order": order_by_id.get(jid, 0)})
    return styles


@dash.callback(
    Output("kpi-total", "children"),
    Output("kpi-running", "children"),
    Output("kpi-queued", "children"),
    Output("kpi-done", "children"),
    Output("kpi-failed", "children"),
    Output("monitor-overall-bar", "style"),
    Output("monitor-overall-text", "children"),
    Input("monitor-snapshot", "data"),
)
def _update_kpis(snapshot):
    jobs = snapshot.get("jobs") if isinstance(snapshot, dict) else None
    if not isinstance(jobs, list):
        jobs = []
    jobs = [job for job in jobs if isinstance(job, dict)]

    total = len(jobs)
    running = queued = done = failed = 0
    progress_sum = 0
    for job in jobs:
        status_norm = str(job.get("status") or "").lower().strip()
        if status_norm in RUNNING_STATUSES:
            running += 1
        elif status_norm in QUEUED_STATUSES:
            queued += 1
        elif status_norm in DONE_STATUSES:
            done += 1
        elif status_norm in FAILED_STATUSES:
            failed += 1
        progress_sum += _job_progress(job)

    overall = int(round(progress_sum / total)) if total > 0 else 0
    return (
        str(total),
        str(running),
        str(queued),
        str(done),
        str(failed),
        {"width": f"{overall}%"},
        f"{overall}%",
    )


@dash.callback(
    Output("monitor-nbjobs-value", "children"),
    Input("monitor-snapshot", "data"),
)
def _update_nbjobs_display(snapshot):
    handler = snapshot.get("handler") if isinstance(snapshot, dict) else None
    if not isinstance(handler, dict):
        raise PreventUpdate
    nb = handler.get("nb_jobs")
    if nb is None:
        raise PreventUpdate
    try:
        return str(max(1, int(nb)))
    except Exception:
        raise PreventUpdate


@dash.callback(
    Output("monitor-nbjobs-value", "children", allow_duplicate=True),
    Input("monitor-nbjobs-inc", "n_clicks"),
    Input("monitor-nbjobs-dec", "n_clicks"),
    State("monitor-nbjobs-value", "children"),
    State("monitor-daemon", "data"),
    State(f"url_{page_path}", "search"),
    State("session-dropdown", "value"),
    prevent_initial_call=True,
)
def _change_nb_jobs(_inc, _dec, current_value, daemon_state, search, selected_session):
    # Step off the currently displayed value so rapid clicks accumulate even
    # before the next snapshot poll reconciles the daemon's authoritative value.
    triggered = ctx.triggered_id
    if triggered not in ("monitor-nbjobs-inc", "monitor-nbjobs-dec"):
        raise PreventUpdate

    try:
        current = int(str(current_value).strip())
    except Exception:
        raise PreventUpdate  # not synced yet; ignore until we know the real value

    new_value = max(1, current + (1 if triggered == "monitor-nbjobs-inc" else -1))
    if new_value == current:
        raise PreventUpdate

    try:
        resolved_daemon = _resolve_daemon_target(search, daemon_state, session_override=selected_session)
        _api_post(resolved_daemon.get("base_url"), "/config", params={"nb_jobs": new_value})
    except Exception:
        # Keep the optimistic value; the next poll reconciles if the post failed.
        pass
    return str(new_value)


@dash.callback(
    Output("monitor-selected-job", "data"),
    Input({"type": "task-container", "task_id": ALL}, "n_clicks"),
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

    # If the user clicked a task container, select that job for the Dash view.
    triggered = ctx.triggered_id
    if isinstance(triggered, dict) and triggered.get("type") == "task-container":
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
    Output({"type": "task-display-name", "task_id": ALL}, "children"),
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
    display_name_text = []
    progress_text = []
    runtime_text = []
    status_text = []
    status_class = []
    start_style = []
    pause_style = []
    stop_style = []

    for job_id in job_ids:

        job = by_id.get(job_id, {})
        display_name = str(job.get("display_name") or f"job{job_id}")
        status = str(job.get("status") or "unknown")
        status_norm = status.lower().strip()

        progress = _job_progress(job)
        runtime = str(job.get("elapsed_time") or "--:--:--")

        display_name_text.append(display_name)
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
        display_name_text,
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
    Output("monitor-log-title", "children"),
    Output("monitor-log-title", "className"),
    Input("monitor-selected-job", "data"),
    Input("monitor-snapshot", "data"),
)
def _update_log_header(selected_job, snapshot):
    try:
        selected_i = int(selected_job) if selected_job is not None else None
    except Exception:
        selected_i = None

    if selected_i is None:
        return "No task selected", "monitor-log-title"

    job = None
    jobs = snapshot.get("jobs") if isinstance(snapshot, dict) else None
    if isinstance(jobs, list):
        for candidate in jobs:
            if isinstance(candidate, dict) and candidate.get("id") == selected_i:
                job = candidate
                break

    if job is None:
        return f"job{selected_i}", "monitor-log-title"

    name = str(job.get("display_name") or f"job{selected_i}")
    status = str(job.get("status") or "").lower().strip()
    return (
        [html.Span(name, className="monitor-log-title-name"),
         html.Span(status, className=f"monitor-log-title-status {status}")],
        "monitor-log-title",
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
    Output("monitor-error", "data", allow_duplicate=True),
    Input("monitor-selected-job", "data"),
    State("monitor-logs", "data"),
    State("monitor-daemon", "data"),
    State(f"url_{page_path}", "search"),
    State("session-dropdown", "value"),
    prevent_initial_call="initial_duplicate",
)
def _fetch_full_log_on_selection(selected_job_id, current_logs, daemon_state, search, selected_session):
    if selected_job_id is None:
        raise PreventUpdate

    try:
        job_id = int(selected_job_id)
    except Exception:
        raise PreventUpdate

    try:
        resolved_daemon = _resolve_daemon_target(search, daemon_state, session_override=selected_session)
        base_url = resolved_daemon.get("base_url")
        # Full log for this job (server supports logs_limit=-1)
        snap = _api_get_slow(base_url, f"/status?logs_job_id={job_id}&logs_offset=0&logs_limit=-1")
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
        }, ""
    except Exception as e:
        # Keep current logs, but surface error to switch UI to error container.
        return current_logs if current_logs is not None else {}, _format_monitor_error(e, daemon_state)


######################################
# Layout modes (split / stacked / tasks-only / log-only) + divider
######################################

# Arrangement modes, always reachable from the always-visible header toolbar.
# "list"/"log" reuse the panel-collapse CSS classes to show a single panel;
# because the controls live in the header (not inside the panels), a hidden
# panel can always be brought back.
_MODE_BY_BUTTON = {
    "monitor-mode-split": "split",
    "monitor-mode-stacked": "stacked",
    "monitor-mode-tasks": "list",
    "monitor-mode-log": "log",
}
_VALID_MODES = ("split", "stacked", "list", "log")


@dash.callback(
    Output("monitor-layout", "data"),
    Input("monitor-mode-split", "n_clicks"),
    Input("monitor-mode-stacked", "n_clicks"),
    Input("monitor-mode-tasks", "n_clicks"),
    Input("monitor-mode-log", "n_clicks"),
    prevent_initial_call=True,
)
def _set_layout_mode(*_clicks):
    mode = _MODE_BY_BUTTON.get(ctx.triggered_id)
    if mode is None:
        raise PreventUpdate
    return mode


@dash.callback(
    Output("monitor-split", "className"),
    Output("monitor-mode-split", "className"),
    Output("monitor-mode-stacked", "className"),
    Output("monitor-mode-tasks", "className"),
    Output("monitor-mode-log", "className"),
    Input("monitor-layout", "data"),
)
def _compose_split_class(layout):
    layout = layout if layout in _VALID_MODES else "split"

    classes = ["monitor-split"]
    if layout == "stacked":
        classes.append("stacked")
    elif layout == "list":
        classes.append("log-collapsed")   # tasks only
    elif layout == "log":
        classes.append("list-collapsed")  # log only
    else:
        classes.append("split")

    def _btn(mode):
        return "monitor-mode-button tooltip top small" + (" active" if layout == mode else "")

    return (
        " ".join(classes),
        _btn("split"),
        _btn("stacked"),
        _btn("list"),
        _btn("log"),
    )


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
    main_class_name = "monitor-dashboard visible"
    error_class_name = "hidden"

    if error_message:
        text = ""
        status = str(error_message)
        main_class_name = "monitor-dashboard hidden"
        error_class_name = "visible"
    return ansi_to_html_spans(text), status, main_class_name, error_class_name


@dash.callback(
    Output("monitor-last-action", "data"),
    Input({"type": "task-start", "task_id": ALL}, "n_clicks"),
    Input({"type": "task-pause", "task_id": ALL}, "n_clicks"),
    Input({"type": "task-stop", "task_id": ALL}, "n_clicks"),
    Input("monitor-stop-all", "n_clicks"),
    Input("monitor-open-path", "n_clicks"),
    State("monitor-selected-job", "data"),
    State("monitor-daemon", "data"),
    State(f"url_{page_path}", "search"),
    State("session-dropdown", "value"),
    prevent_initial_call=True,
)
def _task_action(_start_clicks, _pause_clicks, _stop_clicks, stop_all_clicks, open_clicks,
                 selected_job, daemon_state, search, selected_session):
    if not ctx.triggered:
        raise PreventUpdate

    try:
        resolved_daemon = _resolve_daemon_target(search, daemon_state, session_override=selected_session)
        base_url = resolved_daemon.get("base_url")
    except Exception as e:
        return {"ok": False, "error": _format_monitor_error(e, daemon_state)}

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
            # stop_daemon waits for the process to be gone and removes its state
            # files, so the session list can be refreshed right after.
            daemon_control.stop_daemon(
                host=resolved_daemon.get("host"),
                port=resolved_daemon.get("port"),
            )
            return {"ok": True, "action": "shutdown", "session": resolved_daemon.get("session", "")}
        except Exception as e:
            return {"ok": False, "action": "shutdown", "error": _format_monitor_error(e, daemon_state)}

    if triggered == "monitor-open-path":
        try:
            job_id = int(selected_job)
        except Exception:
            raise PreventUpdate
        try:
            _api_post(base_url, f"/jobs/{job_id}/open")
            return {"ok": True, "action": "open", "job_id": job_id}
        except Exception as e:
            return {"ok": False, "action": "open", "error": _format_monitor_error(e, daemon_state)}

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
            _api_post(base_url, f"/jobs/{job_id}/start")
            return {"ok": True, "action": "start", "job_id": job_id}
        if action_type == "task-pause":
            _api_post(base_url, f"/jobs/{job_id}/pause")
            return {"ok": True, "action": "pause", "job_id": job_id}
        if action_type == "task-stop":
            _api_post(base_url, f"/jobs/{job_id}/kill")
            return {"ok": True, "action": "kill", "job_id": job_id}

        return {"ok": False, "error": f"Unknown action type: {action_type}"}
    except Exception as e:
        return {
            "ok": False,
            "action": action_type,
            "job_id": job_id,
            "error": _format_monitor_error(e, daemon_state),
        }



@dash.callback(
    Output("monitor-open-path", "disabled"),
    Output("monitor-open-path", "data-tooltip"),
    Input("monitor-refresh", "n_intervals"),
    Input("session-dropdown", "value"),
    State(f"url_{page_path}", "search"),
    State("monitor-daemon", "data"),
)
def _toggle_open_path(_n, selected_session, search, daemon_state):
    try:
        resolved_daemon = _resolve_daemon_target(search, daemon_state, session_override=selected_session)
        host = resolved_daemon.get("host")
    except Exception:
        host = None

    if _is_local_host(host):
        return False, "Open task directory"
    return True, "Directory not available: the daemon is running on a remote host"


######################################
# Layout
######################################

# --- Integrated header: toolbar (nav + session + modes + kill) + stats ------
monitor_toolbar = html.Div(
    className="monitor-toolbar",
    children=[
        html.Div(
            className="monitor-toolbar-left",
            children=[
                dcc.Link(
                    icon("back", className="icon back-button", width="26px", height="26px"),
                    href="/",
                    className="monitor-back",
                    title="Back to home",
                    style={"textDecoration": "none"},
                ),
                html.H2("Monitor", className="monitor-title"),
                dcc.Dropdown(
                    id="session-dropdown",
                    options=[],
                    placeholder="Select a session",
                    value=None,
                    clearable=False,
                    className="monitor-session-dropdown",
                ),
            ],
        ),
        html.Div(
            className="monitor-toolbar-right",
            children=[
                html.Div(
                    className="monitor-parallel",
                    children=[
                        html.Span("Parallel", className="monitor-parallel-label"),
                        html.Button(
                            "−", id="monitor-nbjobs-dec", n_clicks=0,
                            className="monitor-parallel-btn tooltip bottom small",
                            **{"data-tooltip": "Fewer jobs in parallel"},
                        ),
                        html.Span("–", id="monitor-nbjobs-value", className="monitor-parallel-value"),
                        html.Button(
                            "+", id="monitor-nbjobs-inc", n_clicks=0,
                            className="monitor-parallel-btn tooltip bottom small",
                            **{"data-tooltip": "More jobs in parallel"},
                        ),
                    ],
                ),
                html.Div(
                    className="monitor-mode-group",
                    children=[
                        _mode_button("monitor-mode-split", "Split", "Task list and log side by side"),
                        _mode_button("monitor-mode-stacked", "Stacked", "Task list above, log below"),
                        _mode_button("monitor-mode-tasks", "Tasks", "Task list only"),
                        _mode_button("monitor-mode-log", "Log", "Log only"),
                    ],
                ),
                ui.icon_button(
                    id="monitor-stop-all",
                    icon=icon("cross_solid", className="icon solid"),
                    color="caution",
                    multiline=True,
                    tooltip="Kill all tasks and exit session",
                ),
            ],
        ),
    ],
)

monitor_header = html.Div(
    id="monitor-header",
    className="monitor-header",
    children=[
        monitor_toolbar,
        html.Div(
            className="monitor-header-row",
            children=[
                html.Div(
                    className="monitor-stats",
                    children=[
                        _stat("kpi-total", "Total", "total"),
                        _stat("kpi-running", "Running", "running"),
                        _stat("kpi-queued", "Queued", "queued"),
                        _stat("kpi-done", "Done", "done"),
                        _stat("kpi-failed", "Failed", "failed"),
                    ],
                ),
                html.Div(
                    className="monitor-overall",
                    children=[
                        html.Span("Overall", className="monitor-overall-label"),
                        html.Div(
                            className="monitor-overall-track",
                            children=[
                                html.Div(id="monitor-overall-bar", className="monitor-overall-bar", style={"width": "0%"}),
                            ],
                        ),
                        html.Span("0%", id="monitor-overall-text", className="monitor-overall-value"),
                    ],
                ),
            ],
        ),
    ],
)

# --- Task list panel --------------------------------------------------------
list_panel = html.Div(
    className="monitor-panel monitor-list-panel",
    children=[
        html.Div(
            className="monitor-panel-header",
            children=[
                html.Div(
                    className="monitor-panel-title-group",
                    children=[
                        html.Span("Tasks", className="monitor-panel-title"),
                        dcc.RadioItems(
                            id="monitor-filter",
                            className="monitor-filter",
                            value="all",
                            options=[
                                {"label": "All", "value": "all"},
                                {"label": "Running", "value": "running"},
                                {"label": "Queued", "value": "queued"},
                                {"label": "Done", "value": "done"},
                                {"label": "Failed", "value": "failed"},
                            ],
                            inline=True,
                        ),
                    ],
                ),
                html.Div(
                    className="monitor-panel-tools",
                    children=[
                        dcc.Dropdown(
                            id="monitor-sort",
                            className="monitor-sort",
                            value="id",
                            clearable=False,
                            options=[
                                {"label": "Sort: Default", "value": "id"},
                                {"label": "Sort: Name", "value": "name"},
                                {"label": "Sort: Status", "value": "status"},
                                {"label": "Sort: Progress", "value": "progress"},
                                {"label": "Sort: Runtime", "value": "runtime"},
                            ],
                            style={"width": "160px"},
                        ),
                        ui.icon_button(
                            icon=icon("sort_dir", className="icon"),
                            color="secondary",
                            id="monitor-sort-dir",
                            width="40px",
                            tooltip="Reverse sort order",
                            tooltip_options="bottom",
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="monitor-list-scroll",
            children=[
                html.Div(children=[], id="monitor-container", className="monitor-container"),
            ],
        ),
    ],
)

# --- Log panel --------------------------------------------------------------
log_panel = html.Div(
    className="monitor-panel monitor-log-panel",
    id="monitor-log-container",
    children=[
        html.Div(
            className="monitor-panel-header",
            children=[
                html.Div("No task selected", id="monitor-log-title", className="monitor-log-title"),
                html.Div(
                    className="monitor-panel-tools",
                    children=[
                        ui.icon_button(
                            icon=icon("folder_open", className="icon"),
                            color="secondary",
                            id="monitor-open-path",
                            width="40px",
                            tooltip="Open task directory",
                            tooltip_options="bottom",
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="monitor-log-scroll",
            children=[
                html.Pre(id="monitor-log", className="monitor-log"),
            ],
        ),
    ],
)

split_view = html.Div(
    id="monitor-split",
    className="monitor-split split",
    children=[
        list_panel,
        html.Div(id="monitor-divider", className="monitor-divider"),
        log_panel,
    ],
)

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
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
            id="monitor-main-container",
            className="monitor-dashboard hidden",
            children=[
                monitor_header,
                split_view,
            ],
        ),
        dcc.Interval(id="monitor-refresh", interval=1000, n_intervals=0),
        dcc.Store(id="monitor-snapshot", data=None),
        dcc.Store(id="monitor-error", data=""),
        dcc.Store(id="monitor-last-action", data=None),
        dcc.Store(id="monitor-daemon", data=None),
        dcc.Store(id="monitor-selected-job", data=0),
        dcc.Store(id="monitor-logs", data=None),
        dcc.Store(id="monitor-job-ids", data=[]),
        dcc.Store(id="monitor-sort-reverse", data=False),
        dcc.Store(id="session-dropdown-open", data=False),
        dcc.Store(id="monitor-layout", data="split"),
    ],
    className="page-content monitor-page",
    style={
        "display": "flex",
        "flexDirection": "column",
    },
)

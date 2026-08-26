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

"""
"Design Space Exploration": which campaigns run, how the exploration is run,
and starting it.

A sweep runs every configuration an architecture describes; an exploration
searches them instead, and what it is looking for is written one campaign at a
time (see "/dse_campaign"). This page is the other half: the campaigns of the
workspace, the ones this run selects, and the button that hands the whole thing
to the daemon -- the very same exploration "odatix dse" would start.
"""

import dash
from dash import ALL, ctx, dcc, html, Input, Output, State

import odatix.gui.navigation as navigation
import odatix.gui.ui_components as ui
from odatix.gui.icons import icon
from odatix.gui.page_scope import page_callback, scoped
from odatix.gui.utils import get_workspace
from odatix.lib.parallel_job_handler import daemon_control
from odatix.lib.utils import AUTO_NB_JOBS_KEYWORD, is_auto_nb_jobs, resolve_nb_jobs

from odatix.gui.dse_config import exploration, popup
from odatix.gui.dse_config.common import (
    DSE_SETTINGS_DEFAULTS,
    campaign_badges,
    campaign_names,
    checked,
    dse_settings,
    editor_path,
    delete_campaign,
    page_path,
    read_campaign,
    save_campaign,
    save_dse_settings,
    switch_value,
    to_int,
    unique_campaign_name,
)

PAGE_SCOPE = "dse"

SAVE_IDLE = "color-button disabled icon-button tooltip delay bottom auto"
SAVE_DIRTY = "color-button warning icon-button tooltip delay bottom auto caution"

START_READY = "color-button success icon-button"
START_WAITING = "color-button disabled icon-button"

NEW_SESSION = "__new_session__"


######################################
# UI Components
######################################

def campaign_card(name, selected, badges):
    """One campaign of the workspace: what it is looking for, and whether it runs."""
    architectures = badges["architectures"]
    objectives = badges["objectives"]
    chips = [
        ui.badge(badges["run"].replace("_", " "), color="primary"),
        ui.badge(badges["strategy"]),
        ui.badge("budget {0}".format(badges["budget"])),
        ui.badge("batch {0}".format(badges["batch"])),
    ]
    for tool in badges["tools"][:2]:
        chips.append(ui.badge(tool))

    goals = html.Div(
        children=[
            html.Span(
                children=[
                    # Which way is better, said once: the arrow is what tells a
                    # maximized metric from a minimized one at a glance.
                    html.Span("\u25b2" if goal == "max" else "\u25bc", className="dse-goal-arrow"),
                    html.Span(metric),
                ],
                className="dse-goal {0}".format(goal),
            )
            for metric, goal in objectives
        ] or [html.Span("no objective yet", className="dse-goal empty")],
        className="dse-goals",
    )

    return html.Div(
        children=[
            html.Div(
                children=[
                    dcc.Checklist(
                        options=[{"label": "", "value": True}],
                        value=switch_value(selected),
                        id={"type": "dse-campaign-enable", "name": name},
                        className="checklist-switch",
                    ),
                    html.Div(name, className="dse-campaign-name", title=name),
                ],
                className="dse-campaign-head",
            ),
            html.Div(chips, className="dse-campaign-chips"),
            goals,
            html.Div(
                ", ".join(architectures) if architectures else "no architecture yet",
                className="dse-campaign-architectures",
                title=", ".join(architectures),
            ),
            html.Div(
                children=[
                    ui.icon_button(
                        id={"type": "dse-campaign-edit", "name": name},
                        icon=icon("edit", className="icon"),
                        text="Edit",
                        color="default",
                        link="{0}?campaign={1}".format(editor_path, name),
                        width="auto",
                        bold=False,
                    ),
                    html.Div(
                        children=[
                            ui.duplicate_button(id={"type": "dse-campaign-duplicate", "name": name}),
                            ui.delete_button(id={"type": "dse-campaign-delete", "name": name}),
                        ],
                        className="inline-flex-buttons",
                    ),
                ],
                className="dse-campaign-actions",
            ),
        ],
        className="card dse-campaign-card" + ("" if selected else " disabled"),
        id={"type": "dse-campaign-card", "name": name},
    )


def build_campaign_cards(workspace):
    settings = dse_settings(workspace)
    selected = set(settings.campaign_names())
    cards = []
    for name in campaign_names(workspace):
        cards.append(campaign_card(name, name in selected, campaign_badges(read_campaign(workspace, name))))
    cards.append(ui.add_card(id={"type": "dse-campaign-add"}, text="New campaign", className="dse-campaign-card"))
    return cards


def settings_form(settings):
    auto_nb_jobs = is_auto_nb_jobs(settings.nb_jobs)
    return ui.grid([
        html.Div([
            ui.caption("Execution"),
            html.Div(
                ui.switch_row(
                    "Evaluate again what is already done", "dse-overwrite",
                    checked=bool(settings.overwrite),
                    tooltip="Designs the workspace already measured are evaluated again "
                            "instead of being reused.",
                ),
                className="odx-switch-stack",
            ),
            html.Div([
                ui.form_field(
                    "Maximum number of parallel jobs", "dse-nb-jobs",
                    value=str(resolve_nb_jobs(AUTO_NB_JOBS_KEYWORD)) if auto_nb_jobs else str(settings.nb_jobs),
                    type="number", disabled=auto_nb_jobs, style={"flex": "1"},
                    tooltip="How many designs of a batch are synthesized at once.",
                ),
                ui.inline_switch(
                    "Auto", "dse-auto-nb-jobs", checked=auto_nb_jobs,
                    tooltip="Use the number of available CPUs minus one.",
                ),
            ], className="odx-field-row"),
        ], className="odx-panel padded"),
        html.Div([
            ui.caption("Monitor"),
            ui.form_field(
                "Size of the log history per job", "dse-log-size",
                value=str(settings.log_size_limit), type="number",
                tooltip="Number of log lines kept per job, the exploration's own log included.",
            ),
            html.Div(
                ui.switch_row(
                    "Exit the monitor when the exploration is over", "dse-exit-when-done",
                    checked=bool(settings.exit_when_done),
                    tooltip="The session closes by itself once the search is done.",
                ),
                className="odx-switch-stack",
                style={"marginTop": "var(--space-2)"},
            ),
        ], className="odx-panel padded"),
    ])


title_buttons = html.Div(
    children=[
        html.Div(
            children=[
                html.Span("Session", className="odx-session-label"),
                dcc.Dropdown(
                    id="dse-session-dropdown",
                    options=[{"label": "New session...", "value": NEW_SESSION}],
                    value=NEW_SESSION,
                    clearable=False,
                    style={"width": "155px"},
                ),
            ],
            className="odx-session",
            style={"margin-bottom": "-5px"},
        ),
        ui.save_button(id="dse-save-all", tooltip="Save the exploration settings and the selected campaigns", disabled=True),
        ui.icon_button(
            id="dse-run",
            icon=icon("play", className="icon"),
            text="Explore",
            tooltip="Start the exploration of every selected campaign",
            tooltip_options="bottom",
            color="success",
        ),
    ],
    className="odx-header-actions",
)


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id="url_dse", refresh=False),
        dcc.Location(id="dse-redirect", refresh=True),
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(
                            html.H1("Design Space Exploration", className="odx-title"),
                            className="odx-header-titles",
                        ),
                        title_buttons,
                    ],
                    className="odx-header-row",
                ),
                html.Div(id="dse-summary", className="odx-summary"),
            ],
            className="odx-header",
        ),
        html.Div(id="dse-feedback", className="dse-feedback"),
        ui.section("Exploration settings", html.Div(id="dse-settings-form")),
        ui.section(
            "Campaigns",
            html.Div(id="dse-campaign-cards", className="dse-campaign-grid"),
            tooltip="One campaign is one question: an architecture, what makes its designs "
                    "good, and how long to look for it. The ones switched on here are the "
                    "ones this exploration runs, one after the other.",
        ),
        # What is on disk, to tell an edit from a card being rendered.
        dcc.Store(id="dse-baseline", data=None),
        dcc.Store(id="dse-run-status", data=None),
        dcc.Store(id="dse-run-render-key", data=""),
        dcc.Store(id="dse-run-popup-opened", data=False),
        dcc.Store(id="dse-delete-info"),
        dcc.Interval(id="dse-run-interval", interval=500, n_intervals=0),
        dcc.Interval(id="dse-session-interval", interval=3000, n_intervals=0),
        html.Div(
            id="dse-run-popup",
            className="overlay-odatix",
            children=[
                html.Div([
                    html.H2("Checking the exploration...", id="dse-run-title", style={"textAlign": "center"}),
                    html.Div(id="dse-run-body", className="dse-plan-scroll"),
                    html.Div([
                        ui.icon_button(
                            icon=icon("cross", className="icon"),
                            color="default", text="Cancel", width="100px",
                            id="dse-run-cancel",
                        ),
                        ui.icon_button(
                            icon=icon("play", className="icon"),
                            color="disabled", text="Start", width="100px",
                            id="dse-run-start",
                        ),
                    ], className="dse-popup-actions"),
                ], className="popup-odatix large"),
            ],
        ),
        html.Div(
            id="dse-delete-popup",
            className="overlay-odatix",
            children=[
                html.Div([
                    html.H2("Warning"),
                    html.Div(id="dse-delete-message"),
                    html.Div("This action is irreversible.", className="dse-danger"),
                    html.Div([
                        ui.icon_button(
                            icon=icon("delete", className="icon"),
                            color="caution", text="Delete", width="90px",
                            id="dse-delete-confirm",
                        ),
                        html.Button("Cancel", id="dse-delete-cancel", n_clicks=0, style={"marginLeft": "10px", "width": "90px"}),
                    ], className="dse-popup-actions"),
                ], className="popup-odatix"),
            ],
        ),
    ],
    className="page-content odx-page dse-page",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": "calc(100vh - {0})".format(navigation.top_bar_height),
    },
)

layout = scoped(PAGE_SCOPE, layout)

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Design Space Exploration",
    name="Design Space Exploration",
    order=7,
)


######################################
# Callbacks: what the page shows
######################################

@dash.callback(
    Output("dse-settings-form", "children"),
    Output("dse-campaign-cards", "children"),
    Output("dse-baseline", "data"),
    Input("url_dse", "pathname"),
)
def init_page(pathname):
    if pathname != page_path:
        raise dash.exceptions.PreventUpdate
    workspace = get_workspace()
    settings = dse_settings(workspace)
    return settings_form(settings), build_campaign_cards(workspace), _baseline(settings)


def _baseline(settings):
    """The exploration settings as they are written, for the unsaved-changes state."""
    settings.ask_continue = False
    return settings.to_dict()


@page_callback(PAGE_SCOPE,
    Output("dse-summary", "children"),
    Output({"type": "dse-campaign-card", "name": ALL}, "className"),
    Input({"type": "dse-campaign-enable", "name": ALL}, "value"),
    State({"type": "dse-campaign-enable", "name": ALL}, "id"),
)
def update_summary(values, ids):
    """
    What the selection amounts to: how many campaigns run, and how many designs
    they are allowed to evaluate between them.
    """
    workspace = get_workspace()
    selected = [
        identifier["name"]
        for value, identifier in zip(values or [], ids or [])
        if isinstance(identifier, dict) and checked(value)
    ]
    budget = 0
    architectures = set()
    for name in selected:
        badges = campaign_badges(read_campaign(workspace, name))
        budget += badges["budget"] * max(len(badges["architectures"]), 1)
        architectures.update(badges["architectures"])

    summary = [
        ui.stat(len(selected), "campaign" if len(selected) == 1 else "campaigns"),
        ui.stat(budget, "designs at most"),
        ui.stat(len(architectures), "architecture" if len(architectures) == 1 else "architectures"),
    ]
    classes = [
        "card dse-campaign-card" + ("" if checked(value) else " disabled")
        for value in (values or [])
    ]
    return summary, classes


@dash.callback(
    Output("dse-nb-jobs", "disabled"),
    Output("dse-nb-jobs", "value"),
    Input("dse-auto-nb-jobs", "value"),
    State("dse-nb-jobs", "value"),
)
def toggle_auto_nb_jobs(auto, current):
    if checked(auto):
        return True, str(resolve_nb_jobs(AUTO_NB_JOBS_KEYWORD))
    return False, current


@dash.callback(
    Output("dse-session-dropdown", "options"),
    Output("dse-session-dropdown", "value"),
    Input("dse-session-interval", "n_intervals"),
    State("dse-session-dropdown", "value"),
)
def update_session_dropdown(_n, current_value):
    options = [{"label": "New session...", "value": NEW_SESSION, "title": "Explore in a new session"}]
    try:
        daemons = daemon_control.list_daemons()
    except Exception:
        daemons = []
    for daemon in daemons:
        session_id = str(daemon.get("session_id", "")).strip()
        session_name = str(daemon.get("session_name", "")).strip()
        label = session_id or session_name
        if label:
            options.append({"label": label, "value": label})

    values = set(option["value"] for option in options)
    selected = str(current_value).strip() if current_value else NEW_SESSION
    return options, selected if selected in values else NEW_SESSION


######################################
# Callbacks: saving
######################################

@page_callback(PAGE_SCOPE,
    Output("dse-save-all", "className", allow_duplicate=True),
    Input("dse-overwrite", "value"),
    Input("dse-nb-jobs", "value"),
    Input("dse-auto-nb-jobs", "value"),
    Input("dse-log-size", "value"),
    Input("dse-exit-when-done", "value"),
    Input({"type": "dse-campaign-enable", "name": ALL}, "value"),
    State({"type": "dse-campaign-enable", "name": ALL}, "id"),
    State("dse-baseline", "data"),
    prevent_initial_call=True,
)
def mark_dirty(overwrite, nb_jobs, auto_nb_jobs, log_size, exit_when_done, values, ids, baseline):
    """
    Whether what is on screen is still what is on disk.

    Dash re-fires a pattern-matching callback as soon as the components it
    matches change, so the cards being rendered would otherwise be reported as
    an edit: the state is compared to the baseline instead.
    """
    if baseline is None:
        raise dash.exceptions.PreventUpdate
    current = _settings_from_page(
        get_workspace(), overwrite, nb_jobs, auto_nb_jobs, log_size, exit_when_done, values, ids
    ).to_dict()
    return SAVE_IDLE if current == baseline else SAVE_DIRTY


def _settings_from_page(workspace, overwrite, nb_jobs, auto_nb_jobs, log_size, exit_when_done, values, ids):
    """
    The exploration settings as the page holds them, saved or not.

    The file's other keys are kept: it is read first and only what the page
    edits is written over it, so a campaign body or a comment the user put there
    survives a save.
    """
    settings = dse_settings(workspace)
    settings.overwrite = checked(overwrite)
    settings.nb_jobs = AUTO_NB_JOBS_KEYWORD if checked(auto_nb_jobs) else to_int(nb_jobs, DSE_SETTINGS_DEFAULTS["nb_jobs"])
    settings.log_size_limit = to_int(log_size, DSE_SETTINGS_DEFAULTS["log_size_limit"])
    settings.exit_when_done = checked(exit_when_done)
    # The page never asks in a terminal nobody is watching: the popup is where
    # the exploration is confirmed.
    settings.ask_continue = False
    settings.campaigns = [
        identifier["name"]
        for value, identifier in zip(values or [], ids or [])
        if isinstance(identifier, dict) and checked(value)
    ]
    return settings


@page_callback(PAGE_SCOPE,
    Output("dse-save-all", "className"),
    Output("dse-feedback", "children"),
    Output("dse-baseline", "data", allow_duplicate=True),
    Input("dse-save-all", "n_clicks"),
    State("dse-overwrite", "value"),
    State("dse-nb-jobs", "value"),
    State("dse-auto-nb-jobs", "value"),
    State("dse-log-size", "value"),
    State("dse-exit-when-done", "value"),
    State({"type": "dse-campaign-enable", "name": ALL}, "value"),
    State({"type": "dse-campaign-enable", "name": ALL}, "id"),
    prevent_initial_call=True,
)
def save_all(n_clicks, overwrite, nb_jobs, auto_nb_jobs, log_size, exit_when_done, values, ids):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    workspace = get_workspace()
    settings = _settings_from_page(
        workspace, overwrite, nb_jobs, auto_nb_jobs, log_size, exit_when_done, values, ids
    )
    try:
        save_dse_settings(workspace, settings)
    except Exception as error:
        return SAVE_DIRTY, html.Div(str(error), className="dse-message error"), dash.no_update
    return (
        SAVE_IDLE,
        html.Div("Exploration settings saved.", className="dse-message success"),
        settings.to_dict(),
    )


######################################
# Callbacks: the campaigns themselves
######################################

@page_callback(PAGE_SCOPE,
    Output("dse-redirect", "href"),
    Input({"type": "dse-campaign-add"}, "n_clicks"),
    prevent_initial_call=True,
)
def add_campaign(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    name = unique_campaign_name(get_workspace(), "New_Campaign")
    return "{0}?campaign={1}".format(editor_path, name)


@page_callback(PAGE_SCOPE,
    Output("dse-campaign-cards", "children", allow_duplicate=True),
    Input({"type": "dse-campaign-duplicate", "name": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def duplicate_campaign(clicks):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not any(clicks or []):
        raise dash.exceptions.PreventUpdate
    workspace = get_workspace()
    name = triggered["name"]
    new_name = unique_campaign_name(workspace, "{0}_copy".format(name))
    try:
        save_campaign(workspace, new_name, read_campaign(workspace, name))
    except Exception:
        raise dash.exceptions.PreventUpdate
    return build_campaign_cards(workspace)


@page_callback(PAGE_SCOPE,
    Output("dse-delete-popup", "className"),
    Output("dse-delete-message", "children"),
    Output("dse-delete-info", "data"),
    Input({"type": "dse-campaign-delete", "name": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def show_delete_popup(clicks):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not any(clicks or []):
        raise dash.exceptions.PreventUpdate
    name = triggered["name"]
    return (
        "overlay-odatix visible",
        'Do you really want to delete campaign "{0}"?'.format(name),
        {"name": name},
    )


@dash.callback(
    Output("dse-delete-popup", "className", allow_duplicate=True),
    Input("dse-delete-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def close_delete_popup(_n):
    return "overlay-odatix"


@dash.callback(
    Output("dse-delete-popup", "className", allow_duplicate=True),
    Output("dse-campaign-cards", "children", allow_duplicate=True),
    Input("dse-delete-confirm", "n_clicks"),
    State("dse-delete-info", "data"),
    prevent_initial_call=True,
)
def do_delete(n_clicks, info):
    if not n_clicks or not info:
        raise dash.exceptions.PreventUpdate
    workspace = get_workspace()
    name = info.get("name")
    try:
        delete_campaign(workspace, name)
        settings = dse_settings(workspace)
        if name in settings.campaign_names():
            settings.campaigns = [entry for entry in settings.campaign_names() if entry != name]
            save_dse_settings(workspace, settings)
    except Exception:
        pass
    return "overlay-odatix", build_campaign_cards(workspace)


######################################
# Callbacks: starting the exploration
######################################

@page_callback(PAGE_SCOPE,
    Output("dse-run-popup", "className"),
    Output("dse-run-popup-opened", "data"),
    Output("dse-run-title", "children"),
    Output("dse-run-render-key", "data", allow_duplicate=True),
    Output("dse-run-status", "data"),
    Input("dse-run", "n_clicks"),
    State("dse-overwrite", "value"),
    State("dse-nb-jobs", "value"),
    State("dse-auto-nb-jobs", "value"),
    State("dse-log-size", "value"),
    State("dse-exit-when-done", "value"),
    State({"type": "dse-campaign-enable", "name": ALL}, "value"),
    State({"type": "dse-campaign-enable", "name": ALL}, "id"),
    State("dse-session-dropdown", "value"),
    prevent_initial_call=True,
)
def run_exploration(n_clicks, overwrite, nb_jobs, auto_nb_jobs, log_size, exit_when_done,
                    values, ids, session):
    """
    Work out what the exploration would do, with the page as it stands -- saved
    or not, exactly like the "Run jobs" page runs what is on screen.
    """
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    if exploration.is_checking():
        raise dash.exceptions.PreventUpdate

    workspace = get_workspace()
    settings = _settings_from_page(
        workspace, overwrite, nb_jobs, auto_nb_jobs, log_size, exit_when_done, values, ids
    )
    campaigns = [read_campaign(workspace, name) for name in settings.campaign_names()]
    selector = None if not session or session == NEW_SESSION else str(session).strip()

    if not campaigns:
        exploration.reset()
        exploration.messages.add(
            "error",
            "No campaign is selected: switch on the ones this exploration should run.",
        )
        exploration.status = {"status": "error", "error": "No campaign selected"}
        return "overlay-odatix visible", True, "Nothing to explore", "", {"status": "error"}

    exploration.check(workspace, settings, campaigns, session=selector)
    return "overlay-odatix visible", True, "Checking the exploration...", "", {"status": "checking"}


@dash.callback(
    Output("dse-run-status", "data", allow_duplicate=True),
    Output("dse-run-body", "children"),
    Output("dse-run-render-key", "data"),
    Output("dse-run-start", "className"),
    Output("dse-run-title", "children", allow_duplicate=True),
    Output("dse-redirect", "href", allow_duplicate=True),
    Input("dse-run-interval", "n_intervals"),
    State("dse-run-status", "data"),
    State("dse-run-popup-opened", "data"),
    State("dse-run-render-key", "data"),
    prevent_initial_call=True,
)
def poll_exploration(_n, run_status, opened, render_key):
    if not run_status or not opened:
        raise dash.exceptions.PreventUpdate

    status = exploration.status.get("status", "idle")
    if status == "started" and exploration.monitor_href:
        # The exploration is a job of the daemon like every other run: from here
        # on it is watched in the monitor.
        return {"status": "started"}, dash.no_update, dash.no_update, START_WAITING, "Exploration started", exploration.monitor_href

    title = {
        "checking": "Checking the exploration...",
        "checked": "Ready to explore",
        "starting": "Starting the exploration...",
        "error": "The exploration cannot run",
    }.get(status, dash.no_update)

    button = START_READY if status == "checked" else START_WAITING
    key = popup.render_key(status)
    if key == render_key:
        return {"status": status}, dash.no_update, dash.no_update, button, title, dash.no_update
    return {"status": status}, popup.body(status), key, button, title, dash.no_update


@dash.callback(
    Output("dse-run-popup", "className", allow_duplicate=True),
    Output("dse-run-popup-opened", "data", allow_duplicate=True),
    Input("dse-run-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def close_run_popup(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return "overlay-odatix", False


@dash.callback(
    Output("dse-run-status", "data", allow_duplicate=True),
    Output("dse-run-title", "children", allow_duplicate=True),
    Output("dse-run-start", "className", allow_duplicate=True),
    Input("dse-run-start", "n_clicks"),
    State("dse-run-status", "data"),
    prevent_initial_call=True,
)
def start_exploration(n_clicks, run_status):
    if not n_clicks or not run_status or run_status.get("status") != "checked":
        raise dash.exceptions.PreventUpdate
    exploration.start()
    return {"status": "starting"}, "Starting the exploration...", START_WAITING

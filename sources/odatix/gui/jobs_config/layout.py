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

"""The static layout of the page."""

from dash import dcc, html

import odatix.gui.navigation as navigation
import odatix.gui.ui_components as ui
from odatix.gui.icons import icon

from odatix.gui.jobs_config.common import page_path
from odatix.gui.jobs_config.settings_form import job_settings_form

#: Who may use a new session besides you ("session_access"), as the page bar names it.
SESSION_ACCESS_OPTIONS = [
    {"label": "Only me", "value": "user"},
    {"label": "My group", "value": "group"},
    {"label": "Everyone", "value": "other"},
]
SESSION_ACCESS_TOOLTIP = (
    "Who may use the new session besides you: monitor it, add, pause or kill its jobs, stop it. "
    "\"My group\" is the group of the workspace directory. Using a session is running commands as you. "
    "A session that runs already keeps its own."
)

#: Where the jobs go: the session, and who may use it if it is a new one.
session_controls = html.Div(
    children=[
        html.Span("Session", className="odx-session-label"),
        dcc.Dropdown(
            id={"page": page_path, "action": "session-dropdown"},
            options=[
                {"label": "New session...", "value": "__new_session__"},
            ],
            placeholder="Select a session",
            value="__new_session__",
            clearable=False,
            # Long session names are not cut in the middle: the menu
            # grows to fit them (see jobs.css).
            className="odx-session-dropdown",
            style={"width": "170px"},
        ),
        html.Div(
            dcc.Dropdown(
                id={"page": page_path, "action": "session-access"},
                options=SESSION_ACCESS_OPTIONS,
                value="user",
                clearable=False,
                searchable=False,
                className="odx-session-dropdown",
                style={"width": "115px"},
            ),
            title=SESSION_ACCESS_TOOLTIP,
        ),
    ],
    className="odx-session",
)

#: Where the selection comes from, and another run settings file to take it from.
selection_controls = html.Div(
    children=[
        html.Span(id="jobs-selection-source"),
        dcc.Dropdown(
            id="jobs-load-selection-from",
            options=[],
            value=None,
            placeholder="Load from...",
            clearable=False,
            searchable=False,
            className="odx-load-from",
            style={"width": "140px"},
        ),
        # What "Load from" picked, with when: picking the same file again
        # loads it again.
        dcc.Store(id="jobs-selection-from", data=None),
    ],
    className="odx-selection-source",
)

title_buttons = html.Div(
    children=[
        ui.icon_button(
            id={"page": page_path, "action": "choose-targets"},
            icon=icon("gear", className="icon"),
            link="/select_targets",  # href updated from the url by update_choose_targets_link
            text="Choose targets",
            multiline=True,
            tooltip="Go to the targets page to select targets",
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
            text="Run jobs",
            tooltip="Run all selected architecture configurations",
            tooltip_options="bottom",
            color="success",
        ),
    ],
    className="odx-header-actions",
)

page_header = html.Div(
    children=[
        html.Div(
            children=[
                html.Div(
                    children=[
                        # Back to the choice this page was opened from (the
                        # tool, or the job type): set from the url by
                        # update_choose_targets_link.
                        dcc.Link(
                            icon("back", className="icon back-button", width="26px", height="26px"),
                            href="/choose_job_type",
                            id="jobs-config-back",
                            className="jobs-back",
                            title="Back",
                        ),
                        html.H1("Select architecture configurations to run", id="jobs-config-main-title", className="odx-title"),
                    ],
                    className="odx-header-titles jobs-titles",
                ),
                title_buttons,
            ],
            className="odx-header-row",
        ),
        html.Div(id="jobs-summary", className="odx-summary"),
        # Where the preselection comes from, so that the page does not read
        # as a blank slate (the run settings file of this job type), and where
        # the jobs go.
        html.Div([selection_controls, session_controls], className="odx-header-footer"),
    ],
    className="odx-header",
)

arch_section_tools = html.Div(
    children=[
        dcc.Input(
            id="jobs-arch-search",
            type="search",
            placeholder="Filter by name...",
            debounce=False,
            className="odx-search small-button",
        ),
        dcc.Checklist(
            options=[{"label": "Selected only", "value": "enabled"}],
            value=[],
            id="jobs-arch-filter",
            className="odx-chips small-button",
        ),
        html.Button("Select all", id="jobs-select-all", n_clicks=0, className="odx-mini-button small-button"),
        html.Button("Clear", id="jobs-select-none", n_clicks=0, className="odx-mini-button small-button"),
    ],
    className="odx-section-tools",
)


layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}", refresh=False),
        page_header,
        html.Div(id={"page": page_path, "type": "title-div"}),
        ui.feedback("jobs-config-save-feedback"),
        ui.section(
            "Job settings",
            html.Div(
                # Rendered with the defaults from the start, then filled by
                # init_form: its fields are inputs of callbacks (the summary,
                # "auto" nb_jobs...), which must find them on load.
                html.Div(job_settings_form({}), id="job-settings-form-container"),
                id="jobs-settings-body",
                className="animated-section",
            ),
            tools=html.Button("Hide", id="jobs-settings-toggle", n_clicks=0, className="odx-mini-button small-button"),
        ),
        dcc.Store(id="job-settings-initial-settings", data=None),
        ui.section(
            "Architectures",
            html.Div(
                # Replaced by the cards once they are built (update_param_domains)
                html.Div(
                    [html.Span(className="jobs-spinner"), html.Span("Loading the selection…")],
                    className="odx-panel odx-empty jobs-loading",
                ),
                id="job-section",
                className="jobs-arch-list",
            ),
            heading_id="job-section-heading",
            tools=arch_section_tools,
        ),
        dcc.Store(id="jobs-config-saved-selection", data=None),
        dcc.Store(id="jobs-config-run-status", data=None),
        dcc.Store(id="run-popup-opened", data=False),
        dcc.Store(id="run-popup-render-key", data=""),
        dcc.Store(id="unsaved-guard-bypass", data=""),
        # Navigates to the monitor once the jobs are in a session. Without a
        # page reload: a reload cut the requests still on their way, which the
        # browser reported as "Callback failed: the server did not respond".
        dcc.Location(id="run-redirect", refresh="callback-nav"),
        # The run popup is polled fast, and only while it is open (see
        # show_run_popup): polling a closed popup kept the page busy for
        # nothing. Listing the daemon sessions is a much slower, network-bound
        # refresh and must not share that timer, or a slow discovery delays the
        # popup updates.
        dcc.Interval(id="run-log-interval", interval=500, n_intervals=0, disabled=True),
        dcc.Interval(id="session-list-interval", interval=5000, n_intervals=0),
        html.Div(
            id="run-popup",
            className="overlay-odatix",
            children=[
                html.Div([
                    html.H2("Checking settings...", id="run-popup-title", style={"textAlign": "center"}),
                    # What the run runs with: tool, flow, last step, targets,
                    # work directory (see run_popup._popup_context)
                    html.Div(id="run-popup-context", className="jobs-plan-context"),
                    html.Div(id="run-popup-progress"),
                    html.Div(id="run-popup-body", className="jobs-plan-scroll"),
                    html.Div([
                        ui.icon_button(
                            icon=icon("cross", className="icon"),
                            color="default",
                            text="Cancel",
                            width="100px",
                            id="run-cancel-btn",
                        ),
                        ui.icon_button(
                            icon=icon("play", className="icon"),
                            color="disabled",
                            text="Start",
                            width="100px",
                            id="run-confirm-btn",
                        ),
                    ], className="jobs-popup-actions"),
                ], className="popup-odatix large")
            ]
        ),
    ],
    className="page-content odx-page jobs-page",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

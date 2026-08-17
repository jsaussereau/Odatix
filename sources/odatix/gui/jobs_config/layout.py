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

title_buttons = html.Div(
    children=[
        html.Div(
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
                    style={"width": "155px"},
                ),
            ],
            className="odx-session",
            style={"margin-bottom": "-5px"}
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
    className="odx-header-actions",
)

page_header = html.Div(
    children=[
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.H1("Select architecture configurations to run", id="jobs-config-main-title", className="odx-title"),
                    ],
                    className="odx-header-titles",
                ),
                title_buttons,
            ],
            className="odx-header-row",
        ),
        html.Div(id="jobs-summary", className="odx-summary"),
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
        ui.section(
            "Job Settings",
            html.Div(
                html.Div(id="job-settings-form-container"),
                id="jobs-settings-body",
                className="animated-section",
            ),
            tools=html.Button("Hide", id="jobs-settings-toggle", n_clicks=0, className="odx-mini-button small-button"),
        ),
        dcc.Store(id="job-settings-initial-settings", data=None),
        ui.section(
            "Architectures",
            html.Div(id="job-section", className="jobs-arch-list"),
            heading_id="job-section-heading",
            tools=arch_section_tools,
        ),
        dcc.Store(id="jobs-config-saved-selection", data=None),
        dcc.Store(id="jobs-config-run-status", data=None),
        dcc.Store(id="run-popup-opened", data=False),
        dcc.Store(id="run-popup-render-key", data=""),
        dcc.Store(id="unsaved-guard-bypass", data=""),
        dcc.Location(id="run-redirect", refresh=True),
        # The run popup is polled fast; listing the daemon sessions is a much
        # slower, network-bound refresh and must not share that timer, or a slow
        # discovery delays the popup updates.
        dcc.Interval(id="run-log-interval", interval=500, n_intervals=0),
        dcc.Interval(id="session-list-interval", interval=3000, n_intervals=0),
        html.Div(
            id="run-popup",
            className="overlay-odatix",
            children=[
                html.Div([
                    html.H2("Checking settings...", id="run-popup-title", style={"textAlign": "center"}),
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

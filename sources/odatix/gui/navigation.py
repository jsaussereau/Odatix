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
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.io as pio

import odatix.gui.themes as themes
import odatix.components.motd as motd

from odatix.gui.css_helper import Style
from odatix.gui.icons import icon

top_bar_height = "50px"
side_bar_width = "0px"

# Topbar entries, either:
#   (label, href)                 -> plain link button, no dropdown (e.g. Monitor)
#   (label, href, [(name, href)]) -> group: hovering opens the dropdown, clicking
#                                     the label itself navigates to href (e.g. Run,
#                                     Explorer). href may be "" for a group with no
#                                     page of its own (e.g. Configure): its label is
#                                     then just a hover target, not a link.
nav_groups = [
    ("Configure", "", [
        ("Workflows", "/workflows"),
        ("RTL Architectures", "/architectures"),
    ]),
    ("Run", "/choose_job_type", [
        ("Workflows", "/run_jobs?type=workflow"),
        ("RTL Analysis", "/run_jobs?type=analyze"),
        ("Fmax Synthesis", "/choose_eda_tool?type=fmax_synthesis"),
        ("Custom Synthesis", "/choose_eda_tool?type=custom_freq_synthesis"),
    ]),
    ("Monitor", "/monitor"),
    ("Explorer", "/explorer", [
        ("Lines", "/explorer/lines"),
        ("Columns", "/explorer/columns"),
        ("Scatter", "/explorer/scatter"),
        ("Scatter 3D", "/explorer/scatter3d"),
        ("Radar", "/explorer/radar"),
        ("Table", "/explorer/table"),
        ("Overview", "/explorer/overview"),
        ("RTL Analysis", "/explorer/analysis"),
    ]),
    ("Settings", "/workspace", [
        ("Workspace", "/workspace"),
    ]),
]


def _nav_entry(entry):
    if len(entry) == 2:
        label, href = entry
        return dcc.Link(label, href=href, className="nav-link-button")

    label, href, items = entry
    header_content = [label, icon("more", width="13px", height="13px", className="nav-chevron")]
    if href:
        header = dcc.Link(header_content, href=href, className="nav-group-label")
    else:
        # No page of its own: keep it a non-navigable hover/focus target.
        header = html.Span(header_content, className="nav-group-label", tabIndex="0")

    return html.Div(
        [
            header,
            html.Div(
                [dcc.Link(name, href=item_href, className="nav-dropdown-link") for name, item_href in items],
                className="nav-dropdown",
            ),
        ],
        className="nav-group",
    )

def top_bar(gui):
    version = motd.read_version()

    return html.Div(
        children=[
            dcc.Link(
                id="navbar-title",
                className="link",
                href="/",
                children=[
                    html.Span(
                        html.Div(
                            children=[
                                html.Span("Odatix " + str(version), className="link-title1 title"),
                                html.Span("Home", className="link-title2 title"),
                            ],
                            className="link-container"
                        ),
                        className="mask"
                    )
                ],
                style={"position": "block", "marginLeft": "30px", "left": "75px", "zIndex": "2", "transition": "marginLeft 0.25s"},
            ),
            html.Div([
                html.Div(
                    [
                        html.Span(className="nav-burger-line"),
                        html.Span(className="nav-burger-line"),
                        html.Span(className="nav-burger-line"),
                    ],
                    id="nav-burger",
                    className="nav-burger",
                    n_clicks=0,
                ),
                html.Div([
                    html.Div(
                        [_nav_entry(entry) for entry in nav_groups],
                        className="nav-groups",
                    ),
                    html.Div(
                        children=[
                            dcc.Dropdown(
                                id="theme-dropdown",
                                options=[{"label": f"{theme}", "value": f"{theme}"} for theme in themes.list],
                                value=gui.start_theme,
                                className="theme-dropdown",
                                clearable=False,
                                style={"width": "150px"},
                            )
                        ],
                        className="nav-theme tooltip delay bottom auto",
                        **{"data-tooltip": "Select Theme"},
                    ),
                ],
                id="nav-menu",
                className="nav-menu",
                ),
            ],
            id="nav-right",
            className="nav-right",)
        ],
        style={"height": f"{top_bar_height}"},
        className="navbar",
        id="navbar",
    )


def side_bar(gui):

    return html.Div(
        [
            html.Div(
                id="sidebar-top",
                className="sidebar-top",
                style={"top": "0px", "left": "0px", "width": side_bar_width, "height": f"{top_bar_height}"},
            ),
            html.Img(
                id="toggle-button",
                className="sidebar-button",
                src="/assets/icons/sidebar-panel-expand-icon.svg",
                n_clicks=0,
                style={
                    "display": "none",
                    "cursor": "pointer",
                    "position": "absolute",
                    "top": "10px",
                    "left": "20px",
                    "width": "30px",
                    "zIndex": "3",
                },
            ),
        ]
    )


def setup_callbacks(gui):
    # Toggle the mobile burger menu on click, close it on navigation
    gui.app.clientside_callback(
        """
        function(n_clicks, pathname, cls) {
            const ctx = window.dash_clientside.callback_context;
            const trigger = (ctx.triggered && ctx.triggered.length) ? ctx.triggered[0].prop_id : "";
            const open = trigger.startsWith("nav-burger") && !(cls || "").includes("open");
            return [open ? "nav-menu open" : "nav-menu", open ? "nav-burger open" : "nav-burger"];
        }
        """,
        [Output("nav-menu", "className"), Output("nav-burger", "className")],
        [Input("nav-burger", "n_clicks"), Input("url-global", "pathname")],
        [State("nav-menu", "className")],
        prevent_initial_call=True,
    )

    @gui.app.callback(
        Output("theme", "className"),
        Input("theme-dropdown", "value"),
    )
    def update_theme(
        theme
    ):
        return f"theme {theme}"
    
    @gui.app.callback(
        Output("url", "href"),
        Input({"type": "update_url", "id": dash.ALL}, "data"),
    )
    def update_url(data_list):
        triggered_id = dash.callback_context.triggered_id
        if triggered_id and isinstance(triggered_id, dict):
            if triggered_id.get("type") == "update_url":
                url_trigger_id = triggered_id.get("id")
                for data in data_list:
                    if data and isinstance(data, dict):
                        if data.get("id") == url_trigger_id:
                            return data.get("href", "")
        return dash.no_update

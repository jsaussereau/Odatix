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

top_bar_height = "50px"
side_bar_width = "0px"

banned_pages = ["PageNotFound", "Home", "Configuration Editor", "Architecture Editor", "Configuration Generator"]

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
                style={"position": "block", "margin-left": "30px", "left": "75px", "z-index": "2", "transition": "margin-left 0.25s"},
            ),
            html.Div([
                html.Div(
                    [
                        html.Div(
                            dcc.Link(f"{page['name']}", href=page["relative_path"], className="nav-link"),
                        ) for page in dash.page_registry.values() if page["name"] not in banned_pages
                    ],
                    className="nav-links",
                ),
                html.Div(
                    children=[
                        dcc.Dropdown(
                            id="theme-dropdown",
                            options=[{"label": f"{theme}", "value": f"{theme}"} for theme in themes.list],
                            value=gui.start_theme,
                            className="theme-dropdown",
                            clearable=False,
                            style={"width": "150px", "margin-right": "20px", "marginTop": "3px"},
                        )
                    ],
                    className="tooltip delay bottom auto",
                    **{'data-tooltip': "Select Theme"},
                ),
            ],
            id="nav-right",
            style={"display": "flex", "position": "absolute", "right": "0", "alignItems": "center", "justifyContent": "right", "z-index": "1000"},)
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
                    "z-index": "3",
                },
            ),
        ]
    )


def setup_callbacks(gui):
    @gui.app.callback(
        Output("theme", "className"),
        Input("theme-dropdown", "value"),
    )
    def update_theme(
        theme
    ):
        return f"theme {theme if theme != 'odatix' else ''}"
    
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

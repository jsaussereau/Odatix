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
import dash
from dash import dcc, html, Input, Output, State

import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
from odatix.lib.settings import OdatixSettings

page_path = "/"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix',
    name='Home',
)

######################################
# UI Components
######################################

padding = 20

# Home page

home_cards = [
    {
        "name": "Architectures",
        "link": "/architectures",
        "image": "assets/icons/architecture.png",
        "description": "Configure your architectures",
    },
    {
        "name": "Monitor jobs",
        "link": "/monitor",
        "image": "assets/icons/monitor.png",
        "description": "Monitor currently running jobs",
    },
    # {
    #     "name": "Export Results",
    #     "link": "/export",
    #     "image": "assets/icons/export.png",
    #     "description": "Export results from synthesis and simulation",
    # },
    # {
    #     "name": "Explore Results",
    #     "link": "/explorer",
    #     "image": "assets/icons/explorer.png",
    #     "description": "Explore results in an interactive interface",
    # },
    # {
    #     "name": "EDA Tools",
    #     "link": "/tools",
    #     "image": "assets/icons/tools.png",
    #     "description": "EDA tools options and metrics definition",
    # },
    {
        "name": "Workspace Settings",
        "link": "/workspace",
        "image": "assets/icons/settings.png",
        "description": "Adjust workspace settings",
    },
    {
        "name": "Documentation",
        "link": "https://odatix.readthedocs.io",
        "image": "assets/icons/documentation.png",
        "description": "Access Odatix online documentation",
    },
]

home_layout = [
    html.Div(
        children=[
            html.Div(
                [ui.create_card_button(card) for card in home_cards],
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "justifyContent": "center",
                    "gap": "20px",
                    "paddingLeft": "50px",
                    "paddingRight": "50px",
                },
            ),
        ],
        id=f"{__name__}-content",
        style={
            "display": "flex",
            "justifyContent": "center",
            "alignItems": "center",
            "paddingTop": f"{padding}px",
            "paddingBottom": f"{padding}px",
        },
    ),
    html.H4(
        "Icons designed by Freepik from Flaticon",
        style={
            "textAlign": "center",
            "color": "#aaa",
            "marginTop": "20px",
            "fontSize": "12px",
            "fontWeight": "normal",
        }
    ),
]


# New workspace page

new_workspace_cards = [
    {
        "name": "Empty workspace",
        "id": "create-empty-workspace",
        "image": "assets/icons/workspace_empty.svg",
        "description": "Start from scratch",
    },
    {
        "name": "Workspace with examples",
        "id": "create-workspace-with-examples",
        "image": "assets/icons/workspace_examples.svg",
        "description": "Get started quickly with pre-configured examples",
    },
]

new_workspace_layout = [
    html.Div(
        children=[
            html.H2("Initialize an Odatix workspace in this directory", style={"fontSize": "32px", "marginBottom": "-15px"}),
            html.Pre(
                f"{os.getcwd()}", 
                style={
                    "display": "inline-block",
                    "width": "fit-content",
                    "fontSize": "20px",
                    "padding": "0px 10px",
                    "whiteSpace": "pre-wrap",
                    "overflowWrap": "anywhere",
                }
            ),
        ],
        className="tile center",
        style={"fontSize": "32px"}
    ),
    html.Div(
        [
            html.Div(
                [html.Div(style={"display": "none"})] + [ui.create_card_button(card) for card in new_workspace_cards],
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "justifyContent": "center",
                    "gap": "20px",
                    "paddingLeft": "50px",
                    "paddingRight": "50px",
                },
            ),
        ],
        id=f"{__name__}-content",
        style={
            "display": "flex",
            "justifyContent": "center",
            "alignItems": "center",
            "paddingTop": f"{padding}px",
            "paddingBottom": f"{padding}px",
        },
    ),
    html.H4(
        "Icons designed by Freepik from Flaticon",
        className="subtle-text",
        style={
            "textAlign": "center",
            "marginTop": "20px",
        }
    ),
    html.Div(style={"height": "10vh"}),  # Spacer at the bottom
]


######################################
# Callbacks
######################################

@dash.callback(
    Output("home-page-content", "children"),
    Input("url", "pathname"),
    Input("odatix-settings", "data"),
    prevent_initial_call=False,
)
def redirect_to_new_workspace(search, odatix_settings):
    triggered_id = dash.ctx.triggered_id
    if odatix_settings == {}:
        return new_workspace_layout
    else:
        return home_layout

@dash.callback(
    Output("odatix-settings", "data", allow_duplicate=True),
    Input("create-empty-workspace", "n_clicks"),
    Input("create-workspace-with-examples", "n_clicks"),
    prevent_initial_call=True,
)
def create_empty_workspace(n_clicks_empty, n_clicks_examples):
    triggered_id = dash.ctx.triggered_id
    success = False
    if triggered_id == "create-empty-workspace" and n_clicks_empty:
        success = OdatixSettings.init_directory_nodialog(include_examples=False, silent=True),
    elif triggered_id == "create-workspace-with-examples" and n_clicks_examples:
        success = OdatixSettings.init_directory_nodialog(include_examples=True, silent=True),
    if success: 
        odatix_settings = OdatixSettings()
        return odatix_settings.to_dict()
    return dash.no_update

######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id="url", refresh=False),
        html.Div(id="home-page-content"),
    ],
    id="home-page",
    className="page-content",
    style={
        "width": "100%", 
        "minHeight": f"calc(100vh - {navigation.top_bar_height})",
        "display": "flex",  
        "flexDirection": "column",
        "justifyContent": "center",
        "alignItems": "center",
    }
)

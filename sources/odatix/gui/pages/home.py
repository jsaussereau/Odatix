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
from dash import dcc, html, Input, Output

from odatix.components import home_shared
from odatix.gui.icons import pictogram
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
        "name": "Workflows",
        "link": "/workflows",
        "icon": "workflow",
        "description": "Configure your workflows",
    },
    {
        "name": "RTL Architectures",
        "link": "/architectures",
        "icon": "architecture",
        "description": "Configure your RTL architectures",
    },
    {
        "name": "Run Jobs",
        "link": "/choose_job_type",
        "icon": "run",
        "description": "Run workflows, RTL analysis, logic synthesis at Fmax and custom frequencies",
    },
    {
        "name": "Monitor Jobs",
        "link": "/monitor",
        "icon": "monitor",
        "description": "Monitor currently running jobs",
    },
    {
        "name": "Explore Results",
        "link": "/explorer",
        "icon": "explorer",
        "description": "Explore results in an interactive interface",
    },
    {
        "name": "Workspace Settings",
        "link": "/workspace",
        "icon": "workspace",
        "description": "Adjust workspace settings",
    },
    {
        "name": "Documentation",
        "link": "https://odatix.readthedocs.io",
        "icon": "documentation",
        "description": "Access Odatix online documentation",
    },
]


def _card_visual(card):
    icon_name = card.get("icon", "explorer")
    return pictogram(icon_name, size="48px", className="xp-card-pictogram")

home_layout = html.Div(
    [
        home_shared.home_header("Odatix", "Configure, run and explore your design space exploration."),
        home_shared.home_card_grid(home_cards, _card_visual),
    ],
    className="xp-home",
)


# New workspace page

new_workspace_cards = [
    {
        "name": "Empty workspace",
        "id": "create-empty-workspace",
        "icon": "workspace_empty",
        "description": "Start from scratch",
    },
    {
        "name": "Workspace with examples",
        "id": "create-workspace-with-examples",
        "icon": "workspace_examples",
        "description": "Get started quickly with pre-configured examples",
    },
]

new_workspace_layout = html.Div(
    [
        home_shared.home_header("Initialize an Odatix workspace", "Create a workspace in the current directory."),
        html.Div(
            [
                html.Div("Current directory", className="xp-source-name"),
                html.Div(f"{os.getcwd()}", className="xp-source-detail"),
            ],
            className="xp-source-card",
            style={"maxWidth": "1100px", "margin": "0 auto 24px auto"},
        ),
        home_shared.home_card_grid(new_workspace_cards, _card_visual),
    ],
    className="xp-home",
)


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
        "justifyContent": "flex-start",
        "alignItems": "stretch",
    }
)

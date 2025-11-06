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

import odatix.gui.navigation as navigation

dash.register_page(
    __name__,
    path='/',
    title='Odatix',
    name='Home',
)

######################################
# UI Components
######################################

def create_button(page):
    return dcc.Link(
        children=[
            html.Img(
                src=page["image"],
                className="card-img",
                style={"height": "125px"}
            ),
            html.Div(
                page["name"],
                className="card-title",
            ),
            html.Div(
                page["description"],
                className="card-description",
            ),
        ],
        className="card home hover",
        href=page["link"],
        style={"textDecoration": "none"},
    )

padding = 20


######################################
# Layout
######################################

cards = [
    {
        "name": "Architectures",
        "link": "/architectures",
        "image": "assets/icons/architecture.png",
        "description": "Configure your architectures",
    },
    # {
    #     "name": "Architectures and Simulations",
    #     "link": "/architectures",
    #     "image": "assets/icons/architecture.png",
    #     "description": "Configure your architectures and simulations",
    # },
    # {
    #     "name": "Run jobs",
    #     "link": "/run",
    #     "image": "assets/icons/run.png",
    #     "description": "Run synthesis and simulation",
    # },
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
]

layout = html.Div(
    children=[
        html.Div(
            [
                html.Div(
                    [create_button(card) for card in cards],
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
    ], 
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

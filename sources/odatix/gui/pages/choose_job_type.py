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

page_path = "/choose_job_type"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Choose Job Type',
    name='choose_job_type',
    order=8,
)

######################################
# UI Components
######################################

padding = 20

# Home page

run_jobs_cards = [
    {
        "name": "Run Fmax Synthesis",
        "link": "/choose_eda_tool?type=fmax_synthesis",
        "image": "assets/icons/run.png",
        "description": "Find the maximum frequency for your design",
    },
    {
        "name": "Run Custom Synthesis",
        "link": "/choose_eda_tool?type=custom_freq_synthesis",
        "image": "assets/icons/run.png",
        "description": "Run synthesis at custom frequencies",
    },
    # {
    #     "name": "Run Simulations",
    #     "link": "/choose_eda_tool?type=simulation",
    #     "image": "assets/icons/run.png",
    #     "description": "Run simulations for validation and benchmarks",
    # },
]

home_layout = [
    html.Div(
        children=[
            html.Div(
                [ui.create_card_button(card) for card in run_jobs_cards],
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

######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id="url", refresh=False),
        html.Div(
            children=home_layout,
            id="run_jobs-page-content"
        ),
    ],
    id="run_jobs-page",
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

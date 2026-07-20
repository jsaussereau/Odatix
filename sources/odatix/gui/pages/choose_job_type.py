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
    name='Run Jobs',
    order=6,
)

######################################
# UI Components
######################################

padding = 20

# Home page

run_jobs_cards = [
    {
        "name": "Run Workflow",
        "link":  "/run_jobs?type=workflow",
        "icon": "workflow",
        "description": "Run a workflow",
    },
    {
        "name": "Run RTL Analysis",
        "link": "/run_jobs?type=analyze",
        "icon": "analysis",
        "description": "Check if your RTL is synthetizable with the selected EDA tools",
    },
    {
        "name": "Run Fmax Synthesis",
        "link": "/choose_eda_tool?type=fmax_synthesis",
        "icon": "fmax",
        "description": "Find the maximum frequency for your design",
    },
    {
        "name": "Run Custom Synthesis",
        "link": "/choose_eda_tool?type=custom_freq_synthesis",
        "icon": "custom_freq",
        "description": "Run synthesis at custom frequencies",
    },
]

home_layout = [
    ui.page_header("Run Jobs", "Choose what you want to run.", back_link="/"),
    html.Div(
        ui.card_grid([ui.create_card_button(card) for card in run_jobs_cards]),
        id=f"{__name__}-content",
        style={
            "display": "flex",
            "justifyContent": "center",
            "paddingBottom": f"{padding}px",
        },
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
        "justifyContent": "flex-start",
        "alignItems": "stretch",
    }
)

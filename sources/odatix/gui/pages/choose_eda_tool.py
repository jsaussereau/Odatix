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
from odatix.gui.utils import get_key_from_url

page_path = "/choose_eda_tool"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Choose EDA Tool',
    name='choose_eda_tool',
    order=9,
)

######################################
# UI Components
######################################

padding = 20

def get_run_jobs_cards(job_type):
    return [
        {
            "name": "Vivado",
            "link": f"/jobs_config?type={job_type}&tool=vivado",
            "image": "assets/icons/vivado.png",
            "description": "AMD/Xilinx Vivado™",
        },
        {
            "name": "Design Compiler",
            "link": f"/jobs_config?type={job_type}&tool=design_compiler",
            "image": "assets/icons/synopsys.png",
            "description": "Synopsys® Design Compiler®",
        },
        {
            "name": "OpenLane",
            "link": f"/jobs_config?type={job_type}&tool=openlane",
            "image": "assets/icons/openroad.png",
            "description": "Open Source OpenLane flow",
        },
    ]
def get_run_jobs_layout(job_type):
    return [
        html.Div(
            children=[
                html.Div(
                    [ui.create_card_button(card) for card in get_run_jobs_cards(job_type)],
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
# Callbacks
######################################

@dash.callback(
    Output("run_jobs_tool-page-content", "children"),
    Input("url", "search"),
    prevent_initial_call=False,
)
def redirect_to_new_workspace(search):
    job_type = get_key_from_url(search, "type")
    return get_run_jobs_layout(job_type)

######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id="url", refresh=False),
        html.Div(
            id="run_jobs_tool-page-content"
        ),
    ],
    id="run_jobs_tool-page",
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

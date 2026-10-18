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
from dash import html
import odatix.gui.navigation as navigation
import odatix.gui.ui_components as ui
from odatix.gui.icons import icon

dash.register_page(
    __name__,
    name='PageNotFound'
)

######################################
# Layout
######################################

layout = html.Div(
    children=[
        html.Div(
            children=[
                html.H1("404"),
                html.H2("Page not found"),
                html.P("This address is not a page of Odatix GUI: the link may be out of date, or mistyped."),
                html.Div(
                    ui.icon_button(
                        icon=icon("back", className="icon"),
                        color="primary",
                        text="Back to home",
                        link="/",
                        id="p404-home",
                        width="150px",
                    ),
                    style={"display": "flex", "justifyContent": "center", "marginBottom": "14px"},
                ),
            ],
            className="tile center"
        ),
    ],
    className="page-content",
    id="p404-container",
    style={
        "width": "100%", 
        "minHeight": f"calc(100vh - {navigation.top_bar_height})",
        "display": "flex",  
        "flexDirection": "column",
        "alignItems": "center",
    },
)

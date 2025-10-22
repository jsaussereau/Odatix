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
                html.H1("404", id="p404-h1"),
                html.H2("Oops, page not found!", id="p404-h2")
            ],
            id="p404",
            className="tile"
        ),
    ],
    className="page-content",
    id="p404-container",
    style={
        "width": "100%", 
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
        "display": "flex",  
        "flex-direction": "column",
        "align-items": "center",
    },
)

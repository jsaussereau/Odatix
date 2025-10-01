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

from dash import html

def delete_button(id, large=False):
    return html.Button(
        html.Div(
            children=[
                html.Img(
                    src="/assets/icons/delete.svg",
                    alt="Delete",
                    style={
                        "width": "25px",
                        "height": "25px",
                        "marginLeft": "-10px",
                    }
                ),
                html.Span(
                    "Delete" if large else "",
                    style={"fontWeight": "bold", "fontSize": "1em", "marginLeft": "5px"} if large else {}
                ),
            ],
            style={"display": "flex", "alignItems": "center", "justifyContent": "flex-start", "marginTop": "-3px",}
        ),
        id=id,
        n_clicks=0,
        className="color-button red icon-button",
        style={"width": "120px"} if large else {},
    )


def duplicate_button(id, large=False):
    return html.Button(
        html.Div(
            children=[
                html.Img(
                    src="/assets/icons/duplicate.svg",
                    alt="Duplicate",
                    style={
                        "width": "25px",
                        "height": "25px",
                        "marginLeft": "-10px",
                    }
                ),
                html.Span(
                    "Duplicate" if large else "",
                    style={"fontWeight": "bold", "fontSize": "1em", "marginLeft": "5px"} if large else {}
                ),
            ],
            style={"display": "flex", "alignItems": "center", "justifyContent": "flex-start", "marginTop": "-3px",}
        ),
        id=id,
        n_clicks=0,
        className=f"color-button blue icon-button",
        style={"width": "120px"} if large else {},
    )

        ),
        id=id,
        n_clicks=0,
        className="color-button blue icon-button",
    )
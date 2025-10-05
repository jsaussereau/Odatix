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

from dash_svg import Svg
from dash import html, dcc

from odatix.gui.icons import icon

def icon_button(icon, color, text="", id=None, link=None, multiline=False, width="115px"):  
    """
    Create a button with an icon and optional text.
    Args:
        icon (str or Svg): The icon to display (filename in assets/icons or Svg component).
        color (str): The color of the button (e.g., "red", "blue", "green").
        text (str, optional): The text to display next to the icon. Defaults to "" (just the icon).
        id (str, optional): The id of the button. Defaults to None.
        link (str, optional): If provided, the button will be a link to this URL. Defaults to None.
        multiline (bool, optional): If True, adjust vertical alignment for multiline text. Defaults to False.
    """ 
    content = html.Button(
        html.Div(
            children=[
                icon if isinstance(icon, Svg) else html.Img(
                    src=f"/assets/icons/{icon}",
                    alt=text if text else icon.capitalize(),
                    style={
                        "width": "25px",
                        "height": "25px",
                        "marginLeft": "-10px",
                    }
                ),
                html.Span(
                    text,
                    style={"fontWeight": "bold", "fontSize": "1em", "marginLeft": "5px"} if text else {}
                ),
            ],
            style={"display": "flex", "alignItems": "center", "justifyContent": "flex-start", "marginTop": "-9px" if multiline else "-4px", "width": "100%"},
        ),
        id=id,
        n_clicks=0,
        className=f"color-button {color} icon-button",
        style={"min-width": width} if text else {},
    )
    if link is None:
        return content
    else:
        return dcc.Link(
            content,
            href=link,
            style={"textDecoration": "none"},
        )

def delete_button(id, large=False):
    return icon_button(
        icon=icon("delete", width="25px", height="25px", className="icon red"),
        color="red", 
        text="Delete" if large else "", 
        id=id,
    )

def duplicate_button(id, large=False):
    return icon_button(
        icon=icon("duplicate", className="icon blue"),
        color="blue",
        text="Duplicate" if large else "", 
        id=id,
    )

def save_button(id, large=False):
    return icon_button(
        icon=icon("save", className="icon orange"),
        color="orange",
        text="Save All" if large else "", 
        id=id,
    )

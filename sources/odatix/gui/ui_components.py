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

from typing import Optional
from dash_svg import Svg
from dash import html, dcc
from dash.development.base_component import Component

from odatix.gui.icons import icon

def icon_button(icon, color, text="", id=None, link=None, multiline=False, width="115px", style={}, tooltip:str="", tooltip_options:str="bottom"):  
    """
    Create a button with an icon and optional text.
    Args:
        icon (str or Svg): The icon to display (filename in assets/icons or Svg component).
        color (str): The color of the button (e.g., "red", "blue", "green").
        text (str, optional): The text to display next to the icon. Defaults to "" (just the icon).
        id (str, optional): The id of the button. Defaults to None.
        link (str | dict, optional): If provided, the button will be a link to this URL. Defaults to None.
        multiline (bool, optional): If True, adjust vertical alignment for multiline text. Defaults to False.
    """ 
    if text:
        style = {**style, "min-width": width}
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
                    style={"fontWeight": "600", "fontSize": "1em", "marginLeft": "5px"} if text else {}
                ),
            ],
            style={"display": "flex", "alignItems": "center", "justifyContent": "flex-start", "marginTop": "-9px" if multiline else "-4px", "width": "100%"},
        ),
        id=id if id else "",
        n_clicks=0,
        className=f"color-button {color} icon-button {f' tooltip {tooltip_options}' if tooltip else ''}",
        style=style,
        **{'data-tooltip': tooltip},
    )
    if link is None:
        return content
    else:
        link_kwargs = {
            "children": content,
            "href": link,
            "style": {"textDecoration": "none"}
        }
        if isinstance(id, dict):
            link_id = id.copy()
            link_id.update({"is_link": True})
        elif isinstance(id, str):
            link_id = id + "-link"
        else:   
            link_id = None
        if link_id is not None:
            link_kwargs["id"] = link_id
        return dcc.Link(**link_kwargs)

def delete_button(id, large=False, tooltip:str="Delete"):
    return icon_button(
        icon=icon("delete", width="25px", height="25px", className="icon red"),
        color="caution", 
        text="Delete" if large else "", 
        tooltip=tooltip,
        tooltip_options="bottom auto",
        id=id,
    )

def duplicate_button(id, large=False, tooltip:str="Duplicate"):
    return icon_button(
        icon=icon("duplicate", className="icon blue"),
        color="secondary",
        text="Duplicate" if large else "", 
        tooltip=tooltip,
        tooltip_options="bottom auto",
        id=id,
    )

def save_button(id, text="Save All", disabled=False, tooltip:str="Save all changes"):
    if isinstance(id, dict):
        icon_id = id.copy()
        icon_id.update({"is_icon": True})
    else:
        icon_id = id + "-icon"

    return icon_button(
        icon=icon("save", className="icon", id=icon_id),
        color="warning",
        text=text, 
        tooltip=tooltip,
        tooltip_options="bottom auto caution",
        id=id,
    )


def title_tile(text:str="", id:str="main-title", buttons:html.Div=html.Div(), back_button_link:Optional[str]=None, back_button_id:Optional[str]=None, tooltip:str=""):
    title_content = html.Div(
        children=[
            html.Div(
                children=[
                    html.H3(text, id=id, style={"marginBottom": "0px", "display": "inline-block"}),
                    tooltip_icon(tooltip) if tooltip else html.Div(style={"display": "none"}),
                ],
            ),
            html.Div(
                [buttons],
            ),
        ],
        className="title-tile-flex",
        style={
            "display": "flex",
            "alignItems": "center",
            "padding": "0px",
            "justifyContent": "space-between",
        }
    )
    return html.Div(
        html.Div(
            children=[
                back_button(link=back_button_link, id=back_button_id),
                title_content
            ],
            className="tile title",
            style={"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "10px", "marginBottom": "0px"},
    )

def subtitle_div(text:str="", id:str="main-title", buttons:html.Div=html.Div()):
    title_content = html.Div([
        html.H3(text, id=id, style={"marginBottom": "0px"}),
        html.Div(
            [buttons],
        ),
    ],
    className="title-tile-flex",
    style={
        "display": "flex",
        "alignItems": "center",
        "padding": "0px",
        "margin-right": "-15px",
        "margin-top": "0px",
        "justifyContent": "space-between",
    })
    return title_content

def back_button(link: Optional[str]="/", id: Optional[str]="back-button"):
    if link is None and id is None:
        return html.Div()
    if link:
        button = dcc.Link(
            icon("back", className="icon back-button", width="30px", height="30px"),
            href=link,
            id=id,
            style={"textDecoration": "none"},
        )
    else:
        button = html.Button(
            icon("back", className="icon back-button", width="30px", height="30px"),
            id=id,
            n_clicks=0,
            style={"background": "none", "border": "none", "padding": "0px", "margin": "0px"},
        )
    return html.Div(
        button,
        style={
            "position": "absolute",
            "display": "flex",
            "alignItems": "center",
            "left": "0",
            "top": "0",
            "height": "100%",
            "width": "45px",
            "transform": "translate(-45px)",
        },
    )

def tooltip_icon(tooltip: str="", tooltip_options: str="secondary") -> Component:
    return html.Div(
        children=[
            icon(
                "tooltip",
                className="icon",
                color="default",
                width="20px",
                height="20px",
            ),
        ],
        className="tooltip " + tooltip_options,
        style={"display": "inline-block", "transform": "translate(15px, 2px)", "verticalAlign": "middle"},
        **{'data-tooltip': tooltip},
    )

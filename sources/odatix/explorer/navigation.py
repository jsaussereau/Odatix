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
from dash.dependencies import Input, Output, State

side_bar_width = "400px"


def top_bar(page_name=""):
  return html.Div(
    [
      html.Div(
        id=f"navbar-title-{page_name}",
        children=[
          dcc.Link("Odatix Explorer", href="/", className="title"),
        ],
        style={"marginLeft": "30px", "transition": "margin-left 0.25s"},
      ),
      html.Div(),
      html.Div(
        [
          dcc.Link("XY", href="/xy", className="nav-link"),
          dcc.Link("VS", href="/vs", className="nav-link"),
          dcc.Link("Radar", href="/radar", className="nav-link"),
          # dcc.Link('Help', href='/help', className='nav-link')
        ],
        className="nav-links",
      ),
    ],
    className="navbar",
  )


def side_bar(content, page_name=""):
  return html.Div(
    [
      html.Div(id=f"sidebar-top-{page_name}", className="sidebar-top", style={"left": "0", "width": side_bar_width}),
      html.Img(
        id=f"toggle-button-{page_name}",
        src="/assets/icons/sidebar-panel-expand-icon.svg",
        n_clicks=0,
        style={
          "display": "none",
          "cursor": "pointer",
          "position": "absolute",
          "top": "10px",
          "left": "20px",
          "width": "30px",
        },
      ),
      html.Div(
        id=f"sidebar-{page_name}",
        children=[
          html.Img(
            id=f"close-button-{page_name}",
            src="/assets/icons/sidebar-panel-collapse-icon.svg",
            n_clicks=0,
            style={"cursor": "pointer", "position": "absolute", "top": "10px", "left": "20px", "width": "30px"},
          ),
          html.Div(children=[content], className="sidebar-content", style={"width": side_bar_width}),
        ],
        className="sidebar",
        style={"left": "0", "width": side_bar_width},
      ),
    ]
  )


def setup_sidebar_callbacks(explorer, page_name=""):
  @explorer.app.callback(
    [
      Output(f"sidebar-{page_name}", "style"),
      Output(f"content-{page_name}", "style"),
      Output(f"navbar-title-{page_name}", "style"),
      Output(f"sidebar-top-{page_name}", "style"),
      Output(f"toggle-button-{page_name}", "style"),
    ],
    [Input(f"toggle-button-{page_name}", "n_clicks"), Input(f"close-button-{page_name}", "n_clicks")],
    [
      State(f"sidebar-{page_name}", "style"),
      State(f"content-{page_name}", "style"),
      State(f"navbar-title-{page_name}", "style"),
      State(f"sidebar-top-{page_name}", "style"),
      State(f"toggle-button-{page_name}", "style"),
    ],
  )
  def toggle_sidebar(
    toggle_n_clicks, close_n_clicks, sidebar_style, content_style, navbar_style, sidebar_top, toggle_style
  ):
    ctx = dash.callback_context
    if not ctx.triggered:
      return sidebar_style, content_style, navbar_style, sidebar_top, toggle_style

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == f"toggle-button-{page_name}":
      if sidebar_style["left"] == "-" + side_bar_width:
        sidebar_style["left"] = "0"
        sidebar_top["left"] = "0"
        content_style["marginLeft"] = side_bar_width
        navbar_style["marginLeft"] = "30px"
        navbar_style["position"] = "fixed"
        toggle_style["display"] = "none"
      else:
        sidebar_style["left"] = "-" + side_bar_width
        sidebar_top["left"] = "-" + side_bar_width
        content_style["marginLeft"] = "0"
        navbar_style["marginLeft"] = "0"
        navbar_style["position"] = "relative"
        toggle_style["display"] = "block"
    elif button_id == f"close-button-{page_name}":
      sidebar_style["left"] = "-" + side_bar_width
      sidebar_top["left"] = "-" + side_bar_width
      content_style["marginLeft"] = "0"
      navbar_style["marginLeft"] = "0"
      navbar_style["position"] = "relative"
      toggle_style["display"] = "block"

    return sidebar_style, content_style, navbar_style, sidebar_top, toggle_style

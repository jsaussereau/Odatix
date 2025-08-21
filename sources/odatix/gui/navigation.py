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
import plotly.io as pio

import odatix.gui.themes as themes
import odatix.components.motd as motd

from odatix.gui.css_helper import Style

top_bar_height = "50px"
side_bar_width = "0px"

banned_pages = ["PageNotFound", "Home"]
sidebar_urls = ["/lines", "/columns", "/scatter", "/scatter3d", "/radar", "/overview"]

def top_bar(explorer):
  version = motd.read_version()

  return html.Div(
    [
      dcc.Link(
        id="navbar-title",
        className="link",
        href="/",
        children=[
          html.Span(
            html.Div(
              [
                html.Span("Odatix " + str(version), className="link-title1 title"),
                html.Span("Home", className="link-title2 title"),
              ],
              className="link-container"
            ),
            className="mask"
          )
        ],
        style={"position": "block", "margin-left": "30px", "left": "75px", "z-index": "2", "transition": "margin-left 0.25s"},
      ),
      html.Div(),
      html.Div(
        [
          html.Div(
            dcc.Link(f"{page['name']}", href=page["relative_path"], className="nav-link"),
          ) for page in dash.page_registry.values() if page["name"] not in banned_pages
        ],
        className="nav-links",
      ),
    ],
    style={"height": f"{top_bar_height}", "backgroundColor": "#24292e",},
    className="navbar",
    id="navbar",
  )


def side_bar(explorer):

  return html.Div(
    [
      html.Div(
        id="sidebar-top",
        className="sidebar-top",
        style={"top": "0px", "left": "0px", "width": side_bar_width, "height": f"{top_bar_height}"},
      ),
      html.Img(
        id="toggle-button",
        className="sidebar-button",
        src="/assets/icons/sidebar-panel-expand-icon.svg",
        n_clicks=0,
        style={
          "display": "none",
          "cursor": "pointer",
          "position": "absolute",
          "top": "10px",
          "left": "20px",
          "width": "30px",
          "z-index": "3",
        },
      ),
      # html.Div(
      #   id="sidebar",
      #   children=[
      #     html.Img(
      #       id="close-button",
      #       className="sidebar-button",
      #       src="/assets/icons/sidebar-panel-collapse-icon.svg",
      #       n_clicks=0,
      #       style={"cursor": "pointer", "position": "absolute", "top": "10px", "left": "20px", "width": "30px"},
      #     ),

      #   ],
      #   className="sidebar",
      #   style={"left": "0", "width": side_bar_width},
      # ),
    ]
  )


def setup_sidebar_callbacks(gui):
  pass
  # @gui.app.callback(
  #   [
  #     Output("navbar", "style"), 
  #     Output("navbar-title", "style"),
  #   ],
  #   [
  #     Input("url", "pathname"),
  #   ],
  #   [
  #     State("navbar", "style"),
  #     State("navbar-title", "style"),
  #   ],
  # )
  # def toggle_sidebar(
  #   navbar_style, navbar_title_style
  # ):

  #   theme = "default"
  #   bar_background = themes.get_nav_bgcolor(theme)
  #   navbar_style["backgroundColor"] = bar_background
  #   navbar_title_style["backgroundColor"] = bar_background

  #   return  navbar_style, navbar_title_style

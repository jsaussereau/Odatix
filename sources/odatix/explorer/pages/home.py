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

import odatix.explorer.navigation as navigation

dash.register_page(
  __name__,
  path='/',
  title='Odatix',
  name='Home',
)

cards = [
  {
    "name": "Lines / Points",
    "link": "/lines",
    "image": "assets/preview/lines.svg",
    "description": "A line chart to draw values for a specific metric",
  },
  {
    "name": "Columns",
    "link": "/columns",
    "image": "assets/preview/columns.svg",
    "description": "A column chart to draw values for a specific metric",
  },
  {
    "name": "Radar",
    "link": "/radar",
    "image": "assets/preview/radar.svg",
    "description": "A radar chart to draw values for a specific metric",
  },
  {
    "name": "Scatter",
    "link": "/scatter",
    "image": "assets/preview/scatter.svg",
    "description": "A scatter chart to draw a metric against another",
  },
  {
    "name": "Scatter 3D",
    "link": "/scatter3d",
    "image": "assets/preview/scatter3d.svg",
    "description": "A 3D scatter chart to draw a metric against another",
  },
  {
    "name": "Overview",
    "link": "/overview",
    "image": "assets/preview/overview.png",
    "description": "A collection of lines/columns/radar charts for all metrics",
  },
]

def create_button(page):
  return dcc.Link(
    html.Div(
      [
        html.Img(
          src=page["image"],
          className="card-img",
          style={"height": "300px"}
        ),
        html.Div(
          page["name"],
          className="card-title",
        ),
        html.Div(
          page["description"],
          className="card-description",
        ),
      ],
      className="card",
    ),
    href=page["link"],
    style={"text-decoration": "none"},
  )

padding = 20

layout = html.Div(
  [
    html.Div(
      [create_button(card) for card in cards],
      style={
        "display": "flex",
        "flex-wrap": "wrap",
        "justify-content": "center",
        "gap": "20px",
        "padding-left": "50px",
        "padding-right": "50px",
      },
    ),
  ],
  id=f"{__name__}-content",
  style={
    "width": "100%", 
    "min-height": f"calc(100vh - 1.8*{navigation.top_bar_height}",
    "display": "flex",
    "justify-content": "center",
    "align-items": "center",
    "padding-top": f"{padding}px",
    "padding-bottom": f"{padding}px",
  },
  className="home-content",
)

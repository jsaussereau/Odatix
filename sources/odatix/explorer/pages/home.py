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

import odatix.explorer.navigation as navigation

dash.register_page(
  __name__,
  path='/',
  title='Odatix',
  name='Home',
)

pages = [
  {"name": "Lines / Points", "link": "/lines", "image": "assets/preview/lines.svg"},
  {"name": "Columns", "link": "/columns", "image": "assets/preview/columns.svg"},
  {"name": "Scatter", "link": "/scatter", "image": "assets/preview/scatter.svg"},
  {"name": "Radar", "link": "/radar", "image": "assets/preview/radar.svg"},
]

def create_button(page):
  return html.A(
    html.Div(
      [
        html.Img(src=page["image"], style={"height": "300px", "margin": "auto", "object-fit": "cover"}),
        html.Div(
          page["name"],
          style={"text-align": "center", "margin-top": "10px", "color": "black", "font-weight": "bold"},
        ),
      ],
      style={
        "min-width": "0",
        "max-width": "100%",
        "width": "450px",
        "height": "390px",
        "box-shadow": "0px 4px 6px rgba(0,0,0,0.1)",
        "border": "1px solid #ddd",
        "border-radius": "8px",
        "overflow": "hidden",
        "cursor": "pointer",
        "display": "flex",
        "flex-direction": "column",
        "justify-content": "space-between",
        "text-decoration": "none",
      },
    ),
    href=page["link"],
    style={"text-decoration": "none"},
  )

padding = 20

layout = html.Div(
  [
    html.Div(
      [create_button(page) for page in pages],
      style={
        "display": "flex",
        "flex-wrap": "wrap",
        "justify-content": "center",
        "gap": "20px",
      },
    ),
  ],
  id=f"{__name__}-content",
  style={
    "width": "100%", 
    "min-height": f"calc(100vh - {navigation.top_bar_height} - {2*padding}px)",
    "display": "flex",
    "justify-content": "center",
    "align-items": "center",
    "padding-top": f"{padding}px",
    "padding-bottom": f"{padding}px",
  },
)

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
import plotly.express as px
import re

plot_colors = px.colors.qualitative.Plotly


def create_legend_items(explorer, page_name=""):
  legend_items = [
    create_legend_item(
      architecture=architecture, line_style="2px dashed", color=plot_colors[i % len(plot_colors)], page_name=page_name
    )
    for i, architecture in enumerate(explorer.all_architectures)
  ]
  return legend_items


def create_legend_item(architecture, line_style, color, page_name=""):
  return html.Div(
    [
      dcc.Checklist(
        id=f"checklist-{architecture}-{page_name}",
        options=[{"label": "", "value": architecture}],
        value=[architecture],
        inline=True,
        style={"display": "inline-block", "margin-right": "10px", "text-wrap": "wrap"},
      ),
      html.Div(
        style={
          "display": "inline-block",
          "width": "30px",
          "height": "2px",
          "border-top": f"{line_style} {color}",
          "position": "relative",
        },
        children=html.Div(
          style={
            "position": "absolute",
            "top": "-6px",
            "left": "50%",
            "transform": "translateX(-50%)",
            "width": "10px",
            "height": "10px",
            "background-color": color,
            "border-radius": "50%",
          }
        ),
      ),
      html.Div(f"{architecture}", style={"display": "inline-block", "margin-left": "5px"}),
    ],
    id=f"legend-item-{architecture}-{page_name}",
    style={"display": "block", "margin-bottom": "5px"},
  )


def setup_callbacks(explorer, page_name):
  @explorer.app.callback(
    [Output(f"checklist-{architecture}-{page_name}", "value") for architecture in explorer.all_architectures],
    [Input("show-all", "n_clicks"), Input("hide-all", "n_clicks")],
    [State(f"checklist-{architecture}-{page_name}", "value") for architecture in explorer.all_architectures],
  )
  def update_checklist_states(show_all_clicks, hide_all_clicks, *current_values):
    ctx = dash.callback_context
    if not ctx.triggered:
      return dash.no_update

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id == "show-all":
      return [[architecture] for architecture in explorer.all_architectures]
    elif button_id == "hide-all":
      return [[] for _ in explorer.all_architectures]

    return current_values

  @explorer.app.callback(
    [Output(f"legend-item-{architecture}-{page_name}", "style") for architecture in explorer.all_architectures],
    [Input(f"target-dropdown-{page_name}", "value"), Input("yaml-dropdown", "value")],
  )
  def update_legend_visibility(selected_target, selected_yaml):
    if not selected_yaml or selected_yaml not in explorer.dfs:
      return [{"display": "none"} for _ in explorer.all_architectures]

    architectures_for_target = explorer.dfs[selected_yaml][explorer.dfs[selected_yaml]["Target"] == selected_target][
      "Architecture"
    ].unique()
    return [
      {"display": "block" if architecture in architectures_for_target else "none"}
      for architecture in explorer.all_architectures
    ]


def get_color(i):
  return plot_colors[i % len(plot_colors)]

def unit_to_html(unit):
  # Regex pattern to match ^(-?\d+) for positive/negative exponents
  pattern = r'\^(-?\d+)'
  html_unit = re.sub(pattern, r'<sup>\1</sup>', unit)

  # Regex pattern to match _(-?\d+) for positive/negative subscripts
  pattern_sub = r'\_(-?\d+)'
  unit_with_sub = re.sub(pattern_sub, r'<sub>\1</sub>', html_unit)

  return unit_with_sub
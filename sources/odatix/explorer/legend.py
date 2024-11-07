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
marker_symbols = ["circle", "square", "diamond", "triangle-up", "cross", "triangle-down", "pentagon", "x", "star"]

def create_legend_items(explorer, page_name="", color_mode="Architecture", symbol_mode="Target"):
  legend_items = [
    create_legend_item(
      label=architecture, 
      line_style="2px dashed",
      color=get_color(i) if color_mode == "Architecture" else "#000",  # Appliquer la couleur en fonction du mode
      page_name=page_name,
      type="arch",
      marker_symbol=i if symbol_mode == "Architecture" else 0,  # Appliquer le symbole en fonction du mode
    )
    for i, architecture in enumerate(explorer.all_architectures)
  ]
  return legend_items


def create_legend_item(label, line_style, color, page_name="", type="arch", marker_symbol=0, draw_line=True, display=True):  
  line_color = color if draw_line else "00000000"
  return html.Div(
    [
      dcc.Checklist(
        id=f"checklist-{type}-{label}-{page_name}",
        options=[{"label": "", "value": label}],
        value=[label],
        inline=True,
        style={"display": "inline-block", "margin-right": "10px", "text-wrap": "wrap"},
      ),
      html.Div(
        style={
          "display": "inline-block",
          "width": "30px",
          "height": "2px",
          "border-top": f"{line_style} {line_color}",
          "position": "relative",
        },
        children=get_legend_marker_symbol(marker_symbol, color),
      ),
      html.Div(f"{label}", style={"display": "inline-block", "margin-left": "5px"}),
    ],
    id=f"legend-item-{type}-{label}-{page_name}",
    style={"display": "block" if display else "none", "margin-top": "2.5px", "margin-bottom": "2.5px"},
  )

def create_target_legend_items(explorer, page_name="", color_mode="Target", symbol_mode="Target"):
  legend_items = [
    create_legend_item(
      label=target,
      line_style="2px dashed",
      color=get_color(i) if color_mode == "Target" else "#fff", 
      page_name=page_name,
      type="target",
      marker_symbol=i if symbol_mode == "Target" else 0,
      draw_line=False,
    )
    for i, target in enumerate(explorer.all_targets)
  ]
  return legend_items

def setup_callbacks(explorer, page_name):

  # Architectures 
  @explorer.app.callback(
    [Output(f"checklist-arch-{architecture}-{page_name}", "value") for architecture in explorer.all_architectures],
    [Input("show-all", "n_clicks"), Input("hide-all", "n_clicks")],
    [State(f"checklist-arch-{architecture}-{page_name}", "value") for architecture in explorer.all_architectures],
  )
  def update_arch_checklist_states(show_all_clicks, hide_all_clicks, *current_values):
    ctx = dash.callback_context
    if not ctx.triggered:
      return current_values

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id == "show-all":
      return [[architecture] for architecture in explorer.all_architectures]
    elif button_id == "hide-all":
      return [[] for _ in explorer.all_architectures]

    return current_values

  @explorer.app.callback(
    Output(f"custom-legend-{page_name}", "children"),
    [
      Input("yaml-dropdown", "value"),
      Input("color-mode-dropdown", "value"),
      Input("symbol-mode-dropdown", "value"),
    ]
  )
  def update_architecture_legend(selected_yaml, color_mode, symbol_mode):
    try:
      if not selected_yaml or selected_yaml not in explorer.dfs:
        return []

      yaml_architectures = explorer.dfs[selected_yaml]["Architecture"].unique()
      legend_items = []

      for i, architecture in enumerate(explorer.all_architectures):
        if architecture in yaml_architectures:
          display = True
        else:
          display = False
        
        color = get_color(i) if color_mode == "architecture" else "#fff"
        marker_symbol = i if symbol_mode == "architecture" else 0

        legend_item = create_legend_item(
          label=architecture,
          line_style="2px dashed",
          color=color,
          page_name=page_name,
          type="arch",
          marker_symbol=marker_symbol,
          draw_line=True,
          display=display
        )
        legend_items.append(legend_item)
    except Exception as e:
      print(f"Error in update_architecture_legend: {e}")
    return legend_items

  # Targets
  @explorer.app.callback(
    [Output(f"checklist-target-{target}-{page_name}", "value") for target in explorer.all_targets],
    [Input("show-all-targets", "n_clicks"), Input("hide-all-targets", "n_clicks")],
    [State(f"checklist-target-{target}-{page_name}", "value") for target in explorer.all_targets],
  )
  def update_target_checklist_states(show_all_clicks, hide_all_clicks, *current_values):
    ctx = dash.callback_context
    if not ctx.triggered:
      return current_values

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id == "show-all-targets":
      return [[target] for target in explorer.all_targets]
    elif button_id == "hide-all-targets":
      return [[] for _ in explorer.all_targets]

    return current_values

  @explorer.app.callback(
    Output(f"target-legend-{page_name}", "children"),
    [
      Input("yaml-dropdown", "value"),
      Input("color-mode-dropdown", "value"),
      Input("symbol-mode-dropdown", "value"),
    ]
  )
  def update_target_legend(selected_yaml, color_mode, symbol_mode):
    if not selected_yaml or selected_yaml not in explorer.dfs:
      return []

    yaml_targets = explorer.dfs[selected_yaml]["Target"].unique()
    legend_items = []

    i_marker = -1 
    for target in explorer.all_targets:
      if target in yaml_targets:
        display = True
        i_marker += 1
      else:
        display = False
      
      color = get_color(i_marker) if color_mode == "target" else "#fff"
      marker_symbol = i_marker if symbol_mode == "target" else 0

      legend_item = create_legend_item(
        label=target,
        line_style="2px dashed",
        color=color,
        page_name=page_name,
        type="target",
        marker_symbol=marker_symbol,
        draw_line=True,
        display=display
      )
      legend_items.append(legend_item)

    return legend_items

def get_color(i):
  return plot_colors[i % len(plot_colors)]

def get_marker_symbol(i):
  return marker_symbols[i % len(marker_symbols)]

def get_legend_marker_symbol(marker_symbol, color="white"):
  marker_symbol_styles = {
    "circle": {"background-color": color, "border-radius": "50%"},
    "square": {"background-color": color, "border-radius": "0"},
    "diamond": {"background-color": color, "transform": "rotate(45deg)", "left": "33%"},
    "cross": {},
    "x": {"left": "40%", "top": "-11px", "font-size": "18px"},
    "cross": {"left": "42%", "top": "-15px"},
    "triangle-up": {"left": "45%", "top": "-19px"},
    "triangle-down": {"left": "45%", "top": "-18px"},
    "pentagon": {"left": "42%", "top": "-10px", "font-size": "15px",},
    "star": {"left": "35%", "top": "-12px", "font-size": "20px",},
  }

  text = {
    "circle": "",
    "square": "",
    "diamond": "",
    "cross": "+",
    "x": "✖",
    "triangle-up": "▴",
    "triangle-down": "▾",
    "pentagon": "⬟",
    "star": "★",
  }


  try:
    marker_style = marker_symbol_styles.get(marker_symbols[marker_symbol], marker_symbol_styles["circle"])
    text = text.get(marker_symbols[marker_symbol], "")
  except Exception as e:
    marker_style = marker_symbol_styles["circle"]
    text = ""

  return html.Div(
    children=html.Div(
      text,
      style={
        "font-weight": "bold",
      }
    ),
    style={
      "font-size": "25px",
      "position": "absolute",
      "top": "-6px",
      "left": "50%",
      "transform": "translateX(-50%)",
      "color": color,
      "width": "10px",
      "height": "10px",
      **marker_style,  # Apply the marker style
    }
  )

def unit_to_html(unit):
  # Regex pattern to match ^(-?\d+) for positive/negative exponents
  pattern = r'\^(-?\d+)'
  html_unit = re.sub(pattern, r'<sup>\1</sup>', unit)

  # Regex pattern to match _(-?\d+) for positive/negative subscripts
  pattern_sub = r'\_(-?\d+)'
  unit_with_sub = re.sub(pattern_sub, r'<sub>\1</sub>', html_unit)

  return unit_with_sub
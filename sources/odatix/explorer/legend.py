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
marker_symbols = ["circle", "square", "diamond", "cross", "x", "triangle-up", "triangle-down", "pentagon", "star"]
marker_symbols_3d = ["circle", "square", "diamond", "cross", "x", "circle-open", "diamond-open", "square-open"]
patterns = ['', '/', 'x', '-', '|', '+', '.', '\\']
greyed_color = "#aaa"

def create_legend_item(label, value, line_style, color, type="arch", marker_symbol=0, draw_line=True, display=True, marker_3d=False):  
  line_color = color if draw_line else "00000000"
  return html.Div(
    [
      dcc.Checklist(
        id=f"checklist-{type}-{label}",
        options=[{"label": "", "value": label}],
        value=value,
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
        children=get_legend_marker_symbol(marker_symbol, color, marker_3d=marker_3d),
      ),
      html.Div(f"{label}", style={"display": "inline-block", "margin-left": "5px"}),
    ],
    id=f"legend-item-{type}-{label}",
    style={"display": "block" if display else "none", "margin-top": "2.5px", "margin-bottom": "2.5px"},
  )

def create_legend_items(explorer, color_mode="Architecture", symbol_mode="Target", marker_3d=False):
  legend_items = [
    create_legend_item(
      label=architecture, 
      value=[architecture],
      line_style="2px dashed",
      color=get_color(i) if color_mode == "Architecture" else "#000",
      type="arch",
      marker_symbol=i if symbol_mode == "Architecture" else 0,
      marker_3d=marker_3d,
    )
    for i, architecture in enumerate(explorer.all_architectures)
  ]
  return legend_items

def create_target_legend_items(explorer, color_mode="Target", symbol_mode="Target", marker_3d=False):
  legend_items = [
    create_legend_item(
      label=target,
      value=[target],
      line_style="2px dashed",
      color=get_color(i) if color_mode == "Target" else "#fff", 
      type="target",
      marker_symbol=i if symbol_mode == "Target" else 0,
      draw_line=False,
      marker_3d=marker_3d,
    )
    for i, target in enumerate(explorer.all_targets)
  ]
  return legend_items

def create_domain_legend_items(explorer, color_mode="Domain", symbol_mode="Domain", marker_3d=False):
  legend_items = []
  for domain in explorer.all_param_domains.keys():
    for i, config in enumerate(explorer.all_param_domains[domain]):
      legend_items.append(
        create_legend_item(
          label=config,
          value=[config],
          line_style="2px dashed",
          color=get_color(i) if color_mode == "Domain" else "#fff", 
          type=f"domains-{domain}",
          marker_symbol=i if symbol_mode == "Domain" else 0,
          draw_line=False,
          marker_3d=marker_3d,
        )
      )
  return legend_items


def setup_callbacks(explorer):

  # Architectures 
  @explorer.app.callback(
    [Output(f"checklist-arch-{architecture}", "value") for architecture in explorer.all_architectures],
    [Input("show-all-architectures", "n_clicks"), Input("hide-all-architectures", "n_clicks")],
    [State(f"checklist-arch-{architecture}", "value") for architecture in explorer.all_architectures],
  )
  def update_arch_checklist_states(show_all_clicks, hide_all_clicks, *current_values):
    ctx = dash.callback_context
    if not ctx.triggered:
      return current_values

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id == "show-all-architectures":
      return [[architecture] for architecture in explorer.all_architectures]
    elif button_id == "hide-all-architectures":
      return [[] for _ in explorer.all_architectures]

    return current_values

  
  # Targets
  @explorer.app.callback(
    [Output(f"checklist-target-{target}", "value") for target in explorer.all_targets],
    [Input("show-all-targets", "n_clicks"), Input("hide-all-targets", "n_clicks")],
    [State(f"checklist-target-{target}", "value") for target in explorer.all_targets],
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

  # Architectures 
  @explorer.app.callback(
    Output(f"custom-legend", "children"),
    [
      Input("url", "pathname"),
      Input("yaml-dropdown", "value"),
      Input("color-mode-dropdown", "value"),
      Input("symbol-mode-dropdown", "value"),
      Input("toggle-unique-architectures", "value"),
    ],
    [State(f"checklist-arch-{architecture}", "value") for architecture in explorer.all_architectures]
  )
  def update_architecture_legend(pathname, selected_yaml, color_mode, symbol_mode, unique_architectures, *current_values):
    if not selected_yaml or selected_yaml not in explorer.dfs:
      return []

    yaml_architectures = explorer.dfs[selected_yaml]["Architecture"].unique()
    legend_items = []

    i_existing = -1 
    for i, (architecture, value) in enumerate(zip(explorer.all_architectures, current_values)):
      if architecture in yaml_architectures:
        display = True
        i_existing += 1
      else:
        display = False

      trace_id = i if unique_architectures else i_existing
      
      color = get_color(trace_id) if color_mode == "architecture" else "#fff"
      marker_symbol = trace_id if symbol_mode == "architecture" else 0

      legend_item = create_legend_item(
        label=architecture,
        value=value,
        line_style="2px dashed",
        color=color,
        type="arch",
        marker_symbol=marker_symbol,
        draw_line=True,
        display=display,
        marker_3d=pathname in ("/scatter3d"),
      )
      legend_items.append(legend_item)

    return legend_items

  # Targets
  @explorer.app.callback(
    Output(f"target-legend", "children"),
    [
      Input("url", "pathname"),
      Input("yaml-dropdown", "value"),
      Input("color-mode-dropdown", "value"),
      Input("symbol-mode-dropdown", "value"),
      Input("toggle-unique-targets", "value"),
    ],
    [State(f"checklist-target-{target}", "value") for target in explorer.all_targets],
  )
  def update_target_legend(pathname, selected_yaml, color_mode, symbol_mode, unique_targets, *current_values):
    if not selected_yaml or selected_yaml not in explorer.dfs:
      return []

    yaml_targets = explorer.dfs[selected_yaml]["Target"].unique()
    legend_items = []

    i_existing = -1 
    for i, (target, value) in enumerate(zip(explorer.all_targets, current_values)):
      if target in yaml_targets:
        display = True
        i_existing += 1
      else:
        display = False

      trace_id = i if unique_targets else i_existing
      
      color = get_color(trace_id) if color_mode == "target" else "#fff"
      marker_symbol = trace_id if symbol_mode == "target" else 0

      legend_item = create_legend_item(
        label=target,
        value=value,
        line_style="2px dashed",
        color=color,
        type="target",
        marker_symbol=marker_symbol,
        draw_line=True,
        display=display,
        marker_3d=pathname in ("/scatter3d"),
      )
      legend_items.append(legend_item)

    return legend_items

  # Domains
  @explorer.app.callback(
    Output("domain-legend", "children"),
    [
      Input("url", "pathname"),
      Input("yaml-dropdown", "value"),
      Input("color-mode-dropdown", "value"),
      Input("symbol-mode-dropdown", "value"),
      Input("param-domain-dropdown", "value"),
      Input("dissociate-domain-dropdown", "value"),
    ],
    [
      State(f"checklist-domains-{domain}-{config}", "value") 
      for domain in explorer.all_param_domains.keys()
      for config in explorer.all_param_domains[domain]
    ],
    )
  def update_domain_legend(pathname, selected_yaml, color_mode, symbol_mode, selected_domain, dissociate_domain, *current_values):
    if not selected_yaml or selected_yaml not in explorer.dfs:
      return []

    legend_items = []

    i_existing = -1 
    i_current_value = 0
    for domain in explorer.all_param_domains.keys():
      for i, config in enumerate(explorer.all_param_domains[domain]):
        if domain == selected_domain and domain in explorer.param_domains[selected_yaml] and config in explorer.param_domains[selected_yaml][domain]:
          display = True
          i_existing += 1
        else:
          display = False

        # trace_id = i if unique_domains else i_existing
        trace_id = i
        
        color = get_color(trace_id) if color_mode == "domain_value" and selected_domain == dissociate_domain else "#fff"
        marker_symbol = trace_id if symbol_mode == "domain_value" and selected_domain == dissociate_domain else 0

        legend_item = create_legend_item(
          label=config,
          value=current_values[i_current_value],
          line_style="2px dashed",
          color=color,
          type=f"domains-{domain}",
          marker_symbol=marker_symbol,
          draw_line=False,
          display=display,
          marker_3d=pathname in ("/scatter3d"),
        )
        legend_items.append(legend_item)
        i_current_value = i_current_value + 1

    return legend_items

  # Parameter domains 
  @explorer.app.callback(
    Output("param-domain-dropdown", "options"),
    Output("param-domain-dropdown", "value"),
    Output("dissociate-domain-dropdown", "options"),
    Output("dissociate-domain-dropdown", "value"),
    Input("yaml-dropdown", "value"),
    State("param-domain-dropdown", "value"),
    State("dissociate-domain-dropdown", "value"),
  )
  def update_param_domain_dropdown(selected_yaml, param_domain, dissociate_domain):
    if len(explorer.all_param_domains) == 0:
      return (
        [], param_domain,
        ["None"], dissociate_domain,
      ) 
    available_values = [{"label": param.replace("__main__", "main"), "value": param} for param in explorer.param_domains[selected_yaml].keys()]
    available_dissociate_values = [{"label": "None", "value": "None"}] + available_values

    valid_param_domains = [x["value"] for x in available_values]
    valid_dissociate_values = [x["value"] for x in available_dissociate_values]

    if param_domain not in valid_param_domains:
      param_domain = valid_param_domains[0]
    if dissociate_domain not in valid_dissociate_values:
      dissociate_domain = "None"

    return (
      available_values, param_domain,
      available_dissociate_values, dissociate_domain,
    )

  @explorer.app.callback(
    [
      Output(f"checklist-domains-{domain}-{config}", "value")
      for domain in explorer.all_param_domains.keys()
      for config in explorer.all_param_domains[domain]
    ],
    [
      Input("show-all-domains", "n_clicks"),
      Input("hide-all-domains", "n_clicks"),
      Input("param-domain-dropdown", "value")
    ],
    [
      State(f"checklist-domains-{domain}-{config}", "value") 
      for domain in explorer.all_param_domains.keys()
      for config in explorer.all_param_domains[domain]
    ],
  )
  def update_domain_checklist_states(show_all_clicks, hide_all_clicks, selected_domain, *current_values):
    if len(explorer.all_param_domains) == 0:
      return

    ctx = dash.callback_context
    if not ctx.triggered:
      return current_values
    
    if selected_domain is None:
      return current_values

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id == "show-all-domains":
      new_values = []
      i_current_value = 0
      for domain in explorer.all_param_domains.keys():
        for config in explorer.all_param_domains[domain]:
          if domain == selected_domain:
            new_values.append([config])
          else:
            new_values.append(current_values[i_current_value])
          i_current_value += 1
      return new_values
    elif button_id == "hide-all-domains":
      new_values = []
      i_current_value = 0
      for domain in explorer.all_param_domains.keys():
        for config in explorer.all_param_domains[domain]:
          if domain == selected_domain:
            new_values.append([])
          else:
            new_values.append(current_values[i_current_value])
          i_current_value += 1
      return new_values

    return current_values

def get_color(i):
  if i == -1:
    return greyed_color
  return plot_colors[i % len(plot_colors)]

def get_marker_symbol(i):
  return marker_symbols[i % len(marker_symbols)]

def get_marker_symbol_3d(i):
  return marker_symbols_3d[i % len(marker_symbols_3d)]

def get_pattern(i):
  return patterns[i % len(patterns)]

def get_legend_marker_symbol(marker_symbol_id, color="white", marker_3d=False):
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
    "circle-open": {"border-color": color, "border-style": "solid", "box-sizing": "border-box", "border-radius": "50%"},
    "square-open": {"border-color": color, "border-style": "solid", "box-sizing": "border-box", "border-radius": "0"},
    "diamond-open": {"border-color": color, "border-style": "solid", "box-sizing": "border-box", "transform": "rotate(45deg)", "left": "33%"},
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
    "circle-open": "",
    "square-open": "",
    "diamond-open": "",
  }

  try:
    marker_symbol = marker_symbols_3d[marker_symbol_id] if marker_3d else marker_symbols[marker_symbol_id] 
    marker_style = marker_symbol_styles.get(marker_symbol, marker_symbol_styles["circle"])
    text = text.get(marker_symbol, "")
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


def clean_configuration_name(config_name, dissociate_domain):
  if dissociate_domain != "none":
    parts = config_name.split("+")
    cleaned_parts = [p for p in parts if not p.startswith(f"{dissociate_domain}_")]
    return "+".join(cleaned_parts)
  return config_name

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

import odatix.explorer.legend as legend
import odatix.explorer.themes as themes

from odatix.explorer.css_helper import Style

top_bar_height = "50px"
side_bar_width = "400px"

banned_pages = ["PageNotFound", "Home"]
sidebar_urls = ["/lines", "/columns", "/scatter", "/scatter3d", "/radar", "/overview"]

def top_bar(explorer):
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
                html.Span("Odatix Explorer", className="link-title1 title"),
                html.Span("Home", className="link-title2 title"),
              ],
              className="link-container"
            ),
            className="mask"
          )
        ],
        style={"position": "fixed", "margin-left": "30px", "left": "75px", "z-index": "2", "transition": "margin-left 0.25s"},
      ),
      html.Div([
        html.Div(
          [
            html.Div(
              dcc.Link(f"{page['name']}", href=page["relative_path"], className="nav-link"),
            ) for page in dash.page_registry.values() if page["name"] not in banned_pages
          ],
          className="nav-links",
        ),
        dcc.Dropdown(
          id="theme-dropdown",
          options=[{"label": f"{theme}", "value": f"{theme}"} for theme in reversed(list(themes.templates))],
          value=explorer.start_theme,
          className="theme-dropdown",
          clearable=False,
        ),
      ],
      id="nav-right",
      style={"display": "flex", "position": "absolute", "right": "0", "alignItems": "center", "justifyContent": "right", "z-index": "1000"},)
    ],
    style={"height": f"{top_bar_height}"},
    className="navbar",
    id="navbar",
  )


def side_bar(explorer):
  legend_items = legend.create_legend_items(explorer, "")
  target_legend_items = legend.create_target_legend_items(explorer, "")
  domain_legend_items = legend.create_domain_legend_items(explorer, "")

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
      html.Div(
        id="sidebar",
        children=[
          html.Img(
            id="close-button",
            className="sidebar-button",
            src="/assets/icons/sidebar-panel-collapse-icon.svg",
            n_clicks=0,
            style={"cursor": "pointer", "position": "absolute", "top": "10px", "left": "20px", "width": "30px"},
          ),
          html.Div(children=[
            html.Div(
              id="sidebar-content",
              className="sidebar-content-holder",
              children=[
                html.H2("Data"),
                html.Div(
                  className="title-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("YAML File")]),
                    dcc.Dropdown(
                      id="yaml-dropdown",
                      options=[{"label": yaml_file, "value": yaml_file} for yaml_file in explorer.valid_yaml_files],
                      value=explorer.valid_yaml_files[0] if explorer.valid_yaml_files else None,
                      clearable=False
                    ),
                  ],
                ),
                html.Div(
                  className="title-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Results")]),
                    dcc.Dropdown(
                      id="results-dropdown",
                      value="All",
                      options= ["All", "Fmax", "Custom Freq"]
                    ),
                  ],
                ),
                html.Div(
                  className="title-dropdown",
                  id="title-metric-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Metric")]),
                    dcc.Dropdown(id="metric-dropdown", value="Fmax"),
                  ],
                ),
                html.Div(
                  className="title-dropdown",
                  id="title-metric-x-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Metric X")]),
                    dcc.Dropdown(id="metric-x-dropdown", value=""),
                  ],
                ),
                html.Div(
                  className="title-dropdown",
                  id="title-metric-y-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Metric Y")]),
                    dcc.Dropdown(id="metric-y-dropdown", value=""),
                  ],
                ),
                html.Div(
                  className="title-dropdown",
                  id="title-metric-z-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Metric Z")]),
                    dcc.Dropdown(id="metric-z-dropdown", value=""),
                  ],
                ),
                html.Div(
                  id="overview-options",
                  children=[
                    html.H2("Overview Options"),
                    html.Div(
                      className="title-dropdown",
                      children=[
                        html.Div(className="dropdown-label", children=[html.Label("Chart Type")]),
                        dcc.Dropdown(
                          id="chart-type-dropdown",
                          options=[
                            {"label": "Lines", "value": "lines"},
                            {"label": "Columns", "value": "columns"},
                            {"label": "Radar", "value": "radar"}
                          ],
                          value="radar",
                        ),
                      ],
                      style={"margin-bottom": "5px"},
                    ),
                    html.Div(
                      className="title-dropdown",
                      children=[
                        html.Div(className="dropdown-label", children=[html.Label("Layout")]),
                        dcc.Dropdown(
                          id="overview-layout-dropdown",
                          options=[
                            {"label": "Default", "value": "default"},
                            {"label": "Large", "value": "large"},
                            {"label": "Default (Tall)", "value": "default_tall"},
                            {"label": "Large (Tall)", "value": "large_tall"},
                            {"label": "Page Wide", "value": "page_wide"}
                          ],
                          value="default",
                        ),
                      ],
                      style={"margin-bottom": "5px"},
                    ),
                  ],
                ),
                html.H2("Targets"),
                html.Div(
                  [
                    html.Div(
                      [
                        html.Button("Show All", id="show-all-targets", n_clicks=0),
                        html.Button("Hide All", id="hide-all-targets", n_clicks=0),
                      ]
                    ),
                    html.Div(target_legend_items, id="target-legend", style={"margin-top": "15px", "margin-bottom": "15px"}),
                  ],
                  style={"display": "inline-block", "margin-left": "20px"},
                ),
                html.H2("Architectures"),
                html.Div(
                  [
                    html.Div(
                      [
                        html.Button("Show All", id="show-all-architectures", n_clicks=0),
                        html.Button("Hide All", id="hide-all-architectures", n_clicks=0),
                      ]
                    ),
                    html.Div(legend_items, id="custom-legend", style={"margin-top": "15px", "margin-bottom": "15px"}),
                  ],
                  style={"display": "inline-block", "margin-left": "20px"},
                ),
                html.H2("Parameter Domains"),
                html.Div(
                  id="parameter-domains-error",
                  children=[
                    html.P(
                      [
                        "No parameter domain found in the result file.", html.Br(),
                        "Are these results from an older version of Odatix?"
                      ],
                      style={"margin-left": "20px", "margin-right": "20px"},
                    ),
                  ],
                ),
                html.Div(
                  id="parameter-domains",
                  children=[
                    html.Div(
                      className="title-dropdown",
                      id="title-dissociate-dropdown",
                      children=[
                        html.Div(className="dropdown-label", children=[html.Label("Dissociate Domain")]),
                        dcc.Dropdown(
                          id="dissociate-domain-dropdown",
                          options=[{"label": param, "value": param} for param in ["None"] + list(explorer.all_param_domains.keys())],
                          value="None",
                          placeholder="Domain",
                          clearable=True
                        ),
                      ],
                      style={"margin-bottom": "5px"},
                    ),
                    html.Div(
                      className="title-dropdown",
                      children=[
                        html.Div(className="dropdown-label", children=[html.Label("Domain")]),
                        dcc.Dropdown(
                          id="param-domain-dropdown",
                          options=[{"label": param, "value": param} for param in explorer.all_param_domains.keys()],
                          value="__main__",
                          placeholder="Domain",
                          clearable=True
                        ),
                      ],
                      style={"margin-bottom": "5px"},
                    ),
                    html.Div(
                      [
                        html.Div(
                          [
                            html.Button("Show All", id="show-all-domains", n_clicks=0),
                            html.Button("Hide All", id="hide-all-domains", n_clicks=0),
                          ]
                        ),
                        html.Div(domain_legend_items, id="domain-legend", style={"margin-top": "15px", "margin-bottom": "15px"}),
                      ],
                      style={"display": "inline-block", "margin-left": "20px"},
                    ),
                  ],
                ),
                html.H2("Display Settings"),
                html.Div(
                  className="title-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Color Mode")]),
                    dcc.Dropdown(
                      id="color-mode-dropdown",
                      options=[
                        {"label": "Target", "value": "target"},
                        {"label": "Architecture", "value": "architecture"},
                        {"label": "Domain Value", "value": "domain_value"},
                        {"label": "Frequency", "value": "frequency"},
                      ],
                      value="architecture",
                    ),
                  ],
                  style={"margin-bottom": "5px"},
                ),
                html.Div(
                  className="title-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Symbol Mode")]),
                    dcc.Dropdown(
                      id="symbol-mode-dropdown",
                      options=[
                        {"label": "None", "value": "none"},
                        {"label": "Target", "value": "target"},
                        {"label": "Architecture", "value": "architecture"},
                        {"label": "Domain Value", "value": "domain_value"},
                        {"label": "Frequency", "value": "frequency"},
                      ],
                      value="target",
                    ),
                  ],
                  style={"margin-bottom": "5px"},
                ),
                html.Div(
                  className="title-dropdown",
                      id="title-legend-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Legend Mode")]),
                    dcc.Dropdown(
                      id="legend-dropdown",
                      options=[
                        {"label": "Hide", "value": "hide_legend"},
                        {"label": "Show", "value": "show_legend"},
                        {"label": "Separate", "value": "separate_legend"},
                      ],
                      value="separate_legend",
                    ),
                  ],
                  style={"margin-bottom": "5px"},
                ),
                html.Div(
                  className="toggle-container",
                  children=[
                    dcc.Checklist(
                      id="toggle-legend",
                      options=[{"label": " Show Legend", "value": True}],
                      value=[],
                      className="toggle",
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                    dcc.Checklist(
                      id="toggle-legendgroup",
                      options=[{"label": " Show Legend Groups", "value": True}],
                      value=[True],
                      className="toggle",
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                    dcc.Checklist(
                      id="toggle-title",
                      options=[{"label": " Show Title", "value": True}],
                      value=[True],
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                    dcc.Checklist(
                      id="toggle-lines",
                      options=[{"label": " Show Lines", "value": True}],
                      value=[True],
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                    dcc.Checklist(
                      id="toggle-lines-scatter",
                      options=[{"label": " Show Lines", "value": True}],
                      value=[],
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                    dcc.Checklist(
                      id="toggle-close-line",
                      options=[{"label": " Close Lines", "value": True}],
                      value=[True],
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                    dcc.Checklist(
                      id="toggle-connect-gaps",
                      options=[{"label": " Connect Gaps", "value": True}],
                      value=[True],
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                    dcc.Checklist(
                      id="toggle-labels",
                      options=[{"label": " Show Labels", "value": True}],
                      value=[True],
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                    dcc.Checklist(
                      id="toggle-zero-axis",
                      options=[{"label": " Start axis at zero", "value": True}],
                      value=[True],
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                    dcc.Checklist(
                      id="toggle-unique-architectures",
                      options=[{"label": " Unique architectures color/symbol", "value": True}],
                      value=[True],
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                    dcc.Checklist(
                      id="toggle-unique-targets",
                      options=[{"label": " Unique targets color/symbol", "value": True}],
                      value=[],
                      labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                    ),
                  ],
                ),
                html.H2("Export Settings"),
                html.Div(
                  className="title-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Download Format")]),
                    dcc.Dropdown(
                      id="dl-format-dropdown",
                      options=[
                        {"label": "SVG", "value": "svg"},
                        {"label": "PNG", "value": "png"},
                        {"label": "JPEG", "value": "jpeg"},
                        {"label": "WEBP", "value": "webp"},
                      ],
                      value="svg",
                    ),
                  ],
                  style={"margin-bottom": "5px"},
                ),
                html.Div(
                  className="title-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Background Color")]),
                    dcc.Dropdown(
                      id="background-dropdown",
                      options=[
                        {"label": "Transparent", "value": "rgba(255, 255, 255, 0)"},
                        {"label": "White", "value": "rgba(255, 255, 255, 255)"},
                      ],
                      value="rgba(255, 255, 255, 0)",
                    ),
                  ],
                ),
              ],
            )
          ], className="sidebar-content", style={"width": side_bar_width}),
        ],
        className="sidebar",
        style={"left": "0", "width": side_bar_width},
      ),
    ]
  )


def setup_sidebar_callbacks(explorer):
  @explorer.app.callback(
    [
      Output("title-metric-dropdown", "style"),
      Output("title-metric-x-dropdown", "style"),
      Output("title-metric-y-dropdown", "style"),
      Output("title-metric-z-dropdown", "style"),
      Output("title-legend-dropdown", "style"),
      Output("toggle-legend", "style"),
      Output("toggle-close-line", "style"),
      Output("toggle-lines", "style"),
      Output("toggle-lines-scatter", "style"),
      Output("toggle-connect-gaps", "style"),
      Output("toggle-zero-axis", "style"),
      Output("overview-options", "style"),
    ],
    [
      Input("url", "pathname"),
      Input("chart-type-dropdown", "value"),
    ],
  )
  def update_visibility(pathname, chart_type):

    if pathname in ["/scatter", "/scatter3d"]:
      dropdown_metric = Style.hidden
      dropdown_metric_x = Style.visible
      dropdown_metric_y = Style.visible
    elif pathname in ["/lines", "/columns", "/radar"]:
      dropdown_metric = Style.visible
      dropdown_metric_x = Style.hidden
      dropdown_metric_y = Style.hidden
    else:
      dropdown_metric = Style.hidden
      dropdown_metric_x = Style.hidden
      dropdown_metric_y = Style.hidden

    if pathname in ["/overview"]:
      toggle_legend = Style.hidden
      legend_dropdown = Style.visible
      overview_options = Style.visible_div
      pathname = "/" + chart_type
    else:
      toggle_legend = Style.visible
      legend_dropdown = Style.hidden
      overview_options = Style.hidden

    if pathname in ["/scatter3d"]:
      dropdown_metric_z = Style.visible
      toggle_zero_axis = Style.visible
    else:
      dropdown_metric_z = Style.hidden
      toggle_zero_axis = Style.hidden

    if pathname in ["/radar", "/overview"]:
      toggle_close_line = Style.visible
    else:
      toggle_close_line = Style.hidden

    if pathname in ["/columns"]:
      toggle_connect_gaps = Style.hidden
    else:
      toggle_connect_gaps = Style.visible

    if pathname in ["/columns"]:
      toggle_lines = Style.hidden
      toggle_lines_scatter = Style.hidden
    elif pathname in ["/scatter", "/scatter3d"]:
      toggle_lines = Style.hidden
      toggle_lines_scatter = Style.visible
    else:
      toggle_lines = Style.visible
      toggle_lines_scatter = Style.hidden

    return (
      dropdown_metric, dropdown_metric_x, dropdown_metric_y, dropdown_metric_z,
      legend_dropdown, toggle_legend, toggle_close_line, toggle_lines,
      toggle_lines_scatter, toggle_connect_gaps, toggle_zero_axis, overview_options
    )

  @explorer.app.callback(
    Output("parameter-domains", "style"),
    Output("parameter-domains-error", "style"),
    [
      Input("param-domain-dropdown", "value"),
      Input("yaml-dropdown", "value"),
    ],
  )
  def update_domain_checklist_states(selected_domain, selected_yaml):
    if len(explorer.param_domains[selected_yaml]) == 0:
      return Style.hidden, Style.visible_div
    return Style.visible_div, Style.hidden

  @explorer.app.callback(
    [
      Output("sidebar", "style"),
      Output("content", "style"),
      Output("navbar", "style"), 
      Output("navbar-title", "style"),
      Output("sidebar-top", "style"),
      Output("toggle-button", "style"),
      Output("previous-url", "data"),
    ],
    [
      Input("toggle-button", "n_clicks"),
      Input("close-button", "n_clicks"),
      Input("url", "pathname"),
      Input("theme-dropdown", "value"),
    ],
    [
      State("previous-url", "data"),
      State("sidebar", "style"),
      State("content", "style"),
      State("navbar", "style"),
      State("navbar-title", "style"),
      State("sidebar-top", "style"),
      State("toggle-button", "style"),
    ],
  )
  def toggle_sidebar(
    toggle_n_clicks, close_n_clicks, url, theme, previous_url, sidebar_style, content_style, navbar_style, navbar_title_style, sidebar_top, toggle_style
  ):
    ctx = dash.callback_context
    if not ctx.triggered:
      return sidebar_style, content_style, navbar_style, navbar_title_style, sidebar_top, toggle_style
    
    hide_button = False

    triggered_property = ctx.triggered[0]["prop_id"].split(".")[0]
    if triggered_property == "url":
      if url not in sidebar_urls:
        triggered_property = "close-button"
        hide_button = True
      else:
        if previous_url not in sidebar_urls:
          triggered_property = "toggle-button"

    if triggered_property == "toggle-button":
      if sidebar_style["left"] == "-" + side_bar_width:
        sidebar_style["left"] = "0"
        sidebar_top["left"] = "0"
        content_style["marginLeft"] = side_bar_width
        navbar_title_style["marginLeft"] = "30px"
        navbar_title_style["position"] = "fixed"
        toggle_style["display"] = "none"
      else:
        sidebar_style["left"] = "-" + side_bar_width
        sidebar_top["left"] = "-" + side_bar_width
        content_style["marginLeft"] = "0"
        navbar_title_style["marginLeft"] = "0"
        navbar_title_style["position"] = "relative"
        toggle_style["display"] = "block"
    elif triggered_property == "close-button":
      sidebar_style["left"] = "-" + side_bar_width
      sidebar_top["left"] = "-" + side_bar_width
      content_style["marginLeft"] = "0"
      navbar_title_style["marginLeft"] = "0"
      navbar_title_style["position"] = "relative"
      toggle_style["display"] = "block"

    if hide_button:
      toggle_style["display"] = "none"

    bar_background = themes.get_nav_bgcolor(theme)
    sidebar_style["backgroundColor"] = bar_background
    sidebar_top["backgroundColor"] = bar_background
    navbar_style["backgroundColor"] = bar_background
    navbar_title_style["backgroundColor"] = bar_background

    return sidebar_style, content_style, navbar_style, navbar_title_style, sidebar_top, toggle_style, url

  @explorer.app.callback(
    Output("main-container", "className"),
    Input("theme-dropdown", "value"),
  
  )
  def update_theme(
    theme
  ):
    return f"main-container {theme if theme != 'plotly' else ''}"

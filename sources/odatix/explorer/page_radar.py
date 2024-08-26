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

import os
import re
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objs as go

import odatix.explorer.legend as legend
import odatix.explorer.navigation as navigation
from odatix.lib.utils import safe_df_append

page_name = "radar"


def layout(explorer):
  legend_items = legend.create_legend_items(explorer, page_name)

  return html.Div(
    [
      navigation.top_bar(page_name),
      navigation.side_bar(
        content=html.Div(
          id=f"sidebar-content-{page_name}",
          className="sidebar-content-holder",
          children=[
            html.H2("Data"),
            html.Div(
              [
                html.Div(
                  className="title-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("YAML File")]),
                    dcc.Dropdown(
                      id="yaml-dropdown",
                      options=[{"label": yaml_file, "value": yaml_file} for yaml_file in explorer.valid_yaml_files],
                      value=explorer.valid_yaml_files[0] if explorer.valid_yaml_files else None,
                    ),
                  ],
                ),
                html.Div(
                  className="title-dropdown",
                  children=[
                    html.Div(className="dropdown-label", children=[html.Label("Target")]),
                    dcc.Dropdown(
                      id=f"target-dropdown-{page_name}",
                      value=explorer.dfs[explorer.valid_yaml_files[0]]["Target"].iloc[0]
                      if explorer.valid_yaml_files
                      else None,
                    ),
                  ],
                ),
              ]
            ),
            html.H2("Architectures"),
            html.Div(
              [
                html.Div(
                  [
                    html.Button("Show All", id="show-all", n_clicks=0),
                    html.Button("Hide All", id="hide-all", n_clicks=0),
                  ]
                ),
                html.Div(legend_items, id="custom-legend", style={"margin-top": "15px", "margin-bottom": "15px"}),
              ],
              style={"display": "inline-block", "margin-left": "20px"},
            ),
            html.H2("Display Settings"),
            html.Div(
              className="title-dropdown",
              children=[
                html.Div(className="dropdown-label", children=[html.Label("Legend Mode")]),
                dcc.Dropdown(
                  id="legend-dropdown",
                  options=[
                    {"label": "Hide", "value": "hide_legend"},
                    {"label": "Show", "value": "show_legend"},
                    {"label": "Separate", "value": "separate_legend"},
                  ],
                  value="hide_legend",
                ),
              ],
              style={"margin-bottom": "5px"},
            ),
            html.Div(
              className="toggle-container",
              children=[
                dcc.Checklist(
                  id="toggle-title",
                  options=[{"label": " Show Title", "value": "show_title"}],
                  value=["show_title"],
                  labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                ),
                dcc.Checklist(
                  id="toggle-lines",
                  options=[{"label": " Show Lines", "value": "show_lines"}],
                  value=["show_lines"],
                  labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                ),
                dcc.Checklist(
                  id="toggle-close-line",
                  options=[{"label": " Close Lines", "value": "close_line"}],
                  value=[""],
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
        ),
        page_name=page_name,
      ),
      html.Div(
        id=f"content-{page_name}",
        children=[
          html.Div(id="radar-graphs"),
        ],
        className="content",
        style={
          "marginLeft": navigation.side_bar_width,
          "width": "calc(100%-" + navigation.side_bar_width + ")",
          "height": "100%",
          "justify-content": "center",
        },
      ),
    ]
  )


def make_legend_chart(df, all_architectures, visible_architectures, toggle_title, background, mode):
  fig = go.Figure()

  if not visible_architectures:
    return None

  for i, architecture in enumerate(all_architectures):
    if architecture in visible_architectures:
      df_architecture = df[df["Architecture"] == architecture]
      fig.add_trace(
        go.Scatterpolar(
          r=[None],
          theta=df_architecture["Configuration"],
          mode=mode,
          name=architecture,
          marker_color=legend.get_color(i),
        )
      )

  fig.update_layout(
    polar_bgcolor="rgba(255, 255, 255, 0)",
    paper_bgcolor=background,
    showlegend=True,
    margin=dict(l=60, r=60, t=60, b=60),
    title="Legend" if "show_title" in toggle_title else "",
    title_x=0.5,
    polar=dict(radialaxis=dict(visible=False), angularaxis=dict(visible=False)),
    autosize=True,
    legend_x=0,
    legend_y=1,
    width=475,
    height=475,
  )

  return fig


def make_radar_chart(
  df,
  units,
  metric,
  all_configurations,
  all_architectures,
  visible_architectures,
  legend_dropdown,
  toggle_title,
  toggle_close,
  background,
  mode,
):
  df.loc[:, metric] = pd.to_numeric(df[metric], errors="coerce")
  df = df.dropna(subset=[metric])

  if df.empty:
    fig = go.Figure(data=go.Scatterpolar())
    fig.update_layout(
      polar=dict(radialaxis=dict(visible=False), angularaxis=dict(showticklabels=False)),
      showlegend=False,
      title=metric.replace("_", " ") if metric is not None else "",
      title_x=0.5,
    )
    return fig

  metric_display = metric.replace("_", " ")
  unit = legend.unit_to_html(units.get(metric, ""))

  fig = go.Figure(
    data=go.Scatterpolar(
      r=[None for c in all_configurations],
      theta=all_configurations,
      marker_color="rgba(0, 0, 0, 0)",
      showlegend=False,
    )
  )

  for i, architecture in enumerate(all_architectures):
    if architecture in visible_architectures:
      df_architecture = df[df["Architecture"] == architecture]
      if "close_line" in toggle_close:
        first_row = df_architecture.iloc[0:1]
        df_architecture = safe_df_append(df_architecture, first_row)

      fig.add_trace(
        go.Scatterpolar(
          r=df_architecture[metric],
          theta=df_architecture["Configuration"],
          mode=mode,
          name=architecture,
          marker_color=legend.get_color(i),
          hovertemplate="<br>".join(
            [
              "Architecture: %{fullData.name}",
              "Configuration: %{theta}",
              str(metric_display) + ": %{r} " + unit,
              "<extra></extra>",
            ]
          ),
        )
      )

  fig.update_layout(
    # template='plotly_dark',
    paper_bgcolor=background,
    polar=dict(radialaxis=dict(visible=True, range=[0, df[metric].max() if not df[metric].empty else 1])),
    showlegend="show_legend" in legend_dropdown,
    margin=dict(l=60, r=60, t=60, b=60),
    title=metric_display if "show_title" in toggle_title else None,
    title_x=0.5,
    width=840 if "show_legend" in legend_dropdown else 475,
    height=475,
  )

  return fig


def make_figure_div(fig, filename, dl_format, remove_zoom=False):
  if fig is not None:
    to_remove = ["lasso", "select"]
    if remove_zoom:
      to_remove.append("zoom")
    return html.Div(
      [
        dcc.Graph(
          figure=fig,
          style={"width": "100%"},
          config={
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": to_remove,
            "toImageButtonOptions": {"format": dl_format, "scale": "3", "filename": filename},
          },
        )
      ],
      style={"flex": "0 0 auto", "margin": "0px"},
    )
  else:
    return html.Div([html.Div([], style={"width": "475px"})], style={"flex": "0 0 auto", "margin": "0px"})


def make_all_radar_charts(
  df,
  units,
  metrics,
  all_configurations,
  all_architectures,
  visible_architectures,
  yaml_name,
  legend_dropdown,
  toggle_title,
  toggle_lines,
  toggle_close,
  dl_format,
  background,
):
  radar_charts = []

  mode = "lines+markers" if "show_lines" in toggle_lines else "markers"

  for metric in metrics:
    fig = make_radar_chart(
      df,
      units,
      metric,
      all_configurations,
      all_architectures,
      visible_architectures,
      legend_dropdown,
      toggle_title,
      toggle_close,
      background,
      mode,
    )
    filename = "Odatix-{}-{}-{}".format(yaml_name, page_name, metric)
    radar_charts.append(make_figure_div(fig, filename, dl_format))

  # Add legend chart
  if "separate_legend" in legend_dropdown:
    legend_fig = make_legend_chart(df, all_architectures, visible_architectures, toggle_title, background, mode)
    radar_charts.append(
      make_figure_div(legend_fig, "Odatix-" + str(page_name) + "-legend", dl_format, remove_zoom=True)
    )

  return radar_charts


def setup_callbacks(explorer):
  @explorer.app.callback(
    Output("radar-graphs", "children"),
    [
      Input("yaml-dropdown", "value"),
      Input(f"target-dropdown-{page_name}", "value"),
      Input("show-all", "n_clicks"),
      Input("hide-all", "n_clicks"),
      Input("legend-dropdown", "value"),
      Input("toggle-title", "value"),
      Input("toggle-lines", "value"),
      Input("toggle-close-line", "value"),
      Input("dl-format-dropdown", "value"),
      Input("background-dropdown", "value"),
    ]
    + [Input(f"checklist-{architecture}-{page_name}", "value") for architecture in explorer.all_architectures],
  )
  def update_radar_charts(
    selected_yaml,
    selected_target,
    show_all,
    hide_all,
    legend_dropdown,
    toggle_title,
    toggle_lines,
    toggle_close,
    dl_format,
    background,
    *checklist_values,
  ):
    if not selected_yaml or selected_yaml not in explorer.dfs:
      return html.Div(className="error", children=[html.Div("Please select a YAML file.")])

    if not selected_target:
      return html.Div(className="error", children=[html.Div("Please select a target.")])

    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if triggered_id in ["show-all", "hide-all"]:
      visible_architectures = set(explorer.all_architectures if triggered_id == "show-all" else [])
    else:
      visible_architectures = set(
        architecture for i, architecture in enumerate(explorer.all_architectures) if checklist_values[i]
      )

    filtered_df = explorer.dfs[selected_yaml][
      (explorer.dfs[selected_yaml]["Target"] == selected_target)
      & (explorer.dfs[selected_yaml]["Architecture"].isin(visible_architectures))
    ]

    unique_configurations = sorted(filtered_df["Configuration"].unique())

    metrics = [col for col in filtered_df.columns if col not in ["Target", "Architecture", "Configuration"]]
    all_configurations = explorer.all_configurations
    all_architectures = explorer.all_architectures

    for metric in metrics:
      filtered_df.loc[:, metric] = pd.to_numeric(filtered_df[metric], errors="coerce")

    yaml_name = os.path.splitext(selected_yaml)[0] + "-" + selected_target

    radar_charts = make_all_radar_charts(
      filtered_df,
      explorer.units[selected_yaml],
      metrics,
      unique_configurations,
      all_architectures,
      visible_architectures,
      yaml_name,
      legend_dropdown,
      toggle_title,
      toggle_lines,
      toggle_close,
      dl_format,
      background,
    )

    return html.Div(radar_charts, style={"display": "flex", "flex-wrap": "wrap", "justify-content": "space-evenly"})

  @explorer.app.callback(Output(f"target-dropdown-{page_name}", "options"), Input("yaml-dropdown", "value"))
  def update_dropdowns_radar(selected_yaml):
    if not selected_yaml or selected_yaml not in explorer.dfs:
      return [], []

    df = explorer.dfs[selected_yaml]
    available_targets = [{"label": target, "value": target} for target in df["Target"].unique()]

    return available_targets

  legend.setup_callbacks(explorer, page_name)
  navigation.setup_sidebar_callbacks(explorer, page_name)

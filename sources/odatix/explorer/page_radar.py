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
import odatix.explorer.content_lib as content_lib
from odatix.lib.utils import safe_df_append

page_name = "radar"


def layout(explorer):
  legend_items = legend.create_legend_items(explorer, page_name)
  target_legend_items = legend.create_target_legend_items(explorer, page_name)

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
                      clearable=False
                    ),
                  ],
                ),
              ]
            ),
            html.Div(
              className="title-dropdown",
              children=[
                html.Div(className="dropdown-label", children=[html.Label("Results")]),
                dcc.Dropdown(
                  id=f"results-dropdown-{page_name}",
                  value="All",
                  options= ["All", "Fmax", "Range"]
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
                html.Div(target_legend_items, id=f"target-legend-{page_name}", style={"margin-top": "15px", "margin-bottom": "15px"}),
              ],
              style={"display": "inline-block", "margin-left": "20px"},
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
                html.Div(legend_items, id=f"custom-legend-{page_name}", style={"margin-top": "15px", "margin-bottom": "15px"}),
              ],
              style={"display": "inline-block", "margin-left": "20px"},
            ),
            html.H2("Display Settings"),
            html.Div(
              className="title-dropdown",
              children=[
                html.Div(className="dropdown-label", children=[html.Label("Color Mode")]),
                dcc.Dropdown(
                  id="color-mode-dropdown",
                  options=[{"label": "Architecture", "value": "architecture"}, {"label": "Target", "value": "target"}, {"label": "Frequency", "value": "frequency"}],
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
                  options=[{"label": "Architecture", "value": "architecture"}, {"label": "Target", "value": "target"}, {"label": "Frequency", "value": "frequency"}],
                  value="target",
                ),
              ],
              style={"margin-bottom": "5px"},
            ),
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
                  value="separate_legend",
                ),
              ],
              style={"margin-bottom": "5px"},
            ),
            html.Div(
              className="toggle-container",
              children=[
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
                  id="toggle-close-line",
                  options=[{"label": " Close Lines", "value": True}],
                  value=[True],
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


def make_legend_chart(df, all_architectures, all_targets, targets_for_yaml, visible_architectures, visible_targets, toggle_legendgroup, toggle_title, background, mode):
  fig = go.Figure()

  if not visible_architectures:
    return None

  unique_configurations = sorted(df["Configuration"].unique())

  i_target = -1

  for target in all_targets:
    if target in targets_for_yaml:
      i_target = i_target + 1
    if target in visible_targets:
      targets = [target] * len(unique_configurations)
      for i, architecture in enumerate(all_architectures):
        if architecture in visible_architectures:
          df_architecture = df[df["Architecture"] == architecture]
          fig.add_trace(
            go.Scatterpolar(
              r=[None],
              theta=df_architecture["Configuration"],
              mode=mode,
              name=architecture,
              legendgroup=target,
              legendgrouptitle_text=str(target) if toggle_legendgroup else None,
              marker_size=10,
              marker_color=legend.get_color(i),
              marker_symbol=legend.get_marker_symbol(i_target),
            )
          )

  fig.update_layout(
    polar_bgcolor="rgba(255, 255, 255, 0)",
    paper_bgcolor=background,
    showlegend=True,
    legend_groupclick="toggleitem",
    margin=dict(l=60, r=60, t=60, b=60),
    title="Legend" if toggle_title else "",
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
  selected_results,
  all_configurations,
  all_architectures,
  all_targets,
  all_frequencies,
  targets_for_yaml,
  visible_architectures,
  visible_targets,
  legend_dropdown,
  toggle_legendgroup,
  toggle_title,
  toggle_close,
  color_mode,
  symbol_mode,
  background,
  mode,
):
  numeric_df = df.copy()
  numeric_df.loc[:, metric] = pd.to_numeric(numeric_df[metric], errors="coerce")
  numeric_df = numeric_df.dropna(subset=[metric])

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

  unique_configurations = sorted(df["Configuration"].unique())
  nb_points = len(unique_configurations) + 1 if toggle_close else len(unique_configurations)

  fig = go.Figure(
    data=go.Scatterpolar(
      r=[None for c in all_configurations],
      theta=all_configurations,
      marker_color="rgba(0, 0, 0, 0)",
      showlegend=False,
    )
  )

  i_target = -1

  for target in all_targets:
    if target in targets_for_yaml:
      i_target = i_target + 1
    if target not in visible_targets:
      continue
      
    targets = [target] * nb_points

    for i_architecture, architecture in enumerate(all_architectures):
      if architecture in visible_architectures:
        df_architecture = df[
          (df["Architecture"] == architecture) & 
          (df["Target"] == target)
        ]

        df_architecture_fmax = df_architecture[df_architecture["Type"] == "Fmax"]
        if selected_results in ["All", "Fmax"] and not df_architecture_fmax.empty:

          if toggle_close:
            first_row = df_architecture_fmax.iloc[0:1]
            df_architecture_fmax = safe_df_append(df_architecture_fmax, first_row)

          if color_mode == "architecture":
            color_id = i_architecture
          elif color_mode == "target":
            color_id = i_target
          else:
            color_id = 0

          if symbol_mode == "architecture":
            symbol_id = i_architecture
          elif symbol_mode == "target":
            symbol_id = i_target
          else:
            symbol_id = 0

          fig.add_trace(
            go.Scatterpolar(
              r=df_architecture_fmax[metric],
              theta=df_architecture_fmax["Configuration"],
              mode=mode,
              name=architecture,
              customdata=targets,
              legendgroup=target,
              legendgrouptitle_text=str(target) if toggle_legendgroup else None,
              marker_size=10,
              marker_color=legend.get_color(color_id),
              marker_symbol=legend.get_marker_symbol(symbol_id),
              hovertemplate="<br>".join(
                [
                  "Architecture: %{fullData.name}",
                  "Configuration: %{theta}",
                  "Target: %{customdata}",
                  "Frequency: fmax",
                  str(metric_display) + ": %{r} " + unit,
                  "<extra></extra>",
                ]
              ),
            )
          )

        df_architecture_range = df_architecture[df_architecture["Type"] == "Range"]
        if selected_results in ["All", "Range"] and not df_architecture_range.empty:
          for i_freq, frequency in enumerate(all_frequencies):
            df_frequency = df_architecture_range[df_architecture_range["Frequency"] == frequency]
            frequencies = [f"{frequency} MHz"] * nb_points

            if toggle_close:
              first_row = df_frequency.iloc[0:1]
              df_frequency = safe_df_append(df_frequency, first_row)
            
            if color_mode == "architecture":
              color_id = i_architecture
            elif color_mode == "target":
              color_id = i_target
            else:
              color_id = i_freq + 1
              
            if symbol_mode == "architecture":
              symbol_id = i_architecture
            elif symbol_mode == "target":
              symbol_id = i_target
            else:
              symbol_id = i_freq + 1

            fig.add_trace(
              go.Scatterpolar(
                r=df_frequency[metric],
                theta=df_frequency["Configuration"],
                mode=mode,
                name=architecture,
                customdata=[list(a) for a in zip(targets, frequencies)],
                legendgroup=target,
                legendgrouptitle_text=str(target) if toggle_legendgroup else None,
                marker_size=10,
                marker_color=legend.get_color(color_id),
                marker_symbol=legend.get_marker_symbol(symbol_id),
                hovertemplate="<br>".join(
                  [
                    "Architecture: %{fullData.name}",
                    "Configuration: %{theta}",
                    "Target: %{customdata[0]}",
                    "Frequency: %{customdata[1]}",
                    str(metric_display) + ": %{r} " + unit,
                    "<extra></extra>",
                  ]
                ),
              )
            )

  fig.update_layout(
    # template='plotly_dark',
    paper_bgcolor=background,
    polar=dict(radialaxis=dict(visible=True, range=[0, numeric_df[metric].max() if not df[metric].empty else 1])),
    showlegend="show_legend" in legend_dropdown,
    legend_groupclick="toggleitem",
    margin=dict(l=60, r=60, t=60, b=60),
    title=metric_display if toggle_title else None,
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
            "toImageButtonOptions": {
              "format": dl_format,
              "scale": 3,
              "filename": filename
            },
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
  selected_results,
  all_configurations,
  all_architectures,
  all_targets,
  all_frequencies,
  targets_for_yaml,
  visible_architectures,
  visible_targets,
  yaml_name,
  legend_dropdown,
  toggle_legendgroup,
  toggle_title,
  toggle_lines,
  toggle_close,
  color_mode,
  symbol_mode,
  dl_format,
  background,
):
  radar_charts = []

  mode = "lines+markers" if toggle_lines else "markers"

  for metric in metrics:
    fig = make_radar_chart(
      df,
      units,
      metric,
      selected_results,
      all_configurations,
      all_architectures,
      all_targets,
      all_frequencies,
      targets_for_yaml,
      visible_architectures,
      visible_targets,
      legend_dropdown,
      toggle_legendgroup,
      toggle_title,
      toggle_close,
      color_mode,
      symbol_mode,
      background,
      mode,
    )
    filename = "Odatix-{}-{}-{}".format(yaml_name, page_name, metric)
    radar_charts.append(make_figure_div(fig, filename, dl_format))

  # Add legend chart
  if "separate_legend" in legend_dropdown:
    legend_fig = make_legend_chart(df, all_architectures, all_targets, targets_for_yaml, visible_architectures, visible_targets, toggle_legendgroup, toggle_title, background, mode)
    radar_charts.append(
      make_figure_div(legend_fig, "Odatix-" + str(page_name) + "-legend", dl_format, remove_zoom=True)
    )

  return radar_charts


def setup_callbacks(explorer):
  all_architecture_inputs = [
    Input(f"checklist-arch-{architecture}-{page_name}", "value") for architecture in explorer.all_architectures
  ]
  all_target_inputs = [
    Input(f"checklist-target-{target}-{page_name}", "value") for target in explorer.all_targets
  ]
  all_checklist_inputs = all_architecture_inputs + all_target_inputs

  @explorer.app.callback(
    Output("radar-graphs", "children"),
    [
      Input("yaml-dropdown", "value"),
      # Input(f"target-dropdown-{page_name}", "value"),
      Input(f"results-dropdown-{page_name}", "value"),
      Input("show-all", "n_clicks"),
      Input("hide-all", "n_clicks"),
      Input("legend-dropdown", "value"),
      Input("toggle-legendgroup", "value"),
      Input("toggle-title", "value"),
      Input("toggle-lines", "value"),
      Input("toggle-close-line", "value"),
      Input("color-mode-dropdown", "value"),
      Input("symbol-mode-dropdown", "value"),
      Input("dl-format-dropdown", "value"),
      Input("background-dropdown", "value"),
    ]
    + all_checklist_inputs  
  )
  def update_radar_charts(
    selected_yaml,
    # selected_target,
    selected_results,
    show_all,
    hide_all,
    legend_dropdown,
    toggle_legendgroup,
    toggle_title,
    toggle_lines,
    toggle_close,
    color_mode,
    symbol_mode,
    dl_format,
    background,
    *checklist_values,
  ):
    try:
      arch_checklist_values = checklist_values[:len(all_architecture_inputs)]
      target_checklist_values = checklist_values[len(all_architecture_inputs):]

      if not selected_yaml or selected_yaml not in explorer.dfs:
        return html.Div(className="error", children=[html.Div("Please select a YAML file.")])

      ctx = dash.callback_context
      triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

      if triggered_id in ["show-all", "hide-all"]:
        visible_architectures = set(
          explorer.dfs[selected_yaml]["Architecture"].unique() if triggered_id == "show-all" else []
        )
      else:
        visible_architectures = set(
          architecture for i, architecture in enumerate(explorer.all_architectures) if arch_checklist_values[i] and architecture in explorer.dfs[selected_yaml]["Architecture"].unique()
        )

      if triggered_id in ["show-all-targets", "hide-all-targets"]:
        visible_targets = set(
          explorer.dfs[selected_yaml]["Target"].unique() if triggered_id == "show-all-targets" else []
        )
      else:
        visible_targets = set(
          target for i, target in enumerate(explorer.all_targets) if target_checklist_values[i] and target in explorer.dfs[selected_yaml]["Target"].unique()
        )

      filtered_df = explorer.dfs[selected_yaml][
        (explorer.dfs[selected_yaml]["Architecture"].isin(visible_architectures))
      ]

      unique_configurations = sorted(filtered_df["Configuration"].unique())

      metrics = [col for col in filtered_df.columns if col not in ["Target", "Architecture", "Configuration", "Type", "Frequency"]]
      all_configurations = explorer.all_configurations
      all_architectures = explorer.all_architectures
      all_targets = explorer.all_targets
      all_frequencies = explorer.all_frequencies
      targets_for_yaml = explorer.dfs[selected_yaml]["Target"].unique()

      yaml_name = os.path.splitext(selected_yaml)[0]

      radar_charts = make_all_radar_charts(
        filtered_df,
        explorer.units[selected_yaml],
        metrics,
        selected_results,
        unique_configurations,
        all_architectures,
        all_targets,
        all_frequencies,
        targets_for_yaml,
        visible_architectures,
        visible_targets,
        yaml_name,
        legend_dropdown,
        toggle_legendgroup,
        toggle_title,
        toggle_lines,
        toggle_close,
        color_mode,
        symbol_mode,
        dl_format,
        background,
      )

      return html.Div(radar_charts, style={"display": "flex", "flex-wrap": "wrap", "justify-content": "space-evenly"})
    except Exception as e:
      return content_lib.generate_error_div(e)
      
  # @explorer.app.callback(
  #   Output(f"target-dropdown-{page_name}", "options"), 
  #   Input("yaml-dropdown", "value")
  # )
  # def update_dropdowns_radar(selected_yaml):
  #   if not selected_yaml or selected_yaml not in explorer.dfs:
  #     return [], []

  #   df = explorer.dfs[selected_yaml]
  #   available_targets = [{"label": target, "value": target} for target in df["Target"].unique()]

  #   return available_targets

  legend.setup_callbacks(explorer, page_name)
  navigation.setup_sidebar_callbacks(explorer, page_name)

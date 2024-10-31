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
import plotly.graph_objs as go

import odatix.explorer.legend as legend
import odatix.explorer.navigation as navigation
import odatix.explorer.content_lib as content_lib

page_name = "xy"


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
            # html.Div(
            #   className="title-dropdown",
            #   children=[
            #     html.Div(className="dropdown-label", children=[html.Label("Results")]),
            #     dcc.Dropdown(
            #       id=f"results-dropdown-{page_name}",
            #       value="All",
            #       options= ["All", "Fmax", "Range"]
            #     ),
            #   ],
            # ),
            html.Div(
              className="title-dropdown",
              children=[
                html.Div(className="dropdown-label", children=[html.Label("Metric")]),
                dcc.Dropdown(id="metric-dropdown", value="Fmax"),
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
                html.Div(legend_items, id="custom-legend", style={"margin-top": "15px", "margin-bottom": "15px"}),
              ],
              style={"display": "inline-block", "margin-left": "20px"},
            ),
            html.H2("Display Settings"),
            html.Div(
              className="title-dropdown",
              children=[
                html.Div(className="dropdown-label", children=[html.Label("Display Mode")]),
                dcc.Dropdown(
                  id="display-mode-dropdown",
                  options=[{"label": "Points", "value": "points"}, {"label": "Bars", "value": "bars"}],
                  value="points",
                ),
              ],
              style={"margin-bottom": "5px"},
            ),
            html.Div(
              className="toggle-container",
              children=[
                dcc.Checklist(
                  id="toggle-legend",
                  options=[{"label": " Show Legend", "value": "show_legend"}],
                  value=[""],
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
          html.Div(
            [html.Div(id=f"graph-{page_name}", style={"width": "100%", "height": "100%"}, className="graph-container")],
            style={"width": "100%", "height": "100%"},
          ),
          # html.Div(id="checklist-states", style={"display": "none"}),
        ],
        className="content",
        style={
          "marginLeft": navigation.side_bar_width,
          "width": "calc(100%-" + navigation.side_bar_width + ")",
          "height": "100%",
        },
      ),
    ],
    style={"width": "100%", "height": "100vh", "display": "flex", "flexDirection": "column"},
  )

# TODO: set a default metric if the current value is no longer in available_metrics
def setup_callbacks(explorer):
  @explorer.app.callback(
    Output("metric-dropdown", "options"),
    Input("yaml-dropdown", "value"),
  )
  def update_dropdowns(selected_yaml):
    if not selected_yaml or selected_yaml not in explorer.dfs:
      return [], []

    df = explorer.dfs[selected_yaml]
    metrics_from_yaml = explorer.update_metrics(explorer.all_data[selected_yaml])
    available_metrics = [{"label": metric.replace("_", " "), "value": metric} for metric in metrics_from_yaml]

    return available_metrics

  all_architecture_inputs = [
    Input(f"checklist-arch-{architecture}-{page_name}", "value") for architecture in explorer.all_architectures
  ]
  all_target_inputs = [
    Input(f"checklist-target-{target}-{page_name}", "value") for target in explorer.all_targets
  ]
  all_checklist_inputs = all_architecture_inputs + all_target_inputs

  @explorer.app.callback(
    Output(f"graph-{page_name}", "children"),
    [
      Input("yaml-dropdown", "value"),
      Input("metric-dropdown", "value"),
      # Input(f"results-dropdown-{page_name}", "value"),
      Input("show-all", "n_clicks"),
      Input("hide-all", "n_clicks"),
      Input("show-all-targets", "n_clicks"),
      Input("hide-all-targets", "n_clicks"),
      Input("toggle-legend", "value"),
      Input("toggle-legendgroup", "value"),
      Input("toggle-title", "value"),
      Input("toggle-lines", "value"),
      Input("display-mode-dropdown", "value"),
      Input("dl-format-dropdown", "value"),
      Input("background-dropdown", "value"),
    ]
    + all_checklist_inputs  
  )
  def update_graph(
    selected_yaml,
    selected_metric,
    # selected_results,
    show_all,
    hide_all,
    show_all_targets,
    hide_all_targets,
    toggle_legend,
    toggle_legendgroup,
    toggle_title,
    toggle_lines,
    display_mode,
    dl_format,
    background,
    *checklist_values,
  ):
    try:
      arch_checklist_values = checklist_values[:len(all_architecture_inputs)]
      target_checklist_values = checklist_values[len(all_architecture_inputs):]

      if not selected_yaml or selected_yaml not in explorer.dfs:
        return html.Div(className="error", children=[html.Div("Please select a YAML file.")])

      selected_metric_display = selected_metric.replace("_", " ") if selected_metric is not None else ""

      unit = legend.unit_to_html(explorer.units[selected_yaml].get(selected_metric, ""))
      selected_metric_display_unit = selected_metric_display + " (" + unit + ")" if unit else selected_metric_display

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

      fig = go.Figure()

      i_target = -1

      if display_mode == "points":
        for target in explorer.all_targets:
          if target in explorer.dfs[selected_yaml]["Target"].unique():
            i_target = i_target + 1
          if target in visible_targets:
            targets = [target] * len(unique_configurations)
            for i, architecture in enumerate(explorer.all_architectures):
              if architecture in visible_architectures:
                df_architecture_target = filtered_df[
                  (filtered_df["Architecture"] == architecture) & 
                  (filtered_df["Target"] == target)
                ]
                
                if selected_metric is None or selected_metric not in df_architecture_target.columns:
                  return html.Div(className="error", children=[html.Div("Please select a valid metric.")])
                else:
                  y_values = [
                    df_architecture_target[df_architecture_target["Configuration"] == config][selected_metric].values[0]
                    if config in df_architecture_target["Configuration"].values
                    else None
                    for config in unique_configurations
                  ]

                mode = "lines+markers" if "show_lines" in toggle_lines else "markers"

                fig.add_trace(
                  go.Scatter(
                    x=unique_configurations,
                    y=y_values,
                    mode=mode,
                    line=dict(dash="dot") if "show_lines" in toggle_lines else None,
                    marker=dict(
                      size=10, 
                      color=legend.get_color(i),
                      symbol=legend.get_marker_symbol(i_target),
                    ),
                    name=architecture,
                    customdata=targets,
                    legendgroup=target,
                    legendgrouptitle_text=str(target) if toggle_legendgroup else None,
                    connectgaps=True,
                    hovertemplate="<br>".join(
                      [
                        "Architecture: %{fullData.name}",
                        "Configuration: %{x}",
                        "Target: %{customdata}",
                        selected_metric_display + ": %{y} " + unit,
                        "<extra></extra>",
                      ]
                    ),
                  )
                )
      elif display_mode == "bars":
        for j, target in enumerate(explorer.all_targets):
          if target in visible_targets:
            targets = [target] * len(unique_configurations)
            for i, architecture in enumerate(explorer.all_architectures):
              if architecture in visible_architectures:
                df_architecture_target = filtered_df[
                  (filtered_df["Architecture"] == architecture) & 
                  (filtered_df["Target"] == target)
                ]
                y_values = [
                  df_architecture_target[df_architecture_target["Configuration"] == config][selected_metric].values[0]
                  if config in df_architecture_target["Configuration"].values
                  else None
                  for config in unique_configurations
                ]

                fig.add_trace(
                  go.Bar(
                    x=unique_configurations,
                    y=y_values,
                    marker=dict(color=legend.get_color(i)),
                    name=architecture,
                    customdata=targets,
                    hovertemplate="<br>".join(
                      [
                        "Architecture: %{fullData.name}",
                        "Configuration: %{x}",
                        "Target: %{customdata}",
                        selected_metric_display + ": %{y} " + unit,
                        "<extra></extra>",
                      ]
                    ),
                  )
                )

      fig.update_layout(
        paper_bgcolor=background,
        showlegend="show_legend" in toggle_legend,
        legend_groupclick="toggleitem",
        xaxis_title="Configuration",
        yaxis_title=selected_metric_display_unit,
        yaxis=dict(range=[0, None]),
        title=selected_metric_display if "show_title" in toggle_title else None,
        title_x=0.5,
        autosize=True,
      )
      filename = "Odatix-{}-{}-{}".format(
        os.path.splitext(selected_yaml)[0], page_name, selected_metric
      )
      return html.Div(
        [
          dcc.Graph(
            figure=fig,
            style={"width": "100%", "height": "100%"},
            config={
              "displayModeBar": True,
              "displaylogo": False,
              "modeBarButtonsToRemove": ["lasso", "select"],
              "toImageButtonOptions": {
                "format": dl_format,
                "scale": 3,
                "filename": filename
              },
            },
          )
        ],
        style={"width": "100%", "height": "100%", "display": "inline-block", "vertical-align": "top"},
      )
    except Exception as e:
      return content_lib.generate_error_div(e)

  legend.setup_callbacks(explorer, page_name)
  navigation.setup_sidebar_callbacks(explorer, page_name)


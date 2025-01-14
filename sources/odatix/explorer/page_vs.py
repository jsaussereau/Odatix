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

page_name = "vs"


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
            # html.Div(
            #   className="title-dropdown",
            #   children=[
            #     html.Div(className="dropdown-label", children=[html.Label("Target")]),
            #     dcc.Dropdown(
            #       id=f"target-dropdown-{page_name}",
            #       value=explorer.dfs[explorer.valid_yaml_files[0]]["Target"].iloc[0]
            #       if explorer.valid_yaml_files
            #       else None,
            #     ),
            #   ],
            # ),
            html.Div(
              className="title-dropdown",
              children=[
                html.Div(className="dropdown-label", children=[html.Label("Metric X")]),
                dcc.Dropdown(id="metric-x-dropdown", value="Fmax"),
              ],
            ),
            html.Div(
              className="title-dropdown",
              children=[
                html.Div(className="dropdown-label", children=[html.Label("Metric Y")]),
                dcc.Dropdown(id="metric-y-dropdown", value="Fmax"),
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
              className="toggle-container",
              children=[
                dcc.Checklist(
                  id="toggle-legend",
                  options=[{"label": " Show Legend", "value": True}],
                  value=[],
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
                  value=[],
                  labelStyle={"display": "block", "font-weight": "515", "margin-bottom": "5px"},
                ),
                dcc.Checklist(
                  id="toggle-labels",
                  options=[{"label": " Show Labels", "value": True}],
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
          html.Div(
            [html.Div(id=f"graph-{page_name}", style={"width": "100%", "height": "100%"}, className="graph-container")],
            style={"width": "100%", "height": "100%"},
          ),
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


def setup_callbacks(explorer):
  @explorer.app.callback(
    [
      Output("metric-x-dropdown", "options"),
      Output("metric-y-dropdown", "options"),
    ],
    Input("yaml-dropdown", "value"),
  )
  def update_dropdowns(selected_yaml):
    if not selected_yaml or selected_yaml not in explorer.dfs:
      return [], [], []

    df = explorer.dfs[selected_yaml]
    metrics_from_yaml = explorer.update_metrics(explorer.all_data[selected_yaml])
    available_metrics = [{"label": metric.replace("_", " "), "value": metric} for metric in metrics_from_yaml]
    available_targets = [{"label": target, "value": target} for target in df["Target"].unique()]

    return available_metrics, available_metrics

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
      Input("metric-x-dropdown", "value"),
      Input("metric-y-dropdown", "value"),
      Input(f"results-dropdown-{page_name}", "value"),
      # Input(f"target-dropdown-{page_name}", "value"),
      Input("show-all", "n_clicks"),
      Input("hide-all", "n_clicks"),
      Input("toggle-legend", "value"),
      Input("toggle-legendgroup", "value"),
      Input("toggle-title", "value"),
      Input("toggle-lines", "value"),
      Input("toggle-labels", "value"),
      Input("color-mode-dropdown", "value"),
      Input("symbol-mode-dropdown", "value"),
      Input("dl-format-dropdown", "value"),
      Input("background-dropdown", "value"),
    ]
    + all_checklist_inputs  
  )
  def update_graph(
    selected_yaml,
    selected_metric_x,
    selected_metric_y,
    selected_results,
    # selected_target,
    show_all,
    hide_all,
    toggle_legend,
    toggle_legendgroup,
    toggle_title,
    toggle_lines,
    toggle_labels,
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

      selected_metric_x_display = selected_metric_x.replace("_", " ") if selected_metric_x is not None else ""
      selected_metric_y_display = selected_metric_y.replace("_", " ") if selected_metric_y is not None else ""

      unit_x = legend.unit_to_html(explorer.units[selected_yaml].get(selected_metric_x, ""))
      unit_y = legend.unit_to_html(explorer.units[selected_yaml].get(selected_metric_y, ""))

      selected_metric_x_display_unit = (
        selected_metric_x_display + " (" + unit_x + ")" if unit_x else selected_metric_x_display
      )
      selected_metric_y_display_unit = (
        selected_metric_y_display + " (" + unit_y + ")" if unit_y else selected_metric_y_display
      )

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
        explorer.dfs[selected_yaml]["Architecture"].isin(visible_architectures)
      ]

      fig = go.Figure()

      i_target = -1

      for j, target in enumerate(explorer.all_targets):
        if target in explorer.dfs[selected_yaml]["Target"].unique():
          i_target = i_target + 1
        if target not in visible_targets:
          continue

        for i_architecture, architecture in enumerate(explorer.all_architectures):
          if architecture in visible_architectures:
            df_architecture = filtered_df[
              (filtered_df["Architecture"] == architecture) & 
              (filtered_df["Target"] == target)
            ]
            if df_architecture.empty:
              continue

            mode = "lines+markers" if toggle_lines else "markers"

            df_architecture_fmax = df_architecture[df_architecture["Type"] == "Fmax"]

            if selected_results in ["All", "Fmax"] and not df_architecture_fmax.empty:
              if selected_metric_x is None or selected_metric_x not in df_architecture_fmax.columns:
                return html.Div(className="error", children=[html.Div("Please select a valid x metric.")])
              if selected_metric_y is None or selected_metric_y not in df_architecture_fmax.columns:
                return html.Div(className="error", children=[html.Div("Please select a valid y metric.")])

              x_values = df_architecture_fmax[selected_metric_x].tolist()
              y_values = df_architecture_fmax[selected_metric_y].tolist()
              config_names = df_architecture_fmax["Configuration"].tolist()
              targets = [target] * len(x_values)
              frequencies = ["fmax"] * len(x_values)

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

              if toggle_labels:
                mode += "+text"

              add_trace_to_fig(
                fig, x_values, y_values, mode, architecture, frequencies, "fmax", config_names,
                targets, target, selected_metric_x_display, selected_metric_y_display,
                unit_x, unit_y, color_id, symbol_id, toggle_lines, toggle_legendgroup
              )

            df_architecture_range = df_architecture[df_architecture["Type"] == "Range"]

            if selected_results in ["All", "Range"] and not df_architecture_range.empty:
              for i_freq, frequency in enumerate(explorer.all_frequencies):
                df_frequency = df_architecture_range[df_architecture_range["Frequency"] == frequency]
                if df_frequency.empty:
                  continue

                if selected_metric_x is None or selected_metric_x not in df_frequency.columns:
                  return html.Div(className="error", children=[html.Div("Please select a valid x metric.")])
                if selected_metric_y is None or selected_metric_y not in df_frequency.columns:
                  return html.Div(className="error", children=[html.Div("Please select a valid y metric.")])

                x_values = df_frequency[selected_metric_x].tolist()
                y_values = df_frequency[selected_metric_y].tolist()
                config_names = df_frequency["Configuration"].tolist()
                targets = [target] * len(x_values)
                frequencies = [f"{frequency} MHz"] * len(x_values)

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

                if toggle_labels:
                  mode += "+text"

                add_trace_to_fig(
                  fig, x_values, y_values, mode, architecture, frequencies, f"{frequency} MHz", config_names,
                  targets, target, selected_metric_x_display, selected_metric_y_display,
                  unit_x, unit_y, color_id, symbol_id, toggle_lines, toggle_legendgroup
                )

      fig.update_layout(
        paper_bgcolor=background,
        showlegend=True if toggle_legend else False,
        legend_groupclick="toggleitem",
        xaxis_title=selected_metric_x_display_unit,
        yaxis_title=selected_metric_y_display_unit,
        xaxis=dict(range=[0, None]),
        yaxis=dict(range=[0, None]),
        title=selected_metric_y_display + " vs " + selected_metric_x_display if toggle_title else None,
        title_x=0.5,
        autosize=True,
      )
      filename = "Odatix-{}-{}-vs-{}".format(
        os.path.splitext(selected_yaml)[0], selected_metric_y, selected_metric_x
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
                "filename": filename,
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

def add_trace_to_fig(fig, x_values, y_values, mode, architecture, frequencies, frequency, config_names, targets, target, selected_metric_x_display, selected_metric_y_display, unit_x, unit_y, color_id, symbol_id, toggle_lines, toggle_legendgroup):
  fig.add_trace(
    go.Scatter(
      x=x_values,
      y=y_values,
      mode=mode,
      line=dict(dash="dot") if toggle_lines else None,
      marker=dict(
        size=10,
        color=legend.get_color(color_id ),
        symbol=legend.get_marker_symbol(symbol_id),
      ),
      name=f"{architecture} @ {frequency}" if frequency else architecture,
      customdata=[list(a) for a in zip(targets, frequencies)],
      legendgroup=target,
      legendgrouptitle_text=str(target) if toggle_legendgroup else None,
      connectgaps=True,
      text=config_names,
      textposition="top center",
      hovertemplate="<br>".join(
        [
          "Architecture: %{fullData.name}",
          "Configuration: %{text}",
          "Target: %{customdata[0]}",
          "Frequency: %{customdata[1]}",
          selected_metric_x_display + ": %{x} " + unit_x,
          selected_metric_y_display + ": %{y} " + unit_y,
          "<extra></extra>",
        ]
      ),
    )
  )
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
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go

import odatix.explorer.legend as legend
import odatix.explorer.content_lib as content_lib
import odatix.explorer.figures as figures

def setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs):

  @explorer.app.callback(
    Output("graph-scatter", "children"),
    [
      Input("yaml-dropdown", "value"),
      Input("metric-x-dropdown", "value"),
      Input("metric-y-dropdown", "value"),
      Input("results-dropdown", "value"),
      Input("show-all-architectures", "n_clicks"),
      Input("hide-all-architectures", "n_clicks"),
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

      if triggered_id in ["show-all-architectures", "hide-all-architectures"]:
        visible_architectures = set(
          explorer.dfs[selected_yaml]["Architecture"].unique() if triggered_id == "show-all-architectures" else []
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

              figures.add_trace_to_vs_fig(
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

                figures.add_trace_to_vs_fig(
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

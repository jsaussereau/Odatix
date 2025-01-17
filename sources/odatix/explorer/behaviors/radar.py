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
    Output("radar-graphs", "children"),
    [
      Input("yaml-dropdown", "value"),
      Input("results-dropdown", "value"),
      Input("show-all-architectures", "n_clicks"),
      Input("hide-all-architectures", "n_clicks"),
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

      radar_charts = figures.make_all_radar_charts(
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
      
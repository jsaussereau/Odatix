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
from dash.dependencies import Input, Output, State

import odatix.explorer.behaviors.lines as behavior_lines
import odatix.explorer.behaviors.columns as behavior_columns
import odatix.explorer.behaviors.scatter as behavior_scatter
import odatix.explorer.behaviors.scatter3d as behavior_scatter3d
import odatix.explorer.behaviors.radar as behavior_radar
import odatix.explorer.behaviors.overview as behavior_overview
import odatix.explorer.legend as legend
import odatix.explorer.themes as themes

def setup_callbacks(explorer):
  all_architecture_inputs = [
    Input(f"checklist-arch-{architecture}", "value") for architecture in explorer.all_architectures
  ]
  all_target_inputs = [
    Input(f"checklist-target-{target}", "value") for target in explorer.all_targets
  ]
  all_domains_inputs = [
      Input(f"checklist-domains-{domain}-{config}", "value") 
      for domain in explorer.all_param_domains.keys()
      for config in explorer.all_param_domains[domain]
  ]

  all_checklist_inputs = all_architecture_inputs + all_target_inputs + all_domains_inputs

  behavior_lines.setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs, all_domains_inputs)
  behavior_columns.setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs, all_domains_inputs)
  behavior_radar.setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs, all_domains_inputs)
  behavior_scatter.setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs, all_domains_inputs)
  behavior_scatter3d.setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs, all_domains_inputs)
  behavior_overview.setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs, all_domains_inputs)
  
  legend.setup_callbacks(explorer)

  # Update metrics on yaml change
  @explorer.app.callback(
    Output("metric-dropdown", "options"),
    Output("metric-x-dropdown", "options"),
    Output("metric-y-dropdown", "options"),
    Output("metric-z-dropdown", "options"),
    Output("metric-dropdown", "value"),
    Output("metric-x-dropdown", "value"),
    Output("metric-y-dropdown", "value"),
    Output("metric-z-dropdown", "value"),
    Input("yaml-dropdown", "value"),
    State("metric-dropdown", "value"),
    State("metric-x-dropdown", "value"),
    State("metric-y-dropdown", "value"),
    State("metric-z-dropdown", "value"),
  )
  def update_dropdowns(selected_yaml, selected_metric, selected_metric_x, selected_metric_y, selected_metric_z):
    if explorer is None:
      return []*4 + []*4

    if not selected_yaml or selected_yaml not in explorer.dfs:
      return []*4 + []*4

    df = explorer.dfs[selected_yaml]
    metrics_from_yaml = explorer.update_metrics(explorer.all_data[selected_yaml])
    available_metrics = [{"label": metric.replace("_", " "), "value": metric} for metric in metrics_from_yaml]
    
    metric0 = available_metrics[0]["value"] if len(available_metrics) > 0 else None
    metric1 = available_metrics[1]["value"] if len(available_metrics) > 1 else None
    metric2 = available_metrics[2]["value"] if len(available_metrics) > 2 else None
    
    # Change current metrics if they are not available anymore
    if selected_metric not in metrics_from_yaml:
      selected_metric = metric0
    if selected_metric_x not in metrics_from_yaml:
      selected_metric_x = metric0
    if selected_metric_y not in metrics_from_yaml:
      selected_metric_y = metric1
    if selected_metric_z not in metrics_from_yaml:
      selected_metric_z = metric2

    return [available_metrics]*4 + [selected_metric, selected_metric_x, selected_metric_y, selected_metric_z]

  @explorer.app.callback(
    Output("main-container", "style"),
    Input("theme-dropdown", "value"),
  )
  def update_theme(theme):
    style = {"backgroundColor": themes.get_page_bgcolor(theme)}
    return style

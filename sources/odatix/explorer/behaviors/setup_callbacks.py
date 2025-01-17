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
from dash.dependencies import Input, Output

import odatix.explorer.behaviors.lines as behavior_lines
import odatix.explorer.behaviors.columns as behavior_columns
import odatix.explorer.behaviors.scatter as behavior_scatter
import odatix.explorer.behaviors.radar as behavior_radar
import odatix.explorer.legend as legend

def setup_callbacks(explorer):
  all_architecture_inputs = [
    Input(f"checklist-arch-{architecture}", "value") for architecture in explorer.all_architectures
  ]
  all_target_inputs = [
    Input(f"checklist-target-{target}", "value") for target in explorer.all_targets
  ]
  all_checklist_inputs = all_architecture_inputs + all_target_inputs

  behavior_lines.setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs)
  behavior_columns.setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs)
  behavior_scatter.setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs)
  behavior_radar.setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs)
  
  legend.setup_callbacks(explorer)

  # Update metrics on yaml change
  @explorer.app.callback(
    Output("metric-dropdown", "options"),
    Output("metric-x-dropdown", "options"),
    Output("metric-y-dropdown", "options"),
    Input("yaml-dropdown", "value"),
  )
  def update_dropdowns(selected_yaml):
    if explorer is None:
      return []*3

    if not selected_yaml or selected_yaml not in explorer.dfs:
      return []*3

    df = explorer.dfs[selected_yaml]
    metrics_from_yaml = explorer.update_metrics(explorer.all_data[selected_yaml])
    available_metrics = [{"label": metric.replace("_", " "), "value": metric} for metric in metrics_from_yaml]

    return [available_metrics]*3

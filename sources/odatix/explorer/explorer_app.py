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
import sys
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import yaml
from flask import jsonify
import traceback

import odatix.explorer.page_xy as page_xy
import odatix.explorer.page_vs as page_vs
import odatix.explorer.page_radar as page_radar

import odatix.lib.printc as printc
from odatix.lib.utils import internal_error
import odatix.lib.term_mode as term_mode

script_name = os.path.basename(__file__)
error_logfile = "odatix-explorer_error.log"

class ResultExplorer:
  def __init__(self, result_path="results", yaml_prefix="results_", old_settings=None, safe_mode=False):
    self.result_path = result_path
    self.yaml_prefix = yaml_prefix
    self.old_settings = old_settings
    self.safe_mode = safe_mode

    self.required_columns = ["Target", "Architecture", "Configuration"]

    # Check paths
    if not os.path.exists(result_path):
      printc.error('Could not find result path "' + result_path + '"')
      if self.old_settings is not None:
        term_mode.restore_mode(self.old_settings)
      sys.exit(-1)

    # Initialize additional instance variables here
    self.yaml_files = [
      file for file in os.listdir(self.result_path) if file.endswith(".yml") and file.startswith(yaml_prefix)
    ]
    self.valid_yaml_files = []
    self.all_data = {}
    self.dfs = {}
    self.units = {}

    # Load and validate YAML files
    self.load_yaml_files()

    if not self.valid_yaml_files:
      printc.error(
        'Could not find any valid YAML file in "' + self.result_path + '", exiting.', script_name=script_name
      )
      sys.exit(-1)

    self.all_architectures = sorted(
      set(architecture for df in self.dfs.values() for architecture in df["Architecture"].unique())
    )
    self.all_targets = sorted(
      set(target for df in self.dfs.values() for target in df["Target"].unique())
    )
    self.all_configurations = sorted(
      set(config for df in self.dfs.values() for config in df["Configuration"].unique())
    )
    self.all_frequencies = sorted(
      set(freq for df in self.dfs.values() for freq in df["Frequency"].unique() if isinstance(freq, (int, float)))
    )


    self.app = dash.Dash(__name__)
    self.app.title = "Odatix"

    self.app.server.register_error_handler(Exception, self.handle_flask_exception)

    self.setup_layout()
    self.setup_callbacks()

  def handle_flask_exception(self, e):
    """
    Handle flask exceptions
    """
    if self.old_settings is not None:
      term_mode.restore_mode(self.old_settings)
    internal_error(e, error_logfile, script_name)
    if not self.safe_mode:
      os._exit(-1)

  def load_yaml_files(self):
    """
    Load and validate YAML files from the specified path.
    """
    for yaml_file in self.yaml_files:
      file_path = os.path.join(self.result_path, yaml_file)
      try:
        fmax_data, range_data, units = self.get_yaml_data(file_path)
        all_data = {"Fmax": fmax_data, "Range": range_data}
        df = self.update_dataframe(all_data)

        # Validate YAML data
        if fmax_data == {} and range_data == {}:
          printc.warning(
              f'Result file "{yaml_file}" is empty or corrupted, skipping...', 
              script_name=script_name
          )
          printc.note(
              f'Run fmax synthesis or range synthesis with the correct settings to generate "{yaml_file}"',
              script_name=script_name
          )
          continue  # Skip to the next file

        # Validate the DataFrame
        if not isinstance(df, pd.DataFrame) or df.empty:
          printc.warning(
            f'Result file "{yaml_file}" is invalid, skipping...', 
            script_name=script_name
          )
          continue  # Skip to the next file

        # Additional checks on the DataFrame
        for col in self.required_columns:
          if col not in df.columns or df[col].isnull().all():
            printc.warning(
              f'Required column "{col}" missing or empty in "{yaml_file}", skipping...', 
              script_name=script_name
            )
            continue  # Skip to the next file

        # Add valid data
        self.all_data[yaml_file] = all_data
        self.units[yaml_file] = units
        self.valid_yaml_files.append(yaml_file)
        self.dfs[yaml_file] = df

        # Diagnostic messages
        if df.get("Fmax", pd.DataFrame()).empty:
          printc.note(f'No fmax results found in YAML file "{yaml_file}".', script_name=script_name)
        if df.get("Range", pd.DataFrame()).empty:
          printc.note(f'No range results found in YAML file "{yaml_file}".', script_name=script_name)

      except Exception as e:
        printc.warning(
            f'YAML file "{yaml_file}" is not a valid result file, skipping...', script_name=script_name
        )
        printc.cyan("Error details: ", end="", script_name=script_name)
        print(str(e))
        print(traceback.format_exc())

  def get_yaml_data(self, file_path):
    """
    Load YAML data from a file.
    """
    with open(file_path, "r") as file:
      yaml_content = yaml.safe_load(file)
      units = yaml_content.get("units", {})
      fmax_results = yaml_content.get("fmax_results", {})
      range_results = yaml_content.get("range_results", {})
      return fmax_results, range_results, units

  def update_dataframe(self, yaml_data):
    """n
    Combine 'fmax' and 'range' data into a single hierarchical DataFrame.
    """
    data = []
    
    for result_type, target_data in yaml_data.items():
      for target, architectures in target_data.items():
        for architecture, configurations in architectures.items():
          for config, metrics in configurations.items():
            if result_type == "Range":
              # For 'range', include frequency as a sub-level
              for frequency, freq_metrics in metrics.items():
                row = {
                  "Target": target,
                  "Architecture": architecture,
                  "Configuration": config,
                  "Frequency": frequency,
                  "Type": result_type
                }
                row.update(freq_metrics)
                data.append(row)
            else:
              # For 'fmax', use a single 'Frequency' entry
              row = {
                "Target": target,
                "Architecture": architecture,
                "Configuration": config,
                "Frequency": "fmax",  # Set a constant for fmax frequency
                "Type": result_type
              }
              row.update(metrics)
              data.append(row)

    # Create DataFrame and set multi-index
    df = pd.DataFrame(data)

    # Check if the dataframe contains the required columns and they are not empty
    required_columns = ["Target", "Architecture", "Configuration"]
    if not all(column in df.columns and not df[column].empty for column in required_columns):
      return None
    return df

  def update_metrics(self, yaml_data, results="Fmax"):
    """
    Update metrics based on YAML data.
    """
    metrics_from_yaml = set()

    for type in yaml_data.keys():
      for target_data in yaml_data[type].values():
        for architecture_data in target_data.values():
          for configuration_data in architecture_data.values():
            if type == "Fmax" and results in ["All", "Fmax"]:
              metrics_from_yaml.update(configuration_data.keys())
            elif type == "Range" and results in ["All", "Range"]:
              for frequency_data in configuration_data.values():
                metrics_from_yaml.update(frequency_data.keys())
          
    return metrics_from_yaml

  def setup_layout(self):
    """
    Setup the layout of the Dash application.
    """
    self.app.layout = html.Div(
      [dcc.Location(id="url", refresh=False), html.Div([html.Div(id="page-content", className="container")])]
    )

  def setup_callbacks(self):
    """
    Setup Dash callbacks for interactivity.
    """

    @self.app.callback(Output("page-content", "children"), [Input("url", "pathname")])
    def display_page(pathname):
      if pathname == "/xy":
        return page_xy.layout(self)
      elif pathname == "/vs":
        return page_vs.layout(self)
      elif pathname == "/radar":
        return page_radar.layout(self)
      else:
        return page_xy.layout(self)

    page_xy.setup_callbacks(self)
    page_vs.setup_callbacks(self)
    page_radar.setup_callbacks(self)

  def run(self):
    self.app.run(
      host='0.0.0.0',
      debug=True
    )


if __name__ == "__main__":
  explorer = ResultExplorer()
  explorer.run()

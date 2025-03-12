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
import numpy as np
import pandas as pd
import yaml
from flask import jsonify
import traceback

import odatix.explorer.navigation as navigation
import odatix.explorer.behaviors.setup_callbacks as setup_callbacks

import odatix.lib.printc as printc
from odatix.lib.utils import internal_error, merge_dicts_of_lists
import odatix.lib.term_mode as term_mode
import odatix.explorer.themes as themes

script_name = os.path.basename(__file__)
error_logfile = "odatix-explorer_error.log"

class ResultExplorer:
  def __init__(self, result_path="results", yaml_prefix="results_", old_settings=None, safe_mode=False, theme=themes.default_theme):
    self.result_path = result_path
    self.yaml_prefix = yaml_prefix
    self.old_settings = old_settings
    self.safe_mode = safe_mode
    self.param_domains = {}
    self.all_param_domains = {}

    if theme is None:
      self.start_theme = themes.default_theme
    elif theme not in themes.templates:
      printc.warning('Theme "' + str(theme) + '" does not exist. Using default theme.')
      self.start_theme = themes.default_theme
    else:
      self.start_theme = theme

    self.required_columns = ["Target", "Architecture", "Configuration"]

    # Check paths
    if not os.path.exists(result_path):
      printc.error('Could not find result path "' + result_path + '"', script_name=script_name)
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
    # self.all_configurations = sorted(
    #   set(config for df in self.dfs.values() for config in df["Configuration"].unique())
    # )
    self.all_configurations = set(config for df in self.dfs.values() for config in df["Configuration"].unique())
    self.all_frequencies = sorted(
      set(freq for df in self.dfs.values() for freq in df["Frequency"].unique() if isinstance(freq, (int, float)) or np.issubdtype(type(freq), np.number))
    )

    self.app = app = dash.Dash(__name__, use_pages=True)
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
        all_data = {"Fmax": fmax_data, "Custom Freq": range_data}
        df = self.update_dataframe(all_data, yaml_file)

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
        if df[df["Type"] == "Fmax"].empty:
          printc.note(f'No fmax results found in YAML file "{yaml_file}".', script_name=script_name)
        if df[df["Type"] == "Custom Freq"].empty:
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

      fmax_results = yaml_content.get("fmax_synthesis", {})
      legacy_fmax_results = yaml_content.get("fmax_results", {})
      fmax_results.update(legacy_fmax_results)

      range_results = yaml_content.get("custom_freq_synthesis", {})

      return fmax_results, range_results, units

  def update_dataframe(self, yaml_data, yaml_file):
    """
    Combine 'fmax' and 'custom freq' data into a single hierarchical DataFrame.
    """
    data = []
    all_param_domains = {}

    for result_type, target_data in yaml_data.items():
      for target, architectures in target_data.items():
        for architecture, configurations in architectures.items():
          for config, metrics in configurations.items():
            param_domains = metrics.pop("Param_Domains", {})

            if param_domains is not None:
              for param, value in param_domains.items():
                if param not in all_param_domains:
                  all_param_domains[param] = set()
                all_param_domains[param].add(value)
            else:
              param_domains = {}

            if result_type == "Custom Freq":
              for frequency, freq_metrics in metrics.items():
                row = {
                  "Target": target,
                  "Architecture": architecture,
                  "Configuration": config,
                  "Frequency": frequency,
                  "Type": result_type,
                  **freq_metrics,
                  **param_domains
                }
                data.append(row)
            else:
              row = {
                "Target": target,
                "Architecture": architecture,
                "Configuration": config,
                "Frequency": "fmax",
                "Type": result_type,
                **metrics,
                **param_domains
              }
              data.append(row)

    # Create DataFrame and set multi-index
    df = pd.DataFrame(data)

    # Check if the dataframe contains the required columns and they are not empty
    required_columns = ["Target", "Architecture", "Configuration"]
    if not all(column in df.columns and not df[column].empty for column in required_columns):
      return None

    self.param_domains[yaml_file] = {k: sorted(v) for k, v in all_param_domains.items()}
    self.all_param_domains = merge_dicts_of_lists(self.all_param_domains, self.param_domains[yaml_file])
    return df

  def update_metrics(self, yaml_data):
    """
    Update metrics based on YAML data.
    """
    metrics_from_yaml = []
    for type in yaml_data.keys():
      for target_data in yaml_data[type].values():
        for architecture_data in target_data.values():
          for configuration_data in architecture_data.values():
            if type == "Fmax":
              for k in configuration_data.keys():
                if k not in metrics_from_yaml:
                  metrics_from_yaml.append(k)
            elif type == "Custom Freq":
              for frequency_data in configuration_data.values():
                for k in frequency_data.keys():
                  if k not in metrics_from_yaml:
                    metrics_from_yaml.append(k)
    return metrics_from_yaml

  def setup_layout(self):
    """
    Setup the layout of the Dash application.
    """
    self.app.layout = html.Div(
      [
        navigation.top_bar(self),
        navigation.side_bar(self),
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="previous-url", data=""),
        html.Div(
          [dash.page_container],
          id="content",
          className="content",
          style={
            "marginLeft": navigation.side_bar_width,
            "width": "calc(100%-" + navigation.side_bar_width + ")",
            "height": "100%",
          },
        ),
      ],
      id="main-container",
      style={
        "width": "100%",
        "height": "100%",
        "display": "flex",
        "flex-direction": "column"
      },
    )

  def setup_callbacks(self):
    """
    Setup Dash callbacks for interactivity.
    """
    navigation.setup_sidebar_callbacks(self)
    setup_callbacks.setup_callbacks(self)

  def run(self):
    self.app.run(
      # host='0.0.0.0',
      host='127.0.0.1',
      debug=True
    )


if __name__ == "__main__":
  explorer = ResultExplorer()
  explorer.run()

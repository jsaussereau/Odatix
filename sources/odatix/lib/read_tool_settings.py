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
import yaml

from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
import odatix.lib.printc as printc

script_name = os.path.basename(__file__)

def read_tool_settings(tool, tool_settings_file, synth_type='fmax_synthesis'):
  """
  Reads the settings for a given EDA tool from a YAML configuration file.

  Args:
    tool (str): The name of the EDA tool.
    tool_settings_file (str): The path to the YAML configuration file.
    synth_type (str, optional): The type of synthesis to be used. 
                                Can be either 'fmax_synthesis' or 'custom_freq_synthesis'. 
                                Defaults to 'fmax_synthesis'.

  Returns:
    tuple: A tuple containing:
      - process_group (bool): Whether the process grouping is enabled.
      - default_metrics_file (str): Path to the default metrics file.
      - synthesis_command (list): The command for the selected synthesis type.
      - tool_test_command (list): The command to check if the tool is installed.

  Raises:
    SystemExit: If the settings file does not exist, is invalid, or if the requested tool 
                or synthesis type is not supported.
  """
  if not os.path.isfile(tool_settings_file):
    printc.error(
      f'Settings file "{tool_settings_file}", for the selected EDA tool "{tool}" does not exist', script_name
    )
    sys.exit(-1)

  # Load YAML settings file
  with open(tool_settings_file, "r") as f:
    try:
      settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    except Exception as e:
      printc.error(f'Settings file "{tool_settings_file}", for the selected EDA tool "{tool}" is not a valid YAML file', script_name)
      printc.cyan("Error details: ", end="", script_name=script_name)
      print(str(e))
      sys.exit(-1)

  # Retrieve global settings
  process_group, _ = get_from_dict("process_group", settings_data, tool_settings_file, default_value=True, script_name=script_name)
  report_path, _ = get_from_dict("report_path", settings_data, tool_settings_file, default_value="report", silent=True, script_name=script_name)
  default_metrics_file, _ = get_from_dict("default_metrics_file", settings_data, tool_settings_file, behavior=Key.MANTADORY, script_name=script_name)

  # Determine the current platform (Unix or Windows)
  platform_key = "windows" if sys.platform == 'win32' else "unix"

  # Ensure the corresponding section exists in the configuration file
  if platform_key not in settings_data:
    printc.error(f'The selected EDA tool "{tool}" does not support {platform_key}', script_name)
    sys.exit(-1)

  platform_settings = settings_data[platform_key]

  # Retrieve tool test command
  tool_test_command, tool_test_supported = get_from_dict("tool_test_command", platform_settings, tool_settings_file, silent=True, script_name=script_name)

  if not tool_test_supported:
    printc.error(f'The selected EDA tool "{tool}" is not supported on {platform_key} (tool_test_command is missing)', script_name)
    sys.exit(-1)

  # Retrieve synthesis command based on the requested type
  synthesis_key = "fmax_synthesis_command" if synth_type == 'fmax_synthesis' else "custom_freq_synthesis_command"
  synthesis_command, synthesis_supported = get_from_dict(synthesis_key, platform_settings, tool_settings_file, silent=True, script_name=script_name)

  if not synthesis_supported:
    printc.error(f'{synth_type.replace("_", " ").capitalize()} is not supported with the selected EDA tool "{tool}" on {platform_key}', script_name)
    sys.exit(-1)

  return process_group, report_path, synthesis_command, tool_test_command, default_metrics_file

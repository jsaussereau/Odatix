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
  if not os.path.isfile(tool_settings_file):
    printc.error(
      'Settings file "' + tool_settings_file + '", for the selected eda tool "' + tool + '" does not exist', script_name
    )
    sys.exit(-1)
  with open(tool_settings_file, "r") as f:
    try:
      settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    except Exception as e:
      printc.error('Settings file "' + tool_settings_file + '", for the selected eda tool "' + tool + '" is not a valid YAML file', script_name)
      printc.cyan("error details: ", end="", script_name=script_name)
      print(str(e))
      sys.exit(-1)

    # Mandatory keys
    process_group, _ = get_from_dict("process_group", settings_data, tool_settings_file, default_value=True, script_name=script_name)
    report_path, _ = get_from_dict("report_path", settings_data, tool_settings_file, default_value="report", silent=True, script_name=script_name)
    
    tool_test_command, _ = get_from_dict("tool_test_command", settings_data, tool_settings_file, behavior=Key.MANTADORY, script_name=script_name)

    default_metrics_file, _ = get_from_dict("default_metrics_file", settings_data, tool_settings_file, behavior=Key.MANTADORY, script_name=script_name)

    fmax_synthesis_command_windows, fmax_synthesis_supported_windows = get_from_dict("fmax_synthesis_command_windows", settings_data, tool_settings_file, silent=True, script_name=script_name)
    fmax_synthesis_command_unix, fmax_synthesis_supported_unix = get_from_dict("fmax_synthesis_command_unix", settings_data, tool_settings_file, silent=True, script_name=script_name)
   
    custom_freq_synthesis_command_unix, custom_freq_synthesis_supported_unix = get_from_dict("custom_freq_synthesis_command_unix", settings_data, tool_settings_file, silent=True, script_name=script_name)
    custom_freq_synthesis_command_windows, custom_freq_synthesis_supported_windows = get_from_dict("custom_freq_synthesis_command_windows", settings_data, tool_settings_file, silent=True, script_name=script_name)

    unix_supported = fmax_synthesis_supported_unix and custom_freq_synthesis_supported_unix
    windows_supported = fmax_synthesis_supported_windows and custom_freq_synthesis_supported_windows

    fmax_synthesis_supported = fmax_synthesis_supported_unix and fmax_synthesis_supported_windows
    custom_freq_synthesis_supported = custom_freq_synthesis_supported_unix and custom_freq_synthesis_supported_windows

    if synth_type == 'fmax_synthesis':
      if not fmax_synthesis_supported:
          printc.error('Fmax synthesis is not supported with the selected eda tool "' + tool + '"')
          sys.exit(-1)
      if sys.platform == 'win32':
        if fmax_supported_windows:
          command = fmax_synthesis_command_windows
        else:
          printc.error('Fmax synthesis is not supported with the selected eda tool "' + tool + '" on Windows')
          sys.exit(-1)
      else:
        if fmax_synthesis_supported_unix:
          command = fmax_synthesis_command_unix
        else:
          printc.error('Fmax synthesis is not supported with the selected eda tool "' + tool + '" on Unix')
          sys.exit(-1)
    elif synth_type == 'custom_freq_synthesis':
      if not fmax_synthesis_supported:
          printc.error('Custom freq synthesis is not supported with the selected eda tool "' + tool + '"')
          sys.exit(-1)
      if sys.platform == 'win32':
        if fmax_supported_windows:
          command = fmax_synthesis_command_windows
        else:
          printc.error('Custom freq synthesis is not supported with the selected eda tool "' + tool + '" on Windows')
          sys.exit(-1)
      else:
        if fmax_synthesis_supported_unix:
          command = fmax_synthesis_command_unix
        else:
          printc.error('Custom freq synthesis is not supported with the selected eda tool "' + tool + '" on Unix')
          sys.exit(-1)

    return process_group, report_path, command, tool_test_command, default_metrics_file

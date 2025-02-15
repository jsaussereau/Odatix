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
import yaml
from enum import Enum

from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
from odatix.lib.settings import OdatixSettings
import odatix.lib.printc as printc

class JobOutputFormatter:
  """
  Class to load and manage formatting settings from a YAML file.
  """

  # ANSI escape codes for terminal color formatting
  ansi_codes = {
    "end"           : "0",
    "bold"          : "1",
    "end_bold"      : "22",
    "black"         : "30",
    "red"           : "31",
    "green"         : "32",
    "yellow"        : "33",
    "blue"          : "34",
    "magenta"       : "35",
    "cyan"          : "36",
    "white"         : "37",
    "grey"          : "90",
    "light_red"     : "91",
    "light_green"   : "92",
    "light_yellow"  : "93",
    "light_blue"    : "94",
    "light_magenta" : "95",
    "light_cyan"    : "96",
    "light_white"   : "97",
  }

  # Mapping of message types to color codes
  message_types = {
    "error"         : "light_red",
    "crit_warning"  : "light_yellow",
    "warning"       : "yellow",
    "info"          : "light_cyan",
    "trace"         : "magenta",
  }

  def __init__(self, filename):
    """
    Initialize the JobOutputFormatter and load format settings.

    Args:
        filename (str): Path to the YAML configuration file.
    """
    self.initialized = False  # Indicates if formatting settings are successfully loaded
    self.filename = filename
    self._load_format_settings()  # Load formatting rules

  def _load_yaml(self):
    """
    Load YAML file and return its content as a dictionary.

    Returns:
        dict: Parsed YAML content.
    """
    try:
      with open(self.filename, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)
    except Exception as e:
      printc.error("Failed loading YAML file '{}': {}".format(self.filename, e))
      return {}

  def _load_format_settings(self):
    """
    Load format settings from the YAML file using `get_from_dict`, and store them
    as class attributes for easier access.

    The function:
      - Retrieves the format dictionary from the YAML file.
      - Populates attributes dynamically based on ANSI color codes and message types.

    Sets:
        - self.black, self.red, self.green, etc. (one per `ansi_codes` keys)
        - self.info, self.crit_warning, self.warning, self.error (from `message_types`)
    """
    yaml_data = self._load_yaml()

    if not yaml_data:
      yaml_data = {}

    # Retrieve formatting data from the YAML file
    format_data, defined = get_from_dict(
      key="format",
      input_dict=yaml_data,
      filename=self.filename,
      type=dict,
      default_value={}
    )

    # Assign values dynamically based on ansi_codes
    for key in JobOutputFormatter.ansi_codes.keys():
      setattr(self, key.lower(), format_data.get(key, []))

    # Assign values dynamically based on message_types
    for key in JobOutputFormatter.message_types.keys():
      setattr(self, key.lower(), format_data.get(key, []))

    # Mark as initialized if data is successfully loaded
    if defined:
      self.initialized = True

  def get_format_keys(self, category):
    """
    Retrieve the list of formatting keywords for a given category.

    Args:
        category (str): The formatting category (e.g., 'error', 'warning', 'red').

    Returns:
        list: List of associated formatting tags, or an empty list if not found.
    """
    return getattr(self, category.lower(), [])

  @staticmethod
  def code_to_escape_code(code):
    """
    Convert an ANSI code to an escape sequence.

    Args:
        code (str): ANSI color code.

    Returns:
        str: ANSI escape sequence.
    """
    return f"\x1b[{code}m"

  def replace_in_line(self, line):
    """
    Apply formatting to a given line based on defined message types and ANSI codes.

    Args:
        line (str): Input string to format.

    Returns:
        str: Formatted string with ANSI color codes.
    """
    if self.initialized:
      replaced = False

      # Iterate over message types (error, warning, etc.)
      for key in JobOutputFormatter.message_types.keys():
        escape_code = JobOutputFormatter.ansi_codes[JobOutputFormatter.message_types[key]]
        head = JobOutputFormatter.code_to_escape_code(escape_code)
        tail = ""

        # Apply bold to error and critical warning messages
        if key in ["error", "crit_warning"]:
          head += JobOutputFormatter.code_to_escape_code(JobOutputFormatter.ansi_codes["bold"])
          tail = JobOutputFormatter.code_to_escape_code(JobOutputFormatter.ansi_codes["end_bold"])

        # Apply formatting if a match is found
        for entry in self.get_format_keys(key):
          if entry in line:
            line = line.replace(entry, head + entry + tail)
            replaced = True
            break  # Stop after first match

        # Append reset code if formatting was applied
        if replaced:
          line += JobOutputFormatter.code_to_escape_code(JobOutputFormatter.ansi_codes["end"])
          break

      # Apply direct ANSI code replacements
      for key in JobOutputFormatter.ansi_codes.keys():
        code = JobOutputFormatter.ansi_codes[key]
        escape_code = JobOutputFormatter.code_to_escape_code(code)
        for entry in self.get_format_keys(key):
          line = line.replace(entry, escape_code)

    return line

# Example usage
if __name__ == "__main__":
  yaml_file = os.path.join(OdatixSettings.odatix_eda_tools_path, "vivado", "tool.yml")
  formatter = JobOutputFormatter(yaml_file)

  # Test text with different formatting tags
  text = [
    " default_text",
    " <bold><red>bold_red_text<end>",
    " <blue>blue_and_<green>green_text",
    " <red>red_text",
    " <end>default_text",
    " ERROR: error_text",
    " just a default formatted phrase passing by",
    " CRITICAL WARNING: critical_warning_text",
    " WARNING: warning_text",
    " INFO: info_text",
  ]

  # Apply formatting and print results
  for line in text:
    formatted_line = formatter.replace_in_line(line)
    print(formatted_line)

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

import re
import os
import yaml
from enum import Enum

from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
from odatix.lib.settings import OdatixSettings
import odatix.lib.printc as printc

class JobOutputFormatter:
  """
  Class to load and manage formatting settings from a YAML file.

  This class provides functionality to:
    - Load format settings from a YAML file.
    - Apply ANSI escape codes to text based on defined format rules.
    - Process log message tags (e.g., "ERROR:", "WARNING:").
    - Perform regex-based replacements on input text.
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

  # Mapping of message types to corresponding ANSI color codes
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
    self.initialized = False  # Flag to indicate if formatting settings are loaded
    self.filename = filename
    self._load_format_settings()  # Load format settings from the YAML file

  def _load_yaml(self):
    """
    Load YAML file and return its content as a dictionary.

    Returns:
        dict: Parsed YAML content, or an empty dictionary if an error occurs.
    """
    try:
      with open(self.filename, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)
    except Exception as e:
      printc.error("Failed loading YAML file '{}': {}".format(self.filename, e))
      return {}

  def _load_format_settings(self):
    """
    Load format settings from the YAML file and store them as class attributes.

    Extracts three sections from the YAML:
      - `logs`: Defines message types and their associated keywords (e.g., "ERROR:", "INFO:").
      - `tags`: Defines inline format tags (e.g., "<red>", "<bold>").
      - `replace`: Defines regex-based replacements.

    Attributes:
        log_tags (dict): Stores log categories and their associated keywords.
        format_tags (dict): Stores format tags and their corresponding escape codes.
        replace_rules (list): Stores regex-based replacement rules.
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

    # Extract format configuration
    self.log_tags = format_data.get("logs", {})
    self.format_tags = format_data.get("tags", {})
    self.replace_rules = format_data.get("replace", [])

    # Mark as initialized if data was successfully loaded
    if defined:
      self.initialized = True

  @staticmethod
  def code_to_escape_code(code):
    """
    Convert an ANSI code to its corresponding escape sequence.

    Args:
        code (str): ANSI color code.

    Returns:
        str: ANSI escape sequence.
    """
    return f"\x1b[{code}m"

  def replace_in_line(self, line):
    """
    Apply formatting and replacements to a given line.

    This method processes the following transformations:
      - Applies regex replacements from the `replace_rules` section.
      - Formats log messages (e.g., "ERROR:", "WARNING:") using ANSI escape codes.
      - Replaces inline format tags (e.g., "<red>", "<bold>") with ANSI escape codes.

    Args:
        line (str): Input string to format.

    Returns:
        str: Formatted string with ANSI escape codes applied.
    """
    if self.initialized:
      replaced = False

      # Apply regex-based replacements
      for rule in self.replace_rules:
        if isinstance(rule, dict):
          for pattern, replacement in rule.items():
            line = re.sub(pattern, lambda match: re.sub(r'\$(\d+)', lambda m: match.group(int(m.group(1))), replacement), line)
        else:
          printc.warning(f"Invalid replacement rule: {rule} (ignored)")

      replaced = False

      # Apply log message formatting (e.g., "ERROR:", "WARNING:")
      for key in JobOutputFormatter.message_types.keys():
        escape_code = JobOutputFormatter.ansi_codes[JobOutputFormatter.message_types[key]]
        head = JobOutputFormatter.code_to_escape_code(escape_code)
        tail = ""

        # Apply bold to error and critical warning messages
        if key in ["error", "crit_warning"]:
          head += JobOutputFormatter.code_to_escape_code(JobOutputFormatter.ansi_codes["bold"])
          tail = JobOutputFormatter.code_to_escape_code(JobOutputFormatter.ansi_codes["end_bold"])

        # Apply formatting if a match is found in log tags
        for entry in self.log_tags.get(key, {}):
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
        for entry in self.format_tags.get(key, []):
          line = line.replace(entry, escape_code)

    return line

# Example usage
if __name__ == "__main__":
  yaml_file = os.path.join(OdatixSettings.odatix_eda_tools_path, "vivado", "tool.yml")
  formatter = JobOutputFormatter(yaml_file)

  # Example input lines to format
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
    " Slack (VIOLATED)",
    " Slack (MET)",
  ]

  # Apply formatting and print results
  for line in text:
    formatted_line = formatter.replace_in_line(line)
    print(formatted_line)


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
import math
import itertools

import odatix.lib.printc as printc
from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
import odatix.lib.hard_settings as hard_settings

script_name = os.path.basename(__file__)

class ConfigGenerator:
  """
  Generates parameter configurations based on a YAML file defining variable types,
  ranges, and naming templates.
  """

  def __init__(self, path, debug=False):
    """
    Initialize the configuration generator by loading the YAML settings.
    
    Args:
        yaml_file (str): Path to the YAML configuration file.
    """
    self.path = path
    self.yaml_file = os.path.join(self.path, hard_settings.param_settings_filename)
    settings = self._load_yaml()
    generate_enabled, generate_defined = get_from_dict("generate", settings, self.yaml_file, default_value=False, silent=True, script_name=script_name)
    generate_settings, generate_settings_defined = get_from_dict("generate_settings", settings, self.yaml_file, silent=True, script_name=script_name)
    if generate_settings_defined:
      self.template, template_defined = get_from_dict("template", generate_settings, self.yaml_file, parent="generate_settings", behavior=Key.MANTADORY, script_name=script_name)
      self.name_template, name_template_defined = get_from_dict("name", generate_settings, self.yaml_file, parent="generate_settings", behavior=Key.MANTADORY, script_name=script_name)
      self.variables, variables_defined = get_from_dict("variables", generate_settings, self.yaml_file, parent="generate_settings", behavior=Key.MANTADORY, script_name=script_name)
      self.valid = generate_settings_defined and template_defined and name_template_defined and variables_defined and generate_defined
    else:
      self.valid = False

    if not generate_defined and generate_settings_defined:
      printc.warning('"generate_settings" is defined while "generate" is not. Disabling configuration generation.', script_name)
    if generate_defined and generate_enabled and not generate_settings_defined:
      printc.error('Configuration generation is enabled while "generate_settings" is not defined.', script_name)

    self.enabled = generate_enabled
    self.debug = debug

  def _load_yaml(self):
    """
    Load the YAML configuration file.
    
    Returns:
        dict: Parsed YAML data.
    """
    if not os.path.isfile(self.yaml_file):
      printc.error(f"YAML file '{self.yaml_file}' does not exist.")
      sys.exit(-1)

    with open(self.yaml_file, "r") as f:
      try:
        return yaml.safe_load(f)
      except yaml.YAMLError as e:
        printc.error(f"Invalid YAML file '{self.yaml_file}': {e}")
        sys.exit(-1)

  def evaluate_expression(self, expr, values_map):
    """
    Evaluate a mathematical expression using the current values of variables.

    Args:
        expr (str): The expression to evaluate.
        values_map (dict): A dictionary containing values for referenced variables.

    Returns:
        Any: The result of evaluating the expression.
    """
    safe_env = {var: values_map[var] for var in values_map}
    safe_env["math"] = math
    expr = expr.replace("^", "**")  # Replace '^' with '**' for Python exponentiation
    expr = expr.replace("$", "")
    expr = expr.replace("{", "")
    expr = expr.replace("}", "")
    try:
      return eval(expr, {"__builtins__": None}, safe_env)
    except Exception as e:
      printc.error(f"Failed to evaluate expression '{expr}': {e}", script_name)
      return None

  def generate(self):
    """
    Generate all possible parameter combinations based on the configuration.
    
    Returns:
        dict: A dictionary where keys are generated names and values are formatted templates.
    """
    values_dict = {}

    if not self.valid or not self.enabled:
      return values_dict

    # Generate all possible values for each variable except function and concatenate types
    generated_values = {var: self.generate_values(var_config, var) for var, var_config in self.variables.items() if var_config["type"] not in ["function", "concatenate"]}
    
    if self.debug:
      print(f"Generated values per variable: {generated_values}")

    # Create cartesian product of all variable values
    variable_names = list(generated_values.keys())
    all_combinations = list(itertools.product(*generated_values.values()))
    if self.debug:
      print(f"Total combinations to process: {len(all_combinations)}")

    # Generate the final dictionary
    for combination in all_combinations:
      value_map = dict(zip(variable_names, combination))

      # Handle function type variables
      for var, config in self.variables.items():
        if config["type"] == "function":
          expr = config["settings"]["op"]
          value_map[var] = self.evaluate_expression(expr, value_map)

      # Handle concatenation type
      for var, config in self.variables.items():
        if config["type"] == "concatenate":
          sources = config["settings"]["sources"]
          value_map[var] = "".join(str(value_map[source]) for source in sources)

      # Format values
      formatted_values = {var: self.format_value(value_map[var], self.variables[var].get("format", "{}")) for var in value_map}

      # Replace in template and name
      formatted_template = self.template
      formatted_name = self.name_template

      for var, value in formatted_values.items():
        formatted_template = formatted_template.replace(f"${var}", str(value)).replace(f"${{{var}}}", str(value))
        formatted_name = formatted_name.replace(f"${var}", str(value)).replace(f"${{{var}}}", str(value))

      values_dict[formatted_name] = formatted_template

    if self.debug:
      print(f"\nGenerated Parameters ({len(values_dict)} total):")

    return values_dict

  def generate_values(self, config, name):
    """
    Generate values for a given variable configuration.
    
    Args:
        config (dict): Configuration settings for value generation.

    Returns:
        list: A list of generated values.
    """
    values = []

    value_type, value_type_defined = get_from_dict("type", config, self.yaml_file, parent=name, behavior=Key.MANTADORY, script_name=script_name)
    settings, settings_defined = get_from_dict("settings", config, self.yaml_file, parent=name, behavior=Key.MANTADORY, script_name=script_name)
    if not value_type_defined or not settings_defined:
      return values


    whitelist, _ = get_from_dict("whitelist", settings, self.yaml_file, parent=name + "[settings]", silent=True, default_value=None, script_name=script_name)
    blacklist, _ = get_from_dict("blacklist", settings, self.yaml_file, parent=name + "[settings]", silent=True, default_value=None, script_name=script_name)

    if value_type == "range":
      from_value, from_defined = get_from_dict("from", settings, self.yaml_file, parent=name + "[settings]", behavior=MANTADORY, script_name=script_name)
      to_value, to_defined = get_from_dict("to", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      step_value, step_defined = get_from_dict("step", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      if to_defined and from_defined and step_defined:
        values = list(range(from_value, to_value + 1, step_value))
      else:
        printc.note('You can define it like this:', script_name)
        printc.magenta("type: range:")
        printc.magenta("settings:")
        printc.magenta("  from: XXX")
        printc.magenta("  to: XXX")
        printc.magenta("  step: XXX")
        return []

    elif value_type == "power_of_two":
      from_value, from_defined = get_from_dict("from_2^", settings, self.yaml_file, parent=name + "[settings]", type=int, silent=True, script_name=script_name)
      to_value, to_defined = get_from_dict("to_2^", settings, self.yaml_file, parent=name + "[settings]", type=int, silent=True, script_name=script_name)
      if to_defined and from_defined:
        values = [2**i for i in range(int(from_value), int(to_value) + 1)]
      else:
        from_value, from_defined = get_from_dict("from", settings, self.yaml_file, parent=name + "[settings]", type=int, silent=True, script_name=script_name)
        to_value, to_defined = get_from_dict("to", settings, self.yaml_file, parent=name + "[settings]", type=int, silent=True, script_name=script_name)
        if to_defined and from_defined:
          values = [2**i for i in range(int(math.log2(from_value)), int(math.log2(to_value)) + 1)]
        else:
          printc.error('Cannot find a valid power_of_two definition for "' + name + "[settings]" + '", in "' + self.yaml_file + '".', script_name)
          printc.note('You can define it like this:', script_name)
          printc.magenta("type: power_of_two:")
          printc.magenta("settings:")
          printc.magenta("  from_2^: XXX")
          printc.magenta("  to_2^: XXX")
          printc.cyan("or ")
          printc.magenta("type: power_of_two:")
          printc.magenta("settings:")
          printc.magenta("  from: XXX")
          printc.magenta("  to: XXX")
          return []

    elif value_type == "list":
      list_values, list_defined = get_from_dict("list", settings, self.yaml_file, parent=name + "[settings]", type=list, behavior=Key.MANTADORY, script_name=script_name)
      if list_defined:
        values = list_values
      else:
        printc.note('You can define it like this:', script_name)
        printc.magenta("type: list:")
        printc.magenta("settings:")
        printc.magenta("  list: [XXX, XXX, XXX]")
        return []
    elif value_type == "multiples":
      from_value, from_defined = get_from_dict("from", settings, self.yaml_file, parent=name + "[settings]", behavior=MANTADORY, script_name=script_name)
      to_value, to_defined = get_from_dict("to", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      base_value, base_defined = get_from_dict("base", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      if to_defined and from_defined and base_defined:
        values = [x for x in range(from_value, to_value + 1) if x % base_value == 0]
      else:
        printc.note('You can define it like this:', script_name)
        printc.magenta("type: multiples:")
        printc.magenta("settings:")
        printc.magenta("  from: XXX")
        printc.magenta("  to: XXX")
        printc.magenta("  base: XXX")
        return []

    # Apply whitelist/blacklist filtering
    if whitelist is not None:
      values = [v for v in values if v in whitelist]

    if blacklist is not None:
      values = [v for v in values if v not in blacklist]

    return values

  def format_value(self, value, format_string):
    """
    Format a value using the specified format string.

    Args:
        value (any): The value to format.
        format_string (str): The format string.

    Returns:
        str: Formatted value as a string.
    """
    if isinstance(value, list):
      return "".join(str(v) for v in value)

    try:
      return format_string % value
    except TypeError:
      return str(value)

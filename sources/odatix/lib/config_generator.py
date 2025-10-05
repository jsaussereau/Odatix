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
from typing import Optional

import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.get_from_dict import get_from_dict, Key

script_name = os.path.basename(__file__)

dimension_types = ("bool", "range", "list", "multiples", "power_of_two")
modification_types = ("union", "disjunctive_union", "intersection", "difference")
combo_types = ("function", "conversion", "format")

######################################
# Generator
######################################

class ConfigGenerator:
  """
  Generates parameter configurations based on a YAML file defining variable types,
  ranges, and naming templates.
  """

  def __init__(self, path: str = "", data: Optional[dict] = None, silent: bool = False, debug: bool = False):
    """
    Initialize the configuration generator.
    
    Args:
        path (str): Path to the directory containing the "_settings.yml" file.
        data (dict): Optional pre-loaded YAML data to use instead of reading from file.
        silent (bool): If True, suppress warnings for missing keys.
        debug (bool): If True, print debug information.
    """
    self.path = path
    self.silent = silent
    self.debug = debug

    self.template = ""
    self.name_template = ""
    self.variables = {}
    self.valid = False
    self.enabled = False

    if data is not None:
      self.yaml_file = "<provided_data>"
      self.data = data
    else:
      self.yaml_file = os.path.join(self.path, hard_settings.param_settings_filename)
      self._load_yaml()

    self._validate_keys(self.data)

  def _load_yaml(self):
    """
    Load YAML settings and validate the presence of necessary keys.
    
    Returns:
        dict: Parsed YAML data.
    """
    self.data = {}
    if not os.path.isfile(self.yaml_file):
      printc.error(f"YAML file '{self.yaml_file}' does not exist.")
      sys.exit(-1)

    try:
      with open(self.yaml_file, "r") as f:
        data = yaml.safe_load(f)
        if data is None:
          printc.error(f"YAML file \"{self.yaml_file}\" is empty!")
          sys.exit(-1)
    except yaml.YAMLError as e:
      printc.error(f"Invalid YAML file \"{self.yaml_file}\": {e}")
      sys.exit(-1)
    self.data = data

  def _validate_keys(self, data):
    # Check main keys
    hide = not self.debug
    generate_enabled, generate_defined = get_from_dict("generate_configurations", data, self.yaml_file, default_value=False, silent=hide, script_name=script_name)
    generate_settings, generate_settings_defined = get_from_dict("generate_configurations_settings", data, self.yaml_file, silent=hide, script_name=script_name)
    
    if generate_settings_defined:
      self.template, template_defined = get_from_dict("template", generate_settings, self.yaml_file, parent="generate_configurations_settings", behavior=Key.MANTADORY, script_name=script_name)
      self.name_template, name_template_defined = get_from_dict("name", generate_settings, self.yaml_file, parent="generate_configurations_settings", type=str, behavior=Key.MANTADORY, script_name=script_name)
      self.variables, variables_defined = get_from_dict("variables", generate_settings, self.yaml_file, parent="generate_configurations_settings", type=dict, behavior=Key.MANTADORY, script_name=script_name)
      self.valid = generate_settings_defined and template_defined and name_template_defined and variables_defined and generate_defined
    else:
      self.valid = False

    # Concat all strings if template is a list
    if isinstance(self.template, list):
      self.template = "\n".join(map(str, self.template)) 

    if not generate_defined and generate_settings_defined and not self.silent:
      printc.warning('"generate_configurations_settings" is defined while "generate_configurations" is not. Disabling configuration generation.', script_name)
    if generate_defined and generate_enabled and not generate_settings_defined and not self.silent:
      printc.error('Configuration generation is enabled while "generate_configurations_settings" is not defined.', script_name)

    self.enabled = generate_enabled

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
    Includes support for union, disjunctive_union, intersection, and difference.
    
    Returns:
        dict: A dictionary where keys are generated names and values are formatted templates.
        dict: A dictionary where keys are variable names and values are lists of all possible values for those variables.
    """
    if not self.valid or not self.enabled:
      return {}

    sources_used = set()
    for variable, config in self.variables.items():
      value_type, value_type_defined = get_from_dict("type", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
      if value_type in modification_types:
        settings, settings_defined = get_from_dict("settings", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
        if not settings_defined:
          return {}
        sources, sources_defined = get_from_dict("sources", settings, self.yaml_file, parent=f"{variable}[settings]", behavior=Key.MANTADORY, type=list, script_name=script_name)
        if not sources_defined:
          return {}
        for source in sources:
          sources_used.add(source)
      elif value_type not in dimension_types and value_type not in combo_types:
        printc.error(f'Invalid type \"{value_type}\" for variable "{variable}", in ' + self.yaml_file + '".', script_name)
        return {}

    dimension_vars = {}
    for variable, config in self.variables.items():
      value_type, _ = get_from_dict("type", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
      if value_type in dimension_types and variable not in sources_used:
        dimension_vars[variable] = self.generate_values_for_dim(variable, config)

    result_set = set()
    for variable, config in self.variables.items():
      value_type, _ = get_from_dict("type", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
      if value_type in modification_types:
        settings, settings_defined = get_from_dict("settings", config, self.yaml_file, behavior=Key.MANTADORY, script_name=script_name)
        if settings_defined:
          sources, sources_defined = get_from_dict("sources", settings, self.yaml_file, behavior=Key.MANTADORY, default_value=[], type=list, script_name=script_name)
          if sources_defined:
            sources = [source.replace("$", "").replace("{", "").replace("}", "") for source in sources]
            sets = [set(self.generate_values_for_dim(source, self.variables.get(source, {}))) for source in sources if source in self.variables]
            
            if value_type == "union":
              result_set = set.union(*sets)
            elif value_type == "disjunctive_union":
              result_set = set.union(*sets) - set.intersection(*sets)
            elif value_type == "intersection":
              result_set = set.intersection(*sets)
            elif value_type == "difference":
              if len(sets) == 2:
                result_set = sets[0] - sets[1]
              else:
                result_set = set()
                printc.error(f'{variable} -> The\"difference\" operation only supports \"sources\" having exactly two elements, in ' + self.yaml_file + '".', script_name)       
            else:
              result_set = set()
              printc.warning(f'Invalid operation for variable "{variable}", in ' + self.yaml_file + '".', script_name)

            dimension_vars[variable] = sorted(result_set)

    if self.debug:
      printc.note(f"dimension_vars after set operations: {dimension_vars}", script_name)

    var_names = list(dimension_vars.keys())
    combos = list(itertools.product(*(dimension_vars[k] for k in var_names)))
    final_configs = {}
    all_vars_values= {}
    values = set()

    for combo in combos:
      value_map = dict(zip(var_names, combo))
      for variable, config in self.variables.items():
        value_type, _ = get_from_dict("type", config, self.yaml_file, parent=variable, behavior=Key.MANTADORY, script_name=script_name)
        if value_type == "function":
          settings, defined = get_from_dict("settings", config, self.yaml_file, silent=True, script_name=script_name)
          if defined:
            op, _ = get_from_dict("op", settings, self.yaml_file, silent=True, script_name=script_name)
            if op:
              evaluated_expr = self.evaluate_expression(op, value_map)
              value_map[variable] = evaluated_expr
              values.add(evaluated_expr)
        elif value_type == "format":
          settings, defined = get_from_dict("settings", config, self.yaml_file, silent=True, script_name=script_name)
          if defined:
            source, _ = get_from_dict("source", settings, self.yaml_file, silent=True, script_name=script_name)
            formatted_values = {}
            for k, v in value_map.items():
              var_cfg = self.variables.get(k, {})
              format_str = None
              if var_cfg.get("type") == "format":
                settings = var_cfg.get("settings", {})
                format_str = settings.get("format", "{}")
              else:
                format_str = var_cfg.get("format", "{}")
              formatted_values[k] = self.format_value(v, format_str)
            for name, value in formatted_values.items():
              source = source.replace(f"${name}", str(value)).replace(f"${{{name}}}", str(value))
            value_map[variable] = source
            values.add(source)
        elif value_type == "conversion":
          settings, defined = get_from_dict("settings", config, self.yaml_file, silent=True, script_name=script_name)
          if defined:
            from_type, _ = get_from_dict("from", settings, self.yaml_file, silent=True, script_name=script_name)
            to_type, _ = get_from_dict("to", settings, self.yaml_file, silent=True, script_name=script_name)
            source, _ = get_from_dict("source", settings, self.yaml_file, silent=True, script_name=script_name)
            source = source.replace("$", "").replace("{", "").replace("}", "")
            if source in value_map:
              converted = self.apply_conversion(value_map[source], from_type, to_type)
              value_map[variable] = converted
              values.add(converted)
            else:
              printc.warning(f'Source "{source}" not found for conversion variable "{variable}"', script_name)
        all_vars_values[variable] = sorted(values)

      formatted_values = {}
      for k, v in value_map.items():
        var_cfg = self.variables.get(k, {})
        format_str = None
        if var_cfg.get("type") == "format":
          settings = var_cfg.get("settings", {})
          format_str = settings.get("format", "{}")
        else:
          format_str = var_cfg.get("format", "{}")
        formatted_values[k] = self.format_value(v, format_str)
      final_template = self.template
      final_name = self.name_template
      for name, value in formatted_values.items():
        final_template = final_template.replace(f"${name}", str(value)).replace(f"${{{name}}}", str(value))
        final_name = final_name.replace(f"${name}", str(value)).replace(f"${{{name}}}", str(value))

      final_configs[final_name] = final_template

    if self.debug:
      printc.note(f"generated {len(final_configs)} configurations.", script_name)

    all_dim_vard_values = {k: sorted(set(v)) if isinstance(v, list) else [v] for k, v in dimension_vars.items()}
    all_vars_values.update(all_dim_vard_values)
    return final_configs, all_vars_values

  def generate_values_for_dim(self, var_name, var_config):
    """
    Generate the list of values for a dimension variable (bool/range/list/multiples/power_of_two).
    If it's 'function' or 'union', we skip for dimension creation here.
    """
    value_type, value_type_defined = get_from_dict("type", var_config, self.yaml_file, behavior=Key.MANTADORY, script_name=script_name)
    if value_type in ("function", "union"):
      return []

    return self.generate_values(var_config, var_name)

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
    
    no_settings_var = value_type == "bool"
    settings, settings_defined = get_from_dict("settings", config, self.yaml_file, parent=name, behavior=Key.MANTADORY, silent=no_settings_var, script_name=script_name)
    if not value_type_defined or (not settings_defined and value_type != "bool"):
      return values

    if no_settings_var:
      whitelist = None
      blacklist = None
    else:
      whitelist, _ = get_from_dict("whitelist", settings, self.yaml_file, parent=name + "[settings]", silent=True, default_value=None, script_name=script_name)
      blacklist, _ = get_from_dict("blacklist", settings, self.yaml_file, parent=name + "[settings]", silent=True, default_value=None, script_name=script_name)

    if value_type == "bool":
      values = [0, 1]

    elif value_type == "range":
      from_value, from_defined = get_from_dict("from", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      to_value, to_defined = get_from_dict("to", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
      step_value, _ = get_from_dict("step", settings, self.yaml_file, parent=name + "[settings]", default_value=1, silent=True, script_name=script_name)
      if to_defined and from_defined:
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
      from_value, from_defined = get_from_dict("from", settings, self.yaml_file, parent=name + "[settings]", behavior=Key.MANTADORY, script_name=script_name)
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

  def apply_conversion(self, value, from_type, to_type):
    """
    Apply number base conversions.

    Args:
        value (str): The value to convert.
        from_type (str): What to convert from.
        to_type (str): What to convert to.

    Returns:
        str: Converted value.
    """
    try:
      if from_type == "bin":
        dec_value = int(value, 2)
        if to_type == "dec":
          return str(dec_value)
        elif to_type == "hex":
          return hex(dec_value)[2:]
      elif from_type == "dec":
        dec_value = int(value)
        if to_type == "bin":
          return bin(dec_value)[2:]
        elif to_type == "hex":
          return hex(dec_value)[2:]
      elif from_type == "hex":
        dec_value = int(value, 16)
        if to_type == "bin":
          return bin(dec_value)[2:]
        elif to_type == "dec":
          return str(dec_value)
      printc.warning(f'Conversion from "{from_type}" to "{to_type}" is not supported', script_name)
    except ValueError:
      printc.error(f'Invalid value "{value}" for conversion from "{from_type}" to "{to_type}"', script_name)
    return value

  def format_value(self, value, format_string):
    """
    Format a value using the specified format string.

    Args:
        value (any): The value to format.
        format_string (str): The format string.

    Returns:
        str: Formatted value as a string.
    """
    if format_string is None:
      value = value
    if isinstance(value, list):
      value = "".join(str(v) for v in value)

    try:
      formatted_value = format_string % float(value)
      return formatted_value
    except (TypeError, ValueError):
      return str(value)

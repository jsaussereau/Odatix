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
import re
import csv
import argparse

import odatix.lib.printc as printc
from odatix.lib.utils import read_from_list, create_dir, KeyNotInListError, BadValueInListError
from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
import odatix.lib.settings as settings
from odatix.lib.settings import OdatixSettings
from odatix.lib.variables import replace_variables, Variables

current_dir = os.path.dirname(os.path.abspath(__file__))

banned_metrics = []
banned_arch = []

######################################
# Settings
######################################

DEFAULT_FORMAT = "yml"

tool_settings_filename = "tool.yml"

simulations_dir = "simulations"
status_done = "Done: 100%"

script_name = os.path.basename(__file__)


######################################
# Parse Arguments
######################################


def add_arguments(parser):
  """
  Add command-line arguments for configuring the script.

  Args:
      parser (ArgumentParser): Argument parser instance.
  """
  parser.add_argument("-t", "--tool", default="all", help="eda tool in use, or 'all' (default: all)")
  parser.add_argument(
    "-f",
    "--format",
    choices=["csv", "yml", "all"],
    default=DEFAULT_FORMAT,
    help="Output format: csv, yml, or all (default: " + DEFAULT_FORMAT + ")",
  )
  parser.add_argument("-u", "--use_benchmark", action="store_true", help="Use benchmark values in yaml file")
  parser.add_argument("-B", "--benchmark_file", help="Benchmark file")
  parser.add_argument("-w", "--work", help="Work directory")
  parser.add_argument("-r", "--respath", help="Result path")
  parser.add_argument("-m", "--metrics", help="Metrics definition file")
  parser.add_argument(
    "-c",
    "--config",
    default=OdatixSettings.DEFAULT_SETTINGS_FILE,
    help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
  )


def parse_arguments():
  """
  Parse and return command-line arguments.

  Returns:
      Namespace: Parsed command-line arguments.
  """
  parser = argparse.ArgumentParser(description="Process FPGA or ASIC results")
  add_arguments(parser)
  return parser.parse_args()


######################################
# Parsing functions
######################################


def parse_regex(file, pattern, group_id, error_prefix=""):
  """
  Parse a file with a regex to extract a specific value.

  Args:
      file (str): Path to the file.
      pattern (str): Regular expression to search for.
      group_id (int): Regex group ID to extract.
      error_prefix (str): Prefix for error messages.

  Returns:
      str | None: The matched value, or None if not found or on error.
  """
  if not os.path.isfile(file):
    printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
    return None
  with open(file, "r") as f:
    try:
      content = f.read()
      match = re.search(pattern, content)
      if match:
        return match.group(group_id)
    except Exception as e:
      printc.error(
        error_prefix + 'Could not get value from regex "' + pattern + '" in file "' + file + '": ' + str(e), script_name=script_name
      )
      return None

  printc.error(error_prefix + 'No match for regex "' + pattern + '" in file "' + file + '"', script_name=script_name)
  return None


def parse_csv(file, key, error_prefix=""):
  """
  Parse a CSV file to extract a value associated with a specific key.

  Args:
      file (str): Path to the CSV file.
      key (str): Key to search for in the file.
      error_prefix (str): Prefix for error messages.

  Returns:
      str | None: The value corresponding to the key, or None if not found.
  """
  if not os.path.isfile(file):
    printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
    return None
  with open(file, mode="r") as csv_file:
    try:
      reader = csv.DictReader(csv_file)
      for row in reader:
        if key in row:
          return row[key]
        else:
          printc.error(error_prefix + 'Could not find key "' + key + '" in csv "' + file + '"', script_name=script_name)
    except csv.Error as e:
      printc.error(error_prefix + 'An error occurred while reading csv file "' + file + '": ' + str(e), script_name=script_name)
      return None

  return None

def parse_yaml(file, key=None, error_prefix=""):
  """
  Parse a YAML file to extract a value associated with a key.

  Args:
      file (str): Path to the YAML file.
      key (str): Key to search for in the YAML data.
      error_prefix (str): Prefix for error messages.

  Returns:
      Any | None: Extracted value, or None if not found or on error.
  """
  if not os.path.isfile(file):
    printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
    return None

  with open(file, "r") as yaml_file:
    try:
      data = yaml.safe_load(yaml_file)
      if key:
        value = data.get(key, None)
        if value is None:
          printc.error(error_prefix + 'Could not find key "' + key + '" in yaml "' + file + '"', script_name=script_name)
        return value
      return data
    except yaml.YAMLError as e:
      printc.error(f'{error_prefix}Could not parse yaml file "{file}": {str(e)}')
      return None

  if not os.path.isfile(file):
    printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
    return None


######################################
# Validate Tool Settings
######################################


def validate_tool_settings(file_path):
  """
  Validate and load tool settings from a YAML file.

  Args:
      file_path (str): Path to the tool settings file.

  Returns:
      dict | None: Loaded settings as a dictionary, or None if invalid.
  """
  if not os.path.isfile(file_path):
    printc.error('Tool settings file "' + os.path.realpath(file_path) + '" does not exist', script_name)
    return None
  with open(file_path, "r") as file:
    try:
      tool_settings = yaml.safe_load(file)
      return tool_settings
    except yaml.YAMLError as e:
      printc.error("Error in tool configuration file: " + str(e), script_name)
      return None


######################################
# Extract Tool Metrics
######################################


def extract_metrics(metrics_data, metrics_file, cur_path, arch, arch_path, use_benchmark, benchmark_file, type="fmax_synthesis"):
  """
  Extract metrics from synthesis results based on tool-specific settings.

  This function processes various types of synthesis metrics, such as 
  `fmax_synthesis` or `custom_freq_synthesis`, by parsing tool output 
  files (e.g., regex, CSV, YAML) and optionally using benchmark values.

  Args:
      metrics_data (dict): The loaded settings for the EDA tool, containing 
                            metric definitions.
      metrics_file (str): Path to the YAML file containing tool settings.
      cur_path (str): Current path to the directory containing synthesis results.
      arch (str): Identifier for the architecture being processed.
      arch_path (str): Full path to the architecture-specific directory.
      use_benchmark (bool): Whether to use benchmark data for extracting metrics.
      benchmark_file (str): Path to the benchmark YAML file.
      type (str): Type of synthesis (e.g., "fmax_synthesis" or "custom_freq_synthesis").
                  Defaults to "fmax_synthesis".

  Returns:
      tuple: 
          - results (dict): A dictionary containing extracted metric values.
            Keys are metric names, and values are the corresponding extracted results.
          - units (dict): A dictionary mapping metric names to their units, if specified.
            If no unit is defined for a metric, it is omitted from this dictionary.

  Raises:
      KeyNotInListError: If a required key is missing in `metrics_data`.
      BadValueInListError: If a value in `metrics_data` is invalid for a metric.
      ValueError: When parsing or formatting a metric value fails.

  Notes:
      - Metrics are extracted from files (regex, CSV, or YAML) defined in the tool 
        settings. Each metric can specify its own type and extraction settings.
      - Metrics marked as "benchmark_only" are only included if `use_benchmark` is True.
      - Global lists `banned_metrics` and `banned_arch` are updated to exclude metrics
        or architectures that encounter errors during extraction.

  Examples:
      For `type="fmax_synthesis"`, metrics defined under "fmax_synthesis_metrics" 
      in the `metrics_data` file are prioritized. Common metrics (defined under 
      "metrics") are always included.
  """
  global banned_metrics
  results = {}
  units = {}
  error_prefix =  arch_path + " => "
  metrics = {}
  
  if type == "fmax_synthesis":
    fmax_metrics = read_from_list("fmax_synthesis_metrics", metrics_data, metrics_file, raise_if_missing=False, print_error=False, script_name=script_name)
    if fmax_metrics != False:
      metrics.update(fmax_metrics)
  elif type == "custom_freq_synthesis":
    range_metrics = read_from_list("custom_freq_synthesis_metrics", metrics_data, metrics_file, raise_if_missing=False, print_error=False, script_name=script_name)
    if range_metrics != False:
      metrics.update(range_metrics)

  common_metrics = read_from_list("metrics", metrics_data, metrics_file, raise_if_missing=False, print_error=False, script_name=script_name)
  if common_metrics != False:
    metrics.update(common_metrics)

  for metric, content in metrics.items():
    if metric in banned_metrics:
      continue

    try:
      type = read_from_list("type", content, metrics_file, parent=metric, script_name=script_name)
      settings = read_from_list("settings", content, metrics_file, parent=metric, script_name=script_name)
    except (KeyNotInListError, BadValueInListError):
      banned_metrics.append(metric)
      continue

    benchmark_only = read_from_list("benchmark_only", content, metrics_file, parent=metric, raise_if_missing=False, type=bool, print_error=False, script_name=script_name)
    if benchmark_only and not use_benchmark:
      banned_metrics.append(metric)
      continue

    if type == "regex":
      try:
        file = read_from_list("file", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
        pattern = read_from_list("pattern", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
        group_id = read_from_list("group_id", settings, metrics_file, parent=metric + "[settings]", type=int, script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      value = parse_regex(os.path.join(cur_path, file), pattern, group_id, error_prefix)
    elif type == "csv":
      try:
        file = read_from_list( "file", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
        key = read_from_list("key", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      value = parse_csv(os.path.join(cur_path, file), key, error_prefix)
    elif type == "yaml":
      try:
        file = read_from_list("file", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      key, _ = get_from_dict("key", settings, metrics_file, parent=metric + "[settings]", silent=True, default_value=None, script_name=script_name)
      value = parse_yaml(os.path.join(cur_path, file), key, error_prefix)
    elif type == "benchmark":
      if not use_benchmark:
        banned_metrics.append(metric)
        continue
      if arch in banned_arch:
        continue
      try:
        key = read_from_list("key", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      key = arch + "[" + key + "]"
      value = parse_yaml(benchmark_file, key, error_prefix)
      if value is None:
        banned_arch.append(arch)
    elif type == "operation":
      try:
        op = read_from_list("op", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      value = calculate_operation(op, results, error_prefix)
    else:
      printc.error(
        'Unsupported metric type "' + type + '" specified for metric "' + metric + '" in "' + metrics_file + '"',
        script_name=script_name,
      )
      banned_metrics.append(metric)
      continue

    # Apply formatting if specified
    if value is not None and "format" in content:
      try:
        value = convert_to_numeric(content["format"] % float(value))
      except ValueError:
        pass  # printc.warning(f"Failed to format value {value} for metric {metric}", script_name)

    # Append unit if specified
    if value is not None:
      results[metric] = value
      if "unit" in content:
        units[metric] = content["unit"]
    else:
      results[metric] = None

  return results, units


######################################
# Misc functions
######################################


def corrupted_directory(directory):
  """
  Log a warning indicating that a synthesis directory is corrupted or incomplete.

  Args:
      directory (str): Path to the directory that is flagged as corrupted.
  """
  printc.warning(
    directory + " => Synthesis has not finished or directory has been corrupted", script_name
  )


def convert_to_numeric(data):
  """
  Convert a string representation of a number to a numeric type (int or float).

  Args:
      data (str): The string to convert.

  Returns:
      int | float | str: The numeric representation of the input if conversion is successful;
      otherwise, the original string.
  """
  try:
    if "." in data:
      return float(data)
    return int(data)
  except ValueError:
    return data


def calculate_operation(op_str, results, error_prefix=""):
  """
  Evaluate a mathematical operation on the extracted results.

  Args:
      op_str (str): The mathematical operation as a string (e.g., "a + b / c").
      results (dict): Dictionary of metric values available for the operation.
      error_prefix (str): Prefix for error messages to provide context.

  Returns:
      float | int | None: The result of the evaluated operation, or None if an error occurs.
  """
  try:
    local_vars = {k: v for k, v in results.items() if v is not None}
    return eval(op_str, {}, local_vars)
  except (NameError, SyntaxError, TypeError, ZeroDivisionError) as e:
    printc.error(error_prefix + 'Failed to evaluate operation "' + op_str + '": ' + str(e) , script_name)
    return None


######################################
# Export Results
######################################

def process_configuration(input, target, architecture, configuration, frequency, type, result_key, units, data, metrics_data, metrics_file, use_benchmark, benchmark_file):
  """
  Process the configuration for a specific architecture and extract relevant metrics.

  This function validates the synthesis status for a given configuration and 
  architecture, and extracts metrics if the synthesis has completed successfully.

  Args:
      input (str): Base directory for the synthesis results.
      target (str): Target device or platform being synthesized.
      architecture (str): Name of the architecture being processed.
      configuration (str): Configuration of the architecture (e.g., specific design options).
      frequency (str | None): Frequency variant for custom frequency synthesis; None for fmax synthesis.
      type (str): Type of results to process (e.g. "fmax_synthesis" or "custom_freq_synthesis").
      units (dict): Dictionary to store metric units for the synthesis results.
      data (dict): Dictionary to store extracted metrics for the current configuration.
      metrics_data (dict): Settings specific to the EDA tool being used.
      metrics_file (str): Path to the YAML file containing tool settings.
      use_benchmark (bool): Whether to use benchmark values for metric extraction.
      benchmark_file (str): Path to the benchmark YAML file.

  Returns:
      tuple:
          - data (dict): Updated dictionary containing extracted metrics.
          - metrics (dict): Extracted metrics for the current configuration.

  Notes:
      - This function ensures the synthesis status is checked before attempting 
        to extract metrics.
      - For `custom_freq_synthesis`, metrics are organized per frequency.
      - Updates the global `units` dictionary with units for the extracted metrics.

  Raises:
      None: Errors are logged using `printc.error`, and the function returns None if an error occurs.
  """
  if type == "custom_freq_synthesis":
    arch = architecture + "[" + configuration + "] @ " + frequency
    arch_path = os.path.join(target, architecture, configuration, frequency)
    status_filename = "synth_status.log"
  else:
    arch = architecture + "[" + configuration + "]"
    arch_path = os.path.join(target, architecture, configuration)
    status_filename = "status.log"

  cur_path = os.path.join(input, arch_path)
  status_log = os.path.join(cur_path, "log", status_filename)

  metrics = {}
  cur_units = {}

  # Check if synthesis completed
  if not os.path.isfile(status_log):
    corrupted_directory(arch_path)
    return None, None

  with open(status_log, "r") as f:
    if status_done not in f.read():
      corrupted_directory(arch_path)
      return None, None

  # Get values
  if type == "custom_freq_synthesis":
    metrics[result_key], cur_units[result_key] = extract_metrics(metrics_data, metrics_file, cur_path, arch, arch_path, use_benchmark, benchmark_file, type)
    data[result_key][target][architecture][configuration][frequency] = metrics[result_key]
  else:
    metrics[result_key], cur_units[result_key] = extract_metrics(metrics_data, metrics_file, cur_path, arch, arch_path, use_benchmark, benchmark_file, type)
    data[result_key][target][architecture][configuration] = metrics[result_key]
  # print(f"metrics[result_key] = {metrics[result_key]}")

  # Update units
  units.update(cur_units[result_key])
  return data, metrics


def export_results(input, output, tools, format, use_benchmark, benchmark_file, result_types, custom_metrics_file=None):
  """
  Export synthesis results for multiple tools, configurations and architectures
  to a specified format.

  This function iterates over synthesis results from specified tools, of every
  architecture configurations in the input directory, extracts metrics, and writes 
  the results to YAML files.

  Args:
      input (str): Base directory containing synthesis results.
      output (str): Directory where the exported results will be saved.
      tools (list | str): List of EDA tools to process or "All" to process all available tools.
      format (str): Output format for the results ("csv", "yml", or "all").
      use_benchmark (bool): Whether to include benchmark data in the metrics.
      benchmark_file (str): Path to the benchmark YAML file.
      result_types (dict): Dictionary specifying the yaml key and path for each result type to process (e.g., `fmax_synthesis` and `custom_freq_synthesis`) 
      custom_metrics_file (str): Path to a metrics definition YAML file.

  Returns:
      None: Results are saved to files; errors are logged.

  Notes:
      - For each tool, synthesis types (`fmax_synthesis` and `custom_freq_synthesis`) 
        are processed separately.
      - Creates a structured YAML output containing extracted metrics and units.
      - Skips tools or configurations with missing or invalid data.
      - Outputs results to separate YAML files for each tool.

  Example:
      If `tools = ["tool1", "tool2"]`, the function generates:
      - `results_tool1.yml` in the specified output directory.
      - `results_tool2.yml` in the specified output directory.

  Raises:
      SystemExit: If no valid synthesis results are found for the specified tools.
  """
  input_path = input

  # Check result_types is valid
  for result_type in result_types:
    if not "path" in result_types[result_type] or not "key" in result_types[result_type]:
      printc.error("Invalid result_types formatting: " + str(result_types), script_name)
      printc.note("Example of valid synthesis type formatting: ", script_name)
      printc.cyan('"custom_freq_synthesis": {')
      printc.cyan('  "key": "custom_freq_synthesis",')
      printc.cyan('  "path": your/custom/freq/synthesis/path,')
      printc.cyan('},')
      printc.cyan('"fmax_synthesis": {')
      printc.cyan('  "key": "fmax_synthesis",')
      printc.cyan('  "path": your/fmax/synthesis/path,')
      printc.cyan('},: ')
      return

  # Get tool list
  if not isinstance(tools, list):
    if not isinstance(tools, str) or tools != "all":
      printc.error("Invalid value for 'tools': " + tools, script_name)
      printc.note("'tools' should be ether a list or 'all'" + tools, script_name)
    else:
      tools = []
      for result_type in result_types:
        work_path = result_types[result_type]["path"]
        type_dir = os.path.join(input_path, work_path)
        if os.path.isdir(type_dir):
          tools += [item for item in os.listdir(type_dir) if os.path.isdir(os.path.join(input, result_type, item))]
      tools = list(set(tools))

  for tool in tools:
    data = {}
    units = {}
    cur_units = {}
    metrics = {}

    # Get tool setting file
    tool_settings_file = os.path.join(OdatixSettings.odatix_eda_tools_path, tool, tool_settings_filename)
    tool_settings = validate_tool_settings(tool_settings_file)
    if tool_settings is None:
      if len(tools) == 1:
        sys.exit(-1)
      else:
        continue

    # Get the default_metrics_file from the tool settings file
    if custom_metrics_file is None:
      metrics_file, defined = get_from_dict("default_metrics_file", tool_settings, tool_settings_file, behavior=Key.MANTADORY, script_name=script_name)
      if not defined:
        continue
    else:
      metrics_file = custom_metrics_file

    # Define user accessible variables
    variables = Variables(
      odatix_path=OdatixSettings.odatix_path,
      odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
    )

    # Replace variables in command
    metrics_file = replace_variables(metrics_file, variables)

    if not os.path.isfile(metrics_file):
      printc.error('Metrics definition file "' + os.path.realpath(metrics_file) + '" does not exist', script_name)
      continue
    with open(metrics_file, "r") as file:
      try:
        metrics_data = yaml.safe_load(file)
      except yaml.YAMLError as e:
        printc.error("Error in metrics definition file: " + str(e), script_name)
        continue

    for result_type in result_types:
      result_key = result_types[result_type]["key"]
      work_path = result_types[result_type]["path"]
      data[result_key] = {}
      printc.cyan("Export " + tool + " " + result_key + " results", script_name)

      input = os.path.join(input_path, work_path, tool)

      try:
        dirs = sorted(next(os.walk(input))[1])
      except StopIteration:
        continue

      for target in dirs:
        data[result_key][target] = {}
        for architecture in sorted(next(os.walk(os.path.join(input, target)))[1]):
          data[result_key][target][architecture] = {}
          for configuration in sorted(next(os.walk(os.path.join(input, target, architecture)))[1]):
            if result_type == "custom_freq_synthesis":
              data[result_key][target][architecture][configuration] = {}
              for frequency in sorted(next(os.walk(os.path.join(input, target, architecture, configuration)))[1]):
                process_configuration(input, target, architecture, configuration, frequency, result_type, result_key, units, data, metrics_data, metrics_file, use_benchmark, benchmark_file)
              if data == None:
                continue
            else:
              process_configuration(input, target, architecture, configuration, None, result_type, result_key, units, data, metrics_data, metrics_file, use_benchmark, benchmark_file)
            
            if data == None:
              continue

    # Export to the desired format
    os.makedirs(output, exist_ok=True)
    output_file = os.path.join(output, "results_" + tool + ".yml")
    try:
      with open(output_file, "w") as file:
        yaml.dump(
          {"units": units, "fmax_synthesis": data["fmax_synthesis"], "custom_freq_synthesis": data["custom_freq_synthesis"]}, file, default_style=None, default_flow_style=False, sort_keys=False
        )
        printc.say('Results written to "' + output_file + '"', script_name=script_name)
        printc.note("Run 'odatix-explorer' to explore the results", script_name=script_name)
    except Exception as e:
      printc.error('Could not write "' + output_file + '"', script_name=script_name)
      printc.cyan("error details: ", script_name=script_name, end="")
      print(str(e))


######################################
# Main
######################################


def main(args, settings=None):
  # Get settings
  if settings is None:
    settings = OdatixSettings(args.config)
    if not settings.valid:
      sys.exit(-1)

  if args.use_benchmark is not None:
    use_benchmark = args.use_benchmark
  else:
    use_benchmark = settings.use_benchmark

  if args.benchmark_file is not None:
    benchmark_file = args.benchmark_file
  else:
    benchmark_file = settings.benchmark_file

  if args.work is not None:
    input = args.work
  else:
    input = settings.work_path

  if not os.path.isdir(input):
    printc.error('Could not find work directory "' + input + '"', script_name=script_name)
    printc.note("Run fmax synthesis using the 'odatix fmax' command before exporting the results", script_name=script_name)
    printc.note("Or run custom frequency synthesis using the 'odatix freq' command before exporting the results", script_name=script_name)
    sys.exit(-1)

  if args.respath is not None:
    output = args.respath
  else:
    output = settings.result_path

  result_types = settings.result_types

  if args.tool == "all":
    tools = args.tool
  else:
    tools = [args.tool]

  if args.metrics is not None:
    metrics_file = args.metrics
  else:
    metrics_file = None

  export_results(
    input=input,
    output=output,
    tools=tools,
    format=args.format,
    use_benchmark=use_benchmark,
    benchmark_file=benchmark_file,
    result_types=result_types,
    custom_metrics_file=metrics_file,
  )


if __name__ == "__main__":
  args = parse_arguments()
  main(args)

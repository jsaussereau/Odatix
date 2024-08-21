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
import odatix.lib.settings as settings
from odatix.lib.settings import OdatixSettings

current_dir = os.path.dirname(os.path.abspath(__file__))

banned_metrics = []
banned_arch = []

######################################
# Settings
######################################

DEFAULT_FORMAT = "yml"

simulations_dir = "simulations"

status_done = "Done: 100%"

script_name = os.path.basename(__file__)


######################################
# Parse Arguments
######################################


def add_arguments(parser):
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
  parser.add_argument(
    "-c",
    "--config",
    default=OdatixSettings.DEFAULT_SETTINGS_FILE,
    help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
  )


def parse_arguments():
  parser = argparse.ArgumentParser(description="Process FPGA or ASIC results")
  add_arguments(parser)
  return parser.parse_args()


######################################
# Parsing functions
######################################


def parse_regex(file, pattern, group_id, error_prefix=""):
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


def parse_yaml(file, key, error_prefix=""):
  if not os.path.isfile(file):
    printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
    return None

  with open(file, "r") as yaml_file:
    try:
      data = yaml.safe_load(yaml_file)
      keys = key.split("[")
      for k in keys:
        k = k.rstrip("]")
        if k in data:
          data = data[k]
        else:
          printc.error(error_prefix + 'Could not find key "' + k + '" in yaml "' + file + '"', script_name=script_name)
          return None
      return data
    except yaml.YAMLError as e:
      printc.error(error_prefix + 'Could not parse yaml file "' + file + '": ' + str(e), script_name=script_name)
      return None


######################################
# Validate Tool Settings
######################################


def validate_tool_settings(file_path):
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


def extract_metrics(tool_settings, tool_settings_file, cur_path, arch, arch_path, use_benchmark, benchmark_file):
  global banned_metrics
  results = {}
  units = {}
  error_prefix = arch_path + " => "
  metrics = read_from_list("metrics", tool_settings, tool_settings_file, raise_if_missing=False, script_name=script_name)
  for metric, content in metrics.items():
    if metric in banned_metrics:
      continue

    try:
      type = read_from_list("type", content, tool_settings_file, parent=metric, script_name=script_name)
      settings = read_from_list("settings", content, tool_settings_file, parent=metric, script_name=script_name)
    except (KeyNotInListError, BadValueInListError):
      banned_metrics.append(metric)
      continue

    benchmark_only = read_from_list("benchmark_only", content, tool_settings_file, parent=metric, raise_if_missing=False, type=bool, print_error=False, script_name=script_name)
    if benchmark_only and not use_benchmark:
      banned_metrics.append(metric)
      continue

    if type == "regex":
      try:
        file = read_from_list("file", settings, tool_settings_file, parent=metric + "[settings]", script_name=script_name)
        pattern = read_from_list("pattern", settings, tool_settings_file, parent=metric + "[settings]", script_name=script_name)
        group_id = read_from_list("group_id", settings, tool_settings_file, parent=metric + "[settings]", type=int, script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      value = parse_regex(os.path.join(cur_path, file), pattern, group_id, error_prefix)
    elif type == "csv":
      try:
        file = read_from_list( "file", settings, tool_settings_file, parent=metric + "[settings]", script_name=script_name)
        key = read_from_list("key", settings, tool_settings_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      value = parse_csv(os.path.join(cur_path, file), key, error_prefix)
    elif type == "yaml":
      try:
        file = read_from_list("file", settings, tool_settings_file, parent=metric + "[settings]", script_name=script_name)
        key = read_from_list("key", settings, tool_settings_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      value = parse_yaml(os.path.join(cur_path, file), key, error_prefix)
    elif type == "benchmark":
      if not use_benchmark:
        banned_metrics.append(metric)
        continue
      if arch in banned_arch:
        continue
      try:
        key = read_from_list("key", settings, tool_settings_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      key = arch + "[" + key + "]"
      value = parse_yaml(benchmark_file, key, error_prefix)
      if value is None:
        banned_arch.append(arch)
    elif type == "operation":
      try:
        op = read_from_list("op", settings, tool_settings_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      value = calculate_operation(op, results, error_prefix)
    else:
      printc.error(
        'Unsupported metric type "' + type + '" specified for metric "' + metric + '" in "' + tool_settings_file + '"',
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
  printc.warning(
    directory + " => Synthesis has not finished or directory has been corrupted", script_name
  )


def convert_to_numeric(data):
  try:
    if "." in data:
      return float(data)
    return int(data)
  except ValueError:
    return data


def calculate_operation(op_str, results, error_prefix=""):
  try:
    local_vars = {k: v for k, v in results.items() if v is not None}
    return eval(op_str, {}, local_vars)
  except (NameError, SyntaxError, TypeError, ZeroDivisionError) as e:
    printc.error(error_prefix + 'Failed to evaluate operation "' + op_str + '": ' + str(e) , script_name)
    return None


######################################
# Export Results
######################################


def export_results(input, output, tools, format, use_benchmark, benchmark_file):
  input_path = input
  for tool in tools:
    if tool == simulations_dir:
      continue
    
    printc.cyan("Export " + tool + " results", script_name)

    tool_settings_file = os.path.join(OdatixSettings.odatix_eda_tools_path, tool, "tool.yml")
    tool_settings = validate_tool_settings(tool_settings_file)
    if tool_settings is None:
      if len(tools) == 1:
        sys.exit(-1)
      else:
        continue

    data = {}
    units = {}

    input = os.path.join(input_path, tool)

    try:
      dirs = sorted(next(os.walk(input))[1])
    except StopIteration:
      continue

    for target in dirs:
      data[target] = {}
      for architecture in sorted(next(os.walk(os.path.join(input, target)))[1]):
        data[target][architecture] = {}
        for configuration in sorted(next(os.walk(os.path.join(input, target, architecture)))[1]):
          arch = architecture + "[" + configuration + "]"
          arch_path = os.path.join(target, architecture, configuration)
          cur_path = os.path.join(input, arch_path)

          status_log = os.path.join(cur_path, "log", "status.log")

          # Check if synthesis completed
          if not os.path.isfile(status_log):
            corrupted_directory(arch_path)
            continue

          with open(status_log, "r") as f:
            if status_done not in f.read():
              corrupted_directory(arch_path)
              continue

          # Get values
          metrics, cur_units = extract_metrics(tool_settings, tool_settings_file, cur_path, arch, arch_path, use_benchmark, benchmark_file)
          data[target][architecture][configuration] = metrics

          # Update units
          units.update(cur_units)

    # Export to the desired format
    os.makedirs(output, exist_ok=True)
    output_file = os.path.join(output, "results_" + tool + ".yml")
    try:
      with open(output_file, "w") as file:
        yaml.dump(
          {"units": units, "fmax_results": data}, file, default_style=None, default_flow_style=False, sort_keys=False
        )
        printc.say('Results written to "' + output_file + '"', script_name=script_name)
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

  if args.respath is not None:
    output = args.respath
  else:
    output = settings.result_path

  if args.tool == "all":
    tools = [item for item in os.listdir(input) if os.path.isdir(os.path.join(input, item))]
  else:
    tools = [args.tool]

  export_results(
    input=input,
    output=output,
    tools=tools,
    format=args.format,
    use_benchmark=use_benchmark,
    benchmark_file=benchmark_file,
  )


if __name__ == "__main__":
  args = parse_arguments()
  main(args)

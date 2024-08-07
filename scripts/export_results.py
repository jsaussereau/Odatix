# ********************************************************************** #
#                               Asterism                                 #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

import os
import sys
import yaml
import re
import csv
import argparse

# Add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, "lib")
sys.path.append(lib_path)

import printc
from utils import read_from_list, create_dir
import settings
from settings import AsterismSettings

######################################
# Settings
######################################

DEFAULT_FORMAT = "yml"

status_done = "Done: 100%"

script_name = os.path.basename(__file__)

# get eda_tools folder
if getattr(sys, "frozen", False):
  base_path = os.path.dirname(sys.executable)
else:
  base_path = current_dir
eda_tools_path = os.path.realpath(os.path.join(base_path, "..", "eda_tools"))

######################################
# Parse Arguments
######################################


def add_arguments(parser):
  parser.add_argument("-t", "--tool", default="vivado", help="eda tool in use (default: vivado)")
  parser.add_argument(
    "-f",
    "--format",
    choices=["csv", "yml", "all"],
    default=DEFAULT_FORMAT,
    help="Output format: csv, yml, or all (default: " + DEFAULT_FORMAT + ")",
  )
  parser.add_argument("-u", "--use_benchmark", action="store_true", help="Use benchmark values in yaml file")
  parser.add_argument("-B", "--benchmark_file", help="Benchmark file")
  parser.add_argument("-w", "--work", help="work directory")
  parser.add_argument("-r", "--respath", help="Result path")
  parser.add_argument(
    "-c",
    "--config",
    default=AsterismSettings.DEFAULT_SETTINGS_FILE,
    help="global settings file for asterism (default: " + AsterismSettings.DEFAULT_SETTINGS_FILE + ")",
  )


def parse_arguments():
  parser = argparse.ArgumentParser(description="Process FPGA or ASIC results")
  add_arguments(parser)
  return parser.parse_args()


######################################
# Parsing functions
######################################


def parse_regex(file, pattern, group_id):
  if not os.path.isfile(file):
    printc.warning('File "' + file + '" does not exist', script_name)
    return None
  with open(file, "r") as f:
    content = f.read()
    match = re.search(pattern, content)
    if match:
      return match.group(group_id)
  return None


def parse_csv(file, key):
  if not os.path.isfile(file):
    printc.warning('File "' + file + '" does not exist', script_name)
    return None
  with open(file, mode="r") as infile:
    reader = csv.DictReader(infile)
    for row in reader:
      if key in row:
        return row[key]
  return None


######################################
# Validate Tool Settings
######################################


def validate_tool_settings(file_path):
  with open(file_path, "r") as file:
    try:
      tool_settings = yaml.safe_load(file)
      # TODO: Add more validation logic
      return tool_settings
    except yaml.YAMLError as exc:
      printc.error("Error in configuration file:", exc, script_name)
      return None


######################################
# Extract Tool Metrics
######################################


def extract_metrics(tool_settings, cur_path):
  results = {}
  for metric, config in tool_settings["metrics"].items():
    if config["type"] == "regex":
      file = config["settings"]["file"]
      pattern = config["settings"]["pattern"]
      group_id = config["settings"]["group_id"]
      value = parse_regex(os.path.join(cur_path, file), pattern, group_id)
    elif config["type"] == "csv":
      file = config["settings"]["file"]
      key = config["settings"]["key"]
      value = parse_csv(os.path.join(cur_path, file), key)
    elif config["type"] == "operation":
      op_str = config["settings"]["op"]
      value = calculate_operation(op_str, results, cur_path)

    # Apply formatting if specified
    if value is not None and "format" in config:
      try:
        value = convert_to_numeric(config["format"] % float(value))
      except ValueError:
        pass  # printc.warning(f"Failed to format value {value} for metric {metric}", script_name)

    # Append unit if specified
    if value is not None:
      result = {"value": value}
      if "unit" in config:
        result["unit"] = config["unit"]
      results[metric] = result
    else:
      results[metric] = {"value": None}

  return results


######################################
# Misc functions
######################################


def corrupted_directory(target, architecture):
  printc.warning(
    target + "/" + architecture + " => synthesis has not finished or directory has been corrupted", script_name
  )


def convert_to_numeric(data):
  try:
    if "." in data:
      return float(data)
    return int(data)
  except ValueError:
    return data


def calculate_operation(op_str, results, cur_path):
  try:
    # Create a local dictionary with only the 'value' parts of the results
    local_vars = {k: v["value"] for k, v in results.items() if v["value"] is not None}
    return eval(op_str, {}, local_vars)
  except (NameError, SyntaxError, TypeError, ZeroDivisionError) as e:
    printc.error('Failed to evaluate operation "' + op_str + '" for ' + cur_path, script_name)
    printc.cyan("error details: ", script_name=script_name, end="")
    print(str(e))
    return None


######################################
# Export Results
######################################


def export_results(input, output, tool, format, use_benchmark, benchmark_file, tool_settings):
  data = {}

  input = os.path.join(input, tool)

  for target in sorted(next(os.walk(input))[1]):
    data[target] = {}
    for architecture in sorted(next(os.walk(os.path.join(input, target)))[1]):
      data[target][architecture] = {}
      for configuration in sorted(next(os.walk(os.path.join(input, target, architecture)))[1]):
        cur_path = os.path.join(input, target, architecture, configuration)

        status_log = os.path.join(cur_path, "log", "status.log")

        # Check if synthesis completed
        if not os.path.isfile(status_log):
          corrupted_directory(target, architecture + "/" + configuration)
          continue

        with open(status_log, "r") as f:
          if status_done not in f.read():
            corrupted_directory(target, architecture + "/" + configuration)
            continue

        # Get values
        metrics = extract_metrics(tool_settings, cur_path)
        data[target][architecture][configuration] = metrics

  # Export to the desired format
  create_dir(output)
  output_file = os.path.join(output, "results_" + tool + ".yml")
  try:
    with open(output_file, "w") as file:
      yaml.dump(data, file, default_style=None, default_flow_style=False, sort_keys=False)
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
    settings = AsterismSettings(args.config)
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

  tool_settings_file = os.path.join(eda_tools_path, args.tool, "tool.yml")
  tool_settings = validate_tool_settings(tool_settings_file)
  if tool_settings is None:
    sys.exit(-1)

  export_results(
    input=input,
    output=output,
    tool=args.tool,
    format=args.format,
    use_benchmark=use_benchmark,
    benchmark_file=benchmark_file,
    tool_settings=tool_settings,
  )


if __name__ == "__main__":
  args = parse_arguments()
  main(args)

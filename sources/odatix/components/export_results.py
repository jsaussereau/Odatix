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

synth_types = ["custom_freq_synthesis", "fmax_synthesis"]

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


def extract_metrics(tool_settings, tool_settings_file, cur_path, arch, arch_path, use_benchmark, benchmark_file, type="fmax_synthesis"):
  global banned_metrics
  results = {}
  units = {}
  error_prefix =  arch_path + " => "
  metrics = {}
  
  if type == "fmax_synthesis":
    fmax_metrics = read_from_list("fmax_synthesis_metrics", tool_settings, tool_settings_file, raise_if_missing=False, print_error=False, script_name=script_name)
    if fmax_metrics != False:
      metrics.update(fmax_metrics)
  elif type == "custom_freq_synthesis":
    range_metrics = read_from_list("custom_freq_synthesis_metrics", tool_settings, tool_settings_file, raise_if_missing=False, print_error=False, script_name=script_name)
    if range_metrics != False:
      metrics.update(range_metrics)

  common_metrics = read_from_list("metrics", tool_settings, tool_settings_file, raise_if_missing=False, print_error=False, script_name=script_name)
  if common_metrics != False:
    metrics.update(common_metrics)

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

def process_configuration(input, target, architecture, configuration, frequency, type, units, data, tool_settings, tool_settings_file, use_benchmark, benchmark_file):
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
    metrics[type], cur_units[type] = extract_metrics(tool_settings, tool_settings_file, cur_path, arch, arch_path, use_benchmark, benchmark_file, type)
    data[type][target][architecture][configuration][frequency] = metrics[type]
  else:
    metrics[type], cur_units[type] = extract_metrics(tool_settings, tool_settings_file, cur_path, arch, arch_path, use_benchmark, benchmark_file, type)
    data[type][target][architecture][configuration] = metrics[type]
  # print(f"metrics[type] = {metrics[type]}")

  # Update units
  units.update(cur_units[type])
  return data, metrics


def export_results(input, output, tools, format, use_benchmark, benchmark_file):
  input_path = input

  data = {}
  units = {}
  cur_units = {}
  metrics = {}

  for type in synth_types:
    data[type] = {}

    for tool in tools:
      
      printc.cyan("Export " + tool + " " + type + " results", script_name)

      tool_settings_file = os.path.join(OdatixSettings.odatix_eda_tools_path, tool, "tool.yml")
      tool_settings = validate_tool_settings(tool_settings_file)
      if tool_settings is None:
        if len(tools) == 1:
          sys.exit(-1)
        else:
          continue

      input = os.path.join(input_path, type, tool)

      # print(f"input : {input}")

      try:
        dirs = sorted(next(os.walk(input))[1])
      except StopIteration:
        continue

      for target in dirs:
        data[type][target] = {}
        for architecture in sorted(next(os.walk(os.path.join(input, target)))[1]):
          data[type][target][architecture] = {}
          for configuration in sorted(next(os.walk(os.path.join(input, target, architecture)))[1]):
            if type == "custom_freq_synthesis":
              data[type][target][architecture][configuration] = {}
              for frequency in sorted(next(os.walk(os.path.join(input, target, architecture, configuration)))[1]):
                process_configuration(input, target, architecture, configuration, frequency, type, units, data, tool_settings, tool_settings_file, use_benchmark, benchmark_file)
              if data == None:
                continue
            else:
              process_configuration(input, target, architecture, configuration, None, type, units, data, tool_settings, tool_settings_file, use_benchmark, benchmark_file)
            
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

  if args.tool == "all":
    tool_list = []
    for type in synth_types:
      type_dir = os.path.join(input, type)
      if os.path.isdir(type_dir):
        tool_list += [item for item in os.listdir(type_dir) if os.path.isdir(os.path.join(input, type, item))]
    tools = list(set(tool_list))
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

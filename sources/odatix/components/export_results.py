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
import argparse

import odatix.lib.printc as printc
import odatix.lib.eda_tools as eda_tools
import odatix.lib.hard_settings as hard_settings
import odatix.lib.job_steps as job_steps
import odatix.lib.metrics as metrics_lib
import odatix.lib.results_schema as results_schema
from odatix.lib.utils import read_from_list, create_dir, KeyNotInListError, BadValueInListError
from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
import odatix.lib.settings as settings
from odatix.lib.settings import OdatixSettings
from odatix.lib.variables import replace_variables, Variables
from odatix.components.export_common import (
    parse_regex,
    parse_csv,
    parse_yaml,
    parse_json,
    parse_xml,
    convert_to_numeric,
    calculate_operation,
    load_existing_results_file,
)

current_dir = os.path.dirname(os.path.abspath(__file__))

banned_metrics = []
banned_arch = []


def _reset_banned_lists():
  banned_metrics.clear()
  banned_arch.clear()

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


def resolve_metrics_file(tool, custom_metrics_file=None, flow=None):
  """
  Path of the highest precedence metrics definition file of a tool for a given
  flow, or None when there is none.

  Metrics are not read from that single file: every file defining the tool is
  merged (see odatix.lib.metrics), which is what load_metrics_for_tool does.
  This function is only kept for callers that need a path to point at.
  """
  if custom_metrics_file is not None:
    return custom_metrics_file if os.path.isfile(custom_metrics_file) else None
  files = metrics_lib.metrics_files(tool, flow=flow)
  return files[-1] if files else None


def load_metrics_file(metrics_file):
  """Load a metrics definition file, or None when it is not valid YAML."""
  with open(metrics_file, "r") as file:
    try:
      metrics_data = yaml.safe_load(file)
    except yaml.YAMLError as e:
      printc.error("Error in metrics definition file: " + str(e), script_name)
      return None
  return metrics_data if metrics_data is not None else {}


######################################
# Extract Tool Metrics
######################################


def resolve_step_path(file, step):
  """Replace "$step"/"${step}" in the file of a metric by the step it declares."""
  if not step or not isinstance(file, str):
    return file
  return file.replace("${step}", str(step)).replace("$step", str(step))


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
  elif type == "pnr":
    pnr_metrics = read_from_list("pnr_metrics", metrics_data, metrics_file, raise_if_missing=False, print_error=False, script_name=script_name)
    if pnr_metrics != False:
      metrics.update(pnr_metrics)

  common_metrics = read_from_list("metrics", metrics_data, metrics_file, raise_if_missing=False, print_error=False, script_name=script_name)
  if common_metrics != False:
    metrics.update(common_metrics)

  # A metric may declare the step of the flow it is extracted from ("step:").
  # Such a metric only exists once that step has run: a job stopped earlier is
  # not missing it, it has simply not produced it yet, so it is left out of the
  # record instead of being reported as an error.
  completed_steps = job_steps.completed_step_names(cur_path)

  for metric, content in metrics.items():
    if metric in banned_metrics:
      continue

    metric_step = content.get("step") if isinstance(content, dict) else None
    if metric_step and str(metric_step) not in completed_steps:
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

    error_if_missing, _ = get_from_dict("error_if_missing", content, metrics_file, parent=metric, default_value=True, type=bool, silent=True, script_name=script_name)

    if type == "regex":
      try:
        file = read_from_list("file", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
        pattern = read_from_list("pattern", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
        group_id = read_from_list("group_id", settings, metrics_file, parent=metric + "[settings]", type=int, script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      value = parse_regex(os.path.join(cur_path, resolve_step_path(file, metric_step)), pattern, group_id, error_if_missing, error_prefix)
    elif type == "csv":
      try:
        file = read_from_list( "file", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
        key = read_from_list("key", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      value = parse_csv(os.path.join(cur_path, resolve_step_path(file, metric_step)), key, error_if_missing, error_prefix)
    elif type == "yaml":
      try:
        file = read_from_list("file", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      key, _ = get_from_dict("key", settings, metrics_file, parent=metric + "[settings]", silent=True, default_value=None, script_name=script_name)
      value = parse_yaml(os.path.join(cur_path, resolve_step_path(file, metric_step)), key, error_if_missing, error_prefix)
    elif type == "json":
      try:
        file = read_from_list("file", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      key, _ = get_from_dict("key", settings, metrics_file, parent=metric + "[settings]", silent=True, default_value=None, script_name=script_name)
      value = parse_json(os.path.join(cur_path, resolve_step_path(file, metric_step)), key, error_if_missing, error_prefix)
    elif type == "xml":
      try:
        file = read_from_list("file", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      key, _ = get_from_dict("key", settings, metrics_file, parent=metric + "[settings]", silent=True, default_value=None, script_name=script_name)
      value = parse_xml(os.path.join(cur_path, resolve_step_path(file, metric_step)), key, error_if_missing, error_prefix)
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
      value = parse_yaml(benchmark_file, key, error_if_missing, error_prefix)
      if value is None:
        banned_arch.append(arch)
    elif type == "operation":
      try:
        op = read_from_list("op", settings, metrics_file, parent=metric + "[settings]", script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        banned_metrics.append(metric)
        continue
      value = calculate_operation(op, results, error_if_missing, error_prefix)
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


######################################
# Export Results
######################################

# Job types whose results the per-job (as-they-finish) export can write.
SUPPORTED_JOB_RESULT_TYPES = ("fmax_synthesis", "custom_freq_synthesis", "pnr")


def tool_work_dirs(type_dir, tool):
  """
  Work directories holding the jobs of a tool inside a job type directory, one
  per flow it has been run with.

  Returns:
      list: (directory name, flow name or None) pairs, the default flow (bare
      tool name) first.
  """
  found = []
  try:
    entries = sorted(os.listdir(type_dir))
  except OSError:
    return found
  for entry in entries:
    if not os.path.isdir(os.path.join(type_dir, entry)):
      continue
    entry_tool, entry_flow = eda_tools.split_tool_work_dirname(entry)
    if entry_tool == tool:
      found.append((entry, entry_flow))
  # The bare tool name (default flow) comes first.
  return sorted(found, key=lambda item: (item[1] is not None, item[1] or ""))


def _subdirectories(path):
  """The sub-directories of a directory, sorted; empty when it cannot be read."""
  try:
    return sorted(entry for entry in os.listdir(path) if os.path.isdir(os.path.join(path, entry)))
  except OSError:
    return []


def _walk_configurations(job_root, has_frequency_level):
  """
  Walk the job directories under a work directory, yielding what identifies each
  of them: (target, architecture, configuration, frequency), the frequency being
  None when the job type has no such level.
  """
  for target in _subdirectories(job_root):
    for architecture in _subdirectories(os.path.join(job_root, target)):
      for configuration in _subdirectories(os.path.join(job_root, target, architecture)):
        if has_frequency_level:
          for frequency in _subdirectories(os.path.join(job_root, target, architecture, configuration)):
            yield target, architecture, configuration, frequency
        else:
          yield target, architecture, configuration, None


def process_configuration(input, target, architecture, configuration, frequency, type, result_key, units, metrics_data, metrics_file, use_benchmark, benchmark_file, tool=None, flow=None, source=None):
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
      result_key (str): Result type key written to the record meta (e.g. "fmax_synthesis").
      units (dict): Dictionary to store metric units for the synthesis results.
      metrics_data (dict): Settings specific to the EDA tool being used.
      metrics_file (str): Path to the YAML file containing tool settings.
      use_benchmark (bool): Whether to use benchmark values for metric extraction.
      benchmark_file (str): Path to the benchmark YAML file.
      tool (str | None): eda tool the job ran with, written to the record meta.
      flow (str | None): flow of that tool the job ran with, written to the record meta.

  Returns:
      dict | None: The extracted result record, or None if the synthesis
      directory is incomplete or corrupted.

  Notes:
      - This function ensures the synthesis status is checked before attempting
        to extract metrics.
      - Parameter domains extracted alongside the metrics are flattened into
        the record meta.
      - Updates the `units` dictionary with units for the extracted metrics.
  """
  if type == "custom_freq_synthesis":
    arch = architecture + "[" + configuration + "] @ " + frequency
    arch_path = os.path.join(target, architecture, configuration, frequency)
    status_filenames = ["synth_status.log"]
  elif type == "pnr":
    # A place & route job directory always has a last segment, "<N>MHz" when it
    # started from a custom frequency synthesis and "fmax" when it started from
    # an fmax search, so both kinds sit side by side at the same depth.
    arch = architecture + "[" + configuration + "] @ " + frequency
    arch_path = os.path.join(target, architecture, configuration, frequency)
    # A place & route tool may report progress through either status file.
    status_filenames = ["synth_status.log", "status.log"]
  else:
    arch = architecture + "[" + configuration + "]"
    arch_path = os.path.join(target, architecture, configuration)
    status_filenames = ["status.log"]

  cur_path = os.path.join(input, arch_path)
  status_log = next(
    (
      os.path.join(cur_path, "log", filename)
      for filename in status_filenames
      if os.path.isfile(os.path.join(cur_path, "log", filename))
    ),
    os.path.join(cur_path, "log", status_filenames[0]),
  )

  # A flow split into steps can stop early (e.g. implemented but no bitstream):
  # record how far this job went, so partial results stay distinguishable.
  step = job_steps.last_completed_step(cur_path)

  if not flow:
    # A full re-export does not know which flow ran: read it back from the
    # "flow.txt" the runner wrote in the job directory.
    flow_file = os.path.join(cur_path, hard_settings.flow_filename)
    if os.path.isfile(flow_file):
      try:
        with open(flow_file, "r") as f:
          flow = f.read().strip() or None
      except OSError:
        flow = None

  if type == "pnr" and not source:
    # A full re-export does not know which synthesis this job started from: read
    # it back from the "pnr.yml" the runner wrote in the job directory. Deriving
    # it from the path is not enough, since nothing there says where the source
    # tool name stops and its flow begins.
    from odatix.components.pnr_common import read_pnr_source_file

    source = read_pnr_source_file(cur_path)

  # Check if synthesis completed
  if not os.path.isfile(status_log):
    corrupted_directory(arch_path)
    return None

  with open(status_log, "r") as f:
    if status_done not in f.read():
      corrupted_directory(arch_path)
      return None

  # Get values
  metrics, cur_units = extract_metrics(metrics_data, metrics_file, cur_path, arch, arch_path, use_benchmark, benchmark_file, type)

  # Build the result record
  meta = {
    results_schema.META_TYPE: str(result_key),
    results_schema.META_TARGET: str(target),
    results_schema.META_ARCHITECTURE: str(architecture),
    results_schema.META_CONFIGURATION: str(configuration),
  }
  if tool:
    meta[results_schema.META_TOOL] = str(tool)
  if flow:
    meta[results_schema.META_FLOW] = str(flow)
  if step:
    meta[results_schema.META_STEP] = str(step)
  if frequency is not None:
    frequency_value = results_schema.parse_frequency_label(frequency)
    if frequency_value is not None:
      meta[results_schema.META_FREQUENCY] = frequency_value
    elif str(frequency) != hard_settings.pnr_fmax_dirname:
      meta[results_schema.META_FREQUENCY] = str(frequency)
    # A place & route job whose source is an fmax search has no target
    # frequency: the one it reached is a metric, not a dimension.

  if isinstance(source, dict):
    for meta_key in (
      results_schema.META_SOURCE_TYPE,
      results_schema.META_SOURCE_TOOL,
      results_schema.META_SOURCE_FLOW,
    ):
      value = source.get(meta_key)
      if value:
        meta[meta_key] = str(value)
  param_domains = metrics.pop(results_schema.PARAM_DOMAINS_KEY, None)
  results_schema.flatten_param_domains(param_domains, meta)

  # Update units
  units.update(cur_units)
  return results_schema.make_record(meta, metrics)


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
      # A work directory is named "<tool>" or "<tool>@<flow>": every flow of a
      # tool is exported into that tool's single results file.
      tools = list(set(eda_tools.split_tool_work_dirname(item)[0] for item in tools))

  for tool in tools:
    _reset_banned_lists()

    records = []
    units = {}

    if eda_tools.get_tool_dir(tool) is None:
      printc.error('No directory found for the selected eda tool "' + tool + '"', script_name)
      if len(tools) == 1:
        sys.exit(-1)
      else:
        continue

    metrics_data, metrics_file = load_metrics_for_tool(tool, custom_metrics_file=custom_metrics_file)
    if metrics_data is None:
      if len(tools) == 1:
        sys.exit(-1)
      else:
        continue

    for result_type in result_types:
      result_key = result_types[result_type]["key"]
      work_path = result_types[result_type]["path"]
      printc.cyan("Export " + tool + " " + result_key + " results", script_name)

      # A tool can have run through several flows, each in its own work
      # directory ("vivado", "vivado@power_opt", ...). They all land in the same
      # results file, told apart by the "flow" meta key.
      for work_dirname, flow in tool_work_dirs(os.path.join(input_path, work_path), tool):
        input = os.path.join(input_path, work_path, work_dirname)

        # A place & route job also carries the synthesis it started from, spelled
        # in the work tree one level below the tool that ran it
        # ("pnr/innovus/design_compiler@dcnxt/..."), so that Design Compiler +
        # Innovus and Genus + Innovus results do not land in the same directory.
        if result_type == "pnr":
          job_roots = [os.path.join(input, source_dirname) for source_dirname in _subdirectories(input)]
        else:
          job_roots = [input]

        # Every job type but an fmax search has a last level below the
        # configuration: the frequency it was run at for a custom frequency
        # synthesis, and for a place & route either that or "fmax".
        has_frequency_level = result_type in ("custom_freq_synthesis", "pnr")

        for job_root in job_roots:
          for target, architecture, configuration, frequency in _walk_configurations(job_root, has_frequency_level):
            record = process_configuration(
              job_root, target, architecture, configuration, frequency,
              result_type, result_key, units, metrics_data, metrics_file,
              use_benchmark, benchmark_file, tool=tool, flow=flow,
            )
            if record is not None:
              records.append(record)

    # Export to the desired format
    output_file = os.path.join(output, "results_" + tool + ".yml")
    try:
      results_schema.dump_results_file(output_file, units, records)
      printc.say('Results written to "' + output_file + '"', script_name=script_name)
      printc.note("Run 'odatix-explorer' to explore the results", script_name=script_name)
    except Exception as e:
      printc.error('Could not write "' + output_file + '"', script_name=script_name)
      printc.cyan("error details: ", script_name=script_name, end="")
      print(str(e))


def export_analysis(input_work_path, output, analysis_work_path, tools="all"):
  """
  Compile the RTL analysis results (odatix analyze) into v2 results files for
  Odatix Explorer, from the analysis work directory.

  For every eda tool that has an analysis work directory
  (``<input_work_path>/<analysis_work_path>/<tool>``), the per-architecture
  status/errors/warnings are recomputed and written to
  "results_analysis_<tool>.yml" in ``output`` (see
  odatix.components.export_analysis), exactly like a fresh ``odatix analyze``
  would.

  Args:
      input_work_path (str): the workspace work directory.
      output (str): the workspace result directory.
      analysis_work_path (str): the analysis work sub-directory name.
      tools (list | str): eda tools to export, or "all" to auto-discover them.
  """
  # Imported here (not at module top) to avoid a heavy import for the common
  # synthesis export path.
  from odatix.components.analyze_results import generate_analysis_summary
  from odatix.components.export_analysis import export_analysis_results

  analysis_root = os.path.join(input_work_path, analysis_work_path)
  if not os.path.isdir(analysis_root):
    return

  discovered = sorted(
    item for item in os.listdir(analysis_root) if os.path.isdir(os.path.join(analysis_root, item))
  )
  if isinstance(tools, list):
    selected = [tool for tool in discovered if tool in tools]
  else:
    selected = discovered

  for tool in selected:
    tool_dir = os.path.join(analysis_root, tool)
    printc.cyan("Export " + tool + " analysis results", script_name)
    summary = generate_analysis_summary(
      root_dir=tool_dir,
      output_file=os.path.join(tool_dir, "analysis.yml"),
      tool=tool,
    )
    export_analysis_results(summary, output, tool)


def load_metrics_for_tool(tool, custom_metrics_file=None, flow=None):
  """
  Load the metrics definitions used to export a tool's results: the built-in
  ones completed and overridden by the workspace metrics.yml, unless an explicit
  metrics file is given (see odatix.lib.metrics.load_metrics).

  Returns:
      tuple: (metrics_data, source) or (None, None) when they cannot be loaded.
  """
  return metrics_lib.load_metrics(tool, custom_metrics_file=custom_metrics_file, flow=flow)


# Deprecated alias.
_load_metrics_for_tool = load_metrics_for_tool


# Backward-compatible alias: the shared loader (odatix.components.export_common)
# handles every supported format version.
_load_existing_results = load_existing_results_file


def configure_synthesis_job_exports(
  parallel_jobs,
  *,
  result_type,
  work_path,
  tool,
  output_dir,
  flow=None,
  use_benchmark=False,
  benchmark_file=None,
  custom_metrics_file=None,
):
  if work_path is None or output_dir is None or tool is None:
    return 0

  if result_type not in SUPPORTED_JOB_RESULT_TYPES:
    printc.error('Unsupported synthesis result type "' + str(result_type) + '" for per-job export', script_name)
    return 0

  # Resolve the flow the same way the runner does, so the exported records carry
  # the flow that actually ran even when none was explicitly requested.
  if flow in (None, ""):
    flow = eda_tools.get_default_flow(tool, job_type=result_type)

  batch_tool_path = os.path.realpath(
    os.path.join(str(work_path), eda_tools.tool_work_dirname(tool, flow, job_type=result_type))
  )
  output_dir = os.path.realpath(str(output_dir))

  configured = 0
  for job in list(getattr(parallel_jobs, "job_list", []) or []):
    tmp_dir = os.path.realpath(str(getattr(job, "tmp_dir", "")))
    if not tmp_dir:
      continue

    # A job that already knows where its result belongs says so. Place & route
    # jobs do: their work directory has one level more (the tool that ran the
    # source synthesis), and it varies from one job of the same batch to the
    # next, so it cannot be derived from the batch's own path.
    coordinates = getattr(job, "export_coordinates", None)
    if isinstance(coordinates, dict):
      input_tool_path = str(coordinates.get("input_tool_path", batch_tool_path))
      target = coordinates.get("target")
      architecture = coordinates.get("architecture")
      configuration = coordinates.get("configuration")
      frequency = coordinates.get("frequency")
      source = coordinates.get("source")
      if not (target and architecture and configuration):
        continue
    else:
      input_tool_path = batch_tool_path
      source = None

      try:
        rel_path = os.path.relpath(tmp_dir, input_tool_path)
      except Exception:
        continue

      if rel_path.startswith(".."):
        continue

      parts = [part for part in rel_path.split(os.sep) if part not in ("", ".")]
      if len(parts) < 3:
        continue

      target = parts[0]
      architecture = parts[1]
      configuration = parts[2]
      frequency = parts[3] if len(parts) >= 4 else None

    if result_type in ("custom_freq_synthesis", "pnr") and frequency is None:
      continue

    job.post_run_export = {
      "kind": "synthesis",
      "result_type": result_type,
      "tool": str(tool),
      "flow": str(flow) if flow else None,
      "input_tool_path": input_tool_path,
      "output_dir": output_dir,
      "source": source,
      "target": str(target),
      "architecture": str(architecture),
      "configuration": str(configuration),
      "frequency": str(frequency) if frequency is not None else None,
      "use_benchmark": bool(use_benchmark),
      "benchmark_file": benchmark_file,
      "custom_metrics_file": custom_metrics_file,
    }
    configured += 1

  return configured


def export_single_job_result(job, export_config=None):
  config = export_config if isinstance(export_config, dict) else getattr(job, "post_run_export", None)
  if not isinstance(config, dict):
    printc.error("Missing per-job synthesis export configuration", script_name=script_name)
    return False

  result_type = str(config.get("result_type", ""))
  if result_type not in SUPPORTED_JOB_RESULT_TYPES:
    printc.error('Unsupported synthesis result type "' + result_type + '"', script_name=script_name)
    return False

  tool = str(config.get("tool", ""))
  flow = config.get("flow", None)
  input_tool_path = str(config.get("input_tool_path", ""))
  output_dir = str(config.get("output_dir", ""))
  target = str(config.get("target", ""))
  architecture = str(config.get("architecture", ""))
  configuration = str(config.get("configuration", ""))
  frequency = config.get("frequency", None)
  if frequency is not None:
    frequency = str(frequency)

  if tool == "" or input_tool_path == "" or output_dir == "":
    printc.error("Per-job export configuration is incomplete", script_name=script_name)
    return False

  if target == "" or architecture == "" or configuration == "":
    printc.error("Per-job export target/architecture/configuration is missing", script_name=script_name)
    return False

  if result_type in ("custom_freq_synthesis", "pnr") and (frequency is None or frequency == ""):
    printc.error("Per-job custom frequency export is missing frequency", script_name=script_name)
    return False

  use_benchmark = bool(config.get("use_benchmark", False))
  benchmark_file = config.get("benchmark_file", None)
  if use_benchmark and not benchmark_file:
    printc.warning("Benchmark export enabled but benchmark file is not configured. Disabling benchmark metrics.", script_name=script_name)
    use_benchmark = False

  metrics_data, metrics_file = _load_metrics_for_tool(
    tool=tool,
    custom_metrics_file=config.get("custom_metrics_file", None),
    flow=flow,
  )
  if metrics_data is None:
    return False

  _reset_banned_lists()

  output_dir = os.path.realpath(output_dir)
  output_file = os.path.join(output_dir, "results_" + tool + ".yml")
  units, records = _load_existing_results(output_file)

  record = process_configuration(
    input=input_tool_path,
    target=target,
    architecture=architecture,
    configuration=configuration,
    frequency=frequency,
    type=result_type,
    result_key=result_type,
    units=units,
    metrics_data=metrics_data,
    metrics_file=metrics_file,
    use_benchmark=use_benchmark,
    benchmark_file=benchmark_file,
    tool=tool,
    flow=flow,
    source=config.get("source", None),
  )

  if record is None:
    printc.warning(
      "Could not export results for " + target + "/" + architecture + "/" + configuration,
      script_name=script_name,
    )
    return False

  records = results_schema.upsert_records(records, [record])

  try:
    results_schema.dump_results_file(output_file, units, records)
  except Exception as e:
    printc.error('Could not write "' + output_file + '"', script_name=script_name)
    printc.cyan("error details: ", script_name=script_name, end="")
    print(str(e))
    return False

  printc.say('Results updated in "' + output_file + '"', script_name=script_name)
  return True


######################################
# Main
######################################


def main(args, settings=None):
  # Get settings
  if settings is None:
    settings = OdatixSettings(args.config)
    if not settings.valid and (args.work is None or args.respath is None):
      printc.error("Could not load settings from file \"" + args.config + "\" and -w and/or -r options are not used", script_name=script_name)
      sys.exit(-1)

  if args.use_benchmark is not None:
    use_benchmark = args.use_benchmark
  else:
    if settings.valid:
      use_benchmark = settings.use_benchmark
    else:
      use_benchmark = False
      benchmark_file = None

  if args.benchmark_file is not None:
    benchmark_file = args.benchmark_file
  else:
    if settings.valid:
      benchmark_file = settings.benchmark_file
    else:
      use_benchmark = False
      benchmark_file = None

  if args.work is not None:
    input = args.work
  else:
    input = settings.work_path

  if not os.path.isdir(input):
    printc.error('Could not find work directory "' + input + '"', script_name=script_name)
    printc.note("Run fmax synthesis using the 'odatix fmax' command before exporting the results", script_name=script_name)
    printc.note("Or run custom frequency synthesis using the 'odatix synth' command before exporting the results", script_name=script_name)
    sys.exit(-1)

  if args.respath is not None:
    output = args.respath
  else:
    output = settings.result_path

  if settings.valid:
    result_types = settings.result_types
  else:
    result_types =  {
      "custom_freq_synthesis": {
        "key": "custom_freq_synthesis",
        "path": OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_WORK_PATH
      },
      "fmax_synthesis": {
        "key": "fmax_synthesis",
        "path": OdatixSettings.DEFAULT_FMAX_SYNTHESIS_WORK_PATH
      },
    }

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

  # Also compile the RTL analysis results (odatix analyze), if any.
  if settings.valid:
    analysis_work_path = settings.analysis_work_path
  else:
    analysis_work_path = OdatixSettings.DEFAULT_ANALYSIS_WORK_PATH
  export_analysis(
    input_work_path=input,
    output=output,
    analysis_work_path=analysis_work_path,
    tools=tools,
  )


if __name__ == "__main__":
  args = parse_arguments()
  main(args)

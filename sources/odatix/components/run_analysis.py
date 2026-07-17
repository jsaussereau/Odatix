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
import re
import sys
import yaml
import shutil
import argparse
import subprocess

from odatix.components.replace_params import replace_params
import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.settings import OdatixSettings
from odatix.lib.architecture_handler import ArchitectureHandler, Architecture
from odatix.lib.read_tool_settings import read_tool_settings
from odatix.lib.utils import read_from_list, copytree, create_dir, ask_to_continue, KeyNotInListError, BadValueInListError, get_timestamp_string
from odatix.lib.get_from_dict import get_from_dict
from odatix.lib.prepare_work import edit_config_file
from odatix.lib.check_tool import check_tool
from odatix.lib.run_settings import get_synth_settings
from odatix.lib.variables import replace_variables, Variables

from odatix.components.run_common import confirm_valid_jobs
from odatix.components.analyze_results import generate_analysis_summary


class AnalysisCancelled(Exception):
  pass

def _check_cancel(cancel_event):
  if cancel_event is not None and cancel_event.is_set():
    raise AnalysisCancelled()


## define colors
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
RESET   = "\033[0m"


script_name = os.path.basename(__file__)


######################################
# Parse Arguments
######################################


def add_arguments(parser):
  parser.add_argument("-t", "--tool", nargs="+", default=None, help="eda tool(s) in use (overrides the 'tools' list of the analysis settings file; default: vivado)")
  parser.add_argument("-o", "--overwrite", action="store_true", help="overwrite existing results")
  parser.add_argument("-y", "--noask", action="store_true", help="do not ask to continue")
  parser.add_argument("-i", "--input", help="input settings file")
  parser.add_argument("-a", "--archpath", help="architecture directory")
  parser.add_argument("-w", "--work", help="work directory")
  parser.add_argument("-E", "--exit", action="store_true", help="exit monitor when all jobs are done")
  parser.add_argument("-j", "--jobs", help="maximum number of parallel jobs")
  parser.add_argument("-T", "--trust", action="store_true", help="do not check eda tool before runnning jobs (saves time)")
  parser.add_argument("-D", "--debug", action="store_true", help="enable debug mode to help troubleshoot settings files")
  parser.add_argument("-k", "--keep", action="store_true", help="store synthesis batch with a timestamp in the configuration name")
  parser.add_argument("--logsize", help="size of the log history per job in the monitor")
  parser.add_argument(
    "-c",
    "--config",
    default=OdatixSettings.DEFAULT_SETTINGS_FILE,
    help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
  )


def parse_arguments():
  parser = argparse.ArgumentParser(description="Run RTL analysis for all architectures")
  add_arguments(parser)
  return parser.parse_args()


######################################
# Tool context
######################################


DEFAULT_ANALYSIS_TOOLS = ["vivado"]


def get_analysis_tools_from_settings(settings_filename):
  """
  Read the default list of eda tools to run the analysis with from the analysis
  settings file ("tools" key). Used when the CLI "--tool" argument is not given.

  Returns:
      list: the tools listed in the settings file, or DEFAULT_ANALYSIS_TOOLS if
      the key is missing/empty/invalid.
  """
  if not settings_filename or not os.path.isfile(settings_filename):
    return list(DEFAULT_ANALYSIS_TOOLS)

  with open(settings_filename, "r") as f:
    try:
      settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    except Exception:
      return list(DEFAULT_ANALYSIS_TOOLS)

  tools, _ = get_from_dict("tools", settings_data or {}, settings_filename, default_value=None, silent=True, script_name=script_name)
  if tools is None:
    return list(DEFAULT_ANALYSIS_TOOLS)
  if isinstance(tools, str):
    tools = [tools]
  tools = [str(tool) for tool in tools if tool]
  if not tools:
    return list(DEFAULT_ANALYSIS_TOOLS)
  return tools


def load_tool_context(tool, target_path):
  """
  Validate an eda tool (tool directory) and load its tool settings, for the RTL
  analysis flow.

  RTL analysis (odatix analyze) does NOT use target definition files
  ("target_<tool>.yml"): it does not target a specific technology / device, so
  there is no target list, no timing constraint and no per-target settings. A
  single generic analysis target is used and the tool install path defaults to
  the tool being on the $PATH.

  Returns:
      dict: eda_target_filename (always None), tool_settings_file, process_group,
      run_command, tool_test_command, targets, constraint_file,
      install_path, force_single_thread.
  """
  # Check if the tool has a dedicated directory in odatix_eda_tools path
  eda_tool_dir = os.path.join(OdatixSettings.odatix_eda_tools_path, tool)
  if not os.path.isdir(eda_tool_dir):
    printc.error(
      'The directory "' + eda_tool_dir + '", for the selected eda tool "' + tool + '" does not exist', script_name
    )
    if tool not in hard_settings.default_supported_tools:
      printc.note(
        'The selected eda tool "'
        + tool
        + "\" is not one of the supported tool. Check out Odatix's documentation to add support for your own eda tool",
        script_name,
      )
    sys.exit(-1)

  # Get tool settings
  tool_settings_file = os.path.realpath(os.path.join(eda_tool_dir, hard_settings.tool_settings_filename))
  process_group, report_path, run_command, tool_test_command, _ = read_tool_settings(tool, tool_settings_file,  synth_type='analysis')

  # No target file for analysis: use a single generic target and a placeholder
  # constraint file (the shared init_script.tcl always creates it, even though
  # analysis never applies timing constraints; it must be a plain filename, not
  # empty, see hard_settings.default_analysis_constraint_file). The install path
  # defaults to "/" (tool expected on the $PATH).
  targets = [hard_settings.default_analysis_target]
  constraint_file = hard_settings.default_analysis_constraint_file
  install_path = "/"
  force_single_thread = False

  # Concat all strings if it is a list
  if isinstance(tool_test_command, list):
    tool_test_command = " ".join(map(str, tool_test_command))

  # Define user accessible variables
  variables = Variables(
    tool_install_path=os.path.realpath(install_path),
    odatix_path=OdatixSettings.odatix_path,
    odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
  )

  # Replace variables in command
  tool_test_command = replace_variables(tool_test_command, variables)

  return {
    "eda_target_filename": None,
    "tool_settings_file": tool_settings_file,
    "process_group": process_group,
    "run_command": run_command,
    "tool_test_command": tool_test_command,
    "targets": targets,
    "constraint_file": constraint_file,
    "install_path": install_path,
    "force_single_thread": force_single_thread,
  }


######################################
# Prepare Analysis (one eda tool)
######################################


def prepare_analysis(
  run_config_settings_filename,
  arch_path,
  tool,
  work_path,
  overwrite,
  noask,
  exit_when_done,
  log_size_limit,
  nb_jobs,
  tool_context,
  job_list,
  timestamp,
  display_suffix="",
  debug=False,
  keep=False,
):
  """
  Check settings and prepare the analysis jobs of a single eda tool,
  appending them to the shared job_list (so that several tools can run
  in one single monitor session, like multi-target synthesis).

  The checklist summary is NOT printed here: the caller merges the
  arch_handler lists of every tool into one single global checklist.

  Returns:
      dict: resolved runtime settings for this tool (work_path,
      tool_settings_file, process_group, arch_handler, ask_continue,
      exit_when_done, log_size_limit, nb_jobs, valid_arch_count).
  """
  _overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs, architectures = get_synth_settings(run_config_settings_filename)

  work_path = os.path.join(work_path, tool)

  if architectures is None:
    printc.error('The "architectures" section of "' + run_config_settings_filename + '" is empty.', script_name)
    printc.note('You must define your architectures in "' + run_config_settings_filename + '" before using this command.', script_name)
    printc.note("Check out examples Odatix's documentation for more information.", script_name)
    sys.exit(-1)

  if overwrite:
    overwrite = True
  else:
    overwrite = _overwrite

  if exit_when_done:
    exit_when_done = True
  else:
    exit_when_done = _exit_when_done

  if log_size_limit is not None:
    log_size_limit = int(log_size_limit)
  else:
    log_size_limit = _log_size_limit

  if nb_jobs is not None:
    nb_jobs = int(nb_jobs)
  else:
    nb_jobs = _nb_jobs

  if noask:
    ask_continue = False

  eda_target_filename = tool_context["eda_target_filename"]
  tool_settings_file = tool_context["tool_settings_file"]
  process_group = tool_context["process_group"]
  run_command = tool_context["run_command"]
  targets = tool_context["targets"]
  constraint_file = tool_context["constraint_file"]
  install_path = tool_context["install_path"]
  force_single_thread = tool_context["force_single_thread"]

  ParallelJob.set_patterns(hard_settings.synth_status_pattern, hard_settings.fmax_status_pattern)

  arch_handler = ArchitectureHandler(
    work_path=work_path,
    arch_path=arch_path,
    script_path=OdatixSettings.odatix_eda_tools_path,
    log_path=hard_settings.work_log_path,
    work_rtl_path=hard_settings.work_rtl_path,
    work_script_path=hard_settings.work_script_path,
    work_report_path=hard_settings.work_report_path,
    work_log_path=hard_settings.work_log_path,
    process_group=process_group,
    command=run_command,
    eda_target_filename=eda_target_filename,
    fmax_status_filename=hard_settings.synth_status_filename,
    frequency_search_filename=hard_settings.frequency_search_filename,
    param_settings_filename=hard_settings.param_settings_filename,
    valid_status=hard_settings.valid_status,
    valid_frequency_search=hard_settings.valid_frequency_search,
    forced_fmax_lower_bound=None,
    forced_fmax_upper_bound=None,
    forced_custom_freq_list=None,
    overwrite=overwrite,
    force_single_thread=force_single_thread
  )

  # RTL analysis does not use target definition files (see load_tool_context):
  # allow get_architectures to run without one.
  architecture_instances = arch_handler.get_architectures(architectures, targets, constraint_file, install_path, keep=keep, timestamp=timestamp, allow_missing_target_file=True)

  valid_arch_count = arch_handler.get_valid_arch_count()

  def prepare_job(arch_instance):
    if True:
      # Get param dir (arch name before '/')
      arch_param_dir = re.sub("/.*", "", arch_instance.arch_name)

      # Create directory
      create_dir(arch_instance.tmp_dir)

      # Create log dir
      create_dir(arch_instance.tmp_log_path)
      
      # Copy scripts
      try:
        copytree(os.path.join(OdatixSettings.odatix_eda_tools_path, hard_settings.common_script_path), arch_instance.tmp_script_path)
      except:
        printc.error('"' + arch_instance.tmp_script_path + '" exists while it should not', script_name)

      copytree(os.path.join(OdatixSettings.odatix_eda_tools_path, tool, hard_settings.tool_tcl_path), arch_instance.tmp_script_path, dirs_exist_ok=True)

      # Copy design
      if arch_instance.design_path is not None:
        copytree(
          src=arch_instance.design_path,
          dst=arch_instance.tmp_dir,
          whitelist=arch_instance.design_path_whitelist,
          blacklist=arch_instance.design_path_blacklist,
          dirs_exist_ok=True
        )

      # Copy rtl (if exists)
      if not arch_instance.generate_rtl:
        copytree(arch_instance.rtl_path, os.path.join(arch_instance.tmp_dir, hard_settings.work_rtl_path), dirs_exist_ok=True)

      # Replace parameters
      if arch_instance.use_parameters:
        if debug: 
          printc.subheader("Replace main parameters")
        param_target_file = os.path.join(arch_instance.tmp_dir, arch_instance.param_target_filename)
        param_filename = os.path.join(arch_path, arch_instance.arch_name + ".txt")
        replace_params(
          base_text_file=param_target_file,
          replacement_text_file=param_filename,
          output_file=param_target_file,
          start_delimiter=arch_instance.start_delimiter,
          stop_delimiter=arch_instance.stop_delimiter,
          replace_all_occurrences=False,
          silent=False if debug else True,
        )
        if debug: 
          print()

      # Replace domain parameters
      domain_dict=dict()
      nb_domain = 0
      arch_config = re.sub('.*/', '', arch_instance.arch_name)
      domain_dict["__main__"] = arch_config
      if timestamp is not None:
        domain_dict["__timestamp__"] = timestamp 
      for param_domain in arch_instance.param_domains:
        if param_domain.use_parameters:
          param_target_file = os.path.join(arch_instance.tmp_dir, param_domain.param_target_file)
          if debug: 
            printc.subheader("Replace parameters for \"" + param_domain.domain + "/" + param_domain.domain_value+ "\"")
          success = replace_params(
            base_text_file=param_target_file,
            replacement_text_file=param_domain.param_file,
            output_file=param_target_file,
            start_delimiter=param_domain.start_delimiter,
            stop_delimiter=param_domain.stop_delimiter,
            replace_all_occurrences=False,
            silent=False if debug else True,
          )
          if success:
            nb_domain = nb_domain + 1
            domain_dict[param_domain.domain] = param_domain.domain_value
          if debug: 
            print()

      with open(os.path.join(arch_instance.tmp_dir, hard_settings.param_domains_filename), 'w') as param_domains_file:
        yaml.dump(domain_dict, param_domains_file, default_flow_style=False, sort_keys=False)

      # Create target and architecture files
      f = open(os.path.join(arch_instance.tmp_dir, hard_settings.target_filename), "w")
      print(arch_instance.target, file=f)
      f.close()
      f = open(os.path.join(arch_instance.tmp_dir, hard_settings.arch_filename), "w")
      print(arch_instance.arch_name, file=f)
      f.close()

      # File copy
      if arch_instance.file_copy_enable:
        file_copy_dest = os.path.join(arch_instance.tmp_dir, arch_instance.file_copy_dest)
        try:
          shutil.copy2(arch_instance.file_copy_source, file_copy_dest)
        except Exception as e:
          printc.error(
            'Could not copy "' + arch_instance.script_copy_source + '" to "' + os.path.realpath(file_copy_dest) + '"',
            script_name,
          )
          printc.cyan("error details: ", end="", script_name=script_name)
          print(str(e))
          return

      # Script copy
      if arch_instance.script_copy_enable:
        try:
          shutil.copy2(arch_instance.script_copy_source, arch_instance.tmp_script_path)
        except Exception as e:
          printc.error(
            'Could not copy "'
            + arch_instance.script_copy_source
            + '" to "'
            + os.path.realpath(arch_instance.tmp_script_path)
            + '"',
            script_name,
          )
          printc.cyan("error details: ", end="", script_name=script_name)
          print(str(e))
          return

      # Edit tcl config script
      tcl_config_file = os.path.join(arch_instance.tmp_script_path, hard_settings.tcl_config_filename)
      report_path = os.path.join(arch_instance.tmp_dir, hard_settings.work_report_path)
      edit_config_file(arch_instance, tcl_config_file)

      # Write yaml config script
      yaml_config_file = os.path.join(arch_instance.tmp_dir, hard_settings.yaml_config_filename)
      Architecture.write_yaml(arch_instance, yaml_config_file)

      # Link all scripts to config script
      for filename in os.listdir(arch_instance.tmp_script_path):
        if filename.endswith(".tcl"):
          with open(os.path.join(arch_instance.tmp_script_path, filename), "r") as f:
            tcl_content = f.read()
          pattern = re.escape(hard_settings.source_tcl) + r"(.+?\.tcl)"

          def replace_path(match):
            return "source " + os.path.join(os.path.realpath(arch_instance.tmp_script_path), match.group(1)).replace('\\','/')

          tcl_content = re.sub(pattern, replace_path, tcl_content)
          with open(os.path.join(arch_instance.tmp_script_path, filename), "w") as f:
            f.write(tcl_content)

      # Concat all strings if it is a list
      if isinstance(arch_handler.command, list):
        command = " ".join(map(str, arch_handler.command)) 
      else:
        command = arch_handler.command

      # Define user accessible variables
      variables = Variables(
        work_path=os.path.realpath(arch_instance.tmp_dir),
        tool_install_path=os.path.realpath(arch_instance.install_path),
        odatix_path=OdatixSettings.odatix_path,
        odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
        script_path=os.path.realpath(os.path.join(arch_instance.tmp_dir, hard_settings.work_script_path)),
        log_path=os.path.realpath(os.path.join(arch_instance.tmp_dir, hard_settings.work_log_path)),
        clock_signal=arch_instance.clock_signal,
        top_level_module=arch_instance.top_level_module,
        lib_name=arch_instance.lib_name,
      )

      # Replace variables in command
      command = replace_variables(command, variables)

      fmax_status_file = os.path.join(arch_instance.tmp_dir, hard_settings.work_log_path, hard_settings.fmax_status_filename)
      synth_status_file = os.path.join(arch_instance.tmp_dir, hard_settings.work_log_path, hard_settings.synth_status_filename)

      # Run custom frequency synthesis script
      running_arch = ParallelJob(
        process=None,
        command=command,
        directory=".",
        generate_rtl=arch_instance.generate_rtl,
        generate_command=arch_instance.generate_command,
        target=arch_instance.target,
        arch=arch_instance.arch_name,
        display_name=arch_instance.arch_display_name + display_suffix,
        status_file=fmax_status_file,
        progress_file=synth_status_file,
        tmp_dir=arch_instance.tmp_dir,
        log_size_limit=log_size_limit,
        progress_mode="analysis",
        status="idle",
      )

      job_list.append(running_arch)

  # The job-building loop is intentionally not run here: the caller runs it
  # after the (single, global) confirmation, so that no temporary work
  # directory is created before the user confirms.
  return {
    "work_path": work_path,
    "tool_settings_file": tool_settings_file,
    "process_group": arch_handler.process_group,
    "arch_handler": arch_handler,
    "architecture_instances": architecture_instances,
    "prepare_job": prepare_job,
    "job_list": job_list,
    "ask_continue": ask_continue,
    "exit_when_done": exit_when_done,
    "log_size_limit": log_size_limit,
    "nb_jobs": nb_jobs,
    "valid_arch_count": valid_arch_count,
  }


######################################
# Run Analysis
######################################


def run_analysis(run_config_settings_filename, arch_path, tool, work_path, target_path, overwrite, noask, exit_when_done, log_size_limit, nb_jobs, check_eda_tool, debug=False, keep=False):
  """
  Run RTL analysis for all selected architectures with one or several eda
  tools. The jobs of every tool run together in a single monitor session
  (like multi-target synthesis); one summary is generated per tool afterwards.

  Args:
      tool (str or list): eda tool(s) to run the analysis with.

  Returns:
      dict: {tool: analysis summary}
  """
  tools = list(dict.fromkeys(tool)) if isinstance(tool, (list, tuple)) else [tool]

  supported_tools = hard_settings.default_supported_tools
  for current_tool in tools:
    if current_tool not in supported_tools:
      printc.error(f"Analysis flow is not yet implemented for tool '{current_tool}'")
      printc.note("Supported tools are: " + ", ".join(supported_tools))
      sys.exit(1)

  # Check every eda tool first (target file, tool directory, test launch)
  tool_contexts = {}
  for current_tool in tools:
    tool_contexts[current_tool] = load_tool_context(current_tool, target_path)
  if check_eda_tool:
    for current_tool in tools:
      tool_context = tool_contexts[current_tool]
      check_tool(
        current_tool,
        command=tool_context["tool_test_command"],
        supported_tools=supported_tools,
        tool_install_path=tool_context["install_path"],
        debug=debug,
      )

  # Same timestamp for the whole batch
  timestamp = get_timestamp_string()

  # The eda tool is displayed like a target: "arch (tool)" in the checklist
  # and in the shared monitor
  multi_tool = len(tools) > 1

  job_list = []
  prepared_tools = []
  for current_tool in tools:
    context = prepare_analysis(
      run_config_settings_filename=run_config_settings_filename,
      arch_path=arch_path,
      tool=current_tool,
      work_path=work_path,
      overwrite=overwrite,
      noask=noask,
      exit_when_done=exit_when_done,
      log_size_limit=log_size_limit,
      nb_jobs=nb_jobs,
      tool_context=tool_contexts[current_tool],
      job_list=job_list,
      timestamp=timestamp,
      display_suffix=f" ({current_tool})" if multi_tool else "",
      debug=debug,
      keep=keep,
    )
    prepared_tools.append((current_tool, context))

  # Print one single global checklist for all tools, with the eda tool shown
  # like a target (same categories as ArchitectureHandler.print_summary)
  merged_lists = {
    "cached_archs": [],
    "overwrite_archs": [],
    "incomplete_archs": [],
    "daemon_archs": [],
    "new_archs": [],
    "error_archs": [],
  }
  for current_tool, context in prepared_tools:
    suffix = f" ({current_tool})" if multi_tool else ""
    arch_handler = context["arch_handler"]
    for key in merged_lists:
      merged_lists[key] += [entry + suffix for entry in getattr(arch_handler, key)]

  ArchitectureHandler.print_arch_list(merged_lists["cached_archs"], "Existing results (skipped -> use '-o' to overwrite)", printc.colors.CYAN)
  ArchitectureHandler.print_arch_list(merged_lists["overwrite_archs"], "Existing results (will be overwritten)", printc.colors.YELLOW)
  ArchitectureHandler.print_arch_list(merged_lists["incomplete_archs"], "Incomplete results (will be overwritten)", printc.colors.YELLOW)
  ArchitectureHandler.print_arch_list(merged_lists["daemon_archs"], "Already managed in a session (skipped)", printc.colors.CYAN)
  ArchitectureHandler.print_arch_list(merged_lists["new_archs"], "New architectures", printc.colors.ENDC)
  ArchitectureHandler.print_arch_list(merged_lists["error_archs"], "Invalid settings, (skipped, see errors above)", printc.colors.RED)

  # Single confirmation for all tools
  total_valid = sum(context["valid_arch_count"] for _, context in prepared_tools)
  if total_valid == 0:
    sys.exit(-1)
  if any(context["ask_continue"] for _, context in prepared_tools):
    printc.bold("\nTotal: " + str(total_valid))
    ask_to_continue()

  print()

  # Build the jobs of every tool (creates the temporary work directories) only
  # now that the run is confirmed.
  for _current_tool, context in prepared_tools:
    for arch_instance in context["architecture_instances"]:
      context["prepare_job"](arch_instance)

  # Single monitor session with the jobs of every tool
  first_context = prepared_tools[0][1]
  parallel_jobs = ParallelJobHandler(
    job_list,
    first_context["nb_jobs"],
    first_context["process_group"],
    auto_exit=first_context["exit_when_done"],
    format_yaml=first_context["tool_settings_file"],
    log_size_limit=first_context["log_size_limit"],
  )
  parallel_jobs.run()

  # Generate one global report per tool
  all_summaries = {}
  for current_tool, context in prepared_tools:
    analysis_file = os.path.join(context["work_path"], "analysis.yml")
    all_summaries[current_tool] = generate_analysis_summary(
      root_dir=context["work_path"],
      output_file=analysis_file,
      tool=current_tool,
    )

  return all_summaries


######################################
# GUI interface (single tool)
######################################


def check_settings(
  run_config_settings_filename,
  arch_path,
  tool,
  work_path,
  target_path,
  overwrite,
  noask,
  exit_when_done,
  log_size_limit,
  nb_jobs,
  check_eda_tool,
  debug=False,
  keep=False,
  cancel_event=None,
):
  """
  Validate the analysis settings of one or several eda tools and prepare (but
  do not build) their jobs, for the Odatix GUI. Mirrors
  run_range_synthesis.check_settings so the GUI run flow can drive analysis
  exactly like a synthesis, and mirrors the CLI run_analysis() multi-tool logic
  so several tools run in a single monitor session (the eda tool is shown like a
  target, "arch (tool)", in one merged global checklist).

  Args:
      tool (str or list): eda tool(s) to run the analysis with.

  Returns the same 8-tuple shape as run_range_synthesis.check_settings:
      (architecture_instances, prepare_job, job_list, tool_settings_file,
       arch_handler, exit_when_done, log_size_limit, nb_jobs)

  For several tools, ``architecture_instances`` is a flat list of
  ``(build_job, arch_instance)`` pairs and ``prepare_job`` dispatches each pair
  to its tool's own builder, so prepare_synthesis() stays tool-agnostic.
  """
  _check_cancel(cancel_event)

  tools = list(dict.fromkeys(tool)) if isinstance(tool, (list, tuple)) else [tool]

  supported_tools = hard_settings.default_supported_tools
  for current_tool in tools:
    if current_tool not in supported_tools:
      printc.error(f"Analysis flow is not yet implemented for tool '{current_tool}'", script_name)
      printc.note("Supported tools are: " + ", ".join(supported_tools), script_name)
      sys.exit(-1)

  tool_contexts = {}
  for current_tool in tools:
    tool_contexts[current_tool] = load_tool_context(current_tool, target_path)
  if check_eda_tool:
    for current_tool in tools:
      tool_context = tool_contexts[current_tool]
      check_tool(
        current_tool,
        command=tool_context["tool_test_command"],
        supported_tools=supported_tools,
        tool_install_path=tool_context["install_path"],
        debug=debug,
      )
      _check_cancel(cancel_event)

  _check_cancel(cancel_event)

  # Same timestamp for the whole batch; the eda tool is displayed like a target
  timestamp = get_timestamp_string()
  multi_tool = len(tools) > 1

  job_list = []
  prepared_tools = []
  for current_tool in tools:
    context = prepare_analysis(
      run_config_settings_filename=run_config_settings_filename,
      arch_path=arch_path,
      tool=current_tool,
      work_path=work_path,
      overwrite=overwrite,
      noask=noask,
      exit_when_done=exit_when_done,
      log_size_limit=log_size_limit,
      nb_jobs=nb_jobs,
      tool_context=tool_contexts[current_tool],
      job_list=job_list,
      timestamp=timestamp,
      display_suffix=f" ({current_tool})" if multi_tool else "",
      debug=debug,
      keep=keep,
    )
    prepared_tools.append((current_tool, context))
    _check_cancel(cancel_event)

  # Print one single global checklist for all tools, with the eda tool shown
  # like a target (same categories as ArchitectureHandler.print_summary)
  merged_lists = {
    "cached_archs": [],
    "overwrite_archs": [],
    "incomplete_archs": [],
    "daemon_archs": [],
    "new_archs": [],
    "error_archs": [],
  }
  for current_tool, context in prepared_tools:
    suffix = f" ({current_tool})" if multi_tool else ""
    arch_handler = context["arch_handler"]
    for key in merged_lists:
      merged_lists[key] += [entry + suffix for entry in getattr(arch_handler, key)]

  ArchitectureHandler.print_arch_list(merged_lists["cached_archs"], "Existing results (skipped -> use '-o' to overwrite)", printc.colors.CYAN)
  ArchitectureHandler.print_arch_list(merged_lists["overwrite_archs"], "Existing results (will be overwritten)", printc.colors.YELLOW)
  ArchitectureHandler.print_arch_list(merged_lists["incomplete_archs"], "Incomplete results (will be overwritten)", printc.colors.YELLOW)
  ArchitectureHandler.print_arch_list(merged_lists["daemon_archs"], "Already managed in a session (skipped)", printc.colors.CYAN)
  ArchitectureHandler.print_arch_list(merged_lists["new_archs"], "New architectures", printc.colors.ENDC)
  ArchitectureHandler.print_arch_list(merged_lists["error_archs"], "Invalid settings, (skipped, see errors above)", printc.colors.RED)

  _check_cancel(cancel_event)

  # Single confirmation for all tools
  total_valid = sum(context["valid_arch_count"] for _, context in prepared_tools)
  ask_continue = any(context["ask_continue"] for _, context in prepared_tools)
  confirm_valid_jobs(total_valid, ask_continue, ask_to_continue, script_name=script_name)

  print()

  # Flatten every tool's instances into (build_job, arch_instance) pairs so the
  # tool-agnostic prepare_synthesis() can build them all after confirmation.
  architecture_instances = []
  for _current_tool, context in prepared_tools:
    build_job = context["prepare_job"]
    for arch_instance in context["architecture_instances"]:
      architecture_instances.append((build_job, arch_instance))

  def prepare_job(pair):
    build_job, arch_instance = pair
    build_job(arch_instance)

  first_context = prepared_tools[0][1]
  return (
    architecture_instances,
    prepare_job,
    job_list,
    first_context["tool_settings_file"],
    first_context["arch_handler"],
    first_context["exit_when_done"],
    first_context["log_size_limit"],
    first_context["nb_jobs"],
  )


def prepare_synthesis(
  architecture_instances,
  prepare_job,
  job_list,
  tool_settings_file,
  arch_handler,
  exit_when_done,
  log_size_limit,
  nb_jobs,
  cancel_event=None,
):
  """
  Build the analysis jobs and return a ParallelJobHandler ready to run/enqueue,
  without running it. Mirrors run_range_synthesis.prepare_synthesis so the GUI
  can enqueue analysis jobs into a daemon session.
  """
  for arch_instance in architecture_instances:
    _check_cancel(cancel_event)
    prepare_job(arch_instance)

  parallel_jobs = ParallelJobHandler(
    job_list,
    nb_jobs,
    arch_handler.process_group,
    auto_exit=exit_when_done,
    format_yaml=tool_settings_file,
    log_size_limit=log_size_limit,
  )
  return parallel_jobs


def get_colored_table_symbol(status, column_width=12):
  """
  Calculates string centers manually before wrapping in ANSI escapes 
  so columns stay perfectly straight in the terminal matrix.
  """
  if status == "PASSED":
    raw_symbol = "✓"
    color = GREEN
  elif status == "WARNING":
    raw_symbol = "⚠"
    color = YELLOW
  elif status == "FAILED":
    raw_symbol = "✗"
    color = RED
  elif status == "INCOMPLETE":
    raw_symbol = "/"
    color = MAGENTA
  else:
    raw_symbol = "-"
    color = BLUE

  # Position the target symbol natively inside plain space cushions
  left_padding = (column_width - 1) // 2
  right_padding = column_width - 1 - left_padding
  
  return f"{' ' * left_padding}{BOLD}{color}{raw_symbol}{RESET}{' ' * right_padding}"


############################################################################

######################################
# Main
######################################

def main(args, settings=None):
  if settings is None:
    settings = OdatixSettings(args.config)
    if not settings.valid:
      sys.exit(-1)

  if args.input is not None:
    run_config_settings_filename = args.input
  else:
    run_config_settings_filename = settings.analysis_settings_file

  if args.archpath is not None:
    arch_path = args.archpath
  else:
    arch_path = settings.arch_path

  if args.work is not None:
    work_path = args.work
  else:
    work_path = os.path.join(settings.work_path, settings.analysis_work_path)

  target_path = settings.target_path
  # The "--tool" CLI argument overrides the "tools" list of the analysis settings
  # file; if neither is given, fall back to DEFAULT_ANALYSIS_TOOLS.
  if args.tool is not None:
    tool = args.tool
  else:
    tool = get_analysis_tools_from_settings(run_config_settings_filename)
  overwrite = args.overwrite
  noask = args.noask
  exit_when_done = args.exit
  log_size_limit = args.logsize
  nb_jobs = args.jobs
  check_eda_tool = not args.trust
  debug = args.debug
  keep = args.keep

  supported_tools = hard_settings.default_supported_tools
  tools = [current_tool for current_tool in tool if current_tool in supported_tools]
  for current_tool in tool:
    if current_tool not in supported_tools:
      printc.warning(f"Tool '{current_tool}' is not supported. Skipping.")
  if len(tools) == 0:
    printc.error("None of the selected tools is supported.", script_name)
    printc.note("Supported tools are: " + ", ".join(supported_tools), script_name)
    sys.exit(-1)

  # All tools run in a single monitor session
  all_summaries = run_analysis(
    run_config_settings_filename,
    arch_path,
    tools,
    work_path,
    target_path,
    overwrite,
    noask,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    check_eda_tool,
    debug,
    keep,
  )

  comparison = {}

  for tool_name, summary in all_summaries.items():
    if not summary or "results" not in summary:
      continue
      
    for result in summary["results"]:
      arch = result["architecture"]
      arch = arch.replace("/log", "")
      parts = arch.split("/")

      if len(parts) >= 2:
        arch = "/".join(parts[-2:])

      if arch not in comparison:
        comparison[arch] = {}
      comparison[arch][tool_name] = result["status"]

  # Global Cross-Validation Summary Layout (Expanded width to 96 for 4 columns)
  print()
  printc.bold("=" * 96, printc.colors.CYAN)
  printc.bold("SUMMARY".center(96), printc.colors.YELLOW)
  printc.bold("=" * 96, printc.colors.CYAN)

  # Column headers match standard fixed widths + added Verilator column
  print(f"{BOLD}{CYAN}{'Architecture':<44} {'DC':^12} {'Genus':^12} {'Vivado':^12} {'Verilator':^12}{RESET}")
  print(f"{CYAN}{'-' * 96}{RESET}")

  for arch in sorted(comparison):
      dc_cell = get_colored_table_symbol(comparison[arch].get("design_compiler", ""))
      genus_cell = get_colored_table_symbol(comparison[arch].get("genus", ""))
      vivado_cell = get_colored_table_symbol(comparison[arch].get("vivado", ""))
      verilator_cell = get_colored_table_symbol(comparison[arch].get("verilator", ""))

      # Print line with native space alignments cleanly respected across 4 columns
      print(f"{arch:<44} {dc_cell} {genus_cell} {vivado_cell} {verilator_cell}")
  print()


if __name__ == "__main__":
  args = parse_arguments()
  main(args)
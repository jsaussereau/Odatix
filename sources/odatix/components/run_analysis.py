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
import odatix.lib.hard_settings as hard_settings
import odatix.lib.eda_tools as eda_tools
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.settings import OdatixSettings
from odatix.lib.architecture_handler import ArchitectureHandler
from odatix.lib.run_report import JobPlan
from odatix.lib.read_tool_settings import read_tool_settings
from odatix.lib.utils import ask_to_continue, get_timestamp_string, resolve_nb_jobs
from odatix.lib.get_from_dict import get_from_dict
from odatix.lib.check_tool import start_tool_check
from odatix.lib.run_settings import get_synth_settings
from odatix.lib.variables import replace_variables, Variables

import odatix.run.cli as run_cli
from odatix.components.cli_options import add_options
from odatix.run.options import RunOptions
from odatix.components.run_common import confirm_valid_jobs, settle_tool_checks, abort_if_empty_job_list, run_prepare_loop
from odatix.components.synthesis_common import build_prepare_synthesis_job
from odatix.components.export_analysis import configure_analysis_job_exports
import odatix.components.export_derived_metrics as exp_derived
import odatix.lib.analysis as analysis
import odatix.lib.yaml_loader as yaml_loader


class AnalysisCancelled(Exception):
  pass

def _check_cancel(cancel_event):
  if cancel_event is not None and cancel_event.is_set():
    raise AnalysisCancelled()


script_name = os.path.basename(__file__)


######################################
# Parse Arguments
######################################

def add_arguments(parser):
  add_options(
    parser, "tool", "architectures", "flow", "overwrite", "noask", "daemon_options", "settings_file", "arch_path", "work_path",
    "exit_when_done", "nb_jobs", "check_eda_tool", "debug", "keep", "log_size_limit", "export_options", "config",
    tool={"nargs": "+", "default": None, "help": "tool(s) to run (default: \"tools\" of the analysis settings file, else \"default_tool\" of odatix.yml)"},
    flow={"nargs": "+", "help": "flow(s) to run, as \"flow\" (applied to every tool) or \"tool:flow\" (default: each tool's default flow)"},
  )


def parse_arguments():
  parser = argparse.ArgumentParser(description="Run RTL analysis for all architectures")
  add_arguments(parser)
  return parser.parse_args()


######################################
# Tool context
######################################


#: Nothing: the run then uses the default tool of the workspace (see Run.resolve_tool).
DEFAULT_ANALYSIS_TOOLS = []


def parse_flow_selection(flow_args, tools):
  """
  Turn the "--flow" arguments into a {tool: flow} mapping. An entry without a
  tool prefix ("place_route") applies to every tool; an entry of the form
  "tool:flow" only applies to that tool and wins over a bare entry.

  Returns:
      dict: {tool: flow name or None for the tool's default flow}
  """
  flows = {current_tool: None for current_tool in tools}
  if not flow_args:
    return flows

  for entry in flow_args:
    if ":" not in str(entry):
      for current_tool in flows:
        flows[current_tool] = str(entry).strip()

  for entry in flow_args:
    entry = str(entry)
    if ":" not in entry:
      continue
    tool_name, _, flow_name = entry.partition(":")
    tool_name = tool_name.strip()
    if tool_name not in flows:
      printc.error(f'"--flow {entry}" refers to the tool "{tool_name}", which is not one of the selected tools', script_name)
      printc.note("Selected tools are: " + ", ".join(flows), script_name)
      sys.exit(-1)
    flows[tool_name] = flow_name.strip()

  return flows


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
      settings_data = yaml.load(f, Loader=yaml_loader.SafeLoader)
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


def analysis_install_path(tool, target_path):
  """
  The install path an analysis runs the tool from.

  An analysis targets no technology, so it reads nothing else from the target
  file — but a tool that is not on the $PATH (LibreLane, run from the nix-shell
  of its checkout) is found through the "tool_install_path" of that file all
  the same. "/" (the tool is on the $PATH) when the file, or the key, is missing.
  """
  try:
    target_file = eda_tools.resolve_target_file(tool, target_path)
  except Exception:
    return "/"
  if not os.path.isfile(target_file):
    return "/"
  try:
    with open(target_file, "r") as f:
      settings_data = yaml.safe_load(f)
  except Exception:
    return "/"
  if not isinstance(settings_data, dict):
    return "/"
  install_path = settings_data.get("tool_install_path")
  if not install_path:
    return "/"
  install_path = os.path.realpath(os.path.expanduser(str(install_path)))
  return install_path if os.path.isdir(install_path) else "/"


def load_tool_context(tool, target_path, flow=None):
  """
  Validate an eda tool (tool directory) and load its tool settings, for the RTL
  RTL analysis job type.

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
  # Resolve the tool directory (user tools directory first, then built-in)
  eda_tool_dir = eda_tools.get_tool_dir(tool)
  if eda_tool_dir is None:
    printc.error('No directory found for the selected eda tool "' + tool + '"', script_name)
    printc.note(
      'The selected eda tool "'
      + tool
      + "\" is not one of the available tools. Check out Odatix's documentation to add support for your own eda tool",
      script_name,
    )
    printc.note("Available tools are: " + ", ".join(eda_tools.get_supported_tools()), script_name)
    sys.exit(-1)

  # Get tool settings
  tool_settings_file = os.path.realpath(os.path.join(eda_tool_dir, hard_settings.tool_settings_filename))
  process_group, run_command, tool_test_command, _, flow_name, flow_steps = read_tool_settings(
    tool, tool_settings_file, synth_type='analysis', flow=flow
  )

  # No target file for analysis: use a single generic target and a placeholder
  # constraint file (the shared init_script.tcl always creates it, even though
  # analysis never applies timing constraints; it must be a plain filename, not
  # empty, see hard_settings.default_analysis_constraint_file). The install path
  # defaults to "/" (tool expected on the $PATH).
  targets = [hard_settings.default_analysis_target]
  constraint_file = hard_settings.default_analysis_constraint_file
  install_path = analysis_install_path(tool, target_path)
  force_single_thread = False

  # Concat all strings if it is a list
  if isinstance(tool_test_command, list):
    tool_test_command = " ".join(map(str, tool_test_command))

  # Define user accessible variables
  variables = Variables(
    tool_install_path=os.path.realpath(install_path),
    odatix_path=OdatixSettings.odatix_path,
    odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
    tool_path=eda_tool_dir,
  )

  # Replace variables in command
  tool_test_command = replace_variables(tool_test_command, variables)

  return {
    "eda_target_filename": None,
    "tool_settings_file": tool_settings_file,
    # tool.yml the log formatter reads (see eda_tools.get_format_settings_file)
    "format_settings_file": eda_tools.get_format_settings_file(tool) or tool_settings_file,
    "flow": flow_name,
    "flow_steps": flow_steps,
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
  selected_architectures=None,
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
  # Architectures named by the run ("--arch") replace the list of the file.
  if selected_architectures:
    architectures = list(selected_architectures)

  # Two flows of the same tool are alternatives to compare: they each get their
  # own work sub-directory ("vivado@lint_strict"), the default flow keeping the
  # bare tool name.
  work_path = os.path.join(work_path, eda_tools.tool_work_dirname(tool, tool_context.get("flow"), job_type="analysis"))

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

  nb_jobs = resolve_nb_jobs(nb_jobs if nb_jobs is not None else _nb_jobs)

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

  # The job directory is prepared exactly like the one of a synthesis: an
  # analysis is the cheapest of the jobs a tool runs, not a different kind.
  build_job = build_prepare_synthesis_job(
    arch_handler=arch_handler,
    arch_path=arch_path,
    tool=tool,
    log_size_limit=log_size_limit,
    debug=debug,
    timestamp=timestamp,
    progress_mode="analysis",
    script_name=script_name,
    flow=tool_context.get("flow"),
    steps=tool_context.get("flow_steps"),
    display_suffix=display_suffix,
  )

  def prepare_job(arch_instance):
    build_job(arch_instance, job_list)

  # The job-building loop is intentionally not run here: the caller runs it
  # after the (single, global) confirmation, so that no temporary work
  # directory is created before the user confirms.
  return {
    "work_path": work_path,
    "tool_settings_file": tool_settings_file,
    # Forwarded from the tool context: needed by the monitor (log formatter)
    # and by the result export (flow name)
    "format_settings_file": tool_context["format_settings_file"],
    "flow": tool_context["flow"],
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


def merged_analysis_plan(prepared_tools, multi_tool):
  """
  The check outcome of every eda tool as a single plan. The tool is appended to
  the job names, the way a target would be, so one checklist covers the run.
  """
  plan = JobPlan()
  for current_tool, context in prepared_tools:
    suffix = f" ({current_tool})" if multi_tool else ""
    plan.merge(context["arch_handler"].plan, suffix=suffix)
  return plan


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
  tool_check_sink=None,
  flows=None,
  selected_architectures=None,
):
  """
  Validate the analysis settings of one or several eda tools and prepare (but
  do not build) their jobs, like run_fixed_freq_synthesis.check_settings does, so
  that odatix.run drives an analysis exactly like a synthesis. The jobs of
  every tool run in a single session, the eda tool shown like a target,
  "arch (tool)", in one merged global checklist.

  Args:
      tool (str or list): eda tool(s) to run the analysis with.

  Returns the same 8-tuple shape as run_fixed_freq_synthesis.check_settings:
      (architecture_instances, prepare_job, job_list, tool_settings_file,
       arch_handler, exit_when_done, log_size_limit, nb_jobs)

  For several tools, ``architecture_instances`` is a flat list of
  ``(build_job, arch_instance)`` pairs and ``prepare_job`` dispatches each pair
  to its tool's own builder, so prepare_synthesis() stays tool-agnostic.
  """
  _check_cancel(cancel_event)

  tools = list(dict.fromkeys(tool)) if isinstance(tool, (list, tuple)) else [tool]

  supported_tools = eda_tools.tools_supporting("analysis")
  for current_tool in tools:
    if current_tool not in supported_tools:
      printc.error(f"RTL analysis is not supported by the tool '{current_tool}'", script_name)
      printc.note("Supported tools are: " + ", ".join(supported_tools), script_name)
      sys.exit(-1)

  flows = parse_flow_selection(None, tools) if flows is None else dict(flows)
  tool_contexts = {}
  for current_tool in tools:
    tool_contexts[current_tool] = load_tool_context(current_tool, target_path, flow=flows.get(current_tool))
  # Every tool check runs in the background while the settings are processed;
  # they are waited for just before the checklist and the confirmation.
  tool_checks = []
  if check_eda_tool:
    for current_tool in tools:
      tool_context = tool_contexts[current_tool]
      tool_checks.append(start_tool_check(
        current_tool,
        command=tool_context["tool_test_command"],
        supported_tools=supported_tools,
        tool_install_path=tool_context["install_path"],
        debug=debug,
      ))
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
      selected_architectures=selected_architectures,
    )
    prepared_tools.append((current_tool, context))
    _check_cancel(cancel_event)

  # One single global checklist for all tools, with the eda tool shown like a
  # target: merge every tool plan into one, suffixing the job names.
  plan = merged_analysis_plan(prepared_tools, multi_tool)
  plan.print_summary(noun="architectures")

  settle_tool_checks(tool_checks, tool_check_sink)

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
    first_context["format_settings_file"],
    first_context["arch_handler"],
    first_context["exit_when_done"],
    first_context["log_size_limit"],
    first_context["nb_jobs"],
    plan,
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
  export_output_dir=None,
  analysis_work_root=None,
  flows=None,
  expected=None,
):
  """
  Build the analysis jobs and return a ParallelJobHandler ready to run/enqueue,
  without running it. Mirrors run_fixed_freq_synthesis.prepare_synthesis so the GUI
  can enqueue analysis jobs into a daemon session.

  When ``export_output_dir`` and ``analysis_work_root`` are given, each job is
  tagged for per-job result export (au fil de l'eau), so the daemon writes the
  Explorer results file as jobs finish (see configure_analysis_job_exports).
  ``expected`` is the "expected" section of the run settings file, what it says
  is normal for these designs.
  """
  run_prepare_loop(
    instances=architecture_instances,
    build_job=prepare_job,
    job_list=job_list,
    check_cancel=lambda: _check_cancel(cancel_event),
  )

  # An architecture can pass the initial checklist but still fail while its job
  # is being built (e.g. a missing design_path): do not launch the monitor/daemon
  # session with zero jobs if every one of them failed.
  abort_if_empty_job_list(job_list, script_name=script_name)

  parallel_jobs = ParallelJobHandler(
    job_list,
    nb_jobs,
    arch_handler.process_group,
    auto_exit=exit_when_done,
    format_yaml=tool_settings_file,
    log_size_limit=log_size_limit,
  )

  if export_output_dir and analysis_work_root:
    configure_analysis_job_exports(
      parallel_jobs=parallel_jobs,
      analysis_work_root=analysis_work_root,
      output_dir=export_output_dir,
      flows=flows,
      expected=expected,
    )

  # Whole-batch derivation: a derived metric reads records other jobs produce,
  # so it can only be computed once every job of the batch is done.
  if export_output_dir:
    exp_derived.configure_post_batch_derivation(parallel_jobs, export_output_dir)

  return parallel_jobs


def read_run_expectations(settings_filename):
  """
  The "expected" section of an analysis settings file, as written: what is
  normal for the designs it analyzes (see odatix.lib.analysis.Expectation).
  """
  if not settings_filename or not os.path.isfile(settings_filename):
    return None
  try:
    with open(settings_filename, "r") as f:
      settings_data = yaml_loader.safe_load(f)
  except Exception:
    return None
  if not isinstance(settings_data, dict):
    return None
  return settings_data.get("expected")


######################################
# Main
######################################

def main(args):
  import odatix.components.analysis_report as analysis_report

  workspace = run_cli.command_workspace(args.config, script_name)
  options = RunOptions.from_namespace(args)
  # Without "--tool", the tools are those the settings file lists.
  if not options.tool:
    settings_file = options.settings_file or workspace.paths.analyze_settings_file
    options.tool = get_analysis_tools_from_settings(settings_file)

  run = run_cli.execute(run_cli.command_run("analysis", workspace=workspace, options=options))

  # Attached to the monitor, the jobs are over when it returns: their report
  # is what the user is waiting for. Detached, they are only starting.
  if options.detach:
    printc.note("Run \"odatix results analysis\" once the jobs are done to get their report", script_name)
    return

  job_dirs = {os.path.realpath(instance.tmp_dir) for _build_job, instance in run.jobs}
  jobs = {
    job_dir: tool_flow
    for job_dir, tool_flow in analysis_report.job_directories(run.work_path).items()
    if os.path.realpath(job_dir) in job_dirs
  }
  analysis_report.print_report(analysis_report.collect_results(
    jobs, expected=analysis.read_expectations(read_run_expectations(run.settings_file))
  ))


if __name__ == "__main__":
  args = parse_arguments()
  main(args)

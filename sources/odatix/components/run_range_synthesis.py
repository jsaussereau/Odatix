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
from odatix.lib.utils import read_from_list, copytree, create_dir, ask_to_continue, KeyNotInListError, BadValueInListError
from odatix.lib.get_from_dict import get_from_dict
from odatix.lib.prepare_work import edit_config_file
from odatix.lib.check_tool import check_tool
from odatix.lib.run_settings import get_synth_settings
from odatix.lib.variables import replace_variables, Variables

script_name = os.path.basename(__file__)


######################################
# Parse Arguments
######################################


def add_arguments(parser):
  parser.add_argument("-t", "--tool", default="vivado", help="eda tool in use (default: vivado)")
  parser.add_argument("-o", "--overwrite", action="store_true", help="overwrite existing results")
  parser.add_argument("-y", "--noask", action="store_true", help="do not ask to continue")
  parser.add_argument("-i", "--input", help="input settings file")
  parser.add_argument("-a", "--archpath", help="architecture directory")
  parser.add_argument("-w", "--work", help="work directory")
  parser.add_argument("-E", "--exit", action="store_true", help="exit monitor when all jobs are done")
  parser.add_argument("-j", "--jobs", help="maximum number of parallel jobs")
  parser.add_argument("-T", "--trust", action="store_true", help="do not check eda tool before runnning jobs (saves time)")
  parser.add_argument("-D", "--debug", action="store_true", help="enable debug mode to help troubleshoot settings files")
  parser.add_argument("--from", dest="from_freq", type=int, help="override range lower bound for custom frequency synthesis (in MHz)")
  parser.add_argument("--to", dest="to_freq", type=int, help="override range upper bound for custom frequency synthesis (in MHz)")
  parser.add_argument("--step", dest="step_freq", type=int, help="override range step bound for custom frequency synthesis (in MHz)")
  parser.add_argument("--at", dest="at_freq", action='append', type=int, help="override freqency at which custom frequency synthesis should be run (in MHz)")
  parser.add_argument("--logsize", help="size of the log history per job in the monitor")
  parser.add_argument(
    "-c",
    "--config",
    default=OdatixSettings.DEFAULT_SETTINGS_FILE,
    help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
  )


def parse_arguments():
  parser = argparse.ArgumentParser(description="Run synthesis at specigied frequencies on selected architectures")
  add_arguments(parser)
  return parser.parse_args()


######################################
# Run Synthesis
######################################


def run_synthesis(run_config_settings_filename, arch_path, tool, work_path, target_path, overwrite, noask, exit_when_done, log_size_limit, nb_jobs, check_eda_tool, custom_freq_list=[], debug=False):
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

  eda_target_filename = os.path.realpath(os.path.join(target_path, "target_" + tool + ".yml"))

  # Check if the target file exists
  if not os.path.isfile(eda_target_filename):
    printc.error(
      'Target file "' + eda_target_filename + '", for the selected eda tool "' + tool + '" does not exist', script_name
    )
    sys.exit(-1)

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
  process_group, report_path, run_command, tool_test_command, _ = read_tool_settings(tool, tool_settings_file,  synth_type='custom_freq_synthesis')

  with open(eda_target_filename, "r") as f:
    try:
      settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    except Exception as e:
      printc.error('Settings file "' + eda_target_filename + '" is not a valid YAML file', script_name)
      printc.cyan("error details: ", end="", script_name=script_name)
      print(str(e))
      sys.exit(-1)

    # Mandatory keys
    try:
      targets = read_from_list("targets", settings_data, eda_target_filename, script_name=script_name)
      constraint_file = read_from_list("constraint_file", settings_data, eda_target_filename, script_name=script_name)
    except (KeyNotInListError, BadValueInListError):
      sys.exit(-1)  # if a key is missing

    # Optional keys
    try:
      install_path = read_from_list("tool_install_path", settings_data, eda_target_filename, print_error=False, script_name=script_name)
      install_path = os.path.realpath(os.path.expanduser(install_path))
      if not os.path.isdir(install_path):
        printc.error('The installation path "' + install_path + '" defined for tool "' + tool + '" in "' + eda_target_filename + '" does not exist', script_name)
        printc.note('Please update the path in "' + eda_target_filename + '"', script_name=script_name)
        printc.note('if no installation path is needed by ' + tool + '\'s Makefile, simply remove "install_path" from "' + eda_target_filename + '"', script_name=script_name)
        sys.exit(-1)

    except (KeyNotInListError, BadValueInListError):
      printc.note('No tool_install_path specified for "' + tool + '"', script_name=script_name)
      install_path = "/"

    force_single_thread, _ = get_from_dict("force_single_thread", settings_data, eda_target_filename, default_value=False, script_name=script_name)

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

  # Try launching eda tool
  if check_eda_tool:
    check_tool(
      tool, command=tool_test_command, supported_tools=hard_settings.default_supported_tools, tool_install_path=install_path, debug=debug
    )

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
    forced_custom_freq_list=custom_freq_list,
    overwrite=overwrite,
    force_single_thread=force_single_thread,
  )

  architecture_instances = arch_handler.get_architectures(architectures, targets, constraint_file, install_path, range_mode=True)

  # Print checklist summary
  arch_handler.print_summary()

  if arch_handler.get_valid_arch_count() > 0:
    if ask_continue:
      print()
      ask_to_continue()
  else:
    sys.exit(-1)

  print()

  job_list = []

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

      if nb_domain > 0:
        with open(os.path.join(arch_instance.tmp_dir, hard_settings.param_domains_filename), 'w') as param_domains_file:
          yaml.dump(domain_dict, param_domains_file, default_flow_style=False)

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
        display_name=arch_instance.arch_display_name,
        status_file=fmax_status_file,
        progress_file=synth_status_file,
        tmp_dir=arch_instance.tmp_dir,
        log_size_limit=log_size_limit,
        progress_mode="synth",
        status="idle",
      )

      job_list.append(running_arch)

  for arch_instance in architecture_instances:
    prepare_job(arch_instance)

  parallel_jobs = ParallelJobHandler(
    job_list,
    nb_jobs,
    arch_handler.process_group,
    auto_exit=exit_when_done,
    format_yaml= tool_settings_file,
    log_size_limit=log_size_limit,
  )
  job_exit_success = parallel_jobs.run()


######################################
# Main
######################################


def main(args, settings=None):
  # Get settings
  if settings is None:
    settings = OdatixSettings(args.config)
    if not settings.valid:
      sys.exit(-1)

  if args.input is not None:
    run_config_settings_filename = args.input
  else:
    run_config_settings_filename = settings.custom_freq_synthesis_settings_file

  if args.archpath is not None:
    arch_path = args.archpath
  else:
    arch_path = settings.arch_path

  if args.work is not None:
    work_path = args.work
  else:
    work_path = os.path.join(settings.work_path, settings.custom_freq_synthesis_work_path)

  target_path = settings.target_path
  tool = args.tool
  overwrite = args.overwrite
  noask = args.noask
  exit_when_done = args.exit
  log_size_limit = args.logsize
  nb_jobs = args.jobs
  check_eda_tool = not args.trust
  debug = args.debug

  if args.at_freq is None:
    custom_freq_list = []
  else:
    custom_freq_list = args.at_freq

  if args.to_freq is not None and (args.from_freq is None or args.step_freq is None):
    printc.error("--to cannot be used without --from and --step", script_name=script_name)
    sys.exit(-1)
  elif args.from_freq is not None and (args.to_freq is None or args.step_freq is None):
    printc.error("--from cannot be used without --to and --step", script_name=script_name)
    sys.exit(-1)
  elif args.step_freq is not None and (args.to_freq is None or args.from_freq is None):
    printc.error("--step cannot be used without --from and --to", script_name=script_name)
    sys.exit(-1)
  elif args.from_freq is not None and args.to_freq is not None and args.step_freq is not None:
    if ArchitectureHandler.check_bounds(args.from_freq, args.to_freq, args.step_freq, synth_type="custom frequency synthesis"):
      range_list = ArchitectureHandler.create_list_from_range(args.from_freq, args.to_freq, args.step_freq)
      custom_freq_list = custom_freq_list + range_list
    else:
      sys.exit(-1)

  run_synthesis(run_config_settings_filename, arch_path, tool, work_path, target_path, overwrite, noask, exit_when_done, log_size_limit, nb_jobs, check_eda_tool, custom_freq_list, debug)


if __name__ == "__main__":
  args = parse_arguments()
  main(args)

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

import odatix.lib.printc as printc
from odatix.lib.replace_params import replace_params
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.settings import OdatixSettings
from odatix.lib.architecture_handler import ArchitectureHandler, Architecture
from odatix.lib.utils import read_from_list, copytree, create_dir, ask_to_continue, KeyNotInListError, BadValueInListError
from odatix.lib.prepare_work import edit_config_file
from odatix.lib.check_tool import check_tool
from odatix.lib.run_settings import get_synth_settings

current_dir = os.path.dirname(os.path.abspath(__file__))

######################################
# Settings
######################################

work_path = "work"

# Get eda_tools folder
if getattr(sys, "frozen", False):
  base_path = os.path.dirname(sys.executable)
else:
  base_path = current_dir
script_path = os.path.realpath(os.path.join(base_path, os.pardir, os.pardir, "odatix_eda_tools"))

work_script_path = "scripts"
work_report_path = "report"
work_result_path = "result"
work_log_path = "log"
common_script_path = "_common"
log_path = "log"
arch_path = "architectures"

nb_jobs = 4

param_settings_filename = "_settings.yml"
arch_filename = "architecture.txt"
target_filename = "target.txt"
tcl_config_filename = "settings.tcl"
yaml_config_filename = "settings.yml"
fmax_status_filename = "status.log"
synth_status_filename = "synth_status.log"
frequency_search_filename = "frequency_search.log"
tool_makefile_filename = "makefile.mk"
constraint_filename = "constraints.txt"
source_tcl = "source scripts/"
synth_fmax_rule = "synth_fmax_only"
test_tool_rule = "test_tool"

settings_ini_section = "SETTINGS"
valid_status = "Done: 100%"
valid_frequency_search = "Highest frequency with timing constraints being met"

progress_bar_size = 50
refresh_time = 5

default_fmax_lower_bound = 50
default_fmax_upper_bound = 500

fmax_status_pattern = re.compile(r"(.*): ([0-9]+)% \(([0-9]+)\/([0-9]+)\)(.*)")
synth_status_pattern = re.compile(r"(.*): ([0-9]+)%(.*)")

default_supported_tools = ["vivado", "design_compiler", "openlane"]

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
  parser.add_argument(
    "-c",
    "--config",
    default=OdatixSettings.DEFAULT_SETTINGS_FILE,
    help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
  )


def parse_arguments():
  parser = argparse.ArgumentParser(description="Run fmax synthesis on selected architectures")
  add_arguments(parser)
  return parser.parse_args()


######################################
# Run Synthesis
######################################


def run_synthesis(run_config_settings_filename, arch_path, tool, work_path, target_path, overwrite, noask):
  _overwrite, ask_continue, show_log_if_one, nb_jobs, architectures = get_synth_settings(run_config_settings_filename)

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

  if noask:
    ask_continue = False

  eda_target_filename = os.path.realpath(os.path.join(target_path, "target_" + tool + ".yml"))

  # Check if the target file exists
  if not os.path.isfile(eda_target_filename):
    printc.error(
      'Target file "' + eda_target_filename + '", for the selected eda tool "' + tool + '" does not exist', script_name
    )
    sys.exit(-1)

  # Check if the tool has a dedicated directory in script_path
  eda_tool_dir = script_path + "/" + tool
  if not os.path.isdir(eda_tool_dir):
    printc.error(
      'The directory "' + eda_tool_dir + '", for the selected eda tool "' + tool + '" does not exist', script_name
    )
    if tool not in default_supported_tools:
      printc.note(
        'The selected eda tool "'
        + tool
        + "\" is not one of the supported tool. Check out Odatix's documentation to add support for your own eda tool",
        script_name,
      )
    sys.exit(-1)

  # Check if the tool makefile exists
  tool_makefile_file = script_path + "/" + tool + "/" + tool_makefile_filename
  if not os.path.isfile(tool_makefile_file):
    printc.error(
      'Makefile "' + tool_makefile_file + '", for the selected eda tool "' + tool + '" does not exist', script_name
    )
    if tool not in default_supported_tools:
      printc.note(
        'The selected eda tool "'
        + tool
        + "\" is not one of the supported tool. Check out Odatix's documentation to add support for your own eda tool",
        script_name,
      )
    sys.exit(-1)

  # Get tool settings
  tool_settings_filename = os.path.realpath(os.path.join(eda_tool_dir, "tool.yml"))

  # Check if the tool file exists 
  if not os.path.isfile(tool_settings_filename):
    printc.error(
      'Settings file "' + tool_settings_filename + '", for the selected eda tool "' + tool + '" does not exist', script_name
    )
    sys.exit(-1)
  with open(tool_settings_filename, "r") as f:
    try:
      settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    except Exception as e:
      printc.error('Settings file "' + tool_settings_filename + '", for the selected eda tool "' + tool + '" is not a valid YAML file', script_name)
      printc.cyan("error details: ", end="", script_name=script_name)
      print(str(e))
      sys.exit(-1)

    # Mandatory keys
    try:
      process_group = read_from_list("process_group", settings_data, tool_settings_filename, script_name=script_name)
    except (KeyNotInListError, BadValueInListError):
      pass

    global work_report_path
    try:
      work_report_path = read_from_list("report_path", settings_data, tool_settings_filename, optional=True, print_error=False, script_name=script_name)
    except (KeyNotInListError, BadValueInListError):
      pass

  # Try launching eda tool
  check_tool(
    tool, script_path, makefile=tool_makefile_filename, rule=test_tool_rule, supported_tools=default_supported_tools
  )

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

  ParallelJob.set_patterns(synth_status_pattern, fmax_status_pattern)

  arch_handler = ArchitectureHandler(
    work_path=work_path,
    arch_path=arch_path,
    script_path=script_path,
    work_script_path=work_script_path,
    work_report_path=work_report_path,
    log_path=log_path,
    process_group=process_group,
    eda_target_filename=eda_target_filename,
    fmax_status_filename=fmax_status_filename,
    frequency_search_filename=frequency_search_filename,
    param_settings_filename=param_settings_filename,
    valid_status=valid_status,
    valid_frequency_search=valid_frequency_search,
    default_fmax_lower_bound=default_fmax_lower_bound,
    default_fmax_upper_bound=default_fmax_upper_bound,
    overwrite=overwrite,
  )

  architecture_instances = arch_handler.get_architectures(architectures, targets, constraint_file)

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

      # Copy scripts
      try:
        copytree(script_path + "/" + common_script_path, arch_instance.tmp_script_path)
      except:
        printc.error('"' + arch_instance.tmp_script_path + '" exists while it should not', script_name)

      copytree(script_path + "/" + tool + "/tcl", arch_instance.tmp_script_path, dirs_exist_ok=True)

      # Copy design
      if arch_instance.design_path != -1:
        copytree(arch_instance.design_path, arch_instance.tmp_dir, dirs_exist_ok=True)

      # Copy rtl (if exists)
      if not arch_instance.generate_rtl:
        copytree(arch_instance.rtl_path, arch_instance.tmp_dir + "/" + "rtl", dirs_exist_ok=True)

      # Replace parameters
      if arch_instance.use_parameters:
        # printc.subheader("Replace parameters")
        param_target_file = arch_instance.tmp_dir + "/" + arch_instance.param_target_filename
        param_filename = arch_path + "/" + arch_instance.arch_name + ".txt"
        replace_params(
          base_text_file=param_target_file,
          replacement_text_file=param_filename,
          output_file=param_target_file,
          start_delimiter=arch_instance.start_delimiter,
          stop_delimiter=arch_instance.stop_delimiter,
          replace_all_occurrences=False,
          silent=True,
        )
        # print()

      # Create target and architecture files
      f = open(arch_instance.tmp_dir + "/" + target_filename, "w")
      print(arch_instance.target, file=f)
      f.close()
      f = open(arch_instance.tmp_dir + "/" + arch_filename, "w")
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
      tcl_config_file = os.path.join(arch_instance.tmp_script_path, tcl_config_filename)
      report_path = os.path.join(arch_instance.tmp_dir, work_report_path)
      edit_config_file(arch_instance, tcl_config_file)

      # Write yaml config script
      yaml_config_file = os.path.join(arch_instance.tmp_dir, yaml_config_filename)
      Architecture.write_yaml(arch_instance, yaml_config_file)

      # Link all scripts to config script
      for filename in os.listdir(arch_instance.tmp_script_path):
        if filename.endswith(".tcl"):
          with open(arch_instance.tmp_script_path + "/" + filename, "r") as f:
            tcl_content = f.read()
          pattern = re.escape(source_tcl) + r"(.+?\.tcl)"

          def replace_path(match):
            return "source " + os.path.realpath(arch_instance.tmp_script_path) + "/" + match.group(1)

          tcl_content = re.sub(pattern, replace_path, tcl_content)
          with open(arch_instance.tmp_script_path + "/" + filename, "w") as f:
            f.write(tcl_content)

      # Run binary search script
      tool_makefile_file = script_path + "/" + tool + "/" + tool_makefile_filename
      command = (
        "make -f {} {}".format(tool_makefile_file, synth_fmax_rule)
        + ' WORK_DIR="{}"'.format(os.path.realpath(arch_instance.tmp_dir))
        + ' SCRIPT_DIR="{}"'.format(os.path.realpath(os.path.join(arch_instance.tmp_dir, work_script_path)))
        + ' LOG_DIR="{}"'.format(os.path.realpath(os.path.join(arch_instance.tmp_dir, log_path)))
        + ' CLOCK_SIGNAL="{}"'.format(arch_instance.clock_signal)
        + ' TOP_LEVEL_MODULE="{}"'.format(arch_instance.top_level_module)
        + ' LIB_NAME="{}"'.format(arch_instance.lib_name)
        + " --no-print-directory"
      )

      fmax_status_file = os.path.join(arch_instance.tmp_dir, log_path, fmax_status_filename)
      synth_status_file = os.path.join(arch_instance.tmp_dir, log_path, synth_status_filename)

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
        progress_mode="fmax",
        status="idle",
      )

      job_list.append(running_arch)

  for arch_instance in architecture_instances:
    prepare_job(arch_instance)

  parallel_jobs = ParallelJobHandler(job_list, nb_jobs, arch_handler.process_group)
  job_exit_success = parallel_jobs.run()

  # Summary
  if job_exit_success:
    print()
    for running_arch in job_list:
      tmp_dir = work_path + "/" + running_arch.target + "/" + running_arch.arch
      frequency_search_file = tmp_dir + "/" + log_path + "/" + frequency_search_filename
      try:
        with open(frequency_search_file, "r") as file:
          lines = file.readlines()
          if len(lines) >= 1:
            summary_line = lines[-1]
            print(running_arch.display_name + ": " + summary_line, end="")
      except:
        pass
    print()


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
    run_config_settings_filename = settings.fmax_synthesis_settings_file

  if args.archpath is not None:
    arch_path = args.archpath
  else:
    arch_path = settings.arch_path

  if args.work is not None:
    work_path = args.work
  else:
    work_path = settings.work_path

  target_path = settings.target_path
  tool = args.tool
  overwrite = args.overwrite
  noask = args.noask

  run_synthesis(run_config_settings_filename, arch_path, tool, work_path, target_path, overwrite, noask)


if __name__ == "__main__":
  args = parse_arguments()
  main(args)

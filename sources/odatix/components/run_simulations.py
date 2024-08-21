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
import argparse
import subprocess

import odatix.lib.printc as printc
from odatix.lib.replace_params import replace_params
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.settings import OdatixSettings
from odatix.lib.simulation_handler import SimulationHandler
from odatix.lib.utils import read_from_list, copytree, create_dir, ask_to_continue
from odatix.lib.prepare_work import edit_config_file
from odatix.lib.check_tool import check_tool
from odatix.lib.run_settings import get_sim_settings

######################################
# Settings
######################################

work_path = "work/simulation"
work_script_path = "scripts"
common_script_path = "_common"
log_path = "log"
arch_path = "architectures"
sim_path = "simulations"
rtl_path = "rtl"

nb_jobs = 4

param_settings_filename = "_settings.yml"
sim_settings_filename = "_settings.yml"
sim_makefile_filename = "Makefile"
sim_rule = "sim"
sim_progress_filename = "progress.log"

progress_bar_size = 50
refresh_time = 5

default_fmax_lower_bound = 50
default_fmax_upper_bound = 500

sim_status_pattern = re.compile(r"(.*): ([0-9]+)%(.*)")

script_name = os.path.basename(__file__)

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument('-o', '--overwrite', action='store_true', help='overwrite existing results')
  parser.add_argument('-y', '--noask', action='store_true', help='do not ask to continue')
  parser.add_argument('-i', '--input', help='input settings file')
  parser.add_argument('-a', '--archpath', help='architecture directory')
  parser.add_argument('-s', '--simpath', help='simulation directory')
  parser.add_argument('-w', '--work', help='simulation work directory')
  parser.add_argument('-c', '--config', default=OdatixSettings.DEFAULT_SETTINGS_FILE, help='global settings file for Odatix (default: ' + OdatixSettings.DEFAULT_SETTINGS_FILE + ')')

def parse_arguments():
  parser = argparse.ArgumentParser(description='Run parallel simulations')
  add_arguments(parser)
  return parser.parse_args()


######################################
# Run Simulations
######################################

def run_simulations(run_config_settings_filename, arch_path, sim_path, work_path, overwrite, noask):
  _overwrite, ask_continue, show_log_if_one, nb_jobs, simulations = get_sim_settings(run_config_settings_filename)

  if simulations is None:
    printc.error('The "simulations" section of "' + run_config_settings_filename + '" is empty.', script_name)
    printc.note('You must define your simulations in "' + run_config_settings_filename + '" before using this command.', script_name)
    printc.note("Check out examples Odatix's documentation for more information.", script_name)
    sys.exit(-1)

  if overwrite:
    overwrite = True
  else:
    overwrite = _overwrite
  
  if noask:
    ask_continue = False

  ParallelJob.set_patterns(sim_status_pattern)

  sim_handler = SimulationHandler(
    work_path = work_path,
    arch_path = arch_path,
    sim_path = sim_path,
    work_script_path = work_script_path,
    log_path = log_path,
    overwrite = overwrite,
    param_settings_filename = param_settings_filename,
    sim_settings_filename = sim_settings_filename,
    sim_makefile_filename = sim_makefile_filename
  )

  if simulations is None:
    printc.note("No simulation selected. Exiting.", script_name)
    sys.exit(-1)
    
  try:
    simulation_instances = sim_handler.get_simulations(simulations)
  except Exception as e:
    printc.error("Could not get list \"simulations\" from \"" + run_config_settings_filename + "\".", script_name=script_name)
    printc.note("Is the YAML file valid? Are you missing a ':'? Is the indentation correct?", script_name=script_name)
    printc.cyan("error details: ", end="", script_name=script_name)
    print(str(e))
    sys.exit(-1)

  # print checklist summary
  sim_handler.print_summary()

  # ask to quit or continue
  if sim_handler.get_valid_sim_count() > 0:
    if ask_continue:
      print()
      ask_to_continue()
  else:
    sys.exit(-1)

  print()

  job_list = []

  def prepare_job(sim_instance):
    
    if True:
      # create directory
      create_dir(sim_instance.tmp_dir)

      # copy simulation sources
      copytree(sim_instance.source_sim_dir, sim_instance.tmp_dir, dirs_exist_ok = True)
     
      # copy design 
      if sim_instance.architecture.design_path != -1:
        try:
          copytree(sim_instance.architecture.design_path, sim_instance.tmp_dir, dirs_exist_ok = True)
        except:
          printc.error("Could not copy \"" + sim_instance.architecture.design_path + "\" into work directory \"" + sim_instance.tmp_dir + "\"", script_name)
          printc.note("make sure there are no file or folder named identically in the two directories", script_name)
          return

      # copy rtl (if exists) 
      if not sim_instance.architecture.generate_rtl:
        copytree(sim_instance.architecture.rtl_path, sim_instance.tmp_dir + '/' + 'rtl', dirs_exist_ok = True)

      # replace parameters
      if sim_instance.architecture.use_parameters:
        #printc.subheader("Replace parameters")
        param_target_file = sim_instance.tmp_dir + '/' + sim_instance.architecture.param_target_filename
        param_filename = arch_path + '/' + sim_instance.architecture.arch_name + '.txt'
        replace_params(
          base_text_file=param_target_file, 
          replacement_text_file=param_filename, 
          output_file=param_target_file, 
          start_delimiter=sim_instance.architecture.start_delimiter, 
          stop_delimiter=sim_instance.architecture.stop_delimiter, 
          replace_all_occurrences=False,
          silent=True
        )
        #print()

      # replace parameters again (override)
      if sim_instance.override_parameters:
        #printc.subheader("Replace parameters")
        param_target_file = sim_instance.tmp_dir + '/' + sim_instance.override_param_target_filename
        param_file = sim_instance.tmp_dir + '/' + sim_instance.override_param_filename
        replace_params(
          base_text_file=param_target_file, 
          replacement_text_file=param_file, 
          output_file=param_target_file, 
          start_delimiter=sim_instance.override_start_delimiter, 
          stop_delimiter=sim_instance.override_stop_delimiter, 
          replace_all_occurrences=False,
          silent=True
        )

      # run simulation command
      command = (
        "make {}".format(sim_rule)
        + ' RTL_DIR="{}"'.format(rtl_path)
        + ' ODATIX_DIR="{}"'.format(OdatixSettings.odatix_path)
        + ' LOG_DIR="{}"'.format(os.path.realpath(os.path.join(sim_instance.tmp_dir, log_path)))
        + ' CLOCK_SIGNAL="{}"'.format(sim_instance.architecture.clock_signal)
        + ' TOP_LEVEL_MODULE="{}"'.format(sim_instance.architecture.top_level_module)
        + " --no-print-directory"
      )

      sim_progress_file = os.path.join(sim_instance.tmp_dir, log_path, sim_progress_filename)

      running_sim = ParallelJob(
        process=None,
        command=command,
        directory=sim_instance.tmp_dir,
        generate_rtl=sim_instance.architecture.generate_rtl,
        generate_command=sim_instance.architecture.generate_command,
        target="",
        arch="",
        display_name=sim_instance.sim_display_name,
        status_file="",
        progress_file=sim_progress_file,
        tmp_dir=sim_instance.tmp_dir,
        status="idle",
      )

      job_list.append(running_sim)

  for sim_instance in simulation_instances:
    prepare_job(sim_instance)

  parallel_jobs = ParallelJobHandler(
    job_list=job_list,
    nb_jobs=nb_jobs,
    process_group=True,
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
    run_config_settings_filename  = args.input
  else:
    run_config_settings_filename = settings.simulation_settings_file

  if args.archpath is not None:
    arch_path = args.archpath
  else:
    arch_path = settings.arch_path

  if args.simpath is not None:
    sim_path = args.simpath
  else:
    sim_path = settings.sim_path

  if args.work is not None:
    work_path = args.work
  else:
    work_path = settings.sim_work_path

  overwrite = args.overwrite
  noask = args.noask

  run_simulations(run_config_settings_filename, arch_path, sim_path, work_path, overwrite, noask)

if __name__ == "__main__":
  args = parse_arguments()
  main(args)

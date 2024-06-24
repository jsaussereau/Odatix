#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
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
import re
import sys
import yaml
import argparse

# add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, 'lib')
sys.path.append(lib_path)

import printc
from replace_params import replace_params

from architecture_handler import ArchitectureHandler
from utils import *
from prepare_work import *
from run_parallel import *
from run_settings import *

######################################
# Settings
######################################

work_path = "work"
script_path = "eda_tools"
work_script_path = "scripts"
common_script_path = "_common"
log_path = "log"
arch_path = "architectures"

nb_jobs = 4

param_settings_filename = "_settings.yml"
arch_filename = "architecture.txt"
target_filename = "target.txt"
config_filename = "settings.tcl"
fmax_status_filename = "status.log"
synth_status_filename = "synth_status.log"
frequency_search_filename = "frequency_search.log"
tool_makefile_filename = "makefile.mk"
constraint_file = "constraints.txt"
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

script_name = os.path.basename(__file__)


######################################
# Misc functions
######################################

def parse_arguments():
  parser = argparse.ArgumentParser(description='Run fmax synthesis on selected architectures')
  parser.add_argument('-i', '--input', default='_run_fmax_synthesis_settings.yml',
                      help='input settings file (default: _run_fmax_synthesis_settings.yml)')
  parser.add_argument('-t', '--tool', default='vivado',
                      help='eda tool in use (default: vivado)')
  parser.add_argument('-w', '--overwrite', action='store_true',
                      help='overwrite existing results')
  parser.add_argument('-y', '--noask', action='store_true',
                      help='do not ask to continue')
  return parser.parse_args()


######################################
# Main
######################################

if __name__ == "__main__":

  args = parse_arguments()
  
  tool = args.tool
  work_path += "/" + tool 

  run_config_settings_filename = args.input
  overwrite, ask_continue, show_log_if_one, nb_jobs, architectures = get_synth_settings(run_config_settings_filename)

  eda_target_filename = "target_" + tool + ".yml"

  if not os.path.isfile(eda_target_filename):
    printc.error("Target file \"" + eda_target_filename + "\", for the selected eda tool \"" + tool + "\" does not exist", script_name)
    sys.exit(-1)

  # try launching eda tool 
  check_tool(tool, script_path, makefile=tool_makefile_filename, rule=test_tool_rule)

  with open(eda_target_filename, 'r') as f:
    settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    # mandatory keys
    try:
      targets            = read_from_list("targets", settings_data, eda_target_filename, script_name=script_name)
      constraint_file    = read_from_list("constraint_file", settings_data, eda_target_filename, script_name=script_name)
    except:
      sys.exit(-1) # if a key is missing
      
    # optional keys
    try:
      target_settings    = read_from_list("target_settings", settings_data, eda_target_filename, optional=True, script_name=script_name)
    except:
      target_settings    = {}
      print()
      pass # if a key is missing

  if args.overwrite:
    overwrite = True
  
  if args.noask:
    ask_continue = False

  Running_arch.set_patterns(fmax_status_pattern, synth_status_pattern)

  arch_handler = ArchitectureHandler(
    work_path = work_path,
    arch_path = arch_path,
    script_path = script_path,
    work_script_path = work_script_path,
    log_path = log_path,
    eda_target_filename = eda_target_filename,
    fmax_status_filename = fmax_status_filename,
    frequency_search_filename = frequency_search_filename,
    param_settings_filename = param_settings_filename,
    valid_status = valid_status,
    valid_frequency_search = valid_frequency_search,
    default_fmax_lower_bound = default_fmax_lower_bound,
    default_fmax_upper_bound = default_fmax_upper_bound,
    target_settings = target_settings,
    overwrite = overwrite
  )

  architecture_instances = arch_handler.get_architectures(architectures, targets)

  # print checklist summary
  arch_handler.print_summary()

  # split architecture in chunks, depending on the number of jobs
  architecture_instances_chunks, nb_chunks = arch_handler.get_chuncks(nb_jobs)

  # ask to quit or continue
  if arch_handler.get_valid_arch_count() > 0:
    if ask_continue:
      print()
      ask_to_continue()
  else:
    sys.exit(-1)
  
  print()

  for i_chunk in range(nb_chunks):
    running_arch_list = []
    active_running_arch_list = []
    
    if nb_chunks == 1:
      architecture_instances_chunk = architecture_instances
    else:
      architecture_instances_chunk = architecture_instances_chunks[i_chunk]

    #print("valid_architectures : {}".format(valid_architectures))
    for i_arch in architecture_instances_chunk:

      # get param dir (arch name before '/')
      arch_param_dir = re.sub('/.*', '', i_arch.arch_name)

      # create directory
      create_dir(i_arch.tmp_dir)

      # copy scripts
      try:
        copytree(script_path + '/' + common_script_path, i_arch.tmp_script_path)
      except: 
        printc.error("\"" + i_arch.tmp_script_path + "\" exists while it should not" , script_name)

      copytree(script_path + '/' + tool + '/tcl', i_arch.tmp_script_path, dirs_exist_ok = True)

      # copy design 
      if i_arch.design_path != -1:
        copytree(i_arch.design_path, i_arch.tmp_dir, dirs_exist_ok = True)

      # copy rtl (if exists) 
      if not i_arch.generate_rtl:
        copytree(i_arch.rtl_path, i_arch.tmp_dir + '/' + 'rtl', dirs_exist_ok = True)

      # replace parameters
      if i_arch.use_parameters:
        #printc.subheader("Replace parameters")
        param_target_file = i_arch.tmp_dir + '/' + i_arch.param_target_filename
        param_filename = arch_path + '/' + i_arch.arch_name + '.txt'
        replace_params(
          base_text_file=param_target_file, 
          replacement_text_file=param_filename, 
          output_file=param_target_file, 
          start_delimiter=i_arch.start_delimiter, 
          stop_delimiter=i_arch.stop_delimiter, 
          replace_all_occurrences=False,
          silent=True
        )
        #print()

      # run generate command
      if i_arch.generate_rtl:
        try:
          print()
          printc.subheader("Run generate command for " + i_arch.arch_display_name)
          printc.bold(" > " + i_arch.generate_command)
          result = subprocess.run([i_arch.generate_command], cwd=i_arch.tmp_dir, shell=True, check=True, text=True)
        except subprocess.CalledProcessError as e:
          print()
          printc.error("rtl generation failed", script_name)
          printc.note("look for earlier error to solve this issue", script_name)
          print()
          continue

      # create target and architecture files
      f = open(i_arch.tmp_dir + '/' + target_filename, 'w')
      print(i_arch.target, file = f)
      f.close()
      f = open(i_arch.tmp_dir + '/' + arch_filename, 'w')
      print(i_arch.arch_name, file = f)
      f.close()

      # set source and dest to null if copy is disabled
      try:
        if not i_arch.file_copy_enable:
          raise
        if not os.path.exists(i_arch.file_copy_source):
          printc.note("the file \"" + i_arch.file_copy_source + "\"specified in \"" + settings_filename + "\" does not exist. File copy disabled.", script_name)
          raise
        i_arch.file_copy_enable = "true"
      except:
        i_arch.file_copy_enable = "false"
        i_arch.file_copy_source = "/dev/null"
        i_arch.file_copy_dest = "/dev/null"
      
      if i_arch.script_copy_enable:
        i_arch.script_copy_enable = "true"
      else: 
        i_arch.script_copy_enable = "false"

      # edit config script
      config_file = i_arch.tmp_script_path + '/' + config_filename 
      edit_config_file(i_arch, config_file, constraint_file)

      # link all scripts to config script
      for filename in os.listdir(i_arch.tmp_script_path):
        if filename.endswith('.tcl'):
          with open(i_arch.tmp_script_path + '/' + filename, 'r') as f:
            tcl_content = f.read()
          pattern = re.escape(source_tcl) + r"(.+?\.tcl)"
          def replace_path(match):
              return "source " + i_arch.tmp_script_path + "/" + match.group(1)
          tcl_content = re.sub(pattern, replace_path, tcl_content)
          with open(i_arch.tmp_script_path + '/' + filename, 'w') as f:
            f.write(tcl_content)

      # run binary search script
      tool_makefile_file = script_path + "/" + tool + "/" + tool_makefile_filename
      process = run_parallel(
        command = "make -f " + tool_makefile_file + " " + synth_fmax_rule + " WORK_DIR=\"" + i_arch.tmp_dir + "\" SCRIPT_DIR=\"" + i_arch.tmp_dir + '/' + work_script_path + "\" LOG_DIR=\"" + i_arch.tmp_dir + '/' + log_path + "\" --no-print-directory",
        nb_process = len(architecture_instances_chunk),
        show_log_if_one = show_log_if_one
      )

      fmax_status_file = i_arch.tmp_dir + '/' + log_path + '/' + fmax_status_filename
      synth_status_file = i_arch.tmp_dir + '/' + log_path + '/' + synth_status_filename

      running_arch_list.append(
        Running_arch(
          process=process,
          target=i_arch.target,
          arch=i_arch.arch_name,
          display_name=i_arch.arch_display_name,
          status_file=fmax_status_file,
          progress_file=synth_status_file,
          tmp_dir=i_arch.tmp_dir
        )
      )
      printc.say("started job for architecture \"{}\" between {} and {} MHz with pid {}".format(i_arch.arch_name, i_arch.fmax_lower_bound, i_arch.fmax_upper_bound, process.pid), script_name)

    show_progress(running_arch_list, refresh_time, show_log_if_one, mode="synthesis")

    # summary
    print()
    for running_arch in running_arch_list:
      tmp_dir = work_path + '/' + running_arch.target + '/' + running_arch.arch
      frequency_search_file = tmp_dir + '/' + log_path + '/' + frequency_search_filename
      try:
        with open(frequency_search_file, 'r') as file:
          lines = file.readlines()
          if len(lines) >= 1:
            summary_line = lines[-1]
            print(running_arch.display_name + ": " + summary_line, end='')
      except:
      #  print(f"frequency_search_file '{frequency_search_file}' does not exist")
        pass
    print()
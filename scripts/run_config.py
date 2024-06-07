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
import math
import time
import copy
import yaml
import argparse
import subprocess

from os.path import isfile
from os.path import isdir
from os import makedirs
from os import listdir

import shutil
from shutil import rmtree

# Add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, 'lib')
sys.path.append(lib_path)

import printc
import replace_params as rp
import architecture_handler as ah
import utils
from utils import *


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

tcl_bool_true = ['true', 'yes', 'on', '1']
tcl_bool_false = ['false', 'no', 'off', '0']

script_name = os.path.basename(__file__)


######################################
# Misc functions
######################################

def parse_arguments():
  parser = argparse.ArgumentParser(description='Run fmax synthesis on selected architectures')
  parser.add_argument('-i', '--input', default='architecture_select.yml',
                      help='input architecture file (default: architecture_select.yml)')
  #parser.add_argument('-m', '--mode', choices=['fpga', 'asic'], default='fpga',
  #                    help='Select the mode (fpga or asic, default: fpga)')
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

  #if args.mode != 'fpga' and args.mode != 'asic' :
  #  raise ValueError("Invalid mode selected. Please choose 'fpga' or 'asic'.")
  
  tool = args.tool
  work_path += "/" + tool 

  run_config_settings_filename = args.input

  eda_target_filename = "target_" + tool + ".yml"

  # Get settings from yaml file
  if not isfile(run_config_settings_filename):
    printc.error("Settings file \"" + run_config_settings_filename + "\" does not exist", script_name)
    sys.exit()

  with open(run_config_settings_filename, 'r') as f:
    settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    try:
      overwrite       = read_from_list("overwrite", settings_data, run_config_settings_filename)
      ask_continue    = read_from_list("ask_continue", settings_data, run_config_settings_filename)
      show_log_if_one = read_from_list("show_log_if_one", settings_data, run_config_settings_filename)
      use_screen      = read_from_list("use_screen", settings_data, run_config_settings_filename)
      nb_jobs         = read_from_list("nb_jobs", settings_data, run_config_settings_filename)
      architectures   = read_from_list("architectures", settings_data, run_config_settings_filename)
    except:
      sys.exit() # if a key is missing

  if not isfile(eda_target_filename):
    printc.error("Target file \"" + eda_target_filename + "\", for the selected eda tool \"" + tool + "\" does not exist", script_name)
    sys.exit()

  # Try launching eda tool 
  print("checking the selected eda tool \"" + tool + "\" ..", end='')
  sys.stdout.flush()
  test_process = subprocess.Popen(["make", "-f", script_path + "/" + tool + "/" + tool_makefile_filename, test_tool_rule, "--no-print-directory"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
  while test_process.poll() is None:
    print('.', end='', flush=True)
    time.sleep(0.5)
  if test_process.returncode == 0:
      printc.green(" success!")
  else:
    printc.red(" failed!")
    printc.error("Could not launch eda tool \"" + tool + "\"", script_name)
    printc.note("did you add the tool path to your PATH environment variable?", script_name)
    printc.note("example -> PATH=$PATH:/opt/xilinx/2022/Vivado/2022.2/bin", script_name)
    sys.exit()
  print()

  with open(eda_target_filename, 'r') as f:
    settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    # mandatory keys
    try:
      targets            = read_from_list("targets", settings_data, eda_target_filename)
      constraint_file    = read_from_list("constraint_file", settings_data, eda_target_filename)
    except:
      sys.exit() # if a key is missing
      
    # optional keys
    try:
      target_settings    = read_from_list("target_settings", settings_data, eda_target_filename, optional=True)
    except:
      target_settings    = {}
      print()
      pass # if a key is missing

  if args.overwrite:
    overwrite = True
  
  if args.noask:
    ask_continue = False

  arch_handler = ah.ArchitectureHandler(
    work_path = work_path,
    arch_path = arch_path,
    script_path = script_path,
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
  if ask_continue and arch_handler.get_valid_arch_count() > 0:
    print()
    ask_to_continue()
  
  print()

  for i_chunk in range(nb_chunks):
    running_arch_list = []
    active_running_arch_list = []
    
    if nb_chunks == 1:
      architecture_instances_chunk = architecture_instances
    else:
      architecture_instances_chunk = architecture_instances_chunks[i_chunk]

    #print("valid_architectures : {}".format(valid_architectures))
    for arch_instance in architecture_instances_chunk:
      target = arch_instance.target
      arch = arch_instance.arch_name
      arch_display_name = arch_instance.arch_display_name
      rtl_path = arch_instance.rtl_path
      design_path = arch_instance.design_path
      top_level_filename = arch_instance.top_level_filename
      top_level_module = arch_instance.top_level_module
      clock_signal = arch_instance.clock_signal
      reset_signal = arch_instance.reset_signal
      file_copy_enable = arch_instance.file_copy_enable
      file_copy_source = arch_instance.file_copy_source
      file_copy_dest = arch_instance.file_copy_dest
      fmax_lower_bound = arch_instance.fmax_lower_bound
      fmax_upper_bound = arch_instance.fmax_upper_bound
      script_copy_enable = arch_instance.script_copy_enable
      script_copy_source = arch_instance.script_copy_source
      use_parameters = arch_instance.use_parameters
      start_delimiter = arch_instance.start_delimiter
      stop_delimiter = arch_instance.stop_delimiter
      generate_rtl = arch_instance.generate_rtl
      generate_command = arch_instance.generate_command
      param_target_filename = arch_instance.param_target_filename
        
      tmp_dir = work_path + '/' + target + '/' + arch

      # get param dir (arch name before '/')
      arch_param_dir = re.sub('/.*', '', arch)
    
      use_parameters = use_parameters.lower()
      if not use_parameters in tcl_bool_true:
        use_parameters = "false"

      # create directory
      if isdir(tmp_dir):
        rmtree(tmp_dir)
      makedirs(tmp_dir)

      # copy scripts
      tmp_script_path = tmp_dir + '/' + work_script_path
      copytree(script_path + '/' + common_script_path, tmp_script_path)
      copytree(script_path + '/' + tool + '/tcl', tmp_script_path, dirs_exist_ok = True)

      # copy design 
      if design_path != -1:
        copytree(design_path, tmp_dir, dirs_exist_ok = True)

      # copy rtl (if exists) 
      if not generate_rtl in tcl_bool_true:
        copytree(rtl_path, tmp_dir + '/' + 'rtl', dirs_exist_ok = True)

      # replace parameters
      if use_parameters in tcl_bool_true:
        #printc.subheader("Replace parameters")
        param_target_file = tmp_dir + '/' + param_target_filename
        param_filename = arch_path + '/' + arch + '.txt'
        rp.replace_params(
          base_text_file=param_target_file, 
          replacement_text_file=param_filename, 
          output_file=param_target_file, 
          start_delimiter=start_delimiter, 
          stop_delimiter=stop_delimiter, 
          replace_all_occurrences=False,
          silent=True
        )
        #print()

      # run generate command
      if generate_rtl in tcl_bool_true:
        try:
          print()
          printc.subheader("Run generate command for " + arch_display_name)
          printc.bold(" > " + generate_command)
          result = subprocess.run([generate_command], cwd=tmp_dir, shell=True, check=True, text=True)
        except subprocess.CalledProcessError as e:
          print()
          printc.error("rtl generation failed", script_name)
          printc.note("look for earlier error to solve this issue", script_name)
          print()
          continue

      # create target and architecture files
      f = open(tmp_dir + '/' + target_filename, 'w')
      print(target, file = f)
      f.close()
      f = open(tmp_dir + '/' + arch_filename, 'w')
      print(arch, file = f)
      f.close()

      # set source and dest to null if copy is disabled
      file_copy_enable = file_copy_enable.lower()
      try:
        if not file_copy_enable in tcl_bool_true:
          raise
        if not os.path.exists(file_copy_source):
          printc.note("the file \"" + file_copy_source + "\"specified in \"" + settings_filename + "\" does not exist. File copy disabled.", script_name)
          raise
      except:
        file_copy_enable = "false"
        file_copy_source = "/dev/null"
        file_copy_dest = "/dev/null"

      # edit config script
      config_file = tmp_script_path + '/' + config_filename
      with open(config_file, 'r') as f:
        cf_content = f.read()

      # lib name
      lib_name = "DC_WORK_" + target + "_" + arch.replace("/", "_")

      cf_content = re.sub("(set script_path.*)",        "set script_path        " + tmp_script_path, cf_content)
      cf_content = re.sub("(set tmp_path.*)",           "set tmp_path           " + tmp_dir, cf_content)
      cf_content = re.sub("(set rtl_path.*)",           "set rtl_path           " + rtl_path, cf_content)
      cf_content = re.sub("(set arch_path.*)",          "set arch_path          " + arch_path, cf_content)
      cf_content = re.sub("(set clock_signal.*)",       "set clock_signal       " + clock_signal, cf_content)
      cf_content = re.sub("(set reset_signal.*)",       "set reset_signal       " + reset_signal, cf_content)
      cf_content = re.sub("(set top_level_module.*)",   "set top_level_module   " + top_level_module, cf_content)
      cf_content = re.sub("(set top_level_file.*)",     "set top_level_file     " + top_level_filename, cf_content)
      cf_content = re.sub("(set file_copy_enable.*)",   "set file_copy_enable   " + file_copy_enable, cf_content)
      cf_content = re.sub("(set file_copy_source.*)",   "set file_copy_source   " + file_copy_source, cf_content)
      cf_content = re.sub("(set file_copy_dest.*)",     "set file_copy_dest     " + file_copy_dest, cf_content)
      cf_content = re.sub("(set fmax_lower_bound.*)",   "set fmax_lower_bound   " + fmax_lower_bound, cf_content)
      cf_content = re.sub("(set fmax_upper_bound.*)",   "set fmax_upper_bound   " + fmax_upper_bound, cf_content)
      cf_content = re.sub("(set script_copy_enable.*)", "set script_copy_enable " + script_copy_enable, cf_content)
      cf_content = re.sub("(set script_copy_source.*)", "set script_copy_source " + script_copy_source, cf_content)
      cf_content = re.sub("(set lib_name.*)",           "set lib_name           " + lib_name, cf_content)
      cf_content = re.sub("(set constraints_file.*)",   "set constraints_file   $tmp_path/" + constraint_file, cf_content)

      with open(config_file, 'w') as f:
        f.write(cf_content)

      # link all scripts to config script
      for filename in listdir(tmp_script_path):
        if filename.endswith('.tcl'):
          with open(tmp_script_path + '/' + filename, 'r') as f:
            tcl_content = f.read()
          pattern = re.escape(source_tcl) + r"(.+?\.tcl)"
          def replace_path(match):
              return "source " + tmp_script_path + "/" + match.group(1)
          tcl_content = re.sub(pattern, replace_path, tcl_content)
          with open(tmp_script_path + '/' + filename, 'w') as f:
            f.write(tcl_content)

      # run binary search script
      if len(architecture_instances_chunk) == 1 and show_log_if_one:
        #process = subprocess.run(["make", "-f", script_path + "/" + tool + "/" + tool_makefile_filename, synth_fmax_rule, "SCRIPT_DIR=\"" + tmp_dir + '/' + work_script_path + "\"", "LOG_DIR=\"" + tmp_dir + '/' + log_path + "\"", "--no-print-directory"])
        process = subprocess.Popen(["make", "-f", script_path + "/" + tool + "/" + tool_makefile_filename, synth_fmax_rule, "WORK_DIR=\"" + tmp_dir + "\"", "SCRIPT_DIR=\"" + tmp_dir + '/' + work_script_path + "\"", "LOG_DIR=\"" + tmp_dir + '/' + log_path + "\"", "--no-print-directory"])
      else:
        process = subprocess.Popen(["make", "-f", script_path + "/" + tool + "/" + tool_makefile_filename, synth_fmax_rule, "WORK_DIR=\"" + tmp_dir + "\"", "SCRIPT_DIR=\"" + tmp_dir + '/' + work_script_path + "\"", "LOG_DIR=\"" + tmp_dir + '/' + log_path + "\"", "--no-print-directory"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

      running_arch_list.append(ah.Running_arch(process, target, arch, arch_display_name))
      printc.say("started job for architecture \"{}\" between {} and {} MHz with pid {}".format(arch, fmax_lower_bound, fmax_upper_bound, process.pid), script_name)

    # prepare output
    print()
    for running_arch in running_arch_list:
      print() 

    active_running_arch_list = copy.copy(running_arch_list)

    # wait for all processes to finish
    while len(active_running_arch_list) > 0:
      if not(len(running_arch_list) == 1 and show_log_if_one):
        # go back to first line
        for running_arch in running_arch_list:
          move_cursor_up()

      max_title_length = max(len(running_arch.display_name) for running_arch in running_arch_list)

      for running_arch in running_arch_list:

        # get status files full paths
        tmp_dir = work_path + '/' + running_arch.target + '/' + running_arch.arch
        fmax_status_file = tmp_dir + '/' + log_path + '/' + fmax_status_filename
        synth_status_file = tmp_dir + '/' + log_path + '/' + synth_status_filename

        # get progress from fmax status file
        fmax_progress = 0
        fmax_step = 1
        fmax_totalstep = 1
        if isfile(fmax_status_file):
          with open(fmax_status_file, 'r') as f:
            content = f.read()
          for match in re.finditer(fmax_status_pattern, content):
            parts = fmax_status_pattern.search(match.group())
            if len(parts.groups()) >= 4:
              fmax_progress = int(parts.group(2))
              fmax_step = int(parts.group(3))
              fmax_totalstep = int(parts.group(4))
        
        # get progress from synth status file
        synth_progress = 0
        if isfile(synth_status_file):
          with open(synth_status_file, 'r') as f:
            content = f.read()
          for match in re.finditer(synth_status_pattern, content):
            parts = synth_status_pattern.search(match.group())
            if len(parts.groups()) >= 2:
              synth_progress = int(parts.group(2))

        # compute progress
        if fmax_totalstep != 0:
          progress = fmax_progress + synth_progress / fmax_totalstep
        else:
          progress = synth_progress
          
        # check if process has finished and print progress 
        if running_arch.process.poll() != None:
          try: 
            active_running_arch_list.remove(running_arch)
          except:
            pass

          if running_arch.process.returncode == 0:
              comment = " (" + printc.colors.GREEN + "done" + printc.colors.ENDC + ")"
          else:
              comment = " (" + printc.colors.RED + "terminated with errors" + printc.colors.ENDC + ")"
          progress_bar(progress, title=running_arch.display_name, title_size=max_title_length, endstr=comment)
        else: 
          progress_bar(progress, title=running_arch.display_name, title_size=max_title_length)

      time.sleep(refresh_time)

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
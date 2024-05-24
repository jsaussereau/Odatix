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
import time
import copy
import yaml
import argparse
import subprocess
import replace_params as rp

from yaml.loader import SafeLoader

from os.path import isfile
from os.path import isdir
from os import makedirs
from os import listdir

import shutil
from shutil import rmtree

######################################
# Settings
######################################

work_path = "work"
script_path = "eda_tools"
work_script_path = "scripts"
common_script_path = "_common"
log_path = "log"
arch_path = "architectures"

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

######################################
# Misc classes
######################################

class Running_arch:
  def __init__(self, process, arch):
    self.process = process
    self.arch = arch

class bcolors:
  HEADER = '\033[95m'
  OKBLUE = '\033[94m'
  OKCYAN = '\033[96m'
  OKGREEN = '\033[92m'
  WARNING = '\033[93m'
  FAIL = '\033[91m'
  GREY = '\033[30m'
  ENDC = '\033[0m'
  BOLD = '\033[1m'
  UNDERLINE = '\033[4m'


######################################
# Misc functions
######################################

def script_name():
  return bcolors.GREY + "[run_config.py]" + bcolors.ENDC + " "

# python 3.8+ like copytree
def copytree(src, dst, dirs_exist_ok=False, **kwargs):
  if not os.path.exists(dst):
    shutil.copytree(src, dst, **kwargs)
  else:
    if dirs_exist_ok:
      for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
          shutil.copytree(s, d, **kwargs)
        else:
          shutil.copy2(s, d)
    else:
      raise

def read_from_list(key, input_list, filename, raise_if_missing=True, optionnal=False, print_error=True, parent=None):
  if key in input_list:
    return input_list[key]
  else:
    parent_string = "" if parent == None else ", inside list \"" + parent + "\","
    if print_error:
      if optionnal:
        print(bcolors.OKCYAN + "note: Cannot find optionnal key \"" + key + "\"" + parent_string + " in \"" + filename + "\". Using default values instead." + bcolors.ENDC)
      else:
        print(bcolors.BOLD + bcolors.FAIL + "error: Cannot find key \"" + key + "\"" + parent_string + " in \"" + filename + "\"." + bcolors.ENDC)
    if raise_if_missing:
      raise
    return False

def read_from_config(identifier, config, filename):
  if identifier in config[settings_ini_section]:
    return config[settings_ini_section][identifier]
  else:
    print(bcolors.BOLD + bcolors.FAIL + "error: Cannot find identifier \"" + identifier + "\" in \"" + filename + "\"." + bcolors.ENDC)
    raise
    return False

def print_arch_list(arch_list, description, color):
  if not len(arch_list) > 0:
    return

  print()
  print(bcolors.BOLD + description + ":" + bcolors.ENDC)
  print(color, end = '')
  for arch in arch_list:
    print("  - " + arch)
  print(bcolors.ENDC, end = '')

def move_cursor_up():
  sys.stdout.write('\x1b[1A') # Move cursor up
  sys.stdout.write("\033[K") # Clear to the end of line
  sys.stdout.flush()

def progress_bar(progress, title, title_size=50, endstr=''):
  if progress > 100:
    progress = 100
  
  limit = int(progress * progress_bar_size / 100)
  padded_title = title.ljust(title_size)

  print(padded_title + " [", end = '')
  for i in range(0, limit):
    print('#', end = '')
  for i in range(limit, progress_bar_size):
    print(' ', end = '')
  print("] {}%".format(int(progress)) + endstr)

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
    print(bcolors.BOLD + bcolors.FAIL + "error: Settings file \"" + run_config_settings_filename + "\" does not exist" + bcolors.ENDC)
    sys.exit()

  with open(run_config_settings_filename, 'r') as f:
    settings_data = yaml.load(f, Loader=SafeLoader)
    try:
      overwrite       = read_from_list("overwrite", settings_data, run_config_settings_filename)
      ask_continue    = read_from_list("ask_continue", settings_data, run_config_settings_filename)
      show_log_if_one = read_from_list("show_log_if_one", settings_data, run_config_settings_filename)
      use_screen      = read_from_list("use_screen", settings_data, run_config_settings_filename)
      architectures   = read_from_list("architectures", settings_data, run_config_settings_filename)
    except:
      sys.exit() # if a key is missing

  if not isfile(eda_target_filename):
    print(bcolors.BOLD + bcolors.FAIL + "error: Target file \"" + eda_target_filename + "\", for the selected eda tool \"" + tool + "\" does not exist" + bcolors.ENDC)
    sys.exit()

  # Try launching eda tool 
  print("checking the selected eda tool \"" + tool + "\" ..", end='')
  sys.stdout.flush()
  test_process = subprocess.Popen(["make", "-f", script_path + "/" + tool + "/" + tool_makefile_filename, test_tool_rule, "--no-print-directory"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
  while test_process.poll() is None:
    print('.', end='', flush=True)
    time.sleep(0.5)
  if test_process.returncode == 0:
      print(bcolors.OKGREEN + " success!" + bcolors.ENDC)
  else:
    print(bcolors.FAIL + " failed!" + bcolors.ENDC)
    print(bcolors.BOLD + bcolors.FAIL + "error: Could not launch eda tool \"" + tool + "\"" + bcolors.ENDC)
    print(bcolors.OKCYAN + "note: did you add the tool path to your PATH environment variable?" + bcolors.ENDC)
    print(bcolors.OKCYAN + "note: example -> PATH=$PATH:/opt/xilinx/2022/Vivado/2022.2/bin" + bcolors.ENDC)
    sys.exit()
  print()

  with open(eda_target_filename, 'r') as f:
    settings_data = yaml.load(f, Loader=SafeLoader)
    # mandatory keys
    try:
      targets            = read_from_list("targets", settings_data, eda_target_filename)
      constraint_file    = read_from_list("constraint_file", settings_data, eda_target_filename)
    except:
      sys.exit() # if a key is missing
      
    # optionnal keys
    try:
      target_settings    = read_from_list("target_settings", settings_data, eda_target_filename, optionnal=True)
    except:
      target_settings    = {}
      print()
      pass # if a key is missing

  if args.overwrite:
    overwrite = True
  
  if args.noask:
    ask_continue = False

  for target in targets:

    print(bcolors.BOLD + bcolors.OKCYAN, end='')
    print("######################################")
    print(" Target: {}".format(target))
    print("######################################")
    print(bcolors.ENDC)
    
    try:
      if target_settings == {}:
        raise
      this_target_settings = read_from_list(target, target_settings, eda_target_filename, optionnal=True, parent="target_settings")
      script_copy_enable = read_from_list('script_copy_enable', this_target_settings, eda_target_filename, optionnal=True, parent="target_settings/" + target)
      script_copy_source = read_from_list('script_copy_source', this_target_settings, eda_target_filename, optionnal=True, parent="target_settings/" + target)
      if not script_copy_enable in tcl_bool_true:
        raise
      if not os.path.exists(script_copy_source):
        print(bcolors.OKCYAN + "note: the script source file \"" + script_copy_source + "\"specified in \"" + eda_target_filename + "\" does not exist. Script copy disabled." + bcolors.ENDC)
        raise
    except:
      script_copy_enable = "false"
      script_copy_source = "/dev/null"

    banned_arch_param = []
    valid_archs = []
    cached_archs = []
    overwrite_archs = []
    error_archs = []
    incomplete_archs = []
    new_archs = []

    for arch in architectures:
      tmp_dir = work_path + '/' + target + '/' + arch
      fmax_status_file = tmp_dir + '/' + log_path + '/' + fmax_status_filename
      frequency_search_file = tmp_dir + '/' + log_path + '/' + frequency_search_filename

      # get param dir (arch name before '/')
      arch_param_dir = re.sub('/.*', '', arch)

      # check if arch_param has been banned
      if arch_param_dir in banned_arch_param:
        error_archs.append(arch)
        continue

      # check if parameter dir exists
      arch_param = arch_path + '/' + arch_param_dir
      if not isdir(arch_param):
        print(bcolors.BOLD + bcolors.FAIL + "error: There is no directory \"" + arch_param_dir + "\" in directory \"" + arch_path + "\"" + bcolors.ENDC)
        error_archs.append(arch)
        continue
      
      # check if settings file exists
      if not isfile(arch_param + '/' + param_settings_filename):
        print(bcolors.BOLD + bcolors.FAIL + "error: There is no setting file \"" + param_settings_filename + "\" in directory \"" + arch_param + "\"" + bcolors.ENDC)
        banned_arch_param.append(arch_param_dir)
        error_archs.append(arch)
        continue

      # get settings variables
      settings_filename = arch_path + '/' + arch_param_dir + '/' + param_settings_filename
      with open(settings_filename, 'r') as f:
        settings_data = yaml.load(f, Loader=SafeLoader)
        try:
          rtl_path           = read_from_list('rtl_path', settings_data, settings_filename)
          top_level_filename = read_from_list('top_level_file', settings_data, settings_filename)
          top_level_module   = read_from_list('top_level_module', settings_data, settings_filename)
          clock_signal       = read_from_list('clock_signal', settings_data, settings_filename)
          reset_signal       = read_from_list('reset_signal', settings_data, settings_filename)
          file_copy_enable   = read_from_list('file_copy_enable', settings_data, settings_filename)
          file_copy_source   = read_from_list('file_copy_source', settings_data, settings_filename)
          file_copy_dest     = read_from_list('file_copy_dest', settings_data, settings_filename)
          use_parameters     = read_from_list('use_parameters', settings_data, settings_filename)
          start_delimiter    = read_from_list('start_delimiter', settings_data, settings_filename)
          stop_delimiter     = read_from_list('stop_delimiter', settings_data, settings_filename)
        except:
          banned_arch_param.append(arch_param_dir)
          error_archs.append(arch)
          continue # if an identifier is missing

        param_filename = arch + ".txt"
        use_parameters = use_parameters.lower()
        if use_parameters in use_parameters:
          # check if parameter file exists
          if not isfile(arch_path + '/' + param_filename):
            print(bcolors.BOLD + bcolors.FAIL + "error: There is no parameter file \"" + arch_path + param_filename + "\", while use_parameters=true" + bcolors.ENDC)
            banned_arch_param.append(arch_param_dir)
            error_archs.append(arch)
            continue

        try:
          design_path = read_from_list('design_path', settings_data, settings_filename, optionnal=True, print_error=False)
        except:
          design_path = rtl_path

        try:
          param_target_filename = read_from_list('param_target_file', settings_data, settings_filename, optionnal=True, print_error=False)
          # check if param target file path exists
          param_target_file = design_path + '/' + param_target_filename
          if not isfile(param_target_file): 
            print(bcolors.BOLD + bcolors.FAIL + "error: The parameter target file \"" + param_target_filename + "\" specified in \"" + settings_filename + "\" does not exist" + bcolors.ENDC)
            error_archs.append(arch)
            continue
        except:
          param_target_filename = top_level_filename

        try:
          generate_rtl = read_from_list('generate_rtl', settings_data, settings_filename, optionnal=True, print_error=False)
          if generate_rtl in tcl_bool_true:
            try:
              generate_command = read_from_list('generate_command', settings_data, settings_filename, print_error=False)
            except:
              print(bcolors.BOLD + bcolors.FAIL + "error: Cannot find key \"generate_command\" in \"" + settings_filename + "\" while generate_rtl=true" + bcolors.ENDC)
              banned_arch_param.append(arch_param_dir)
              error_archs.append(arch)
              continue
        except:
          generate_rtl = "false"

      # check if file_copy_enable is a boolean
      file_copy_enable = file_copy_enable.lower()
      if not (file_copy_enable in tcl_bool_true or file_copy_enable in tcl_bool_false):
        print(bcolors.BOLD + bcolors.FAIL + "error: Value for identifier \"file_copy_enable\" is not one of the boolean value supported by tcl (\"true\", \"false\", \"yes\", \"no\", \"on\", \"off\", \"1\", \"0\")" + bcolors.ENDC)
        error_archs.append(arch)
        continue

      # check if generate_rtl is a boolean
      generate_rtl = generate_rtl.lower()
      if not (generate_rtl in tcl_bool_true or generate_rtl in tcl_bool_false):
        print(bcolors.BOLD + bcolors.FAIL + "error: Value for identifier \"generate_rtl\" is not one of the boolean value supported by tcl (\"true\", \"false\", \"yes\", \"no\", \"on\", \"off\", \"1\", \"0\")" + bcolors.ENDC)
        error_archs.append(arch)
        continue

      if not generate_rtl in tcl_bool_true:
        # check if rtl path exists
        if not isdir(rtl_path):
          print(bcolors.BOLD + bcolors.FAIL + "error: The rtl path \"" + rtl_path + "\" specified in \"" + settings_filename + "\" does not exist" + bcolors.ENDC)
          error_archs.append(arch)
          continue

        # check if top level file path exists
        top_level = rtl_path + '/' + top_level_filename
        if not isfile(top_level):
          print(bcolors.BOLD + bcolors.FAIL + "error: The top level file \"" + top_level_filename + "\" specified in \"" + settings_filename + "\" does not exist" + bcolors.ENDC)
          error_archs.append(arch)
          continue

        # check if the top level module name exists in the top level file, at least
        f = open(top_level, "r")
        if not top_level_module in f.read():
          print(bcolors.BOLD + bcolors.FAIL + "error: There is no occurence of top level module name \"" + top_level_module + "\" in top level file \"" + top_level + "\"" + bcolors.ENDC)
          error_archs.append(arch)
          f.close()
          continue
        f.close()
        
        # check if the top clock name exists in the top level file, at least
        f = open(top_level, "r")
        if not clock_signal in f.read():
          print(bcolors.BOLD + bcolors.FAIL + "error: There is no occurence of clock signal name \"" + clock_signal + "\" in top level file \"" + top_level + "\"" + bcolors.ENDC)
          error_archs.append(arch)
          f.close()
          continue
        f.close()
        
        # check if the top reset name exists in the top level file, at least
        f = open(top_level, "r")
        if not clock_signal in f.read():
          print(bcolors.BOLD + bcolors.FAIL + "error: There is no occurence of reset signal name \"" + reset_signal + "\" in top level file \"" + top_level + "\"" + bcolors.ENDC)
          error_archs.append(arch)
          f.close()
          continue
        f.close()

      # check if param file exists
      if not isfile(arch_path + '/' + arch + '.txt'):
        print(bcolors.BOLD + bcolors.FAIL + "error: The parameter file \"" + arch + ".txt\" does not exist in directory \"" + arch_path + "/" + arch_param_dir + "\"" + bcolors.ENDC)
        error_archs.append(arch)
        continue

      # check file copy
      if file_copy_enable in tcl_bool_true:
        if not isfile(file_copy_source):
          print(bcolors.BOLD + bcolors.FAIL + "error: The source file to copy \"" + file_copy_source + "\" does not exist" + bcolors.ENDC)
          error_archs.append(arch)
          continue

      # check if the architecture is in cache and has a status file
      if isdir(tmp_dir) and isfile(fmax_status_file) and isfile(frequency_search_file):
        # check if the previous synth_fmax has completed
        sf = open(fmax_status_file, "r")
        if valid_status in sf.read():
          ff = open(frequency_search_file, "r")
          if valid_frequency_search in ff.read():
            if overwrite:
              print(bcolors.WARNING + "Found cached results for \"" + arch + "\" with target \"" + target + "\"." + bcolors.ENDC)
              overwrite_archs.append(arch)
            else:
              print(bcolors.OKCYAN + "Found cached results for \"" + arch + "\" with target \"" + target + "\". Skipping." + bcolors.ENDC)
              cached_archs.append(arch)
              continue
          else:
            print(bcolors.WARNING + "The previous synthesis for \"" + arch + "\" did not result in a valid maximum operating frequency." + bcolors.ENDC)
            overwrite_archs.append(arch)
          ff.close()
        else: 
          print(bcolors.WARNING + "The previous synthesis for \"" + arch + "\" has not finished or the directory has been corrupted." + bcolors.ENDC)
          incomplete_archs.append(arch)
        sf.close()
      else:
        new_archs.append(arch)

      # passed all check: added to the list
      valid_archs.append(arch)
    
    # print checklist summary
    print_arch_list(new_archs, "New architectures", bcolors.ENDC)
    print_arch_list(incomplete_archs, "Incomplete results (will be overwritten)", bcolors.WARNING)
    print_arch_list(cached_archs, "Existing results (skipped)", bcolors.OKCYAN)
    print_arch_list(overwrite_archs, "Existing results (will be overwritten)", bcolors.WARNING)
    print_arch_list(error_archs, "Invalid settings, (skipped, see errors above)", bcolors.FAIL)

    if ask_continue and len(valid_archs) > 0:
      print()
      while True:
        answer = input("Continue? (Y/n) ")
        if answer.lower() in ['yes', 'ye', 'y', '1', '']:
          break
        elif answer.lower() in ['no', 'n', '0']:
          sys.exit()
        else:
          print("Please enter yes or no")

    print()  
    running_arch_list = []
    active_running_arch_list = []

    #print("valid_architectures : {}".format(valid_architectures))
    for arch in valid_archs:
      tmp_dir = work_path + '/' + target + '/' + arch

      # get param dir (arch name before '/')
      arch_param_dir = re.sub('/.*', '', arch)

      # get settings variables
      settings_filename = arch_path + '/' + arch_param_dir + '/' + param_settings_filename
      with open(settings_filename, 'r') as f:
        settings_data = yaml.load(f, Loader=SafeLoader)
        try:
          rtl_path           = read_from_list('rtl_path', settings_data, settings_filename)
          top_level_filename = read_from_list('top_level_file', settings_data, settings_filename)
          top_level_module   = read_from_list('top_level_module', settings_data, settings_filename)
          clock_signal       = read_from_list('clock_signal', settings_data, settings_filename)
          file_copy_enable   = read_from_list('file_copy_enable', settings_data, settings_filename)
          file_copy_source   = read_from_list('file_copy_source', settings_data, settings_filename)
          file_copy_dest     = read_from_list('file_copy_dest', settings_data, settings_filename)
          use_parameters     = read_from_list('use_parameters', settings_data, settings_filename)
          start_delimiter    = read_from_list('start_delimiter', settings_data, settings_filename)
          stop_delimiter     = read_from_list('stop_delimiter', settings_data, settings_filename)
        except:
          continue # if an identifier is missing (modified since first read)
        
        # optionnal settings
        try:
          target_options = read_from_list(target, settings_data, settings_filename, optionnal=True, raise_if_missing=False, print_error=False)
          if target_options == False:
            print(bcolors.OKCYAN + "note: Cannot find optionnal target-specific options for target \"" + target + "\" in \"" + settings_filename + "\". Using default frequency bounds instead: " + "[{},{}] MHz.".format(default_fmax_lower_bound, default_fmax_upper_bound) + bcolors.ENDC)
            raise
          fmax_lower_bound = read_from_list('fmax_lower_bound', target_options, eda_target_filename, optionnal=True)
          fmax_upper_bound = read_from_list('fmax_upper_bound', target_options, eda_target_filename, optionnal=True)
        except:
          fmax_lower_bound = default_fmax_lower_bound
          fmax_upper_bound = default_fmax_upper_bound

        fmax_lower_bound = str(fmax_lower_bound)
        fmax_upper_bound = str(fmax_upper_bound)

        try:
          design_path = read_from_list('design_path', settings_data, settings_filename, optionnal=True, print_error=False)
        except:
          design_path = rtl_path

        try:
          param_target_filename = read_from_list('param_target_file', settings_data, settings_filename, optionnal=True, print_error=False)
        except:
          param_target_filename = top_level_filename

        try:
          generate_rtl = read_from_list('generate_rtl', settings_data, settings_filename, optionnal=True, print_error=False)
          try:
            generate_command = read_from_list('generate_command', settings_data, settings_filename, optionnal=True, print_error=False)
          except:
            print(bcolors.OKCYAN + "note: Cannot find key \"generate_command\" in \"" + settings_filename + "\" while generate_rtl=true, disabled hdl generation" + bcolors.ENDC)
            generate_command = ""
            generate_rtl = "false"
        except:
          generate_rtl = "false"

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
      copytree(design_path, tmp_dir, dirs_exist_ok = True)

      # replace parameters
      if use_parameters in tcl_bool_true:
        print(bcolors.OKCYAN + "Replace parameters" + bcolors.ENDC)
        param_target_file = tmp_dir + '/' + param_target_filename
        param_filename = arch_path + '/' + arch + ".txt"
        rp.replace_params(
          base_text_file=param_target_file, 
          replacement_text_file=param_filename, 
          output_file=param_target_file, 
          start_delimiter=start_delimiter, 
          stop_delimiter=stop_delimiter, 
          replace_all_occurrences=False
        )
        print()

      # run generate command
      if generate_rtl in tcl_bool_true:
        try:
          print(bcolors.OKCYAN + "Run generate command" + bcolors.ENDC)
          print(bcolors.BOLD + generate_command + bcolors.ENDC)
          result = subprocess.run([generate_command], cwd=tmp_dir, shell=True, check=True, text=True)
        except subprocess.CalledProcessError as e:
          print(bcolors.BOLD + bcolors.FAIL + "error: Cannot find identifier \"" + identifier + "\" in \"" + filename + "\"." + bcolors.ENDC)
        print()

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
          print(bcolors.OKCYAN + "note: the file \"" + file_copy_source + "\"specified in \"" + settings_filename + "\" does not exist. File copy disabled." + bcolors.ENDC)
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
      if len(valid_archs) == 1 and show_log_if_one:
        #process = subprocess.run(["make", "-f", script_path + "/" + tool + "/" + tool_makefile_filename, synth_fmax_rule, "SCRIPT_DIR=\"" + tmp_dir + '/' + work_script_path + "\"", "LOG_DIR=\"" + tmp_dir + '/' + log_path + "\"", "--no-print-directory"])
        process = subprocess.Popen(["make", "-f", script_path + "/" + tool + "/" + tool_makefile_filename, synth_fmax_rule, "WORK_DIR=\"" + tmp_dir + "\"", "SCRIPT_DIR=\"" + tmp_dir + '/' + work_script_path + "\"", "LOG_DIR=\"" + tmp_dir + '/' + log_path + "\"", "--no-print-directory"])
      else:
        process = subprocess.Popen(["make", "-f", script_path + "/" + tool + "/" + tool_makefile_filename, synth_fmax_rule, "WORK_DIR=\"" + tmp_dir + "\"", "SCRIPT_DIR=\"" + tmp_dir + '/' + work_script_path + "\"", "LOG_DIR=\"" + tmp_dir + '/' + log_path + "\"", "--no-print-directory"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

      running_arch_list.append(Running_arch(process, arch))
      print("started job for architecture \"{}\" between {} and {} MHz with pid {}".format(arch, fmax_lower_bound, fmax_upper_bound, process.pid))

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

      max_title_length = max(len(running_arch.arch) for running_arch in running_arch_list)

      for running_arch in running_arch_list:

        # get status files full paths
        tmp_dir = work_path + '/' + target + '/' + running_arch.arch
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
              comment = " (" + bcolors.OKGREEN + "done" + bcolors.ENDC + ")"
          else:
              comment = " (" + bcolors.FAIL + "terminated with errors" + bcolors.ENDC + ")"
          progress_bar(progress, title=running_arch.arch, title_size=max_title_length, endstr=comment)
        else: 
          progress_bar(progress, title=running_arch.arch, title_size=max_title_length)

      time.sleep(refresh_time)

    # summary
    print()
    for running_arch in running_arch_list:
      tmp_dir = work_path + '/' + target + '/' + running_arch.arch
      frequency_search_file = tmp_dir + '/' + log_path + '/' + frequency_search_filename
      try:
        with open(frequency_search_file, 'r') as file:
          lines = file.readlines()
          if len(lines) >= 1:
            summary_line = lines[-1]
            print(running_arch.arch + ": " + summary_line, end='')
      except:
      #  print(f"frequency_search_file '{frequency_search_file}' does not exist")
        pass
    print()
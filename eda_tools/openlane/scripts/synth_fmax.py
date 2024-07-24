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
import sys
import csv
import yaml
import json
import math
import time
import random
import argparse
import subprocess

# add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, '../../../scripts/lib')
sys.path.append(lib_path)

import printc

from architecture_handler import Architecture
from utils import *

import gen_config 

######################################
# Settings
######################################

report_path = "report"

yaml_config_filename = "settings.yml"
logfilename = "frequency_search.log"
statusfilename = "status.log"
synth_statusfilename = "synth_status.log"
freq_rep_filename = "frequency.rep"

fmax_explore = False
fmax_mindiff = 1
fmax_safezone = 5

script_name = "eda_tools/openlane/scripts/synth_fmax.py"
metrics_csv_filename = "runs/asterism/reports/metrics.csv"

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument('-b', '--basepath', default='.', help='base path (default: .)')
  parser.add_argument('-c', '--command', default='make synth', help='command to start synthesis (default: make synth)')

def parse_arguments():
  parser = argparse.ArgumentParser(description='Fmax synthesis')
  add_arguments(parser)
  return parser.parse_args()

######################################
# Subfunctions
######################################

def is_slack_met(tmp_path):
  wns_values = []
  metrics_csv_file = os.path.join(tmp_path, metrics_csv_filename)
  if not os.path.isfile(metrics_csv_file):
    printc.error("Metrics file \"" + metrics_csv_file + "\" not found", script_name=script_name)
    sys.exit(-1)

  with open(metrics_csv_file, mode='r', newline='') as csvfile:
    csvreader = csv.DictReader(csvfile)
    for row in csvreader:
      wns_values.append(row['wns'])
  
  print()
  if float(wns_values[0]) < 0:
    print("Timing ", end="")
    printc.red("VIOLATED!")
    return False
  printc.green("MET!")
  return True

def run_synth_script(command):
  process = subprocess.Popen(command, shell=True)
  while process.poll() is None:
    time.sleep(0.5)
  print()

def update_frequency(frequency, constraint_file):

  if not os.path.isfile(constraint_file):
    printc.error("Constraint file \"" + constraint_file + "\" not found", script_name=script_name)
    sys.exit(-1)

  with open(constraint_file, 'r') as f:
    data = json.load(f)

  data['CLOCK_PERIOD'] = 1000.0/frequency

  try: 
    with open(constraint_file, 'w') as f:
      json.dump(data, f, indent=4)
  except Exception as e:
    printc.error("Could not write config file \"" + constraint_file + "\"", script_name=script_name)
    printc.cyan("error details: ", end="", script_name=script_name)
    print(str(e))
    sys.exit(-1)

def report_progress(progress, statusfile, message):
  with open(statusfile, 'a') as f:
    f.write(str(progress) + "% - " + message + "\n")

######################################
# Synth Fmax
######################################

def synth_fmax(tmp_path, command):
  yaml_config_file = os.path.realpath(os.path.join(tmp_path, yaml_config_filename))
  arch = Architecture.read_yaml(yaml_config_file)

  if arch is None:
    printc.error("Could not read architecture settings from  \"" + yaml_config_file + "\"", script_name=script_name)
    sys.exit(-1)

  lower_bound = int(arch.fmax_lower_bound)
  upper_bound = int(arch.fmax_upper_bound)

  # Sanity check
  if upper_bound < lower_bound:
    printc.error("Upper bound cannot be smaller than lower bound", script_name=script_name)
    sys.exit(-1)

  # Create tmp folders
  create_dir(os.path.join(tmp_path, "report_MET"))
  create_dir(os.path.join(tmp_path, "report_VIOLATED"))


  # Get fimes full path
  logfile = os.path.join(tmp_path, arch.log_path, logfilename)
  statusfile = os.path.join(tmp_path, arch.log_path, statusfilename)
  synth_statusfile = os.path.join(tmp_path, arch.log_path, synth_statusfilename)
  constraint_file = os.path.join(tmp_path, arch.constraint_filename)

  # Create logfile
  create_dir(arch.log_path)
  with open(logfile, 'w') as logfile_handler:
    logfile_handler.write("Binary search for interval [" + str(lower_bound) + ":" + str(upper_bound) + "] MHz\n\n")

  report_path = os.path.join(tmp_path, "report")

  # Generate config file
  gen_config.main(
    base_path=tmp_path, 
    clock_signal=arch.clock_signal, 
    docker_id=arch.lib_name, 
    design_name=arch.top_level_module
  )

  start_lower_bound = lower_bound
  start_upper_bound = upper_bound

  max_runs = math.ceil(math.log((start_upper_bound - start_lower_bound) / fmax_mindiff) / math.log(2))
  report_progress(0, statusfile, "(1/" + str(max_runs) + ")")

  got_met = False
  got_violated = False

  fs_start_time = time.time()

  runs = 0

  while True:
    runs += 1
    mean = (upper_bound + lower_bound) / 2
    cur_freq = int(mean)

    with open(logfile, 'a') as logfile_handler:
      logfile_handler.write(f"{cur_freq} MHz: ")

    update_frequency(cur_freq, constraint_file)
    printc.header(f"\nRunning synthesis at {cur_freq} MHz\n")

    run_synth_script(command)

    freq_rep_file = os.path.join(report_path, freq_rep_filename)
    with open(freq_rep_file, 'w') as frequency_handler:
      frequency_handler.write(f"Target frequency: {cur_freq}")

    if is_slack_met(tmp_path):
      lower_bound = cur_freq
      got_met = True
      with open(logfile, 'a') as logfile_handler:
        logfile_handler.write("MET\n")
      try:
        copytree(report_path, os.path.join(tmp_path, "report_MET"))
      except:
        pass
    else:
      upper_bound = cur_freq
      got_violated = True
      with open(logfile, 'a') as logfile_handler:
        logfile_handler.write("VIOLATED\n")
      try:
        copytree(report_path, os.path.join(tmp_path, "report_VIOLATED"))
      except:
        pass

    diff = upper_bound - lower_bound

    if fmax_explore:
      if diff < fmax_safezone and runs > 2:
        if not got_violated:
          upper_bound += 2 * fmax_safezone
          start_upper_bound = upper_bound
        if not got_met:
          lower_bound -= 2 * fmax_safezone
          start_lower_bound = lower_bound

    if abs(diff) < fmax_mindiff + 1:
      break

      progress = round(100 * runs / max_runs)
      report_progress(progress, statusfile, f"({runs}/{max_runs})")

  report_progress(100, statusfile, f"({runs}/{max_runs})")

  fs_stop_time = time.time()
  fs_total_time = fs_stop_time - fs_start_time

  fs_total_time_formatted = time.strftime("%H:%M:%S", time.gmtime(fs_total_time))
  printc.cyan(f"\ntotal time for max frequency search: {fs_total_time_formatted} ({fs_total_time} seconds)")

  with open(logfile, 'a') as logfile_handler:
    logfile_handler.write("\n")

    if got_met and got_violated:
      shutil.copytree(os.path.join(tmp_path, "report_MET"), report_path, dirs_exist_ok=True)
      update_frequency(lower_bound, constraint_file)
      logfile_handler.write(f"Highest frequency with timing constraints being met: {lower_bound} MHz\n")
      print()
      printc.cyan(f"Highest frequency with timing constraints being met: {lower_bound} MHz\n", script_name=script_name)
    elif not got_met and not got_violated:
      printc.error("Path is unconstrained. Make sure there are registers at input and output of design.", script_name=script_name)
      logfile_handler.write("Path is unconstrained. Make sure there are registers at input and output of design.\n")
      sys.exit(-2)
    elif not got_violated:
      printc.error(f"No timing violated! Try raising the upper bound ({upper_bound} MHz)", script_name=script_name)
      logfile_handler.write(f"No timing violated! Try raising the upper bound ({upper_bound} MHz)\n")
      sys.exit(-3)
    else:
      printc.error(f"No timing met! Try lowering the lower bound ({lower_bound} MHz)", script_name=script_name)
      logfile_handler.write(f"No timing met! Try lowering the lower bound ({lower_bound} MHz)\n")
      sys.exit(-4)

######################################
# Main
######################################

def main(base_path, command):
  synth_fmax(base_path, command)

if __name__ == "__main__":
  args = parse_arguments()

  main(
    base_path = args.basepath,
    command = args.command
  )
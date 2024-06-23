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

import re
import copy
import time
import subprocess

import printc
from utils import *

script_name = os.path.basename(__file__)

class Running_arch:
  status_file_pattern = re.compile(r"(.*)")
  progress_file_pattern = re.compile(r"(.*)")

  def __init__(self, process, target, arch, display_name, status_file, progress_file, tmp_dir):
    self.process = process
    self.target = target
    self.arch = arch
    self.display_name = display_name
    self.status_file = status_file
    self.progress_file = progress_file
    self.tmp_dir = tmp_dir

  @staticmethod
  def set_patterns(status_file_pattern, progress_file_pattern):
    Running_arch.status_file_pattern = status_file_pattern
    Running_arch.progress_file_pattern = progress_file_pattern


def check_tool(tool, script_path, makefile, rule):
  print("checking the selected eda tool \"" + tool + "\" ..", end='')
  sys.stdout.flush()
  test_process = subprocess.Popen(["make", "-f", script_path + "/" + tool + "/" + makefile, rule, "--no-print-directory"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
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
    sys.exit(-1)
  print()

def run_parallel(command, nb_process=1, show_log_if_one=True):
  if nb_process == 1 and show_log_if_one:
    process = subprocess.Popen(command)
  else:
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
  return process

def show_progress(running_arch_list, refresh_time=5, show_log_if_one=True, mode="synthesis"):
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

      if mode == "synthesis":
        # get status files full paths
        fmax_status_file = running_arch.status_file
        synth_status_file = running_arch.progress_file
        fmax_status_pattern = Running_arch.status_file_pattern
        synth_status_pattern = Running_arch.progress_file_pattern

        # get progress from fmax status file
        fmax_progress = 0
        fmax_step = 1
        fmax_totalstep = 1
        if os.path.isfile(fmax_status_file):
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
        if os.path.isfile(synth_status_file):
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
      else:
        progress = None
        
      # check if process has finished and print progress 
      if running_arch.process.poll() is not None:
        try: 
          active_running_arch_list.remove(running_arch)
        except:
          pass
        
        if running_arch.process.returncode == 0:
          comment = " (" + printc.colors.GREEN + "done" + printc.colors.ENDC + ")"
          if progress is None:
            progress = 100
        else:
          comment = " (" + printc.colors.RED + "terminated with errors" + printc.colors.ENDC + ")"
          if progress is None:
            progress = 0
        progress_bar(progress, title=running_arch.display_name, title_size=max_title_length, endstr=comment)
      else: 
        progress_bar(progress, title=running_arch.display_name, title_size=max_title_length)

    time.sleep(refresh_time)
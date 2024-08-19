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
import json
import time
import argparse
import subprocess

# add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, '../../../scripts/lib')
sys.path.append(lib_path)

import printc

from architecture_handler import Architecture

######################################
# Settings
######################################

config_filename = "config.json"
yaml_config_filename = "settings.yml"
generate_command = "/openlane/flow.tcl -init_design_config"

script_name = "eda_tools/openlane/scripts/" + os.path.basename(__file__)

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument('-b', '--basepath', default='.', help='base path (default: .)')
  parser.add_argument('-c', '--clock', help='clock signal')
  parser.add_argument('-d', '--docker', help='docker id or name')
  parser.add_argument('-n', '--name', help='design name')

def parse_arguments():
  parser = argparse.ArgumentParser(description='Edit OpenLane config.json file')
  add_arguments(parser)
  return parser.parse_args()

######################################
# Main
######################################

def main(base_path, clock_signal, docker_id, design_name):
  config_file = os.path.join(base_path, config_filename)

  # Check if config file exists
  if not os.path.isfile(config_file):
    try:
      #command = "docker exec -it " + docker_id + " /bin/sh -c ' cd " + base_path + "; " + generate_command + " --design-dir " + base_path + "'"
      command = "docker exec -it " + docker_id + " /bin/sh -c ' python3 /openlane/scripts/config/init.py --design-dir " + base_path + " --design-name " + design_name + " --add-to-designs" + "'"
      printc.cyan("Run config generation command", script_name=script_name)
      printc.bold(" > " + command)
      print("", end="", flush=True)
      process = subprocess.Popen(command, shell=True)
      while process.poll() is None:
        # print('.', end='', flush=True)
        time.sleep(0.5)
      print()
    except Exception as e:
      printc.error("Config file generation failed", script_name=script_name)
      printc.cyan("error details: ", end="", script_name=script_name)
      print(str(e))
      sys.exit(-1)
      
  if not os.path.isfile(config_file):
    printc.error("Config file generation failed", script_name=script_name)
    sys.exit(-1)

  with open(config_file, 'r') as f:
    data = json.load(f)

  data['DESIGN_NAME'] = design_name
  data['CLOCK_PORT'] = clock_signal
  data['VERILOG_FILES'] = "dir::rtl/*.v"

  try: 
    with open(config_file, 'w') as f:
      json.dump(data, f, indent=4)
  except Exception as e:
    printc.error("Could not write config file \"" + config_file + "\"", script_name=script_name)
    printc.cyan("error details: ", end="", script_name=script_name)
    print(str(e))
    sys.exit(-1)

if __name__ == "__main__":
  args = parse_arguments()

  yaml_config_file = os.path.realpath(os.path.join(args.basepath, yaml_config_filename))
  arch = Architecture.read_yaml(yaml_config_file)

  if arch is None:
    printc.error("Could not read architecture settings from  \"" + yaml_config_file + "\"", script_name=script_name)
  else:
    if args.clock is None:
      args.clock = arch.clock_signal

    if args.docker is None:
      args.docker = arch.lib_name 

    if args.name is None:
      args.name = arch.top_level_module 

  if args.clock is None:
    printc.error("Missing --clock option", script_name=script_name)
    sys.exit(-1)

  if args.docker is None:
    printc.error("Missing --docker option", script_name=script_name)
    sys.exit(-1)

  if args.name is None:
    printc.error("Missing --name option", script_name=script_name)
    sys.exit(-1)

  main(
    base_path = args.basepath,
    clock_signal = args.clock,
    docker_id = args.docker,
    design_name = args.name
  )
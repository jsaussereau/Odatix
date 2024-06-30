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
import csv
import yaml
import argparse

dmips_per_mhz_pattern = re.compile("(.*)DMIPS_Per_MHz: ([0-9.]+)")
bad_value = ' /   '

# Add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, 'lib')
sys.path.append(lib_path)

import re_helper as rh
import printc

######################################
# Settings
######################################

benchmark_file = 'benchmark/benchmark.yml'

status_done = 'Done: 100%'

script_name = os.path.basename(__file__)

######################################
# Misc functions
######################################

def corrupted_directory(variant):
  printc.warning(variant + " => synthesis has not finished or directory has been corrupted", script_name)

def safe_cast(val, to_type, default=None):
  try:
      return to_type(val)
  except (ValueError, TypeError):
      return default

def parse_arguments():
  parser = argparse.ArgumentParser(description='Process FPGA or ASIC results')
  parser.add_argument('-i', '--input', default='work',
                      help='Input path (default: work/<tool>)')
  parser.add_argument('-o', '--output', default='results/benchmark.yml',
                      help='Output file (default: results/benchmark.yml')
  parser.add_argument('-b', '--benchmark', choices=['dhrystone'], default='dhrystone',
                      help='benchmark to parse (default: dhrystone)')
  parser.add_argument('-s', '--sim_file', default='log/sim.log',
                      help='simulation log file (default: log/sim.log)')
  #parser.add_argument('-f', '--format', choices=['yml'], default='yml',
  #                    help='Output formats: yml (default: yml)')
  return parser.parse_args()


######################################
# Parsing functions
######################################

def get_dmips_per_mhz(file):
  return rh.get_re_group_from_file(file, dmips_per_mhz_pattern, group_id=2)


######################################
# Format functions
######################################

def cast_to_int(input):
  if input == bad_value:
    return '/'
  else:
    return safe_cast(input, int, 0)

def cast_to_float(input):
  if input == bad_value:
    return '/'
  else:
    return safe_cast(input, float, 0.0)

def write_to_yaml(args, output_file):
  yaml_data = {}

  for arch in sorted(next(os.walk(args.input))[1]):
    yaml_data[arch] = {}
    for variant in sorted(next(os.walk(os.path.join(args.input, arch)))[1]):
      cur_path = os.path.join(args.input, arch, variant)
      cur_sim_file = os.path.join(cur_path, args.sim_file)

      if not os.path.exists(cur_sim_file):
        corrupted_directory(arch + '/' + variant)
        continue

      dmips_per_mhz = get_dmips_per_mhz(cur_sim_file)
      dmips_per_mhz = cast_to_float(dmips_per_mhz) if dmips_per_mhz != ' /  ' else ""
      yaml_data[arch][variant] = {
        'DMIPS_per_MHz': dmips_per_mhz,
      }

  output_path = os.path.dirname(output_file)
  if not os.path.exists(output_path):
    os.makedirs(output_path, exist_ok=True)
  try:
    with open(output_file, 'w') as file:
      yaml.dump(yaml_data, file, default_flow_style=False, sort_keys=False)
      printc.say("Results written to \"" + output_file + "\"", script_name=script_name)
  except Exception as e:
    printc.error("Could not write results to \"" + output_file + "\"", script_name=script_name)
    printc.cyan("error details: ", end="", script_name=script_name)
    print(e)

######################################
# Main
######################################

if __name__ == "__main__":
  args = parse_arguments()

  print(printc.colors.CYAN + "Export " +  args.benchmark + " results" + printc.colors.ENDC)

  if not os.path.isdir(args.input):
    printc.error("input directory \"" + args.input + "\" does not exist", script_name)
    sys.exit(1)

  #if args.format in ['yml']:
  write_to_yaml(args, args.output)

  print()
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
import argparse

from odatix.lib.settings import OdatixSettings
import odatix.lib.re_helper as rh
import odatix.lib.printc as printc

######################################
# Settings
######################################

DEFAULT_BENCHMARK = "dhrystone"
DEFAULT_SIM_FILE = "log/sim.log"

status_done = 'Done: 100%'

script_name = os.path.basename(__file__)

dmips_per_mhz_pattern = re.compile("(.*)DMIPS_Per_MHz: ([0-9.]+)")
bad_value = None

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument('-b', '--benchmark', default=DEFAULT_BENCHMARK, help='benchmark to parse (default: ' + DEFAULT_BENCHMARK + ')')
  parser.add_argument('-S', '--sim_file', default=DEFAULT_SIM_FILE, help='simulation log file (default: ' + DEFAULT_SIM_FILE + ')')
  parser.add_argument('-B', '--benchmark_file', help='output benchmark file')
  parser.add_argument('-w', '--work', help='simulation work directory')
  parser.add_argument('-c', '--config', default=OdatixSettings.DEFAULT_SETTINGS_FILE, help='global settings file for Odatix (default: ' + OdatixSettings.DEFAULT_SETTINGS_FILE + ')')

def parse_arguments():
  parser = argparse.ArgumentParser(description='Process benchmark results')
  add_arguments(parser)
  return parser.parse_args()

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

def write_to_yaml(input, sim_file, output_file):
  yaml_data = {}

  for arch in sorted(next(os.walk(input))[1]):
    yaml_data[arch] = {}
    for variant in sorted(next(os.walk(os.path.join(input, arch)))[1]):
      cur_path = os.path.join(input, arch, variant)
      cur_sim_file = os.path.join(cur_path, sim_file)

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
    print(str(e))

######################################
# Export Results
######################################

def export_benchmark(input, output, benchmark, sim_file):
  print(printc.colors.CYAN + "Export " +  benchmark + " results" + printc.colors.ENDC)
  input = os.path.join(input, benchmark)
  if not os.path.isdir(input):
    printc.error("input directory \"" + input + "\" does not exist", script_name)
    sys.exit(1)

  #if format in ['yml']:
  write_to_yaml(input, sim_file, output)

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

  if args.benchmark_file is not None:
    benchmark_file  = args.benchmark_file
  else:
    benchmark_file = settings.benchmark_file

  if args.work is not None:
    work = args.work
  else:
    work = settings.sim_work_path

  export_benchmark(
    input=work,
    output=benchmark_file,
    benchmark=args.benchmark,
    sim_file=args.sim_file
  )

if __name__ == "__main__":
  args = parse_arguments()
  main(args)
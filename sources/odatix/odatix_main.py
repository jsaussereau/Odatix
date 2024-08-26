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
import argparse
from pathlib import Path

# Add parent dir to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sources_dir = os.path.realpath(os.path.join(current_dir, os.pardir))
sys.path.append(sources_dir)

from odatix.components.motd import *
import odatix.components.run_simulations as run_sim
import odatix.components.run_fmax_synthesis as run_synth
import odatix.components.export_results as exp_res
import odatix.components.export_benchmark as exp_bench
import odatix.components.clean as cln

import odatix.lib.settings as settings
from odatix.lib.settings import OdatixSettings
import odatix.lib.printc as printc
from odatix.lib.utils import *

######################################
# Settings
######################################

EXIT_SUCCESS = 0

error_logfile = "odatix_error.log"

prog = os.path.basename(sys.argv[0])
script_name = os.path.basename(__file__)

######################################
# Parse Arguments
######################################

class ArgParser:

  def add_nobanner(parser):
    parser.add_argument('-Q', '--nobanner', action='store_true', help='suppress printing of banner')

  def parse_arguments():
    formatter = OdatixHelpFormatter
    ArgParser.parser = argparse.ArgumentParser(
      conflict_handler="resolve", 
      formatter_class=formatter,
      add_help=False
    )
    ArgParser.parser.add_argument('-v', '--version', action='store_true', help='show version and exit')
    ArgParser.parser.add_argument('-h', '--help', action='store_true', help='show this help message and exit')
    ArgParser.parser.add_argument('--init', action='store_true', help="init current directory by adding all the necessary config files")
    args, remaining_args = ArgParser.parser.parse_known_args()

    # Parse other arguments
    subparsers = ArgParser.parser.add_subparsers(dest="command")
    
    # Define parser for the 'init' command
    ArgParser.init_parser = subparsers.add_parser("init", help="init current directory by adding all the necessary config files (without any prompt)", formatter_class=formatter)
    ArgParser.init_parser.add_argument("-e", "--examples", action="store_true", help="Include examples")

    # Define parser for the 'fmax' command
    ArgParser.fmax_parser = subparsers.add_parser("fmax", help="run fmax synthesis", formatter_class=formatter)
    run_synth.add_arguments(ArgParser.fmax_parser)
    ArgParser.fmax_parser.add_argument('-e', '--noexport', action='store_true', help='do not export results after synthesis')
    ArgParser.add_nobanner(ArgParser.fmax_parser)

    # Define parser for the 'sim' command
    ArgParser.sim_parser = subparsers.add_parser("sim", help="run simulations", formatter_class=formatter)
    run_sim.add_arguments(ArgParser.sim_parser)
    ArgParser.add_nobanner(ArgParser.sim_parser)

    # Define parser for the 'results' command
    ArgParser.res_parser = subparsers.add_parser("results", help="export benchmark results", formatter_class=formatter)
    ArgParser.res_parser.add_argument("-t", "--tool", default="all", help="eda tool in use, or 'all'")
    ArgParser.res_parser.add_argument("-f", "--format", choices=["csv", "yml", "all"], help="Output format: csv, yml, or all")
    ArgParser.res_parser.add_argument("-u", "--use_benchmark", action="store_true", help="Use benchmark values in yaml file")
    ArgParser.res_parser.add_argument('-b', '--benchmark', choices=['dhrystone'], default=exp_bench.DEFAULT_BENCHMARK, help='benchmark to parse (default: ' + exp_bench.DEFAULT_BENCHMARK + ')')
    ArgParser.res_parser.add_argument("-B", "--benchmark_file", help="output benchmark file")
    ArgParser.res_parser.add_argument('-S', '--sim_file', default=exp_bench.DEFAULT_SIM_FILE, help='simulation log file (default: ' + exp_bench.DEFAULT_SIM_FILE + ')')
    ArgParser.res_parser.add_argument("-w", "--work", help="simulation work directory")
    ArgParser.res_parser.add_argument("-r", "--respath", help="Result path")
    ArgParser.res_parser.add_argument("-c", "--config", default=OdatixSettings.DEFAULT_SETTINGS_FILE, help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")")
    ArgParser.add_nobanner(ArgParser.res_parser)

    # Define parser for the 'res_benchmark' command
    ArgParser.bm_res_parser = subparsers.add_parser("res_benchmark", help="export benchmark results", formatter_class=formatter)
    exp_bench.add_arguments(ArgParser.bm_res_parser)
    ArgParser.add_nobanner(ArgParser.bm_res_parser)

    # Define parser for the 'res_synth' command
    ArgParser.exp_res_parser = subparsers.add_parser("res_synth", help="export synthesis results")
    exp_res.add_arguments(ArgParser.exp_res_parser)
    ArgParser.add_nobanner(ArgParser.exp_res_parser)

    # Define parser for the 'clean' command
    ArgParser.clean_parser = subparsers.add_parser("clean", help="clean directory", formatter_class=formatter)
    cln.add_arguments(ArgParser.clean_parser)
    ArgParser.add_nobanner(ArgParser.clean_parser)

    # Parse arguments
    return ArgParser.parser.parse_args()

  def help():
    full_header(description="Odatix - a FPGA/ASIC toolbox for design space exploration")
    printc.bold("Global:\n  ", printc.colors.CYAN, end="")
    ArgParser.parser.print_help()
    print()
    printc.bold("Synthesis:\n  ", printc.colors.CYAN, end="")
    ArgParser.fmax_parser.print_help()
    print()
    printc.bold("Simulation:\n  ", printc.colors.CYAN, end="")
    ArgParser.sim_parser.print_help()
    print()
    printc.bold("Results:", printc.colors.CYAN)
    printc.cyan("- All Results:\n  ", end="")
    ArgParser.res_parser.print_help()
    print()
    printc.cyan("- Benchmark Results:\n  ", end="")
    print(ArgParser.bm_res_parser.format_usage(), end="")
    print("  run ", end="")
    printc.bold(prog + " res_benchmark -h", end="")
    print(" for more details")
    print()
    printc.cyan("- Synthesis Results:\n  ", end="")
    print(ArgParser.exp_res_parser.format_usage(), end="")
    print("  run ", end="")
    printc.bold(prog + " res_synth -h", end="")
    print(" for more details")
    print()
    printc.bold("Clean:\n  ", printc.colors.CYAN, end="")
    ArgParser.clean_parser.print_help()
    print()
    printc.bold("Init:\n  ", printc.colors.CYAN, end="")
    ArgParser.init_parser.print_help()
    print()

class OdatixHelpFormatter(argparse.HelpFormatter):
  def __init__(self, prog):
    super().__init__(
      prog=prog,
      max_help_position=8
    )
    self._current_indent = 2

  def _format_action_invocation(self, action):
    parts = super()._format_action_invocation(action).split(", ")
    parts = [printc.colors.BOLD + part + printc.colors.ENDC for part in parts]
    return ", ".join(parts)

######################################
# Run functions
######################################

def run_simulations(args):
  success = True
  try:
    run_sim.main(args)
  except SystemExit as e:
    if e.code != EXIT_SUCCESS:
      success = False
  except Exception as e:
    internal_error(e, error_logfile, script_name)
    success = False
  return success

def run_fmax_synthesis(args):
  success = True
  try:
    run_synth.main(args)
  except SystemExit as e:
    if e.code != EXIT_SUCCESS:
      success = False
  except Exception as e:
    internal_error(e, error_logfile, script_name)
    success = False
  if success and not args.noexport:
    try:
      newargs = argparse.Namespace(
        tool = args.tool,
        format = exp_res.DEFAULT_FORMAT,
        use_benchmark = None,
        benchmark_file = None,
        work = args.work,
        respath = None,
        config = args.config,
      )
      exp_res.main(newargs)
    except SystemExit as e:
      if e.code != EXIT_SUCCESS:
        success = False
    except Exception as e:
      internal_error(e, error_logfile, script_name)
      success = False
  return success

def export_benchmark(args):
  success = True
  try:
    exp_bench.main(args)
  except SystemExit as e:
    if e.code != EXIT_SUCCESS:
      success = False
  except Exception as e:
    internal_error(e, error_logfile, script_name)
    success = False

def export_results(args):
  success = True
  try:
    exp_res.main(args)
  except SystemExit as e:
    if e.code != EXIT_SUCCESS:
      success = False
  except Exception as e:
    internal_error(e, error_logfile, script_name)
    success = False
  return success

def export_all_results(args):
  success = True
  try:
    if args.use_benchmark:
      newargs = argparse.Namespace(
        benchmark = args.benchmark,
        sim_file = args.sim_file,
        benchmark_file = args.benchmark_file,
        work = args.work,
        config = args.config,
      )
      exp_bench.main(newargs)
  except SystemExit as e:
    if e.code != EXIT_SUCCESS:
      success = False
      return success
  except Exception as e:
    internal_error(e, error_logfile, script_name)
    success = False
    return success
  try:
    newargs = argparse.Namespace(
      tool = args.tool,
      format = args.format,
      use_benchmark = args.use_benchmark,
      benchmark_file = args.benchmark_file,
      work = args.work,
      respath = args.respath,
      config = args.config,
    )
    exp_res.main(newargs)
  except SystemExit as e:
    if e.code != EXIT_SUCCESS:
      success = False
  except Exception as e:
    internal_error(e, error_logfile, script_name)
    success = False
  return success

def clean(args):
  success = True
  try:
    cln.main(args)
  except SystemExit as e:
    if e.code != EXIT_SUCCESS:
      success = False
  except Exception as e:
    internal_error(e, error_logfile, script_name)
    success = False


######################################
# Main
######################################

def main(args=None):

  if args is None:
    args = ArgParser.parse_arguments()

  # Display the version if requested
  if args.version:
    print_version()
    sys.exit(0)

  # Display help if requested
  if args.help:
    ArgParser.help()
    sys.exit(0)

  # If no command is selected 
  if args.command is None and not args.init:
    full_header()
    print("run ", end="")
    printc.bold(prog + " -h", end="")
    print(" to get a list of useful commands")
    sys.exit(0)

  try:
    args.nobanner
  except AttributeError:
    args.nobanner = False

  # Display init dialog
  if args.init:
    OdatixSettings.init_directory_dialog(prog=prog)
    sys.exit(0)

  # Display the banner
  if not args.nobanner:
    motd()
    print()

  # Dispatch the command to the appropriate function
  if args.command == "init":
    success = OdatixSettings.init_directory_nodialog(args.examples, prog)
  elif args.command == "sim":
    success = run_simulations(args)
  elif args.command == "fmax":
    success = run_fmax_synthesis(args)
  elif args.command == "results":
    success = export_all_results(args)
  elif args.command in "res_benchmark":
    success = export_benchmark(args)
  elif args.command in "res_synth":
    success = export_results(args)
  elif args.command in "clean":
    success = clean(args)

  sys.exit(success)

if __name__ == "__main__":
  main()

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
import odatix.components.run_fixed_freq_synthesis as run_fixed_freq_synthesis_module
import odatix.components.run_pnr as run_pnr_cmd
import odatix.components.run_analysis as analyze
import odatix.components.run_workflow as run_workflow
import odatix.components.run_dse as run_dse
import odatix.components.export_results as exp_res
import odatix.components.export_simulation_results as exp_sim_res
import odatix.components.export_workflow_results as exp_workflow_res
import odatix.components.export_derived_metrics as exp_derived
import odatix.components.export_analysis as exp_analysis
from odatix.components import results_command
import odatix.components.clean as cln
import odatix.components.migrate as migrate_cmd
import odatix.components.generate_configs as gen_configs
import odatix.components.replace_params as replace_params
import odatix.components.ls_command as ls_command
from odatix.components.cli_options import add_options, deprecated_option

import odatix.lib.parallel_job_handler.daemon_control as daemon_control  # noqa: F401  (jobtender's)
import jobtender.commands as session_commands
from odatix.lib.settings import OdatixSettings
import odatix.lib.printc as printc
from odatix.lib.utils import *

######################################
# Settings
######################################

EXIT_SUCCESS = 0

error_logfile = "odatix_error.log"

prog = "odatix"
script_name = os.path.basename(__file__)

######################################
# Parse Arguments
######################################

######################################
# Commands
######################################

#: Every command, by group, in the order the help lists them.
COMMAND_GROUPS = (
  ("Run", ("fmax", "synth", "pnr", "analyze", "sim", "workflow", "dse")),
  ("Results", ("results",)),
  ("Workspace", ("ls",)),
  ("Daemon", ("ps", "monitor", "stop")),
  ("Utilities", ("init", "generate", "replace", "clean", "migrate")),
)

#: What "odatix results" exports: "all" does every other one in turn.
RESULT_TYPES = ("all", "synth", "sim", "workflow", "analysis", "derived")

#: Former command names, still accepted for one version, and what they now read.
DEPRECATED_COMMANDS = {
  "freq": ["synth"],
  "res_synth": ["results", "synth"],
  "res_simulation": ["results", "sim"],
  "res_workflow": ["results", "workflow"],
  "res_analysis": ["results", "analysis"],
  "res_derived": ["results", "derived"],
}

#: Former commands that are gone, and what to do instead.
REMOVED_COMMANDS = {
  "res_benchmark": "benchmark results are no longer exported: declare a benchmark score as a simulation metric (_metrics.yml)",
  "explore": 'use "odatix dse"',
  "synthesis": 'use "odatix synth"',
}

#: Where the words of Odatix are defined.
from odatix.lib.doc_links import GLOSSARY_URL

#: Options of the root parser, which take no value.
ROOT_FLAGS = ("-v", "--version", "-h", "--help", "--init")


def normalize_argv(argv):
  """
  The command line as the parser reads it, with the former spellings of the
  commands rewritten, and what was rewritten.

  argparse cannot alias "res_synth" to "results synth", nor give "results" a
  default type, so this is done on the words themselves before parsing.

  Returns:
      tuple: (argv, warnings), argv without the program name.

  Raises:
      SystemExit: a command that no longer exists.
  """
  argv = list(argv)
  warnings = []
  position = 0
  while position < len(argv) and argv[position] in ROOT_FLAGS:
    if argv[position] == "--init":
      del argv[position]
      argv.insert(position, "init")
      warnings.append('"odatix --init" is deprecated and will be removed in a future version: use "odatix init"')
      break
    position += 1
  if position >= len(argv):
    return argv, warnings

  command = argv[position]
  if command in REMOVED_COMMANDS:
    printc.error('"odatix ' + command + '" no longer exists: ' + REMOVED_COMMANDS[command], "odatix")
    raise SystemExit(2)
  if command in DEPRECATED_COMMANDS:
    replacement = DEPRECATED_COMMANDS[command]
    argv[position:position + 1] = replacement
    warnings.append(
      '"odatix ' + command + '" is deprecated and will be removed in a future version: use "odatix ' + " ".join(replacement) + '"'
    )
    command = replacement[0]
  if command == "results":
    following = argv[position + 1] if position + 1 < len(argv) else None
    if following is None or (following.startswith("-") and following not in ("-h", "--help")):
      argv.insert(position + 1, "all")
  return argv, warnings


class ArgParser:

  def add_nobanner(parser):
    add_options(parser, "nobanner")

  def parse_arguments(argv=None):
    formatter = OdatixHelpFormatter
    argv, warnings = normalize_argv(sys.argv[1:] if argv is None else argv)
    for warning in warnings:
      printc.warning(warning, "odatix")

    ArgParser.parser = argparse.ArgumentParser(
      prog="odatix",
      conflict_handler="resolve",
      formatter_class=formatter,
      add_help=False,
    )
    ArgParser.parser.add_argument("-v", "--version", action="store_true", help="show version and exit")
    ArgParser.parser.add_argument("-h", "--help", action="store_true", help="show this help message and exit")

    subparsers = ArgParser.parser.add_subparsers(dest="command", metavar="<command>")
    ArgParser.subparsers = subparsers
    add = lambda name, help, **keywords: subparsers.add_parser(name, help=help, description=help[:1].upper() + help[1:], formatter_class=formatter, **keywords)

    # Run
    ArgParser.fmax_parser = add("fmax", "run Fmax synthesis")
    run_synth.add_arguments(ArgParser.fmax_parser)
    ArgParser.add_nobanner(ArgParser.fmax_parser)

    ArgParser.range_parser = add("synth", "run synthesis at given frequencies")
    run_fixed_freq_synthesis_module.add_arguments(ArgParser.range_parser)
    ArgParser.add_nobanner(ArgParser.range_parser)

    ArgParser.pnr_parser = add("pnr", "place & route designs already synthesized")
    run_pnr_cmd.add_arguments(ArgParser.pnr_parser)
    ArgParser.add_nobanner(ArgParser.pnr_parser)

    ArgParser.analyze_parser = add("analyze", "run RTL analysis")
    analyze.add_arguments(ArgParser.analyze_parser)
    ArgParser.add_nobanner(ArgParser.analyze_parser)

    ArgParser.sim_parser = add("sim", "run simulations")
    run_sim.add_arguments(ArgParser.sim_parser)
    ArgParser.add_nobanner(ArgParser.sim_parser)

    ArgParser.workflow_parser = add("workflow", "run workflows")
    run_workflow.add_arguments(ArgParser.workflow_parser)
    ArgParser.add_nobanner(ArgParser.workflow_parser)

    ArgParser.dse_parser = add("dse", "explore a design space with a search campaign instead of sweeping it")
    run_dse.add_arguments(ArgParser.dse_parser)
    ArgParser.add_nobanner(ArgParser.dse_parser)

    # Results
    ArgParser.res_parser = add(
      "results", "export the results of the work directory (all of them by default)",
      epilog='Without a type, "odatix results" is "odatix results all", and takes its options: '
             'see "odatix results all -h". The options of a type come after it.',
    )
    ArgParser.add_nobanner(ArgParser.res_parser)
    result_types = ArgParser.res_parser.add_subparsers(dest="result_type", metavar="<type>")
    result_types.required = True
    add_type = lambda name, help: result_types.add_parser(name, help=help, description=help[:1].upper() + help[1:], formatter_class=formatter)

    ArgParser.res_all_parser = add_type("all", "export synthesis, simulation and workflow results, then apply derived metrics")
    add_options(
      ArgParser.res_all_parser, "tool", "work_path", "result_path", "metrics", "config",
      tool={"default": "all", "help": "tool whose synthesis results to export, or 'all' (default: all)"},
    )
    ArgParser.add_nobanner(ArgParser.res_all_parser)

    ArgParser.exp_res_parser = add_type("synth", "export synthesis and place & route results")
    exp_res.add_arguments(ArgParser.exp_res_parser)
    ArgParser.add_nobanner(ArgParser.exp_res_parser)

    ArgParser.exp_sim_res_parser = add_type("sim", "export simulation results")
    exp_sim_res.add_arguments(ArgParser.exp_sim_res_parser)
    ArgParser.add_nobanner(ArgParser.exp_sim_res_parser)

    ArgParser.exp_workflow_res_parser = add_type("workflow", "export workflow results")
    exp_workflow_res.add_arguments(ArgParser.exp_workflow_res_parser)
    ArgParser.add_nobanner(ArgParser.exp_workflow_res_parser)

    ArgParser.exp_analysis_parser = add_type("analysis", "report the RTL analyses of the work directory, and export them again")
    exp_analysis.add_arguments(ArgParser.exp_analysis_parser)
    ArgParser.add_nobanner(ArgParser.exp_analysis_parser)

    ArgParser.exp_derived_parser = add_type("derived", "apply derived metrics to the result files (post-processing)")
    exp_derived.add_arguments(ArgParser.exp_derived_parser)
    ArgParser.add_nobanner(ArgParser.exp_derived_parser)

    # Daemon
    ArgParser.monitor_parser = add("monitor", "attach the monitor to a session of the workspace")
    add_options(
      ArgParser.monitor_parser, "session_selector", "any_workspace", "any_user", "endpoint_options",
      session_selector={"help": "session to attach to: its name, its ID (12345.nightly), its PID, or the start of one of them (default: the only session of the workspace)"},
      remote={"help": "attach to a session on another machine over ssh, e.g. user@host or user@host:/path/to/workspace"},
    )
    ArgParser.add_nobanner(ArgParser.monitor_parser)

    ArgParser.ps_parser = add("ps", "list the active sessions of the workspace")
    add_options(
      ArgParser.ps_parser, "session_selector", "zombies", "any_workspace", "any_user", "endpoint_options",
      session_selector={"help": "only the sessions this selects: a name, an ID (12345.nightly), a PID, or the start of one of them"},
      zombies={"help": "also list zombie sessions (unresponsive daemons and leftover state files)"},
      any_workspace={"help": "list the sessions of every workspace (default: those of the current workspace only)"},
      any_user={"help": "list the sessions of every user, with whose they are and who may use them (default: yours only)"},
      remote={"help": "list the sessions of another machine over ssh, e.g. user@host or user@host:/path/to/workspace"},
    )
    ArgParser.ps_parser.add_argument('-V', '--verbose', action='store_true', help='also show where each session listens')
    ArgParser.ps_parser.add_argument('--json', action='store_true', help='print the session list as JSON, session tokens included (this is what a remote odatix reads over ssh: do not pipe it anywhere public)')
    ArgParser.add_nobanner(ArgParser.ps_parser)

    ArgParser.stop_parser = add("stop", "stop a session of the workspace")
    stop_selector_group = ArgParser.stop_parser.add_mutually_exclusive_group()
    add_options(stop_selector_group, "session_selector")
    stop_selector_group.add_argument('-a', '--all', action='store_true', help='stop all your sessions of the workspace (of every workspace with --any-workspace, of every user with --any-user)')
    add_options(
      ArgParser.stop_parser, "zombies", "any_workspace", "any_user", "endpoint_options",
      zombies={"help": "also kill zombie sessions (unresponsive daemons and leftover state files)"},
      remote={"help": "stop a session on another machine over ssh, e.g. user@host or user@host:/path/to/workspace"},
    )
    ArgParser.add_nobanner(ArgParser.stop_parser)

    # Workspace
    ArgParser.ls_parser = add("ls", "list the architectures, simulations and workflows of the workspace")
    ls_command.add_arguments(ArgParser.ls_parser)
    ArgParser.add_nobanner(ArgParser.ls_parser)

    # Utilities
    ArgParser.init_parser = add("init", "create the configuration files of a workspace in the current directory")
    ArgParser.init_parser.add_argument("-y", "--yes", dest="noask", action="store_true", help="do not ask anything: create the files, without the examples unless --examples is given")
    ArgParser.init_parser.add_argument("--examples", action="store_true", default=None, help="include the examples")
    deprecated_option(ArgParser.init_parser, "-e", "--examples", action="store_true", dest="examples")
    ArgParser.add_nobanner(ArgParser.init_parser)

    ArgParser.gen_configs_parser = add("generate", "generate configurations")
    gen_configs.add_arguments(ArgParser.gen_configs_parser)
    ArgParser.add_nobanner(ArgParser.gen_configs_parser)

    ArgParser.replace_parser = add("replace", "replace the text between two delimiters of a file")
    replace_params.add_arguments(ArgParser.replace_parser)
    ArgParser.add_nobanner(ArgParser.replace_parser)

    ArgParser.clean_parser = add("clean", "remove generated files, as a clean profile says")
    cln.add_arguments(ArgParser.clean_parser)
    ArgParser.add_nobanner(ArgParser.clean_parser)

    ArgParser.migrate_parser = add("migrate", "rewrite the settings files written in a former format")
    migrate_cmd.add_arguments(ArgParser.migrate_parser)
    ArgParser.add_nobanner(ArgParser.migrate_parser)

    # Try enabling autocompletion if argcomplete is installed
    try:
      import argcomplete
      argcomplete.autocomplete(ArgParser.parser)
    except ImportError:
      pass  # No error if argcomplete is missing

    return ArgParser.parser.parse_args(argv)

  def command_help(name):
    """The one-line help of a command, as its parser declares it."""
    for action in ArgParser.subparsers._choices_actions:
      if action.dest == name:
        return action.help or ""
    return ""

  def help():
    """The help of "odatix", generated from the commands it has."""
    full_header(description="Odatix - an FPGA/ASIC toolbox for design space exploration")
    print("usage: " + printc.colors.BOLD + "odatix" + printc.colors.ENDC + " [-h] [-v] <command> [<options>]")
    width = max(len(name) for _group, names in COMMAND_GROUPS for name in names) + 2
    for group, names in COMMAND_GROUPS:
      print()
      printc.bold(group + ":", printc.colors.CYAN)
      for name in names:
        print("  " + printc.colors.BOLD + name.ljust(width) + printc.colors.ENDC + ArgParser.command_help(name))
    print()
    print('Run "odatix <command> -h" for the options of a command.')
    print("Also: odatix-gui (graphical interface), odatix-explorer (results explorer).")
    print("Words of Odatix: " + GLOSSARY_URL)

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

def command_status(result):
  """
  Whether a command succeeded, from what its main() returned: nothing or True
  for a success, False or a non-zero exit code for a failure.
  """
  if result is None or result is True:
    return True
  if result is False:
    return False
  if isinstance(result, int):
    return result == EXIT_SUCCESS
  return bool(result)

def run_main(main_function, args):
  """
  Run the main() of a command, and say whether it succeeded, however it says
  so: by what it returns, or by stopping with an exit code.
  """
  try:
    return command_status(main_function(args))
  except SystemExit as e:
    return e.code in (None, EXIT_SUCCESS)
  except Exception as e:
    internal_error(e, error_logfile, script_name)
    return False

# The session commands are jobtender's (see jobtender.commands), with the
# options table of Odatix (cli_options) and its command names in their hints
# (see odatix.jobs_plugin).

def monitor_daemon(args):
  return session_commands.monitor_session(args, script_name)

def stop_daemon(args):
  return session_commands.stop_sessions(args, script_name)

def list_daemons(args):
  return session_commands.list_sessions(args, script_name)

#: "odatix results" alone: every kind of result there is, then the derived
#: metrics (see odatix.components.results_command, shared with the API).
export_all_results = results_command.export_all

def export_result_type(result_type, args):
  """
  One type of "odatix results". It fails as soon as it reported an error,
  whatever the export went on to do: a metric that could not be read is a
  definition to fix, and a script must be able to tell.
  """
  success, errors = results_command.export(
    result_type, args, on_exception=lambda e: internal_error(e, error_logfile, script_name),
  )
  if errors:
    printc.note(
      str(len(errors)) + " error" + ("s" if len(errors) > 1 else "") + " reported above: exiting with status 1",
      script_name,
    )
  return success

#: What runs each type of "odatix results".
RESULT_COMMANDS = dict(
  (result_type, lambda args, result_type=result_type: export_result_type(result_type, args))
  for result_type in RESULT_TYPES
)

def export_results_command(args):
  return RESULT_COMMANDS[args.result_type](args)

def init_directory(args):
  """
  "odatix init": asks before writing, unless told not to (-y) or there is no
  one to ask (no terminal, as in a script).
  """
  if args.noask or not sys.stdin.isatty():
    return OdatixSettings.init_directory_nodialog(bool(args.examples), prog)
  return OdatixSettings.init_directory_dialog(include_examples=args.examples, prog=prog)

#: What runs each command.
COMMANDS = {
  "init": init_directory,
  "generate": lambda args: run_main(gen_configs.main, args),
  "replace": lambda args: run_main(replace_params.main, args),
  "fmax": lambda args: run_main(run_synth.main, args),
  "synth": lambda args: run_main(run_fixed_freq_synthesis_module.main, args),
  "pnr": lambda args: run_main(run_pnr_cmd.main, args),
  "analyze": lambda args: run_main(analyze.main, args),
  "sim": lambda args: run_main(run_sim.main, args),
  "workflow": lambda args: run_main(run_workflow.main, args),
  "dse": lambda args: run_main(run_dse.main, args),
  "monitor": monitor_daemon,
  "stop": stop_daemon,
  "ps": list_daemons,
  "ls": ls_command.main,
  "results": export_results_command,
  "clean": lambda args: run_main(cln.main, args),
  "migrate": lambda args: run_main(migrate_cmd.main, args),
}

######################################
# Main
######################################

def main(args=None):

  # No color codes in a pipe or a file (or with NO_COLOR): they are for a terminal.
  printc.plain_unless_terminal()

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
  if args.command is None:
    full_header()
    print("run ", end="")
    printc.bold("odatix -h", end="")
    print(" to get a list of useful commands")
    sys.exit(0)

  try:
    args.nobanner
  except AttributeError:
    args.nobanner = False

  if args.command in ("monitor", "stop", "ps", "ls"):
    args.nobanner = True

  # What is said from here on is said by the command, not by the module
  # saying it.
  label = "odatix " + args.command
  if args.command == "results":
    label += " " + args.result_type
  printc.set_command(label)

  # Display the banner
  if not args.nobanner:
    motd()
    print()

  try:
    success = command_status(COMMANDS[args.command](args))
  except KeyboardInterrupt:
    print()
    printc.note("Interrupted", "odatix")
    success = False
  except Exception as e:
    # A short message and the log holding the trace, rather than the trace.
    internal_error(e, error_logfile, script_name)
    success = False

  sys.exit(EXIT_SUCCESS if success else 1)

if __name__ == "__main__":
  main()

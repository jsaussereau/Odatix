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
import argparse

import odatix.lib.printc as printc
import odatix.run.cli as run_cli
from odatix.components.cli_options import add_options
from odatix.workspace import migrate as workspace_migrate
from odatix.workspace.yaml_io import read_mapping

script_name = os.path.basename(__file__)

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument("-n", "--dry-run", action="store_true", help="only say what would change")
  parser.add_argument("--no-backup", action="store_true", help="do not keep the former version of each file as <file>.bak")
  add_options(parser, "config")

def parse_arguments():
  parser = argparse.ArgumentParser(description="Rewrite the settings files written in a former format")
  add_arguments(parser)
  return parser.parse_args()

######################################
# Deprecated simulation keys
######################################

# The top-level parameter keys of a simulation, superseded by "param_domains"
# under "architectures". They still run, but their meaning depends on the
# architecture, which only the user can tell: they are listed, not rewritten.
DEPRECATED_SIMULATION_KEYS = (
  "use_parameters", "param_target_file", "start_delimiter", "stop_delimiter",
  "override_parameters", "override_param_file", "override_param_target_file",
  "override_start_delimiter", "override_stop_delimiter",
)

SIMULATION_REFERENCE_URL = "https://odatix.readthedocs.io/docs/reference/simulation/#parameters"

def deprecated_simulation_keys(workspace):
  """
  The simulations of the workspace still written with the deprecated parameter
  keys, as (settings file, [keys]) pairs.
  """
  found = []
  try:
    simulations = list(workspace.simulations)
  except Exception:
    return found
  for simulation in simulations:
    try:
      settings_path = simulation.settings_path
      data = read_mapping(settings_path)
    except Exception:
      continue
    keys = [key for key in DEPRECATED_SIMULATION_KEYS if key in (data or {})]
    if keys:
      found.append((settings_path, keys))
  return found

######################################
# Report
######################################

def report_deprecated_simulations(deprecated):
  """Say which simulations hold deprecated keys. False when there is one."""
  if not deprecated:
    return True
  root = os.getcwd()
  for path, keys in deprecated:
    printc.warning(
      os.path.relpath(path, root) + ": deprecated " + ", ".join('"' + key + '"' for key in keys)
      + ', to express under "architectures" with "param_domains"', script_name
    )
  printc.note(
    "{0} simulation(s) still use the deprecated parameter keys, which odatix migrate does not rewrite: "
    "see {1}".format(len(deprecated), SIMULATION_REFERENCE_URL), script_name
  )
  return False

def report(migrations, dry_run=False, deprecated=None):
  """Print what was (or would be) migrated. False when something is left to the user."""
  if not migrations:
    if deprecated:
      return report_deprecated_simulations(deprecated)
    printc.note("Every settings file is already in the current format", script_name)
    return True

  root = os.getcwd()
  for migration in migrations:
    path = os.path.relpath(migration.path, root)
    printc.bold(path + " (" + migration.kind + ")")
    for line in migration.changes:
      {"-": printc.red, "+": printc.green}.get(line[0], printc.yellow)("  " + line)
    for reason in migration.left:
      printc.warning(reason, script_name)
    if migration.backup:
      printc.note("former version kept as " + os.path.relpath(migration.backup, root), script_name)

  changed = sum(1 for migration in migrations if migration.changed)
  left = sum(1 for migration in migrations if migration.left)
  if dry_run:
    printc.note("{0} file(s) would be rewritten. Run without --dry-run to do it.".format(changed), script_name)
  else:
    printc.note("{0} file(s) rewritten".format(changed), script_name)
  if left:
    printc.warning("{0} file(s) still hold settings to rewrite by hand".format(left), script_name)
  simulations_ok = report_deprecated_simulations(deprecated)
  return left == 0 and simulations_ok

######################################
# Main
######################################

def main(args):
  workspace = run_cli.command_workspace(args.config, script_name)
  migrations = workspace_migrate.migrate(workspace, dry_run=args.dry_run, backup=not args.no_backup)
  return report(migrations, dry_run=args.dry_run, deprecated=deprecated_simulation_keys(workspace))

if __name__ == "__main__":
  args = parse_arguments()
  main(args)

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
import yaml
import argparse

import odatix.lib.printc as printc
from odatix.lib.utils import read_from_list, KeyNotInListError, BadValueInListError
from odatix.lib.settings import OdatixSettings
from odatix.workspace.clean import DANGEROUS_PATHS, remove_path as remove_matching_paths
import odatix.lib.yaml_loader as yaml_loader

script_name = os.path.basename(__file__)

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument("-i", "--input", default=None, help="input settings file")
  parser.add_argument("-f", "--force", action="store_true", help="force delete (dangerous!)")
  parser.add_argument("-v", "--verbose", action="store_true", help="print extra details")
  parser.add_argument("-q", "--quiet", action="store_true", help="do not print anything, except errors")
  parser.add_argument(
    "-c",
    "--config",
    default=OdatixSettings.DEFAULT_SETTINGS_FILE,
    help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
  )

def parse_arguments():
  parser = argparse.ArgumentParser(description="Clean up current directory")
  add_arguments(parser)
  return parser.parse_args()

######################################
# Helper Functions
######################################

def remove_path(path, force=False, verbose=False, quiet=False):
  """
  Remove everything one clean pattern matches, and report it on the terminal.

  The removal itself is the one the workspace API performs (see
  odatix.workspace.clean), so "odatix clean" and the graphical interface always
  delete exactly the same things.
  """
  result = remove_matching_paths(path, force=force)

  for removal in result.removed:
    if not quiet:
      printc.say("Removed \"" + removal.path + "\" (" + removal.kind + ")", script_name=script_name)

  for removal in result.skipped:
    if not quiet:
      printc.warning("Deleting \"" + removal.path + "\" seams dangerous! Use --force to force deletion (use at your own risks!)", script_name=script_name)

  if verbose:
    for pattern in result.unmatched:
      printc.warning("Path \"" + pattern + "\" does not exist or is not accessible.", script_name=script_name)

  for removal in result.errors:
    printc.error("Failed to remove \"" + removal.path + "\".", script_name=script_name)
    printc.cyan("error details: ", end="", script_name=script_name)
    print(removal.message)

######################################
# Clean
######################################

def clean(settings_filename, force=False, verbose=False, quiet=False):
  if not os.path.isfile(settings_filename):
    if not quiet:
      printc.note("There is no clean settings file \"" + settings_filename + "\" in \"" + os.path.realpath(".") + "\". Using default Odatix clean settings file", script_name)
    settings_filename = os.path.join(OdatixSettings.odatix_path, OdatixSettings.DEFAULT_CLEAN_SETTINGS_FILE)
    if not os.path.isfile(settings_filename):
      printc.error("There is no default Odatix clean settings file \"" + settings_filename, script_name)
      sys.exit(-1)
  with open(settings_filename, "r") as f:
    try:
      settings_data = yaml.load(f, Loader=yaml_loader.SafeLoader)
    except Exception as e:
      printc.error("Settings file \"" + settings_filename + "\" is not a valid YAML file", script_name)
      printc.cyan("error details: ", end="", script_name=script_name)
      print(str(e))
      sys.exit(-1)
    try:
      remove_list = read_from_list("remove_list", settings_data, settings_filename, script_name=script_name)
    except (KeyNotInListError, BadValueInListError):
      sys.exit(-1)

    if not isinstance(remove_list, list):
      printc.error("\"remove_list\" from settings file \"" + settings_filename + "\" is not a list", script_name)
      printc.note("Are you missing dashes (-)?", script_name)
      sys.exit(-1)

    for path in remove_list:
      remove_path(path, force, verbose, quiet)

######################################
# Main
######################################

def main(args, settings=None): 
  # Get settings
  if settings is None:
    settings = OdatixSettings(args.config)
    if not settings.valid:
      sys.exit(-1)

  if args.input is None:
    args.input = settings.clean_settings_file

  clean(
    settings_filename=args.input,
    force=args.force,
    verbose=args.verbose,
    quiet=args.quiet
  )

if __name__ == "__main__":
  args = parse_arguments()
  main(args)

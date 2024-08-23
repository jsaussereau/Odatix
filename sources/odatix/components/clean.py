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
import glob
import shutil
import argparse

import odatix.lib.printc as printc
from odatix.lib.utils import read_from_list, KeyNotInListError, BadValueInListError
from odatix.lib.settings import OdatixSettings

script_name = os.path.basename(__file__)

DANGEROUS_PATHS = ["/", "./", "./*", "*", "~", ".", ".."]

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
      
  cwd = os.getcwd()
  full_path = os.path.realpath(os.path.join(cwd, path))

  if path in DANGEROUS_PATHS or full_path in DANGEROUS_PATHS:
    if not force:
      if not quiet:
        printc.warning("Deleting \"" + full_path + "\" seams dangerous! Use --force to force deletion (use at your own risks!)", script_name=script_name)
      return

  # Handle asterisks
  paths_to_remove = glob.glob(full_path)

  # Check if the lis is empty
  if not paths_to_remove:
    if verbose:
      printc.warning("Path \"" + full_path + "\" does not exist or is not accessible.", script_name=script_name)
    return

  # Remove path
  for p in paths_to_remove:
    try:
      if os.path.isfile(p) or os.path.islink(p):
        os.remove(p)
        if not quiet:
          printc.say("Removed \"" + p + "\" (file)", script_name=script_name)
      elif os.path.isdir(p):
        shutil.rmtree(p)
        if not quiet:
          printc.say("Removed \"" + p + "\" (directory)", script_name=script_name)
      else:
        if verbose:
          printc.warning("Path \"" + p + "\" does not exist or is not accessible.", script_name=script_name)
    except Exception as e:
      printc.error("Failed to remove \"" + p + "\".", script_name=script_name)
      printc.cyan("error details: ", end="", script_name=script_name)
      print(str(e))

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
      settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
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

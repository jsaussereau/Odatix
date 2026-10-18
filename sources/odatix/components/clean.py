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
from odatix.components.cli_options import add_options, deprecated_option
from odatix.workspace.clean import DANGEROUS_PATHS, remove_path as remove_matching_paths
import odatix.lib.yaml_loader as yaml_loader

script_name = os.path.basename(__file__)

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  add_options(parser, "settings_file")
  parser.add_argument("-y", "--yes", dest="force", action="store_true", help="also remove what the patterns that look dangerous match (/, ~, *, ...): they are left alone otherwise")
  deprecated_option(parser, "-f", "-y/--yes", action="store_true", dest="force")
  deprecated_option(parser, "--force", "-y/--yes", action="store_true", dest="force")
  parser.add_argument("-V", "--verbose", action="store_true", help="print extra details")
  parser.add_argument("-q", "--quiet", action="store_true", help="do not print anything, except errors")
  add_options(parser, "config")

def parse_arguments():
  parser = argparse.ArgumentParser(description="Clean up current directory")
  add_arguments(parser)
  return parser.parse_args()

######################################
# Helper Functions
######################################

def display_path(path):
  """
  A path as the terminal shows it: relative to the workspace (the current
  directory) when it lies inside it, absolute otherwise. What a clean touched
  outside the workspace is exactly what must be shown in full.
  """
  try:
    relative = os.path.relpath(path, os.path.realpath("."))
  except ValueError:
    return path
  if relative == os.pardir or relative.startswith(os.pardir + os.sep):
    return path
  return relative


def remove_path(path, force=False, verbose=False, quiet=False):
  """
  Remove everything one clean pattern matches, and report it on the terminal.
  Returns the odatix.workspace.clean.CleanResult of the pattern.

  The removal itself is the one the workspace API performs (see
  odatix.workspace.clean), so "odatix clean" and the graphical interface always
  delete exactly the same things.
  """
  result = remove_matching_paths(path, force=force)

  for removal in result.removed:
    if not quiet:
      printc.say("Removed \"" + display_path(removal.path) + "\" (" + removal.kind + ")", script_name=script_name)

  for removal in result.skipped:
    if not quiet:
      printc.warning("Deleting \"" + display_path(removal.path) + "\" seems dangerous: it is left alone. Use -y/--yes to delete it anyway (at your own risk)", script_name=script_name)

  if verbose and not quiet:
    # Not a problem: a clean profile lists what a run may leave behind.
    for pattern in result.unmatched:
      printc.note("Nothing matches \"" + display_path(pattern) + "\"", script_name=script_name)

  for removal in result.errors:
    printc.error("Failed to remove \"" + display_path(removal.path) + "\".", script_name=script_name)
    printc.cyan("error details: ", end="", script_name=script_name)
    print(removal.message)

  return result

######################################
# Clean
######################################

def clean(settings_filename, force=False, verbose=False, quiet=False):
  if not os.path.isfile(settings_filename):
    if not quiet:
      printc.note("There is no clean settings file \"" + settings_filename + "\" in \"" + os.path.realpath(".") + "\". Using default Odatix clean settings file", script_name)
    settings_filename = os.path.join(OdatixSettings.odatix_init_path, OdatixSettings.DEFAULT_CLEAN_SETTINGS_FILE)
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

    touched = 0
    success = True
    for path in remove_list:
      result = remove_path(path, force, verbose, quiet)
      touched += len(result.removed) + len(result.skipped)
      success = success and not result.errors
    if touched == 0 and success and not quiet:
      # A clean that printed nothing would leave the user wondering whether it
      # ran at all.
      printc.note(
        "Nothing to clean: none of the " + str(len(remove_list)) + " patterns of \""
        + display_path(settings_filename) + "\" matches anything",
        script_name,
      )
    return success

######################################
# Main
######################################

def main(args, settings=None): 
  # Get settings
  if settings is None:
    settings = OdatixSettings(args.config)
    if not settings.valid:
      sys.exit(-1)

  settings_file = args.settings_file
  if settings_file is None:
    settings_file = settings.clean_settings_file
  elif not os.path.isfile(settings_file):
    # Named on purpose: falling back to another profile would remove what the
    # user did not ask for.
    printc.error("Settings file \"" + settings_file + "\" does not exist", script_name)
    return False

  return clean(
    settings_filename=settings_file,
    force=args.force,
    verbose=args.verbose,
    quiet=args.quiet
  )

if __name__ == "__main__":
  args = parse_arguments()
  main(args)

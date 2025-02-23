
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

import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings
from odatix.lib.config_generator import ConfigGenerator
from odatix.lib.architecture_handler import ArchitectureHandler
from odatix.lib.utils import ask_to_continue

script_name = os.path.basename(__file__)

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument("-o", "--overwrite", action="store_true", help="overwrite existing results")
  parser.add_argument("-y", "--noask", action="store_true", help="do not ask to continue")
  parser.add_argument("-a", "--archpath", help="architecture directory")
  parser.add_argument("-D", "--debug", action="store_true", help="enable debug mode to help troubleshoot settings files")
  parser.add_argument(
    "-c",
    "--config",
    default=OdatixSettings.DEFAULT_SETTINGS_FILE,
    help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
  )


def parse_arguments():
  parser = argparse.ArgumentParser(description="Run synthesis at specigied frequencies on selected architectures")
  add_arguments(parser)
  return parser.parse_args()


######################################
# Generate Configs
######################################

def generate_configs(arch_path, overwrite, noask, debug=False):
  """
  Traverse the architecture directory and generate configurations based on _settings.yml files.

  Args:
      arch_path (str): Root architecture directory.
      overwrite (bool): Whether to overwrite existing configuration files.
      noask (bool): Whether to skip user confirmation prompts.
  """
  if not os.path.isdir(arch_path):
    printc.error(f"Architecture path '{arch_path}' does not exist or is not a directory.", script_name)
    sys.exit(-1)

  new_configs = []         # List of configurations that will be newly created
  existing_configs = []    # List of configurations that already exist (and won't be generated)
  overwrite_configs = []   # List of configurations that will be overwritten
  error_configs = []       # List of configurations skipped due to invalid settings

  # First pass: Collect information about which files will be generated
  for root, _, files in sorted(os.walk(arch_path, topdown=True), key=lambda x: x[0].lower()):
    for file in files:
      if file == hard_settings.param_settings_filename:  # "_settings.yml"
        settings_file_path = os.path.join(root, file)

        if debug:
          printc.note(f"Processing settings file: {settings_file_path}", script_name)

        # Generate configurations using ConfigGenerator
        generator = ConfigGenerator(root, debug)
        
        if not generator.enabled:
          if debug:
            printc.note(f"Generation is not enabled for {settings_file_path}", script_name)
          continue

        if not generator.valid:
          printc.warning(f"Skipping {settings_file_path}: invalid settings.", script_name)
          error_configs.append(settings_file_path)
          continue

        generated_params = generator.generate()

        if not generated_params:
          error_configs.append(settings_file_path)
          continue

        # Determine the status of each generated configuration file
        for config_name in generated_params.keys():
          config_file_path = os.path.join(root, f"{config_name}.txt")

          if os.path.exists(config_file_path):
            if overwrite:
              overwrite_configs.append(config_file_path)
            else:
              existing_configs.append(config_file_path)
          else:
            new_configs.append(config_file_path)

  # Print summary before proceeding
  print()
  ArchitectureHandler.print_arch_list(new_configs, "New configurations", printc.colors.ENDC)
  ArchitectureHandler.print_arch_list(existing_configs, "Existing configurations (skipped -> use '-o' to overwrite)", printc.colors.CYAN)
  ArchitectureHandler.print_arch_list(overwrite_configs, "Existing configurations (will be overwritten)", printc.colors.YELLOW)
  ArchitectureHandler.print_arch_list(error_configs, "Invalid settings (skipped, see errors above)", printc.colors.RED)
  
  valid_configs = new_configs + overwrite_configs

  # Ask user confirmation 
  if len(valid_configs) > 0:
    if not noask:
      print()
      ask_to_continue()
  else:
    sys.exit(-1)
  print()

  # Second pass: Actually write the configuration files
  for config_file_path in valid_configs:
    config_name = os.path.basename(config_file_path).replace(".txt", "")
    root = os.path.dirname(config_file_path)

    # Reload the generator for this directory
    generator = ConfigGenerator(root, silent=True)
    generated_params = generator.generate()

    if config_name in generated_params:
      try:
        with open(config_file_path, "w") as config_file:
          config_file.write(generated_params[config_name] + "\n")
        printc.note(f"Generated {config_file_path}", script_name)
      except Exception as e:
        printc.error(f"Failed to write {config_file_path}: {e}", script_name)


######################################
# Main
######################################


def main(args, settings=None):
  # Get settings
  if settings is None:
    settings = OdatixSettings(args.config)
    if not settings.valid:
      sys.exit(-1)

  if args.archpath is not None:
    arch_path = args.archpath
  else:
    arch_path = settings.arch_path

  overwrite = args.overwrite
  noask = args.noask
  debug = args.debug

  generate_configs(arch_path, overwrite, noask, debug)

if __name__ == "__main__":
  args = parse_arguments()
  main(args)

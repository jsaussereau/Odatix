
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
  parser.add_argument(
    "-a",
    "--archpath",
    nargs="?",
    const="",
    help="architecture directory (optional path, default from settings if omitted)",
  )
  parser.add_argument(
    "-w",
    "--workflowpath",
    nargs="?",
    const="",
    help="workflow directory (optional path, default from settings if omitted)",
  )
  parser.add_argument("-D", "--debug", action="store_true", help="enable debug mode to help troubleshoot settings files")
  parser.add_argument(
    "-c",
    "--config",
    default=OdatixSettings.DEFAULT_SETTINGS_FILE,
    help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
  )


def parse_arguments():
  parser = argparse.ArgumentParser(description="Generate configurations from architecture/workflow parameter domains")
  add_arguments(parser)
  return parser.parse_args()


######################################
# Generate Configs
######################################

def collect_configs(path, overwrite, debug=False, path_kind="config"):
  new_configs = []         # List of configurations that will be newly created
  existing_configs = []    # List of configurations that already exist (and won't be generated)
  overwrite_configs = []   # List of configurations that will be overwritten
  error_configs = []       # List of configurations skipped due to invalid settings

  if not os.path.isdir(path):
    printc.error(f"{path_kind.capitalize()} path '{path}' does not exist or is not a directory.", script_name)
    sys.exit(-1)

  # First pass: Collect information about which files will be generated
  for root, _, files in sorted(os.walk(path, topdown=True), key=lambda x: x[0].lower()):
    for file in files:
      if file == hard_settings.param_settings_filename:  # "_settings.yml"
        settings_file_path = os.path.join(root, file)

        if debug:
          printc.note(f"Processing settings file: {settings_file_path}", script_name)

        # Generate configurations using ConfigGenerator
        generator = ConfigGenerator(path=root, debug=debug)
        
        if not generator.enabled:
          if debug:
            printc.note(f"Generation is not enabled for {settings_file_path}", script_name)
          continue

        if not generator.valid:
          printc.warning(f"Skipping {settings_file_path}: invalid settings.", script_name)
          error_configs.append(settings_file_path)
          continue

        generated_params, _ = generator.generate()

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

  valid_configs = new_configs + overwrite_configs
  return existing_configs, overwrite_configs, new_configs, error_configs, valid_configs


def print_summary(path, path_kind, existing_configs, overwrite_configs, new_configs, error_configs):
  print()
  printc.header(f"{path_kind.capitalize()} path: {path}")
  ArchitectureHandler.print_arch_list(existing_configs, "Existing configurations (skipped -> use '-o' to overwrite)", printc.colors.CYAN)
  ArchitectureHandler.print_arch_list(overwrite_configs, "Existing configurations (will be overwritten)", printc.colors.YELLOW)
  ArchitectureHandler.print_arch_list(new_configs, "New configurations", printc.colors.ENDC)
  ArchitectureHandler.print_arch_list(error_configs, "Invalid settings (skipped, see errors above)", printc.colors.RED)


def write_configs(valid_configs):
  # Second pass: Actually write the configuration files
  for config_file_path in valid_configs:
    config_name = os.path.basename(config_file_path).replace(".txt", "")
    root = os.path.dirname(config_file_path)

    # Reload the generator for this directory
    generator = ConfigGenerator(path=root, silent=True)
    generated_params, _ = generator.generate()

    if config_name in generated_params:
      try:
        with open(config_file_path, "w") as config_file:
          config_file.write(generated_params[config_name])
        printc.note(f"Generated {config_file_path}", script_name)
      except Exception as e:
        printc.error(f"Failed to write {config_file_path}: {e}", script_name)


def generate_configs(path, overwrite, noask, debug=False, path_kind="config"):
  """
  Traverse a directory and generate configurations based on _settings.yml files.

  Args:
      path (str): Root directory to traverse.
      overwrite (bool): Whether to overwrite existing configuration files.
      noask (bool): Whether to skip user confirmation prompts.
      debug (bool): Enable debug logging.
      path_kind (str): Human-readable path kind used in logs.
  """
  existing_configs, overwrite_configs, new_configs, error_configs, valid_configs = collect_configs(
    path=path,
    overwrite=overwrite,
    debug=debug,
    path_kind=path_kind,
  )

  print_summary(path, path_kind, existing_configs, overwrite_configs, new_configs, error_configs)

  # Ask user confirmation 
  if len(valid_configs) > 0:
    if not noask:
      print()
      ask_to_continue()
  else:
    sys.exit(-1)
  print()

  write_configs(valid_configs)


######################################
# Main
######################################


def main(args, settings=None):
  # Get settings
  if settings is None:
    settings = OdatixSettings(args.config)
    if not settings.valid:
      sys.exit(-1)

  def resolve_requested_path(arg_value, default_path):
    if arg_value is None:
      return None
    if arg_value == "":
      return default_path
    return arg_value

  overwrite = args.overwrite
  noask = args.noask
  debug = args.debug
  arch_path = settings.arch_path
  workflow_path = settings.workflow_path

  requested_arch_path = resolve_requested_path(args.archpath, arch_path)
  requested_workflow_path = resolve_requested_path(args.workflowpath, workflow_path)

  explicit_target = args.archpath is not None or args.workflowpath is not None

  selected_paths = []
  if requested_arch_path is not None:
    selected_paths.append((requested_arch_path, "architecture"))
  if requested_workflow_path is not None:
    selected_paths.append((requested_workflow_path, "workflow"))

  # Default behavior: generate for both architectures and workflows
  if not selected_paths:
    selected_paths = [
      (arch_path, "architecture"),
      (workflow_path, "workflow"),
    ]

  # Remove duplicates while preserving order
  dedup_selected_paths = []
  seen = set()
  for selected_path, path_kind in selected_paths:
    normalized_path = str(selected_path)
    key = (os.path.realpath(normalized_path), path_kind)
    if key not in seen:
      seen.add(key)
      dedup_selected_paths.append((normalized_path, path_kind))

  generated_any = False
  all_valid_configs = []

  for selected_path, path_kind in dedup_selected_paths:
    if not os.path.isdir(selected_path):
      if explicit_target:
        printc.error(f"{path_kind.capitalize()} path '{selected_path}' does not exist or is not a directory.", script_name)
        sys.exit(-1)
      else:
        printc.warning(f"Skipping missing {path_kind} path '{selected_path}'.", script_name)
        continue

    existing_configs, overwrite_configs, new_configs, error_configs, valid_configs = collect_configs(
      path=selected_path,
      overwrite=overwrite,
      debug=debug,
      path_kind=path_kind,
    )

    print_summary(selected_path, path_kind, existing_configs, overwrite_configs, new_configs, error_configs)
    print()

    if valid_configs:
      generated_any = True
      all_valid_configs.extend(valid_configs)

  if not generated_any:
    printc.error("No valid architecture/workflow path found for configuration generation.", script_name)
    sys.exit(-1)

  # Remove duplicates while preserving order
  dedup_valid_configs = []
  seen_valid = set()
  for config_file_path in all_valid_configs:
    if config_file_path not in seen_valid:
      seen_valid.add(config_file_path)
      dedup_valid_configs.append(config_file_path)

  if not noask:
    ask_to_continue()

  print()
  write_configs(dedup_valid_configs)

if __name__ == "__main__":
  args = parse_arguments()
  main(args)

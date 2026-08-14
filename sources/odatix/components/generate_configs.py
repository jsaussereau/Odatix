
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
from collections import namedtuple

import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings
from odatix.lib.architecture_handler import ArchitectureHandler
import odatix.workspace.space as space
from odatix.workspace.errors import WorkspaceError
from odatix.lib.utils import ask_to_continue

script_name = os.path.basename(__file__)

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument("-o", "--overwrite", action="store_true", help="take configurations edited by hand back to what their rules say")
  parser.add_argument("-C", "--clean", action="store_true", help="delete the configurations an earlier generation wrote and the rules no longer describe")
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

#: What generating would do, as :func:`collect_configs` reports it.
GenerationPlan = namedtuple(
  "GenerationPlan",
  ["existing", "overwrite", "new", "errors", "valid", "edited", "leftovers"],
)


def domain_paths(path):
  """The directories under `path` that hold a settings file, in a stable order."""
  found = []
  for root, _, files in sorted(os.walk(path, topdown=True), key=lambda x: x[0].lower()):
    if hard_settings.param_settings_filename in files:
      found.append(root)
  return found


def collect_configs(path, overwrite, debug=False, path_kind="config", clean=False):
  """
  What generating would do, without doing any of it.

  Everything is decided by resolving each domain (see
  :class:`odatix.workspace.space.ConfigSet`): a configuration whose file is
  missing is new, one whose file still holds what was generated is up to date,
  and one whose file was edited by hand is only touched when it is asked for.
  """
  new_configs = []         # Configurations that will be newly created
  existing_configs = []    # Configurations already up to date (nothing to do)
  edited_configs = []      # Configurations edited by hand (kept, unless overwriting)
  overwrite_configs = []   # Configurations whose edit will be dropped
  leftover_configs = []    # Files an earlier generation wrote and the rules no longer describe
  error_configs = []       # Domains skipped because their settings are invalid

  if not os.path.isdir(path):
    printc.error(f"{path_kind.capitalize()} path '{path}' does not exist or is not a directory.", script_name)
    sys.exit(-1)

  for root in domain_paths(path):
    settings_file_path = os.path.join(root, hard_settings.param_settings_filename)

    if debug:
      printc.note(f"Processing settings file: {settings_file_path}", script_name)

    config_set = space.config_set_at(root, debug=debug)
    if not config_set.space.generates:
      if debug:
        printc.note(f"No configurations are described in {settings_file_path}", script_name)
      continue

    if not config_set.space.valid:
      printc.warning(f"Skipping {settings_file_path}: invalid settings.", script_name)
      error_configs.append(settings_file_path)
      continue

    try:
      resolved = config_set.resolve()
    except WorkspaceError as e:
      printc.error(str(e), script_name)
      error_configs.append(settings_file_path)
      continue

    files = config_set.files()
    for config in resolved:
      if not config.from_rules:
        continue
      config_file_path = os.path.join(root, config.filename)
      if config.origin == space.ORIGIN_EDITED:
        (overwrite_configs if overwrite else edited_configs).append(config_file_path)
      elif config.name in files:
        existing_configs.append(config_file_path)
      else:
        new_configs.append(config_file_path)

    if clean:
      for name in config_set.leftovers():
        leftover_configs.append(os.path.join(root, name + ".txt"))

  # Writing a configuration that is already what it should be costs nothing and
  # keeps the manifest in step with what is on disk, so it is not skipped.
  valid_configs = new_configs + overwrite_configs + existing_configs
  return GenerationPlan(
    existing=existing_configs,
    overwrite=overwrite_configs,
    new=new_configs,
    errors=error_configs,
    valid=valid_configs,
    edited=edited_configs,
    leftovers=leftover_configs,
  )


def print_summary(path, path_kind, plan):
  print()
  printc.header(f"{path_kind.capitalize()} path: {path}")
  ArchitectureHandler.print_arch_list(plan.new, "New configurations", printc.colors.ENDC)
  ArchitectureHandler.print_arch_list(plan.existing, "Up to date configurations", printc.colors.CYAN)
  ArchitectureHandler.print_arch_list(plan.edited, "Configurations edited by hand (kept -> use '-o' to regenerate)", printc.colors.CYAN)
  ArchitectureHandler.print_arch_list(plan.overwrite, "Configurations edited by hand (edits will be dropped)", printc.colors.YELLOW)
  ArchitectureHandler.print_arch_list(plan.leftovers, "Leftovers of an earlier generation (will be deleted)", printc.colors.YELLOW)
  ArchitectureHandler.print_arch_list(plan.errors, "Invalid settings (skipped, see errors above)", printc.colors.RED)


def write_configs(valid_configs, overwrite=False, clean=False):
  """
  Write what was announced, one domain at a time.

  Each domain is materialized as a whole, which is also what records the
  manifest that a later generation reads to tell an edit from what it wrote
  itself.
  """
  roots = []
  for config_file_path in valid_configs:
    root = os.path.dirname(config_file_path)
    if root not in roots:
      roots.append(root)

  for root in roots:
    config_set = space.config_set_at(root)
    try:
      written = config_set.materialize(overwrite=overwrite, prune=clean)
    except Exception as e:
      printc.error(f"Failed to generate the configurations of \"{root}\": {e}", script_name)
      continue
    for name in written:
      printc.note(f"Generated {os.path.join(root, name + '.txt')}", script_name)


def generate_configs(path, overwrite, noask, debug=False, path_kind="config", clean=False):
  """
  Traverse a directory and generate configurations based on _settings.yml files.

  Generating is no longer a step to run before anything else -- a run resolves
  what it needs on its own. It stays here for a workspace that would rather keep
  its configurations as files: to read them, to track them, or to edit one by
  hand.

  Args:
      path (str): Root directory to traverse.
      overwrite (bool): Whether to take configurations edited by hand back to
          what their rules say.
      noask (bool): Whether to skip user confirmation prompts.
      debug (bool): Enable debug logging.
      path_kind (str): Human-readable path kind used in logs.
      clean (bool): Delete what an earlier generation left behind and the rules
          no longer describe.
  """
  plan = collect_configs(
    path=path,
    overwrite=overwrite,
    debug=debug,
    path_kind=path_kind,
    clean=clean,
  )

  print_summary(path, path_kind, plan)

  # Ask user confirmation
  if len(plan.valid) > 0:
    if not noask:
      print()
      ask_to_continue()
  else:
    sys.exit(-1)
  print()

  write_configs(plan.valid, overwrite=overwrite, clean=clean)


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
  clean = getattr(args, "clean", False)
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

    plan = collect_configs(
      path=selected_path,
      overwrite=overwrite,
      debug=debug,
      path_kind=path_kind,
      clean=clean,
    )

    print_summary(selected_path, path_kind, plan)
    print()

    if plan.valid:
      generated_any = True
      all_valid_configs.extend(plan.valid)

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
  write_configs(dedup_valid_configs, overwrite=overwrite, clean=clean)

if __name__ == "__main__":
  args = parse_arguments()
  main(args)

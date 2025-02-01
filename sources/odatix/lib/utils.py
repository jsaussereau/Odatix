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

"""
This module contains utility functions for file operations, error handling,
and user interactions within Odatix.

Functions:
    - copytree: Custom function to copy directories with filtering options.
    - chunk_list: Splits a list into smaller chunks of a given size.
    - read_from_list: Reads and validates values from a dictionary.
    - read_from_config: Reads a value from a configuration file.
    - move_cursor_up: Moves the cursor up in the terminal.
    - progress_bar: Displays a progress bar in the terminal.
    - ask_to_continue: Prompts the user to continue or exit.
    - ask_yes_no: Prompts the user for a yes/no input.
    - create_dir: Creates a directory, removing it first if it exists.
    - internal_error: Logs internal errors and prints an error message.
    - safe_df_append: Safely appends data to a pandas DataFrame.
    - open_path_in_explorer: Opens a file or directory in the system explorer.
"""

import os
import sys
import glob
import shutil
import fnmatch
import platform
import traceback
import subprocess
from datetime import datetime

import odatix.lib.printc as printc
import odatix.components.motd

YAML_BOOL = ('true', 'false', 'yes', 'no', 'on', 'off')

def copytree(src, dst, dirs_exist_ok=False, whitelist=None, blacklist=None, **kwargs):
  """
  Custom copytree to copy directories with support for dirs_exist_ok, whitelist, and blacklist.

  Args:
    src (str): Source directory.
    dst (str): Destination directory.
    dirs_exist_ok (bool): Whether to allow overwriting the destination directory.
    whitelist (list, optional): List of patterns to include (relative to `src`).
    blacklist (list, optional): List of patterns to exclude (relative to `src`).
    **kwargs: Additional arguments passed to shutil.copy2.
  """
  def is_pattern_matched(path, patterns):
    """
    Check if the path matches any pattern in the list.
    Args:
      path (str): The path to check (relative to `src`).
      patterns (list): List of patterns to match against.
    Returns:
      bool: True if any pattern matches, False otherwise.
    """
    for pattern in patterns:
      if fnmatch.fnmatch(path, pattern):
        return True
      if os.path.realpath(pattern) == os.path.realpath(path):
        return True
      if os.path.dirname(os.path.realpath(path)).startswith(os.path.realpath(pattern)):
        return True
    return False

  def should_copy_file(rel_path):
    """
    Determine if a file should be copied based on whitelist and blacklist.
    Args:
      rel_path (str): Relative path to check.
    Returns:
      bool: True if the file should be copied, False otherwise.
    """
    # If whitelist exists, only copy paths matching the whitelist
    if whitelist and not is_pattern_matched(rel_path, whitelist) and not os.path.isdir(rel_path):
      return False
    # Exclude paths matching the blacklist
    if blacklist and is_pattern_matched(rel_path, blacklist):
      return False
    # Default: copy the path
    return True

  def should_explore_dir(rel_path):
    """
    Determine if a directory should be explored based on the blacklist.
    The whitelist does not apply to directories for exploration.
    Args:
      rel_path (str): Relative path to check.
    Returns:
      bool: True if the directory should be explored, False otherwise.
    """
    # Exclude directories matching the blacklist
    if blacklist and is_pattern_matched(rel_path, blacklist):
      return False
    # Default: explore the directory
    return True

  # Normalize paths
  src = os.path.realpath(src)
  dst = os.path.realpath(dst)

  # Ensure destination exists
  if os.path.exists(dst):
    if not dirs_exist_ok:
      raise FileExistsError(f"Destination directory {dst} exists and dirs_exist_ok is False.")
  else:
    os.makedirs(dst)

  for root, dirs, files in os.walk(src):
    # Calculate the relative path from src
    rel_root = os.path.relpath(root, src)

    # Remove directories that should not be explored
    dirs[:] = [d for d in dirs if should_explore_dir(os.path.join(rel_root, d))]

    # Process files
    for file in files:
      src_file = os.path.join(root, file)
      rel_file = os.path.join(rel_root, file)  # Relative path for whitelist/blacklist checks
      dst_file = os.path.join(dst, rel_file)
      
      if should_copy_file(rel_file):  # Pass relative path to should_copy_file
        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
        shutil.copy2(src_file, dst_file, **kwargs)

def chunk_list(lst, n):
  """Splits a list into chunks of size n."""
  for i in range(0, len(lst), n):
    yield lst[i:i + n]

class KeyNotInListError(Exception):
  """Exception raised when a required key is missing in a list."""
  pass

class BadValueInListError(Exception):
  """Exception raised when a value in a list is of the wrong type."""
  pass

def read_from_list(key, input_list, filename, raise_if_missing=True, optional=False, print_error=True, parent=None, type=None, script_name=""):
  """
  Retrieves a value from a dictionary, with error handling and type validation.
  """
  parent_string = "" if parent == None else ", inside list \"" + parent + "\","
  if key in input_list:
    value = input_list[key]
    if type is None:
      return value
    else:
      if isinstance(value, type):
        return value
      else:
        if print_error:
          if optional:
            printc.note("Value \"" + str(value) + "\" for key \"" + key + "\"" + parent_string + " in \"" + filename + "\" is of type \"" + value.__class__.__name__ + "\" while it should be of type \"" + type.__name__ + "\". Using default values instead.", script_name)
          else:
            printc.error("Value \"" + str(value) + "\" for key \"" + key + "\"" + parent_string + " in \"" + filename + "\" is of type \"" + value.__class__.__name__ + "\" while it should be of type \"" + type.__name__ + "\".", script_name)
        if raise_if_missing:
          raise BadValueInListError
        return False
  else:
    if print_error:
      if optional:
        printc.note("Cannot find optional key \"" + key + "\"" + parent_string + " in \"" + filename + "\". Using default values instead.", script_name)
      else:
        printc.error("Cannot find key \"" + key + "\"" + parent_string + " in \"" + filename + "\".", script_name)
    if raise_if_missing:
      raise KeyNotInListError
    return False

def read_from_config(identifier, config, filename, script_name=""):
  if identifier in config[settings_ini_section]:
    return config[settings_ini_section][identifier]
  else:
    printc.error("Cannot find identifier \"" + identifier + "\" in \"" + filename + "\".", script_name)
    raise
    return False

def move_cursor_up():
  """Moves the terminal cursor up one line."""
  sys.stdout.write('\x1b[1A') # Move cursor up
  sys.stdout.write("\033[K") # Clear to the end of line
  sys.stdout.flush()

def progress_bar(progress, title, title_size=50, bar_size=50, endstr='', progress_char="#"):
  """Displays a progress bar in the terminal."""
  if progress is None:
    limit = 1
  else:
    if progress > 100:
      progress = 100
    limit = int(progress * bar_size / 100)

  padded_title = title.ljust(title_size)

  print(padded_title + " [", end='')
  if progress is None:
    printc.color(printc.colors.BLINK)
  for i in range(0, limit):
    print(progress_char, end='')
  for i in range(limit, bar_size):
    print(' ', end='')
  if progress is None:
    printc.color(printc.colors.ENDC)
  print("]", end='')
  if progress is not None:
    print(" {}%".format(int(progress)) + endstr)
  else:
    print()

def ask_to_continue(exit_code=-1):
  print("Continue? ", end="")
  answer = ask_yes_no()
  if answer is False:
    sys.exit(exit_code)
    
def ask_yes_no():
  while True:
    answer = input("(Y/n) ")
    if answer.lower() in ['yes', 'ye', 'y', '1', '']:
      return True
    elif answer.lower() in ['no', 'n', '0']:
      return False
    else:
      print("Please enter yes or no")

def create_dir(dir):
  """Creates a directory, removing it first if it exists."""
  if os.path.isdir(dir):
    shutil.rmtree(dir)
  os.makedirs(dir)

def internal_error(e, error_logfile, script_name):
  tb_full = traceback.format_exc()
  command_line = ' '.join(sys.argv)
  current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  system_info = {
    "OS": platform.system(),
    "OS Version": platform.version(),
    "Python Version": platform.python_version(),
    "Machine": platform.machine(),
  }
  with open(error_logfile, "w") as log_file:
    log_file.write("Date and Time: " + current_time + "\n\n")
    log_file.write("System Information:\n")
    for key, value in system_info.items():
      log_file.write("  " + key + ": " + value + "\n")
    log_file.write("\nOdatix Version: " + str(odatix.components.motd.read_version()) + "\n\n")
    log_file.write("\nCommand:\n")
    log_file.write("  " + command_line + "\n\n")
    log_file.write(tb_full)
  printc.internal_error(type(e).__name__ + ": " + str(e), script_name)
  printc.note('Full error details written to "' + error_logfile + '"', script_name)
  printc.note("Please, report this error with the error log attached", script_name)

def safe_df_append(df, row, ignore_index=True):
  if hasattr(df, 'append'):
    return df.append(row, ignore_index=ignore_index)
  else:
    return df._append(row, ignore_index=ignore_index)

def open_path_in_explorer(path):
  """Opens the given path in the system file explorer."""
  if sys.platform.startswith("win"): # Windows
    os.startfile(path)
  elif sys.platform.startswith("linux"): # Linux
    subprocess.run(["xdg-open", path])
  elif sys.platform.startswith("darwin"): # macOS
    subprocess.run(["open", path])
  else:
    raise NotImplementedError(f"Unsupported platform: {platform}")

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
import shutil
import platform
import traceback
from datetime import datetime

import odatix.lib.printc as printc

YAML_BOOL = ('true', 'false', 'yes', 'no', 'on', 'off')

# python 3.8+ like copytree
def copytree(src, dst, dirs_exist_ok=False, **kwargs):
  if not os.path.exists(dst):
    shutil.copytree(src, dst, **kwargs)
  else:
    if dirs_exist_ok:
      for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
          shutil.rmtree(d, ignore_errors=True)
          shutil.copytree(s, d, **kwargs)
        else:
          shutil.copy2(s, d)
    else:
      raise

def chunk_list(lst, n):
  for i in range(0, len(lst), n):
    yield lst[i:i + n]

class KeyNotInListError(Exception):
  pass

class BadValueInListError(Exception):
  pass

def read_from_list(key, input_list, filename, raise_if_missing=True, optional=False, print_error=True, parent=None, type=None, script_name=""):
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
  sys.stdout.write('\x1b[1A') # Move cursor up
  sys.stdout.write("\033[K") # Clear to the end of line
  sys.stdout.flush()

def progress_bar(progress, title, title_size=50, bar_size=50, endstr='', progress_char="#"):
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
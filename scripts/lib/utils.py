#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

import os
import sys
import shutil
import printc

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
          shutil.copytree(s, d, **kwargs)
        else:
          shutil.copy2(s, d)
    else:
      raise

def chunk_list(lst, n):
  for i in range(0, len(lst), n):
    yield lst[i:i + n]

def read_from_list(key, input_list, filename, raise_if_missing=True, optional=False, print_error=True, parent=None, script_name=""):
  if key in input_list:
    return input_list[key]
  else:
    parent_string = "" if parent == None else ", inside list \"" + parent + "\","
    if print_error:
      if optional:
        printc.note("Cannot find optional key \"" + key + "\"" + parent_string + " in \"" + filename + "\". Using default values instead.", script_name)
      else:
        printc.error("Cannot find key \"" + key + "\"" + parent_string + " in \"" + filename + "\".", script_name)
    if raise_if_missing:
      raise
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

def progress_bar(progress, title, title_size=50, bar_size=50, endstr=''):
  if progress > 100:
    progress = 100
  
  limit = int(progress * bar_size / 100)
  padded_title = title.ljust(title_size)

  print(padded_title + " [", end = '')
  for i in range(0, limit):
    print('#', end = '')
  for i in range(limit, bar_size):
    print(' ', end = '')
  print("] {}%".format(int(progress)) + endstr)

def ask_to_continue():
  while True:
    answer = input("Continue? (Y/n) ")
    if answer.lower() in ['yes', 'ye', 'y', '1', '']:
      break
    elif answer.lower() in ['no', 'n', '0']:
      sys.exit()
    else:
      print("Please enter yes or no")
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

# Add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, 'lib')
sys.path.append(lib_path)

import printc

version_file = "version.txt"

def motd():
  print(printc.colors.BOLD, end="")
  print("********************************************************************")
  print("*                             Asterism                             *")
  print("********************************************************************")
  print(printc.colors.ENDC)

def read_version():
  try:
    with open(version_file, 'r') as file:
      return file.read().strip()
  except:
    #printc.warning("Could not read version file \"" + version_file + "\"")
    return "Unknown"

def print_version():
  version = read_version()
  print("Asterism " + str(version))

def print_copyright():
  print("Copyright (C) 2022-2024 Jonathan Saussereau")

def full_header(description=""):
  motd()
  if description != "":
    print(description)
  print_copyright()
  print()
  print("version: " + str(read_version()))
  print()

if __name__ == "__main__":
  motd()

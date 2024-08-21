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

current_dir = os.path.dirname(os.path.abspath(__file__))

# get eda_tools folder
if getattr(sys, 'frozen', False):
  base_path = os.path.dirname(sys.executable)
  
else:
  base_path = current_dir

######################################
# Settings
######################################

version_file = os.path.realpath(os.path.join(base_path, os.pardir, "version.txt"))

######################################
# Parse Arguments
######################################

def add_arguments(parser):
  parser.add_argument('-f', '--full', action='store_true', help='show full motd')

def parse_arguments():
  parser = argparse.ArgumentParser(description="Odatix's message of the day")
  add_arguments(parser)
  return parser.parse_args()

######################################
# Message of the day
######################################

def motd():
  try:
    print()
    print(" ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗")
    print("██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝")
    print("██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ ")
    print("██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ ")
    print("╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗")
    print(" ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝")   
  except:
    print()
    print(r" ######\         ##\              ##\      ##\            ")
    print(r"##  __##\        ## |             ## |     \__|           ")
    print(r"## /  ## |  ####### |  ######\  ######\    ##\  ##\   ##\ ")
    print(r"## |  ## | ##  __## |  \____##\ \_##  _|   ## | \##\ ##  |")
    print(r"## |  ## | ## /  ## |  ####### |  ## |     ## |  \####  / ")
    print(r"## |  ## | ## |  ## | ##  __## |  ## |##\  ## |  ##  ##\  ")
    print(r" ######  | \####### | \####### |  \####  | ## | ##  /\##\ ")
    print(r" \______/   \_______|  \_______|   \____/  \__| \__/  \__|")
    print()

def full_header(description=True):
  motd()
  if description:
    print("Odatix - a FPGA/ASIC toolbox for design space exploration")
  print_copyright()
  print()
  print("version: " + str(read_version()))
  print()

def print_copyright():
  print("Copyright (C) 2022-2024 Jonathan Saussereau")

######################################
# Version
######################################

def read_version():
  try:
    with open(version_file, 'r') as file:
      return file.read().strip()
  except:
    printc.warning("Could not read version file \"" + version_file + "\"")
    return "Unknown"

def print_version():
  version = read_version()
  print("Odatix " + str(version))

######################################
# Main
######################################

if __name__ == "__main__":
  args = parse_arguments()
  
  if args.full:
    full_header()
  else:
    motd()

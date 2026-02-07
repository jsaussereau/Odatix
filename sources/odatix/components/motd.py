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
This script displays the message of the day (MOTD) for Odatix, checks for updates,
and prints version information.

Functions:
    - add_arguments: Adds command-line arguments for the script.
    - parse_arguments: Parses command-line arguments.
    - motd: Displays the message of the day for Odatix.
    - full_header: Prints the full MOTD along with version and copyright.
    - print_copyright: Displays copyright information.
    - read_version: Reads the installed version of Odatix.
    - print_version: Prints the installed version.
    - check_for_update: Checks PyPI for a newer version of Odatix.
"""

import os
import sys
import argparse
import requests

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

def motd(check_updates=True):
  """Displays the message of the day (MOTD)."""
  try:
    print()
    print(" ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗", end="\r\n")
    print("██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝", end="\r\n")
    print("██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ ", end="\r\n")
    print("██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ ", end="\r\n")
    print("╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗", end="\r\n")
    print(" ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝", end="\r\n")   
  except:
    print()
    print(r" ######\         ##\              ##\      ##\            ", end='\r\n')
    print(r"##  __##\        ## |             ## |     \__|           ", end='\r\n')
    print(r"## /  ## |  ####### |  ######\  ######\    ##\  ##\   ##\ ", end='\r\n')
    print(r"## |  ## | ##  __## |  \____##\ \_##  _|   ## | \##\ ##  |", end='\r\n')
    print(r"## |  ## | ## /  ## |  ####### |  ## |     ## |  \####  / ", end='\r\n')
    print(r"## |  ## | ## |  ## | ##  __## |  ## |##\  ## |  ##  ##\  ", end='\r\n')
    print(r" ######  | \####### | \####### |  \####  | ## | ##  /\##\ ", end='\r\n')
    print(r" \______/   \_______|  \_______|   \____/  \__| \__/  \__|", end='\r\n')
    print()
  if check_updates:
    check_for_update()

def full_header(description=True):
  """Displays the full header, including MOTD, version, and copyright."""
  motd()
  if description:
    print("Odatix - a FPGA/ASIC toolbox for design space exploration")
  print_copyright()
  print()
  print("version: " + str(read_version()))
  print()

def print_copyright():
  """Prints the copyright information."""
  print("Copyright (C) 2022-2026 Jonathan Saussereau")

######################################
# Version
######################################

def read_version():
  """Reads and returns the current installed version of Odatix."""
  try:
    with open(version_file, 'r') as file:
      return file.read().strip()
  except:
    printc.warning("Could not read version file \"" + version_file + "\"")
    return "Unknown"

def print_version():
  """Prints the current installed version of Odatix."""
  version = read_version()
  print("Odatix " + str(version))

def check_for_update():
  """Checks for a newer version of Odatix on PyPI."""
  installed_version = read_version()
  try:
    # Get last version code from PyPI
    response = requests.get("https://pypi.org/pypi/odatix/json", timeout=0.5)
    response.raise_for_status()
    latest_version = response.json()["info"]["version"]

    # Comparer les versions
    if installed_version < latest_version:
      printc.green(f"\nA new version of Odatix ({latest_version}) is available!")
      printc.note(f"You currently have Odatix {installed_version}.")
      printc.note("You can run ", end="")
      printc.grey("python3 -m pip install -U odatix", end="")
      printc.cyan(" to update.\n")

  except Exception as e:
    printc.warning("Could not check for updates")

######################################
# Main
######################################

if __name__ == "__main__":
  args = parse_arguments()
  
  if args.full:
    full_header()
  else:
    motd()

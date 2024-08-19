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
import yaml

import odatix.lib.printc as printc
from odatix.lib.utils import *

script_name = os.path.basename(__file__)

def get_synth_settings(settings_filename):
  # failsafe
  if settings_filename is None:
    printc.error("No settings file specified: get_synth_settings(settings_filename) -> settings_filename is None", script_name)
    sys.exit(-1)

  # get synth settings from yaml file
  if not os.path.isfile(settings_filename):
    printc.error("Settings file \"" + settings_filename + "\" does not exist", script_name)
    sys.exit(-1)

  with open(settings_filename, 'r') as f:
    try:
      settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    except Exception as e:
      printc.error("Settings file \"" + settings_filename + "\" is not a valid YAML file", script_name)
      printc.cyan("error details: ", end="", script_name=script_name)
      print(str(e))
      sys.exit(-1)
    try:
      overwrite       = read_from_list("overwrite", settings_data, settings_filename, type=bool, script_name=script_name)
      ask_continue    = read_from_list("ask_continue", settings_data, settings_filename, type=bool, script_name=script_name)
      show_log_if_one = read_from_list("show_log_if_one", settings_data, settings_filename, type=bool, script_name=script_name)
      nb_jobs         = read_from_list("nb_jobs", settings_data, settings_filename, type=int, script_name=script_name)
      architectures   = read_from_list("architectures", settings_data, settings_filename, script_name=script_name)
    except (KeyNotInListError, BadValueInListError):
      sys.exit(-1) # if a key is missing
  return overwrite, ask_continue, show_log_if_one, nb_jobs, architectures


def get_sim_settings(settings_filename):
  # failsafe
  if settings_filename is None:
    printc.error("No settings file specified: get_sim_settings(settings_filename) -> settings_filename is None", script_name)
    sys.exit(-1)

  # get sim settings from yaml file
  if not os.path.isfile(settings_filename):
    printc.error("Settings file \"" + settings_filename + "\" does not exist", script_name)
    sys.exit(-1)

  with open(settings_filename, 'r') as f:
    settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    try:
      overwrite       = read_from_list("overwrite", settings_data, settings_filename, type=bool, script_name=script_name)
      ask_continue    = read_from_list("ask_continue", settings_data, settings_filename, type=bool, script_name=script_name)
      show_log_if_one = read_from_list("show_log_if_one", settings_data, settings_filename, type=bool, script_name=script_name)
      nb_jobs         = read_from_list("nb_jobs", settings_data, settings_filename, type=int, script_name=script_name)
      simulations     = read_from_list("simulations", settings_data, settings_filename, script_name=script_name)
    except (KeyNotInListError, BadValueInListError):
      sys.exit(-1) # if a key is missing
  return overwrite, ask_continue, show_log_if_one, nb_jobs, simulations

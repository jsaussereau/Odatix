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
import yaml

# Add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, 'lib')
sys.path.append(lib_path)

import printc
from utils import *

script_name = os.path.basename(__file__)

######################################
# Settings
######################################

class AsterismSettings:
  DEFAULT_SETTINGS_FILE = "asterism.yml"

  DEFAULT_WORK_PATH = "work"
  DEFAULT_RESULT_PATH = "results"
  DEFAULT_ARCH_PATH = "architectures"
  DEFAULT_SIM_PATH = "simulations"
  DEFAULT_USE_BENCHMARK = True
  DEFAULT_BENCHMARK_FILE = "results/benchmark.yml"
  DEFAULT_SIMULATION_SETTINGS_FILE = "_run_simulations_settings.yml"
  DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE = "_run_fmax_synthesis_settings.yml"
  DEFAULT_RANGE_SYNTHESIS_SETTINGS_FILE = "_run_range_synthesis_settings.yml"

  def __init__(self, settings_filename=DEFAULT_SETTINGS_FILE):
    self.settings_file_exists = self.generate_settings_file()
    if self.settings_file_exists:
      success = self.read_settings_file(settings_filename)
    else:
      self.valid = False

  def read_settings_file(self, settings_filename=DEFAULT_SETTINGS_FILE):
    if not os.path.isfile(settings_filename):
      printc.error("Asterism settings file \"" + settings_filename + "\" does not exists.", script_name=script_name)
      printc.note("Asterism settings file should be in \"" + current_dir + "\"", script_name=script_name)
      self.valid = False
      return False

    with open(settings_filename, 'r') as f:
      settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
      try:
        self.work_path = read_from_list('work_path', settings_data, settings_filename, script_name=script_name)
        self.result_path = read_from_list('result_path', settings_data, settings_filename , script_name=script_name)
        self.arch_path = read_from_list('arch_path', settings_data, settings_filename , script_name=script_name)
        self.sim_path = read_from_list('sim_path', settings_data, settings_filename , script_name=script_name)
        self.use_benchmark = read_from_list('use_benchmark', settings_data, settings_filename, script_name=script_name)
        self.benchmark_file = read_from_list('benchmark_file', settings_data, settings_filename , script_name=script_name)
        self.simulation_settings_file = read_from_list('simulation_settings_file', settings_data, settings_filename , script_name=script_name)
        self.fmax_synthesis_settings_file = read_from_list('fmax_synthesis_settings_file', settings_data, settings_filename , script_name=script_name)
        self.range_synthesis_settings_file = read_from_list('range_synthesis_settings_file', settings_data, settings_filename , script_name=script_name)
      except Exception as e:
        self.valid = False
        return False
    self.valid = True
    return True
    
  def generate_settings_file(self, settings_filename=DEFAULT_SETTINGS_FILE):
    if os.path.isfile(settings_filename):
      return True
    else:
      printc.say("This directory does not contain an Asterism settings file \"" + settings_filename + "\".", script_name=script_name)
      printc.say("This file is mandatory. Would you like to create one? ", end="", script_name=script_name)
      answer = ask_yes_no()
      if answer is False:
        return False
      else:
        settings_data = {
          'work_path': input("  Enter work path [default: " + AsterismSettings.DEFAULT_WORK_PATH + "]: ") or AsterismSettings.DEFAULT_WORK_PATH,
          'result_path': input("  Enter result path [default: " + AsterismSettings.DEFAULT_RESULT_PATH + "]: ") or AsterismSettings.DEFAULT_RESULT_PATH,
          'arch_path': input("  Enter architecture path [default: " + AsterismSettings.DEFAULT_ARCH_PATH + "]: ") or AsterismSettings.DEFAULT_ARCH_PATH,
          'sim_path': input("  Enter simulation path [default: " + AsterismSettings.DEFAULT_SIM_PATH + "]: ") or AsterismSettings.DEFAULT_SIM_PATH,
          'use_benchmark': input("  Use benchmark (True/False) [default: " + str(AsterismSettings.DEFAULT_USE_BENCHMARK) + "]: ").lower() in AsterismSettings.YAML_BOOL or AsterismSettings.DEFAULT_USE_BENCHMARK,
          'benchmark_file': input("  Enter benchmark file path [default: " + AsterismSettings.DEFAULT_BENCHMARK_FILE + "]: ") or AsterismSettings.DEFAULT_BENCHMARK_FILE,
          'simulation_settings_file': input("  Enter simulation settings file [default: " + AsterismSettings.DEFAULT_SIMULATION_SETTINGS_FILE + "]: ") or AsterismSettings.DEFAULT_SIMULATION_SETTINGS_FILE,
          'fmax_synthesis_settings_file': input("  Enter fmax synthesis settings file [default: " + AsterismSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE + "]: ") or AsterismSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
          'range_synthesis_settings_file': input("  Enter range synthesis settings file [default: " + AsterismSettings.DEFAULT_RANGE_SYNTHESIS_SETTINGS_FILE + "]: ") or AsterismSettings.DEFAULT_RANGE_SYNTHESIS_SETTINGS_FILE
        }

        with open(settings_filename, 'w') as f:
          yaml.dump(settings_data, f, sort_keys=False)

        printc.say("Asterism settings file \"" + settings_filename + "\" has been generated.", script_name=script_name)
        print()
        return True
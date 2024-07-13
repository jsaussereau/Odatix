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

  def __init__(self, settings_filename=DEFAULT_SETTINGS_FILE):
    success = self.read_settings_file(settings_filename)

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
    

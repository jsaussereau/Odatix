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
import re
import sys
import math
import yaml

from architecture_handler import ArchitectureHandler

from os.path import isfile
from os.path import isdir

import utils
from utils import *

script_name = os.path.basename(__file__)

tcl_bool_true = ['true', 'yes', 'on', '1']
tcl_bool_false = ['false', 'no', 'off', '0']

class Simulation:
  def __init__(self, sim_name, sim_display_name, architecture, tmp_dir, source_sim_dir, simulation_command):
    self.sim_name = sim_name
    self.sim_display_name = sim_display_name
    self.architecture = architecture
    self.tmp_dir = tmp_dir
    self.source_sim_dir = source_sim_dir
    self.simulation_command = simulation_command
    

class SimulationHandler:

  def __init__(self, work_path, arch_path, sim_path, script_path, work_script_path, log_path, param_settings_filename, overwrite):
    self.work_path = work_path
    self.arch_path = arch_path
    self.sim_path = sim_path
    self.script_path = script_path
    self.work_script_path = work_script_path
    self.log_path = log_path
    self.overwrite = overwrite
    self.param_settings_filename = param_settings_filename

  def get_simulations(self, simulations):
    self.banned_sim_param = []
    self.valid_sims = []
    self.cached_sims = []
    self.overwrite_sims = []
    self.error_sims = []
    self.incomplete_sims = []
    self.new_sims = []

    self.simulation_instances = []

    arch_handler = ArchitectureHandler(
      work_path = self.work_path,
      arch_path = self.arch_path,
      script_path = self.script_path,
      work_script_path = self.work_script_path,
      log_path = self.log_path,
      eda_target_filename = "",
      fmax_status_filename = "",
      frequency_search_filename = "",
      param_settings_filename = self.param_settings_filename,
      valid_status = "",
      valid_frequency_search = "",
      default_fmax_lower_bound = 0,
      default_fmax_upper_bound = 1000,
      target_settings = None,
      overwrite = self.overwrite
    )

    if simulations is not None:
      for sim_dict in simulations:
        if sim_dict is not None:
          for sim, arch_list in sim_dict.items():
            if arch_list is not None and arch_list is not None:
              for arch in arch_list:
                simulation_instance = self.get_simulation(sim, arch, arch_handler)
                if simulation_instance is not None:
                  self.simulation_instances.append(simulation_instance)

    return self.simulation_instances
    
  
  def get_simulation(self, sim, arch, arch_handler):
    tmp_dir = self.work_path + '/' + sim + '/' + arch 

    sim_name = sim
    sim_display_name = sim + " (" + arch + ")"
    tmp_dir = tmp_dir
    simulation_command = None
    use_parameters = None
    start_delimiter = None
    stop_delimiter = None
    design_path = None
    generate_rtl = None
    generate_command = None

    # check if sim has been banned
    if sim in self.banned_sim_param:
      self.error_sims.append(sim_display_name)
      return None

    # check if sim dir exists
    source_sim_dir = self.sim_path + '/' + sim
    if not isdir(source_sim_dir):
      printc.error("There is no directory \"" + sim + "\" in directory \"" + self.sim_path + "\"", script_name)
      self.banned_sim_param.append(sim)
      self.error_sims.append(sim_display_name)
      return None

    # check if sim dir exists
    source_sim_dir = self.sim_path + '/' + sim
    if not isdir(source_sim_dir):
      printc.error("There is no directory \"" + sim + "\" in directory \"" + self.sim_path + "\"", script_name)
      self.banned_sim_param.append(sim)
      self.error_sims.append(sim_display_name)
      return None

    # get architecture
    architecture = arch_handler.get_architecture(arch)
    if architecture is None:
      self.error_sims.append(sim_display_name)
      return None


    # passed all check: added to the list
    self.new_sims.append(sim_display_name)
    self.valid_sims.append(sim_display_name)

    sim_instance = Simulation(
      sim_name = sim_name,
      sim_display_name = sim_display_name,
      architecture = architecture,
      tmp_dir = tmp_dir,
      source_sim_dir = source_sim_dir,
      simulation_command = simulation_command
    )

    return sim_instance

  def print_summary(self):
    SimulationHandler.print_sim_list(self.new_sims, "New simulations", printc.colors.ENDC)
    SimulationHandler.print_sim_list(self.incomplete_sims, "Incomplete results (will be overwritten)", printc.colors.YELLOW)
    SimulationHandler.print_sim_list(self.cached_sims, "Existing results (skipped)", printc.colors.CYAN)
    SimulationHandler.print_sim_list(self.overwrite_sims, "Existing results (will be overwritten)", printc.colors.YELLOW)
    SimulationHandler.print_sim_list(self.error_sims, "Invalid settings, (skipped, see errors above)", printc.colors.RED)

  def get_chuncks(self, nb_jobs):
    if len(self.simulation_instances) > nb_jobs:
      nb_chunks = math.ceil(len(self.simulation_instances) / nb_jobs)
      print()
      printc.note("Current maximum number of jobs is " + str(nb_jobs) + ". Simulations will be split in " + str(nb_chunks) + " chunks")
      self.simulation_instances_chunks = list(chunk_list(self.simulation_instances, nb_jobs))
    else:
      nb_chunks = 1
      self.simulation_instances_chunks = []
    return self.simulation_instances_chunks, nb_chunks


  def get_valid_sim_count(self):
    return len(self.valid_sims)

  @staticmethod
  def print_sim_list(arch_list, description, color):
    if not len(arch_list) > 0:
      return

    print()
    printc.bold(description + ":")
    for arch in arch_list:
      printc.color(color)
      print("  - " + arch)
    printc.endc()

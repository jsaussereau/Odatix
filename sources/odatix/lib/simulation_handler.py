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
import re
import math
import yaml
import itertools

from os.path import isfile
from os.path import isdir

from odatix.lib.architecture_handler import ArchitectureHandler
from odatix.lib.utils import *
from odatix.lib.param_domain import ParamDomain

script_name = os.path.basename(__file__)

class Simulation:
  def __init__(self, sim_name, sim_display_name, architecture, tmp_dir, source_sim_dir, override_parameters, override_param_target_filename, override_param_filename, override_start_delimiter, override_stop_delimiter, simulation_command):
    self.sim_name = sim_name
    self.sim_display_name = sim_display_name
    self.architecture = architecture
    self.tmp_dir = tmp_dir
    self.source_sim_dir = source_sim_dir
    self.override_parameters = override_parameters
    self.override_param_target_filename = override_param_target_filename
    self.override_param_filename = override_param_filename
    self.override_start_delimiter = override_start_delimiter
    self.override_stop_delimiter = override_stop_delimiter
    self.simulation_command = simulation_command
    

class SimulationHandler:

  def __init__(self, work_path, arch_path, sim_path, work_rtl_path, work_script_path, work_log_path, log_path, param_settings_filename, sim_settings_filename, sim_makefile_filename, overwrite):
    self.work_path = work_path
    self.arch_path = arch_path
    self.sim_path = sim_path
    self.work_rtl_path = work_rtl_path
    self.work_script_path = work_script_path
    self.work_log_path = work_log_path
    self.log_path = log_path
    self.overwrite = overwrite
    self.param_settings_filename = param_settings_filename
    self.sim_settings_filename = sim_settings_filename
    self.sim_makefile_filename = sim_makefile_filename
    self.reset_lists()

  def reset_lists(self):
    self.no_settings_sims = []
    self.banned_sim_param = []
    self.valid_sims = []
    self.cached_sims = []
    self.overwrite_sims = []
    self.error_sims = []
    self.incomplete_sims = []
    self.new_sims = []

  def get_simulations(self, simulations):

    self.reset_lists()
    self.simulation_instances = []

    arch_handler = ArchitectureHandler(
      work_path = self.work_path,
      arch_path = self.arch_path,
      script_path = "",
      work_rtl_path=self.work_rtl_path,
      work_script_path = self.work_script_path,
      work_log_path = self.work_log_path,
      work_report_path = "",
      log_path = self.log_path,
      process_group=True,
      command="",
      eda_target_filename = "",
      fmax_status_filename = "",
      frequency_search_filename = "",
      param_settings_filename = self.param_settings_filename,
      valid_status = "",
      valid_frequency_search = "",
      forced_fmax_lower_bound = None,
      forced_fmax_upper_bound = None,
      forced_custom_freq_list = None,
      overwrite = self.overwrite
    )

    if simulations is not None:
      for sim_dict in simulations:
        if sim_dict is not None:
          for sim, arch_list in sim_dict.items():
            if arch_list is not None and arch_list is not None:
              # Handle joker
              architectures = []
              for arch in arch_list:
                arch, arch_param_dir, arch_config, _, _, requested_param_domains = ArchitectureHandler.get_basic(arch, "", False)
                if arch.endswith("/*"):
                  # get param dir (arch name before '/*')
                  arch_param_dir = re.sub(r'/\*', '', arch)

                  # check if parameter dir exists
                  arch_param = self.arch_path + '/' + arch_param_dir
                  if isdir(arch_param):
                    files = [f[:-4] for f in os.listdir(arch_param) if os.path.isfile(os.path.join(arch_param, f)) and f.endswith(".txt")]
                    joker_archs = [os.path.join(arch_param_dir, file) for file in sorted(files)]
                    joker_param_domain = {}

                    for requested_param_domain in requested_param_domains:
                      if requested_param_domain.endswith("/*"):
                        param_domain = re.sub(r'/\*', '', requested_param_domain)
                        # get parameter domain dir
                        param_domain_dir = os.path.join(arch_param, param_domain)
                        # check if parameter domain dir exists
                        if isdir(param_domain_dir):
                          files = [f[:-4] for f in os.listdir(param_domain_dir) if os.path.isfile(os.path.join(param_domain_dir, f)) and f.endswith(".txt")]
                          joker_param_domain[param_domain] = sorted(files)
                      else:
                        param_domain = re.sub(r'/.*', '', requested_param_domain)
                        value = re.sub(r'.*/', '', requested_param_domain)
                        joker_param_domain[param_domain] = value

                    # Generate combinations
                    param_keys = list(joker_param_domain.keys())
                    param_values = [joker_param_domain[key] if isinstance(joker_param_domain[key], list) else [joker_param_domain[key]] for key in param_keys]

                    for arch_instance in joker_archs:
                      for param_combination in itertools.product(*param_values):
                        param_string = "+".join(f"{param_keys[i]}/{param_combination[i]}" for i in range(len(param_keys)))
                        architectures.append(f"{arch_instance}+{param_string}")
                else:
                  architectures.append(arch)

              for arch in architectures:
                simulation_instance = self.get_simulation(sim, arch, arch_handler)
                if simulation_instance is not None:
                  self.simulation_instances.append(simulation_instance)

    return self.simulation_instances
    
  
  def get_simulation(self, sim, arch_full, arch_handler):
    
    arch, arch_param, arch_config, arch_display_name, arch_param_dir_work, requested_param_domains = ArchitectureHandler.get_basic(arch_full)

    tmp_dir = os.path.join(self.work_path, sim, arch_param_dir_work, arch_config) 

    sim_name = sim
    sim_display_name = sim + ": " + arch_display_name 
    simulation_command = None

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
    architecture = arch_handler.get_architecture(arch_full)
    if architecture is None:
      self.error_sims.append(sim_display_name)
      return None

    # check if makefile exists
    makefile_filename = source_sim_dir + '/' + self.sim_makefile_filename
    if not isfile(makefile_filename):
      printc.error("There is no setting \"Makefile\" in directory \"" + source_sim_dir + "\"", script_name)
      printc.note("A Makefile with a rule \"sim\" is mandatory", script_name)
      self.banned_sim_param.append(sim)
      self.error_sims.append(sim_display_name)
      return None

    override_parameters = False
    override_param_target_filename = ""
    override_param_file = ""
    override_start_delimiter = ""
    override_stop_delimiter = ""

    # check if settings file exists
    if sim not in self.no_settings_sims:
      settings_filename = source_sim_dir + '/' + self.sim_settings_filename
      if not isfile(settings_filename):
        printc.note("There is no setting file \"" + self.sim_settings_filename + "\" in directory \"" + source_sim_dir + "\"", script_name)
        self.no_settings_sims.append(sim)
      else:
        with open(settings_filename, 'r') as f:
          try:
            settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
          except Exception as e:
            printc.error("Settings file \"" + settings_filename + "\" is not a valid YAML file", script_name)
            printc.cyan("error details: ", end="", script_name=script_name)
            print(str(e))
            self.banned_arch_param.append(arch_param_dir)
            self.error_archs.append(arch_display_name)
            return None # if an identifier is missing

          # get use_parameters, start_delimiter and stop_delimiter
          use_parameters, start_delimiter, stop_delimiter, param_target_filename = arch_handler.get_use_parameters(arch, arch_display_name, settings_data, settings_filename, None, add_to_error_list=False)
          if use_parameters is None:
            self.banned_sim_param.append(sim)
            self.error_sims.append(sim_display_name)
            return None
          elif start_delimiter is None or stop_delimiter is None:
            self.error_sims.append(sim_display_name)
            return None

          # overwrite architecture settings
          architecture.use_parameters = use_parameters
          architecture.start_delimiter = start_delimiter
          architecture.stop_delimiter = stop_delimiter

          # get param_target_file
          if use_parameters:
            if param_target_filename is None:
              self.banned_sim_param.append(sim)
              self.error_sims.append(sim_display_name)
              return None
            else:
              # check if param target file path exists
              param_target_file_rtl = architecture.rtl_path + '/' + param_target_filename
              param_target_file_sim = source_sim_dir + '/' + param_target_filename
              #if not isfile(param_target_file_rtl) and not isfile(param_target_file_sim): 
                #printc.warning("The parameter target file \"" + param_target_filename + "\" specified in \"" + settings_filename + "\" does not seem to exist", script_name)
              # overwrite architecture settings
              architecture.param_target_filename = param_target_filename

          # get override_parameters
          try:
            override_parameters = read_from_list('override_parameters', settings_data, settings_filename, type=bool, script_name=script_name)
          except (KeyNotInListError, BadValueInListError):
            self.banned_sim_param.append(sim)
            self.error_sims.append(sim_display_name)
            return None

          if override_parameters:
            # get override_param_target_file
            try:
              override_param_file = read_from_list('override_param_file', settings_data, settings_filename, print_error=False, script_name=script_name)
            except (KeyNotInListError, BadValueInListError):
              printc.error("Cannot find key \"override_param_file\" in \"" + settings_filename + "\", while \"override_parameters\" is true", script_name)
              self.banned_sim_param.append(sim)
              self.error_sims.append(sim_display_name)
              return None

            # check if parameter file exists
            if not isfile(source_sim_dir + '/' + override_param_file):
              printc.error("There is no parameter file \"" + source_sim_dir + '/' + override_param_file + "\", while override_parameters=true", script_name)
              self.error_sims.append(sim_display_name)
              return True
          
          if override_parameters:
            # get start delimiter
            try:
              override_start_delimiter = read_from_list('override_start_delimiter', settings_data, settings_filename, print_error=False, script_name=script_name)
            except (KeyNotInListError, BadValueInListError):
              printc.error("Cannot find key \"override_start_delimiter\" in \"" + settings_filename + "\", while \"override_parameters\" is true", script_name)
              self.banned_sim_param.append(sim)
              self.error_sims.append(sim_display_name)
              return None

            # get stop delimiter
            try:
              override_stop_delimiter = read_from_list('override_stop_delimiter', settings_data, settings_filename, print_error=False, script_name=script_name)
            except (KeyNotInListError, BadValueInListError):
              printc.error("Cannot find key \"override_stop_delimiter\" in \"" + settings_filename + "\", while \"override_parameters\" is true", script_name)
              self.banned_sim_param.append(sim)
              self.error_sims.append(sim_display_name)
          else:
            override_start_delimiter = ""
            override_stop_delimiter = ""

          # get override_param_target_file
          if override_parameters:
            try:
              override_param_target_filename = read_from_list('override_param_target_file', settings_data, settings_filename, script_name=script_name)

              # check if param target file path exists
              override_param_target_file_rtl = architecture.rtl_path + '/' + override_param_target_filename
              override_param_target_file_sim = source_sim_dir + '/' + override_param_target_filename
              #if not isfile(override_param_target_file_rtl) and not isfile(override_param_target_file_sim): 
                #printc.warning("The override parameter target file \"" + override_param_target_filename + "\" specified in \"" + settings_filename + "\" does not seem to exist", script_name)
            except (KeyNotInListError, BadValueInListError):
              self.banned_sim_param.append(sim)
              self.error_sims.append(sim_display_name)
              return None
          else:
            override_param_target_filename = "/dev/null"
      
    # check if the architecture is in cache and has a status file
    if isdir(tmp_dir):
      if self.overwrite:
        printc.warning("Found cached results for \"" + sim_display_name +"\".", script_name)
        self.overwrite_sims.append(sim_display_name)
      else:
        printc.note("Found cached results for \"" + sim_display_name + "\". Skipping.", script_name)
        self.cached_sims.append(sim_display_name)
        return None
    else:
      self.new_sims.append(sim_display_name)

    # passed all check: added to the list
    self.valid_sims.append(sim_display_name)

    sim_instance = Simulation(
      sim_name = sim_name,
      sim_display_name = sim_display_name,
      architecture = architecture,
      tmp_dir = tmp_dir,
      source_sim_dir = source_sim_dir,
      override_parameters = override_parameters,
      override_param_target_filename = override_param_target_filename,
      override_param_filename = override_param_file,
      override_start_delimiter = override_start_delimiter,
      override_stop_delimiter = override_stop_delimiter,
      simulation_command = simulation_command
    )

    return sim_instance

  def print_summary(self):
    SimulationHandler.print_sim_list(self.new_sims, "New simulations", printc.colors.ENDC)
    SimulationHandler.print_sim_list(self.incomplete_sims, "Incomplete results (will be overwritten)", printc.colors.YELLOW)
    SimulationHandler.print_sim_list(self.cached_sims, "Existing results (skipped)", printc.colors.CYAN)
    SimulationHandler.print_sim_list(self.overwrite_sims, "Existing results (will be overwritten)", printc.colors.YELLOW)
    SimulationHandler.print_sim_list(self.error_sims, "Invalid settings, (skipped, see errors above)", printc.colors.RED)

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

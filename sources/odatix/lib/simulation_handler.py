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

from os.path import isfile
from os.path import isdir

from odatix.lib.architecture_handler import ArchitectureHandler
from odatix.lib.run_report import JobPlan, Category
from odatix.lib.utils import *
from odatix.lib.param_domain import ParamDomain
import odatix.lib.param_domain as param_domain
import odatix.lib.hard_settings as hard_settings
import odatix.workspace.selection as selection

script_name = os.path.basename(__file__)

class Simulation:
  def __init__(
    self,
    sim_name,
    sim_display_name,
    architecture,
    arch_full,
    arch_param_dir,
    arch_config,
    tmp_dir,
    source_sim_dir,
    override_parameters,
    override_param_target_filename,
    override_param_filename,
    override_start_delimiter,
    override_stop_delimiter,
    tasks=None,
    progress_file=None,
    progress_regex=None,
    invariant_domains=None,
  ):
    self.sim_name = sim_name
    self.sim_display_name = sim_display_name
    self.architecture = architecture
    self.arch_full = arch_full
    self.arch_param_dir = arch_param_dir
    self.arch_config = arch_config
    self.tmp_dir = tmp_dir
    self.source_sim_dir = source_sim_dir
    self.override_parameters = override_parameters
    self.override_param_target_filename = override_param_target_filename
    self.override_param_filename = override_param_filename
    self.override_start_delimiter = override_start_delimiter
    self.override_stop_delimiter = override_stop_delimiter
    # Tasks are the workflow-style execution graph of the simulation. When the
    # settings file defines none, run_simulations falls back to the historical
    # single "make sim" rule (see default_simulation_task there).
    self.tasks = tasks if isinstance(tasks, list) else []
    self.progress_file = progress_file
    self.progress_regex = progress_regex
    # Parameter domains this simulation's result does not depend on. They are
    # collapsed to a single run (see SimulationHandler.get_simulations) and are
    # left out of the exported record, so it matches every value of them.
    self.invariant_domains = invariant_domains if isinstance(invariant_domains, dict) else {}


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

  def get_invariant_domains(self, sim):
    """
    The parameter domains a simulation declares its result does not depend on.

    Read straight from the simulation settings file, and before the
    configurations are expanded: which configurations are worth running depends
    on it, so it cannot wait until each one is built.
    """
    if sim in self._invariant_domains_cache:
      return self._invariant_domains_cache[sim]

    domains = {}
    settings_filename = os.path.join(self.sim_path, sim, self.sim_settings_filename)
    if isfile(settings_filename):
      try:
        with open(settings_filename, "r") as f:
          settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
        if isinstance(settings_data, dict):
          domains = param_domain.parse_invariant_domains(
            settings_data.get(param_domain.INVARIANT_DOMAINS_KEY), settings_filename
          )
      except Exception:
        # An unreadable settings file is reported by get_simulation, which needs
        # to ban the simulation anyway. Nothing to add here.
        domains = {}

    self._invariant_domains_cache[sim] = domains
    return domains

  def reset_lists(self):
    self._invariant_domains_cache = {}
    self.no_settings_sims = []
    self.banned_sim_param = []
    # Single source of truth for the check outcome (see lib/run_report.py).
    self.plan = JobPlan()
    # Simulations that passed every check (not derivable from the plan: a
    # simulation is categorized before the last checks run).
    self.valid_sims = []

  @property
  def cached_sims(self):
    return self.plan.names(Category.CACHED)

  @property
  def overwrite_sims(self):
    return self.plan.names(Category.OVERWRITE)

  @property
  def error_sims(self):
    return self.plan.names(Category.ERROR)

  @property
  def incomplete_sims(self):
    return self.plan.names(Category.INCOMPLETE)

  @property
  def new_sims(self):
    return self.plan.names(Category.NEW)

  def get_simulations(self, simulations, keep=False, timestamp=""):

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
              # What the simulation runs on is written exactly like what a
              # synthesis runs on, wildcards included (see workspace.selection).
              messages = []
              architectures = selection.expand(arch_list, self.arch_path, messages=messages)
              printc.messages(messages, script_name)

              # Configurations that only differ by a domain the simulation is
              # invariant to would all compute the same result: keep one.
              invariant_domains = self.get_invariant_domains(sim)
              if invariant_domains:
                architectures, dropped = param_domain.collapse_invariant_configurations(
                  architectures, invariant_domains, error_prefix=sim + ": "
                )
                if dropped > 0:
                  printc.note(
                    sim + ': skipping ' + str(dropped) + ' redundant configuration'
                    + ("s" if dropped > 1 else "")
                    + ' (invariant to "' + '", "'.join(sorted(invariant_domains)) + '")',
                    script_name,
                  )

              for arch in architectures:
                simulation_instance = self.get_simulation(sim, arch, arch_handler, keep=keep, timestamp=timestamp)
                if simulation_instance is not None:
                  self.simulation_instances.append(simulation_instance)

    return self.simulation_instances
    
  
  def get_simulation(self, sim, arch_full, arch_handler, keep=False, timestamp=""):
    
    arch, arch_param_dir, arch_config, arch_display_name, arch_param_dir_work, arch_config_dir_work, requested_param_domains = ArchitectureHandler.get_basic(arch_full)

    arch_config_dir_work = arch_config_dir_work + "_" + timestamp if keep and timestamp != "" else arch_config_dir_work

    tmp_dir = os.path.join(self.work_path, sim, arch_param_dir_work, arch_config_dir_work) 

    sim_name = sim
    sim_display_name = sim + ": " + arch_display_name

    # check if sim has been banned
    if sim in self.banned_sim_param:
      self.plan.add(sim_display_name, Category.ERROR)
      return None

    # check if sim dir exists
    source_sim_dir = self.sim_path + '/' + sim
    if not isdir(source_sim_dir):
      printc.error("There is no directory \"" + sim + "\" in directory \"" + self.sim_path + "\"", script_name)
      self.banned_sim_param.append(sim)
      self.plan.add(sim_display_name, Category.ERROR)
      return None

    # get architecture
    architecture = arch_handler.get_architecture(arch_full)
    if architecture is None:
      self.plan.add(sim_display_name, Category.ERROR)
      return None

    override_parameters = False
    override_param_target_filename = ""
    override_param_file = ""
    override_start_delimiter = ""
    override_stop_delimiter = ""

    # Workflow-style execution graph. Empty means "use the legacy 'make sim'
    # rule", which is what every simulation defined before tasks existed does.
    tasks = []
    progress_file = hard_settings.sim_progress_filename
    progress_regex = hard_settings.sim_status_pattern.pattern

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
            self.banned_sim_param.append(sim)
            self.plan.add(sim_display_name, Category.ERROR)
            return None # if an identifier is missing

          # get tasks (optional: without them the legacy "make sim" rule is used)
          try:
            tasks = read_from_list('tasks', settings_data, settings_filename, type=list, optional=True, raise_if_missing=False, print_error=False)
          except (KeyNotInListError, BadValueInListError):
            tasks = []
          if tasks in (False, None):
            tasks = []

          # get progress tracking settings (optional)
          try:
            progress = read_from_list('progress', settings_data, settings_filename, type=dict, optional=True, raise_if_missing=False, print_error=False)
          except (KeyNotInListError, BadValueInListError):
            progress = None
          if progress not in (False, None):
            progress_file_setting = read_from_list('file', progress, settings_filename, parent='progress', optional=True, raise_if_missing=False, print_error=False)
            progress_regex_setting = read_from_list('regex', progress, settings_filename, parent='progress', optional=True, raise_if_missing=False, print_error=False)
            if progress_file_setting not in (False, None):
              progress_file = progress_file_setting
            if progress_regex_setting not in (False, None):
              progress_regex = progress_regex_setting

          # get use_parameters, start_delimiter and stop_delimiter
          use_parameters, start_delimiter, stop_delimiter, param_target_filename = arch_handler.get_use_parameters(arch, arch_display_name, settings_data, settings_filename, None, add_to_error_list=False)
          if use_parameters is None:
            self.banned_sim_param.append(sim)
            self.plan.add(sim_display_name, Category.ERROR)
            return None
          elif start_delimiter is None or stop_delimiter is None:
            self.plan.add(sim_display_name, Category.ERROR)
            return None

          # overwrite architecture settings
          architecture.use_parameters = use_parameters
          architecture.start_delimiter = start_delimiter
          architecture.stop_delimiter = stop_delimiter

          # get param_target_file
          if use_parameters:
            if param_target_filename is None:
              self.banned_sim_param.append(sim)
              self.plan.add(sim_display_name, Category.ERROR)
              return None
            else:
              # check if param target file path exists
              param_target_file_rtl = architecture.rtl_path + '/' + param_target_filename
              param_target_file_sim = source_sim_dir + '/' + param_target_filename
              #if not isfile(param_target_file_rtl) and not isfile(param_target_file_sim): 
                #printc.warning("The parameter target file \"" + param_target_filename + "\" specified in \"" + settings_filename + "\" does not seem to exist", script_name)
              # overwrite architecture settings
              architecture.param_target_filename = param_target_filename

          # get override_parameters (optional, defaults to no override)
          try:
            override_parameters = read_from_list('override_parameters', settings_data, settings_filename, type=bool, optional=True, raise_if_missing=False, print_error=False)
          except (KeyNotInListError, BadValueInListError):
            override_parameters = False
          if override_parameters is False or override_parameters is None:
            override_parameters = False

          if override_parameters:
            # get override_param_target_file
            try:
              override_param_file = read_from_list('override_param_file', settings_data, settings_filename, print_error=False, script_name=script_name)
            except (KeyNotInListError, BadValueInListError):
              printc.error("Cannot find key \"override_param_file\" in \"" + settings_filename + "\", while \"override_parameters\" is true", script_name)
              self.banned_sim_param.append(sim)
              self.plan.add(sim_display_name, Category.ERROR)
              return None

            # check if parameter file exists
            if not isfile(source_sim_dir + '/' + override_param_file):
              printc.error("There is no parameter file \"" + source_sim_dir + '/' + override_param_file + "\", while override_parameters=true", script_name)
              self.plan.add(sim_display_name, Category.ERROR)
              return True
          
          if override_parameters:
            # get start delimiter
            try:
              override_start_delimiter = read_from_list('override_start_delimiter', settings_data, settings_filename, print_error=False, script_name=script_name)
            except (KeyNotInListError, BadValueInListError):
              printc.error("Cannot find key \"override_start_delimiter\" in \"" + settings_filename + "\", while \"override_parameters\" is true", script_name)
              self.banned_sim_param.append(sim)
              self.plan.add(sim_display_name, Category.ERROR)
              return None

            # get stop delimiter
            try:
              override_stop_delimiter = read_from_list('override_stop_delimiter', settings_data, settings_filename, print_error=False, script_name=script_name)
            except (KeyNotInListError, BadValueInListError):
              printc.error("Cannot find key \"override_stop_delimiter\" in \"" + settings_filename + "\", while \"override_parameters\" is true", script_name)
              self.banned_sim_param.append(sim)
              self.plan.add(sim_display_name, Category.ERROR)
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
              self.plan.add(sim_display_name, Category.ERROR)
              return None
          else:
            override_param_target_filename = "/dev/null"

    # Without tasks, the simulation is run through its Makefile's "sim" rule:
    # that Makefile is then mandatory. Task-based simulations do not need one.
    if len(tasks) == 0:
      makefile_filename = source_sim_dir + '/' + self.sim_makefile_filename
      if not isfile(makefile_filename):
        printc.error("There is no file \"" + self.sim_makefile_filename + "\" in directory \"" + source_sim_dir + "\"", script_name)
        printc.note("A Makefile with a rule \"sim\" is mandatory, unless the simulation defines \"tasks\" in \"" + self.sim_settings_filename + "\"", script_name)
        self.banned_sim_param.append(sim)
        self.plan.add(sim_display_name, Category.ERROR)
        return None

    # check if the architecture is in cache and has a status file
    if isdir(tmp_dir):
      if self.overwrite:
        printc.warning("Found cached results for \"" + sim_display_name +"\".", script_name)
        self.plan.add(sim_display_name, Category.OVERWRITE)
      else:
        printc.note("Found cached results for \"" + sim_display_name + "\". Skipping.", script_name)
        self.plan.add(sim_display_name, Category.CACHED)
        return None
    else:
      self.plan.add(sim_display_name, Category.NEW, tasks=max(len(tasks), 1))

    # passed all check: added to the list
    self.valid_sims.append(sim_display_name)

    sim_instance = Simulation(
      sim_name = sim_name,
      sim_display_name = sim_display_name,
      architecture = architecture,
      arch_full = arch_full,
      arch_param_dir = arch_param_dir,
      arch_config = arch_config,
      tmp_dir = tmp_dir,
      source_sim_dir = source_sim_dir,
      override_parameters = override_parameters,
      override_param_target_filename = override_param_target_filename,
      override_param_filename = override_param_file,
      override_start_delimiter = override_start_delimiter,
      override_stop_delimiter = override_stop_delimiter,
      tasks = tasks,
      progress_file = progress_file,
      progress_regex = progress_regex,
      invariant_domains = self.get_invariant_domains(sim),
    )

    return sim_instance

  def print_summary(self):
    self.plan.print_summary(noun="simulations")

  def get_valid_sim_count(self):
    return len(self.valid_sims)


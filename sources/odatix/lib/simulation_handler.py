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
import odatix.workspace.sim_architectures as sim_architectures
import odatix.lib.yaml_loader as yaml_loader

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
          settings_data = yaml.load(f, Loader=yaml_loader.SafeLoader)
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

  def get_architecture_entries(self, sim):
    """
    The architectures a simulation declares it runs on, and what it changes for
    each of them (see odatix.workspace.sim_architectures).

    Read straight from the settings file, and cached: the compatibility warning
    needs them before the configurations are expanded, and every job of the
    simulation reads them again.
    """
    if sim in self._architectures_cache:
      return self._architectures_cache[sim]

    entries = []
    settings_filename = os.path.join(self.sim_path, sim, self.sim_settings_filename)
    if isfile(settings_filename):
      try:
        with open(settings_filename, "r") as f:
          settings_data = yaml.load(f, Loader=yaml_loader.SafeLoader)
        if isinstance(settings_data, dict):
          messages = []
          entries = sim_architectures.parse(
            settings_data.get(sim_architectures.ARCHITECTURES_KEY),
            messages=messages,
            where='"' + sim_architectures.ARCHITECTURES_KEY + '" in "' + settings_filename + '"',
          )
          printc.messages(messages, script_name)
          if any(message.level == "error" for message in messages):
            entries = []
            self.banned_sim_param.append(sim)
      except Exception:
        # An unreadable settings file is reported by get_simulation, which needs
        # to ban the simulation anyway. Nothing to add here.
        entries = []

    self._architectures_cache[sim] = entries
    return entries

  def check_architectures(self, sim, architectures):
    """
    Warn about the architectures a simulation is run on but does not list. Once
    per architecture, whatever the number of configurations.
    """
    entries = self.get_architecture_entries(sim)
    if not entries:
      return

    for arch_full in architectures:
      arch_name = str(arch_full).split("+", 1)[0].split("/", 1)[0].strip()
      if sim_architectures.matches(entries, arch_name) or (sim, arch_name) in self._warned_unlisted:
        continue
      self._warned_unlisted.add((sim, arch_name))
      printc.warning(
        "\"" + arch_name + "\" is not one of the architectures \"" + sim + "\" runs on",
        script_name,
      )
      printc.note(
        "Add it to \"" + sim_architectures.ARCHITECTURES_KEY + "\" in \""
        + os.path.join(self.sim_path, sim, self.sim_settings_filename) + "\" to silence this warning",
        script_name,
      )

  def reset_lists(self):
    self._invariant_domains_cache = {}
    self._architectures_cache = {}
    self._warned_unlisted = set()
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

              # Running a simulation on an architecture it does not list is
              # allowed: only say so.
              self.check_architectures(sim, architectures)

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
    progress_file = hard_settings.sim_progress_file
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
            settings_data = yaml.load(f, Loader=yaml_loader.SafeLoader)
          except Exception as e:
            printc.error("Settings file \"" + settings_filename + "\" is not a valid YAML file", script_name)
            printc.cyan("error details: ", end="", script_name=script_name)
            print(str(e))
            self.banned_sim_param.append(sim)
            self.plan.add(sim_display_name, Category.ERROR)
            return None # if an identifier is missing

          # Both moved under "architectures", which lists what the simulation runs on and
          # what it changes for each. A file still written the old way would be read as
          # having no override at all: say so rather than running something else.
          for moved_key in ('param_domains', 'compatible_architectures'):
            if moved_key in settings_data:
              printc.error("\"" + moved_key + "\" in \"" + settings_filename + "\" is not read anymore", script_name)
              printc.note(
                "The architectures a simulation runs on, and what it changes for each of them, "
                "are now listed under \"" + sim_architectures.ARCHITECTURES_KEY + "\"", script_name
              )
              self.banned_sim_param.append(sim)
              self.plan.add(sim_display_name, Category.ERROR)
              return None

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

          # deprecated: "use_parameters" (and its delimiters/target file) at the top level of a
          # simulation's settings only ever covered a single, non-domain parameter file. Prefer
          # "param_domains" below, which can override (or add) any number of parameter domains.
          if 'use_parameters' in settings_data:
            printc.warning("\"use_parameters\" in \"" + settings_filename + "\" is deprecated, use \"param_domains\" instead", script_name)

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
                architecture.param_target_filename = param_target_filename

          # get override_parameters (optional, defaults to no override)
          try:
            override_parameters = read_from_list('override_parameters', settings_data, settings_filename, type=bool, optional=True, raise_if_missing=False, print_error=False)
          except (KeyNotInListError, BadValueInListError):
            override_parameters = False
          if override_parameters is False or override_parameters is None:
            override_parameters = False
          elif 'override_parameters' in settings_data:
            printc.warning("\"override_parameters\" in \"" + settings_filename + "\" is deprecated, use \"param_domains\" instead", script_name)

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

          # What the simulation changes for the architecture under test, taken from the
          # "architectures" block (see odatix.workspace.sim_architectures): the entries
          # matching this architecture, merged in the order they are written.
          # The "architectures" block names architectures, not configurations: match it
          # against the architecture name alone, the way check_architectures does. "arch"
          # here is the parameter directory ("AsteRISC/M0000"), which no entry would match.
          arch_entry_name = str(arch_full).split("+", 1)[0].split("/", 1)[0].strip()
          arch_settings = sim_architectures.settings_for(self.get_architecture_entries(sim), arch_entry_name)
          if sim in self.banned_sim_param:
            self.plan.add(sim_display_name, Category.ERROR)
            return None

          # "param_domains" customizes the parameter substitution of this simulation for
          # this architecture. A key matching one of the architecture's own domains (e.g.
          # "width") overrides only the fields it lists, the rest is inherited from the
          # architecture's domain settings. A key that does not match any architecture
          # domain declares a standalone substitution of its own (a "param_file" is then
          # mandatory), which subsumes what the deprecated "override_parameters"
          # mechanism used to do.
          #
          # One domain lists as many substitutions as the places its values are written
          # in: a value of "width" is written into the testbench, into the Makefile
          # building it, and into the design itself, each with its own target file,
          # delimiters and parameters.
          if arch_settings.get("param_domains"):
            for domain_name, domain_value in arch_settings["param_domains"].items():
              domain_name = str(domain_name)
              domain_id = arch_entry_name + ": param_domains: " + domain_name
              substitutions = sim_architectures.substitutions(domain_value)
              if not substitutions:
                printc.error("\"architectures: " + domain_id + "\" in \"" + settings_filename + "\" must be a mapping, or a list of mappings", script_name)
                self.banned_sim_param.append(sim)
                self.plan.add(sim_display_name, Category.ERROR)
                return None

              # The domain of the architecture every substitution of this domain inherits
              # from, read once: a substitution replacing it changes it in place, and the
              # ones after it would otherwise inherit what the first one wrote.
              existing_domain = next((pd for pd in architecture.param_domains if pd.domain == domain_name), None)
              base_domain = ParamDomain(
                domain=existing_domain.domain,
                domain_value=existing_domain.domain_value,
                use_parameters=existing_domain.use_parameters,
                start_delimiter=existing_domain.start_delimiter,
                stop_delimiter=existing_domain.stop_delimiter,
                param_target_file=existing_domain.param_target_file,
                param_file=existing_domain.param_file,
              ) if existing_domain is not None else None
              replaced = False

              for index, domain_overrides in enumerate(substitutions):
                # Where the substitution points at a directory of configurations, that
                # directory says how its parameters are written, in its own
                # "_settings.yml": read it here, so the rest of this reads one
                # mapping whichever file it was written in.
                domain_overrides = sim_architectures.domain_settings(domain_overrides, source_sim_dir)
                combine = sim_architectures.combine_mode(domain_overrides, index)

                # "__main__" names the architecture's own substitution (its configurations),
                # which is not one of its "param_domains": it is described by the architecture
                # itself. The substitution inherits from it whatever it does not say, and
                # "combine" says whether the architecture's own substitution still happens.
                if domain_name == hard_settings.main_parameter_domain:
                  if combine != sim_architectures.COMBINE_BOTH:
                    architecture.use_parameters = False
                  domain_overrides = dict(domain_overrides)
                  # The configuration of "__main__" being run is the architecture's own
                  # configuration ("AsteRISC/M0000" runs "M0000"), which is what a
                  # "param_dir" of this domain is looked up by.
                  domain_overrides.setdefault('domain_value', arch_config)
                  domain_overrides.setdefault('start_delimiter', architecture.start_delimiter)
                  domain_overrides.setdefault('stop_delimiter', architecture.stop_delimiter)
                  domain_overrides.setdefault('param_target_file', architecture.param_target_filename)

                if base_domain is not None:
                  # "combine" says what to do with the architecture's own substitution for
                  # this domain: "replace" customizes it in place, "both" leaves it alone
                  # and does a second substitution, described here and inheriting from it
                  # whatever it does not say. Only one substitution can replace it, so the
                  # ones after the first are added to it whatever they say.
                  if combine == sim_architectures.COMBINE_BOTH or replaced:
                    target_domain = ParamDomain(
                      domain=base_domain.domain,
                      domain_value=base_domain.domain_value,
                      use_parameters=base_domain.use_parameters,
                      start_delimiter=base_domain.start_delimiter,
                      stop_delimiter=base_domain.stop_delimiter,
                      param_target_file=base_domain.param_target_file,
                      param_file=base_domain.param_file,
                    )
                    architecture.param_domains.append(target_domain)
                  else:
                    target_domain = existing_domain
                    replaced = True

                  if 'use_parameters' in domain_overrides:
                    target_domain.use_parameters = bool(domain_overrides['use_parameters'])
                  if 'start_delimiter' in domain_overrides:
                    target_domain.start_delimiter = domain_overrides['start_delimiter']
                  if 'stop_delimiter' in domain_overrides:
                    target_domain.stop_delimiter = domain_overrides['stop_delimiter']
                  if 'param_target_file' in domain_overrides:
                    target_domain.param_target_file = domain_overrides['param_target_file']
                  elif target_domain.param_target_file == "":
                    # The architecture had the domain switched off, so it never resolved a target
                    # file for it. Re-enabling it here has to fall back to the top level, as the
                    # architecture would have.
                    target_domain.param_target_file = architecture.top_level_filename
                  if target_domain.use_parameters and (target_domain.start_delimiter == "" or target_domain.stop_delimiter == ""):
                    printc.error("\"architectures: " + domain_id + "\" in \"" + settings_filename + "\" enables the replacement but no \"start_delimiter\"/\"stop_delimiter\" is defined, here or in the architecture", script_name)
                    self.banned_sim_param.append(sim)
                    self.plan.add(sim_display_name, Category.ERROR)
                    return None
                  # What the simulation substitutes for this domain: one file for every
                  # configuration ("param_file"), or one per configuration of the domain
                  # ("param_dir", files or rules, like an architecture's configurations).
                  domain_messages = []
                  domain_param_file = sim_architectures.resolve_param_file(
                    domain_overrides, source_sim_dir,
                    domain_value=target_domain.domain_value,
                    # What the configuration being substituted holds, which a
                    # "match" block reads as "$value": the file the architecture
                    # substitutes for this domain, read only if a selector asks.
                    domain_content=target_domain.param_file,
                    messages=domain_messages,
                    where="\"architectures: " + domain_id + "\" in \"" + settings_filename + "\"",
                  )
                  printc.messages(domain_messages, script_name)
                  if any(message.level == "error" for message in domain_messages):
                    self.plan.add(sim_display_name, Category.ERROR)
                    return None
                  if domain_param_file is not None:
                    target_domain.param_file = domain_param_file
                else:
                  # Standalone substitution: not tied to any architecture domain, so
                  # everything needed to run it has to be given here.
                  if 'param_file' not in domain_overrides and 'param_dir' not in domain_overrides:
                    printc.error("Cannot find key \"param_file\" or \"param_dir\" in \"architectures: " + domain_id + "\" in \"" + settings_filename + "\", required since \"" + domain_name + "\" is not a domain of this architecture", script_name)
                    self.banned_sim_param.append(sim)
                    self.plan.add(sim_display_name, Category.ERROR)
                    return None
                  domain_messages = []
                  new_domain_param_file = sim_architectures.resolve_param_file(
                    domain_overrides, source_sim_dir,
                    domain_value=str(domain_overrides.get('domain_value', '')),
                    messages=domain_messages,
                    where="\"architectures: " + domain_id + "\" in \"" + settings_filename + "\"",
                  )
                  printc.messages(domain_messages, script_name)
                  if new_domain_param_file is None or any(message.level == "error" for message in domain_messages):
                    self.plan.add(sim_display_name, Category.ERROR)
                    return None
                  new_domain_use_parameters = bool(domain_overrides.get('use_parameters', True))
                  new_domain_start_delimiter = domain_overrides.get('start_delimiter', '')
                  new_domain_stop_delimiter = domain_overrides.get('stop_delimiter', '')
                  if new_domain_use_parameters and (new_domain_start_delimiter == '' or new_domain_stop_delimiter == ''):
                    printc.error("\"architectures: " + domain_id + "\" in \"" + settings_filename + "\" needs \"start_delimiter\" and \"stop_delimiter\", since it does not match any domain of this architecture", script_name)
                    self.banned_sim_param.append(sim)
                    self.plan.add(sim_display_name, Category.ERROR)
                    return None
                  architecture.param_domains.append(ParamDomain(
                    domain=domain_name,
                    domain_value=str(domain_overrides.get('domain_value', '')),
                    use_parameters=new_domain_use_parameters,
                    start_delimiter=new_domain_start_delimiter,
                    stop_delimiter=new_domain_stop_delimiter,
                    param_target_file=domain_overrides.get('param_target_file', '') or architecture.top_level_filename,
                    param_file=new_domain_param_file,
                  ))

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


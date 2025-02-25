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
import sys
import math
import yaml
import copy

from os.path import isfile
from os.path import isdir

from odatix.lib.settings import OdatixSettings
from odatix.lib.utils import *
from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
import odatix.lib.printc as printc
from odatix.lib.variables import replace_variables, Variables
from odatix.lib.param_domain import ParamDomain

script_name = os.path.basename(__file__)

class Architecture:
  def __init__(
    self, arch_name, arch_display_name, lib_name, target, local_rtl_path, tmp_script_path, tmp_report_path, tmp_log_path, tmp_dir, 
    design_path, design_path_whitelist, design_path_blacklist, rtl_path, log_path, arch_path,
    clock_signal, reset_signal, top_level_module, top_level_filename, use_parameters, start_delimiter, stop_delimiter,
    file_copy_enable, file_copy_source, file_copy_dest, script_copy_enable, script_copy_source, 
    fmax_lower_bound, fmax_upper_bound, range_list, target_frequency,
    param_target_filename, generate_rtl, generate_command, constraint_filename, install_path, 
    param_domains, continue_on_error=False, force_single_thread=False,
  ):
    self.arch_name = arch_name
    self.arch_display_name = arch_display_name
    self.lib_name = lib_name
    self.target = target
    self.local_rtl_path = local_rtl_path
    self.tmp_script_path = tmp_script_path
    self.tmp_report_path = tmp_report_path
    self.tmp_log_path = tmp_log_path
    self.tmp_dir = tmp_dir
    self.design_path = design_path
    self.design_path_whitelist = design_path_whitelist
    self.design_path_blacklist = design_path_blacklist
    self.rtl_path = rtl_path
    self.log_path = log_path
    self.arch_path = arch_path
    self.clock_signal = clock_signal
    self.reset_signal = reset_signal
    self.top_level_module = top_level_module
    self.top_level_filename = top_level_filename
    self.file_copy_enable = file_copy_enable
    self.file_copy_source = file_copy_source
    self.file_copy_dest = file_copy_dest
    self.script_copy_enable = script_copy_enable
    self.script_copy_source = script_copy_source
    self.fmax_lower_bound = fmax_lower_bound
    self.fmax_upper_bound = fmax_upper_bound
    self.range_list = range_list
    self.target_frequency = target_frequency
    self.param_target_filename = param_target_filename
    self.use_parameters = use_parameters
    self.start_delimiter = start_delimiter
    self.stop_delimiter = stop_delimiter
    self.generate_rtl = generate_rtl
    self.generate_command = generate_command
    self.constraint_filename = constraint_filename
    self.install_path = install_path
    self.param_domains = param_domains
    self.continue_on_error = continue_on_error
    self.force_single_thread = force_single_thread

  def write_yaml(arch, config_file): 
    yaml_data = {
      'arch_name': arch.arch_name,
      'arch_display_name': arch.arch_display_name,
      'lib_name': arch.lib_name,
      'target': arch.target,
      'rtl_path': arch.local_rtl_path,
      'script_path': arch.tmp_script_path,
      'report_path': arch.tmp_report_path,
      'log_path': arch.tmp_log_path,
      'tmp_path': arch.tmp_dir,
      'design_path': arch.design_path,
      'design_path_whitelist': arch.design_path_whitelist,
      'design_path_blacklist': arch.design_path_blacklist,
      'source_rtl_path': arch.rtl_path,
      'arch_path': arch.arch_path,
      'clock_signal': arch.clock_signal,
      'reset_signal': arch.reset_signal,
      'top_level_module': arch.top_level_module,
      'top_level_file': arch.top_level_filename,
      'use_parameters': arch.use_parameters,
      'start_delimiter': arch.start_delimiter,
      'stop_delimiter': arch.stop_delimiter,
      'file_copy_enable': arch.file_copy_enable,
      'file_copy_source': arch.file_copy_source,
      'file_copy_dest': arch.file_copy_dest,
      'script_copy_enable': arch.script_copy_enable,
      'script_copy_source': arch.script_copy_source,
      'fmax_lower_bound': arch.fmax_lower_bound,
      'fmax_upper_bound': arch.fmax_upper_bound,
      'range_list': arch.range_list,
      'target_frequency': arch.target_frequency,
      'param_target_filename': arch.param_target_filename,
      'generate_rtl': arch.generate_rtl,
      'generate_command': arch.generate_command,
      'constraint_filename': arch.constraint_filename,
      'install_path': arch.install_path,
      'continue_on_error': arch.continue_on_error,
      'force_single_thread': arch.force_single_thread,
    }
      
    with open(config_file, 'w') as f:
      yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

  def read_yaml(config_file):
    if not os.path.isfile(config_file):
      printc.error("Settings file \"" + config_file + "\" does not exist", script_name)
      return None

    with open(config_file, 'r') as f:
      yaml_data = yaml.safe_load(f)
    
    try:
      arch = Architecture(
        arch_name                = get_from_dict("arch_name", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        arch_display_name        = get_from_dict("arch_display_name", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        lib_name                 = get_from_dict("lib_name", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        target                   = get_from_dict("target", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        rtl_path                 = get_from_dict("source_rtl_path", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        tmp_script_path          = get_from_dict("script_path", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        tmp_report_path          = get_from_dict("report_path", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        tmp_log_path             = get_from_dict("log_path", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        tmp_dir                  = get_from_dict("tmp_path", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        design_path              = get_from_dict("design_path", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        design_path_whitelist    = get_from_dict("design_path_whitelist", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        design_path_blacklist    = get_from_dict("design_path_blacklist", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        local_rtl_path           = get_from_dict("rtl_path", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        arch_path                = get_from_dict("arch_path", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        clock_signal             = get_from_dict("clock_signal", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        reset_signal             = get_from_dict("reset_signal", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        top_level_module         = get_from_dict("top_level_module", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        top_level_filename       = get_from_dict("top_level_file", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        use_parameters           = get_from_dict("use_parameters", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        start_delimiter          = get_from_dict("start_delimiter", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        stop_delimiter           = get_from_dict("stop_delimiter", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        file_copy_enable         = get_from_dict("file_copy_enable", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        file_copy_source         = get_from_dict("file_copy_source", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        file_copy_dest           = get_from_dict("file_copy_dest", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        script_copy_enable       = get_from_dict("script_copy_enable", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        script_copy_source       = get_from_dict("script_copy_source", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        fmax_lower_bound         = get_from_dict("fmax_lower_bound", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        fmax_upper_bound         = get_from_dict("fmax_upper_bound", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        range_list               = get_from_dict("range_list", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        target_frequency         = get_from_dict("target_frequency", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        param_target_filename    = get_from_dict("param_target_filename", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        generate_rtl             = get_from_dict("generate_rtl", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        generate_command         = get_from_dict("generate_command", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        constraint_filename      = get_from_dict("constraint_filename", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],   
        install_path             = get_from_dict("install_path", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],
        continue_on_error        = get_from_dict("continue_on_error", yaml_data, config_file, behavior=Key.OPTIONAL_DEFAULT, default_value=False, script_name=script_name)[0],
        force_single_thread      = get_from_dict("force_single_thread", yaml_data, config_file, behavior=Key.OPTIONAL_DEFAULT, default_value=False, script_name=script_name)[0],
      )
    except (KeyNotInListError, BadValueInListError):
      return None
    return arch

class ArchitectureHandler:

  def __init__(
    self,
    work_path,
    arch_path,
    script_path,
    log_path,
    work_rtl_path,
    work_script_path,
    work_log_path,
    work_report_path,
    process_group,
    command,
    eda_target_filename,
    fmax_status_filename,
    frequency_search_filename,
    param_settings_filename,
    valid_status,
    valid_frequency_search,
    forced_fmax_lower_bound,
    forced_fmax_upper_bound,
    forced_custom_freq_list,
    overwrite,
    continue_on_error=False,
    force_single_thread=False,
  ):
    self.work_path = work_path
    self.arch_path = arch_path
    self.script_path = script_path
    self.log_path = log_path
    self.work_rtl_path = work_rtl_path
    self.work_script_path = work_script_path
    self.work_log_path = work_log_path
    self.work_report_path = work_report_path

    self.process_group = process_group
    self.command = command
    
    self.eda_target_filename = eda_target_filename
    self.fmax_status_filename = fmax_status_filename
    self.frequency_search_filename = frequency_search_filename
    self.param_settings_filename = param_settings_filename
    
    self.valid_status = valid_status
    self.valid_frequency_search = valid_frequency_search

    self.forced_fmax_lower_bound = forced_fmax_lower_bound
    self.forced_fmax_upper_bound = forced_fmax_upper_bound
    self.forced_custom_freq_list = forced_custom_freq_list

    self.overwrite = overwrite
    self.continue_on_error = continue_on_error
    self.force_single_thread = force_single_thread

    self.reset_lists()

    self.odatix_path = os.path.realpath(os.path.join(self.script_path, ".."))

  def reset_lists(self):
    self.checked_arch_param = []
    self.banned_arch_param = []
    self.valid_archs = []
    self.cached_archs = []
    self.overwrite_archs = []
    self.error_archs = []
    self.incomplete_archs = []
    self.new_archs = []
    self.deprecation_notice_archs = []

  def get_architectures(self, architectures, targets, constraint_filename="", install_path="", range_mode=False):

    self.reset_lists()
    self.architecture_instances = []

    only_one_target = len(targets) == 1

    # Define user accessible variables
    variables = Variables(
      tool_install_path=os.path.realpath(install_path),
      odatix_path=OdatixSettings.odatix_path,
      odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
    )
      
    with open(self.eda_target_filename, 'r') as f:
      try:
        settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
      except Exception as e:
        printc.error("Settings file \"" + self.eda_target_filename + "\" is not a valid YAML file", script_name)
        printc.cyan("error details: ", end="", script_name=script_name)
        print(str(e))
        sys.exit(-1)
      
      try:
        script_copy_enable = read_from_list('script_copy_enable', settings_data, self.eda_target_filename, type=bool, optional=True, script_name=script_name)
        if script_copy_enable:
          script_copy_source = read_from_list('script_copy_source', settings_data, self.eda_target_filename, optional=True, script_name=script_name)        
          script_copy_source = replace_variables(script_copy_source, variables) # Replace variables in command

          if not os.path.isfile(script_copy_source):
            printc.note("The script source file \"" + script_copy_source + "\" specified in \"" + self.eda_target_filename + "\" does not exist. Script copy disabled.", script_name)
            raise BadValueInListError
        else:
          raise BadValueInListError
      except (KeyNotInListError, BadValueInListError):
        script_copy_enable = False
        script_copy_source = "/dev/null"

      try:
        target_settings = read_from_list("target_settings", settings_data, self.eda_target_filename, optional=True, print_error=False, script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        target_settings = {}

      for target in targets:
        # Overwrite existing script copy settings if there are target specific settings
        if target_settings != {}:
          try:
            this_target_settings = read_from_list(target, target_settings, self.eda_target_filename, optional=True, parent="target_settings", script_name=script_name)
          except (KeyNotInListError, BadValueInListError):
            this_target_settings = {}
            pass
          if this_target_settings != {}:
            try:
              script_copy_enable = read_from_list('script_copy_enable', this_target_settings, self.eda_target_filename, type=bool, optional=True, parent="target_settings/" + target, script_name=script_name)
              if script_copy_enable:
                script_copy_source = read_from_list('script_copy_source', this_target_settings, self.eda_target_filename, optional=True, parent="target_settings/" + target, script_name=script_name)        
                script_copy_source = replace_variables(script_copy_source, variables) # Replace variables in command

                if not os.path.isfile(script_copy_source):
                  printc.note("The script source file \"" + script_copy_source + "\" specified in \"" + self.eda_target_filename + "\" does not exist. Script copy disabled.", script_name)
                  raise BadValueInListError
            except (KeyNotInListError, BadValueInListError):
              script_copy_enable = False
              script_copy_source = "/dev/null"

        # Handle joker
        for arch in architectures:
          if arch.endswith("/*"):
            # get param dir (arch name before '/')
            arch_param_dir = re.sub(r'/\*', '', arch)

            # check if parameter dir exists
            arch_param = self.arch_path + '/' + arch_param_dir
            if isdir(arch_param):
              files = [f[:-4] for f in os.listdir(arch_param) if os.path.isfile(os.path.join(arch_param, f)) and f.endswith(".txt")]              
              joker_archs = [os.path.join(arch_param_dir, file) for file in files]
              architectures = architectures + joker_archs
            architectures.remove(arch)

        # Remove duplicates
        architectures = list(dict.fromkeys(architectures))

        for arch in architectures:
          architecture_instance = self.get_architecture(
            arch = arch,
            target = target, 
            only_one_target = only_one_target, 
            script_copy_enable = script_copy_enable, 
            script_copy_source = script_copy_source,
            synthesis = True,
            constraint_filename = constraint_filename,
            install_path = install_path,
            range_mode = range_mode
          )
          if not range_mode:
            if architecture_instance is not None:
              self.architecture_instances.append(architecture_instance)
          else:
            if architecture_instance is not None:
              for freq in architecture_instance.range_list:
                freq_arch = copy.copy(architecture_instance)
                formatted_freq = " {}@ {} MHz{}".format(printc.colors.GREY, freq, printc.colors.ENDC)
                unformatted_display_name = freq_arch.arch_display_name
                freq_arch.arch_display_name = freq_arch.arch_display_name + " @ " + str(freq) + " MHz"
                freq_arch.tmp_dir = os.path.join(freq_arch.tmp_dir, str(freq) + "MHz")
                freq_arch.tmp_script_path = os.path.join(freq_arch.tmp_dir, self.work_script_path)
                freq_arch.tmp_report_path = os.path.join(freq_arch.tmp_dir, self.work_report_path)
                freq_arch.target_frequency = freq

                # check if the architecture is in cache and has a status file
                status_file = os.path.join(freq_arch.tmp_dir, self.work_log_path, self.fmax_status_filename)
                if isdir(freq_arch.tmp_dir) and isfile(status_file):
                  # check if the previous synthesis has completed
                  sf = open(status_file, "r")
                  if self.valid_status in sf.read():
                    if self.overwrite:
                      printc.warning("Found cached results for \"" + unformatted_display_name + "\" @ " + str(freq) + " MHz with target \"" + target + "\".", script_name)
                      self.overwrite_archs.append(unformatted_display_name)
                      self.architecture_instances.append(freq_arch)
                      self.valid_archs.append(unformatted_display_name + formatted_freq)
                    else:
                      printc.note("Found cached results for \"" + unformatted_display_name + "\" @ " + str(freq) + " MHz with target \"" + target + "\". Skipping.", script_name)
                      self.cached_archs.append(freq_arch.arch_display_name)
                  else: 
                    printc.warning("The previous synthesis for \"" + unformatted_display_name + "\" @ " + str(freq) + " MHz with target \"" + target + "\" has not finished or the directory has been corrupted.", script_name)
                    self.incomplete_archs.append(freq_arch.arch_display_name)
                    self.architecture_instances.append(freq_arch)
                    self.valid_archs.append(unformatted_display_name + formatted_freq)
                  sf.close()
                else:
                  self.new_archs.append(unformatted_display_name + formatted_freq)
                  self.architecture_instances.append(freq_arch)
                  self.valid_archs.append(unformatted_display_name + formatted_freq)

    return self.architecture_instances
  
  def get_architecture(self, arch, target="", only_one_target=True, script_copy_enable=False, script_copy_source="/dev/null", synthesis=False, constraint_filename="", install_path="", range_mode=False):

    arch_full = arch.replace(" ", "")

    parts = [part.strip() for part in arch_full.split('+')]

    arch = parts[0]
    requested_param_domains = parts[1:]

    if arch.endswith(".txt"):
      arch = arch[:-4] 
      printc.note("'.txt' after the configuration name is not needed. Just use \"" + arch + "\"", script_name)

    if arch.endswith("/"):
      arch = arch[:-1] 

    # get param dir (arch name before '/')
    arch_param_dir = re.sub('/.*', '', arch)

    if len(requested_param_domains) > 0: 
      arch_param_dir_work = arch_param_dir + "-" + "-".join(map(str, requested_param_domains)).replace("/", "_")
      arch_display_name = arch + " [" + ", ".join(map(str, requested_param_domains)).replace("/", ":") + "]"
    else:
      arch_param_dir_work = arch_param_dir
      arch_display_name = arch_full

    if not only_one_target:
      arch_display_name = arch_display_name + " (" + target + ")"

    # get configuration (arch name after '/')
    arch_config = re.sub('.*/', '', arch)

    # check if there is a configuration specified
    if arch_config == arch_param_dir:
      printc.note("No architecture configuration selected for \"" + arch +  "\". Using default parameters", script_name)
      arch = arch + "/" + arch
      no_configuration = True
    else:
      no_configuration = False

    tmp_dir = os.path.join(self.work_path, target, arch_param_dir_work, arch_config)
    fmax_status_file = os.path.join(tmp_dir, self.log_path, self.fmax_status_filename)
    frequency_search_file = os.path.join(tmp_dir, self.log_path, self.frequency_search_filename)

    # check if arch_param has been banned
    if arch_param_dir in self.banned_arch_param:
      self.error_archs.append(arch_display_name)
      return None

    # check if parameter dir exists
    arch_param = os.path.join(self.arch_path, arch_param_dir)
    if not isdir(arch_param):
      printc.error("There is no directory \"" + arch_param_dir + "\" in directory \"" + self.arch_path + "\"", script_name)
      self.banned_arch_param.append(arch_param_dir)
      self.error_archs.append(arch_display_name)
      return None
    
    # check if settings file exists
    if not isfile(os.path.join(arch_param, self.param_settings_filename)):
      printc.error("There is no setting file \"" + self.param_settings_filename + "\" in directory \"" + arch_param + "\"", script_name)
      self.banned_arch_param.append(arch_param_dir)
      self.error_archs.append(arch_display_name)
      return None

    # get settings variables
    settings_filename = os.path.join(self.arch_path, arch_param_dir, self.param_settings_filename)
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
      try:
        top_level_filename = read_from_list('top_level_file', settings_data, settings_filename, script_name=script_name)
        top_level_module   = read_from_list('top_level_module', settings_data, settings_filename, script_name=script_name)
        clock_signal       = read_from_list('clock_signal', settings_data, settings_filename, script_name=script_name)
        reset_signal       = read_from_list('reset_signal', settings_data, settings_filename, script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None # if an identifier is missing

      file_copy_enable, defined = get_from_dict('file_copy_enable', settings_data, settings_filename, type=bool, silent=True, default_value=False, script_name=script_name)
      if defined:
        file_copy_source, source_defined = get_from_dict('file_copy_source', settings_data, settings_filename, behavior=Key.MANTADORY, script_name=script_name)
        file_copy_dest, dest_defined = get_from_dict('file_copy_dest', settings_data, settings_filename, behavior=Key.MANTADORY, script_name=script_name)
        if not source_defined or not dest_defined:
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
          return None
      else:
        file_copy_source = ""
        file_copy_dest = ""
      
      generate_command = ""
      generate_rtl, defined = get_from_dict('generate_rtl', settings_data, settings_filename, type=bool, silent=True, script_name=script_name)
      if not defined:
        generate_rtl = False

      if generate_rtl:
        local_rtl_path, _ = get_from_dict('generate_output', settings_data, settings_filename, default_value=self.work_rtl_path, script_name=script_name)
        rtl_path = self.work_rtl_path 
        generate_command, defined = get_from_dict('generate_command', settings_data, settings_filename, silent=True, script_name=script_name)
        if defined:
          generate_rtl = True
        else:
          printc.error("Cannot find key \"generate_command\" in \"" + settings_filename + "\" while generate_rtl=true", script_name)
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
          generate_rtl = False
          return None
      else:
        local_rtl_path = self.work_rtl_path 
        rtl_path, defined = get_from_dict('rtl_path', settings_data, settings_filename, script_name=script_name)
        if not defined:
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
          return None

      top_level = os.path.join(rtl_path, top_level_filename)
      work_top_level = os.path.join(local_rtl_path, top_level_filename)

      use_parameters, start_delimiter, stop_delimiter, param_target_filename = self.get_use_parameters(arch, arch_display_name, settings_data, settings_filename, work_top_level, no_configuration, arch_param_dir=arch_param_dir)
      if use_parameters is None or start_delimiter is None or stop_delimiter is None or param_target_filename is None:
        return None

      design_path, design_path_defined = get_from_dict('design_path', settings_data, settings_filename, silent=True, script_name=script_name)
      if not defined:
        design_path = None
        if generate_rtl:
          printc.error("Cannot find key \"design_path\" in \"" + settings_filename + "\" while generate_rtl=true", script_name)
          self.banned_arch_param.append(arch_param_dir)
          return None
      
      design_path_whitelist, _ = get_from_dict("design_path_whitelist", settings_data, settings_filename, type=list, default_value=[], silent=True, script_name=script_name)
      design_path_blacklist, _ = get_from_dict("design_path_blacklist", settings_data, settings_filename, type=list, default_value=[], silent=True, script_name=script_name)
      # if param_target_file is None:
      #   printc.error("Cannot find key \"param_target_file\" in \"" + settings_filename + "\" while generate_rtl=true", script_name)
      #   printc.note("\"param_target_file\" is the file in which parameters will be replaced before running the generate command", script_name)

    if not generate_rtl:
      # check if rtl path exists
      if not isdir(rtl_path):
        printc.error("The rtl path \"" + rtl_path + "\" specified in \"" + settings_filename + "\" does not exist", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None

      # check if top level file path exists
      if not isfile(top_level):
        printc.error("The top level file \"" + top_level_filename + "\" specified in \"" + settings_filename + "\" does not exist", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None

      # check if the top level module name exists in the top level file, at least
      f = open(top_level, "r")
      if top_level_module not in f.read():
        printc.error("There is no occurence of top level module name \"" + top_level_module + "\" in top level file \"" + top_level + "\"", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        f.close()
        return None
      f.close()
      
      # check if the top clock name exists in the top level file, at least
      f = open(top_level, "r")
      if clock_signal not in f.read():
        printc.error("There is no occurence of clock signal name \"" + clock_signal + "\" in top level file \"" + top_level + "\"", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        f.close()
        return None
      f.close()
      
      # check if the top reset name exists in the top level file, at least
      f = open(top_level, "r")
      if clock_signal not in f.read():
        printc.error("There is no occurence of reset signal name \"" + reset_signal + "\" in top level file \"" + top_level + "\"", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        f.close()
        return None
      f.close()

    # check if param file exists
    if not no_configuration:
      if not isfile(os.path.join(self.arch_path, arch + '.txt')):
        printc.error("The parameter file \"" + arch + ".txt\" does not exist in directory \"" + os.path.join(self.arch_path, arch_param_dir) + "\"", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None
    
    if len(requested_param_domains) > 0:
      param_domains = ParamDomain.get_param_domains(requested_param_domains, self.param_settings_filename, arch_param, work_top_level)
      if param_domains is None:
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None
    else:
      param_domains = []
      
    # optional settings
    formatted_bound = ""
    fmax_lower_bound = 0
    fmax_upper_bound = 0
    range_list = []

    if synthesis:
      fmax_lower_bound, fmax_upper_bound, range_list, warn_fmax_obsolete = self.get_frequency_settings(
        arch_config=arch_config,
        target=target, 
        settings_data=settings_data, 
        settings_filename=settings_filename, 
        range_mode=range_mode
      )

      # Override by bounds from --from and --to if used
      if self.forced_fmax_lower_bound is not None:
        fmax_lower_bound = self.forced_fmax_lower_bound
      if self.forced_fmax_upper_bound is not None:
        fmax_upper_bound = self.forced_fmax_upper_bound
      if self.forced_custom_freq_list is not None and self.forced_custom_freq_list != []:
        range_list = self.forced_custom_freq_list

      if warn_fmax_obsolete and not arch_param_dir in self.deprecation_notice_archs:
        self.deprecation_notice_archs.append(arch_param_dir)
        printc.warning("{} -> 'fmax_lower_bound' and 'fmax_upper_bound' are deprecated".format(settings_filename), script_name)
        printc.note("Use this syntax instead:", script_name)
        printc.magenta("fmax_synthesis:")
        printc.magenta("  lower_bound: XXX")
        printc.magenta("  upper_bound: XXX")

      # check if frequencies are valid
      if range_mode:
        if range_list is None or range_list == []: 
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
          return None
      else:
        if not ArchitectureHandler.check_bounds(fmax_lower_bound, fmax_upper_bound):
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
          return None

      fmax_lower_bound = str(fmax_lower_bound)
      fmax_upper_bound = str(fmax_upper_bound)

      formatted_bound = " {}({} - {} MHz){}".format(printc.colors.GREY, fmax_lower_bound, fmax_upper_bound, printc.colors.ENDC)

      # check if the architecture is in cache and has a status file
      if not range_mode:
        if isdir(tmp_dir) and isfile(fmax_status_file) and isfile(frequency_search_file):
          # check if the previous synth_fmax has completed
          sf = open(fmax_status_file, "r")
          if self.valid_status in sf.read():
            ff = open(frequency_search_file, "r")
            if self.valid_frequency_search in ff.read():
              if self.overwrite:
                printc.warning("Found cached results for \"" + arch + "\" with target \"" + target + "\".", script_name)
                self.overwrite_archs.append(arch_display_name + formatted_bound)
              else:
                printc.note("Found cached results for \"" + arch + "\" with target \"" + target + "\". Skipping.", script_name)
                self.cached_archs.append(arch_display_name)
                return None
            else:
              printc.warning("The previous synthesis for \"" + arch + "\" did not result in a valid maximum operating frequency.", script_name)
              self.incomplete_archs.append(arch_display_name + formatted_bound)
            ff.close()
          else: 
            printc.warning("The previous synthesis for \"" + arch + "\" has not finished or the directory has been corrupted.", script_name)
            self.incomplete_archs.append(arch_display_name + formatted_bound)
          sf.close()
        else:
          if not range_mode:
            self.new_archs.append(arch_display_name + formatted_bound)


    # Retrieve target-specific settings if they exist
    target_specific_data, target_specific_defined = get_from_dict(target, settings_data, settings_filename, silent=True)

    # target specific file copy
    if target_specific_defined:
      try:
        _file_copy_enable = read_from_list('file_copy_enable', target_specific_data, settings_filename, optional=True, print_error=False, type=bool, script_name=script_name)
        try:
          _file_copy_source = read_from_list('file_copy_source', target_specific_data, settings_filename, optional=True, script_name=script_name)
          _file_copy_dest = read_from_list('file_copy_dest', target_specific_data, settings_filename, optional=True, script_name=script_name)
          file_copy_enable = _file_copy_enable
          file_copy_source = _file_copy_source
          file_copy_dest = _file_copy_dest
        except (KeyNotInListError, BadValueInListError):
          pass
      except KeyNotInListError:
        pass
      except BadValueInListError:
        printc.note("Value \"" + str(_file_copy_enable) + "\" for key \"" + 'file_copy_enable' + "\"" + ", inside list \"" + "target_settings/" + target + "\"," + " in \"" + settings_filename + "\" is of type \"" + _file_copy_enable.__class__.__name__ + "\" while it should be of type \"bool\". Using default values instead.", script_name)
    
    # Define user accessible variables
    variables = Variables(
      tool_install_path=os.path.realpath(install_path),
      odatix_path=OdatixSettings.odatix_path,
      odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
    )

    # Replace variables in command
    file_copy_source = replace_variables(file_copy_source, variables)

    # check file copy
    if file_copy_enable:
      if not isfile(file_copy_source):
        printc.error("The source file to copy \"" + file_copy_source + "\" does not exist", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None

    # passed all check: added to the list
    if not range_mode:
      self.valid_archs.append(arch_display_name)
      self.checked_arch_param.append(arch_param_dir)

    lib_name = "LIB_" + target + "_" + arch.replace("/", "_")

    tmp_script_path = os.path.join(tmp_dir, self.work_script_path)
    tmp_report_path = os.path.join(tmp_dir, self.work_report_path)
    tmp_log_path = os.path.join(tmp_dir, self.work_log_path)

    arch_instance = Architecture(
      arch_name=arch,
      arch_display_name=arch_display_name,
      lib_name=lib_name,
      target=target,
      local_rtl_path=local_rtl_path,
      tmp_script_path=tmp_script_path,
      tmp_log_path=tmp_log_path,
      tmp_report_path=tmp_report_path,
      tmp_dir=tmp_dir,
      design_path=design_path,
      design_path_whitelist=design_path_whitelist,
      design_path_blacklist=design_path_blacklist,
      rtl_path=rtl_path,
      log_path=self.log_path,
      arch_path=self.arch_path,
      clock_signal=clock_signal,
      reset_signal=reset_signal,
      top_level_module=top_level_module,
      top_level_filename=top_level_filename,
      file_copy_enable=file_copy_enable,
      file_copy_source=file_copy_source,
      file_copy_dest=file_copy_dest,
      script_copy_enable = script_copy_enable,
      script_copy_source = script_copy_source,
      fmax_lower_bound=fmax_lower_bound,
      fmax_upper_bound=fmax_upper_bound,
      range_list=range_list,
      target_frequency=0,
      param_target_filename=param_target_filename,
      generate_rtl=generate_rtl,
      use_parameters=use_parameters,
      start_delimiter=start_delimiter,
      stop_delimiter=stop_delimiter,
      generate_command=generate_command,
      constraint_filename=constraint_filename,
      install_path=install_path,
      param_domains=param_domains,
      continue_on_error=self.continue_on_error,
      force_single_thread=self.force_single_thread,
    )

    return arch_instance

  def get_use_parameters(self, arch, arch_display_name, settings_data, settings_filename, top_level_file, no_configuration=False, add_to_error_list=True, arch_param_dir=""):

    use_parameters, start_delimiter, stop_delimiter, param_target_filename = ParamDomain.get_param_delimiters(settings_data, settings_filename, top_level_file)

    if no_configuration:
      use_parameters = False
    else:
      if use_parameters:
        # check if parameter file exists
        param_file = os.path.join(self.arch_path, arch + ".txt")
        if not isfile(param_file):
          printc.error("There is no parameter file \"" + param_file + "\", while \"use_parameters\" is true", script_name)
          if add_to_error_list:
            self.error_archs.append(arch_display_name)
          return None, None, None, None

    return use_parameters, start_delimiter, stop_delimiter, param_target_filename

  @staticmethod
  def get_frequency_settings(arch_config, target, settings_data, settings_filename, range_mode):
    """
    Retrieves frequency synthesis settings from the YAML configuration.

    Args:
        arch_config (str): The architecture configuration.
        target (str): The target FPGA/ASIC.
        settings_data (dict): The parsed YAML settings data.
        settings_filename (str): Name of the YAML file.
        range_mode (bool): Whether to use custom frequency synthesis.

    Returns:
        tuple: (fmax_lower_bound, fmax_upper_bound, custom_freq_list, warn_fmax_obsolete).
    """

    # Defaults
    fmax_lower_bound = None
    fmax_upper_bound = None
    custom_freq_list = []
    warn_fmax_obsolete = False

    target_fmax_defined = False
    target_custom_freq_defined = False
    arch_specific_defined = False
    arch_fmax_defined = False
    arch_custom_freq_defined = False

    # Retrieve general settings
    global_fmax_data, global_fmax_defined =  get_from_dict("fmax_synthesis", settings_data, settings_filename, silent=True)
    global_custom_freq_data, global_custom_freq_defined = get_from_dict("custom_freq_synthesis", settings_data, settings_filename, silent=True)

    # Retrieve target-specific settings
    target_specific_data, target_specific_defined = get_from_dict(target, settings_data, settings_filename, silent=True)
    if target_specific_defined:
      target_fmax_data, target_fmax_defined =  get_from_dict("fmax_synthesis", target_specific_data, settings_filename, silent=True)
      target_custom_freq_data, target_custom_freq_defined = get_from_dict("custom_freq_synthesis", target_specific_data, settings_filename, silent=True)

      # Retrieve architecture-specific settings
      arch_specific_data, arch_specific_defined = get_from_dict(arch_config, target_specific_data, settings_filename, silent=True)
      if arch_specific_defined:
        arch_fmax_data, arch_fmax_defined =  get_from_dict("fmax_synthesis", arch_specific_data, settings_filename, silent=True)
        arch_custom_freq_data, arch_custom_freq_defined = get_from_dict("custom_freq_synthesis", arch_specific_data, settings_filename, silent=True)

    if range_mode: # Custom frequency synthesis

      # Get lower bound
      lower_bound_defined = False
      if arch_custom_freq_defined:
        range_lower_bound, lower_bound_defined = get_from_dict("lower_bound", arch_custom_freq_data, settings_filename, default_value=None, silent=True)
      if not lower_bound_defined and target_custom_freq_defined:
        range_lower_bound, lower_bound_defined = get_from_dict("lower_bound", target_custom_freq_data, settings_filename, default_value=None, silent=True)
      if not lower_bound_defined and global_custom_freq_defined:
        range_lower_bound, lower_bound_defined = get_from_dict("lower_bound", global_custom_freq_data, settings_filename, default_value=None, silent=True)

      # Get upper bound
      upper_bound_defined = False
      if arch_custom_freq_defined:
        range_upper_bound, upper_bound_defined = get_from_dict("upper_bound", arch_custom_freq_data, settings_filename, default_value=None, silent=True)
      if not upper_bound_defined and target_custom_freq_defined:
        range_upper_bound, upper_bound_defined = get_from_dict("upper_bound", target_custom_freq_data, settings_filename, default_value=None, silent=True)
      if not upper_bound_defined and global_custom_freq_defined:
        range_upper_bound, upper_bound_defined = get_from_dict("upper_bound", global_custom_freq_data, settings_filename, default_value=None, silent=True)

      # Get step
      step_defined = False
      if arch_custom_freq_defined:
        range_step, step_defined = get_from_dict("step", arch_custom_freq_data, settings_filename, default_value=None, silent=True)
      if not step_defined and target_custom_freq_defined:
        range_step, step_defined = get_from_dict("step", target_custom_freq_data, settings_filename, default_value=None, silent=True)
      if not step_defined and global_custom_freq_defined:
        range_step, step_defined = get_from_dict("step", global_custom_freq_data, settings_filename, default_value=None, silent=True)

      # Get list
      list_defined = False
      list_defined_arch = False
      list_defined_target = False
      list_defined_global = False
      list_append = False
      if arch_custom_freq_defined:
        custom_freq_list, list_defined_arch = get_from_dict("list", arch_custom_freq_data, settings_filename, default_value=None, silent=True)
        if list_defined_arch:
          list_append, _ = get_from_dict("list_append", arch_custom_freq_data, settings_filename, default_value=False, silent=True)
      if target_custom_freq_defined:
        tmp_list, list_defined_target = get_from_dict("list", target_custom_freq_data, settings_filename, default_value=None, silent=True)
        if list_defined_target:
          if not list_defined_arch:
            custom_freq_list = tmp_list
          elif list_append:
            custom_freq_list = custom_freq_list + tmp_list
          list_append, _ = get_from_dict("list_append", target_custom_freq_data, settings_filename, default_value=False, silent=True)
      if global_custom_freq_defined:
        tmp_list, list_defined_global = get_from_dict("list", global_custom_freq_data, settings_filename, default_value=None, silent=True)
        if list_defined_global:
          if not list_defined_target:
            custom_freq_list = tmp_list
          elif list_append:
            custom_freq_list = custom_freq_list + tmp_list

      list_defined = list_defined_global or list_defined_target or list_defined_arch
      if not list_defined:
        custom_freq_list = []

      if not step_defined or (step_defined and (range_step == 0 or range_step == False)): # Check if range is deactivated
        range_list = []
      else:
        if lower_bound_defined and upper_bound_defined and step_defined:
          if ArchitectureHandler.check_bounds(range_lower_bound, range_upper_bound, range_step, synth_type="custom frequency synthesis"):
            range_list = ArchitectureHandler.create_list_from_range(range_lower_bound, range_upper_bound, range_step)
            custom_freq_list = custom_freq_list + range_list

      # Check if a list is defined
      if len(custom_freq_list) == 0:
        printc.error('Could not find any valid custom frequency definition in "{}" for architecture configuration "{}" with target "{}"'.format(settings_filename, arch_config, target), script_name)
        printc.note('You can define custom synthesis frequencies like this:', script_name)
        printc.magenta("custom_freq_synthesis:")
        printc.magenta("  lower_bound: XXX")
        printc.magenta("  upper_bound: XXX")
        printc.magenta("  step: XXX")
        printc.cyan("or ")
        printc.magenta("custom_freq_synthesis:")
        printc.magenta("  step: No")
        printc.magenta("  list: [XXX, XXX, XXX]")
        printc.cyan("or ")
        printc.magenta("custom_freq_synthesis:")
        printc.magenta("  lower_bound: XXX")
        printc.magenta("  upper_bound: XXX")
        printc.magenta("  step: XXX")
        printc.magenta("  list: [XXX, XXX, XXX] # append to the list generated by range")

      return None, None, custom_freq_list, warn_fmax_obsolete

    else: # fmax synthesis

      # Legacy fallback for older odatix version
      lower_defined = False
      if target_specific_defined:
        fmax_lower_bound, lower_defined = get_from_dict("fmax_lower_bound", target_specific_data, settings_filename, silent=True)
      if not lower_defined and arch_specific_defined:
        fmax_lower_bound, lower_defined = get_from_dict("fmax_lower_bound", arch_specific_data, settings_filename, silent=True)
      upper_defined = False
      if target_specific_defined:
        fmax_upper_bound, upper_defined = get_from_dict("fmax_upper_bound", target_specific_data, settings_filename, silent=True)
      if not upper_defined and arch_specific_defined:
        fmax_upper_bound, upper_defined = get_from_dict("fmax_upper_bound", arch_specific_data, settings_filename, silent=True)
      
      # Deprecation warning
      if lower_defined or upper_defined:
        warn_fmax_obsolete = True

      # Get lower bound
      defined = False
      if arch_fmax_defined:
        fmax_lower_bound, defined = get_from_dict("lower_bound", arch_fmax_data, settings_filename, default_value=None, silent=True)
      if not defined and target_fmax_defined:
        fmax_lower_bound, defined = get_from_dict("lower_bound", target_fmax_data, settings_filename, default_value=None, silent=True)
      if not defined and global_fmax_defined:
        fmax_lower_bound, defined = get_from_dict("lower_bound", global_fmax_data, settings_filename, default_value=None, silent=True)

      # Get upper bound
      defined = False
      if arch_fmax_defined:
        fmax_upper_bound, defined = get_from_dict("upper_bound", arch_fmax_data, settings_filename, default_value=None, silent=True)
      if not defined and target_fmax_defined:
        fmax_upper_bound, defined = get_from_dict("upper_bound", target_fmax_data, settings_filename, default_value=None, silent=True)
      if not defined and global_fmax_defined:
        fmax_upper_bound, defined = get_from_dict("upper_bound", global_fmax_data, settings_filename, default_value=None, silent=True)

      # Check if bounds are defined
      if fmax_lower_bound is None:
        printc.error('Lower bound for fmax synthesis is not defined in "{}" for architecture configuration "{}" with target "{}"'.format(settings_filename, arch_config, target), script_name)
      if fmax_upper_bound is None:
        printc.error('Upper bound for fmax synthesis is not defined in "{}" for architecture configuration "{}" with target "{}"'.format(settings_filename, arch_config, target), script_name)
      if fmax_lower_bound is None or fmax_upper_bound is None:
        printc.note('You can define fmax synthesis frequency bounds like this:', script_name)
        printc.magenta("fmax_synthesis:")
        printc.magenta("  lower_bound: XXX")
        printc.magenta("  upper_bound: XXX")
        return None, None, None, warn_fmax_obsolete

      return fmax_lower_bound, fmax_upper_bound, None, warn_fmax_obsolete

  def create_list_from_range(lower_bound, upper_bound, step):
    return list(range(lower_bound, upper_bound + 1, step))

  def check_bounds(lower_bound, upper_bound, step=0, synth_type="fmax synthesis"):
    success = True
    if not isinstance(lower_bound, int):
      printc.error('Lower bound for {} is "{}" which is a "{}" while it should be an integer'.format(synth_type, lower_bound, type(lower_bound).__name__), script_name)
      success =  False
    if not isinstance(upper_bound, int):
      printc.error('Upper bound for {} is "{}" which is a "{}" while it should be an integer'.format(synth_type, upper_bound, type(upper_bound).__name__), script_name)
      success =  False
    if not isinstance(step, int):
      printc.error('Step for {} is "{}" which is a "{}" while it should be an integer or "No"'.format(synth_type, upper_bound, type(upper_bound).__name__), script_name)
      success =  False
    if success:
      if upper_bound <= lower_bound:
        printc.error("The upper bound ({}) for {} must be strictly greater than the lower bound ({})".format(synth_type, upper_bound, lower_bound), script_name)
        success =  False
    return success

  def print_summary(self):
    ArchitectureHandler.print_arch_list(self.new_archs, "New architectures", printc.colors.ENDC)
    ArchitectureHandler.print_arch_list(self.incomplete_archs, "Incomplete results (will be overwritten)", printc.colors.YELLOW)
    ArchitectureHandler.print_arch_list(self.cached_archs, "Existing results (skipped -> use '-o' to overwrite)", printc.colors.CYAN)
    ArchitectureHandler.print_arch_list(self.overwrite_archs, "Existing results (will be overwritten)", printc.colors.YELLOW)
    ArchitectureHandler.print_arch_list(self.error_archs, "Invalid settings, (skipped, see errors above)", printc.colors.RED)

  def get_valid_arch_count(self):
    return len(self.valid_archs)

  @staticmethod
  def print_arch_list(arch_list, description, color):
    if not len(arch_list) > 0:
      return

    print()
    printc.bold(description + ":")
    for arch in arch_list:
      printc.color(color)
      print("  - " + arch)
    printc.endc()

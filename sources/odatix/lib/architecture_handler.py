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

from os.path import isfile
from os.path import isdir

from odatix.lib.utils import *
import odatix.lib.printc as printc

script_name = os.path.basename(__file__)

odatix_path_pattern = re.compile(r"\$odatix")

class Architecture:
  def __init__(self, arch_name, arch_display_name, lib_name, target, tmp_script_path, tmp_report_path, tmp_dir, design_path, rtl_path, log_path, arch_path,
               clock_signal, reset_signal, top_level_module, top_level_filename, use_parameters, start_delimiter, stop_delimiter,
               file_copy_enable, file_copy_source, file_copy_dest, script_copy_enable, script_copy_source, 
               fmax_lower_bound, fmax_upper_bound, param_target_filename, generate_rtl, generate_command, constraint_filename):
    self.arch_name = arch_name
    self.arch_display_name = arch_display_name
    self.lib_name = lib_name
    self.target = target
    self.tmp_script_path = tmp_script_path
    self.tmp_report_path = tmp_report_path
    self.tmp_dir = tmp_dir
    self.design_path = design_path
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
    self.param_target_filename = param_target_filename
    self.use_parameters = use_parameters
    self.start_delimiter = start_delimiter
    self.stop_delimiter = stop_delimiter
    self.generate_rtl = generate_rtl
    self.generate_command = generate_command
    self.constraint_filename = constraint_filename

  def write_yaml(arch, config_file): 
    yaml_data = {
      'arch_name': arch.arch_name,
      'arch_display_name': arch.arch_display_name,
      'lib_name': arch.lib_name,
      'target': arch.target,
      'script_path': arch.tmp_script_path,
      'report_path': arch.tmp_report_path,
      'tmp_path': arch.tmp_dir,
      'design_path': arch.design_path,
      'rtl_path': arch.rtl_path,
      'log_path': arch.log_path,
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
      'param_target_filename': arch.param_target_filename,
      'generate_rtl': arch.generate_rtl,
      'generate_command': arch.generate_command,
      'constraint_filename': arch.constraint_filename
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
        arch_name             = read_from_list("arch_name", yaml_data, config_file, script_name=script_name),
        arch_display_name     = read_from_list("arch_display_name", yaml_data, config_file, script_name=script_name),
        lib_name              = read_from_list("lib_name", yaml_data, config_file, script_name=script_name),
        target                = read_from_list("target", yaml_data, config_file, script_name=script_name),
        tmp_script_path       = read_from_list("script_path", yaml_data, config_file, script_name=script_name),
        tmp_report_path       = read_from_list("report_path", yaml_data, config_file, script_name=script_name),
        tmp_dir               = read_from_list("tmp_path", yaml_data, config_file, script_name=script_name),
        design_path           = read_from_list("design_path", yaml_data, config_file, script_name=script_name),
        rtl_path              = read_from_list("rtl_path", yaml_data, config_file, script_name=script_name),
        log_path              = read_from_list("log_path", yaml_data, config_file, script_name=script_name),
        arch_path             = read_from_list("arch_path", yaml_data, config_file, script_name=script_name),
        clock_signal          = read_from_list("clock_signal", yaml_data, config_file, script_name=script_name),
        reset_signal          = read_from_list("reset_signal", yaml_data, config_file, script_name=script_name),
        top_level_module      = read_from_list("top_level_module", yaml_data, config_file, script_name=script_name),
        top_level_filename    = read_from_list("top_level_file", yaml_data, config_file, script_name=script_name),
        use_parameters        = read_from_list("use_parameters", yaml_data, config_file, script_name=script_name),
        start_delimiter       = read_from_list("start_delimiter", yaml_data, config_file, script_name=script_name),
        stop_delimiter        = read_from_list("stop_delimiter", yaml_data, config_file, script_name=script_name),
        file_copy_enable      = read_from_list("file_copy_enable", yaml_data, config_file, script_name=script_name),
        file_copy_source      = read_from_list("file_copy_source", yaml_data, config_file, script_name=script_name),
        file_copy_dest        = read_from_list("file_copy_dest", yaml_data, config_file, script_name=script_name),
        script_copy_enable    = read_from_list("script_copy_enable", yaml_data, config_file, script_name=script_name),
        script_copy_source    = read_from_list("script_copy_source", yaml_data, config_file, script_name=script_name),
        fmax_lower_bound      = read_from_list("fmax_lower_bound", yaml_data, config_file, script_name=script_name),
        fmax_upper_bound      = read_from_list("fmax_upper_bound", yaml_data, config_file, script_name=script_name),
        param_target_filename = read_from_list("param_target_filename", yaml_data, config_file, script_name=script_name),
        generate_rtl          = read_from_list("generate_rtl", yaml_data, config_file, script_name=script_name),
        generate_command      = read_from_list("generate_command", yaml_data, config_file, script_name=script_name),
        constraint_filename   = read_from_list("constraint_filename", yaml_data, config_file, script_name=script_name)
      )
    except (KeyNotInListError, BadValueInListError):
      return None
    return arch

class ArchitectureHandler:

  def __init__(self, work_path, arch_path, script_path, work_script_path, work_report_path, log_path, process_group, eda_target_filename, fmax_status_filename, frequency_search_filename, param_settings_filename, valid_status, valid_frequency_search, default_fmax_lower_bound, default_fmax_upper_bound, overwrite):
    self.work_path = work_path
    self.arch_path = arch_path
    self.script_path = script_path
    self.work_script_path = work_script_path
    self.work_report_path = work_report_path
    self.log_path = log_path

    self.process_group = process_group
    
    self.eda_target_filename = eda_target_filename
    self.fmax_status_filename = fmax_status_filename
    self.frequency_search_filename = frequency_search_filename
    self.param_settings_filename = param_settings_filename
    
    self.valid_status = valid_status
    self.valid_frequency_search = valid_frequency_search

    self.default_fmax_lower_bound = default_fmax_lower_bound
    self.default_fmax_upper_bound = default_fmax_upper_bound

    self.overwrite = overwrite
    self.reset_lists()

    self.odatix_path = os.path.realpath(os.path.join(self.script_path, ".."))

  def reset_lists(self):
    self.banned_arch_param = []
    self.valid_archs = []
    self.cached_archs = []
    self.overwrite_archs = []
    self.error_archs = []
    self.incomplete_archs = []
    self.new_archs = []

  def get_architectures(self, architectures, targets, constraint_filename=""):

    self.reset_lists()
    self.architecture_instances = []

    only_one_target = len(targets) == 1
      
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
          script_copy_source = os.path.realpath(re.sub(odatix_path_pattern, self.odatix_path, script_copy_source))
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
                script_copy_source = os.path.realpath(re.sub(odatix_path_pattern, self.odatix_path, script_copy_source))

                if not os.path.isfile(script_copy_source):
                  printc.note("The script source file \"" + script_copy_source + "\" specified in \"" + self.eda_target_filename + "\" does not exist. Script copy disabled.", script_name)
                  raise BadValueInListError
            except (KeyNotInListError, BadValueInListError):
              script_copy_enable = False
              script_copy_source = "/dev/null"

        for arch in architectures:
          architecture_instance = self.get_architecture(
            arch = arch,
            target = target, 
            only_one_target = only_one_target, 
            script_copy_enable = script_copy_enable, 
            script_copy_source = script_copy_source,
            synthesis = True,
            constraint_filename = constraint_filename
          )
          if architecture_instance is not None:
            self.architecture_instances.append(architecture_instance)

    return self.architecture_instances
  
  def get_architecture(self, arch, target="", only_one_target=True, script_copy_enable=False, script_copy_source="/dev/null", synthesis=False, constraint_filename=""):

    if arch.endswith(".txt"):
      arch = arch[:-4] 
      printc.note("'.txt' after the configuration name is not needed. Just use \"" + arch + "\"", script_name)

    if arch.endswith("/"):
      arch = arch[:-1] 

    if only_one_target:
      arch_display_name = arch
    else:
      arch_display_name = arch + " (" + target + ")"

    # get param dir (arch name before '/')
    arch_param_dir = re.sub('/.*', '', arch)

    # get param dir (arch name after '/')
    arch_suffix = re.sub('.*/', '', arch)

    # check if there is a configuration specified
    if arch_suffix == arch_param_dir:
      printc.note("No architecture configuration selected for \"" + arch +  "\". Using default parameters", script_name)
      arch = arch + "/" + arch
      no_configuration = True
    else:
      no_configuration = False

    tmp_dir = self.work_path + '/' + target + '/' + arch
    fmax_status_file = tmp_dir + '/' + self.log_path + '/' + self.fmax_status_filename
    frequency_search_file = tmp_dir + '/' + self.log_path + '/' + self.frequency_search_filename

    # check if arch_param has been banned
    if arch_param_dir in self.banned_arch_param:
      self.error_archs.append(arch_display_name)
      return None

    # check if parameter dir exists
    arch_param = self.arch_path + '/' + arch_param_dir
    if not isdir(arch_param):
      printc.error("There is no directory \"" + arch_param_dir + "\" in directory \"" + self.arch_path + "\"", script_name)
      self.banned_arch_param.append(arch_param_dir)
      self.error_archs.append(arch_display_name)
      return None
    
    # check if settings file exists
    if not isfile(arch_param + '/' + self.param_settings_filename):
      printc.error("There is no setting file \"" + self.param_settings_filename + "\" in directory \"" + arch_param + "\"", script_name)
      self.banned_arch_param.append(arch_param_dir)
      self.error_archs.append(arch_display_name)
      return None

    # get settings variables
    settings_filename = self.arch_path + '/' + arch_param_dir + '/' + self.param_settings_filename
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
        rtl_path           = read_from_list('rtl_path', settings_data, settings_filename, script_name=script_name)
        top_level_filename = read_from_list('top_level_file', settings_data, settings_filename, script_name=script_name)
        top_level_module   = read_from_list('top_level_module', settings_data, settings_filename, script_name=script_name)
        clock_signal       = read_from_list('clock_signal', settings_data, settings_filename, script_name=script_name)
        reset_signal       = read_from_list('reset_signal', settings_data, settings_filename, script_name=script_name)
        file_copy_enable   = read_from_list('file_copy_enable', settings_data, settings_filename, type=bool, script_name=script_name)
        file_copy_source   = read_from_list('file_copy_source', settings_data, settings_filename, script_name=script_name)
        file_copy_dest     = read_from_list('file_copy_dest', settings_data, settings_filename, script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None # if an identifier is missing

      use_parameters, start_delimiter, stop_delimiter = self.get_use_parameters(arch, arch_display_name, settings_data, settings_filename, no_configuration, arch_param_dir=arch_param_dir)
      if use_parameters is None or start_delimiter is None or stop_delimiter is None:
        return None

      generate_command = ""
      try:
        generate_rtl = read_from_list('generate_rtl', settings_data, settings_filename, type=bool, optional=True, print_error=False, script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        generate_rtl = False

      if generate_rtl:
        try:
          generate_command = read_from_list('generate_command', settings_data, settings_filename, print_error=False, script_name=script_name)
          generate_rtl = True
        except (KeyNotInListError, BadValueInListError):
          printc.error("Cannot find key \"generate_command\" in \"" + settings_filename + "\" while generate_rtl=true", script_name)
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
          generate_rtl = False
          return None

      try:
        design_path = read_from_list('design_path', settings_data, settings_filename, optional=True, print_error=False, script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        design_path = -1
        if generate_rtl:
          printc.error("Cannot find key \"design_path\" in \"" + settings_filename + "\" while generate_rtl=true", script_name)
          self.banned_arch_param.append(arch_param_dir)
          return None
      
      try:
        param_target_filename = read_from_list('param_target_file', settings_data, settings_filename, optional=True, print_error=False, script_name=script_name)
        if design_path == -1:
          printc.error("Cannot find key \"design_path\" in \"" + settings_filename + "\" while param_target_file is defined", script_name)
          self.banned_arch_param.append(arch_param_dir)
          return None
        # check if param target file path exists
        param_target_file = design_path + '/' + param_target_filename
        if not isfile(param_target_file): 
          printc.error("The parameter target file \"" + param_target_filename + "\" specified in \"" + settings_filename + "\" does not exist", script_name)
          self.banned_arch_param.append(arch_param_dir)
          return None
      except (KeyNotInListError, BadValueInListError):
        param_target_filename = 'rtl/' + top_level_filename

    if not generate_rtl:
      # check if rtl path exists
      if not isdir(rtl_path):
        printc.error("The rtl path \"" + rtl_path + "\" specified in \"" + settings_filename + "\" does not exist", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None

      # check if top level file path exists
      top_level = rtl_path + '/' + top_level_filename
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
      if not isfile(self.arch_path + '/' + arch + '.txt'):
        printc.error("The parameter file \"" + arch + ".txt\" does not exist in directory \"" + self.arch_path + "/" + arch_param_dir + "\"", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None

    # optional settings
    formatted_bound = ""
    fmax_lower_bound_ok = False
    fmax_upper_bound_ok = False
    fmax_lower_bound = 0
    fmax_upper_bound = 0

    target_options = read_from_list(target, settings_data, settings_filename, optional=True, raise_if_missing=False, print_error=False, script_name=script_name)
    
    if synthesis:
      if target_options == False:
        printc.note("Cannot find optional target-specific options for target \"" + target + "\" in \"" + settings_filename + "\". Using default frequency bounds instead: " + "[{},{}] MHz.".format(self.default_fmax_lower_bound, self.default_fmax_upper_bound), script_name)
        fmax_lower_bound = self.default_fmax_lower_bound
        fmax_upper_bound = self.default_fmax_upper_bound
      else:
        architectures_bounds = read_from_list('architectures', target_options, self.eda_target_filename, optional=True, raise_if_missing=False, print_error=False, script_name=script_name)
        if architectures_bounds:
          this_architecture_bounds = read_from_list(arch_suffix, architectures_bounds, self.eda_target_filename, optional=True, raise_if_missing=False, print_error=False, script_name=script_name)
          if this_architecture_bounds:
            fmax_lower_bound = read_from_list('fmax_lower_bound', this_architecture_bounds, self.eda_target_filename, optional=True, raise_if_missing=False, print_error=False, script_name=script_name)
            if fmax_lower_bound:
              fmax_lower_bound_ok = True
            
            fmax_upper_bound = read_from_list('fmax_upper_bound', this_architecture_bounds, self.eda_target_filename, optional=True, raise_if_missing=False, print_error=False, script_name=script_name)
            if fmax_upper_bound:
              fmax_upper_bound_ok = True

            # check if bounds are valid
            if (fmax_upper_bound <= fmax_lower_bound) : 
              printc.error("The upper bound (" + fmax_upper_bound + ") must be strictly superior to the lower bound (" + fmax_lower_bound + ")", script_name)
              self.error_archs.append(arch_display_name)
              return None

        if fmax_lower_bound_ok == False:
          fmax_lower_bound = read_from_list('fmax_lower_bound', target_options, self.eda_target_filename, optional=True, raise_if_missing=False, script_name=script_name)
          if fmax_lower_bound == False:
            printc.note("Cannot find optional key \"fmax_lower_bound\" for target \"" + target + "\" in \"" + settings_filename + "\". Using default frequency lower bound instead: " + "{} MHz.".format(self.default_fmax_lower_bound), script_name)
            fmax_lower_bound = self.default_fmax_lower_bound
          #else:
            #printc.note("Cannot find optional key \"fmax_lower_bound\" for architecture \"" + arch + "\" with target \"" + target + "\" in \"" + settings_filename + "\". Using target frequency lower bound instead: " + "{} MHz.".format(self.default_fmax_lower_bound), script_name)

        if fmax_upper_bound_ok == False:
          fmax_upper_bound = read_from_list('fmax_upper_bound', target_options, self.eda_target_filename, optional=True, raise_if_missing=False, script_name=script_name)
          if fmax_upper_bound == False:
            printc.note("Cannot find optional key \"fmax_upper_bound\" for target \"" + target + "\" in \"" + settings_filename + "\". Using default frequency upper bound instead: " + "{} MHz.".format(self.default_fmax_upper_bound), script_name)
            fmax_upper_bound = self.default_fmax_upper_bound
          #else:
            #printc.note("Cannot find optional key \"fmax_upper_bound\" for architecture \"" + arch + "\" with target \"" + target + "\" in \"" + settings_filename + "\". Using target frequency upper bound instead: " + "{} MHz.".format(self.default_fmax_upper_bound), script_name)
            
      # check if bounds are valid
      if (fmax_upper_bound <= fmax_lower_bound) : 
        printc.error("The upper bound (" + fmax_upper_bound + ") must be strictly superior to the lower bound (" + fmax_lower_bound + ")", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None

      fmax_lower_bound = str(fmax_lower_bound)
      fmax_upper_bound = str(fmax_upper_bound)

      formatted_bound = " {}({} - {} MHz){}".format(printc.colors.GREY, fmax_lower_bound, fmax_upper_bound, printc.colors.ENDC)

      # check if the architecture is in cache and has a status file
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
        self.new_archs.append(arch_display_name + formatted_bound)

    # target specific file copy
    if target_options:
      try:
        _file_copy_enable = read_from_list('file_copy_enable', target_options, self.eda_target_filename, optional=True, print_error=False, type=bool, script_name=script_name)
        try:
          _file_copy_source = read_from_list('file_copy_source', target_options, self.eda_target_filename, optional=True, script_name=script_name)
          _file_copy_dest = read_from_list('file_copy_dest', target_options, self.eda_target_filename, optional=True, script_name=script_name)
          file_copy_enable = _file_copy_enable
          file_copy_source = _file_copy_source
          file_copy_dest = _file_copy_dest
        except (KeyNotInListError, BadValueInListError):
          pass
      except KeyNotInListError:
        pass
      except BadValueInListError:
        printc.note("Value \"" + str(_file_copy_enable) + "\" for key \"" + 'file_copy_enable' + "\"" + ", inside list \"" + "target_settings/" + target + "\"," + " in \"" + self.eda_target_filename + "\" is of type \"" + _file_copy_enable.__class__.__name__ + "\" while it should be of type \"bool\". Using default values instead.", script_name)

    # check file copy
    file_copy_source = os.path.realpath(re.sub(odatix_path_pattern, self.odatix_path, file_copy_source))
    if file_copy_enable:
      if not isfile(file_copy_source):
        printc.error("The source file to copy \"" + file_copy_source + "\" does not exist", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None

    # passed all check: added to the list
    self.valid_archs.append(arch_display_name)

    lib_name = "LIB_" + target + "_" + arch.replace("/", "_")

    tmp_script_path = os.path.join(tmp_dir, self.work_script_path)
    tmp_report_path = os.path.join(tmp_dir, self.work_report_path)

    arch_instance = Architecture(
      arch_name = arch,
      arch_display_name = arch_display_name,
      lib_name = lib_name,
      target = target,
      tmp_script_path=tmp_script_path,
      tmp_report_path=tmp_report_path,
      tmp_dir=tmp_dir,
      design_path=design_path,
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
      param_target_filename=param_target_filename,
      generate_rtl=generate_rtl,
      use_parameters=use_parameters,
      start_delimiter=start_delimiter,
      stop_delimiter=stop_delimiter,
      generate_command=generate_command,
      constraint_filename=constraint_filename
    )

    return arch_instance

  def get_use_parameters(self, arch, arch_display_name, settings_data, settings_filename, no_configuration=False, add_to_error_list=True, arch_param_dir=""):
    # get use_parameters
    try:
      use_parameters = read_from_list('use_parameters', settings_data, settings_filename, type=bool, script_name=script_name)
    except (KeyNotInListError, BadValueInListError):
      if add_to_error_list:
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
      return None, None, None

    param_filename = arch + ".txt"
    if no_configuration:
      use_parameters = False
    else:
      if use_parameters:
        # check if parameter file exists
        if not isfile(self.arch_path + '/' + param_filename):
          printc.error("There is no parameter file \"" + self.arch_path + '/' + param_filename + "\", while use_parameters=true", script_name)
          if add_to_error_list:
            self.error_archs.append(arch_display_name)
          return True, None, None
    
    if use_parameters:
      # get start delimiter
      try:
        start_delimiter = read_from_list('start_delimiter', settings_data, settings_filename, print_error=False, script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        printc.error("Cannot find key \"start_delimiter\" in \"" + settings_filename + "\", while \"use_parameters\" is true", script_name)
        if add_to_error_list:
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
        return None, None, None

      # get stop delimiter
      try:
        stop_delimiter = read_from_list('stop_delimiter', settings_data, settings_filename, print_error=False, script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        printc.error("Cannot find key \"stop_delimiter\" in \"" + settings_filename + "\", while \"use_parameters\" is true", script_name)
        if add_to_error_list:
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
        return None, None, None
    else:
      start_delimiter = ""
      stop_delimiter = ""

    return use_parameters, start_delimiter, stop_delimiter

  def print_summary(self):
    ArchitectureHandler.print_arch_list(self.new_archs, "New architectures", printc.colors.ENDC)
    ArchitectureHandler.print_arch_list(self.incomplete_archs, "Incomplete results (will be overwritten)", printc.colors.YELLOW)
    ArchitectureHandler.print_arch_list(self.cached_archs, "Existing results (skipped)", printc.colors.CYAN)
    ArchitectureHandler.print_arch_list(self.overwrite_archs, "Existing results (will be overwritten)", printc.colors.YELLOW)
    ArchitectureHandler.print_arch_list(self.error_archs, "Invalid settings, (skipped, see errors above)", printc.colors.RED)

  def get_chuncks(self, nb_jobs):
    if len(self.architecture_instances) > nb_jobs:
      nb_chunks = math.ceil(len(self.architecture_instances) / nb_jobs)
      print()
      printc.note("Current maximum number of jobs is " + str(nb_jobs) + ". Architectures will be split in " + str(nb_chunks) + " chunks")
      self.architecture_instances_chunks = list(chunk_list(self.architecture_instances, nb_jobs))
    else:
      nb_chunks = 1
      self.architecture_instances_chunks = []
    return self.architecture_instances_chunks, nb_chunks


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

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

from os.path import isfile
from os.path import isdir

import utils
from utils import *

script_name = os.path.basename(__file__)

tcl_bool_true = ['true', 'yes', 'on', '1']
tcl_bool_false = ['false', 'no', 'off', '0']

class Architecture:
  def __init__(self, arch_name, arch_display_name, lib_name, target, tmp_script_path, tmp_dir, design_path, rtl_path, arch_path,
               clock_signal, reset_signal, top_level_module, top_level_filename, use_parameters, start_delimiter, stop_delimiter,
               file_copy_enable, file_copy_source, file_copy_dest, script_copy_enable, script_copy_source, 
               fmax_lower_bound, fmax_upper_bound, param_target_filename, generate_rtl, generate_command):
    self.arch_name = arch_name
    self.arch_display_name = arch_display_name
    self.lib_name = lib_name
    self.target = target
    self.tmp_script_path = tmp_script_path
    self.tmp_dir = tmp_dir
    self.design_path = design_path
    self.rtl_path = rtl_path
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

class ArchitectureHandler:

  def __init__(self, work_path, arch_path, script_path, work_script_path, log_path, eda_target_filename, fmax_status_filename, frequency_search_filename, param_settings_filename, valid_status, valid_frequency_search, default_fmax_lower_bound, default_fmax_upper_bound, target_settings, overwrite):
    self.work_path = work_path
    self.arch_path = arch_path
    self.script_path = script_path
    self.work_script_path = work_script_path
    self.log_path = log_path

    self.eda_target_filename = eda_target_filename
    self.fmax_status_filename = fmax_status_filename
    self.frequency_search_filename = frequency_search_filename
    self.param_settings_filename = param_settings_filename
    
    self.valid_status = valid_status
    self.valid_frequency_search = valid_frequency_search

    self.default_fmax_lower_bound = default_fmax_lower_bound
    self.default_fmax_upper_bound = default_fmax_upper_bound

    self.target_settings = target_settings
    self.overwrite = overwrite
    self.reset_lists()

  def reset_lists(self):
    self.banned_arch_param = []
    self.valid_archs = []
    self.cached_archs = []
    self.overwrite_archs = []
    self.error_archs = []
    self.incomplete_archs = []
    self.new_archs = []

  def get_architectures(self, architectures, targets):

    self.reset_lists()
    self.architecture_instances = []

    only_one_target = len(targets) == 1

    for target in targets:
      try:
        if target_settings == {}:
          raise
        this_target_settings = read_from_list(target, target_settings, self.eda_target_filename, optional=True, parent="target_settings", script_name=script_name)
        script_copy_enable = read_from_list('script_copy_enable', this_target_settings, self.eda_target_filename, optional=True, parent="target_settings/" + target, script_name=script_name)
        script_copy_source = read_from_list('script_copy_source', this_target_settings, self.eda_target_filename, optional=True, parent="target_settings/" + target, script_name=script_name)
        if not script_copy_enable in tcl_bool_true:
          raise
        if not os.path.exists(script_copy_source):
          printc.note("the script source file \"" + script_copy_source + "\"specified in \"" + self.eda_target_filename + "\" does not exist. Script copy disabled.", script_name)
          raise
      except:
        script_copy_enable = "false"
        script_copy_source = "/dev/null"
        
      for arch in architectures:
        architecture_instance = self.get_architecture(
          arch = arch,
          target = target, 
          only_one_target = only_one_target, 
          script_copy_enable = script_copy_enable, 
          script_copy_source = script_copy_source,
          synthesis = True
        )
        if architecture_instance is not None:
          self.architecture_instances.append(architecture_instance)

    return self.architecture_instances
  
  def get_architecture(self, arch, target="", only_one_target=True, script_copy_enable=False, script_copy_source="/dev/null", synthesis=False):
    if only_one_target:
      arch_display_name = arch
    else:
      arch_display_name = arch + " (" + target + ")"

    tmp_dir = self.work_path + '/' + target + '/' + arch
    fmax_status_file = tmp_dir + '/' + self.log_path + '/' + self.fmax_status_filename
    frequency_search_file = tmp_dir + '/' + self.log_path + '/' + self.frequency_search_filename

    # get param dir (arch name before '/')
    arch_param_dir = re.sub('/.*', '', arch)

    # get param dir (arch name after '/')
    arch_suffix = re.sub('.*/', '', arch)

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
      settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
      try:
        rtl_path           = read_from_list('rtl_path', settings_data, settings_filename, script_name=script_name)
        top_level_filename = read_from_list('top_level_file', settings_data, settings_filename, script_name=script_name)
        top_level_module   = read_from_list('top_level_module', settings_data, settings_filename, script_name=script_name)
        clock_signal       = read_from_list('clock_signal', settings_data, settings_filename, script_name=script_name)
        reset_signal       = read_from_list('reset_signal', settings_data, settings_filename, script_name=script_name)
        file_copy_enable   = read_from_list('file_copy_enable', settings_data, settings_filename, script_name=script_name)
        file_copy_source   = read_from_list('file_copy_source', settings_data, settings_filename, script_name=script_name)
        file_copy_dest     = read_from_list('file_copy_dest', settings_data, settings_filename, script_name=script_name)
      except:
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None # if an identifier is missing

      use_parameters, start_delimiter, stop_delimiter = self.get_use_parameters(arch, settings_data, settings_filename)
      if use_parameters is None or start_delimiter is None or stop_delimiter is None:
        return None

      generate_command = ""
      try:
        generate_rtl = read_from_list('generate_rtl', settings_data, settings_filename, optional=True, print_error=False, script_name=script_name)
        # check if generate_rtl is a boolean
        generate_rtl = generate_rtl.lower()
        if generate_rtl in tcl_bool_true:
          generate_rtl = True
        elif generate_rtl in tcl_bool_false:
          generate_rtl = False
        else:
          printc.error("Value for identifier \"generate_rtl\" is not one of the boolean value supported by tcl (\"true\", \"false\", \"yes\", \"no\", \"on\", \"off\", \"1\", \"0\")", script_name)
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
          generate_rtl = False
          return None
      except:
        generate_rtl = False

      if generate_rtl:
        try:
          generate_command = read_from_list('generate_command', settings_data, settings_filename, print_error=False, script_name=script_name)
          generate_rtl = True
        except:
          printc.error("Cannot find key \"generate_command\" in \"" + settings_filename + "\" while generate_rtl=true", script_name)
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
          generate_rtl = False
          return None

      try:
        design_path = read_from_list('design_path', settings_data, settings_filename, optional=True, print_error=False, script_name=script_name)
      except:
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
      except:
        param_target_filename = 'rtl/' + top_level_filename

    # check if file_copy_enable is a boolean
    file_copy_enable = file_copy_enable.lower()
    if file_copy_enable in tcl_bool_true:
      file_copy_enable = True
    elif file_copy_enable in tcl_bool_false:
      file_copy_enable = False
    else:
      printc.error("Value for identifier \"file_copy_enable\" is not one of the boolean value supported by tcl (\"true\", \"false\", \"yes\", \"no\", \"on\", \"off\", \"1\", \"0\")", script_name)
      self.banned_arch_param.append(arch_param_dir)
      self.error_archs.append(arch_display_name)
      return None

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
      if not top_level_module in f.read():
        printc.error("There is no occurence of top level module name \"" + top_level_module + "\" in top level file \"" + top_level + "\"", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        f.close()
        return None
      f.close()
      
      # check if the top clock name exists in the top level file, at least
      f = open(top_level, "r")
      if not clock_signal in f.read():
        printc.error("There is no occurence of clock signal name \"" + clock_signal + "\" in top level file \"" + top_level + "\"", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        f.close()
        return None
      f.close()
      
      # check if the top reset name exists in the top level file, at least
      f = open(top_level, "r")
      if not clock_signal in f.read():
        printc.error("There is no occurence of reset signal name \"" + reset_signal + "\" in top level file \"" + top_level + "\"", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        f.close()
        return None
      f.close()

    # check if param file exists
    if not isfile(self.arch_path + '/' + arch + '.txt'):
      printc.error("The parameter file \"" + arch + ".txt\" does not exist in directory \"" + self.arch_path + "/" + arch_param_dir + "\"", script_name)
      self.banned_arch_param.append(arch_param_dir)
      self.error_archs.append(arch_display_name)
      return None

    # check file copy
    if file_copy_enable:
      if not isfile(file_copy_source):
        printc.error("The source file to copy \"" + file_copy_source + "\" does not exist", script_name)
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
        return None

    # optional settings
    formatted_bound = ""
    fmax_lower_bound_ok = False
    fmax_upper_bound_ok = False
    fmax_lower_bound = 0
    fmax_upper_bound = 0
    if synthesis:
      target_options = read_from_list(target, settings_data, settings_filename, optional=True, raise_if_missing=False, print_error=False, script_name=script_name)
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

    # passed all check: added to the list
    self.new_archs.append(arch_display_name + formatted_bound)
    self.valid_archs.append(arch_display_name)

    lib_name = "LIB_" + target + "_" + arch.replace("/", "_")

    tmp_script_path = tmp_dir + '/' + self.work_script_path

    arch_instance = Architecture(
      arch_name = arch,
      arch_display_name = arch_display_name,
      lib_name = lib_name,
      target = target,
      tmp_script_path=tmp_script_path,
      tmp_dir=tmp_dir,
      design_path=design_path,
      rtl_path=rtl_path,
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
      generate_command=generate_command
    )

    return arch_instance

  def get_use_parameters(self, arch, settings_data, settings_filename, add_to_error_list=True):
    # get use_parameters
    try:
      use_parameters = read_from_list('use_parameters', settings_data, settings_filename, script_name=script_name)
    except:
      if add_to_error_list:
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
      return None, None, None

    param_filename = arch + ".txt"
    use_parameters = use_parameters.lower()
    if use_parameters in tcl_bool_true:
      use_parameters = True
      # check if parameter file exists
      if not isfile(self.arch_path + '/' + param_filename):
        printc.error("There is no parameter file \"" + self.arch_path + '/' + param_filename + "\", while use_parameters=true", script_name)
        if add_to_error_list:
          self.error_archs.append(arch_display_name)
        return True, None, None
    elif use_parameters in tcl_bool_false:
        use_parameters = False
    else:
      printc.error("Value for identifier \"use_parameters\" is not one of the boolean value supported by tcl (\"true\", \"false\", \"yes\", \"no\", \"on\", \"off\", \"1\", \"0\")", script_name)
      if add_to_error_list:
        self.banned_arch_param.append(arch_param_dir)
        self.error_archs.append(arch_display_name)
      return None, None, None
    
    if use_parameters:
      # get start delimiter
      try:
        start_delimiter = read_from_list('start_delimiter', settings_data, settings_filename, print_error=False, script_name=script_name)
      except:
        printc.error("Cannot find key \"start_delimiter\" in \"" + settings_filename + "\", while \"use_parameters\" is true", script_name)
        if add_to_error_list:
          self.banned_arch_param.append(arch_param_dir)
          self.error_archs.append(arch_display_name)
        return None, None, None

      # get stop delimiter
      try:
        stop_delimiter = read_from_list('stop_delimiter', settings_data, settings_filename, print_error=False, script_name=script_name)
      except:
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

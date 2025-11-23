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
import yaml

from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings

script_name = os.path.basename(__file__)

class ParamDomain:
  """
  Represents a parameter domain, which defines configuration settings
  for a given hardware architecture.

  Attributes:
      domain (str): Name of the parameter domain (e.g., architecture name).
      domain_value (str): Specific configuration variant.
      use_parameters (bool): Whether parameters are used in this domain.
      start_delimiter (str): Start delimiter for parameter extraction.
      stop_delimiter (str): Stop delimiter for parameter extraction.
      param_target_file (str): File where parameters should be applied.
      param_file (str): Path to the parameter definition file.
  """

  def __init__(
    self,
    domain,
    domain_value,
    use_parameters,
    start_delimiter,
    stop_delimiter,
    param_target_file,
    param_file,
  ):
    """Initializes a ParamDomain object with its attributes."""
    self.domain = domain
    self.domain_value = domain_value
    self.use_parameters = use_parameters
    self.start_delimiter = start_delimiter
    self.stop_delimiter = stop_delimiter
    self.param_target_file = param_target_file
    self.param_file = param_file
  
  def __repr__(self):
    """Returns a string representation of the object for debugging purposes."""
    out = f"domain: {self.domain}\n"
    out += f"domain_value: {self.domain_value}\n"
    out += f"use_parameters: {self.use_parameters}\n"
    out += f"start_delimiter: {self.start_delimiter}\n"
    out += f"stop_delimiter: {self.stop_delimiter}\n"
    out += f"param_target_file: {self.param_target_file}\n"
    out += f"param_file: {self.param_file}\n"
    return out

  @staticmethod
  def check_parameter_file(parameter_file, arch_param_dir, generate_enabled=False):
    """
    Checks if the parameter file exists.

    Args:
        parameter_file (str): Path to the parameter file.
        arch_param_dir (str): Directory of the architecture parameters.
        generate_enabled (bool): Whether configuration generation generation is enabled.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    if not os.path.isfile(parameter_file):
      printc.error("The parameter file \"" + parameter_file + "\" does not exist in directory \"" + arch_param_dir + "\"", script_name)
      if generate_enabled:
        printc.note("Since \"generate_configutations\" is enabled:", script_name)
        printc.note("Did you run \"odatix generate\"?", script_name)
        printc.note("Are your generation settings correct?", script_name)
      return False
    return True

  @staticmethod
  def check_settings_file(settings_file, arch_param_dir):
    """
    Checks if the settings file exists.

    Args:
        settings_file (str): Path to the settings file.
        arch_param_dir (str): Directory of the architecture parameters.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    if not os.path.isfile(settings_file):
      printc.error("The settings file \"" + settings_file + "\" does not exist in directory \"" + arch_param_dir + "\"", script_name)
      return False
    return True

  @staticmethod
  def get_param_domains(requested_param_domains, architecture, arch_path=OdatixSettings.DEFAULT_ARCH_PATH, param_settings_filename=hard_settings.param_settings_filename, top_level_file=""):
    """
    Retrieves multiple parameter domains.

    Args:
        requested_param_domains (list): List of requested parameter domains.
        architecture (str): Name of the architecture.
        arch_path (str): Path to the architecture directory.
        param_settings_filename (str): Name of the settings file.
        top_level_file (str): Path to the top-level configuration file.

    Returns:
        list[ParamDomain] or None: List of ParamDomain objects if successful, otherwise None.
    """
    if not isinstance(requested_param_domains, list):
      printc.error("requested_param_domains must be a list", script_name)
      return None

    param_domains = []
    for request in requested_param_domains:
      param_domain = ParamDomain.get_param_domain(
        request=request, 
        architecture=architecture,
        arch_path=arch_path, 
        param_settings_filename=param_settings_filename,
        top_level_file=top_level_file,
        param_domain_def=True,
      )
      if param_domain is None:
        return None
      param_domains.append(param_domain)
    return param_domains

  @staticmethod
  def get_param_domain(request, architecture, arch_path=OdatixSettings.DEFAULT_ARCH_PATH, param_settings_filename=hard_settings.param_settings_filename, top_level_file="", param_domain_def=False):
    """
    Retrieves a single parameter domain.

    Args:
        request (str): Requested parameter domain.
        architecture (str): Name of the architecture.
        arch_path (str): Path to the architecture directory.
        param_settings_filename (str): Name of the settings file.
        top_level_file (str): Path to the top-level configuration file.
        param_domain_def (bool): Whether this is the definition of a parameter domain.

    Returns:
        ParamDomain or None: A ParamDomain object if successful, otherwise None.
    """

    arch_path = os.path.join(arch_path, architecture)

    # get param dir (request name before '/')
    arch_param_dir = re.sub('/.*', '', request)

    # get configuration (request name after '/')
    arch_config = re.sub('.*/', '', request)

    param_domain_path = os.path.join(arch_path, arch_param_dir)

    parameter_file = os.path.join(param_domain_path, arch_config + '.txt')

    settings_file = os.path.join(param_domain_path, param_settings_filename)
    success = ParamDomain.check_settings_file(settings_file, param_domain_path)
    if not success:
      return None

    # Load settings file
    with open(settings_file, 'r') as f: 
      try:
        settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
      except Exception as e:
        printc.error("Settings file \"" + settings_file + "\" is not a valid YAML file", script_name)
        printc.cyan("error details: ", end="", script_name=script_name)
        print(str(e))
        return None

    generate_enabled, _ = get_from_dict("generate_configutations", settings_data, settings_file, default_value=False, silent=True, script_name=script_name)
    success = ParamDomain.check_parameter_file(parameter_file, param_domain_path, generate_enabled)
    if not success:
      return None

    # Retrieve parameter delimiters and usage details
    use_parameters, start_delimiter, stop_delimiter, param_target_filename = ParamDomain.get_param_delimiters(
        settings_data, settings_file, top_level_file, param_domain_def
    )

    return ParamDomain(
      domain=arch_param_dir,
      domain_value=arch_config,
      use_parameters=use_parameters,
      start_delimiter=start_delimiter,
      stop_delimiter=stop_delimiter,
      param_target_file=param_target_filename,
      param_file=parameter_file,
    )

  @staticmethod
  def get_param_delimiters(settings_data, settings_file, top_level_file=None, param_domain_def=False):
    """
    Extracts parameter delimiters and target file information.

    Args:
        settings_data (dict): Parsed YAML settings data.
        settings_file (str): Path to the settings file.
        top_level_file (str): Path to the top-level configuration file.
        param_domain_def (bool): Whether this is a parameter domain definition.

    Returns:
        tuple: (use_parameters, start_delimiter, stop_delimiter, param_target_filename)
    """
    default_value = param_domain_def
    silent = param_domain_def

    use_parameters, _ = get_from_dict('use_parameters', settings_data, settings_file, default_value=default_value, silent=silent, type=bool, script_name=script_name)
    
    if use_parameters:
      start_delimiter, defined = get_from_dict('start_delimiter', settings_data, settings_file, silent=True, script_name=script_name)
      if not defined:
        printc.error("Cannot find key \"start_delimiter\" in \"" + settings_file + "\", while \"use_parameters\" is true", script_name)
        return None, None, None, None
      stop_delimiter, defined = get_from_dict('stop_delimiter', settings_data, settings_file, silent=True, script_name=script_name)
      if not defined:
        printc.error("Cannot find key \"stop_delimiter\" in \"" + settings_file + "\", while \"use_parameters\" is true", script_name)
        return None, None, None, None

      # Print an error if the default value is not defined
      silent = False if top_level_file is None else True
      param_target_filename, _ = get_from_dict('param_target_file', settings_data, settings_file, default_value=top_level_file, silent=silent, script_name=script_name)
      if param_target_filename == "":
        param_target_filename = top_level_file
    else:
      start_delimiter = ""
      stop_delimiter = ""
      param_target_filename = ""

    return use_parameters, start_delimiter, stop_delimiter, param_target_filename

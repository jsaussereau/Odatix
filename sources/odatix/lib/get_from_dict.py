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

"""
This module provides utility functions and custom error handling.

It includes the following features:
- Enums to define key behaviors for configuration management.
- Custom exceptions to handle errors related to missing keys or invalid values.
- Functions to safely retrieve and validate data from dictionaries.

Classes:
    Key (Enum): Defines behavior for key retrieval.
    KeyNotInDictError (Exception): Raised when a required key is not found.
    BadValueInDictError (Exception): Raised when a key's value is of an unexpected type.

Functions:
    get_from_dict: Retrieve a value from a dictionary with type validation and error handling.

Usage:
    Use `get_from_dict` to safely extract values from dictionaries and manage optional/mandatory keys.
"""

from enum import Enum

import odatix.lib.printc as printc

class Key(Enum):
  """
  Enum to define the behavior for key retrieval.

  Attributes:
      OPTIONAL (int): Key is optional; no error is raised if missing.
      OPTIONAL_RAISE (int): Key is optional, but an error is raised if the type is invalid.
      MANTADORY (int): Key is mandatory; logs an error if missing.
      MANTADORY_RAISE (int): Key is mandatory; raises an exception if missing.
  """
  OPTIONAL = 0
  OPTIONAL_RAISE = 1
  MANTADORY = 2
  MANTADORY_RAISE = 3

class KeyNotInDictError(Exception):
  """Exception raised when a required key is missing from the list."""
  pass

class BadValueInDictError(Exception):
  """Exception raised when a key's value is of an invalid type."""
  pass

def get_from_dict(
  key, 
  input_dict, 
  filename="",
  parent=None,
  type=None, 
  behavior=Key.OPTIONAL, 
  silent=False, 
  default_value=None,
  script_name=""
):
  """
  Retrieve and validate a value from a dictionary, with optional error handling.

  Args:
      key (str): The key to retrieve from the dictionary.
      input_dict (dict): The dictionary containing the data.
      filename (str): Name of the file (yaml file for example) containing the dictionary (for error messages).
      parent (str | None): Parent key for nested dictionaries (used in error messages).
      type (type | None): Expected type of the value. If None, no type validation is performed.
      behavior (Key): Behavior for key retrieval (optional, mandatory, raise on error).
      silent (bool): Whether to suppress error and note messages (default: False).
      default_value (Any): Default value to return if the key is not found or invalid.
      script_name (str): Name of the script for logging purposes.

  Returns:
      tuple:
          - value (Any): Retrieved and validated value, or the default value if validation fails.
          - success (bool): True if the value was successfully retrieved and validated, False otherwise.

  Raises:
      KeyNotInDictError: If the key is mandatory and missing.
      BadValueInDictError: If the key exists but the value is of the wrong type and behavior requires raising.

  Notes:
      - The function distinguishes between mandatory and optional keys using the `behavior` argument.
      - Logs warnings or errors depending on the context and settings.
  """
  raise_on_error = behavior == Key.OPTIONAL_RAISE or behavior == Key.MANTADORY_RAISE
  optional = behavior == Key.OPTIONAL or behavior == Key.OPTIONAL_RAISE
  parent_string = "" if parent == None else ", inside parent key \"" + parent + "\","  
  if not isinstance(input_dict, dict):
    printc.error("Cannot find key \"" + key + "\"" + parent_string + " because the parent key is not a dictionnary but a \"" + input_dict.__class__.__name__ + "\", in \"" + filename + "\".", script_name)
    return default_value, False
  if key in input_dict:
    value = input_dict[key]
    if type is None:
      return value, True
    else:
      if isinstance(value, type):
        return value, True
      else:
        if silent is not None:
          if optional:
            printc.note("Value \"" + str(value) + "\" for key \"" + key + "\"" + parent_string + " in \"" + filename + "\" is of type \"" + value.__class__.__name__ + "\" while it should be of type \"" + type.__name__ + "\". Using default value (" + str(default_value) + ") instead", script_name)
          else:
            printc.error("Value \"" + str(value) + "\" for key \"" + key + "\"" + parent_string + " in \"" + filename + "\" is of type \"" + value.__class__.__name__ + "\" while it should be of type \"" + type.__name__ + "\".", script_name)
        if raise_on_error:
          raise BadValueInDictError
        return default_value, False
  else:
    if not silent:
      if optional:
        printc.note("Cannot find optional key \"" + key + "\"" + parent_string + " in \"" + filename + "\". Using default value instead: " + str(default_value), script_name)
      else:
        printc.error("Cannot find key \"" + key + "\"" + parent_string + " in \"" + filename + "\".", script_name)
    if raise_on_error:
      raise KeyNotInDictError
    return default_value, False

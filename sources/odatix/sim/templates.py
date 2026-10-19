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
Simulation templates: a simulation Odatix provides for a simulator.

A template is a simulation directory like any other, shipped with Odatix in
"odatix_sim_templates/<simulator>/": a "_settings.yml" (the languages it
compiles, its tasks), a "_metrics.yml" (the figures every template reports) and
the script compiling, elaborating and running the design ("run.py"). It knows
nothing about the design: what it runs is read from "odatix_sim.yml" (see
odatix.sim.design_info).

A simulation is found by name, in this order:

  1. the workspace's simulation directory ("sim_path"), so a workspace can
     override a template by holding a simulation of the same name;
  2. the templates Odatix provides.

So a run can name a template directly, with no directory of its own:

    simulations:
      - questa: [Example_Cordic_sv/*, Example_Cordic_vhdl/*]

A simulation can also start from a template (the same way a tool "extends"
another one) and say only what changes, its testbench most of the time:

    # simulations/TB_Cordic/_settings.yml
    template: xsim
    testbench:
      top: tb_cordic
      files: [tb/tb_cordic.sv]

Its settings are then the template's, merged with its own (mappings key by
key, anything else replaced), and its work directory gets the template's files
first, then its own, which take precedence. A template can start from another
one; a simulation naming a template of its own name starts from the one Odatix
provides.
"""

import copy
import os
import shlex
import shutil
import subprocess
import tempfile

import yaml

import odatix.lib.hard_settings as hard_settings
import odatix.lib.wsl as wsl
import odatix.lib.yaml_loader as yaml_loader

TEMPLATE_KEY = "template"
# The languages a template compiles. A simulation that does not say compiles
# whatever it is given.
LANGUAGES_KEY = "languages"
# The command telling whether the simulator is installed.
TEST_COMMAND_KEY = "test_command"
DESCRIPTION_KEY = "description"
METRICS_FILENAME = "_metrics.yml"


class SimulationNotFound(LookupError):
  pass


class TemplateError(ValueError):
  pass


def builtin_path():
  """The directory holding the templates Odatix provides."""
  from odatix.lib.settings import OdatixSettings

  return OdatixSettings.odatix_sim_templates_path


def list_templates():
  """{name: directory} of the templates Odatix provides, sorted by name."""
  templates = {}
  path = builtin_path()
  try:
    names = sorted(os.listdir(path))
  except OSError:
    return templates
  for name in names:
    directory = os.path.join(path, name)
    if not name.startswith(("_", ".")) and os.path.isfile(os.path.join(directory, hard_settings.sim_settings_filename)):
      templates[name] = directory
  return templates


def read_settings(directory):
  """
  The "_settings.yml" of a simulation directory, {} when it has none.

  Raises:
    TemplateError: the file is not valid YAML, or not a mapping.
  """
  path = os.path.join(directory, hard_settings.sim_settings_filename)
  if not os.path.isfile(path):
    return {}
  try:
    with open(path, "r", encoding="utf-8") as f:
      data = yaml.load(f, Loader=yaml_loader.SafeLoader)
  except yaml.YAMLError as e:
    raise TemplateError('Settings file "' + path + '" is not a valid YAML file: ' + str(e))
  if data is None:
    return {}
  if not isinstance(data, dict):
    raise TemplateError('Settings file "' + path + '" must hold a mapping')
  return data


def find_definition(name, sim_path, skip=()):
  """
  The directory defining the simulation `name`: the workspace's, else the
  template Odatix provides. None when there is neither. Directories in `skip`
  (real paths) are passed over.
  """
  candidates = []
  if sim_path:
    candidates.append(os.path.join(sim_path, name))
  candidates.append(os.path.join(builtin_path(), name))
  for candidate in candidates:
    if os.path.isdir(candidate) and os.path.realpath(candidate) not in skip:
      return candidate
  return None


def _merge(base, override):
  merged = dict(base)
  for key, value in override.items():
    if isinstance(value, dict) and isinstance(merged.get(key), dict):
      merged[key] = _merge(merged[key], value)
    else:
      merged[key] = copy.deepcopy(value)
  return merged


def resolve(name, sim_path):
  """
  Every directory defining a simulation, the template it starts from first,
  and its settings, merged.

  Returns:
    (directories, settings)

  Raises:
    SimulationNotFound: there is no simulation and no template of that name.
    TemplateError: a settings file cannot be read, or names a template that
      does not exist.
  """
  current = find_definition(name, sim_path)
  if current is None:
    raise SimulationNotFound(
      'There is no simulation "' + str(name) + '" in "' + str(sim_path) + '", and no template of that name'
      + _available_templates()
    )

  directories = []
  chain = []
  seen = set()
  while current is not None:
    seen.add(os.path.realpath(current))
    settings = read_settings(current)
    directories.insert(0, current)
    chain.insert(0, settings)
    base = settings.get(TEMPLATE_KEY)
    if base in (None, ""):
      break
    if not isinstance(base, str):
      raise TemplateError('"' + TEMPLATE_KEY + '" in "' + _settings_file(current) + '" must be the name of a template')
    current = find_definition(base, sim_path, skip=seen)
    if current is None:
      raise TemplateError(
        'Unknown template "' + base + '" in "' + _settings_file(directories[0]) + '"' + _available_templates()
      )

  merged = {}
  for settings in chain:
    merged = _merge(merged, settings)
  merged.pop(TEMPLATE_KEY, None)
  return directories, merged


def _settings_file(directory):
  return os.path.join(directory, hard_settings.sim_settings_filename)


def _available_templates():
  names = list(list_templates())
  return " (templates: " + ", ".join(names) + ")" if names else ""


def accepted_languages(settings):
  """The languages a simulation compiles, or None when it does not say."""
  languages = settings.get(LANGUAGES_KEY)
  if isinstance(languages, str):
    languages = [languages]
  if not isinstance(languages, list):
    return None
  return [str(language).lower() for language in languages]


def description(name):
  """What the template says it is, its name when it says nothing."""
  directory = list_templates().get(name)
  if directory is None:
    return name
  try:
    settings = read_settings(directory)
  except TemplateError:
    return name
  return str(settings.get(DESCRIPTION_KEY) or name)


def is_installed(name, timeout=15):
  """
  Whether the simulator of a template is installed: its "test_command" runs
  and succeeds, the same check as the "tool_test_command" of an eda tool. None
  when the template says no command to check with.
  """
  directory = list_templates().get(name)
  if directory is None:
    return None
  try:
    command = read_settings(directory).get(TEST_COMMAND_KEY)
  except TemplateError:
    return None
  if isinstance(command, str):
    command = command.split()
  if not command:
    return None
  command = [str(part) for part in command]
  in_wsl = runs_in_wsl(name)
  if in_wsl:
    # Checked where it runs: in WSL (see odatix.lib.wsl)
    if wsl.which(command[0]) is None:
      return False
    command = wsl.command(" ".join(shlex.quote(part) for part in command))
  else:
    program = shutil.which(command[0])
    if program is None:
      return False
    # As found in the PATH: Windows does not look for a ".cmd" or ".bat" itself
    command[0] = program
  # Some simulators write a log where they run: not in the workspace.
  scratch = tempfile.mkdtemp(prefix="odatix_check_")
  try:
    returncode = subprocess.call(
      command, cwd=scratch, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout,
      shell=in_wsl,
    )
  except (OSError, subprocess.TimeoutExpired):
    return False
  finally:
    shutil.rmtree(scratch, ignore_errors=True)
  return returncode == 0


def runs_in_wsl(name):
  """Whether the simulator of a template runs in WSL rather than on Windows (see odatix.lib.wsl)."""
  directory = list_templates().get(name)
  if directory is None:
    return False
  try:
    program = test_program(read_settings(directory))
  except TemplateError:
    return False
  return wsl.simulation_runs_in_wsl([name], program)


def test_program(settings):
  """The program a simulation's "test_command" runs, or None when it says no command."""
  command = settings.get(TEST_COMMAND_KEY)
  if isinstance(command, str):
    command = command.split()
  if not command:
    return None
  return str(command[0])


def missing_executable(settings):
  """
  The program a simulation's "test_command" runs, when it is not in the PATH:
  a quick check, done when a run is checked (see is_installed for the full
  one). None when it is there, or when the simulation says no command.
  """
  program = test_program(settings)
  if program is None:
    return None
  return None if shutil.which(program) else program


def compatible(accepted, languages):
  """
  Whether a design written in `languages` can run with a simulation compiling
  `accepted` (None: anything). A design whose languages are not known yet (a
  generated RTL) is.
  """
  if accepted is None or not languages:
    return True
  return all(language in accepted for language in languages)


def metrics_files(directories):
  """The "_metrics.yml" of every directory defining a simulation, in order."""
  return [
    os.path.realpath(os.path.join(directory, METRICS_FILENAME))
    for directory in directories
    if os.path.isfile(os.path.join(directory, METRICS_FILENAME))
  ]

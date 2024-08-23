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
import sys
import yaml

import odatix.lib.printc as printc
from odatix.lib.utils import read_from_list, KeyNotInListError, BadValueInListError, ask_yes_no, YAML_BOOL, copytree

current_dir = os.path.dirname(os.path.abspath(__file__))
script_name = os.path.basename(__file__)

######################################
# Settings
######################################

# get eda_tools folder
if getattr(sys, "frozen", False):
  base_path = os.path.dirname(sys.executable)
else:
  base_path = current_dir

class OdatixSettings:
  DEFAULT_SETTINGS_FILE = "odatix.yml"

  DEFAULT_WORK_PATH = "work"
  DEFAULT_SIM_WORK_PATH = "work/simulations"
  DEFAULT_RESULT_PATH = "results"
  DEFAULT_USERCONFIG_PATH = "odatix_userconfig"
  DEFAULT_ARCH_PATH = os.path.join(DEFAULT_USERCONFIG_PATH, "architectures")
  DEFAULT_SIM_PATH = os.path.join(DEFAULT_USERCONFIG_PATH, "simulations")
  DEFAULT_TARGET_PATH = DEFAULT_USERCONFIG_PATH
  DEFAULT_USE_BENCHMARK = False
  DEFAULT_BENCHMARK_FILE = "results/benchmark.yml"
  DEFAULT_CLEAN_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "clean.yml")
  DEFAULT_SIMULATION_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "simulations_settings.yml")
  DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "fmax_synthesis_settings.yml")
  # DEFAULT_RANGE_SYNTHESIS_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "range_synthesis_settings.yml")
  
  odatix_path = os.path.realpath(os.path.join(base_path, os.pardir))
  odatix_eda_tools_path = os.path.realpath(os.path.join(odatix_path, os.pardir, "odatix_eda_tools"))
  odatix_init_path = os.path.realpath(os.path.join(odatix_path, os.pardir, "odatix_init"))
  odatix_examples_path = os.path.realpath(os.path.join(odatix_path, os.pardir, "odatix_examples"))

  def __init__(self, settings_filename=DEFAULT_SETTINGS_FILE):
    self.settings_file_exists = os.path.isfile(settings_filename)
    if self.settings_file_exists:
      success = self.read_settings_file(settings_filename)
    else:
      printc.warning("This directory does not contain an Odatix settings file \"" + settings_filename + "\".", script_name=script_name)
      printc.note("Run Odatix with the '--init' flag to generate it alongside other necessary config files", script_name=script_name)
      self.valid = False

  def read_settings_file(self, settings_filename=DEFAULT_SETTINGS_FILE):
    if not os.path.isfile(settings_filename):
      printc.error("Odatix settings file \"" + settings_filename + "\" does not exists.", script_name=script_name)
      printc.note("Odatix settings file should be in \"" + current_dir + "\"", script_name=script_name)
      self.valid = False
      return False

    with open(settings_filename, "r") as f:
      try:
        settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
      except Exception as e:
        printc.error("Settings file \"" + settings_filename + "\" is not a valid YAML file", script_name)
        printc.cyan("error details: ", end="", script_name=script_name)
        print(str(e))
        self.valid = False
        return False
      try:
        self.work_path = read_from_list("work_path", settings_data, settings_filename, script_name=script_name)
        self.sim_work_path = read_from_list("sim_work_path", settings_data, settings_filename, script_name=script_name)
        self.result_path = read_from_list("result_path", settings_data, settings_filename, script_name=script_name)
        self.arch_path = read_from_list("arch_path", settings_data, settings_filename, script_name=script_name)
        self.sim_path = read_from_list("sim_path", settings_data, settings_filename, script_name=script_name)
        self.target_path = read_from_list("target_path", settings_data, settings_filename, script_name=script_name)
        self.use_benchmark = read_from_list("use_benchmark", settings_data, settings_filename, type=bool, script_name=script_name)
        self.benchmark_file = read_from_list("benchmark_file", settings_data, settings_filename , script_name=script_name)
        self.clean_settings_file = read_from_list("clean_settings_file", settings_data, settings_filename , script_name=script_name)
        self.simulation_settings_file = read_from_list("simulation_settings_file", settings_data, settings_filename , script_name=script_name)
        self.fmax_synthesis_settings_file = read_from_list("fmax_synthesis_settings_file", settings_data, settings_filename , script_name=script_name)
        # self.range_synthesis_settings_file = read_from_list("range_synthesis_settings_file", settings_data, settings_filename , script_name=script_name)
      except (KeyNotInListError, BadValueInListError):
        self.valid = False
        return False
    self.valid = True
    return True
    
  def generate_settings_file(self, settings_filename=DEFAULT_SETTINGS_FILE):
    if os.path.isfile(settings_filename):
      return True
    else:
      printc.say("This directory does not contain an Odatix settings file \"" + settings_filename + "\".", script_name=script_name)
      printc.say("This file is mandatory. Would you like to create one? ", end="", script_name=script_name)
      answer = ask_yes_no()
      if answer is False:
        return False
      else:
        settings_data = {
          "work_path": input("  Enter work path [default: " + OdatixSettings.DEFAULT_WORK_PATH + "]: ") or OdatixSettings.DEFAULT_WORK_PATH,
          "sim_work_path": input("  Enter simulation work path [default: " + OdatixSettings.DEFAULT_SIM_WORK_PATH + "]: ") or OdatixSettings.DEFAULT_SIM_WORK_PATH,
          "result_path": input("  Enter result path [default: " + OdatixSettings.DEFAULT_RESULT_PATH + "]: ") or OdatixSettings.DEFAULT_RESULT_PATH,
          "arch_path": input("  Enter architecture path [default: " + OdatixSettings.DEFAULT_ARCH_PATH + "]: ") or OdatixSettings.DEFAULT_ARCH_PATH,
          "sim_path": input("  Enter simulation path [default: " + OdatixSettings.DEFAULT_SIM_PATH + "]: ") or OdatixSettings.DEFAULT_SIM_PATH,
          "target_path": input("  Enter target settings files path [default: " + OdatixSettings.DEFAULT_TARGET_PATH + "]: ") or OdatixSettings.DEFAULT_TARGET_PATH,
          "use_benchmark": input("  Use benchmark (True/False) [default: " + str(OdatixSettings.DEFAULT_USE_BENCHMARK) + "]: ").lower() in YAML_BOOL or OdatixSettings.DEFAULT_USE_BENCHMARK,
          "benchmark_file": input("  Enter benchmark file path [default: " + OdatixSettings.DEFAULT_BENCHMARK_FILE + "]: ") or OdatixSettings.DEFAULT_BENCHMARK_FILE,
          "clean_settings_file": input("  Enter clean settings file [default: " + OdatixSettings.DEFAULT_CLEAN_SETTINGS_FILE + "]: ") or OdatixSettings.DEFAULT_CLEAN_SETTINGS_FILE,
          "simulation_settings_file": input("  Enter simulation settings file [default: " + OdatixSettings.DEFAULT_SIMULATION_SETTINGS_FILE + "]: ") or OdatixSettings.DEFAULT_SIMULATION_SETTINGS_FILE,
          "fmax_synthesis_settings_file": input("  Enter fmax synthesis settings file [default: " + OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE + "]: ") or OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
          # "range_synthesis_settings_file": input("  Enter range synthesis settings file [default: " + OdatixSettings.DEFAULT_RANGE_SYNTHESIS_SETTINGS_FILE + "]: ") or OdatixSettings.DEFAULT_RANGE_SYNTHESIS_SETTINGS_FILE
        }

        with open(settings_filename, "w") as f:
          yaml.dump(settings_data, f, sort_keys=False)

        printc.say("Odatix settings file \"" + settings_filename + "\" has been generated.", script_name=script_name)
        print()
        return True

  @staticmethod
  def init_examples():
    try:
      src_path = OdatixSettings.odatix_examples_path
      dst_path = os.getcwd()
      copytree(src_path, dst_path, dirs_exist_ok=True)
    except Exception as e:
      printc.error("Could not copy examples: " + str(e), script_name=script_name)
      return False
    return True

  @staticmethod
  def init_path():
    try:
      src_path = OdatixSettings.odatix_init_path
      dst_path = os.getcwd()
      copytree(src_path, dst_path, dirs_exist_ok=True)
    except Exception as e:
      printc.error("Could not initialize directory: " + str(e), script_name=script_name)
      return False
    return True

  @staticmethod
  def init_directory_dialog(include_examples=None, prog=""):
    printc.note("This command will create all the configuration files needed by Odatix in the current dictory.", script_name=script_name)
    printc.warning("This will overwrite any existing configuration files.", script_name=script_name)
    printc.say("Would you like to continue? ", end="", script_name=script_name)
    answer = ask_yes_no()
    if answer == False:
      return False
    success = OdatixSettings.init_path()
    if not success:
      return False
    if include_examples is None:
      printc.say("Would you like to add Odatix examples? ", end="", script_name=script_name)
      include_examples = ask_yes_no()
    if include_examples:
      success = OdatixSettings.init_examples()
      if not success:
        return False
    OdatixSettings.init_success(prog)
    return True

  @staticmethod
  def init_directory_nodialog(include_examples=None, prog=""):
    success = OdatixSettings.init_path()
    if not success:
      return False
    if include_examples:
      success = OdatixSettings.init_examples()
      if not success:
        return False
    OdatixSettings.init_success(prog)
    return True

  @staticmethod
  def init_success(prog=""):
    printc.green("Your directory can now be used by Odatix!", script_name=script_name)
    printc.say("Run ", end="", script_name=script_name)
    printc.bold(prog + " -h", end="")
    print(" to get a list of useful commands")

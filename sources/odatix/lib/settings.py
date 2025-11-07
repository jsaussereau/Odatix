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
This module defines the settings and initialization functions for Odatix.

Classes:
    OdatixSettings: Encapsulates all paths, settings, and initialization logic for Odatix.

Functions:
    None defined at the module level; all logic is encapsulated in the OdatixSettings class.

Usage:
    Use `OdatixSettings` to handle configuration file paths, work directories, and
    initialization procedures for Odatix.

    Example:
        settings = OdatixSettings()
        if settings.valid:
            print("Settings loaded successfully")
"""

import os
import sys
import yaml

import odatix.lib.printc as printc
from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
from odatix.lib.utils import ask_yes_no, YAML_BOOL, copytree

current_dir = os.path.dirname(os.path.abspath(__file__))
script_name = os.path.basename(__file__)

######################################
# Settings
######################################

# Determine the install path of Odatix
if getattr(sys, "frozen", False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = current_dir

class OdatixSettings:
    """
    Handles Odatix configuration, paths, and initialization.

    Attributes:
        DEFAULT_* (str): Default paths and filenames for Odatix configurations.
        odatix_*_path (str): Paths to key Odatix components (e.g., EDA tools definition, embedded examples).
        valid (bool): Indicates whether the settings were successfully loaded.
        settings_file_exists (bool): Whether the settings file exists.

    Methods:
        __init__: Initializes the settings object and loads configurations.
        read_settings_file: Reads and validates the Odatix settings file.
        init_examples: Copies example configurations to the current directory.
        init_path: Initializes the required directory structure for Odatix.
        init_directory_dialog: Creates the configuration with user prompts.
        init_directory_nodialog: Creates the configuration without user prompts.
        init_success: Displays success messages post-initialization.
    """

    DEFAULT_SETTINGS_FILE = "odatix.yml"

    DEFAULT_WORK_PATH = "work"
    DEFAULT_SIMULATION_WORK_PATH = "simulations"
    DEFAULT_FMAX_SYNTHESIS_WORK_PATH = "fmax_synthesis"
    DEFAULT_CUSTOM_FREQ_SYNTHESIS_WORK_PATH = "custom_freq_synthesis"
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
    DEFAULT_CUSTOM_FREQ_SYNTHESIS_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "custom_freq_synthesis_settings.yml")
    
    odatix_path = os.path.realpath(os.path.join(base_path, os.pardir))
    odatix_eda_tools_path = os.path.realpath(os.path.join(odatix_path, os.pardir, "odatix_eda_tools"))
    odatix_init_path = os.path.realpath(os.path.join(odatix_path, os.pardir, "odatix_init"))
    odatix_examples_path = os.path.realpath(os.path.join(odatix_path, os.pardir, "odatix_examples"))

    def __init__(self, settings_filename=DEFAULT_SETTINGS_FILE, silent=False):
        """
        Initialize Odatix settings by reading the configuration file.

        Args:
            settings_filename (str): Name of the settings file to load.
        """
        self.settings_file_exists = os.path.isfile(settings_filename)
        if self.settings_file_exists:
            success = self.read_settings_file(settings_filename)
        else:
            if not silent:
                printc.warning("This directory does not contain an Odatix settings file \"" + settings_filename + "\".", script_name=script_name)
                printc.note("Run Odatix with the '--init' flag to generate it alongside other necessary config files", script_name=script_name)
            self.valid = False

    def read_settings_file(self, settings_filename=DEFAULT_SETTINGS_FILE):
        """
        Read and parse the settings file for Odatix configurations.

        Args:
            settings_filename (str): Path to the settings file.

        Returns:
            bool: True if the settings were successfully loaded, False otherwise.
        """
        if not os.path.isfile(settings_filename):
            printc.note("Odatix settings file \"" + settings_filename + "\" does not exist.", script_name=script_name)
            settings_data = {}
        else:
            with open(settings_filename, "r") as f:
                try:
                    settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
                except Exception as e:
                    printc.error("Settings file \"" + settings_filename + "\" is not a valid YAML file", script_name)
                    printc.cyan("error details: ", end="", script_name=script_name)
                    print(str(e))
                    self.valid = False
                    return False
            
        # Retrieve values from the settings file
        self.work_path, _ = get_from_dict("work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_WORK_PATH, script_name=script_name)
        self.simulation_work_path, _ = get_from_dict("simulation_work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_SIMULATION_WORK_PATH, script_name=script_name)
        self.fmax_synthesis_work_path, _ = get_from_dict("fmax_synthesis_work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_FMAX_SYNTHESIS_WORK_PATH, script_name=script_name)
        self.custom_freq_synthesis_work_path, _ = get_from_dict("custom_freq_synthesis_work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_WORK_PATH, script_name=script_name)
        self.result_path, _ = get_from_dict("result_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_RESULT_PATH, script_name=script_name)
        self.arch_path, _ = get_from_dict("arch_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_ARCH_PATH, script_name=script_name)
        self.sim_path, _ = get_from_dict("sim_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_SIM_PATH, script_name=script_name)
        self.target_path, _ = get_from_dict("target_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_TARGET_PATH, script_name=script_name)
        self.use_benchmark, _ = get_from_dict("use_benchmark", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_USE_BENCHMARK, type=bool, script_name=script_name)
        self.benchmark_file, _ = get_from_dict("benchmark_file", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_BENCHMARK_FILE, script_name=script_name)
        self.clean_settings_file, _ = get_from_dict("clean_settings_file", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_CLEAN_SETTINGS_FILE, script_name=script_name)
        self.simulation_settings_file, _ = get_from_dict("simulation_settings_file", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_SIMULATION_SETTINGS_FILE, script_name=script_name)
        self.fmax_synthesis_settings_file, _ = get_from_dict("fmax_synthesis_settings_file", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE , script_name=script_name)
        self.custom_freq_synthesis_settings_file, _ = get_from_dict("custom_freq_synthesis_settings_file", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_SETTINGS_FILE , script_name=script_name)
        
        # Depreciation warnings
        no_longer_supported = False
        if "sim_work_path" in settings_data:
            printc.warning("\"sim_work_path\" is no longer supported, use \"simulation_work_path\" instead", script_name=script_name)
            no_longer_supported = True
        if "fmax_work_path" in settings_data:
            printc.warning("\"fmax_work_path\" is no longer supported, use \"fmax_synthesis_work_path\" instead", script_name=script_name)
            no_longer_supported = True
        if "custom_freq_work_path" in settings_data:
            printc.warning("\"custom_freq_work_path\" is no longer supported, use \"custom_freq_synthesis_work_path\" instead", script_name=script_name)
            no_longer_supported = True
        if no_longer_supported:
            printc.note("\"simulation_work_path\", \"fmax_synthesis_work_path\" and \"custom_freq_synthesis_work_path\" are relative to \"work_path\"", script_name=script_name)
        
        self.result_types = {
            "custom_freq_synthesis": {
                "key": "custom_freq_synthesis",
                "path": self.custom_freq_synthesis_work_path,
            },
            "fmax_synthesis": {
                "key": "fmax_synthesis",
                "path": self.fmax_synthesis_work_path,
            },
        }

        self.valid = True
        return True
        
    @staticmethod
    def init_examples():
        """
        Copy example configurations to the current directory.

        Returns:
            bool: True if successful, False otherwise.
        """
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
        """
        Initialize the required directory structure for Odatix.

        Returns:
            bool: True if successful, False otherwise.
        """
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
        """
        Initialize the configuration directory with user interaction.

        Args:
            include_examples (bool | None): Whether to include example files (prompted if None).
            prog (str): Program name for success message.

        Returns:
            bool: True if initialization is successful, False otherwise.
        """
        printc.note("This command will create all the configuration files needed by Odatix in the current directory.", script_name=script_name)
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
    def init_directory_nodialog(include_examples=None, prog="", silent=False):
        """
        Initialize the configuration directory without user interaction.

        Args:
            include_examples (bool | None): Whether to include example files.
            prog (str): Program name for success message.

        Returns:
            bool: True if initialization is successful, False otherwise.
        """
        success = OdatixSettings.init_path()
        if not success:
            return False
        if include_examples:
            success = OdatixSettings.init_examples()
            if not success:
                return False
        if not silent:
            OdatixSettings.init_success(prog)
        return True

    @staticmethod
    def init_success(prog=""):
        """
        Display a success message after directory initialization.

        Args:
            prog (str): Program name for the message.
        """
        printc.green("Your directory can now be used by Odatix!", script_name=script_name)
        printc.say("Run ", end="", script_name=script_name)
        printc.bold(prog + " -h", end="")
        print(" to get a list of useful commands")

    def to_dict(self):
        """
        Returns a dictionary representation of the current settings.
        """
        return {
            "work_path": self.work_path,
            "simulation_work_path": self.simulation_work_path,
            "fmax_synthesis_work_path": self.fmax_synthesis_work_path,
            "custom_freq_synthesis_work_path": self.custom_freq_synthesis_work_path,
            "result_path": self.result_path,
            "arch_path": self.arch_path,
            "sim_path": self.sim_path,
            "target_path": self.target_path,
            "use_benchmark": self.use_benchmark,
            "benchmark_file": self.benchmark_file,
            "clean_settings_file": self.clean_settings_file,
            "simulation_settings_file": self.simulation_settings_file,
            "fmax_synthesis_settings_file": self.fmax_synthesis_settings_file,
            "custom_freq_synthesis_settings_file": self.custom_freq_synthesis_settings_file,
            "result_types": self.result_types,
            "valid": self.valid,
            "settings_file_exists": self.settings_file_exists,
        }

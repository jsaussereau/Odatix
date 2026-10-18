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
import odatix.lib.yaml_loader as yaml_loader

current_dir = os.path.dirname(os.path.abspath(__file__))
script_name = os.path.basename(__file__)

######################################
# Settings
######################################

DEFAULT_SETTINGS_FILE = "odatix.yml"

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

    DEFAULT_SETTINGS_FILE = DEFAULT_SETTINGS_FILE

    DEFAULT_WORK_PATH = "work"
    DEFAULT_SIMULATION_WORK_PATH = "simulations"
    DEFAULT_FMAX_SYNTHESIS_WORK_PATH = "fmax_synthesis"
    DEFAULT_CUSTOM_FREQ_SYNTHESIS_WORK_PATH = "custom_freq_synthesis"
    DEFAULT_PNR_WORK_PATH = "pnr"
    DEFAULT_ANALYSIS_WORK_PATH = "analysis"
    DEFAULT_WORKFLOW_WORK_PATH = "workflows"
    DEFAULT_RESULT_PATH = "results"
    DEFAULT_USERCONFIG_PATH = "odatix_userconfig"
    DEFAULT_ARCH_PATH = os.path.join(DEFAULT_USERCONFIG_PATH, "architectures")
    DEFAULT_SIM_PATH = os.path.join(DEFAULT_USERCONFIG_PATH, "simulations")
    DEFAULT_TOOLS_PATH = os.path.join(DEFAULT_USERCONFIG_PATH, "tools")
    DEFAULT_WORKFLOW_PATH = os.path.join(DEFAULT_USERCONFIG_PATH, "workflows")
    # User-defined GUI themes (one .css file per theme, see odatix.gui.themes)
    DEFAULT_GUI_THEME_PATH = os.path.join(DEFAULT_USERCONFIG_PATH, "themes", "gui")
    DEFAULT_TARGET_PATH = os.path.join(DEFAULT_USERCONFIG_PATH, "targets")
    # Target definition files not found in the configured target_path are also
    # looked up in this directory (the userconfig root), so workspaces created
    # before target_path defaulted to "<userconfig>/targets" keep working.
    DEFAULT_TARGET_FALLBACK_PATH = DEFAULT_USERCONFIG_PATH
    # Resource guard of the job scheduler: pause running jobs while the CPU or
    # memory usage of the machine is above these percentages.
    DEFAULT_RESOURCE_GUARD = True
    DEFAULT_CPU_LIMIT = 98.0
    DEFAULT_MEM_LIMIT = 98.0
    # A settings file is named after the command that reads it.
    DEFAULT_CLEAN_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "clean_settings.yml")
    DEFAULT_SIM_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "sim_settings.yml")
    DEFAULT_FMAX_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "fmax_settings.yml")
    DEFAULT_SYNTH_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "synth_settings.yml")
    DEFAULT_PNR_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "pnr_settings.yml")
    DEFAULT_ANALYZE_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "analyze_settings.yml")
    # What those of them that were renamed used to be called. A workspace that
    # still has a file of the former name, and names none in odatix.yml, keeps
    # reading it until "odatix migrate" renames it.
    FORMER_DEFAULT_SETTINGS_FILES = {
        "clean_settings_file": os.path.join(DEFAULT_USERCONFIG_PATH, "clean.yml"),
        "sim_settings_file": os.path.join(DEFAULT_USERCONFIG_PATH, "simulations_settings.yml"),
        "fmax_settings_file": os.path.join(DEFAULT_USERCONFIG_PATH, "fmax_synthesis_settings.yml"),
        "synth_settings_file": os.path.join(DEFAULT_USERCONFIG_PATH, "custom_freq_synthesis_settings.yml"),
        "analyze_settings_file": os.path.join(DEFAULT_USERCONFIG_PATH, "analysis_settings.yml"),
    }
    # The keys of odatix.yml that named the settings files before they were
    # named after their command, and the key each one became. Still read.
    FORMER_SETTINGS_KEYS = {
        "simulation_settings_file": "sim_settings_file",
        "fmax_synthesis_settings_file": "fmax_settings_file",
        "custom_freq_synthesis_settings_file": "synth_settings_file",
        "analysis_settings_file": "analyze_settings_file",
    }
    DEFAULT_WORKFLOW_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "workflow_settings.yml")
    DEFAULT_DSE_SETTINGS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "dse_settings.yml")
    DEFAULT_DSE_CAMPAIGN_PATH = os.path.join(DEFAULT_USERCONFIG_PATH, "dse_campaigns")
    DEFAULT_DERIVED_METRICS_FILE = os.path.join(DEFAULT_USERCONFIG_PATH, "derived_metrics.yml")

    odatix_path = os.path.realpath(os.path.join(base_path, os.pardir))
    odatix_eda_tools_path = os.path.realpath(os.path.join(odatix_path, os.pardir, "odatix_eda_tools"))
    # The simulation templates Odatix provides, one directory per simulator
    # (see odatix.sim.templates).
    odatix_sim_templates_path = os.path.realpath(os.path.join(odatix_path, os.pardir, "odatix_sim_templates"))
    # User eda tools directory, resolved from the workspace settings file when it
    # is read (defaults to DEFAULT_TOOLS_PATH, relative to the current directory).
    # This class-level latch mirrors odatix_eda_tools_path so the many tool
    # resolution call sites can reach it without holding a settings instance.
    user_tools_path = None
    # User GUI theme directory, resolved from the workspace settings file when it
    # is read (defaults to DEFAULT_GUI_THEME_PATH, relative to the current
    # directory). Latched at the class level like user_tools_path so the theme
    # registry can find it without holding a settings instance.
    user_theme_path = None
    # Resource guard settings (enabled, cpu_limit, mem_limit) of the workspace,
    # latched when the settings file is read, like user_tools_path: the job
    # handler takes them as its defaults without holding a settings instance.
    # None until a settings file has been read (the handler then uses the
    # DEFAULT_* values above).
    resource_guard_settings = None
    odatix_init_path = os.path.realpath(os.path.join(odatix_path, os.pardir, "odatix_init"))
    odatix_examples_path = os.path.realpath(os.path.join(odatix_path, os.pardir, "odatix_examples"))

    def __init__(self, settings_filename=DEFAULT_SETTINGS_FILE, silent=False, verbose=False):
        """
        Initialize Odatix settings by reading the configuration file.

        Args:
            settings_filename (str): Name of the settings file to load.
        """
        self.verbose = verbose
        self.settings_file_exists = os.path.isfile(settings_filename)
        if self.settings_file_exists:
            success = self.read_settings_file(settings_filename)
        else:
            if not silent:
                printc.warning("This directory does not contain an Odatix settings file \"" + settings_filename + "\".", script_name=script_name)
                printc.note("Run \"odatix init\" to create it, with the other configuration files", script_name=script_name)
            self.valid = False

    @staticmethod
    def get_settings_file_dict(settings_filename=DEFAULT_SETTINGS_FILE, silent=False, verbose=False):
        """
        Static method to load Odatix settings from a file.

        Args:
            settings_filename (str): Name of the settings file to load.
            silent (bool): If True, suppresses warning messages.
            verbose (bool): If True, enables verbose output.
        Returns:
            dict | None: Dictionary of settings if successful, None otherwise.
        """
        if not os.path.isfile(settings_filename):
            if not silent:
                printc.note("Odatix settings file \"" + settings_filename + "\" does not exist.", script_name=script_name)
            settings_data = {}
        else:
            with open(settings_filename, "r") as f:
                try:
                    settings_data = yaml.load(f, Loader=yaml_loader.SafeLoader)
                except Exception as e:
                    printc.error("Settings file \"" + settings_filename + "\" is not a valid YAML file", script_name)
                    printc.cyan("error details: ", end="", script_name=script_name)
                    print(str(e))
                    return None

        # Empty YAML file -> valid but empty config (defaults will be applied).
        if settings_data is None:
            settings_data = {}

        # Top-level settings must be a mapping.
        if not isinstance(settings_data, dict):
            printc.error(
                "Settings file \"" + settings_filename + "\" does not hold a list of settings.",
                script_name,
            )
            return None
        return OdatixSettings.carry_over_former_keys(settings_data, settings_filename, silent=silent)

    _warned_former_keys = set()

    @staticmethod
    def carry_over_former_keys(settings_data, settings_filename="", silent=False):
        """
        The settings with the former key of each renamed setting read as the
        current one (unless the file says both), saying so once per file.
        """
        settings_data = dict(settings_data)
        for former, key in OdatixSettings.FORMER_SETTINGS_KEYS.items():
            if former not in settings_data:
                continue
            if key not in settings_data:
                settings_data[key] = settings_data[former]
            # Said whatever "silent" says (it only quiets the note about a
            # missing file), but once per file and key: the file is read often.
            seen = (os.path.realpath(settings_filename) if settings_filename else "", former)
            if settings_filename and seen not in OdatixSettings._warned_former_keys:
                OdatixSettings._warned_former_keys.add(seen)
                printc.warning(
                    '"{0}" of "{1}" is now called "{2}": run "odatix migrate" to rewrite it'.format(former, settings_filename, key),
                    script_name,
                )
        return settings_data

    @staticmethod
    def default_settings_file(name, resolve=None):
        """
        The default path of a settings file setting: its current name, or the
        former one when only a file of the former name is there.

        Args:
            name (str): the setting ("fmax_settings_file", ...).
            resolve (callable): turns a workspace path into one usable from here.
        """
        resolve = resolve or (lambda path: path)
        default = getattr(OdatixSettings, "DEFAULT_" + name.upper())
        former = OdatixSettings.FORMER_DEFAULT_SETTINGS_FILES.get(name)
        if former and not os.path.exists(resolve(default)) and os.path.exists(resolve(former)):
            return former
        return default

    def read_settings_file(self, settings_filename=DEFAULT_SETTINGS_FILE):
        """
        Read and parse the settings file for Odatix configurations.

        Args:
            settings_filename (str): Path to the settings file.

        Returns:
            bool: True if the settings were successfully loaded, False otherwise.
        """
        silent = not self.verbose

        settings_data = OdatixSettings.get_settings_file_dict(settings_filename, silent=silent)
        if settings_data is None:
            self.valid = False
            return False

        # Retrieve values from the settings file
        self.work_path, _ = get_from_dict("work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_WORK_PATH, silent=silent, script_name=script_name)
        self.simulation_work_path, _ = get_from_dict("simulation_work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_SIMULATION_WORK_PATH, silent=silent, script_name=script_name)
        self.fmax_synthesis_work_path, _ = get_from_dict("fmax_synthesis_work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_FMAX_SYNTHESIS_WORK_PATH, silent=silent, script_name=script_name)
        self.custom_freq_synthesis_work_path, _ = get_from_dict("custom_freq_synthesis_work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_WORK_PATH, silent=silent, script_name=script_name)
        self.pnr_work_path, _ = get_from_dict("pnr_work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_PNR_WORK_PATH, silent=silent, script_name=script_name)
        self.analysis_work_path, _ = get_from_dict( "analysis_work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_ANALYSIS_WORK_PATH, silent=silent, script_name=script_name)
        self.workflow_work_path, _ = get_from_dict("workflow_work_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_WORKFLOW_WORK_PATH, silent=silent, script_name=script_name)
        self.result_path, _ = get_from_dict("result_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_RESULT_PATH, silent=silent, script_name=script_name)
        self.arch_path, _ = get_from_dict("arch_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_ARCH_PATH, silent=silent, script_name=script_name)
        self.sim_path, _ = get_from_dict("sim_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_SIM_PATH, silent=silent, script_name=script_name)
        self.tools_path, _ = get_from_dict("tools_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_TOOLS_PATH, silent=silent, script_name=script_name)
        # Latch the user tools path at the class level so tool resolution helpers odatix.lib.eda_tools) can find user-defined tools without a settings instance.
        OdatixSettings.user_tools_path = os.path.realpath(self.tools_path)
        self.gui_theme_path, _ = get_from_dict("gui_theme_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_GUI_THEME_PATH, silent=silent, script_name=script_name)
        # Latch the user theme path at the class level so odatix.gui.themes can discover user themes without a settings instance.
        OdatixSettings.user_theme_path = os.path.realpath(self.gui_theme_path)
        self.workflow_path, _ = get_from_dict("workflow_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_WORKFLOW_PATH, silent=silent, script_name=script_name)
        self.target_path, _ = get_from_dict("target_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_TARGET_PATH, silent=silent, script_name=script_name)
        self.resource_guard, self.cpu_limit, self.mem_limit = OdatixSettings.read_resource_guard(settings_data, settings_filename)
        OdatixSettings.resource_guard_settings = (self.resource_guard, self.cpu_limit, self.mem_limit)
        self.clean_settings_file, _ = get_from_dict("clean_settings_file", settings_data, settings_filename, default_value=OdatixSettings.default_settings_file("clean_settings_file"), silent=silent, script_name=script_name)
        self.sim_settings_file, _ = get_from_dict("sim_settings_file", settings_data, settings_filename, default_value=OdatixSettings.default_settings_file("sim_settings_file"), silent=silent, script_name=script_name)
        self.fmax_settings_file, _ = get_from_dict("fmax_settings_file", settings_data, settings_filename, default_value=OdatixSettings.default_settings_file("fmax_settings_file") , silent=silent, script_name=script_name)
        self.synth_settings_file, _ = get_from_dict("synth_settings_file", settings_data, settings_filename, default_value=OdatixSettings.default_settings_file("synth_settings_file") , silent=silent, script_name=script_name)
        self.pnr_settings_file, _ = get_from_dict("pnr_settings_file", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_PNR_SETTINGS_FILE , silent=silent, script_name=script_name)
        self.analyze_settings_file, _ = get_from_dict("analyze_settings_file", settings_data, settings_filename, default_value=OdatixSettings.default_settings_file("analyze_settings_file") , silent=silent, script_name=script_name)
        self.workflow_settings_file, _ = get_from_dict("workflow_settings_file", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_WORKFLOW_SETTINGS_FILE , silent=silent, script_name=script_name)
        self.dse_settings_file, _ = get_from_dict("dse_settings_file", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_DSE_SETTINGS_FILE , silent=silent, script_name=script_name)
        self.dse_campaign_path, _ = get_from_dict("dse_campaign_path", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_DSE_CAMPAIGN_PATH , silent=silent, script_name=script_name)
        self.derived_metrics_file, _ = get_from_dict("derived_metrics_file", settings_data, settings_filename, default_value=OdatixSettings.DEFAULT_DERIVED_METRICS_FILE , silent=silent, script_name=script_name)

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
            "pnr": {
                "key": "pnr",
                "path": self.pnr_work_path,
            },
        }

        self.valid = True
        return True
        
    @staticmethod
    def read_resource_guard(settings_data, settings_filename=DEFAULT_SETTINGS_FILE):
        """
        The resource guard settings of a settings file, checked.

        Args:
            settings_data (dict): the content of the settings file.
            settings_filename (str): its name, for the warnings.

        Returns:
            tuple: (enabled, cpu_limit, mem_limit). A missing or invalid value
                holds its default.
        """
        settings_data = settings_data if isinstance(settings_data, dict) else {}
        enabled = settings_data.get("resource_guard", "")
        if enabled in ("", None):
            enabled = OdatixSettings.DEFAULT_RESOURCE_GUARD
        elif not isinstance(enabled, bool):
            printc.warning(
                "\"resource_guard\" in \"" + settings_filename + "\" should be a boolean, not \"" + str(enabled)
                + "\". Using default value (" + str(OdatixSettings.DEFAULT_RESOURCE_GUARD) + ") instead",
                script_name=script_name,
            )
            enabled = OdatixSettings.DEFAULT_RESOURCE_GUARD

        def limit(key, default):
            value = settings_data.get(key, "")
            if value in ("", None):
                return default
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = None
            if isinstance(settings_data.get(key), bool) or value is None or not 1.0 <= value <= 100.0:
                printc.warning(
                    "\"" + key + "\" in \"" + settings_filename + "\" should be a percentage between 1 and 100, not \""
                    + str(settings_data.get(key)) + "\". Using default value (" + str(default) + ") instead",
                    script_name=script_name,
                )
                return default
            return value

        cpu_limit = limit("cpu_limit", OdatixSettings.DEFAULT_CPU_LIMIT)
        mem_limit = limit("mem_limit", OdatixSettings.DEFAULT_MEM_LIMIT)
        return bool(enabled), cpu_limit, mem_limit

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
        printc.say("New to Odatix? Follow https://odatix.readthedocs.io/docs/getting-started/", script_name=script_name)

    def to_dict(self):
        """
        The settings as a mapping, every one of them resolved (a setting the
        file leaves out holds its default).
        """
        from odatix.workspace.core import PATH_SETTINGS

        settings = dict((name, getattr(self, name)) for name, _default in PATH_SETTINGS)
        return settings

    @staticmethod
    def from_dict(settings_dict):
        """
        Create an OdatixSettings object from a dictionary.

        Args:
            settings_dict (dict): Dictionary containing settings.
        Returns:
            OdatixSettings: The created settings object.
        """
        settings = OdatixSettings()
        for key, value in settings_dict.items():
            try:
                setattr(settings, key, value)
            except Exception as e:
                printc.warning(f"Key '{key}' is not a valid attribute of OdatixSettings: {str(e)}. Skipping key.", script_name=script_name)
        return settings

    @staticmethod
    def save_dict_to_file(settings, settings_filename=DEFAULT_SETTINGS_FILE):
        """
        Write settings into a workspace settings file. Only the given keys are
        changed: the comments, the layout and every other key of the file are
        kept. A key given empty is removed, so that its default applies.

        This is the same writer as :meth:`odatix.workspace.Workspace.save_settings`.
        """
        from odatix.workspace.core import save_workspace_settings

        save_workspace_settings(settings_filename, settings)

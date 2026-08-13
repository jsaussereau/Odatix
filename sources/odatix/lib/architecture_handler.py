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
import yaml
import copy

from os.path import isfile
from os.path import isdir

from odatix.lib import hard_settings
from odatix.lib.settings import OdatixSettings
from odatix.lib.utils import *
from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
from odatix.lib.parallel_job_handler.daemon_control import list_daemon_jobs
import odatix.lib.printc as printc
from odatix.lib.run_report import JobPlan, Category
from odatix.lib.variables import replace_variables, Variables
from odatix.lib.param_domain import ParamDomain
import odatix.lib.virtual_param_domain as virtual_param_domain
import odatix.lib.constraint_files as constraints_lib
from odatix.lib.constraint_files import ConstraintFileError
import odatix.lib.overrides as overrides_lib
from odatix.lib.overrides import OverrideError
from odatix.run.planner import JobPlanner
import odatix.workspace.architectures as workspace_architectures
import odatix.workspace.selection as selection
from odatix.workspace.errors import InvalidSettingsError
from odatix.workspace.yaml_io import read_mapping

script_name = os.path.basename(__file__)

class Architecture:
    def __init__(
        self, arch_name, arch_display_name, lib_name, target, local_rtl_path, tmp_script_path, tmp_report_path, tmp_log_path, tmp_dir, 
        design_path, design_path_whitelist, design_path_blacklist, rtl_path, log_path, arch_path,
        clock_signal, reset_signal, top_level_module, top_level_filename, use_parameters, start_delimiter, stop_delimiter,
        file_copy_enable, file_copy_source, file_copy_dest, script_copy_enable, script_copy_source, 
        fmax_lower_bound, fmax_upper_bound, range_list, target_frequency,
        param_target_filename, generate_rtl, generate_command, constraint_filename, install_path, 
        param_domains, continue_on_error=False, force_single_thread=False, virtual_param_domains=None,
        constraint_files=None,
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
        # Constraint files the user provides, read on top of the timing
        # constraint file Odatix generates: {"source", "scope", "dest"} entries,
        # already resolved (see lib/constraint_files.py).
        self.constraint_files = list(constraint_files) if constraint_files else []
        self.install_path = install_path
        self.param_domains = param_domains
        # Variables selected for this job: domains with no directory on disk, kept
        # apart from the physical ones since they have no parameter file to apply.
        self.virtual_param_domains = (
            dict(virtual_param_domains) if isinstance(virtual_param_domains, dict) else {}
        )
        self.continue_on_error = continue_on_error
        self.force_single_thread = force_single_thread

    # Keys of a ParamDomain serialized in the job's settings.yml. Writing them all
    # is what lets read_yaml rebuild the domains instead of only their values.
    PARAM_DOMAIN_KEYS = (
        "domain",
        "domain_value",
        "use_parameters",
        "start_delimiter",
        "stop_delimiter",
        "param_target_file",
        "param_file",
    )

    def write_yaml(arch, config_file):
        domain_list = [
            {key: getattr(param_domain, key, None) for key in Architecture.PARAM_DOMAIN_KEYS}
            for param_domain in (arch.param_domains or [])
        ]
        yaml_data = {
            'arch_name': arch.arch_name,
            'arch_display_name': arch.arch_display_name,
            'lib_name': arch.lib_name,
            'target': arch.target,
            'rtl_path': arch.local_rtl_path,
            'script_path': arch.tmp_script_path,
            'report_path': arch.tmp_report_path,
            'log_path': arch.tmp_log_path,
            'local_log_path': arch.log_path,
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
            'constraint_files': arch.constraint_files,
            'install_path': arch.install_path,
            'param_domains': domain_list,
            'virtual_param_domains': arch.virtual_param_domains,
            'continue_on_error': arch.continue_on_error,
            'force_single_thread': arch.force_single_thread,
        }
            
        with open(config_file, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    @staticmethod
    def read_param_domains(value):
        """
        Rebuild the parameter domains of a job from what its settings.yml holds.

        Two shapes are accepted: the list of full domains write_yaml produces, and
        the "{domain: value}" mapping older job directories hold, which only
        carries the domain values.
        """
        if isinstance(value, list):
            return [
                ParamDomain(**{key: entry.get(key) for key in Architecture.PARAM_DOMAIN_KEYS})
                for entry in value
                if isinstance(entry, dict)
            ]
        if isinstance(value, dict):
            return [
                ParamDomain(
                    domain=domain,
                    domain_value=domain_value,
                    use_parameters=False,
                    start_delimiter=None,
                    stop_delimiter=None,
                    param_target_file=None,
                    param_file=None,
                )
                for domain, domain_value in value.items()
            ]
        return []

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
                log_path                 = get_from_dict("local_log_path", yaml_data, config_file, default_value=hard_settings.work_log_path, silent=True, script_name=script_name)[0],
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
                # Optional: job directories written before user constraint files
                # existed have no such key, and they stay readable.
                constraint_files         = get_from_dict("constraint_files", yaml_data, config_file, default_value=[], silent=True, script_name=script_name)[0],
                install_path             = get_from_dict("install_path", yaml_data, config_file, behavior=Key.MANTADORY_RAISE, script_name=script_name)[0],
                param_domains            = Architecture.read_param_domains(
                    get_from_dict("param_domains", yaml_data, config_file, default_value=[], silent=True, script_name=script_name)[0]
                ),
                virtual_param_domains    = get_from_dict("virtual_param_domains", yaml_data, config_file, default_value={}, silent=True, script_name=script_name)[0],
                continue_on_error        = get_from_dict("continue_on_error", yaml_data, config_file, default_value=False, script_name=script_name)[0],
                force_single_thread      = get_from_dict("force_single_thread", yaml_data, config_file, default_value=False, script_name=script_name)[0],
            )
        except (KeyNotInDictError, BadValueInDictError):
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
        fallback_custom_freq_list=None,
        tool="",
        flow="",
        continue_on_error=False,
        force_single_thread=False,
        requested_steps=None,
        rerun_step_index=None,
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
        self.fallback_custom_freq_list = fallback_custom_freq_list

        # Which jobs a rule of an architecture's "overrides" section selects is
        # answered with these: the tool running the jobs and the flow of it they
        # run. Empty for a run that has no tool (RTL analysis), which only
        # rules naming no tool then apply to.
        self.tool = tool or ""
        self.flow = flow or ""

        self.continue_on_error = continue_on_error
        self.force_single_thread = force_single_thread

        # What to do with a job directory that already exists is the same
        # question for every job type, and is answered there.
        self.planner = JobPlanner(
            work_path=work_path,
            work_log_path=work_log_path,
            status_filename=fmax_status_filename,
            valid_status=valid_status,
            overwrite=overwrite,
            requested_steps=requested_steps,
            rerun_step_index=rerun_step_index,
        )

        self.reset_lists()

        self.odatix_path = os.path.realpath(os.path.join(self.script_path, ".."))

    ######################################
    # What this run does with a job directory
    ######################################

    # The decisions themselves live in the planner; these keep the handler
    # usable as it always was, from the run flows and from the GUI.

    @property
    def plan(self):
        return self.planner.plan

    @property
    def overwrite(self):
        return self.planner.overwrite

    @overwrite.setter
    def overwrite(self, value):
        self.planner.overwrite = value

    @property
    def requested_steps(self):
        return self.planner.requested_steps

    @property
    def rerun_step_index(self):
        return self.planner.rerun_step_index

    def steps_decision(self, tmp_dir):
        return self.planner.steps_decision(tmp_dir)

    def classify_job(self, tmp_dir, subject, job_noun="synthesis"):
        return self.planner.classify_job(tmp_dir, subject, job_noun=job_noun)

    @staticmethod
    def _format_daemon_entry(entry):
        return JobPlanner.format_daemon_entry(entry)

    def _get_daemon_job_decision(self, tmp_dir, steps_decision=None):
        return self.planner.daemon_decision(tmp_dir, steps_decision)

    def _refresh_daemon_jobs_index(self):
        self.planner.refresh_daemon_jobs()

    def reset_lists(self):
        self.checked_arch_param = []
        self.banned_arch_param = []
        self.planner.reset()
        # Architectures that passed *every* check. Not derivable from the plan:
        # an architecture is categorized (new, overwrite, ...) before the last
        # checks run, and may still be rejected afterwards.
        self.valid_archs = []
        self.deprecation_notice_archs = []

    # Kept as read-only views so existing callers (and the CLI) keep working.
    @property
    def cached_archs(self):
        return self.plan.names(Category.CACHED)

    @property
    def overwrite_archs(self):
        return self.plan.names(Category.OVERWRITE)

    @property
    def error_archs(self):
        return self.plan.names(Category.ERROR)

    @property
    def incomplete_archs(self):
        return self.plan.names(Category.INCOMPLETE)

    @property
    def daemon_archs(self):
        return self.plan.names(Category.DAEMON)

    @property
    def new_archs(self):
        return self.plan.names(Category.NEW)

    def get_architectures(self, architectures, targets, constraint_filename="", install_path="", run_mode="default", keep=False, timestamp="", allow_missing_target_file=False):

        self.reset_lists()
        self.architecture_instances = []
        self._refresh_daemon_jobs_index()

        only_one_target = len(targets) == 1

        # Define user accessible variables
        variables = Variables(
            tool_install_path=os.path.realpath(install_path),
            odatix_path=OdatixSettings.odatix_path,
            odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
        )

        # A missing / None target file is only tolerated when explicitly allowed
        # (RTL analysis, odatix analyze, does not use target definition files).
        # Every other flow (synthesis) still requires a valid target file.
        has_target_file = self.eda_target_filename is not None and os.path.isfile(self.eda_target_filename)
        if not has_target_file and not allow_missing_target_file:
            printc.error("Settings file \"" + str(self.eda_target_filename) + "\" does not exist or is not a valid file", script_name)
            sys.exit(-1)

        if not has_target_file:
            settings_data = {}
            script_copy_enable = False
            script_copy_source = "/dev/null"
            target_settings = {}
            base_constraints = []
        else:
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

            # Constraint files every target of this tool gets. What a target
            # declares for itself is added to these, not substituted for them:
            # the list here is what does not depend on the part.
            try:
                base_constraints = constraints_lib.read_constraints(settings_data, self.eda_target_filename, variables)
            except ConstraintFileError as error:
                printc.error(str(error), script_name)
                sys.exit(-1)

        # Expand every (target, architecture) pair into an architecture instance.
        # For RTL analysis the target list is a single generic entry.
        if True:
            # Virtual parameter domains have no directory on disk: drop their
            # wildcard selectors before the generic wildcard resolver runs.
            full_architectures = virtual_param_domain.normalize_requests_for_wildcards(
                requests=architectures,
                base_path=self.arch_path,
                get_basic=ArchitectureHandler.get_basic,
                param_settings_filename=self.param_settings_filename,
                script_name=script_name,
            )
            for target in targets:
                target_constraints = list(base_constraints)
                # Overwrite existing script copy settings if the target file has some for this target
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

                        # Constraint files of this target only: an IO placement
                        # is a property of the part or the board, not of the tool.
                        try:
                            target_constraints += constraints_lib.read_constraints(
                                this_target_settings, self.eda_target_filename, variables,
                                parent="target_settings/" + target,
                            )
                        except ConstraintFileError as error:
                            printc.error(str(error), script_name)
                            sys.exit(-1)

                # Handle wildcard
                architectures = ArchitectureHandler.configuration_wildcard(full_architectures, self.arch_path, target)

                # One job per combination of the virtual parameter domains
                architectures = self.expand_virtual_param_domains(architectures, target, only_one_target)

                for arch, command_substitutions in architectures:
                    architecture_instance = self.get_architecture(
                        arch = arch,
                        target = target,
                        only_one_target = only_one_target,
                        script_copy_enable = script_copy_enable,
                        script_copy_source = script_copy_source,
                        synthesis = True,
                        constraint_filename = constraint_filename,
                        target_constraints = target_constraints,
                        install_path = install_path,
                        run_mode = run_mode,
                        keep=keep,
                        timestamp=timestamp,
                        command_substitutions=command_substitutions,
                    )
                    if run_mode == "custom_freq":
                        if architecture_instance is not None:
                            for freq in architecture_instance.range_list:
                                freq_arch = copy.copy(architecture_instance)
                                formatted_freq = " {}@ {} MHz{}".format(printc.colors.GREY, freq, printc.colors.ENDC)
                                unformatted_display_name = freq_arch.arch_display_name
                                freq_arch.arch_display_name = freq_arch.arch_display_name + " @ " + str(freq) + " MHz"
                                freq_arch.tmp_dir = os.path.join(freq_arch.tmp_dir, str(freq) + "MHz")
                                freq_arch.tmp_script_path = os.path.join(freq_arch.tmp_dir, self.work_script_path)
                                freq_arch.tmp_report_path = os.path.join(freq_arch.tmp_dir, self.work_report_path)
                                freq_arch.tmp_log_path = os.path.join(freq_arch.tmp_dir, self.work_log_path)
                                freq_arch.target_frequency = freq
                                freq_arch.lib_name = freq_arch.lib_name + "_" + str(freq) + "MHz"

                                # check if the architecture is in cache and has a status file
                                subject = (
                                    "\"" + unformatted_display_name + "\" @ " + str(freq)
                                    + " MHz with target \"" + target + "\""
                                )
                                local_state, daemon_entry = self.classify_job(freq_arch.tmp_dir, subject)

                                if local_state == "cached":
                                    self.plan.add(freq_arch.arch_display_name, Category.CACHED)
                                    continue

                                if local_state == "daemon":
                                    self.plan.add(freq_arch.arch_display_name + ArchitectureHandler._format_daemon_entry(daemon_entry), Category.DAEMON)
                                    continue

                                if local_state == "overwrite":
                                    self.plan.add(unformatted_display_name, Category.OVERWRITE)
                                elif local_state == "incomplete":
                                    self.plan.add(freq_arch.arch_display_name, Category.INCOMPLETE)
                                elif local_state == "resume":
                                    self.plan.add(freq_arch.arch_display_name + formatted_freq, Category.RESUME)
                                else:
                                    self.plan.add(unformatted_display_name + formatted_freq, Category.NEW)

                                self.architecture_instances.append(freq_arch)
                                self.valid_archs.append(unformatted_display_name + formatted_freq)

                    else:
                        if architecture_instance is not None:
                            self.architecture_instances.append(architecture_instance)
        return self.architecture_instances

    def expand_virtual_param_domains(self, architectures, target="", only_one_target=True, debug=False):
        """
        Expand each architecture request into one request per combination of its
        virtual parameter domains (the variables defined in its settings file).

        Only "generate_command" consumes these variables, so an architecture that
        does not reference any of them there keeps a single job, and its variables
        keep their sole original meaning: generating configurations.

        Returns a list of (architecture request, command substitutions) tuples.
        """
        expanded = []
        for arch_request in architectures:
            expanded.extend(
                self._expand_arch_virtual_param_domains(arch_request, target, only_one_target, debug=debug)
            )
        return expanded

    def _expand_arch_virtual_param_domains(self, arch_request, target="", only_one_target=True, debug=False):
        no_expansion = [(arch_request, {})]

        arch, arch_param_dir, _, arch_display_name, _, _, requested_param_domains = ArchitectureHandler.get_basic(
            arch_request, target, only_one_target
        )

        settings_data = virtual_param_domain.load_instance_settings(
            self.arch_path, arch_param_dir, self.param_settings_filename
        )
        if settings_data is None:
            # Missing or invalid settings file: let get_architecture report it.
            return no_expansion

        virtual_domain_names = virtual_param_domain.get_virtual_domain_names(settings_data)
        if len(virtual_domain_names) == 0:
            return no_expansion

        requested_physical_param_domains, requested_virtual_param_domains = (
            virtual_param_domain.split_requested_param_domains(requested_param_domains, virtual_domain_names)
        )

        generate_command = settings_data.get("generate_command", "") if settings_data.get("generate_rtl", False) else ""
        referenced_variables = virtual_param_domain.referenced_variable_names(generate_command) & virtual_domain_names

        # Without an explicit selector, only expand when the generation command
        # actually uses the variables.
        if len(requested_virtual_param_domains) == 0 and len(referenced_variables) == 0:
            return no_expansion

        settings_file = os.path.join(self.arch_path, arch_param_dir, self.param_settings_filename)
        variants = virtual_param_domain.build_variants(
            settings=settings_data,
            settings_file=settings_file,
            debug=debug,
            script_name=script_name,
        )
        if variants is None:
            self.plan.add(arch_display_name, Category.ERROR)
            return []
        if len(variants) == 0:
            return no_expansion

        if len(requested_virtual_param_domains) > 0:
            variants = virtual_param_domain.filter_variants(variants, requested_virtual_param_domains)
            if len(variants) == 0:
                requested_domain = re.sub('/.*', '', requested_virtual_param_domains[0])
                requested_value = re.sub('.*/', '', requested_virtual_param_domains[0])
                printc.error(
                    "No variable combination matches selector(s) for architecture \"" + arch_display_name + "\".",
                    script_name,
                )
                printc.tip(
                    "Add a parameter-domain config file \"" + requested_value + ".txt\" in \""
                    + os.path.join(arch_param_dir, requested_domain) + "\" ",
                    script_name,
                )
                printc.magenta(
                    "or add a variable \"" + requested_domain + "\" generating the value \"" + requested_value
                    + "\" to the architecture settings file \"" + settings_file + "\"."
                )
                self.plan.add(arch_display_name, Category.ERROR)
                return []

        expanded = []
        for variant in variants:
            variant_param_domains = requested_physical_param_domains + list(variant.get("requested_param_domains", []))
            variant_request = arch
            if len(variant_param_domains) > 0:
                variant_request = arch + "+" + "+".join(variant_param_domains)
            expanded.append((variant_request, variant.get("substitutions", {})))

        return expanded

    @staticmethod
    def get_basic(arch, target="", only_one_target=True):
        """
        Read a job selection entry ("counter/08bits+corner/tt").

        The grammar itself lives in odatix.workspace.selection, which every part
        of Odatix reading a selection goes through. What is left here is the flat
        tuple the run flows are written around, and the printing of what reading
        the entry has to say.
        """
        request = selection.parse(arch)
        for message in request.notes:
            printc.note(message.text, script_name)

        return (
            request.path if request.has_configuration else request.entry,
            request.entry,
            request.configuration,
            request.display_name(target, only_one_target),
            request.entry,
            request.work_dirname,
            request.domains,
        )


    def generation_command_substitutions(
        self, arch_param_dir, arch_config, arch_display_name, target, tmp_dir, local_rtl_path,
        design_path, top_level_module, clock_signal, reset_signal
    ):
        """
        The names Odatix itself replaces in a generation command.

        Same spirit as the simulation and workflow commands: what the command
        needs to know about the job it generates the RTL of, so it does not have
        to be written around hardcoded paths. The command runs from the work
        directory, so the paths it is given inside it are relative to it.

        Kept in step with odatix.gui.builtin_variables, which promises this list
        to the user in the architecture editor.
        """
        substitutions = {
            "architecture": arch_param_dir,
            "configuration": arch_config,
            "arch_full": arch_display_name,
            "target": target,
            "top_level_module": top_level_module,
            "clock_signal": clock_signal,
            "reset_signal": reset_signal,
            "work_path": tmp_dir,
            "rtl_path": local_rtl_path,
            "log_path": self.log_path,
            "design_path": design_path if design_path else "",
            "arch_path": self.arch_path,
            "odatix_path": OdatixSettings.odatix_path,
        }
        # A setting left empty reads as an empty string rather than as "None".
        return {name: str(value) if value is not None else "" for name, value in substitutions.items()}

    def get_architecture(self, arch, target="", only_one_target=True, script_copy_enable=False, script_copy_source="/dev/null", synthesis=False, constraint_filename="", install_path="", run_mode="fmax", keep=False, timestamp="", command_substitutions=None, target_constraints=None):
        
        arch, arch_param_dir, arch_config, arch_display_name, arch_param_dir_work, arch_config_dir_work, requested_param_domains = ArchitectureHandler.get_basic(arch, target, only_one_target)

        # check if there is a configuration specified
        if arch_config == arch_param_dir:
            # printc.note("No architecture configuration selected for \"" + arch +  "\". Using default parameters", script_name)
            arch = arch + "/" + arch
            no_configuration = True
        else:
            no_configuration = False
        
        arch_config_dir_work = arch_config_dir_work + "_" + timestamp if keep and timestamp != "" else arch_config_dir_work

        tmp_dir = os.path.join(self.work_path, target, arch_param_dir_work, arch_config_dir_work)
        fmax_status_file = os.path.join(tmp_dir, self.log_path, self.fmax_status_filename)
        frequency_search_file = os.path.join(tmp_dir, self.log_path, self.frequency_search_filename)

        # check if arch_param has been banned
        if arch_param_dir in self.banned_arch_param:
            self.plan.add(arch_display_name, Category.ERROR)
            return None

        # check if parameter dir exists
        arch_param = os.path.join(self.arch_path, arch_param_dir)
        if not isdir(arch_param):
            printc.error("There is no directory \"" + arch_param_dir + "\" in directory \"" + self.arch_path + "\"", script_name)
            self.banned_arch_param.append(arch_param_dir)
            self.plan.add(arch_display_name, Category.ERROR)
            return None
        
        # check if settings file exists
        if not isfile(os.path.join(arch_param, self.param_settings_filename)):
            printc.error("There is no setting file \"" + self.param_settings_filename + "\" in directory \"" + arch_param + "\"", script_name)
            self.banned_arch_param.append(arch_param_dir)
            self.plan.add(arch_display_name, Category.ERROR)
            return None

        # get settings variables
        settings_filename = os.path.join(self.arch_path, arch_param_dir, self.param_settings_filename)
        try:
            settings_data = read_mapping(settings_filename)
        except InvalidSettingsError as error:
            printc.error(str(error), script_name)
            for hint in error.hints:
                printc.cyan(hint, script_name=script_name)
            self.banned_arch_param.append(arch_param_dir)
            self.plan.add(arch_display_name, Category.ERROR)
            return None

        # What the architecture has to say before a job can be built from it.
        settings_messages = workspace_architectures.validate(settings_data, settings_filename)
        if settings_messages:
            printc.messages(settings_messages, script_name)
            self.banned_arch_param.append(arch_param_dir)
            self.plan.add(arch_display_name, Category.ERROR)
            return None

        settings = workspace_architectures.ArchitectureSettings.from_dict(settings_data)

        top_level_filename = settings.top_level_file
        top_level_module = settings.top_level_module
        clock_signal = settings.clock_signal
        reset_signal = settings.reset_signal

        file_copy_enable = settings.file_copy_enable
        file_copy_source = settings.file_copy_source if file_copy_enable else ""
        file_copy_dest = settings.file_copy_dest if file_copy_enable else ""

        generate_rtl = settings.generate_rtl
        generate_command = settings.generate_command if generate_rtl else ""
        if generate_rtl:
            # The generation writes into the work directory, so that is where
            # the design is read from, wherever the command puts it.
            local_rtl_path = settings.generate_output or self.work_rtl_path
            rtl_path = self.work_rtl_path
        else:
            local_rtl_path = self.work_rtl_path
            rtl_path = settings.rtl_path

        top_level = os.path.join(rtl_path, top_level_filename)

        # The default target file for parameter replacement, written the way the
        # user would have written it: relative to what the sources are copied
        # from. Generating the RTL, that is "design_path", copied at the root of
        # the work directory, so the generation output has to be named;
        # otherwise it is "rtl_path", and the "rtl" subfolder it is copied into
        # is added by the job itself (see run_common.resolve_param_target_file).
        if generate_rtl:
            work_top_level = os.path.join(local_rtl_path, top_level_filename)
        else:
            work_top_level = top_level_filename

        use_parameters, start_delimiter, stop_delimiter, param_target_filename = self.get_use_parameters(arch, arch_display_name, settings_data, settings_filename, work_top_level, no_configuration, arch_param_dir=arch_param_dir)
        if use_parameters is None or start_delimiter is None or stop_delimiter is None or param_target_filename is None:
            return None

        design_path = settings_data.get("design_path")
        design_path_whitelist = settings.design_path_whitelist
        design_path_blacklist = settings.design_path_blacklist

        if not generate_rtl:
            # check if rtl path exists
            if not isdir(rtl_path):
                printc.error("The rtl path \"" + rtl_path + "\" specified in \"" + settings_filename + "\" does not exist", script_name)
                self.banned_arch_param.append(arch_param_dir)
                self.plan.add(arch_display_name, Category.ERROR)
                return None

            # check if top level file path exists
            if not isfile(top_level):
                printc.error("The top level file \"" + top_level_filename + "\" specified in \"" + settings_filename + "\" does not exist", script_name)
                self.banned_arch_param.append(arch_param_dir)
                self.plan.add(arch_display_name, Category.ERROR)
                return None

            # check if the top level module name exists in the top level file, at least
            f = open(top_level, "r")
            if top_level_module not in f.read():
                printc.error("There is no occurence of top level module name \"" + top_level_module + "\" in top level file \"" + top_level + "\"", script_name)
                self.banned_arch_param.append(arch_param_dir)
                self.plan.add(arch_display_name, Category.ERROR)
                f.close()
                return None
            f.close()
            
            # check if the top clock name exists in the top level file, at least
            f = open(top_level, "r")
            if clock_signal not in f.read():
                printc.error("There is no occurence of clock signal name \"" + clock_signal + "\" in top level file \"" + top_level + "\"", script_name)
                self.banned_arch_param.append(arch_param_dir)
                self.plan.add(arch_display_name, Category.ERROR)
                f.close()
                return None
            f.close()
            
            # check if the top reset name exists in the top level file, at least
            f = open(top_level, "r")
            if clock_signal not in f.read():
                printc.error("There is no occurence of reset signal name \"" + reset_signal + "\" in top level file \"" + top_level + "\"", script_name)
                self.banned_arch_param.append(arch_param_dir)
                self.plan.add(arch_display_name, Category.ERROR)
                f.close()
                return None
            f.close()

        # check if param file exists
        if not no_configuration:
            if not isfile(os.path.join(self.arch_path, arch + '.txt')):
                printc.error("The parameter file \"" + arch + ".txt\" does not exist in directory \"" + os.path.join(self.arch_path, arch_param_dir) + "\"", script_name)
                self.banned_arch_param.append(arch_param_dir)
                self.plan.add(arch_display_name, Category.ERROR)
                return None
        
        # Virtual parameter domains (variables) have no directory on disk: their
        # values are provided as command substitutions instead.
        virtual_domain_names = virtual_param_domain.get_virtual_domain_names(settings_data)
        requested_physical_param_domains, requested_virtual_param_domains = (
            virtual_param_domain.split_requested_param_domains(requested_param_domains, virtual_domain_names)
        )
        virtual_param_domains = virtual_param_domain.domains_dict(requested_virtual_param_domains)

        if len(requested_physical_param_domains) > 0:
            param_domains = ParamDomain.get_param_domains(
                requested_param_domains=requested_physical_param_domains,
                architecture=arch_param_dir,
                arch_path=self.arch_path,
                param_settings_filename=self.param_settings_filename,
                top_level_file=work_top_level
            )
            if param_domains is None:
                self.banned_arch_param.append(arch_param_dir)
                self.plan.add(arch_display_name, Category.ERROR)
                return None
        else:
            param_domains = []

        # Resolve ${...} placeholders in the generation command: Odatix' own names
        # first, then virtual parameter domains (variables), then the values of the
        # selected configuration and of each physical parameter domain. The user's
        # own names come last on purpose: a parameter domain named like a built-in
        # one is what the user wrote, so it is what wins.
        if generate_rtl and generate_command:
            substitutions = self.generation_command_substitutions(
                arch_param_dir=arch_param_dir,
                arch_config=arch_config,
                arch_display_name=arch_display_name,
                target=target,
                tmp_dir=tmp_dir,
                local_rtl_path=local_rtl_path,
                design_path=design_path,
                top_level_module=top_level_module,
                clock_signal=clock_signal,
                reset_signal=reset_signal,
            )
            if isinstance(command_substitutions, dict):
                for key, value in command_substitutions.items():
                    substitutions[str(key)] = str(value)

            if not no_configuration:
                main_value = virtual_param_domain.read_command_parameter_value(
                    os.path.join(self.arch_path, arch + ".txt")
                )
                if main_value is not None:
                    substitutions[arch_param_dir] = main_value

            for param_domain in param_domains:
                domain_value = virtual_param_domain.read_command_parameter_value(param_domain.param_file)
                if domain_value is not None:
                    substitutions[param_domain.domain] = domain_value

            generate_command = virtual_param_domain.replace_command_vars(generate_command, substitutions)

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
                run_mode=run_mode,
                fallback_custom_freq_list=self.fallback_custom_freq_list,
                tool=self.tool,
                flow=self.flow,
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
            if run_mode == "fmax":
                if not ArchitectureHandler.check_bounds(fmax_lower_bound, fmax_upper_bound):
                    self.banned_arch_param.append(arch_param_dir)
                    self.plan.add(arch_display_name, Category.ERROR)
                    return None
            elif run_mode == "custom_freq":
                if range_list is None or range_list == []: 
                    self.banned_arch_param.append(arch_param_dir)
                    self.plan.add(arch_display_name, Category.ERROR)
                    return None

            fmax_lower_bound = str(fmax_lower_bound)
            fmax_upper_bound = str(fmax_upper_bound)

            if run_mode == "fmax":
                formatted_bound = " {}({} - {} MHz){}".format(printc.colors.GREY, fmax_lower_bound, fmax_upper_bound, printc.colors.ENDC)
            else:
                formatted_bound = ""

            # check if the architecture is in cache and has a status file
            if run_mode == "fmax":
                local_state = "new"
                steps_decision = self.steps_decision(tmp_dir)
                if steps_decision is not None:
                    if steps_decision == "cached":
                        if self.overwrite:
                            printc.warning("Every requested step is already done for \"" + arch + "\" with target \"" + target + "\".", script_name)
                            local_state = "overwrite"
                        else:
                            printc.note("Every requested step is already done for \"" + arch + "\" with target \"" + target + "\". Skipping.", script_name)
                            self.plan.add(arch_display_name, Category.CACHED)
                            return None
                    elif steps_decision == "resume" and not self.overwrite:
                        local_state = "resume"
                elif isdir(tmp_dir) and isfile(fmax_status_file) and isfile(frequency_search_file):
                    # check if the previous synth_fmax has completed
                    sf = open(fmax_status_file, "r")
                    if self.valid_status in sf.read():
                        ff = open(frequency_search_file, "r")
                        if self.valid_frequency_search in ff.read():
                            if self.overwrite:
                                printc.warning("Found cached results for \"" + arch + "\" with target \"" + target + "\".", script_name)
                                local_state = "overwrite"
                            else:
                                printc.note("Found cached results for \"" + arch + "\" with target \"" + target + "\". Skipping.", script_name)
                                self.plan.add(arch_display_name, Category.CACHED)
                                return None
                        else:
                            printc.warning("The previous synthesis for \"" + arch + "\" did not result in a valid maximum operating frequency.", script_name)
                            local_state = "incomplete"
                        ff.close()
                    else: 
                        printc.warning("The previous synthesis for \"" + arch + "\" has not finished or the directory has been corrupted.", script_name)
                        local_state = "incomplete"
                    sf.close()

                daemon_decision, daemon_entry = self._get_daemon_job_decision(tmp_dir, steps_decision)
                if daemon_decision == "skip":
                    daemon_status = str(daemon_entry.get("status", "unknown"))
                    daemon_session = str(daemon_entry.get("session_id", "")).strip() or "unknown"
                    printc.note(
                        "Found existing daemon job for \""
                        + arch
                        + "\" with target \""
                        + target
                        + "\" (session \""
                        + daemon_session
                        + "\", status \""
                        + daemon_status
                        + "\"). Skipping.",
                        script_name,
                    )
                    self.plan.add(arch_display_name + formatted_bound + ArchitectureHandler._format_daemon_entry(daemon_entry), Category.DAEMON)
                    return None
                elif daemon_decision == "replace":
                    daemon_status = str(daemon_entry.get("status", "unknown"))
                    printc.warning(
                        "Found previously failed/canceled daemon job for \""
                        + arch
                        + "\" with target \""
                        + target
                        + "\" (status \""
                        + daemon_status
                        + "\"). Re-enqueueing.",
                        script_name,
                    )

                if local_state == "overwrite":
                    self.plan.add(arch_display_name + formatted_bound, Category.OVERWRITE)
                elif local_state == "incomplete":
                    self.plan.add(arch_display_name + formatted_bound, Category.INCOMPLETE)
                elif local_state == "resume":
                    self.plan.add(arch_display_name + formatted_bound, Category.RESUME)
                else:
                    self.plan.add(arch_display_name + formatted_bound, Category.NEW)

            elif run_mode == "default":
                self.plan.add(arch_display_name, Category.NEW)

        # What this architecture says for a part of its jobs only: the rules of
        # its "overrides" section that select this one, in file order, the last
        # of them having the last word (see odatix.lib.overrides).
        try:
            job_overrides = overrides_lib.select(
                settings_data, tool=self.tool, flow=self.flow, target=target,
                configuration=arch_config, where=settings_filename,
            )
        except OverrideError as error:
            printc.error(str(error), script_name)
            self.banned_arch_param.append(arch_param_dir)
            self.plan.add(arch_display_name, Category.ERROR)
            return None

        # file copy of these jobs only
        for index, override in enumerate(job_overrides):
            parent = overrides_lib.OVERRIDES_KEY + "[" + str(index) + "]"
            try:
                _file_copy_enable = read_from_list('file_copy_enable', override, settings_filename, optional=True, print_error=False, type=bool, parent=parent, script_name=script_name)
                try:
                    _file_copy_source = read_from_list('file_copy_source', override, settings_filename, optional=True, parent=parent, script_name=script_name)
                    _file_copy_dest = read_from_list('file_copy_dest', override, settings_filename, optional=True, parent=parent, script_name=script_name)
                    file_copy_enable = _file_copy_enable
                    file_copy_source = _file_copy_source
                    file_copy_dest = _file_copy_dest
                except (KeyNotInListError, BadValueInListError):
                    pass
            except KeyNotInListError:
                pass
            except BadValueInListError:
                printc.note("Value \"" + str(_file_copy_enable) + "\" for key \"" + 'file_copy_enable' + "\"" + ", inside list \"" + parent + "\"," + " in \"" + settings_filename + "\" is of type \"" + _file_copy_enable.__class__.__name__ + "\" while it should be of type \"bool\". Using default values instead.", script_name)
        
        # Define user accessible variables
        variables = Variables(
            tool_install_path=os.path.realpath(install_path),
            odatix_path=OdatixSettings.odatix_path,
            odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
        )

        # Replace variables in command
        file_copy_source = replace_variables(file_copy_source, variables)

        # Constraint files: what the target file declares for this target, then
        # what the architecture declares for every job and in each rule matching
        # this one. All of them add up -- a design does not stop needing its
        # timing exceptions because the board it runs on has a pinout.
        try:
            job_constraints = list(target_constraints) if target_constraints else []
            job_constraints += constraints_lib.read_constraints(settings_data, settings_filename, variables)
            for index, override in enumerate(job_overrides):
                job_constraints += constraints_lib.read_constraints(
                    override, settings_filename, variables,
                    parent=overrides_lib.OVERRIDES_KEY + "[" + str(index) + "]",
                )
            job_constraints = constraints_lib.resolve(job_constraints)
        except ConstraintFileError as error:
            printc.error(str(error), script_name)
            self.banned_arch_param.append(arch_param_dir)
            self.plan.add(arch_display_name, Category.ERROR)
            return None

        # check file copy
        if file_copy_enable:
            if not isfile(file_copy_source):
                printc.error("The source file to copy \"" + file_copy_source + "\" does not exist", script_name)
                self.banned_arch_param.append(arch_param_dir)
                self.plan.add(arch_display_name, Category.ERROR)
                return None

        # passed all check: added to the list
        if run_mode in ["default", "fmax"]:
            self.valid_archs.append(arch_display_name)
            self.checked_arch_param.append(arch_param_dir)

        lib_name = "LIB_" + target + "_" + arch_param_dir_work + "_" + arch_config_dir_work

        tmp_script_path = os.path.join(tmp_dir, self.work_script_path)
        tmp_report_path = os.path.join(tmp_dir, self.work_report_path)
        tmp_log_path = os.path.join(tmp_dir, self.work_log_path)

        arch_instance = Architecture(
            virtual_param_domains=virtual_param_domains,
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
            log_path=tmp_log_path,
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
            constraint_files=job_constraints,
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
                        self.plan.add(arch_display_name, Category.ERROR)
                    return None, None, None, None

        return use_parameters, start_delimiter, stop_delimiter, param_target_filename

    @staticmethod
    def get_frequency_settings(arch_config, target, settings_data, settings_filename, run_mode, fallback_custom_freq_list=None, tool="", flow=""):
        """
        Retrieves frequency synthesis settings from the YAML configuration.

        Which level of the settings file has the last word is the workspace
        API's business (odatix.workspace.architectures.resolve_frequencies), so
        that a script asking an architecture what it runs at gets the same
        answer as a run. What is left here is the flat tuple the run flows use.

        Args:
                arch_config (str): The architecture configuration.
                target (str): The target FPGA/ASIC.
                settings_data (dict): The parsed YAML settings data.
                settings_filename (str): Name of the YAML file.
                run_mode (str): The mode of operation (e.g., "fmax", "custom_freq").
                fallback_custom_freq_list (list, optional): A fallback list of custom frequencies to use instead of default values.
                tool (str, optional): The EDA tool running the jobs, which a rule of the "overrides" section can select.
                flow (str, optional): The flow of that tool the jobs run.

        Returns:
                tuple: (fmax_lower_bound, fmax_upper_bound, custom_freq_list, warn_fmax_obsolete).
        """
        resolved = workspace_architectures.resolve_frequencies(
            settings_data,
            target=target,
            configuration=arch_config,
            tool=tool,
            flow=flow,
            mode=run_mode,
            fallback=fallback_custom_freq_list,
        )
        printc.messages(resolved.messages, script_name)

        if run_mode == "custom_freq":
            return None, None, resolved.frequencies, resolved.deprecated_bounds
        return resolved.lower_bound, resolved.upper_bound, None, resolved.deprecated_bounds

    @staticmethod
    def configuration_wildcard(full_architectures, arch_path=OdatixSettings.DEFAULT_ARCH_PATH, target=""):
        """
        Expand the wildcards of a job selection against what is on disk.

        The expansion itself lives in odatix.workspace.selection, and is what
        the architectures, the workflows and the simulations all go through.
        Here it only gets said out loud.
        """
        messages = []
        architectures = selection.expand(full_architectures, arch_path, messages=messages)
        printc.messages(messages, script_name)
        return architectures

    def create_list_from_range(lower_bound, upper_bound, step):
        return list(range(lower_bound, upper_bound + 1, step))

    def check_bounds(lower_bound, upper_bound, step=0, synth_type="fmax synthesis"):
        """Whether a frequency range can be run, saying what is wrong with it."""
        messages = workspace_architectures.check_bounds(lower_bound, upper_bound, step, kind=synth_type)
        printc.messages(messages, script_name)
        return not messages

    def print_summary(self):
        self.plan.print_summary(noun="architectures")

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

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
import argparse

from odatix.components.replace_params import replace_params
from odatix.components.run_common import (
    normalize_run_settings,
    confirm_valid_jobs,
    replace_and_write_param_domains,
    start_parallel_jobs as start_parallel_jobs_common,
)
import odatix.components.export_workflow_results as exp_workflow_res
import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.config_generator import ConfigGenerator
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.settings import OdatixSettings
from odatix.lib.architecture_handler import ArchitectureHandler
from odatix.lib.param_domain import ParamDomain
from odatix.lib.utils import read_from_list, copytree, create_dir, ask_to_continue, get_timestamp_string, KeyNotInListError, BadValueInListError
from odatix.lib.run_settings import get_workflow_settings
from odatix.lib.wosit import createTaskGraph

script_name = os.path.basename(__file__)
WORKFLOW_META_FILENAME = "workflow_meta.yml"
WORKFLOW_COMMAND_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
WORKFLOW_VIRTUAL_DOMAIN_SAFE_VALUE_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")


class WorkflowInstance:
    def __init__(
        self,
        workflow_name,
        workflow_display_name,
        workflow_full,
        workflow_param_dir,
        workflow_config,
        tmp_dir,
        source_path,
        source_whitelist,
        source_blacklist,
        param_target_file,
        start_delimiter,
        stop_delimiter,
        param_file,
        param_domains,
        progress_file,
        tasks,
        workflow_settings_file,
        workflow_definition_dir,
        no_main_configuration=False,
        use_parameters=True,
        extra_command_substitutions=None,
    ):
        self.workflow_name = workflow_name
        self.workflow_display_name = workflow_display_name
        self.workflow_full = workflow_full
        self.workflow_param_dir = workflow_param_dir
        self.workflow_config = workflow_config
        self.tmp_dir = tmp_dir
        self.source_path = source_path
        self.source_whitelist = source_whitelist
        self.source_blacklist = source_blacklist
        self.param_target_file = param_target_file
        self.start_delimiter = start_delimiter
        self.stop_delimiter = stop_delimiter
        self.param_file = param_file
        self.param_domains = param_domains
        self.progress_file = progress_file
        self.tasks = tasks
        self.workflow_settings_file = workflow_settings_file
        self.workflow_definition_dir = workflow_definition_dir
        self.no_main_configuration = no_main_configuration
        self.use_parameters = use_parameters
        self.extra_command_substitutions = (
            dict(extra_command_substitutions) if isinstance(extra_command_substitutions, dict) else {}
        )


def _read_command_parameter_value(param_file):
    if param_file is None or not os.path.isfile(param_file):
        return None

    with open(param_file, "r") as f:
        content = f.read().strip()

    if content == "":
        return ""

    # Commands are single-line shell entries, so multi-line values are folded.
    if "\n" in content:
        return " ".join(line.strip() for line in content.splitlines() if line.strip() != "")

    return content


def _build_workflow_command_substitutions(workflow_instance):
    substitutions = {}

    if isinstance(workflow_instance.extra_command_substitutions, dict):
        for key, value in workflow_instance.extra_command_substitutions.items():
            substitutions[str(key)] = str(value)

    if workflow_instance.param_file is not None:
        main_value = _read_command_parameter_value(workflow_instance.param_file)
        if main_value is not None:
            substitutions[workflow_instance.workflow_param_dir] = main_value

    for param_domain in workflow_instance.param_domains:
        value = _read_command_parameter_value(param_domain.param_file)
        if value is not None:
            substitutions[param_domain.domain] = value

    return substitutions


def _sanitize_virtual_param_domain_value(value):
    value = str(value).strip()
    if value == "":
        return "_"
    sanitized = WORKFLOW_VIRTUAL_DOMAIN_SAFE_VALUE_PATTERN.sub("_", value)
    if sanitized == "":
        return "_"
    return sanitized


def get_workflow_virtual_domain_names(workflow_settings):
    if not isinstance(workflow_settings, dict):
        return set()
    generate_settings = workflow_settings.get("generate_configurations_settings")
    if not isinstance(generate_settings, dict):
        return set()
    variables = generate_settings.get("variables")
    if not isinstance(variables, dict):
        return set()
    return set(name for name in variables.keys() if isinstance(name, str) and name.strip() != "")


def _normalize_workflow_requests_for_virtual_domain_wildcards(workflow_requests, workflow_path, debug=False):
    """
    Normalize workflow requests before wildcard expansion.

    If a request uses only virtual-domain wildcards (for example
    workflow_name + var/* + other/*), strip these selectors so the generic
    wildcard resolver does not expect physical parameter-domain directories.
    """
    normalized_requests = []
    for request in workflow_requests:
        (
            workflow,
            workflow_param_dir,
            _workflow_config,
            _workflow_display_name,
            _workflow_param_dir_work,
            _workflow_config_dir_work,
            requested_param_domains,
        ) = ArchitectureHandler.get_basic(request)

        if len(requested_param_domains) == 0:
            normalized_requests.append(request)
            continue

        workflow_settings_file = os.path.join(workflow_path, workflow_param_dir, hard_settings.param_settings_filename)
        if not os.path.isfile(workflow_settings_file):
            normalized_requests.append(request)
            continue

        try:
            with open(workflow_settings_file, "r") as f:
                workflow_settings = yaml.load(f, Loader=yaml.loader.SafeLoader)
        except Exception:
            normalized_requests.append(request)
            continue

        virtual_domain_names = get_workflow_virtual_domain_names(workflow_settings)
        if len(virtual_domain_names) == 0:
            normalized_requests.append(request)
            continue

        dropped_virtual_wildcards = False
        kept_param_domains = []
        for requested_param_domain in requested_param_domains:
            domain = re.sub('/.*', '', requested_param_domain)
            value = re.sub('.*/', '', requested_param_domain)
            if domain in virtual_domain_names and value == "*":
                dropped_virtual_wildcards = True
                continue
            kept_param_domains.append(requested_param_domain)

        if dropped_virtual_wildcards:
            normalized_request = workflow
            if len(kept_param_domains) > 0:
                normalized_request = workflow + "+" + "+".join(kept_param_domains)
            if debug:
                printc.note(
                    "Using generated workflow variables for wildcard selector(s) in request \""
                    + request
                    + "\".",
                    script_name,
                )
            normalized_requests.append(normalized_request)
        else:
            normalized_requests.append(request)

    return normalized_requests


def build_workflow_virtual_param_domain_variants(workflow_settings, workflow_settings_file, debug=False):
    """
    Build workflow variants from generate_configurations_settings.variables.

    Variants are only generated when generate_configurations is not enabled.
    This preserves the existing meaning of generate_configurations while
    allowing variable-based command placeholders to emulate parameter domains.
    """
    generate_enabled = bool(workflow_settings.get("generate_configurations", False))
    if generate_enabled:
        return []

    generate_settings = workflow_settings.get("generate_configurations_settings")
    if not isinstance(generate_settings, dict):
        return []

    variables = generate_settings.get("variables")
    if not isinstance(variables, dict) or len(variables) == 0:
        return []

    variable_names = [name for name in variables.keys() if isinstance(name, str) and name.strip() != ""]
    if len(variable_names) == 0:
        printc.error(
            "Invalid workflow variable settings in \""
            + workflow_settings_file
            + "\": no valid variable names found in \"generate_configurations_settings.variables\".",
            script_name,
        )
        return None

    synthetic_template = "\n".join([f"{variable_name}: ${{{variable_name}}}" for variable_name in variable_names])
    synthetic_name = "__workflow_virtual__" + "__".join([f"${{{variable_name}}}" for variable_name in variable_names])

    generator_data = {
        "generate_configurations": True,
        "generate_configurations_settings": {
            "template": synthetic_template,
            "name": synthetic_name,
            "variables": variables,
        },
    }

    generator = ConfigGenerator(data=generator_data, silent=True, debug=debug)
    if not generator.valid:
        printc.error(
            "Invalid \"generate_configurations_settings.variables\" in workflow settings file \""
            + workflow_settings_file
            + "\".",
            script_name,
        )
        return None

    generated = generator.generate()
    if not isinstance(generated, tuple) or len(generated) != 2:
        printc.error(
            "Could not generate workflow variable combinations from \""
            + workflow_settings_file
            + "\".",
            script_name,
        )
        return None

    generated_params, _all_values = generated
    if not isinstance(generated_params, dict):
        printc.error(
            "Could not generate workflow variable combinations from \""
            + workflow_settings_file
            + "\".",
            script_name,
        )
        return None

    variants = []
    for rendered_values in generated_params.values():
        try:
            parsed_values = yaml.load(rendered_values, Loader=yaml.loader.BaseLoader)
        except yaml.YAMLError as e:
            printc.error(
                "Could not parse generated workflow variables from \""
                + workflow_settings_file
                + "\": "
                + str(e),
                script_name,
            )
            return None

        if not isinstance(parsed_values, dict):
            printc.error(
                "Could not parse generated workflow variables from \""
                + workflow_settings_file
                + "\": generated values are not a mapping.",
                script_name,
            )
            return None

        substitutions = {}
        requested_param_domains = []

        for variable_name in variable_names:
            raw_value = parsed_values.get(variable_name, "")
            value = str(raw_value).strip() if raw_value is not None else ""
            substitutions[variable_name] = value

            variable_cfg = variables.get(variable_name, {})
            unit = ""
            if isinstance(variable_cfg, dict):
                unit_value = variable_cfg.get("unit", "")
                if unit_value is not None:
                    unit = str(unit_value)

            display_value = value + unit if unit != "" else value
            requested_param_domains.append(variable_name + "/" + _sanitize_virtual_param_domain_value(display_value))

        variants.append(
            {
                "requested_param_domains": requested_param_domains,
                "substitutions": substitutions,
            }
        )

    if debug and len(variants) > 0:
        printc.note(
            "Generated "
            + str(len(variants))
            + " workflow variants from \"generate_configurations_settings.variables\" in \""
            + workflow_settings_file
            + "\".",
            script_name,
        )

    return variants


def _replace_workflow_command_vars(value, substitutions):
    if not isinstance(value, str) or len(substitutions) == 0:
        return value

    def _replace_var(match):
        var_name = match.group(1)
        return substitutions.get(var_name, match.group(0))

    return WORKFLOW_COMMAND_VAR_PATTERN.sub(_replace_var, value)


def _resolve_workflow_tasks(tasks, substitutions):
    if len(substitutions) == 0:
        return tasks

    resolved_tasks = []
    for task in tasks:
        if not isinstance(task, dict):
            resolved_tasks.append(task)
            continue

        resolved_task = dict(task)

        commands = resolved_task.get("commands")
        if isinstance(commands, list):
            resolved_task["commands"] = [_replace_workflow_command_vars(command, substitutions) for command in commands]

        task_path = resolved_task.get("path")
        if isinstance(task_path, str):
            resolved_task["path"] = _replace_workflow_command_vars(task_path, substitutions)

        resolved_tasks.append(resolved_task)

    return resolved_tasks


def _parse_workflow_task_platforms(platforms_value, task_name):
    if isinstance(platforms_value, str):
        platforms = [platforms_value.strip()]
    elif isinstance(platforms_value, (list, tuple, set)):
        platforms = []
        for value in platforms_value:
            if not isinstance(value, str):
                raise ValueError(
                    "Task \"{}\" has an invalid \"platforms\" entry. "
                    "Expected strings, got {}.".format(task_name, type(value).__name__)
                )
            stripped = value.strip()
            if stripped != "":
                platforms.append(stripped)
    else:
        raise ValueError(
            "Task \"{}\" has an invalid \"platforms\" value of type {}. "
            "Expected a string or a list of strings.".format(task_name, type(platforms_value).__name__)
        )

    platforms = [platform for platform in platforms if platform != ""]
    if len(platforms) == 0:
        raise ValueError("Task \"{}\" has an empty \"platforms\" value.".format(task_name))

    return platforms


def _select_platform_task_implementations(tasks, current_platform):
    grouped_tasks = {}
    ordered_task_names = []

    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Each task must be a mapping/object in \"tasks\".")

        task_name = task.get("name")
        if not isinstance(task_name, str) or task_name.strip() == "":
            raise ValueError("Each task must have a non-empty \"name\" key.")
        task_name = task_name.strip()

        if task_name not in grouped_tasks:
            grouped_tasks[task_name] = []
            ordered_task_names.append(task_name)

        grouped_tasks[task_name].append(task)

    selected_tasks = []
    for task_name in ordered_task_names:
        candidates = grouped_tasks[task_name]
        default_implementations = []
        matching_platform_implementations = []

        for candidate in candidates:
            has_platforms_key = "platforms" in candidate and candidate.get("platforms") not in (None, False, "")
            has_legacy_platform_key = "platform" in candidate and candidate.get("platform") not in (None, False, "")

            if has_platforms_key and has_legacy_platform_key:
                raise ValueError(
                    "Task \"{}\" defines both \"platform\" and \"platforms\". "
                    "Please keep only \"platforms\".".format(task_name)
                )

            if not has_platforms_key and not has_legacy_platform_key:
                default_implementations.append(candidate)
                continue

            platforms_value = candidate.get("platforms") if has_platforms_key else candidate.get("platform")
            platforms = _parse_workflow_task_platforms(platforms_value, task_name)
            if current_platform in platforms:
                matching_platform_implementations.append(candidate)

        if len(default_implementations) > 1:
            raise ValueError(
                "Task \"{}\" has more than one default implementation "
                "(without \"platforms\").".format(task_name)
            )

        if len(matching_platform_implementations) > 1:
            raise ValueError(
                "Task \"{}\" has more than one implementation matching platform \"{}\".".format(
                    task_name, current_platform
                )
            )

        selected_task = None
        if len(matching_platform_implementations) == 1:
            selected_task = matching_platform_implementations[0]
        elif len(default_implementations) == 1:
            selected_task = default_implementations[0]

        if selected_task is None:
            continue

        selected_task = dict(selected_task)
        selected_task.pop("platforms", None)
        selected_task.pop("platform", None)
        selected_tasks.append(selected_task)

    return selected_tasks


def _validate_selected_workflow_tasks(tasks, current_platform):
    task_names = set()
    for task in tasks:
        task_name = task.get("name")
        if isinstance(task_name, str) and task_name.strip() != "":
            task_names.add(task_name.strip())

    if "main" not in task_names:
        raise ValueError(
            "No implementation selected for task \"main\" on platform \"{}\". "
            "Define matching \"platforms\" values or a default implementation without \"platforms\".".format(
                current_platform
            )
        )

    missing_dependencies = []
    for task in tasks:
        task_name = task.get("name", "<unknown>")
        dependencies = task.get("dependencies", [])

        if isinstance(dependencies, str):
            dependencies = [dependencies]

        if not isinstance(dependencies, list):
            continue

        for dependency in dependencies:
            if isinstance(dependency, str) and dependency not in task_names:
                missing_dependencies.append((task_name, dependency))

    if len(missing_dependencies) > 0:
        missing_dependencies = sorted(set(missing_dependencies))
        formatted_missing_dependencies = ", ".join(
            ["\"{}\" -> \"{}\"".format(task_name, dependency) for task_name, dependency in missing_dependencies]
        )
        raise ValueError(
            "Some dependencies reference tasks that are not selected for platform \"{}\": {}".format(
                current_platform, formatted_missing_dependencies
            )
        )



def _expand_env_tokens(path):
    if not isinstance(path, str):
        return path

    def _replace_env(match):
        env_name = match.group(1)
        return os.environ.get(env_name, "")

    expanded = re.sub(r"\$env\(([^)]+)\)", _replace_env, path)
    expanded = os.path.expandvars(expanded)
    expanded = os.path.expanduser(expanded)
    return expanded


######################################
# Parse Arguments
######################################

def add_arguments(parser):
    parser.add_argument('-o', '--overwrite', action='store_true', help='overwrite existing results')
    parser.add_argument('-y', '--noask', action='store_true', help='do not ask to continue')
    parser.add_argument('-d', '--detach', action='store_true', help='enqueue jobs to daemon and return without attaching monitor')
    parser.add_argument('-S', '--session', help='daemon session name or selector')
    parser.add_argument('-i', '--input', help='input settings file')
    parser.add_argument('-p', '--workflowpath', help='workflow directory')
    parser.add_argument('-w', '--work', help='workflow work directory')
    parser.add_argument("-E", "--exit", action="store_true", help="exit monitor when all jobs are done")
    parser.add_argument("-j", "--jobs", help="maximum number of parallel jobs")
    parser.add_argument("-k", "--keep", action="store_true", help="store workflow batch with a timestamp in the configuration name")
    parser.add_argument("-r", "--resume", action="store_true", help="resume from existing work directories (do not delete/recreate them)")
    parser.add_argument("--logsize", help="size of the log history per job in the monitor")
    parser.add_argument("-D", "--debug", action="store_true", help="enable debug mode to help troubleshoot settings files")
    parser.add_argument('-c', '--config', default=OdatixSettings.DEFAULT_SETTINGS_FILE, help='global settings file for Odatix (default: ' + OdatixSettings.DEFAULT_SETTINGS_FILE + ')')


def parse_arguments():
    parser = argparse.ArgumentParser(description='Run parallel workflows')
    add_arguments(parser)
    return parser.parse_args()


######################################
# Run Workflows
######################################

def run_workflows(
    run_config_settings_filename,
    workflow_path,
    work_path,
    overwrite,
    noask,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    debug=False,
    keep=False,
    resume=False,
    output_dir=None,
    output_filename=exp_workflow_res.DEFAULT_OUTPUT_FILENAME,
    detach=False,
    daemon_session=None,
):
    workflow_instances, prepare_job, job_list, exit_when_done, log_size_limit, nb_jobs = check_settings(
        run_config_settings_filename=run_config_settings_filename,
        workflow_path=workflow_path,
        work_path=work_path,
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        debug=debug,
        keep=keep,
    )
    parallel_jobs = prepare_workflows(
        workflow_instances=workflow_instances,
        prepare_job=prepare_job,
        job_list=job_list,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        resume=resume,
    )

    exp_workflow_res.configure_workflow_job_exports(
        parallel_jobs=parallel_jobs,
        work_root=work_path,
        workflow_path=workflow_path,
        output_dir=output_dir,
        output_filename=output_filename,
    )

    start_parallel_jobs(parallel_jobs, detach=detach, session=daemon_session)


def check_settings(
    run_config_settings_filename,
    workflow_path,
    work_path,
    overwrite,
    noask,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    debug=False,
    keep=False,
):
    _overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs, workflows = get_workflow_settings(run_config_settings_filename)

    if workflows is None:
        printc.error('The "workflows" section of "' + run_config_settings_filename + '" is empty.', script_name)
        printc.note('You must define your workflows in "' + run_config_settings_filename + '" before using this command.', script_name)
        sys.exit(-1)

    overwrite, ask_continue, exit_when_done, log_size_limit, nb_jobs = normalize_run_settings(
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        defaults=(_overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs),
    )

    if not isinstance(workflows, list):
        printc.error('The "workflows" key in "' + run_config_settings_filename + '" must be a list.', script_name)
        sys.exit(-1)

    workflow_requests = [item for item in workflows if isinstance(item, str) and item.strip() != ""]
    workflow_requests = _normalize_workflow_requests_for_virtual_domain_wildcards(
        workflow_requests=workflow_requests,
        workflow_path=workflow_path,
        debug=debug,
    )
    expanded_workflows = ArchitectureHandler.configuration_wildcard(workflow_requests, arch_path=workflow_path)

    if expanded_workflows is None:
        printc.error("Could not expand workflow list. Please check wildcard and parameter domain definitions.", script_name)
        sys.exit(-1)

    timestamp = get_timestamp_string()

    valid_workflows = []
    invalid_workflows = []
    workflow_instances = []

    first_progress_regex = None

    for workflow_full in expanded_workflows:
        (
            workflow,
            workflow_param_dir,
            workflow_config,
            workflow_display_name,
            workflow_param_dir_work,
            workflow_config_dir_work,
            requested_param_domains,
        ) = ArchitectureHandler.get_basic(workflow_full)

        # If no explicit config is provided (e.g. "workflow_simple" instead of
        # "workflow_simple/default"), treat it as the main/default configuration
        # and skip main parameter replacement.
        no_main_configuration = workflow_config == workflow_param_dir

        workflow_settings_file = os.path.join(workflow_path, workflow_param_dir, hard_settings.param_settings_filename)

        if not os.path.isfile(workflow_settings_file):
            printc.error("Workflow settings file \"" + workflow_settings_file + "\" does not exist", script_name)
            invalid_workflows.append(workflow_display_name)
            continue

        with open(workflow_settings_file, "r") as f:
            try:
                workflow_settings = yaml.load(f, Loader=yaml.loader.SafeLoader)
            except Exception as e:
                printc.error("Workflow settings file \"" + workflow_settings_file + "\" is not a valid YAML file", script_name)
                printc.cyan("error details: ", end="", script_name=script_name)
                print(str(e))
                invalid_workflows.append(workflow_display_name)
                continue

        try:
            sources = read_from_list("sources", workflow_settings, workflow_settings_file, type=dict, script_name=script_name)
            source_path = read_from_list("path", sources, workflow_settings_file, parent="sources", script_name=script_name)
            source_path = os.path.realpath(str(_expand_env_tokens(source_path)))
            if not os.path.isdir(source_path):
                printc.error("The sources.path \"" + source_path + "\" does not exist", script_name)
                invalid_workflows.append(workflow_display_name)
                continue

            source_whitelist = read_from_list("whitelist", sources, workflow_settings_file, parent="sources", optional=True, raise_if_missing=False, print_error=False)
            source_blacklist = read_from_list("blacklist", sources, workflow_settings_file, parent="sources", optional=True, raise_if_missing=False, print_error=False)
            if source_whitelist is False:
                source_whitelist = None
            if source_blacklist is False:
                source_blacklist = None

            # Check if use_parameters is explicitly set to False
            use_parameters = workflow_settings.get("use_parameters", True)

            if use_parameters:
                param_target_file = read_from_list("param_target_file", workflow_settings, workflow_settings_file, script_name=script_name)
                start_delimiter = read_from_list("start_delimiter", workflow_settings, workflow_settings_file, script_name=script_name)
                stop_delimiter = read_from_list("stop_delimiter", workflow_settings, workflow_settings_file, script_name=script_name)
            else:
                param_target_file = None
                start_delimiter = None
                stop_delimiter = None

            tasks = read_from_list("tasks", workflow_settings, workflow_settings_file, type=list, script_name=script_name)
        except (KeyNotInListError, BadValueInListError):
            invalid_workflows.append(workflow_display_name)
            continue

        progress_file = hard_settings.sim_progress_filename
        progress_regex = hard_settings.sim_status_pattern.pattern
        try:
            progress = read_from_list("progress", workflow_settings, workflow_settings_file, type=dict, optional=True, raise_if_missing=False, print_error=False)
            if progress not in (False, None):
                progress_file = read_from_list("file", progress, workflow_settings_file, parent="progress", optional=True, raise_if_missing=False, print_error=False)
                progress_regex = read_from_list("regex", progress, workflow_settings_file, parent="progress", optional=True, raise_if_missing=False, print_error=False)
                if progress_file in (False, None):
                    progress_file = hard_settings.sim_progress_filename
                if progress_regex in (False, None):
                    progress_regex = hard_settings.sim_status_pattern.pattern
        except (KeyNotInListError, BadValueInListError):
            progress_file = hard_settings.sim_progress_filename
            progress_regex = hard_settings.sim_status_pattern.pattern

        if first_progress_regex is None:
            first_progress_regex = progress_regex
        elif first_progress_regex != progress_regex:
            printc.note(
                "Multiple progress.regex values detected. Using the first one for monitor parsing: \"" + first_progress_regex + "\"",
                script_name,
            )

        param_file = os.path.join(workflow_path, workflow_param_dir, workflow_config + ".txt")
        if use_parameters and not no_main_configuration and not os.path.isfile(param_file):
            printc.error("Workflow parameter file \"" + param_file + "\" does not exist", script_name)
            invalid_workflows.append(workflow_display_name)
            continue
        if no_main_configuration or not use_parameters:
            param_file = None

        virtual_domain_names = get_workflow_virtual_domain_names(workflow_settings)
        requested_physical_param_domains = []
        requested_virtual_param_domains = []
        for requested_param_domain in requested_param_domains:
            domain = re.sub('/.*', '', requested_param_domain)
            if domain in virtual_domain_names:
                requested_virtual_param_domains.append(requested_param_domain)
            else:
                requested_physical_param_domains.append(requested_param_domain)

        param_domains = []
        if len(requested_physical_param_domains) > 0:
            param_domains = ParamDomain.get_param_domains(
                requested_param_domains=requested_physical_param_domains,
                architecture=workflow_param_dir,
                arch_path=workflow_path,
                param_settings_filename=hard_settings.param_settings_filename,
                top_level_file=workflow_settings_file,
            )
            if param_domains is None:
                invalid_workflows.append(workflow_display_name)
                continue

        virtual_param_domain_variants = [{"requested_param_domains": [], "substitutions": {}}]
        if len(virtual_domain_names) > 0:
            generated_virtual_variants = build_workflow_virtual_param_domain_variants(
                workflow_settings=workflow_settings,
                workflow_settings_file=workflow_settings_file,
                debug=debug,
            )
            if generated_virtual_variants is None:
                invalid_workflows.append(workflow_display_name)
                continue

            if len(requested_virtual_param_domains) > 0:
                filtered_virtual_variants = []
                for virtual_variant in generated_virtual_variants:
                    variant_domains = set(virtual_variant.get("requested_param_domains", []))
                    keep_variant = True
                    for requested_virtual_domain in requested_virtual_param_domains:
                        domain = re.sub('/.*', '', requested_virtual_domain)
                        value = re.sub('.*/', '', requested_virtual_domain)
                        if value == "*":
                            continue
                        if (domain + "/" + value) not in variant_domains:
                            keep_variant = False
                            break
                    if keep_variant:
                        filtered_virtual_variants.append(virtual_variant)

                if len(filtered_virtual_variants) == 0:
                    printc.error(
                        "No workflow variable combination matches selector(s) for workflow \""
                        + workflow_display_name
                        + "\".",
                        script_name,
                    )
                    param_domain = re.sub('/.*', '', requested_virtual_param_domains[0])
                    param_domain_value = re.sub('.*/', '', requested_virtual_param_domains[0])
                    printc.tip("Add a parameter-domain config file \"" + param_domain_value + ".txt\" in \"" + os.path.join(workflow_param_dir, param_domain) + "\" ", script_name)
                    printc.magenta("or add a variable \"" + param_domain + "\" generating the value \"" + param_domain_value + "\" to the workflow settings file \"" + workflow_settings_file + "\".")
                    invalid_workflows.append(workflow_display_name)
                    continue

                virtual_param_domain_variants = filtered_virtual_variants
            elif len(requested_param_domains) == 0:
                if len(generated_virtual_variants) > 0:
                    virtual_param_domain_variants = generated_virtual_variants

        for virtual_variant in virtual_param_domain_variants:
            variant_requested_param_domains = requested_physical_param_domains + list(
                virtual_variant.get("requested_param_domains", [])
            )

            workflow_full_variant = workflow
            if len(variant_requested_param_domains) > 0:
                workflow_full_variant = workflow + "+" + "+".join(variant_requested_param_domains)

            (
                _workflow_variant,
                _workflow_param_dir_variant,
                _workflow_config_variant,
                workflow_display_name_variant,
                workflow_param_dir_work_variant,
                workflow_config_dir_work_variant,
                _variant_domains,
            ) = ArchitectureHandler.get_basic(workflow_full_variant)

            workflow_config_dir_work_variant = (
                workflow_config_dir_work_variant + "_" + timestamp if keep and timestamp != "" else workflow_config_dir_work_variant
            )
            tmp_dir = os.path.join(work_path, workflow_param_dir_work_variant, workflow_config_dir_work_variant)

            workflow_instances.append(
                WorkflowInstance(
                    workflow_name=workflow,
                    workflow_display_name=workflow_display_name_variant,
                    workflow_full=workflow_full_variant,
                    workflow_param_dir=workflow_param_dir,
                    workflow_config=workflow_config,
                    tmp_dir=tmp_dir,
                    source_path=source_path,
                    source_whitelist=source_whitelist,
                    source_blacklist=source_blacklist,
                    param_target_file=param_target_file,
                    start_delimiter=start_delimiter,
                    stop_delimiter=stop_delimiter,
                    param_file=param_file,
                    param_domains=param_domains,
                    progress_file=progress_file,
                    tasks=tasks,
                    workflow_settings_file=workflow_settings_file,
                    workflow_definition_dir=os.path.join(workflow_path, workflow_param_dir),
                    no_main_configuration=no_main_configuration,
                    use_parameters=use_parameters,
                    extra_command_substitutions=virtual_variant.get("substitutions", {}),
                )
            )
            valid_workflows.append(workflow_display_name_variant)

    if first_progress_regex is None:
        first_progress_regex = hard_settings.sim_status_pattern.pattern

    ParallelJob.set_patterns(re.compile(first_progress_regex))

    if len(valid_workflows) > 0:
        print()
        printc.bold("Valid workflows:")
        for wf in valid_workflows:
            print("  - " + wf)
    if len(invalid_workflows) > 0:
        print()
        printc.bold("Invalid workflows (skipped):")
        for wf in invalid_workflows:
            printc.red("  - " + wf)
        printc.endc()

    confirm_valid_jobs(len(valid_workflows), ask_continue, ask_to_continue, script_name=script_name)

    print()

    job_list = []

    def prepare_job(workflow_instance, resume=False):
        if not (resume and os.path.isdir(workflow_instance.tmp_dir)):
            create_dir(workflow_instance.tmp_dir)

        # Write run metadata to make post-processing/export robust.
        workflow_meta_file = os.path.join(workflow_instance.tmp_dir, WORKFLOW_META_FILENAME)
        try:
            with open(workflow_meta_file, "w") as f:
                yaml.dump(
                    {
                        "workflow_full": workflow_instance.workflow_full,
                        "workflow_name": workflow_instance.workflow_name,
                        "workflow_display_name": workflow_instance.workflow_display_name,
                        "workflow_param_dir": workflow_instance.workflow_param_dir,
                        "workflow_config": workflow_instance.workflow_config,
                        "workflow_definition_dir": workflow_instance.workflow_definition_dir,
                        "workflow_settings_file": workflow_instance.workflow_settings_file,
                    },
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                )
        except Exception as e:
            printc.warning(
                "Could not write workflow metadata file \""
                + workflow_meta_file
                + "\": "
                + str(e),
                script_name,
            )

        # copy source files
        copytree(
            src=workflow_instance.source_path,
            dst=workflow_instance.tmp_dir,
            whitelist=workflow_instance.source_whitelist,
            blacklist=workflow_instance.source_blacklist,
            dirs_exist_ok=True,
        )

        # replace main parameters (skip when no explicit main configuration is selected)
        if workflow_instance.use_parameters and not workflow_instance.no_main_configuration:
            if debug:
                printc.subheader("Replace main parameters")

            param_target_file = os.path.join(workflow_instance.tmp_dir, workflow_instance.param_target_file)
            replace_params(
                base_text_file=param_target_file,
                replacement_text_file=workflow_instance.param_file,
                output_file=param_target_file,
                start_delimiter=workflow_instance.start_delimiter,
                stop_delimiter=workflow_instance.stop_delimiter,
                replace_all_occurrences=False,
                silent=False if debug else True,
            )

        # replace domain parameters and write param_domains.yml
        replace_and_write_param_domains(
            tmp_dir=workflow_instance.tmp_dir,
            arch_name=workflow_instance.workflow_full,
            param_domains=workflow_instance.param_domains,
            default_target_filename=workflow_instance.param_target_file,
            target_filename_getter=lambda param_domain: param_domain.param_target_file,
            debug=debug,
            timestamp=None,
        )

        selected_tasks = _select_platform_task_implementations(workflow_instance.tasks, sys.platform)

        substitutions = _build_workflow_command_substitutions(workflow_instance)
        resolved_tasks = _resolve_workflow_tasks(selected_tasks, substitutions)
        _validate_selected_workflow_tasks(resolved_tasks, sys.platform)

        try:
            maker = createTaskGraph(resolved_tasks)
            old_cwd = os.getcwd()
            try:
                os.chdir(workflow_instance.tmp_dir)
                execution_stages = maker.getStages(name="main", max_process=1)
            finally:
                os.chdir(old_cwd)
        except Exception as e:
            printc.error("Error while creating task graph for workflow \"" + workflow_instance.workflow_display_name + "\". Please check your workflow settings file and task definitions.", script_name)
            printc.cyan("error details: ", end="", script_name=script_name)
            print(str(e))
            sys.exit(-1)

        if execution_stages is None or len(execution_stages) == 0:
            printc.error("Failed to generate execution stages for workflow \"" + workflow_instance.workflow_display_name + "\". Please check your workflow settings file and task definitions.", script_name)
            sys.exit(-1)

        progress_file = os.path.join(workflow_instance.tmp_dir, workflow_instance.progress_file)

        running_workflow = ParallelJob(
            process=None,
            command=execution_stages,
            directory=workflow_instance.tmp_dir,
            generate_rtl=False,
            generate_command="",
            target="",
            arch="",
            display_name=workflow_instance.workflow_display_name,
            status_file="",
            progress_file=progress_file,
            tmp_dir=workflow_instance.tmp_dir,
            log_size_limit=log_size_limit,
            status="idle",
        )

        job_list.append(running_workflow)

    return workflow_instances, prepare_job, job_list, exit_when_done, log_size_limit, nb_jobs


def prepare_workflows(
    workflow_instances,
    prepare_job,
    job_list,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    resume=False,
):
    for workflow_instance in workflow_instances:
        prepare_job(workflow_instance, resume=resume)

    parallel_jobs = ParallelJobHandler(
        job_list=job_list,
        nb_jobs=nb_jobs,
        process_group=True,
        auto_exit=exit_when_done,
        log_size_limit=log_size_limit,
    )
    return parallel_jobs


def start_parallel_jobs(
    parallel_jobs,
    use_api=True,
    start_headless_on_startup=False,
    detach=False,
    session=None,
):
    start_parallel_jobs_common(
        parallel_jobs=parallel_jobs,
        use_api=use_api,
        start_headless_on_startup=start_headless_on_startup,
        detach=detach,
        session=session,
    )


######################################
# Main
######################################

def main(args, settings=None):

    if settings is None:
        settings = OdatixSettings(args.config)
        if not settings.valid:
            sys.exit(-1)

    if args.input is not None:
        run_config_settings_filename = args.input
    else:
        run_config_settings_filename = settings.workflow_settings_file

    if args.workflowpath is not None:
        workflow_path = args.workflowpath
    else:
        workflow_path = settings.workflow_path

    if args.work is not None:
        work_path = args.work
    else:
        work_path = os.path.join(str(settings.work_path), str(settings.workflow_work_path))

    overwrite = args.overwrite
    noask = args.noask
    exit_when_done = args.exit
    log_size_limit = args.logsize
    nb_jobs = args.jobs
    debug = args.debug
    keep = args.keep
    resume = args.resume
    detach = args.detach
    daemon_session = args.session

    run_workflows(
        run_config_settings_filename,
        workflow_path,
        work_path,
        overwrite,
        noask,
        exit_when_done,
        log_size_limit,
        nb_jobs,
        debug,
        keep,
        resume,
        settings.result_path,
        exp_workflow_res.DEFAULT_OUTPUT_FILENAME,
        detach,
        daemon_session,
    )


if __name__ == "__main__":
    args = parse_arguments()
    main(args)

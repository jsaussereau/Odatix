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
    abort_if_empty_job_list,
    replace_and_write_param_domains,
    resolve_workflow_param_target_file,
    run_prepare_loop,
    start_parallel_jobs as start_parallel_jobs_common,
)
import odatix.components.export_workflow_results as exp_workflow_res
import odatix.components.export_derived_metrics as exp_derived
import odatix.components.task_common as task_common
import odatix.lib.printc as printc
import odatix.run.cli as run_cli
from odatix.components.cli_options import add_options
from odatix.run.options import RunOptions
import odatix.lib.hard_settings as hard_settings
from odatix.lib.config_generator import ConfigGenerator
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.settings import OdatixSettings
from odatix.lib.architecture_handler import ArchitectureHandler
from odatix.lib.run_report import JobPlan, Category, runs
from odatix.run.planner import leave_jobs_to_sessions
from odatix.lib.param_domain import ParamDomain
import odatix.lib.virtual_param_domain as virtual_param_domain
from odatix.lib.utils import read_from_list, copytree, create_dir, ask_to_continue, get_timestamp_string, KeyNotInListError, BadValueInListError
from odatix.lib.run_settings import get_workflow_settings
from odatix.lib.wosit import createTaskGraph
import odatix.workspace.space as space
import odatix.lib.yaml_loader as yaml_loader

script_name = os.path.basename(__file__)
WORKFLOW_META_FILENAME = "workflow_meta.yml"
#: Written by the task "main" of a job once every task succeeded: what tells a
#: workflow that ran to its end from one that failed or was stopped halfway.
WORKFLOW_DONE_FILENAME = "workflow_done"


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
        virtual_param_domains=None,
        command_param_file=None,
        progress_regex=None,
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
        self.virtual_param_domains = (
            dict(virtual_param_domains) if isinstance(virtual_param_domains, dict) else {}
        )
        # The configuration's parameter file, for ${<workflow_name>} in the
        # commands: read whether or not it is also replaced into a source file
        # (param_file is None when "use_parameters" is off).
        self.command_param_file = command_param_file
        self.progress_regex = progress_regex


_read_command_parameter_value = virtual_param_domain.read_command_parameter_value


def _build_workflow_command_substitutions(workflow_instance):
    """
    Values a workflow task command can reference as ${name}: what the workflow
    is, where it runs, and one entry per parameter domain and per variable.

    The built-in names are put in first on purpose: a variable or a parameter
    domain the user named the same way wins over them, so declaring one never
    silently stops working.
    """
    substitutions = {
        "workflow": workflow_instance.workflow_name,
        "configuration": workflow_instance.workflow_config,
        "workflow_full": workflow_instance.workflow_full,
        "work_path": os.path.realpath(workflow_instance.tmp_dir),
        "log_path": hard_settings.work_log_path,
        "workflow_path": os.path.realpath(workflow_instance.workflow_definition_dir)
        if workflow_instance.workflow_definition_dir
        else "",
        "source_path": os.path.realpath(workflow_instance.source_path) if workflow_instance.source_path else "",
        "odatix_path": str(OdatixSettings.odatix_path),
    }
    substitutions = {name: str(value) for name, value in substitutions.items() if value is not None}

    if isinstance(workflow_instance.extra_command_substitutions, dict):
        for key, value in workflow_instance.extra_command_substitutions.items():
            substitutions[str(key)] = str(value)

    main_param_file = workflow_instance.command_param_file or workflow_instance.param_file
    if main_param_file is not None:
        main_value = _read_command_parameter_value(main_param_file)
        if main_value is not None:
            substitutions[workflow_instance.workflow_param_dir] = main_value

    for param_domain in workflow_instance.param_domains:
        value = _read_command_parameter_value(param_domain.param_file)
        if value is not None:
            substitutions[param_domain.domain] = value

    return substitutions


_sanitize_virtual_param_domain_value = virtual_param_domain.sanitize_value

get_workflow_virtual_domain_names = virtual_param_domain.get_virtual_domain_names


def _normalize_workflow_requests_for_virtual_domain_wildcards(workflow_requests, workflow_path, debug=False):
    """
    Normalize workflow requests before wildcard expansion.

    If a request uses only virtual-domain wildcards (for example
    workflow_name + var/* + other/*), strip these selectors so the generic
    wildcard resolver does not expect physical parameter-domain directories.
    """
    return virtual_param_domain.normalize_requests_for_wildcards(
        requests=workflow_requests,
        base_path=workflow_path,
        get_basic=ArchitectureHandler.get_basic,
        param_settings_filename=hard_settings.param_settings_filename,
        debug=debug,
        script_name=script_name,
    )


def build_workflow_virtual_param_domain_variants(workflow_settings, workflow_settings_file, debug=False):
    """
    Build workflow variants from the "variables" of the workflow settings.

    Variants are only generated when generate_configurations is not enabled.
    This preserves the existing meaning of generate_configurations while
    allowing variable-based command placeholders to emulate parameter domains.
    """
    return virtual_param_domain.build_variants(
        settings=workflow_settings,
        settings_file=workflow_settings_file,
        debug=debug,
        script_name=script_name,
    )


_replace_workflow_command_vars = virtual_param_domain.replace_command_vars


def _resolve_workflow_tasks(tasks, substitutions):
    if len(substitutions) == 0:
        return tasks

    resolved_tasks = []
    for task in tasks:
        if not isinstance(task, dict):
            resolved_tasks.append(task)
            continue

        resolved_task = dict(task)

        for key in ("commands", "on_failure_commands"):
            commands = resolved_task.get(key)
            if isinstance(commands, list):
                resolved_task[key] = [_replace_workflow_command_vars(command, substitutions) for command in commands]

        task_path = resolved_task.get("path")
        if isinstance(task_path, str):
            resolved_task["path"] = _replace_workflow_command_vars(task_path, substitutions)

        resolved_tasks.append(resolved_task)

    return resolved_tasks


# Task-list handling (platform selection, validation) is shared with the
# simulation runner: see odatix.components.task_common.


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


def workflow_done_file(tmp_dir):
    """The file a job writes once its workflow ran to its end."""
    return os.path.join(tmp_dir, WORKFLOW_DONE_FILENAME)


def _done_command(tmp_dir):
    """What the task "main" runs last: the same line for sh and cmd.exe."""
    return "echo done> \"" + os.path.realpath(workflow_done_file(tmp_dir)) + "\""


def job_category(tmp_dir, overwrite, resume=False):
    """
    What a run does with the job of one workflow variant, from what its work
    directory holds.

    A job whose workflow ran to its end has results: it is skipped, unless the
    run overwrites them. A directory without that mark is a job that failed or
    was stopped: it is run again, from where it is with "resume".
    """
    if not os.path.isdir(tmp_dir):
        return Category.NEW
    if os.path.isfile(workflow_done_file(tmp_dir)):
        return Category.OVERWRITE if overwrite else Category.CACHED
    return Category.RESUME if resume else Category.INCOMPLETE


#: ${name} in a command: what the shell would expand when Odatix does not.
_BRACED_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def unresolved_placeholders(tasks, substitutions, environment=None):
    """
    The ${name} placeholders of the commands of the tasks that nothing replaces:
    no variable, parameter domain or built-in name of the job, and no variable of
    the environment. The shell expands them, to nothing most of the time.

    Returns:
        list: (task name, placeholder name) pairs, in the order they appear.
    """
    environment = os.environ if environment is None else environment
    found = []
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        for key in ("commands", "on_failure_commands", "path"):
            value = task.get(key)
            lines = value if isinstance(value, list) else [value]
            for line in lines:
                if not isinstance(line, str):
                    continue
                for name in _BRACED_PLACEHOLDER.findall(line):
                    if name in substitutions or name in environment:
                        continue
                    entry = (str(task.get("name", "")), name)
                    if entry not in found:
                        found.append(entry)
    return found


def _warn_unresolved_placeholders(workflow_instance, workflow_path, warned):
    """
    Say which placeholders of a job nothing replaces, once per workflow. A
    domain left out of the selection or a configuration that is not selected
    runs the command with an empty value otherwise, without a word.
    """
    try:
        tasks = task_common.select_platform_task_implementations(workflow_instance.tasks, sys.platform)
    except Exception:
        return
    substitutions = _build_workflow_command_substitutions(workflow_instance)
    workflow = workflow_instance.workflow_param_dir
    for task_name, name in unresolved_placeholders(tasks, substitutions):
        if (workflow, name) in warned:
            continue
        warned.add((workflow, name))
        printc.warning(
            "Placeholder \"${" + name + "}\" of task \"" + task_name + "\" of workflow \"" + workflow
            + "\" matches no variable, parameter domain or built-in name: the shell will expand it, most likely to nothing.",
            script_name,
        )
        if name == workflow:
            printc.tip("Select a configuration of the workflow: \"" + workflow + "/<configuration>\".", script_name)
        elif os.path.isdir(os.path.join(workflow_path, workflow, name)):
            printc.tip("Add the parameter domain to the selection: \"" + workflow + " + " + name + "/*\".", script_name)


######################################
# Parse Arguments
######################################

def add_arguments(parser):
    add_options(
        parser, "workflows", "overwrite", "noask", "daemon_options", "settings_file", "workflow_path", "work_path",
        "exit_when_done", "nb_jobs", "keep", "resume", "log_size_limit", "debug", "export_options", "config",
        work_path={"help": "workflow work directory"},
        keep={"help": "store workflow batch with a timestamp in the configuration name"},
    )


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
    # See run_fmax_synthesis.run_synthesis: every run goes through odatix.run.
    run_cli.execute(run_cli.command_run(
        "workflow",
        settings_file=run_config_settings_filename,
        workflow_path=workflow_path,
        work_path=work_path,
        result_path=output_dir,
        output_filename=output_filename,
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        debug=debug,
        keep=keep,
        resume=resume,
        detach=detach,
        session=daemon_session,
    ))


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
    resume=False,
    selected_workflows=None,
):
    _overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs, workflows = get_workflow_settings(run_config_settings_filename)
    # Workflows named by the run ("--workflow") replace the list of the file.
    if selected_workflows:
        workflows = list(selected_workflows)

    if workflows is None:
        printc.error('The "workflows" section of "' + run_config_settings_filename + '" is empty.', script_name)
        printc.note('You must define your workflows in "' + run_config_settings_filename + '" before using this command, or name them with -W/--workflow.', script_name)
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

    plan = JobPlan()
    workflow_instances = []
    warned_placeholders = set()

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
            plan.add(workflow_display_name, Category.ERROR)
            continue

        with open(workflow_settings_file, "r") as f:
            try:
                workflow_settings = yaml.load(f, Loader=yaml_loader.SafeLoader)
            except Exception as e:
                printc.error("Workflow settings file \"" + workflow_settings_file + "\" is not a valid YAML file", script_name)
                printc.cyan("error details: ", end="", script_name=script_name)
                print(str(e))
                plan.add(workflow_display_name, Category.ERROR)
                continue

        try:
            sources = read_from_list("sources", workflow_settings, workflow_settings_file, type=dict, script_name=script_name)
            source_path = read_from_list("path", sources, workflow_settings_file, parent="sources", script_name=script_name)
            source_path = os.path.realpath(str(_expand_env_tokens(source_path)))
            if not os.path.isdir(source_path):
                printc.error("The sources.path \"" + source_path + "\" does not exist", script_name)
                plan.add(workflow_display_name, Category.ERROR)
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
            plan.add(workflow_display_name, Category.ERROR)
            continue

        progress_file = hard_settings.sim_progress_file
        progress_regex = hard_settings.sim_status_pattern.pattern
        try:
            progress = read_from_list("progress", workflow_settings, workflow_settings_file, type=dict, optional=True, raise_if_missing=False, print_error=False)
            if progress not in (False, None):
                progress_file = read_from_list("file", progress, workflow_settings_file, parent="progress", optional=True, raise_if_missing=False, print_error=False)
                progress_regex = read_from_list("regex", progress, workflow_settings_file, parent="progress", optional=True, raise_if_missing=False, print_error=False)
                if progress_file in (False, None):
                    progress_file = hard_settings.sim_progress_file
                if progress_regex in (False, None):
                    progress_regex = hard_settings.sim_status_pattern.pattern
        except (KeyNotInListError, BadValueInListError):
            progress_file = hard_settings.sim_progress_file
            progress_regex = hard_settings.sim_status_pattern.pattern

        # Each job reads its progress with the regex of its own workflow (see
        # ParallelJob progress_pattern); this one is only the default.
        if first_progress_regex is None:
            first_progress_regex = progress_regex

        # A configuration described by a rule is resolved here, on the way, so
        # nothing has to have been generated before the run.
        param_file = space.config_file(
            os.path.join(workflow_path, workflow_param_dir), workflow_config, settings=workflow_settings
        )
        if use_parameters and not no_main_configuration and param_file is None:
            printc.error(
                "The workflow parameter file \"" + workflow_config + ".txt\" does not exist in directory \""
                + os.path.join(workflow_path, workflow_param_dir) + "\"",
                script_name,
            )
            printc.note("Add it, or declare the configurations of this workflow in \"" + workflow_settings_file + "\".", script_name)
            plan.add(workflow_display_name, Category.ERROR)
            continue
        command_param_file = None if no_main_configuration else param_file
        if no_main_configuration or not use_parameters:
            param_file = None

        virtual_domain_names = get_workflow_virtual_domain_names(workflow_settings)
        requested_physical_param_domains, requested_virtual_param_domains = (
            virtual_param_domain.split_requested_param_domains(requested_param_domains, virtual_domain_names)
        )

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
                plan.add(workflow_display_name, Category.ERROR)
                continue

        virtual_param_domain_variants = [{"requested_param_domains": [], "substitutions": {}}]
        if len(virtual_domain_names) > 0:
            generated_virtual_variants = build_workflow_virtual_param_domain_variants(
                workflow_settings=workflow_settings,
                workflow_settings_file=workflow_settings_file,
                debug=debug,
            )
            if generated_virtual_variants is None:
                plan.add(workflow_display_name, Category.ERROR)
                continue

            if len(requested_virtual_param_domains) > 0:
                filtered_virtual_variants = virtual_param_domain.filter_variants(
                    generated_virtual_variants, requested_virtual_param_domains
                )

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
                    plan.add(workflow_display_name, Category.ERROR)
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
            if no_main_configuration and len(_variant_domains) > 0:
                # No configuration to name: "basic [width:8]", not "basic/basic [width:8]".
                workflow_display_name_variant = (
                    workflow + " [" + ", ".join(_variant_domains).replace("/", ":") + "]"
                )

            workflow_config_dir_work_variant = (
                workflow_config_dir_work_variant + "_" + timestamp if keep and timestamp != "" else workflow_config_dir_work_variant
            )
            tmp_dir = os.path.join(work_path, workflow_param_dir_work_variant, workflow_config_dir_work_variant)

            workflow_instance = WorkflowInstance(
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
                virtual_param_domains=virtual_param_domain.domains_dict(
                    virtual_variant.get("requested_param_domains", [])
                ),
                command_param_file=command_param_file,
                progress_regex=progress_regex,
            )
            _warn_unresolved_placeholders(workflow_instance, workflow_path, warned_placeholders)

            category = job_category(tmp_dir, overwrite, resume=resume)
            plan.add(workflow_display_name_variant, category, tasks=len(tasks))
            if runs(category):
                workflow_instances.append(workflow_instance)

    if first_progress_regex is None:
        first_progress_regex = hard_settings.sim_status_pattern.pattern

    ParallelJob.set_patterns(re.compile(first_progress_regex))

    # A job a session is already running is left to it: two sessions running
    # the same run directory would write into each other's files.
    workflow_instances = leave_jobs_to_sessions(
        workflow_instances, plan,
        tmp_dir=lambda instance: instance.tmp_dir,
        name=lambda instance: instance.workflow_display_name,
        overwrite=overwrite, script_name=script_name,
    )

    plan.print_summary(noun="workflows")

    confirm_valid_jobs(plan.run_count(), ask_continue, ask_to_continue, script_name=script_name, plan=plan)

    print()

    job_list = []

    def prepare_job(workflow_instance, resume=False):
        if not (resume and os.path.isdir(workflow_instance.tmp_dir)):
            create_dir(workflow_instance.tmp_dir)
        elif os.path.isfile(workflow_done_file(workflow_instance.tmp_dir)):
            # Running again in place: done only once it is done again.
            os.remove(workflow_done_file(workflow_instance.tmp_dir))

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
            target_resolver=resolve_workflow_param_target_file,
            debug=debug,
            timestamp=None,
            virtual_domains=workflow_instance.virtual_param_domains,
            main_param_file=workflow_instance.param_file,
        )

        selected_tasks = task_common.select_platform_task_implementations(workflow_instance.tasks, sys.platform)

        substitutions = _build_workflow_command_substitutions(workflow_instance)
        resolved_tasks = _resolve_workflow_tasks(selected_tasks, substitutions)
        task_common.validate_selected_tasks(resolved_tasks, sys.platform)

        done_command = _done_command(workflow_instance.tmp_dir)
        try:
            maker = createTaskGraph(resolved_tasks, done_command=done_command)
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
            # Every task stands for a file that is already there ("phony: No"):
            # nothing to run, but the job still ends as done.
            printc.note("Every task of workflow \"" + workflow_instance.workflow_display_name + "\" is up to date.", script_name)
            execution_stages = {0: [{"name": "main", "command": done_command}]}

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
            progress_pattern=workflow_instance.progress_regex,
        )

        job_list.append(running_workflow)

    return workflow_instances, prepare_job, job_list, exit_when_done, log_size_limit, nb_jobs, plan


def prepare_workflows(
    workflow_instances,
    prepare_job,
    job_list,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    resume=False,
    export_output_dir=None,
    export_work_root=None,
    export_workflow_path=None,
    export_output_filename=exp_workflow_res.DEFAULT_OUTPUT_FILENAME,
):
    run_prepare_loop(
        instances=workflow_instances,
        build_job=lambda workflow_instance: prepare_job(workflow_instance, resume=resume),
        job_list=job_list,
    )

    # A workflow can pass the initial checklist but still fail while its job is
    # being built: do not launch the monitor/daemon session with zero jobs if
    # every one of them failed.
    abort_if_empty_job_list(job_list, script_name=script_name)

    parallel_jobs = ParallelJobHandler(
        job_list=job_list,
        nb_jobs=nb_jobs,
        process_group=True,
        auto_exit=exit_when_done,
        log_size_limit=log_size_limit,
    )

    # Per-job result export (au fil de l'eau): tag every job so the handler
    # exports its result as soon as it finishes, for both the CLI and the
    # GUI/daemon (which both call this prepare function).
    if export_output_dir and export_work_root and export_workflow_path:
        exp_workflow_res.configure_workflow_job_exports(
            parallel_jobs=parallel_jobs,
            work_root=export_work_root,
            workflow_path=export_workflow_path,
            output_dir=export_output_dir,
            output_filename=export_output_filename,
        )

    # Whole-batch derivation: a derived metric reads records other jobs produce,
    # so it can only be computed once every job of the batch is done.
    if export_output_dir:
        exp_derived.configure_post_batch_derivation(parallel_jobs, export_output_dir)

    return parallel_jobs


def start_parallel_jobs(
    parallel_jobs,
    use_api=True,
    start_headless_on_startup=False,
    detach=False,
    session=None,
    configure=True,
):
    start_parallel_jobs_common(
        parallel_jobs=parallel_jobs,
        use_api=use_api,
        start_headless_on_startup=start_headless_on_startup,
        detach=detach,
        session=session,
        configure=configure,
    )


######################################
# Main
######################################

def main(args):
    run_cli.execute(run_cli.command_run(
        "workflow",
        workspace=run_cli.command_workspace(args.config, script_name),
        options=RunOptions.from_namespace(args),
    ))


if __name__ == "__main__":
    args = parse_arguments()
    main(args)

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
import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.settings import OdatixSettings
from odatix.lib.architecture_handler import ArchitectureHandler
from odatix.lib.param_domain import ParamDomain
from odatix.lib.utils import read_from_list, copytree, create_dir, ask_to_continue, get_timestamp_string, KeyNotInListError, BadValueInListError
from odatix.lib.run_settings import get_workflow_settings
from odatix.lib.wosit import createTaskGraph

script_name = os.path.basename(__file__)


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



def _replace_runtime_vars(self, value):
    if not isinstance(value, str):
        return value
    out = value
    out = out.replace("$tmp_dir", self.tmp_dir)
    out = out.replace("$workflow_dir", self.workflow_dir)
    return out



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

def run_workflows(run_config_settings_filename, workflow_path, work_path, overwrite, noask, exit_when_done, log_size_limit, nb_jobs, debug=False, keep=False, resume=False):
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
    start_parallel_jobs(parallel_jobs)


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

            param_target_file = read_from_list("param_target_file", workflow_settings, workflow_settings_file, script_name=script_name)
            start_delimiter = read_from_list("start_delimiter", workflow_settings, workflow_settings_file, script_name=script_name)
            stop_delimiter = read_from_list("stop_delimiter", workflow_settings, workflow_settings_file, script_name=script_name)
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
        if not os.path.isfile(param_file):
            printc.error("Workflow parameter file \"" + param_file + "\" does not exist", script_name)
            invalid_workflows.append(workflow_display_name)
            continue

        param_domains = []
        if len(requested_param_domains) > 0:
            param_domains = ParamDomain.get_param_domains(
                requested_param_domains=requested_param_domains,
                architecture=workflow_param_dir,
                arch_path=workflow_path,
                param_settings_filename=hard_settings.param_settings_filename,
                top_level_file=workflow_settings_file,
            )
            if param_domains is None:
                invalid_workflows.append(workflow_display_name)
                continue

        workflow_config_dir_work = workflow_config_dir_work + "_" + timestamp if keep and timestamp != "" else workflow_config_dir_work
        tmp_dir = os.path.join(work_path, workflow_param_dir_work, workflow_config_dir_work)

        workflow_instances.append(
            WorkflowInstance(
                workflow_name=workflow,
                workflow_display_name=workflow_display_name,
                workflow_full=workflow_full,
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
            )
        )
        valid_workflows.append(workflow_display_name)

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

        # copy source files
        copytree(
            src=workflow_instance.source_path,
            dst=workflow_instance.tmp_dir,
            whitelist=workflow_instance.source_whitelist,
            blacklist=workflow_instance.source_blacklist,
            dirs_exist_ok=True,
        )

        # replace main parameters
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

        try:
            maker = createTaskGraph(workflow_instance.tasks)
            old_cwd = os.getcwd()
            try:
                os.chdir(workflow_instance.tmp_dir)
                execusion_stages = maker.getStages(name="main", max_process=1)
            finally:
                os.chdir(old_cwd)
        except Exception as e:
            printc.error("Error while creating task graph for workflow \"" + workflow_instance.workflow_display_name + "\". Please check your workflow settings file and task definitions.", script_name)
            printc.cyan("error details: ", end="", script_name=script_name)
            print(str(e))
            sys.exit(-1)

        progress_file = os.path.join(workflow_instance.tmp_dir, workflow_instance.progress_file)

        running_workflow = ParallelJob(
            process=None,
            command=execusion_stages,
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
):
    start_parallel_jobs_common(
        parallel_jobs=parallel_jobs,
        use_api=use_api,
        start_headless_on_startup=start_headless_on_startup,
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
    )


if __name__ == "__main__":
    args = parse_arguments()
    main(args)

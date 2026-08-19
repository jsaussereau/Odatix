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
    resolve_sim_param_target_file,
    run_prepare_loop,
    start_parallel_jobs as start_parallel_jobs_common,
)
import odatix.components.export_simulation_results as exp_sim_res
import odatix.components.export_derived_metrics as exp_derived
import odatix.components.task_common as task_common
import odatix.lib.printc as printc
import odatix.run.cli as run_cli
import odatix.lib.hard_settings as hard_settings
import odatix.lib.virtual_param_domain as virtual_param_domain
from odatix.lib.parallel_job_handler import ParallelJobHandler, ParallelJob
from odatix.lib.settings import OdatixSettings
from odatix.lib.simulation_handler import SimulationHandler
from odatix.lib.utils import copytree, create_dir, ask_to_continue, get_timestamp_string
from odatix.lib.run_settings import get_sim_settings
from odatix.lib.wosit import createTaskGraph
from odatix.workspace.space import selected_config_file

script_name = os.path.basename(__file__)

sim_makefile_filename = "Makefile"
sim_rule = "sim"

SIMULATION_META_FILENAME = exp_sim_res.SIMULATION_META_FILENAME

######################################
# Parse Arguments
######################################

def add_arguments(parser):
    parser.add_argument('-o', '--overwrite', action='store_true', help='overwrite existing results')
    parser.add_argument('-y', '--noask', action='store_true', help='do not ask to continue')
    parser.add_argument('-d', '--detach', action='store_true', help='enqueue jobs to daemon and return without attaching monitor')
    parser.add_argument('-S', '--session', help='daemon session name or selector')
    parser.add_argument('-i', '--input', help='input settings file')
    parser.add_argument('-a', '--archpath', help='architecture directory')
    parser.add_argument('-s', '--simpath', help='simulation directory')
    parser.add_argument('-w', '--work', help='simulation work directory')
    parser.add_argument("-E", "--exit", action="store_true", help="exit monitor when all jobs are done")
    parser.add_argument("-j", "--jobs", help="maximum number of parallel jobs (use 'auto' for the number of CPUs minus one)")
    parser.add_argument("-k", "--keep", action="store_true", help="store simulation batch with a timestamp in the configuration name")
    parser.add_argument("-r", "--resume", action="store_true", help="resume from existing work directories (do not delete/recreate them)")
    parser.add_argument("--logsize", help="size of the log history per job in the monitor")
    parser.add_argument("-D", "--debug", action="store_true", help="enable debug mode to help troubleshoot settings files")
    parser.add_argument('-c', '--config', default=OdatixSettings.DEFAULT_SETTINGS_FILE, help='global settings file for Odatix (default: ' + OdatixSettings.DEFAULT_SETTINGS_FILE + ')')

def parse_arguments():
    parser = argparse.ArgumentParser(description='Run parallel simulations')
    add_arguments(parser)
    return parser.parse_args()


######################################
# Tasks
######################################

def default_simulation_task(sim_instance):
    """
    The historical simulation command, expressed as a single "main" task: a
    simulation that defines no "tasks" in its settings file keeps running
    through its Makefile's "sim" rule, exactly as before.
    """
    command = (
        "make {}".format(sim_rule)
        + ' RTL_DIR="{}"'.format(hard_settings.work_rtl_path)
        + ' ODATIX_DIR="{}"'.format(OdatixSettings.odatix_path)
        + ' LOG_DIR="{}"'.format(os.path.realpath(os.path.join(sim_instance.tmp_dir, hard_settings.work_log_path)))
        + ' CLOCK_SIGNAL="{}"'.format(sim_instance.architecture.clock_signal)
        + ' TOP_LEVEL_MODULE="{}"'.format(sim_instance.architecture.top_level_module)
        + " --no-print-directory"
    )
    return [{"name": "main", "commands": [command]}]


def build_simulation_command_substitutions(sim_instance):
    """
    Values a simulation task command can reference as ${name}: the architecture
    it runs on, the usual work directories, and one entry per parameter domain
    holding that domain's configuration value (like workflow commands do).
    """
    architecture = sim_instance.architecture
    substitutions = {
        "simulation": sim_instance.sim_name,
        "architecture": sim_instance.arch_param_dir,
        "configuration": sim_instance.arch_config,
        "arch_full": sim_instance.arch_full,
        "top_level_module": str(architecture.top_level_module or ""),
        "clock_signal": str(architecture.clock_signal or ""),
        "work_path": os.path.realpath(sim_instance.tmp_dir),
        "rtl_path": hard_settings.work_rtl_path,
        "log_path": hard_settings.work_log_path,
        "script_path": hard_settings.work_script_path,
        "sim_path": os.path.realpath(sim_instance.source_sim_dir),
        "design_path": str(architecture.design_path or ""),
        "odatix_path": str(OdatixSettings.odatix_path),
    }
    # The names these variables had before they were aligned on the tool ones.
    # Still substituted so existing simulation settings keep working, but no
    # longer offered by the editors (see odatix.gui.builtin_variables).
    substitutions["rtl_dir"] = substitutions["rtl_path"]
    substitutions["log_dir"] = substitutions["log_path"]
    substitutions["odatix_dir"] = substitutions["odatix_path"]

    for param_domain in getattr(architecture, "param_domains", []) or []:
        value = virtual_param_domain.read_command_parameter_value(param_domain.param_file)
        if value is not None:
            substitutions[param_domain.domain] = value

    return substitutions


def resolve_simulation_tasks(tasks, substitutions):
    """Substitute ${name} placeholders in every task command and path."""
    resolved_tasks = []
    for task in tasks:
        if not isinstance(task, dict):
            resolved_tasks.append(task)
            continue

        resolved_task = dict(task)

        commands = resolved_task.get("commands")
        if isinstance(commands, list):
            resolved_task["commands"] = [
                virtual_param_domain.replace_command_vars(command, substitutions) for command in commands
            ]

        task_path = resolved_task.get("path")
        if isinstance(task_path, str):
            resolved_task["path"] = virtual_param_domain.replace_command_vars(task_path, substitutions)

        resolved_tasks.append(resolved_task)

    return resolved_tasks


######################################
# Run Simulations
######################################

def run_simulations(
    run_config_settings_filename,
    arch_path,
    sim_path,
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
    output_filename=exp_sim_res.DEFAULT_OUTPUT_FILENAME,
    detach=False,
    daemon_session=None,
):
    # See run_fmax_synthesis.run_synthesis: every run goes through odatix.run.
    run_cli.execute(run_cli.command_run(
        "simulation",
        settings_file=run_config_settings_filename,
        arch_path=arch_path,
        sim_path=sim_path,
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
    arch_path,
    sim_path,
    work_path,
    overwrite,
    noask,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    debug=False,
    keep=False,
):
    _overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs, simulations = get_sim_settings(run_config_settings_filename)

    if simulations is None:
        printc.error('The "simulations" section of "' + run_config_settings_filename + '" is empty.', script_name)
        printc.note('You must define your simulations in "' + run_config_settings_filename + '" before using this command.', script_name)
        printc.note("Check out examples Odatix's documentation for more information.", script_name)
        sys.exit(-1)

    overwrite, ask_continue, exit_when_done, log_size_limit, nb_jobs = normalize_run_settings(
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        defaults=(_overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs),
    )

    sim_handler = SimulationHandler(
        work_path = work_path,
        arch_path = arch_path,
        sim_path = sim_path,
        work_rtl_path = hard_settings.work_rtl_path,
        work_script_path = hard_settings.work_script_path,
        work_log_path = hard_settings.work_log_path,
        log_path = hard_settings.work_log_path,
        overwrite = overwrite,
        param_settings_filename = hard_settings.param_settings_filename,
        sim_settings_filename = hard_settings.sim_settings_filename,
        sim_makefile_filename = sim_makefile_filename
    )

    timestamp = get_timestamp_string()

    try:
        simulation_instances = sim_handler.get_simulations(simulations, keep=keep, timestamp=timestamp)
    except yaml.YAMLError as e:
        printc.error("Could not get list \"simulations\" from \"" + run_config_settings_filename + "\".", script_name=script_name)
        printc.note("Is the YAML file valid? Are you missing a ':'? Is the indentation correct?", script_name=script_name)
        printc.cyan("error details: ", end="", script_name=script_name)
        print(str(e))
        sys.exit(-1)

    # The monitor parses every job's progress with a single pattern, so the
    # first simulation's regex wins (same rule as workflows).
    first_progress_regex = None
    for sim_instance in simulation_instances:
        regex = sim_instance.progress_regex or hard_settings.sim_status_pattern.pattern
        if first_progress_regex is None:
            first_progress_regex = regex
        elif first_progress_regex != regex:
            printc.note(
                "Multiple progress.regex values detected. Using the first one for monitor parsing: \"" + first_progress_regex + "\"",
                script_name,
            )
            break
    if first_progress_regex is None:
        first_progress_regex = hard_settings.sim_status_pattern.pattern
    ParallelJob.set_patterns(re.compile(first_progress_regex))

    # print checklist summary
    sim_handler.print_summary()

    confirm_valid_jobs(sim_handler.get_valid_sim_count(), ask_continue, ask_to_continue, script_name=script_name, plan=sim_handler.plan)

    print()

    job_list = []

    def prepare_job(sim_instance, resume=False):

        # create directory
        if not (resume and os.path.isdir(sim_instance.tmp_dir)):
            create_dir(sim_instance.tmp_dir)

        # write run metadata to make post-processing/export robust
        write_simulation_meta(sim_instance)

        # copy simulation sources
        copytree(sim_instance.source_sim_dir, sim_instance.tmp_dir, dirs_exist_ok = True)

        # copy design
        if sim_instance.architecture.design_path is not None:
            if not os.path.isdir(sim_instance.architecture.design_path):
                printc.error('The design directory "' + sim_instance.architecture.design_path + '" does not exist', script_name)
                return
            try:
                copytree(
                    src=sim_instance.architecture.design_path,
                    dst=sim_instance.architecture.tmp_dir,
                    whitelist=sim_instance.architecture.design_path_whitelist,
                    blacklist=sim_instance.architecture.design_path_blacklist,
                    dirs_exist_ok=True
                )
            except:
                printc.error("Could not copy \"" + sim_instance.architecture.design_path + "\" into work directory \"" + sim_instance.tmp_dir + "\"", script_name)
                printc.note("make sure there are no file or folder named identically in the two directories", script_name)
                return

        # copy rtl (if exists)
        if not sim_instance.architecture.generate_rtl:
            copytree(sim_instance.architecture.rtl_path, os.path.join(sim_instance.tmp_dir, 'rtl'), dirs_exist_ok = True)

        # replace parameters
        if sim_instance.architecture.use_parameters:
            if debug:
                printc.subheader("Replace main parameters")
            param_target_file = resolve_sim_param_target_file(
                sim_instance.tmp_dir, sim_instance.architecture.param_target_filename
            )
            param_filename = selected_config_file(arch_path, sim_instance.architecture.arch_name)
            replace_params(
                base_text_file=param_target_file,
                replacement_text_file=param_filename,
                output_file=param_target_file,
                start_delimiter=sim_instance.architecture.start_delimiter,
                stop_delimiter=sim_instance.architecture.stop_delimiter,
                replace_all_occurrences=False,
                silent=True
            )
            if debug:
                print()

        replace_and_write_param_domains(
            tmp_dir=sim_instance.tmp_dir,
            arch_name=sim_instance.architecture.arch_name,
            param_domains=sim_instance.architecture.param_domains,
            default_target_filename=sim_instance.architecture.param_target_filename,
            target_filename_getter=lambda param_domain: param_domain.param_target_file,
            debug=debug,
            target_resolver=resolve_sim_param_target_file,
            timestamp=None,
            virtual_domains=getattr(sim_instance.architecture, "virtual_param_domains", None),
        )

        # replace parameters again (override)
        if sim_instance.override_parameters:
            param_target_file = resolve_sim_param_target_file(
                sim_instance.tmp_dir, sim_instance.override_param_target_filename
            )
            param_file = os.path.join(sim_instance.tmp_dir, sim_instance.override_param_filename)
            replace_params(
                base_text_file=param_target_file,
                replacement_text_file=param_file,
                output_file=param_target_file,
                start_delimiter=sim_instance.override_start_delimiter,
                stop_delimiter=sim_instance.override_stop_delimiter,
                replace_all_occurrences=False,
                silent=True
            )

        command = build_simulation_command(sim_instance)
        if command is None:
            return

        sim_progress_file = os.path.join(
            sim_instance.tmp_dir,
            sim_instance.progress_file or hard_settings.sim_progress_file,
        )

        running_sim = ParallelJob(
            process=None,
            command=command,
            directory=sim_instance.tmp_dir,
            generate_rtl=sim_instance.architecture.generate_rtl,
            generate_command=sim_instance.architecture.generate_command,
            target="",
            arch="",
            display_name=sim_instance.sim_display_name,
            status_file="",
            progress_file=sim_progress_file,
            tmp_dir=sim_instance.tmp_dir,
            log_size_limit=log_size_limit,
            status="idle",
        )

        job_list.append(running_sim)

    return simulation_instances, prepare_job, job_list, exit_when_done, log_size_limit, nb_jobs, sim_handler.plan


def write_simulation_meta(sim_instance):
    """
    Write the run metadata file the result exporter reads back, so a work
    directory always says which simulation and which architecture configuration
    produced it (see odatix.components.export_simulation_results).
    """
    meta_file = os.path.join(sim_instance.tmp_dir, SIMULATION_META_FILENAME)
    try:
        with open(meta_file, "w") as f:
            yaml.dump(
                {
                    "simulation": sim_instance.sim_name,
                    "simulation_display_name": sim_instance.sim_display_name,
                    "simulation_definition_dir": sim_instance.source_sim_dir,
                    "architecture": sim_instance.arch_param_dir,
                    "configuration": sim_instance.arch_config,
                    "arch_full": sim_instance.arch_full,
                    # Which domains the run is invariant to is what the record
                    # must leave out to match every value of them, so it travels
                    # with the run rather than being looked up again at export.
                    "invariant_domains": sorted(sim_instance.invariant_domains),
                },
                f,
                default_flow_style=False,
                sort_keys=False,
            )
    except Exception as e:
        printc.warning(
            "Could not write simulation metadata file \"" + meta_file + "\": " + str(e),
            script_name,
        )


def build_simulation_command(sim_instance):
    """
    Build what the job actually runs: the execution stages of the simulation's
    task graph, or the legacy single "make sim" command when it defines no task.

    Returns:
        The command (a string or a list of execution stages), or None when the
        task graph could not be built (the job is then skipped).
    """
    tasks = sim_instance.tasks if sim_instance.tasks else default_simulation_task(sim_instance)

    try:
        selected_tasks = task_common.select_platform_task_implementations(tasks, sys.platform)
        substitutions = build_simulation_command_substitutions(sim_instance)
        resolved_tasks = resolve_simulation_tasks(selected_tasks, substitutions)
        task_common.validate_selected_tasks(resolved_tasks, sys.platform)
    except ValueError as e:
        printc.error(
            "Invalid tasks for simulation \"" + sim_instance.sim_display_name + "\": " + str(e),
            script_name,
        )
        return None

    # A single-command "main" task with no dependency is the historical case:
    # run it directly instead of paying for a task graph.
    if len(resolved_tasks) == 1 and not resolved_tasks[0].get("dependencies") and not resolved_tasks[0].get("path"):
        commands = resolved_tasks[0].get("commands", [])
        if len(commands) == 1:
            return commands[0]

    try:
        maker = createTaskGraph(resolved_tasks)
        old_cwd = os.getcwd()
        try:
            os.chdir(sim_instance.tmp_dir)
            execution_stages = maker.getStages(name="main", max_process=1)
        finally:
            os.chdir(old_cwd)
    except Exception as e:
        printc.error(
            "Error while creating task graph for simulation \"" + sim_instance.sim_display_name + "\". "
            "Please check your simulation settings file and task definitions.",
            script_name,
        )
        printc.cyan("error details: ", end="", script_name=script_name)
        print(str(e))
        return None

    if execution_stages is None or len(execution_stages) == 0:
        printc.error(
            "Failed to generate execution stages for simulation \"" + sim_instance.sim_display_name + "\".",
            script_name,
        )
        return None

    return execution_stages


def prepare_simulations(
    simulation_instances,
    prepare_job,
    job_list,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    resume=False,
    export_output_dir=None,
    export_work_root=None,
    export_sim_path=None,
    export_output_filename=exp_sim_res.DEFAULT_OUTPUT_FILENAME,
):
    run_prepare_loop(
        instances=simulation_instances,
        build_job=lambda sim_instance: prepare_job(sim_instance, resume=resume),
        job_list=job_list,
    )

    # A simulation can pass the initial checklist but still fail while its job
    # is being built (e.g. a missing design_path): do not launch the
    # monitor/daemon session with zero jobs if every one of them failed.
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
    if export_output_dir and export_work_root and export_sim_path:
        exp_sim_res.configure_simulation_job_exports(
            parallel_jobs=parallel_jobs,
            work_root=export_work_root,
            sim_path=export_sim_path,
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

def main(args, settings=None):

    # Get settings
    if settings is None:
        settings = OdatixSettings(args.config)
        if not settings.valid:
            sys.exit(-1)

    if args.input is not None:
        run_config_settings_filename  = args.input
    else:
        run_config_settings_filename = settings.simulation_settings_file

    if args.archpath is not None:
        arch_path = args.archpath
    else:
        arch_path = settings.arch_path

    if args.simpath is not None:
        sim_path = args.simpath
    else:
        sim_path = settings.sim_path

    if args.work is not None:
        work_path = args.work
    else:
        work_path = os.path.join(str(settings.work_path), str(settings.simulation_work_path))

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

    run_simulations(
        run_config_settings_filename,
        arch_path,
        sim_path,
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
        exp_sim_res.DEFAULT_OUTPUT_FILENAME,
        detach,
        daemon_session,
    )


if __name__ == "__main__":
    args = parse_arguments()
    main(args)

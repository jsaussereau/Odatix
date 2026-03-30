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
from odatix.lib.simulation_handler import SimulationHandler
from odatix.lib.utils import copytree, create_dir, ask_to_continue, get_timestamp_string
from odatix.lib.run_settings import get_sim_settings

script_name = os.path.basename(__file__)

sim_makefile_filename = "Makefile"
sim_rule = "sim"

######################################
# Parse Arguments
######################################

def add_arguments(parser):
    parser.add_argument('-o', '--overwrite', action='store_true', help='overwrite existing results')
    parser.add_argument('-y', '--noask', action='store_true', help='do not ask to continue')
    parser.add_argument('-i', '--input', help='input settings file')
    parser.add_argument('-a', '--archpath', help='architecture directory')
    parser.add_argument('-s', '--simpath', help='simulation directory')
    parser.add_argument('-w', '--work', help='simulation work directory')
    parser.add_argument("-E", "--exit", action="store_true", help="exit monitor when all jobs are done")
    parser.add_argument("-j", "--jobs", help="maximum number of parallel jobs")
    parser.add_argument("-k", "--keep", action="store_true", help="store synthesis batch with a timestamp in the configuration name")
    parser.add_argument("--logsize", help="size of the log history per job in the monitor")
    parser.add_argument("-D", "--debug", action="store_true", help="enable debug mode to help troubleshoot settings files")
    parser.add_argument('-c', '--config', default=OdatixSettings.DEFAULT_SETTINGS_FILE, help='global settings file for Odatix (default: ' + OdatixSettings.DEFAULT_SETTINGS_FILE + ')')

def parse_arguments():
    parser = argparse.ArgumentParser(description='Run parallel simulations')
    add_arguments(parser)
    return parser.parse_args()


######################################
# Run Simulations
######################################

def run_simulations(run_config_settings_filename, arch_path, sim_path, work_path, overwrite, noask, exit_when_done, log_size_limit, nb_jobs, debug=False, keep=False):
    simulation_instances, prepare_job, job_list, exit_when_done, log_size_limit, nb_jobs = check_settings(
        run_config_settings_filename=run_config_settings_filename,
        arch_path=arch_path,
        sim_path=sim_path,
        work_path=work_path,
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        debug=debug,
        keep=keep,
    )
    parallel_jobs = prepare_simulations(
        simulation_instances=simulation_instances,
        prepare_job=prepare_job,
        job_list=job_list,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
    )
    start_parallel_jobs(parallel_jobs)


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

    ParallelJob.set_patterns(hard_settings.sim_status_pattern)

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

    # print checklist summary
    sim_handler.print_summary()

    confirm_valid_jobs(sim_handler.get_valid_sim_count(), ask_continue, ask_to_continue, script_name=script_name)

    print()

    job_list = []

    def prepare_job(sim_instance):
        
        if True:
            # create directory
            create_dir(sim_instance.tmp_dir)

            # copy simulation sources
            copytree(sim_instance.source_sim_dir, sim_instance.tmp_dir, dirs_exist_ok = True)
         
            # copy design 
            if sim_instance.architecture.design_path is not None:
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
                param_target_file = os.path.join(sim_instance.tmp_dir, sim_instance.architecture.param_target_filename)
                param_filename = os.path.join(arch_path, sim_instance.architecture.arch_name + '.txt')
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
                target_filename_getter=lambda _param_domain: sim_instance.architecture.param_target_filename,
                debug=debug,
                timestamp=None,
            )

            # replace parameters again (override)
            if sim_instance.override_parameters:
                #printc.subheader("Replace parameters")
                param_target_file = os.path.join(sim_instance.tmp_dir, sim_instance.override_param_target_filename)
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

            # run simulation command
            command = (
                "make {}".format(sim_rule)
                + ' RTL_DIR="{}"'.format(hard_settings.work_rtl_path)
                + ' ODATIX_DIR="{}"'.format(OdatixSettings.odatix_path)
                + ' LOG_DIR="{}"'.format(os.path.realpath(os.path.join(sim_instance.tmp_dir, hard_settings.work_log_path)))
                + ' CLOCK_SIGNAL="{}"'.format(sim_instance.architecture.clock_signal)
                + ' TOP_LEVEL_MODULE="{}"'.format(sim_instance.architecture.top_level_module)
                + " --no-print-directory"
            )

            sim_progress_file = os.path.join(sim_instance.tmp_dir, hard_settings.work_log_path, hard_settings.sim_progress_filename)

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

    return simulation_instances, prepare_job, job_list, exit_when_done, log_size_limit, nb_jobs


def prepare_simulations(
    simulation_instances,
    prepare_job,
    job_list,
    exit_when_done,
    log_size_limit,
    nb_jobs,
):
    for sim_instance in simulation_instances:
        prepare_job(sim_instance)

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

    run_simulations(run_config_settings_filename, arch_path, sim_path, work_path, overwrite, noask, exit_when_done, log_size_limit, nb_jobs, debug, keep)


if __name__ == "__main__":
    args = parse_arguments()
    main(args)

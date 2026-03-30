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
import argparse
from odatix.components.synthesis_common import load_synthesis_context, build_prepare_synthesis_job, prepare_synthesis_jobs
from odatix.components.run_common import confirm_valid_jobs, start_parallel_jobs as start_parallel_jobs_common
import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.parallel_job_handler import ParallelJob
from odatix.lib.settings import OdatixSettings
from odatix.lib.architecture_handler import ArchitectureHandler
from odatix.lib.utils import ask_to_continue, get_timestamp_string

script_name = os.path.basename(__file__)

class SynthesisCancelled(Exception):
    pass

def _check_cancel(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise SynthesisCancelled()

######################################
# Parse Arguments
######################################


def add_arguments(parser):
    parser.add_argument("-t", "--tool", default="vivado", help="eda tool in use (default: vivado)")
    parser.add_argument("-o", "--overwrite", action="store_true", help="overwrite existing results")
    parser.add_argument("-y", "--noask", action="store_true", help="do not ask to continue")
    parser.add_argument("-i", "--input", help="input settings file")
    parser.add_argument("-a", "--archpath", help="architecture directory")
    parser.add_argument("-w", "--work", help="work directory")
    parser.add_argument("-E", "--exit", action="store_true", help="exit monitor when all jobs are done")
    parser.add_argument("-j", "--jobs", help="maximum number of parallel jobs")
    parser.add_argument("-f", "--force", action="store_true", help="force fmax synthesis to continue on synthesis error")
    parser.add_argument("-T", "--trust", action="store_true", help="do not check eda tool before runnning jobs (saves time)")
    parser.add_argument("-D", "--debug", action="store_true", help="enable debug mode to help troubleshoot settings files")
    parser.add_argument("--from", dest="from_freq", type=int, help="override lower bound for fmax synthesis (in MHz)")
    parser.add_argument("--to", dest="to_freq", type=int, help="override upper bound for fmax synthesis (in MHz)")
    parser.add_argument("-k", "--keep", action="store_true", help="store synthesis batch with a timestamp in the configuration name")
    parser.add_argument("--logsize", help="size of the log history per job in the monitor")
    parser.add_argument(
        "-c",
        "--config",
        default=OdatixSettings.DEFAULT_SETTINGS_FILE,
        help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
    )


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run fmax synthesis on selected architectures")
    add_arguments(parser)
    return parser.parse_args()


######################################
# Run Synthesis
######################################


def run_synthesis(
    run_config_settings_filename,
    arch_path,
    tool,
    work_path,
    target_path,
    overwrite,
    noask, 
    exit_when_done,
    log_size_limit,
    nb_jobs,
    continue_on_error,
    check_eda_tool,
    forced_fmax_lower_bound=None,
    forced_fmax_upper_bound=None,
    debug=False,
    keep=False,
    cancel_event=None,
):
    architecture_instances, prepare_job, job_list, tool_settings_file, arch_handler, exit_when_done, log_size_limit, nb_jobs = check_settings(
        run_config_settings_filename=run_config_settings_filename,
        arch_path=arch_path,
        tool=tool,
        work_path=work_path,
        target_path=target_path,
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        continue_on_error=continue_on_error,
        check_eda_tool=check_eda_tool,
        forced_fmax_lower_bound=forced_fmax_lower_bound,
        forced_fmax_upper_bound=forced_fmax_upper_bound,
        debug=debug,
        keep=keep,
        cancel_event=cancel_event,
    )
    parallel_jobs = prepare_synthesis(
        architecture_instances=architecture_instances,
        prepare_job=prepare_job,
        job_list=job_list,
        arch_handler=arch_handler,
        tool_settings_file=tool_settings_file,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        cancel_event=cancel_event,
    )
    start_parallel_jobs(parallel_jobs)

def check_settings(
    run_config_settings_filename,
    arch_path,
    tool,
    work_path,
    target_path,
    overwrite,
    noask, 
    exit_when_done,
    log_size_limit,
    nb_jobs,
    continue_on_error,
    check_eda_tool,
    forced_fmax_lower_bound=None,
    forced_fmax_upper_bound=None,
    debug=False,
    keep=False,
    cancel_event=None,
):
    _check_cancel(cancel_event)
    context = load_synthesis_context(
        run_config_settings_filename=run_config_settings_filename,
        arch_path=arch_path,
        tool=tool,
        work_path=work_path,
        target_path=target_path,
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        check_eda_tool=check_eda_tool,
        debug=debug,
        script_name=script_name,
        synth_type=None,
        check_cancel=lambda: _check_cancel(cancel_event),
    )

    ParallelJob.set_patterns(hard_settings.synth_status_pattern, hard_settings.fmax_status_pattern)

    arch_handler = ArchitectureHandler(
        work_path=context["work_path"],
        arch_path=arch_path,
        script_path=OdatixSettings.odatix_eda_tools_path,
        log_path=hard_settings.work_log_path,
        work_rtl_path=hard_settings.work_rtl_path,
        work_script_path=hard_settings.work_script_path,
        work_log_path=hard_settings.work_log_path,
        work_report_path=hard_settings.work_report_path,
        process_group=context["process_group"],
        command=context["run_command"],
        eda_target_filename=os.path.realpath(os.path.join(target_path, "target_" + tool + ".yml")),
        fmax_status_filename=hard_settings.fmax_status_filename,
        frequency_search_filename=hard_settings.frequency_search_filename,
        param_settings_filename=hard_settings.param_settings_filename,
        valid_status=hard_settings.valid_status,
        valid_frequency_search=hard_settings.valid_frequency_search,
        forced_fmax_lower_bound=forced_fmax_lower_bound,
        forced_fmax_upper_bound=forced_fmax_upper_bound,
        forced_custom_freq_list=None,
        overwrite=context["overwrite"],
        continue_on_error=continue_on_error,
        force_single_thread=context["force_single_thread"],
    )

    timestamp = get_timestamp_string()
    architecture_instances = arch_handler.get_architectures(
        context["architectures"],
        context["targets"],
        context["constraint_file"],
        context["install_path"],
        keep=keep,
        timestamp=timestamp,
    )

    _check_cancel(cancel_event)

    arch_handler.print_summary()
    confirm_valid_jobs(arch_handler.get_valid_arch_count(), context["ask_continue"], ask_to_continue, script_name=script_name)

    print()

    job_list = []
    prepare_job = build_prepare_synthesis_job(
        arch_handler=arch_handler,
        arch_path=arch_path,
        tool=tool,
        log_size_limit=context["log_size_limit"],
        debug=debug,
        timestamp=timestamp,
        progress_mode="fmax",
        script_name=script_name,
        check_cancel=lambda: _check_cancel(cancel_event),
    )
    return (
        architecture_instances,
        prepare_job,
        job_list,
        context["tool_settings_file"],
        arch_handler,
        context["exit_when_done"],
        context["log_size_limit"],
        context["nb_jobs"],
    )

def prepare_synthesis(
    architecture_instances,
    prepare_job,
    job_list,
    tool_settings_file,
    arch_handler,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    cancel_event=None,
):
    return prepare_synthesis_jobs(
        architecture_instances=architecture_instances,
        prepare_job=prepare_job,
        job_list=job_list,
        process_group=arch_handler.process_group,
        tool_settings_file=tool_settings_file,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        check_cancel=lambda: _check_cancel(cancel_event),
    )

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

    # # Summary
    # if job_exit_success:
    #     print()
    #     for running_arch in job_list:
    #         tmp_dir = os.path.join(work_path, running_arch.target, running_arch.arch)
    #         frequency_search_file = os.path.join(tmp_dir, hard_settings.work_log_path, hard_settings.frequency_search_filename)
    #         try:
    #             with open(frequency_search_file, "r") as file:
    #                 lines = file.readlines()
    #                 if len(lines) >= 1:
    #                     summary_line = lines[-1]
    #                     print(running_arch.display_name + ": " + summary_line, end="")
    #         except:
    #             pass
    #     print()


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
        run_config_settings_filename = args.input
    else:
        run_config_settings_filename = settings.fmax_synthesis_settings_file

    if args.archpath is not None:
        arch_path = args.archpath
    else:
        arch_path = settings.arch_path

    if args.work is not None:
        work_path = args.work
    else:
        work_path = os.path.join(str(settings.work_path), str(settings.fmax_synthesis_work_path))

    target_path = settings.target_path
    tool = args.tool
    overwrite = args.overwrite
    noask = args.noask
    exit_when_done = args.exit
    log_size_limit = args.logsize
    nb_jobs = args.jobs
    continue_on_error = args.force
    check_eda_tool = not args.trust
    debug = args.debug
    keep = args.keep

    if args.from_freq is not None and args.to_freq is not None:
        if not ArchitectureHandler.check_bounds(args.from_freq, args.to_freq):
            sys.exit(-1)

    run_synthesis(
        run_config_settings_filename=run_config_settings_filename,
        arch_path=arch_path,
        tool=tool,
        work_path=work_path,
        target_path=target_path,
        overwrite=overwrite,
        noask=noask, 
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        continue_on_error=continue_on_error,
        check_eda_tool=check_eda_tool,
        forced_fmax_lower_bound=args.from_freq,
        forced_fmax_upper_bound=args.to_freq,
        debug=debug,
        keep=keep,
    )


if __name__ == "__main__":
    args = parse_arguments()
    main(args)

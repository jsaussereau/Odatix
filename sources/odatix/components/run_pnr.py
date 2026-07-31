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
"odatix pnr": place & route designs another tool has already synthesized.

This is the one job type that chains two eda tools. A run picks the completed
synthesis jobs it starts from (see odatix.lib.pnr_source) and runs the place &
route flow of the tool given by "--tool" on each of them, so Design Compiler +
Innovus, Genus + ICC2 and any other pairing are just two commands:

    odatix freq -t design_compiler
    odatix pnr  -t innovus --from-tool design_compiler
"""

import os
import sys
import argparse

from odatix.components.pnr_common import build_prepare_pnr_job, load_pnr_context
from odatix.components.run_common import (
    confirm_valid_jobs,
    settle_tool_checks,
    start_parallel_jobs as start_parallel_jobs_common,
)
from odatix.components.synthesis_common import prepare_synthesis_jobs
import odatix.components.export_results as exp_res
import odatix.components.export_derived_metrics as exp_derived
import odatix.lib.eda_tools as eda_tools
import odatix.lib.hard_settings as hard_settings
import odatix.lib.job_steps as job_steps
import odatix.lib.pnr_source as pnr_source
import odatix.lib.printc as printc
from odatix.lib.parallel_job_handler import ParallelJob
from odatix.lib.pnr_handler import PnrJobHandler
from odatix.lib.settings import OdatixSettings
from odatix.lib.utils import ask_to_continue

script_name = os.path.basename(__file__)


class PnrCancelled(Exception):
    pass


def _check_cancel(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise PnrCancelled()


######################################
# Parse Arguments
######################################


def add_arguments(parser):
    parser.add_argument("-t", "--tool", default=None, help="eda tool running the place & route")
    parser.add_argument("-f", "--flow", default=None, help="flow of the eda tool to run (default: the tool's default flow)")
    parser.add_argument("-u", "--until", default=None, help="last step of the flow to run, inclusive (default: all its steps)")
    parser.add_argument("--rerun-from", dest="rerun_from", default=None, help="re-run this step and the following ones, even if already done")
    parser.add_argument(
        "--from-type",
        dest="from_type",
        default=None,
        choices=list(pnr_source.SOURCE_JOB_TYPES),
        help="only place & route the synthesis jobs of this type",
    )
    parser.add_argument("--from-tool", dest="from_tool", default=None, help="only place & route the synthesis jobs run with this eda tool")
    parser.add_argument("--from-flow", dest="from_flow", default=None, help="only place & route the synthesis jobs run with this flow of --from-tool")
    parser.add_argument("-o", "--overwrite", action="store_true", help="overwrite existing results")
    parser.add_argument("-y", "--noask", action="store_true", help="do not ask to continue")
    parser.add_argument("-d", "--detach", action="store_true", help="enqueue jobs to daemon and return without attaching monitor")
    parser.add_argument("-S", "--session", help="daemon session name or selector")
    parser.add_argument("-i", "--input", help="input settings file")
    parser.add_argument("-w", "--work", help="work directory")
    parser.add_argument("-E", "--exit", action="store_true", help="exit monitor when all jobs are done")
    parser.add_argument("-j", "--jobs", help="maximum number of parallel jobs (use 'auto' for the number of CPUs minus one)")
    parser.add_argument("-T", "--trust", action="store_true", help="do not check eda tool before runnning jobs (saves time)")
    parser.add_argument("-D", "--debug", action="store_true", help="enable debug mode to help troubleshoot settings files")
    parser.add_argument("--logsize", help="size of the log history per job in the monitor")
    parser.add_argument(
        "-c",
        "--config",
        default=OdatixSettings.DEFAULT_SETTINGS_FILE,
        help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
    )


def parse_arguments():
    parser = argparse.ArgumentParser(description="Place & route designs already synthesized by another eda tool")
    add_arguments(parser)
    return parser.parse_args()


def _restrict_selectors(selectors, from_type, from_tool, from_flow):
    """
    Narrow what the settings file selects with what the command line asks for.

    "--from-tool innovus" does not add sources: it drops the selected ones that
    another tool synthesized, so a settings file listing everything can still be
    run one source tool at a time.
    """
    if from_type is None and from_tool is None and from_flow is None:
        return list(selectors or [])

    if from_flow is not None and from_tool is None:
        printc.error("--from-flow cannot be used without --from-tool", script_name)
        raise SystemExit(-1)

    wanted_work_dirname = None
    if from_tool is not None:
        wanted_work_dirname = eda_tools.tool_work_dirname(from_tool, from_flow, job_type=None) if from_flow else from_tool

    restricted = []
    for selector in selectors or []:
        parsed = pnr_source.parse_selector(selector)
        if parsed is None:
            # Left as is: match_sources reports it properly.
            restricted.append(selector)
            continue

        if from_type is not None:
            if parsed["job_type"] not in (from_type, pnr_source.WILDCARD):
                continue
            parsed["job_type"] = from_type

        if wanted_work_dirname is not None:
            if parsed["work_dirname"] not in (wanted_work_dirname, pnr_source.WILDCARD):
                continue
            parsed["work_dirname"] = wanted_work_dirname

        selector = "/".join(
            [parsed["job_type"], parsed["work_dirname"], parsed["target"], parsed["architecture"], parsed["configuration"]]
        )
        if parsed["frequency_segment"] != pnr_source.WILDCARD:
            selector += pnr_source.FREQUENCY_SEPARATOR + parsed["frequency_segment"]
        restricted.append(selector)

    if not restricted:
        printc.warning("No selected source matches the requested --from-* filters", script_name)

    return restricted


######################################
# Run Place & Route
######################################


def check_settings(
    run_config_settings_filename,
    source_work_root,
    tool,
    flow,
    until_step,
    rerun_from_step,
    work_path,
    target_path,
    overwrite,
    noask,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    check_eda_tool,
    source_result_types=None,
    from_type=None,
    from_tool=None,
    from_flow=None,
    debug=False,
    cancel_event=None,
    tool_check_sink=None,
):
    """
    Build the job list of a place & route run and confirm it, exactly like the
    other runners do. Returns the same 9-tuple, so the GUI unpacks it the same
    way whatever the job type.
    """
    _check_cancel(cancel_event)

    context = load_pnr_context(
        run_config_settings_filename=run_config_settings_filename,
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
        flow=flow,
        check_cancel=lambda: _check_cancel(cancel_event),
    )

    steps = context["flow_steps"]
    rerun_index = None
    if steps:
        steps, rerun_index, step_error = job_steps.select_steps(steps, until=until_step, rerun_from=rerun_from_step)
        if step_error is not None:
            printc.error('Flow "' + str(context["flow"]) + '" of eda tool "' + tool + '": ' + step_error, script_name)
            raise SystemExit(-1)
    elif until_step or rerun_from_step:
        printc.error(
            'Flow "' + str(context["flow"]) + '" of eda tool "' + tool + '" is not split into steps',
            script_name,
        )
        printc.note("--until and --rerun-from only apply to a flow declaring steps in its tool.yml", script_name)
        raise SystemExit(-1)

    ParallelJob.set_patterns(hard_settings.synth_status_pattern, hard_settings.fmax_status_pattern)

    pnr_handler = PnrJobHandler(
        work_path=context["work_path"],
        source_work_root=source_work_root,
        source_result_types=source_result_types,
        script_path=OdatixSettings.odatix_eda_tools_path,
        work_rtl_path=hard_settings.work_rtl_path,
        work_script_path=hard_settings.work_script_path,
        work_report_path=hard_settings.work_report_path,
        work_log_path=hard_settings.work_log_path,
        process_group=context["process_group"],
        command=context["run_command"],
        eda_target_filename=eda_tools.resolve_target_file(tool, target_path),
        overwrite=context["overwrite"],
        force_single_thread=context["force_single_thread"],
        requested_steps=[step["name"] for step in steps] if steps else None,
        rerun_step_index=rerun_index,
    )

    selectors = _restrict_selectors(context["architectures"], from_type, from_tool, from_flow)

    architecture_instances = pnr_handler.get_pnr_jobs(
        selectors,
        targets=context["targets"],
        install_path=context["install_path"],
        constraint_filename=context["constraint_file"],
    )

    _check_cancel(cancel_event)

    pnr_handler.print_summary()

    settle_tool_checks([context["tool_check"]], tool_check_sink)
    confirm_valid_jobs(pnr_handler.get_valid_arch_count(), context["ask_continue"], ask_to_continue, script_name=script_name)

    print()

    job_list = []
    prepare_job = build_prepare_pnr_job(
        arch_handler=pnr_handler,
        tool=tool,
        log_size_limit=context["log_size_limit"],
        flow=context["flow"],
        steps=steps,
        rerun_index=rerun_index,
        progress_mode="synth",
        script_name=script_name,
        check_cancel=lambda: _check_cancel(cancel_event),
    )

    return (
        architecture_instances,
        prepare_job,
        job_list,
        context["format_settings_file"],
        pnr_handler,
        context["exit_when_done"],
        context["log_size_limit"],
        context["nb_jobs"],
        pnr_handler.plan,
    )


def prepare_pnr(
    architecture_instances,
    prepare_job,
    job_list,
    tool_settings_file,
    arch_handler,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    cancel_event=None,
    export_output_dir=None,
    export_tool=None,
    export_flow=None,
    export_work_path=None,
    use_benchmark=False,
    benchmark_file=None,
    custom_metrics_file=None,
):
    parallel_jobs = prepare_synthesis_jobs(
        architecture_instances=architecture_instances,
        prepare_job=prepare_job,
        job_list=job_list,
        process_group=arch_handler.process_group,
        tool_settings_file=tool_settings_file,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        check_cancel=lambda: _check_cancel(cancel_event),
        script_name=script_name,
    )

    # Per-job result export: every job is tagged so the handler exports its
    # result as soon as it finishes, for both the CLI and the GUI/daemon.
    if export_output_dir and export_tool and export_work_path:
        exp_res.configure_synthesis_job_exports(
            parallel_jobs=parallel_jobs,
            result_type="pnr",
            work_path=export_work_path,
            tool=export_tool,
            flow=export_flow,
            output_dir=export_output_dir,
            use_benchmark=use_benchmark,
            benchmark_file=benchmark_file,
            custom_metrics_file=custom_metrics_file,
        )

    # A derived metric reads records other jobs produce, so it can only be
    # computed once every job of the batch is done.
    if export_output_dir:
        exp_derived.configure_post_batch_derivation(parallel_jobs, export_output_dir)

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


def run_pnr(
    run_config_settings_filename,
    source_work_root,
    tool,
    flow,
    until_step,
    rerun_from_step,
    work_path,
    target_path,
    overwrite,
    noask,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    check_eda_tool,
    source_result_types=None,
    from_type=None,
    from_tool=None,
    from_flow=None,
    debug=False,
    export_output_dir=None,
    use_benchmark=False,
    benchmark_file=None,
    custom_metrics_file=None,
    cancel_event=None,
    detach=False,
    daemon_session=None,
):
    (
        architecture_instances,
        prepare_job,
        job_list,
        tool_settings_file,
        arch_handler,
        exit_when_done,
        log_size_limit,
        nb_jobs,
        _plan,
    ) = check_settings(
        run_config_settings_filename=run_config_settings_filename,
        source_work_root=source_work_root,
        tool=tool,
        flow=flow,
        until_step=until_step,
        rerun_from_step=rerun_from_step,
        work_path=work_path,
        target_path=target_path,
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        check_eda_tool=check_eda_tool,
        source_result_types=source_result_types,
        from_type=from_type,
        from_tool=from_tool,
        from_flow=from_flow,
        debug=debug,
        cancel_event=cancel_event,
    )

    parallel_jobs = prepare_pnr(
        architecture_instances=architecture_instances,
        prepare_job=prepare_job,
        job_list=job_list,
        arch_handler=arch_handler,
        tool_settings_file=tool_settings_file,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        cancel_event=cancel_event,
        export_output_dir=export_output_dir,
        export_tool=tool,
        export_flow=flow,
        export_work_path=work_path,
        use_benchmark=use_benchmark,
        benchmark_file=benchmark_file,
        custom_metrics_file=custom_metrics_file,
    )

    start_parallel_jobs(parallel_jobs, detach=detach, session=daemon_session)


######################################
# Main
######################################


def main(args, settings=None):
    if settings is None:
        settings = OdatixSettings(args.config)
        if not settings.valid:
            sys.exit(-1)

    tool = args.tool
    if tool is None:
        supported = eda_tools.tools_supporting("pnr")
        printc.error("No eda tool specified: use -t/--tool to say what should place & route", script_name)
        if supported:
            printc.note("Eda tools able to run a place & route: " + ", ".join(supported), script_name)
        else:
            printc.note(
                'No eda tool declares a place & route: add a "pnr_command" or "pnr_steps" section to the tool.yml of one.',
                script_name,
            )
        sys.exit(-1)

    if args.input is not None:
        run_config_settings_filename = args.input
    else:
        run_config_settings_filename = settings.pnr_settings_file

    if args.work is not None:
        work_root = args.work
    else:
        work_root = str(settings.work_path)

    run_pnr(
        run_config_settings_filename=run_config_settings_filename,
        source_work_root=work_root,
        tool=tool,
        flow=args.flow,
        until_step=args.until,
        rerun_from_step=args.rerun_from,
        work_path=os.path.join(work_root, str(settings.pnr_work_path)),
        target_path=settings.target_path,
        overwrite=args.overwrite,
        noask=args.noask,
        exit_when_done=args.exit,
        log_size_limit=args.logsize,
        nb_jobs=args.jobs,
        check_eda_tool=not args.trust,
        source_result_types=settings.result_types,
        from_type=args.from_type,
        from_tool=args.from_tool,
        from_flow=args.from_flow,
        debug=args.debug,
        export_output_dir=settings.result_path,
        use_benchmark=bool(getattr(settings, "use_benchmark", False)),
        benchmark_file=getattr(settings, "benchmark_file", None),
        custom_metrics_file=None,
        detach=args.detach,
        daemon_session=args.session,
    )


if __name__ == "__main__":
    args = parse_arguments()
    main(args)

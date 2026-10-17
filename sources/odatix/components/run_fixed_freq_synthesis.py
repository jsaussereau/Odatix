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
from odatix.workspace.yaml_io import read_yaml
from odatix.components.run_common import confirm_valid_jobs, settle_tool_checks, start_parallel_jobs as start_parallel_jobs_common
import odatix.components.export_results as exp_res
import odatix.components.export_derived_metrics as exp_derived
import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
import odatix.lib.eda_tools as eda_tools
import odatix.lib.job_steps as job_steps
import odatix.run.cli as run_cli
from odatix.components.cli_options import add_options
from odatix.run.options import RunOptions
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
    add_options(parser, "tool", "flow", "targets", "until", "rerun_from", "overwrite", "noask", "daemon_options", "settings_file", "arch_path", "work_path", "exit_when_done", "nb_jobs", "check_eda_tool", "debug")
    parser.add_argument("--from", dest="from_freq", type=int, help="lowest frequency of the range, in MHz")
    parser.add_argument("--to", dest="to_freq", type=int, help="highest frequency of the range, in MHz")
    parser.add_argument("--step", dest="step_freq", type=int, help="step of the range, in MHz")
    parser.add_argument("--at", dest="at_freq", action='append', type=int, help="run the synthesis at this frequency, in MHz (repeatable)")
    add_options(parser, "keep", "log_size_limit", "export_options", "config", keep={"help": "store synthesis batch with a timestamp in the configuration name"})


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run synthesis at specigied frequencies on selected architectures")
    add_arguments(parser)
    return parser.parse_args()


def _frequencies_error(settings_filename, text, example):
    """Stop the run on a "frequencies" section it cannot read, saying how to write it."""
    printc.error(text + ' in "' + settings_filename + '".', script_name)
    printc.note("You can define it like this:", script_name)
    printc.grey(example)
    raise SystemExit(-1)


_FREQUENCIES_EXAMPLE = (
    "frequencies:\n"
    "  override: No\n"
    "  list: [100, 200]\n"
    "  range:\n"
    "    from: 50\n"
    "    to: 100\n"
    "    step: 10"
)


def _is_frequency(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _load_settings_custom_frequencies(run_config_settings_filename):
    """
    The frequencies the run settings file asks for, and whether they replace
    the ones of the architectures.

    A key left empty ("frequencies:", "range:") asks for nothing. A key holding
    something that is not what it should (a list where a mapping is expected,
    a word where a frequency is) stops the run with a message saying so,
    rather than with a Python traceback or by running other frequencies.
    """
    settings_payload = read_yaml(run_config_settings_filename, default={})
    if not isinstance(settings_payload, dict):
        settings_payload = {}
    frequencies = settings_payload.get("frequencies")
    if frequencies is None:
        return [], False
    if not isinstance(frequencies, dict):
        _frequencies_error(
            run_config_settings_filename,
            '"frequencies" holds a "' + type(frequencies).__name__ + '" while it should hold "list" and/or "range"',
            _FREQUENCIES_EXAMPLE,
        )

    override_arch_frequencies = bool(frequencies.get("override", False))
    custom_freq_list = []

    list_data = frequencies.get("list")
    if _is_frequency(list_data):
        list_data = [list_data]
    if list_data is not None:
        if not isinstance(list_data, list) or not all(_is_frequency(item) for item in list_data):
            _frequencies_error(
                run_config_settings_filename,
                '"frequencies: list" is "' + str(list_data) + '" while it should be a list of frequencies in MHz',
                _FREQUENCIES_EXAMPLE,
            )
        custom_freq_list.extend(list_data)

    range_data = frequencies.get("range")
    if range_data is not None and not isinstance(range_data, dict):
        _frequencies_error(
            run_config_settings_filename,
            '"frequencies: range" holds a "' + type(range_data).__name__ + '" while it should hold "from", "to" and "step"',
            _FREQUENCIES_EXAMPLE,
        )
    range_data = range_data or {}
    # A bound the GUI leaves blank is written as "": it is as unset as a missing one.
    bounds = [range_data.get(key) for key in ("from", "to", "step")]
    bounds = [None if bound == "" else bound for bound in bounds]
    if any(bound is not None for bound in bounds):
        missing = [key for key, bound in zip(("from", "to", "step"), bounds) if bound is None]
        if missing:
            _frequencies_error(
                run_config_settings_filename,
                '"frequencies: range" has no "' + '", "'.join(missing) + '"',
                _FREQUENCIES_EXAMPLE,
            )
        lower_bound, upper_bound, step = bounds
        if not ArchitectureHandler.check_bounds(lower_bound, upper_bound, step, synth_type="custom frequency synthesis"):
            raise SystemExit(-1)
        custom_freq_list.extend(ArchitectureHandler.create_list_from_range(lower_bound, upper_bound, step))
    # Keep order stable while removing duplicates.
    custom_freq_list = list(dict.fromkeys(custom_freq_list))
    return custom_freq_list, override_arch_frequencies


######################################
# Run Synthesis
######################################

def run_synthesis(
    run_config_settings_filename,
    arch_path,
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
    custom_freq_list=None,
    debug=False,
    keep=False,
    export_output_dir=None,
    custom_metrics_file=None,
    cancel_event=None,
    detach=False,
    daemon_session=None,
):
    # See run_fmax_synthesis.run_synthesis: every run goes through odatix.run.
    run_cli.execute(run_cli.command_run(
        "custom_freq_synthesis",
        cancel_event=cancel_event,
        settings_file=run_config_settings_filename,
        arch_path=arch_path,
        target_path=target_path,
        work_path=work_path,
        result_path=export_output_dir,
        tool=tool,
        flow=flow,
        until=until_step,
        rerun_from=rerun_from_step,
        overwrite=overwrite,
        noask=noask,
        exit_when_done=exit_when_done,
        log_size_limit=log_size_limit,
        nb_jobs=nb_jobs,
        check_eda_tool=check_eda_tool,
        frequencies=custom_freq_list or [],
        debug=debug,
        keep=keep,
        custom_metrics_file=custom_metrics_file,
        detach=detach,
        session=daemon_session,
    ))

def check_settings(
    run_config_settings_filename,
    arch_path,
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
    selected_targets=None,
    custom_freq_list=None,
    debug=False,
    keep=False,
    cancel_event=None,
    tool_check_sink=None,
):
    _check_cancel(cancel_event)

    if custom_freq_list is None:
        custom_freq_list = []

    cli_custom_freq_list = list(custom_freq_list)
    settings_custom_freq_list, override_arch_frequencies = _load_settings_custom_frequencies(run_config_settings_filename)

    # Priority order:
    # 1) CLI (--at / --from --to --step)
    # 2) settings frequencies when override=true
    # 3) architecture-specific settings
    # 4) fallback frequencies list
    # 5) default frequencies list
    forced_custom_freq_list = cli_custom_freq_list
    if len(forced_custom_freq_list) == 0 and override_arch_frequencies and len(settings_custom_freq_list) > 0:
        forced_custom_freq_list = settings_custom_freq_list

    fallback_custom_freq_list = settings_custom_freq_list if len(settings_custom_freq_list) > 0 else None

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
        synth_type="custom_freq_synthesis",
        flow=flow,
        selected_targets=selected_targets,
        check_cancel=lambda: _check_cancel(cancel_event),
    )

    # A flow can be split into ordered steps: narrow them to what this run
    # covers ("--until"), and let "--rerun-from" force redoing part of what a
    # previous run already did.
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

    arch_handler = ArchitectureHandler(
        work_path=context["work_path"],
        arch_path=arch_path,
        script_path=OdatixSettings.odatix_eda_tools_path,
        log_path=hard_settings.work_log_path,
        work_rtl_path=hard_settings.work_rtl_path,
        work_script_path=hard_settings.work_script_path,
        work_report_path=hard_settings.work_report_path,
        work_log_path=hard_settings.work_log_path,
        process_group=context["process_group"],
        command=context["run_command"],
        eda_target_filename=eda_tools.resolve_target_file(tool, target_path),
        tool=tool,
        flow=context["flow"],
        fmax_status_filename=hard_settings.synth_status_filename,
        frequency_search_filename=hard_settings.frequency_search_filename,
        param_settings_filename=hard_settings.param_settings_filename,
        valid_status=hard_settings.valid_status,
        valid_frequency_search=hard_settings.valid_frequency_search,
        forced_fmax_lower_bound=None,
        forced_fmax_upper_bound=None,
        forced_custom_freq_list=forced_custom_freq_list,
        fallback_custom_freq_list=fallback_custom_freq_list,
        overwrite=context["overwrite"],
        requested_steps=[step["name"] for step in steps] if steps else None,
        rerun_step_index=rerun_index,
        force_single_thread=context["force_single_thread"],
    )

    timestamp = get_timestamp_string()
    architecture_instances = arch_handler.get_architectures(
        context["architectures"],
        context["targets"],
        context["constraint_file"],
        context["install_path"],
        run_mode="custom_freq",
        keep=keep,
        timestamp=timestamp,
    )

    _check_cancel(cancel_event)

    arch_handler.print_summary()

    # The eda tool check was started in the background by load_synthesis_context:
    # its outcome is only needed now, right before the confirmation.
    settle_tool_checks([context["tool_check"]], tool_check_sink)
    confirm_valid_jobs(arch_handler.get_valid_arch_count(), context["ask_continue"], ask_to_continue, script_name=script_name, plan=arch_handler.plan)

    print()

    job_list = []
    prepare_job = build_prepare_synthesis_job(
        arch_handler=arch_handler,
        arch_path=arch_path,
        tool=tool,
        log_size_limit=context["log_size_limit"],
        debug=debug,
        timestamp=timestamp,
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
        arch_handler,
        context["exit_when_done"],
        context["log_size_limit"],
        context["nb_jobs"],
        arch_handler.plan,
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
    export_output_dir=None,
    export_tool=None,
    export_flow=None,
    export_work_path=None,
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

    # Per-job result export (au fil de l'eau): tag every job so the handler
    # exports its result as soon as it finishes, for both the CLI and the
    # GUI/daemon (which both call this prepare function).
    if export_output_dir and export_tool and export_work_path:
        exp_res.configure_synthesis_job_exports(
            parallel_jobs=parallel_jobs,
            result_type="custom_freq_synthesis",
            work_path=export_work_path,
            tool=export_tool,
            flow=export_flow,
            output_dir=export_output_dir,
            custom_metrics_file=custom_metrics_file,
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
    custom_freq_list = list(args.at_freq or [])

    if args.to_freq is not None and (args.from_freq is None or args.step_freq is None):
        printc.error("--to cannot be used without --from and --step", script_name=script_name)
        sys.exit(-1)
    elif args.from_freq is not None and (args.to_freq is None or args.step_freq is None):
        printc.error("--from cannot be used without --to and --step", script_name=script_name)
        sys.exit(-1)
    elif args.step_freq is not None and (args.to_freq is None or args.from_freq is None):
        printc.error("--step cannot be used without --from and --to", script_name=script_name)
        sys.exit(-1)
    elif args.from_freq is not None and args.to_freq is not None and args.step_freq is not None:
        if ArchitectureHandler.check_bounds(args.from_freq, args.to_freq, args.step_freq, synth_type="custom frequency synthesis"):
            range_list = ArchitectureHandler.create_list_from_range(args.from_freq, args.to_freq, args.step_freq)
            custom_freq_list = custom_freq_list + range_list
        else:
            sys.exit(-1)

    run_cli.execute(run_cli.command_run(
        "custom_freq_synthesis",
        workspace=run_cli.command_workspace(args.config, script_name),
        options=RunOptions.from_namespace(args, frequencies=custom_freq_list),
    ))


if __name__ == "__main__":
    args = parse_arguments()
    main(args)

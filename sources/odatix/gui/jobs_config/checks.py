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

"""The two background phases of a run, one function per job type: checking the
settings (which produces the run plan the popup displays), and preparing the
jobs. Both are started in a thread by the run callbacks and publish their
outcome through prepare_state."""

import contextlib

import odatix.components.run_analysis as run_analysis
import odatix.components.run_fmax_synthesis as run_fmax_synthesis
import odatix.components.run_pnr as run_pnr
import odatix.components.run_range_synthesis as run_range_synthesis
import odatix.components.run_simulations as run_simulations
import odatix.components.run_workflow as run_workflow
import odatix.lib.printc as printc

from odatix.gui.jobs_config import prepare_state
from odatix.gui.jobs_config.prepare_state import _collect_tool_check

def _run_check_custom_freq_settings(
    run_config_settings_filename,
    arch_path,
    tool,
    flow,
    until_step,
    work_path,
    target_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
    check_eda_tool,
    custom_freq_list=None,
):
    if custom_freq_list is None:
        custom_freq_list = []
    try:
        with printc.collect(prepare_state._prepare_messages.add), contextlib.redirect_stdout(prepare_state._prepare_log_buffer):
            prepare_state._prepare_check_data = run_range_synthesis.check_settings(
                run_config_settings_filename,
                arch_path,
                tool,
                flow,
                until_step,
                # Re-running an already completed step ("--rerun-from") is
                # CLI-only: from the GUI a run always resumes where it stopped.
                None,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                check_eda_tool,
                custom_freq_list=custom_freq_list,
                debug=False,
                keep=False,
                cancel_event=prepare_state._prepare_cancel_event,
                tool_check_sink=_collect_tool_check,
            )
        prepare_state._prepare_status = {"status": "checked", "error": None}
    except run_range_synthesis.SynthesisCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except Exception as exc:
        prepare_state._prepare_status = {"status": "error", "error": str(exc)}

def _run_check_pnr_settings(
    run_config_settings_filename,
    source_work_root,
    tool,
    flow,
    until_step,
    work_path,
    target_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
    check_eda_tool,
    source_result_types=None,
):
    try:
        with printc.collect(prepare_state._prepare_messages.add), contextlib.redirect_stdout(prepare_state._prepare_log_buffer):
            prepare_state._prepare_check_data = run_pnr.check_settings(
                run_config_settings_filename=run_config_settings_filename,
                source_work_root=source_work_root,
                tool=tool,
                flow=flow,
                until_step=until_step,
                # Re-running an already completed step ("--rerun-from") is
                # CLI-only: from the GUI a run always resumes where it stopped.
                rerun_from_step=None,
                work_path=work_path,
                target_path=target_path,
                overwrite=overwrite_enabled,
                noask=noask,
                exit_when_done=exit_when_done_enabled,
                log_size_limit=log_size_val,
                nb_jobs=nb_jobs_val,
                check_eda_tool=check_eda_tool,
                source_result_types=source_result_types,
                debug=False,
                cancel_event=prepare_state._prepare_cancel_event,
                tool_check_sink=_collect_tool_check,
            )
        prepare_state._prepare_status = {"status": "checked", "error": None}
    except run_pnr.PnrCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except Exception as exc:
        prepare_state._prepare_status = {"status": "error", "error": str(exc)}

def _run_check_fmax_settings(
    run_config_settings_filename,
    arch_path,
    tool,
    flow,
    until_step,
    work_path,
    target_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
    continue_on_error,
    check_eda_tool,
):
    try:
        with printc.collect(prepare_state._prepare_messages.add), contextlib.redirect_stdout(prepare_state._prepare_log_buffer):
            prepare_state._prepare_check_data = run_fmax_synthesis.check_settings(
                run_config_settings_filename,
                arch_path,
                tool,
                flow,
                until_step,
                # Re-running an already completed step ("--rerun-from") is
                # CLI-only: from the GUI a run always resumes where it stopped.
                None,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                continue_on_error,
                check_eda_tool,
                forced_fmax_lower_bound=None,
                forced_fmax_upper_bound=None,
                debug=False,
                keep=False,
                cancel_event=prepare_state._prepare_cancel_event,
                tool_check_sink=_collect_tool_check,
            )
        prepare_state._prepare_status = {"status": "checked", "error": None}
    except run_fmax_synthesis.SynthesisCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except Exception as exc:
        prepare_state._prepare_status = {"status": "error", "error": str(exc)}

def _run_check_analysis_settings(
    run_config_settings_filename,
    arch_path,
    tool,
    flow,
    work_path,
    target_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
    check_eda_tool,
):
    try:
        with printc.collect(prepare_state._prepare_messages.add), contextlib.redirect_stdout(prepare_state._prepare_log_buffer):
            prepare_state._prepare_check_data = run_analysis.check_settings(
                run_config_settings_filename,
                arch_path,
                tool,
                work_path,
                target_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                check_eda_tool,
                debug=False,
                keep=False,
                cancel_event=prepare_state._prepare_cancel_event,
                tool_check_sink=_collect_tool_check,
                flows=run_analysis.parse_flow_selection([flow] if flow else None, tool if isinstance(tool, (list, tuple)) else [tool]),
            )
        prepare_state._prepare_status = {"status": "checked", "error": None}
    except run_analysis.AnalysisCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except SystemExit:
        # check_settings() calls sys.exit(-1) when there is no valid architecture
        # to analyze: turn that into a normal error status.
        prepare_state._prepare_status = {"status": "error", "error": "No valid architecture to analyze. See log above for details."}
    except Exception as exc:
        prepare_state._prepare_status = {"status": "error", "error": str(exc)}

def _run_check_workflow_settings(
    run_config_settings_filename,
    workflow_path,
    work_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
):
    try:
        with printc.collect(prepare_state._prepare_messages.add), contextlib.redirect_stdout(prepare_state._prepare_log_buffer):
            prepare_state._prepare_check_data = run_workflow.check_settings(
                run_config_settings_filename,
                workflow_path,
                work_path,
                overwrite_enabled,
                noask,
                exit_when_done_enabled,
                log_size_val,
                nb_jobs_val,
                debug=False,
                keep=False,
            )
        prepare_state._prepare_status = {"status": "checked", "error": None}
    except SystemExit:
        # check_settings() calls sys.exit(-1) on invalid workflow settings
        # instead of raising: turn that into a normal error status.
        prepare_state._prepare_status = {"status": "error", "error": "Invalid workflow settings. See log above for details."}
    except Exception as exc:
        prepare_state._prepare_status = {"status": "error", "error": str(exc)}

def _run_check_simulation_settings(
    run_config_settings_filename,
    arch_path,
    sim_path,
    work_path,
    overwrite_enabled,
    noask,
    exit_when_done_enabled,
    log_size_val,
    nb_jobs_val,
):
    try:
        with printc.collect(prepare_state._prepare_messages.add), contextlib.redirect_stdout(prepare_state._prepare_log_buffer):
            prepare_state._prepare_check_data = run_simulations.check_settings(
                run_config_settings_filename=run_config_settings_filename,
                arch_path=arch_path,
                sim_path=sim_path,
                work_path=work_path,
                overwrite=overwrite_enabled,
                noask=noask,
                exit_when_done=exit_when_done_enabled,
                log_size_limit=log_size_val,
                nb_jobs=nb_jobs_val,
                debug=False,
                keep=False,
            )
        prepare_state._prepare_status = {"status": "checked", "error": None}
    except SystemExit:
        # check_settings() calls sys.exit(-1) on invalid simulation settings
        # instead of raising: turn that into a normal error status.
        prepare_state._prepare_status = {"status": "error", "error": "Invalid simulation settings. See log above for details."}
    except Exception as exc:
        prepare_state._prepare_status = {"status": "error", "error": str(exc)}

def _run_prepare_synthesis():
    try:
        if not prepare_state._prepare_check_data:
            raise RuntimeError("Missing preparation settings")
        # Per-job export context captured at run time (see the run callback);
        # it lets prepare_* tag every job so the daemon exports results as jobs
        # finish (au fil de l'eau).
        export_ctx = {}
        if isinstance(prepare_state._prepare_runtime_settings, dict):
            export_ctx = prepare_state._prepare_runtime_settings.get("export") or {}
        with printc.collect(prepare_state._prepare_messages.add), contextlib.redirect_stdout(prepare_state._prepare_log_buffer):
            if prepare_state._prepare_synth_type == "simulation":
                (
                    simulation_instances,
                    prepare_job,
                    job_list,
                    exit_when_done,
                    log_size_limit,
                    nb_jobs,
                    _plan,
                ) = prepare_state._prepare_check_data
                prepare_state._prepare_parallel_jobs = run_simulations.prepare_simulations(
                    simulation_instances=simulation_instances,
                    prepare_job=prepare_job,
                    job_list=job_list,
                    exit_when_done=exit_when_done,
                    log_size_limit=log_size_limit,
                    nb_jobs=nb_jobs,
                    export_output_dir=export_ctx.get("output_dir"),
                    export_work_root=export_ctx.get("work_root"),
                    export_sim_path=export_ctx.get("sim_path"),
                )
            elif prepare_state._prepare_synth_type == "workflow":
                (
                    workflow_instances,
                    prepare_job,
                    job_list,
                    exit_when_done,
                    log_size_limit,
                    nb_jobs,
                    _plan,
                ) = prepare_state._prepare_check_data
                prepare_state._prepare_parallel_jobs = run_workflow.prepare_workflows(
                    workflow_instances=workflow_instances,
                    prepare_job=prepare_job,
                    job_list=job_list,
                    exit_when_done=exit_when_done,
                    log_size_limit=log_size_limit,
                    nb_jobs=nb_jobs,
                    export_output_dir=export_ctx.get("output_dir"),
                    export_work_root=export_ctx.get("work_root"),
                    export_workflow_path=export_ctx.get("workflow_path"),
                )
            else:
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
                ) = prepare_state._prepare_check_data
                if prepare_state._prepare_synth_type == "fmax_synthesis":
                    prepare_state._prepare_parallel_jobs = run_fmax_synthesis.prepare_synthesis(
                        architecture_instances=architecture_instances,
                        prepare_job=prepare_job,
                        job_list=job_list,
                        tool_settings_file=tool_settings_file,
                        arch_handler=arch_handler,
                        exit_when_done=exit_when_done,
                        log_size_limit=log_size_limit,
                        nb_jobs=nb_jobs,
                        cancel_event=prepare_state._prepare_cancel_event,
                        export_output_dir=export_ctx.get("output_dir"),
                        export_tool=export_ctx.get("tool"),
                        export_flow=export_ctx.get("flow"),
                        export_work_path=export_ctx.get("work_path"),
                        use_benchmark=export_ctx.get("use_benchmark", False),
                        benchmark_file=export_ctx.get("benchmark_file"),
                    )
                elif prepare_state._prepare_synth_type == "pnr":
                    # Explicit rather than left to the fallback below: a place &
                    # route batch sent to run_range_synthesis would be exported
                    # as custom frequency synthesis results, writing wrong
                    # records without ever failing.
                    prepare_state._prepare_parallel_jobs = run_pnr.prepare_pnr(
                        architecture_instances=architecture_instances,
                        prepare_job=prepare_job,
                        job_list=job_list,
                        tool_settings_file=tool_settings_file,
                        arch_handler=arch_handler,
                        exit_when_done=exit_when_done,
                        log_size_limit=log_size_limit,
                        nb_jobs=nb_jobs,
                        cancel_event=prepare_state._prepare_cancel_event,
                        export_output_dir=export_ctx.get("output_dir"),
                        export_tool=export_ctx.get("tool"),
                        export_flow=export_ctx.get("flow"),
                        export_work_path=export_ctx.get("work_path"),
                        use_benchmark=export_ctx.get("use_benchmark", False),
                        benchmark_file=export_ctx.get("benchmark_file"),
                    )
                elif prepare_state._prepare_synth_type == "analyze":
                    prepare_state._prepare_parallel_jobs = run_analysis.prepare_synthesis(
                        architecture_instances=architecture_instances,
                        prepare_job=prepare_job,
                        job_list=job_list,
                        tool_settings_file=tool_settings_file,
                        arch_handler=arch_handler,
                        exit_when_done=exit_when_done,
                        log_size_limit=log_size_limit,
                        nb_jobs=nb_jobs,
                        cancel_event=prepare_state._prepare_cancel_event,
                        export_output_dir=export_ctx.get("output_dir"),
                        analysis_work_root=export_ctx.get("analysis_work_root"),
                        flows=export_ctx.get("flows"),
                    )
                else:
                    prepare_state._prepare_parallel_jobs = run_range_synthesis.prepare_synthesis(
                        architecture_instances=architecture_instances,
                        prepare_job=prepare_job,
                        job_list=job_list,
                        tool_settings_file=tool_settings_file,
                        arch_handler=arch_handler,
                        exit_when_done=exit_when_done,
                        log_size_limit=log_size_limit,
                        nb_jobs=nb_jobs,
                        cancel_event=prepare_state._prepare_cancel_event,
                        export_output_dir=export_ctx.get("output_dir"),
                        export_tool=export_ctx.get("tool"),
                        export_flow=export_ctx.get("flow"),
                        export_work_path=export_ctx.get("work_path"),
                        use_benchmark=export_ctx.get("use_benchmark", False),
                        benchmark_file=export_ctx.get("benchmark_file"),
                    )
        prepare_state._prepare_status = {"status": "prepared", "error": None}
    except run_range_synthesis.SynthesisCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except run_fmax_synthesis.SynthesisCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except run_analysis.AnalysisCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except run_pnr.PnrCancelled:
        prepare_state._prepare_status = {"status": "canceled", "error": None}
    except SystemExit:
        # abort_if_empty_job_list() calls sys.exit(-1) when every selected job
        # failed while being built (e.g. a missing design_path): turn that into
        # a normal error status instead of silently launching an empty session.
        prepare_state._prepare_status = {"status": "error", "error": "None of the selected jobs could be prepared. See log above for details."}
    except Exception as exc:
        prepare_state._prepare_status = {"status": "error", "error": str(exc)}

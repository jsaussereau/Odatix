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
Preparation of the work directory of a place & route job.

A place & route job is prepared like any other — the same scripts are copied in,
the same identity files are written, the same tcl settings are patched — minus
everything that only makes sense when starting from the RTL: no rtl directory, no
design copy, no parameter replacement. What it gains instead is the link to the
synthesis it continues: the tcl settings point at that job's netlist and sdc, the
command can reach it through $source_work_path, and "pnr.yml" records it so a
later export can tell where the result came from without re-deriving it from the
path.
"""

import os

import yaml

import odatix.lib.hard_settings as hard_settings
import odatix.lib.job_steps as job_steps
import odatix.lib.printc as printc
from odatix.components.synthesis_common import (
    build_job_command,
    build_job_variables,
    build_parallel_job,
    copy_job_scripts,
    load_synthesis_context,
    prepare_job_directory,
    rewrite_tcl_source_paths,
    write_job_identity_files,
)
from odatix.lib.prepare_work import edit_config_file, edit_pnr_config_file
from odatix.lib.run_settings import get_pnr_settings

script_name = os.path.basename(__file__)


def load_pnr_context(
    run_config_settings_filename,
    tool,
    work_path,
    target_path,
    overwrite,
    noask,
    exit_when_done,
    log_size_limit,
    nb_jobs,
    check_eda_tool,
    debug=False,
    flow=None,
    check_cancel=None,
):
    """
    Load what a place & route run needs to build its job list: the run settings
    (its "sources" ride in context["architectures"]), the tool's targets, and the
    command or steps its flow runs.
    """
    return load_synthesis_context(
        run_config_settings_filename=run_config_settings_filename,
        arch_path=None,
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
        synth_type="pnr",
        flow=flow,
        check_cancel=check_cancel,
        settings_reader=get_pnr_settings,
        selection_key="sources",
        selection_noun="place & route sources",
    )


def write_pnr_source_file(arch_instance, source, tool, flow):
    """
    Record in the job directory which synthesis it started from.

    The path already says it, but re-deriving it from the path means knowing
    where the tool name stops and the flow begins; a full re-export reads this
    file instead (see export_results.process_configuration).
    """
    payload = {
        "source_type": source.job_type,
        "source_tool": source.tool,
        "source_flow": source.flow,
        "source_work_dirname": source.work_dirname,
        "source_path": os.path.realpath(source.job_dir),
        "target": source.target,
        "architecture": source.architecture,
        "configuration": source.configuration,
        "frequency": source.frequency,
        "tool": tool,
        "flow": flow,
    }
    with open(os.path.join(arch_instance.tmp_dir, hard_settings.pnr_source_filename), "w") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False)


def read_pnr_source_file(job_dir):
    """
    Read back what write_pnr_source_file recorded, or {} when the job directory
    holds no such file.
    """
    path = os.path.join(str(job_dir), hard_settings.pnr_source_filename)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r") as f:
            data = yaml.load(f, Loader=yaml.loader.SafeLoader)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def build_prepare_pnr_job(
    arch_handler,
    tool,
    log_size_limit,
    progress_mode,
    script_name,
    flow=None,
    steps=None,
    rerun_index=None,
    check_cancel=None,
):
    """
    Build the function preparing one place & route job directory.

    Same contract as synthesis_common.build_prepare_synthesis_job: returns a
    _prepare_job(arch_instance, job_list) the shared preparation loop calls for
    every instance the handler produced.
    """

    def _prepare_job(arch_instance, job_list):
        if check_cancel is not None:
            check_cancel()

        source = getattr(arch_instance, "pnr_source", None)
        if source is None:
            printc.error("Place & route job without a source synthesis", script_name)
            return

        # The synthesis may have been cleaned, or run with a flow that does not
        # write the handoff files, since the job list was built.
        missing = source.missing_handoff_files()
        if missing:
            printc.error(
                'The synthesis "' + source.selector + '" did not write ' + ", ".join(os.path.basename(path) for path in missing),
                script_name,
            )
            printc.note(
                "A synthesis flow can only feed a place & route job if it writes its netlist, sdc and sdf "
                "under the names Odatix expects (see $netlist_file, $sdc_file and $sdf_file in settings.tcl).",
                script_name,
            )
            return

        if arch_handler.overwrite:
            resume_index = 0
        else:
            resume_index = job_steps.start_index(arch_instance.tmp_dir, steps, rerun_index) if steps else 0
        resuming = resume_index > 0

        prepare_job_directory(arch_instance, resuming)

        if not copy_job_scripts(arch_instance, tool, resuming, script_name):
            return

        write_job_identity_files(arch_instance, flow)
        write_pnr_source_file(arch_instance, source, tool, flow)

        tcl_config_file = os.path.join(arch_instance.tmp_script_path, hard_settings.tcl_config_filename)
        edit_config_file(arch_instance, tcl_config_file)
        edit_pnr_config_file(arch_instance, source, tcl_config_file)

        from odatix.lib.architecture_handler import Architecture

        yaml_config_file = os.path.join(arch_instance.tmp_dir, hard_settings.yaml_config_filename)
        Architecture.write_yaml(arch_instance, yaml_config_file)

        rewrite_tcl_source_paths(arch_instance, check_cancel)

        variables = build_job_variables(
            arch_instance,
            tool,
            source_work_path=os.path.realpath(source.job_dir),
            source_tool=str(source.tool),
        )
        command = build_job_command(arch_handler.command, steps, variables)

        running_job = build_parallel_job(
            arch_instance,
            command=command,
            steps=steps,
            resume_index=resume_index,
            flow=flow,
            log_size_limit=log_size_limit,
            progress_mode=progress_mode,
        )

        # Where this job's result belongs, so the per-job export does not have to
        # re-derive it from the path (which it cannot, the source tool level
        # varying from one job of the same batch to the next).
        running_job.export_coordinates = {
            "input_tool_path": os.path.realpath(os.path.join(arch_handler.work_path, source.work_dirname)),
            "target": source.target,
            "architecture": source.architecture,
            "configuration": source.configuration,
            "frequency": source.frequency_segment,
            "source": {
                "source_type": source.job_type,
                "source_tool": source.tool,
                "source_flow": source.flow,
            },
        }

        job_list.append(running_job)

    return _prepare_job

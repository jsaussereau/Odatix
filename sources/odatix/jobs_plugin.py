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
What Odatix plugs into its job handler, jobtender.

The handler knows nothing of Odatix: it runs commands, shows their logs and
their progress, and calls back what a job names when it is over. This module
gives those names their meaning -- the exports of each kind of run, the
derived metrics of a batch, the progress of an fmax search -- and the settings
Odatix runs its sessions with. It is imported with the odatix package, and by
every daemon Odatix starts (handed to it with --plugin).

Everything Odatix-specific is imported when first used: this module is loaded
by every odatix command, and most of them never export anything.
"""

import os

from jobtender import config, plugins

PLUGIN = __name__

config.configure(
    # What the messages call the program and its commands: "odatix ps", the
    # Monitor page of the GUI...
    app_name="Odatix",
    cli_name="odatix",
    commands={"start": "daemon", "list": "ps"},
    other_monitors=["the Monitor page of odatix-gui"],
    access_setting_hint="'session_access' in odatix.yml, or --session-access",
    # Where its sessions live, as they always have.
    workspace_marker="odatix.yml",
    state_dirname=".odatix_sessions",
    env_prefix="ODATIX",
    runtime_dirname="odatix",
    # "ps" before it had that name was "ls".
    remote_list_commands=(("ps",), ("ls",)),
    # Sessions started before the job handler became jobtender.
    legacy_server_modules=("odatix.lib.parallel_job_handler.daemon_server",),
    plugins=[PLUGIN],
)


######################################
# Exports
######################################

def _export_synthesis(job, export_config=None):
    from odatix.components.export_results import export_single_job_result
    return export_single_job_result(job=job, export_config=export_config)


def _export_workflow(job, export_config=None):
    from odatix.components.export_workflow_results import export_single_workflow_job
    return export_single_workflow_job(job=job, export_config=export_config)


def _export_simulation(job, export_config=None):
    from odatix.components.export_simulation_results import export_single_simulation_job
    return export_single_simulation_job(job=job, export_config=export_config)


def _export_analysis(job, export_config=None):
    from odatix.components.export_analysis import export_single_analysis_job
    return export_single_analysis_job(job=job, export_config=export_config)


plugins.register_post_run("synthesis", _export_synthesis)
plugins.register_post_run("workflow", _export_workflow)
plugins.register_post_run("simulation", _export_simulation)
plugins.register_post_run("analysis", _export_analysis)


def _derived_metrics(action):
    derived_metrics_file = action.get("derived_metrics_file")
    if derived_metrics_file and os.path.isfile(derived_metrics_file):
        from odatix.components.export_derived_metrics import apply_derived_metrics
        apply_derived_metrics(action.get("result_path"), derived_metrics_file)


plugins.register_post_batch("derived_metrics", _derived_metrics)


class _ResultsBuffer(object):
    """The exports write the results files through odatix.lib.results_cache."""

    def deferred(self, interval_s):
        import odatix.lib.results_cache as results_cache
        return results_cache.deferred_writes(interval_s)

    def flush(self):
        import odatix.lib.results_cache as results_cache
        results_cache.flush()

    def flush_due(self):
        import odatix.lib.results_cache as results_cache
        results_cache.flush_due()


plugins.register_service("export_buffer", _ResultsBuffer())


######################################
# Steps a run can resume after
######################################

class _StepStore(object):
    """The steps of a job that are done, kept by odatix.lib.job_steps."""

    def record(self, tmp_dir, step_name, flow=None):
        import odatix.lib.job_steps as job_steps
        job_steps.record_completed_step(tmp_dir, step_name, flow=flow)

    def forget_from(self, tmp_dir, index=0):
        import odatix.lib.job_steps as job_steps
        return job_steps.forget_steps_from(tmp_dir, index)

    def count(self, tmp_dir):
        import odatix.lib.job_steps as job_steps
        return len(job_steps.completed_step_names(tmp_dir))


plugins.register_service("step_store", _StepStore())


######################################
# Progress of an fmax search
######################################

def _extract_fmax_status(content, pattern):
    """(progress of the search, its step, its number of steps) from a status file, or None."""
    if pattern is None:
        return None

    for line in reversed(content.splitlines()):
        line_tail = line[-4096:]
        parts = pattern.search(line_tail)
        if parts is None:
            continue
        if len(parts.groups()) < 4:
            continue
        try:
            return int(parts.group(2)), int(parts.group(3)), int(parts.group(4))
        except (TypeError, ValueError):
            continue

    content_tail = content[-65536:]
    parts = pattern.search(content_tail)
    if parts is None or len(parts.groups()) < 4:
        return None
    try:
        return int(parts.group(2)), int(parts.group(3)), int(parts.group(4))
    except (TypeError, ValueError):
        return None


def _fmax_progress(job):
    """
    An fmax search runs one synthesis per step: its progress is the steps
    done, read from the status file, plus the share of the running synthesis.
    """
    progress_pattern, status_pattern = job.patterns()

    fmax_progress = 0
    fmax_totalstep = 1
    content = job._read_status_file(job.status_file)
    if content is not None:
        parsed_fmax_status = _extract_fmax_status(content, status_pattern)
        if parsed_fmax_status is not None:
            fmax_progress, _fmax_step, fmax_totalstep = parsed_fmax_status

    synth_progress = 0
    content = job._read_status_file(job.progress_file)
    if content is not None:
        parsed_synth_progress = job._extract_int_from_pattern(
            content,
            progress_pattern,
            default_group_index=1,
        )
        if parsed_synth_progress is not None:
            synth_progress = parsed_synth_progress

    if fmax_totalstep != 0:
        return fmax_progress + synth_progress / fmax_totalstep
    return synth_progress


plugins.register_progress("fmax", _fmax_progress)


######################################
# Session settings
######################################

def _version():
    from odatix.components.motd import read_version
    return read_version()


def _resource_guard_defaults():
    from odatix.lib.settings import OdatixSettings
    return OdatixSettings.resource_guard_settings or (
        OdatixSettings.DEFAULT_RESOURCE_GUARD,
        OdatixSettings.DEFAULT_CPU_LIMIT,
        OdatixSettings.DEFAULT_MEM_LIMIT,
    )


def _daemon_pythonpath(workspace_root):
    """A workspace holding the sources of Odatix runs its daemons on them."""
    sources_dir = os.path.join(str(workspace_root), "sources")
    if os.path.isdir(os.path.join(sources_dir, "odatix")):
        return [sources_dir]
    return []


plugins.register_service("version", _version)
plugins.register_service("resource_guard_defaults", _resource_guard_defaults)
plugins.register_service("daemon_pythonpath", _daemon_pythonpath)


# Imported directly (with the odatix package) rather than through
# plugins.load(): mark it loaded all the same.
plugins.load([PLUGIN])

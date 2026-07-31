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

"""Reading the current (possibly unsaved) state of the page back into the settings
dict the settings file uses, and writing it to a temporary file so a run can use
it without saving."""

import os
import tempfile

import odatix.components.workspace as workspace
from odatix.lib.utils import AUTO_NB_JOBS_KEYWORD, is_auto_nb_jobs

from odatix.gui.jobs_config.common import (
    _JOB_SETTINGS_DEFAULTS,
    _checklist_enabled,
    _to_int,
)
from odatix.gui.jobs_config.simulation import _collect_simulation_selection

def _nb_jobs_setting(nb_jobs, auto_enabled):
    """Return the persisted nb_jobs value: the "auto" keyword when the Auto
    switch is on, otherwise the integer entered in the widget."""
    if auto_enabled:
        return AUTO_NB_JOBS_KEYWORD
    return _to_int(nb_jobs, _JOB_SETTINGS_DEFAULTS["nb_jobs"])

def _job_settings_current(overwrite, force_single_thread, nb_jobs, log_size_limit, ask_continue, exit_when_done, auto_nb_jobs=None) -> dict:
    """Job Settings as edited in the widgets (used for the 'current' selection)."""
    return {
        "overwrite": _checklist_enabled(overwrite),
        "force_single_thread": _checklist_enabled(force_single_thread),
        "nb_jobs": _nb_jobs_setting(nb_jobs, _checklist_enabled(auto_nb_jobs)),
        "log_size_limit": _to_int(log_size_limit, _JOB_SETTINGS_DEFAULTS["log_size_limit"]),
        "ask_continue": _checklist_enabled(ask_continue),
        "exit_when_done": _checklist_enabled(exit_when_done),
    }


def _collect_run_settings(
    run_mode,
    selection_key,
    switch_values,
    switch_ids,
    preview_values,
    preview_ids,
    overwrite,
    force_single_thread,
    nb_jobs,
    auto_nb_jobs,
    log_size_limit,
    ask_continue,
    exit_when_done,
    override_arch_frequencies,
    use_custom_freq_list,
    target_frequencies,
    use_custom_freq_range,
    from_frequency,
    to_frequency,
    step_frequency,
    lower_bound,
    upper_bound,
    analysis_tools,
    sim_selection_values=None,
    sim_selection_ids=None,
) -> dict:
    """
    Build the settings dict that reflects the current, possibly unsaved, state of
    the page: the enabled architectures/configurations, the job settings, and the
    mode-specific frequency/tool fields. Shared by the "Save" callback and the
    "Run" callback (which writes it to a temporary file to run without saving).
    """
    if run_mode == "simulation":
        # Simulations hold a mapping, not a flat list (see
        # _collect_simulation_selection), so they short-circuit the shared
        # architecture/preview flattening below.
        return {
            selection_key: _collect_simulation_selection(
                switch_values, switch_ids, sim_selection_values, sim_selection_ids
            ),
            **_job_settings_current(
                overwrite, force_single_thread, nb_jobs, log_size_limit, ask_continue, exit_when_done,
                auto_nb_jobs=auto_nb_jobs,
            ),
        }

    if run_mode == "pnr":
        # Place & route cards hold their selection in the same per-instance store
        # simulations use (see _pnr_job_sections), but write it as the flat
        # selector list the settings file expects.
        enabled_tools = {
            sid.get("arch")
            for value, sid in zip(switch_values or [], switch_ids or [])
            if isinstance(sid, dict) and bool(value)
        }
        selectors = []
        for value, pid in zip(sim_selection_values or [], sim_selection_ids or []):
            if not isinstance(pid, dict) or pid.get("sim") not in enabled_tools:
                continue
            selectors.extend(str(entry) for entry in (value or []) if entry is not None)
        return {
            selection_key: list(dict.fromkeys(selectors)),
            **_job_settings_current(
                overwrite, force_single_thread, nb_jobs, log_size_limit, ask_continue, exit_when_done,
                auto_nb_jobs=auto_nb_jobs,
            ),
        }

    preview_by_arch = {}
    for val, pid in zip(preview_values or [], preview_ids or []):
        arch = pid.get("arch") if isinstance(pid, dict) else None
        if arch:
            preview_by_arch[arch] = list(val or [])

    architectures = []
    for val, sid in zip(switch_values or [], switch_ids or []):
        arch = sid.get("arch") if isinstance(sid, dict) else None
        if arch and bool(val):
            for item in preview_by_arch.get(arch, []):
                if item is not None:
                    architectures.append(str(item))
    # Remove duplicates but keep order
    architectures = list(dict.fromkeys(architectures))

    current_settings = {
        selection_key: architectures,
        **_job_settings_current(overwrite, force_single_thread, nb_jobs, log_size_limit, ask_continue, exit_when_done, auto_nb_jobs=auto_nb_jobs),
    }
    if run_mode == "custom_freq_synthesis":
        current_settings["frequencies"] = workspace.create_custom_frequencies_settings_dict(
            _checklist_enabled(override_arch_frequencies),
            target_frequencies,
            from_frequency,
            to_frequency,
            step_frequency,
            use_custom_freq_list=_checklist_enabled(use_custom_freq_list),
            use_custom_freq_range=_checklist_enabled(use_custom_freq_range),
        )
    if run_mode == "fmax_synthesis":
        current_settings["fmax_synthesis"] = workspace.create_fmax_bounds_settings_dict(
            lower_bound,
            upper_bound,
            override_enabled=_checklist_enabled(override_arch_frequencies),
        )
    if run_mode == "analyze":
        current_settings["tools"] = [tool for tool in (analysis_tools or []) if tool]

    return current_settings


def _write_temp_run_settings(settings_path, current_settings, run_mode, use_custom_freq_list, use_custom_freq_range):
    """
    Write the current (unsaved) page settings to a temporary settings file so a
    run can use them without touching the real settings file, and return its
    path. The real file's other keys are preserved (loaded and overlaid).
    """
    base_settings = workspace.load_arch_selection_settings(settings_path) if settings_path else {}
    payload = {**(base_settings or {}), **current_settings}

    fd, temp_path = tempfile.mkstemp(prefix="odatix_run_", suffix=".yml")
    os.close(fd)
    workspace.save_architecture_selection(
        temp_path,
        payload,
        run_mode=run_mode,
        use_custom_freq_list=use_custom_freq_list,
        use_custom_freq_range=use_custom_freq_range,
    )
    return temp_path


def _job_settings_baseline(settings: dict) -> dict:
    """Job Settings as loaded from the settings file (used for the saved
    baseline). Must mirror how job_settings_form() initializes the widgets."""
    settings = settings or {}
    nb_jobs_raw = settings.get("nb_jobs", _JOB_SETTINGS_DEFAULTS["nb_jobs"])
    return {
        "overwrite": bool(settings.get("overwrite", _JOB_SETTINGS_DEFAULTS["overwrite"])),
        "force_single_thread": bool(settings.get("force_single_thread", _JOB_SETTINGS_DEFAULTS["force_single_thread"])),
        "nb_jobs": AUTO_NB_JOBS_KEYWORD if is_auto_nb_jobs(nb_jobs_raw) else _to_int(nb_jobs_raw, _JOB_SETTINGS_DEFAULTS["nb_jobs"]),
        "log_size_limit": _to_int(settings.get("log_size_limit", _JOB_SETTINGS_DEFAULTS["log_size_limit"]), _JOB_SETTINGS_DEFAULTS["log_size_limit"]),
        "ask_continue": bool(settings.get("ask_continue", _JOB_SETTINGS_DEFAULTS["ask_continue"])),
        "exit_when_done": bool(settings.get("exit_when_done", _JOB_SETTINGS_DEFAULTS["exit_when_done"])),
    }

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
import re
import tempfile

from odatix.workspace.jobs import FmaxBoundsSettings, FrequenciesSettings, job_config
from odatix.workspace.settings import Settings
from odatix.workspace.yaml_io import read_text, read_yaml, write_text
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
        current_settings["frequencies"] = FrequenciesSettings(
            override=_checklist_enabled(override_arch_frequencies),
            frequencies=target_frequencies,
            range={"from": from_frequency, "to": to_frequency, "step": step_frequency},
            use_custom_freq_list=_checklist_enabled(use_custom_freq_list),
            use_custom_freq_range=_checklist_enabled(use_custom_freq_range),
        ).to_dict()
    if run_mode == "fmax_synthesis":
        current_settings["fmax_synthesis"] = FmaxBoundsSettings(
            override=_checklist_enabled(override_arch_frequencies),
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        ).to_dict()
    if run_mode == "analyze":
        current_settings["tools"] = [tool for tool in (analysis_tools or []) if tool]

    return current_settings


def _write_temp_run_settings(settings_path, current_settings, run_mode, use_custom_freq_list, use_custom_freq_range):
    """
    Write the current (unsaved) page settings to a temporary settings file so a
    run can use them without touching the real settings file, and return its
    path. The real file's other keys are preserved (loaded and overlaid).
    """
    base_settings = job_config(settings_path, run_mode).settings.to_dict() if settings_path else {}
    payload = {**base_settings, **current_settings}

    fd, temp_path = tempfile.mkstemp(prefix="odatix_run_", suffix=".yml")
    os.close(fd)
    # The file is empty: it is written whole, not merged into.
    write_run_settings(temp_path, payload, run_mode, use_custom_freq_list, use_custom_freq_range, fresh=True)
    return temp_path


def _merge_settings(settings, values):
    """
    Set on `settings` the values the page holds, key by key and into the nested
    blocks ("frequencies", "fmax_synthesis") rather than replacing them: the
    settings keep knowing what their file said, which is what lets the file be
    updated in place. A key the run mode does not declare is left out, so a key
    belonging to another run mode never leaks in.
    """
    declared = set(spec.key for spec in settings.specs())
    for key, value in values.items():
        if key not in declared:
            continue
        current = settings[key]
        if isinstance(current, Settings) and isinstance(value, dict):
            _merge_settings(current, value)
        else:
            settings[key] = value


_TOP_LEVEL_KEY = re.compile(r"^[^\s#-][^:]*:")
_DOCUMENT_MARKER = re.compile(r"^(---|\.\.\.)\s*$")
_ACTIVE_ITEM = re.compile(r"^(\s*)-\s+(.*?)(\s+#.*)?$")
_COMMENTED_ITEM = re.compile(r"^(\s*)#\s*-\s*(\S.*?)(\s+#.*)?$")


def _item_value(text):
    """The entry a list line names, without the quotes it may be written with."""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    return text


def _edit_selection_text(text, key, selection):
    """
    The text of a run settings file whose `key` list holds `selection`, edited
    the way its author would: an entry no longer selected is commented out where
    it is, a commented-out entry selected again is uncommented where it is, and
    only an entry the file never mentioned is added, after the last selected
    one. The comments and the catalogue of commented-out entries of the file stay
    exactly as they were.

    Returns None when the list is not a block list this can edit ("key: []",
    an inline list), for the caller to write it the usual way.
    """
    lines = text.splitlines(True)
    start = None
    for index, line in enumerate(lines):
        if re.match(r"^" + re.escape(key) + r":\s*(#.*)?$", line.rstrip("\n")):
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index].rstrip("\n")
        if _TOP_LEVEL_KEY.match(line) or _DOCUMENT_MARKER.match(line):
            end = index
            break

    wanted = [str(entry) for entry in selection]
    kept = set()
    last_item = None
    indent = "  "
    for index in range(start + 1, end):
        line = lines[index].rstrip("\n")
        newline = lines[index][len(line):]
        match = _ACTIVE_ITEM.match(line)
        if match:
            indent = match.group(1)
            value = _item_value(match.group(2))
            if value in wanted and value not in kept:
                kept.add(value)
                last_item = index
            else:
                lines[index] = match.group(1) + "# - " + line[len(match.group(1)):].lstrip()[1:].lstrip() + newline
    for index in range(start + 1, end):
        line = lines[index].rstrip("\n")
        match = _COMMENTED_ITEM.match(line)
        if not match:
            continue
        value = _item_value(match.group(2))
        if value in wanted and value not in kept:
            kept.add(value)
            newline = lines[index][len(line):]
            lines[index] = match.group(1) + "- " + match.group(2) + (match.group(3) or "") + newline
            last_item = index if last_item is None else max(last_item, index)
    missing = [value for value in wanted if value not in kept]
    if not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    # Where the file lists the configurations of an architecture is where a new
    # entry of it goes ("Counter/*" next to "Counter/04bits", ...); an entry of an
    # architecture the file never mentions goes after the last selected one.
    for value in reversed(missing):
        design = value.split("/")[0].split("+")[0].strip()
        position = None
        for index in range(start + 1, end):
            line = lines[index].rstrip("\n")
            match = _ACTIVE_ITEM.match(line) or _COMMENTED_ITEM.match(line)
            if match and _item_value(match.group(2)).split("/")[0].split("+")[0].strip() == design:
                position = index
                break
        if position is None:
            position = (last_item if last_item is not None else start) + 1
        lines.insert(position, indent + "- " + value + "\n")
        end += 1
        if last_item is not None and position <= last_item:
            last_item += 1
    return "".join(lines)


def _write_selection_in_place(settings_path, key, selection):
    """
    Write the selection of a run settings file by editing its text (see
    _edit_selection_text), then read it back: the list as the file now holds it,
    in the file's order, or None when the file was left untouched for the usual
    writer to handle.
    """
    previous = read_text(settings_path)
    if not previous or not isinstance(selection, list):
        return None
    edited = _edit_selection_text(previous, key, selection)
    if edited is None:
        return None
    if edited != previous:
        write_text(settings_path, edited)
    written = (read_yaml(settings_path, default={}) or {}).get(key)
    if not isinstance(written, list) or set(map(str, written)) != set(map(str, selection)):
        # Not what was asked for: put the file back and let the writer do it.
        write_text(settings_path, previous)
        return None
    return written


def write_run_settings(settings_path, payload, run_mode, use_custom_freq_list=False, use_custom_freq_range=False, fresh=False):
    """
    Write a run settings file from what the page holds.

    An existing file is updated in place: only what changed is rewritten, and
    its comments, its commented-out entries (the catalogue of examples the
    tutorials ask to uncomment) and the keys Odatix does not know stay as they
    were. `fresh` writes the file whole instead, for a file that holds nothing
    yet (the temporary file a run reads).
    """
    config = job_config(settings_path, run_mode)
    if fresh:
        config.settings = payload
        config.settings.extra.clear()
    else:
        # A list rewritten whole would take the comments between its entries
        # with it: the selection is edited in the text first, so that the file
        # already holds it when the other settings are written.
        key = config.selection_key
        payload = dict(payload)
        written = _write_selection_in_place(settings_path, key, payload.get(key))
        if written is not None:
            payload[key] = written
            config.reload()
        _merge_settings(config.settings, payload)
    if run_mode == "custom_freq_synthesis":
        config.settings.frequencies.use_custom_freq_list = use_custom_freq_list
        config.settings.frequencies.use_custom_freq_range = use_custom_freq_range
    config.save(regenerate=fresh)
    return settings_path


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

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

"""Page path, constants and helpers shared by every part of the "Run jobs" page."""

from typing import Optional

from dash import html

from odatix.workspace.jobs import job_config
import odatix.lib.eda_tools as eda_tools
import odatix.lib.hard_settings as hard_settings
from odatix.gui.utils import get_key_from_url
from odatix.lib.settings import OdatixSettings

page_path = "/run_jobs"

MAX_PREVIEW_COMBINATIONS = 10000

# Display labels of the job types the page can be opened with (?type=...),
# shown as a tag in the summary strip of the header.
RUN_MODE_LABELS = {
    "fmax_synthesis": "Fmax synthesis",
    "custom_freq_synthesis": "Custom frequency synthesis",
    "pnr": "Place & route",
    "analyze": "RTL analysis",
    "workflow": "Workflow",
    "simulation": "Simulation",
}

def _analysis_tools():
    """Discovered eda tools that support the RTL analysis job type."""
    return eda_tools.tools_supporting("analysis")


def _analysis_tool_options():
    """Checklist options for the analysis 'Tools' tile, one per discovered tool
    that supports the analysis job type."""
    return [
        {"label": eda_tools.get_tool_label(tool), "value": tool}
        for tool in _analysis_tools()
    ]

def _normalize_session_selector(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text == "__new_session__":
        return None
    return text


def _session_option(daemon: dict) -> dict:
    host = str(daemon.get("host", hard_settings.daemon_default_host))
    port = int(daemon.get("port", hard_settings.daemon_default_port))
    session_id = str(daemon.get("session_id", "")).strip()
    session_name = str(daemon.get("session_name", "")).strip()

    value = session_id or session_name or f"{host}:{port}"
    label = session_id or session_name or f"{host}:{port}"
    return {
        "label": label,
        "value": value,
        "title": f"{host}:{port}",
    }

def _checklist_enabled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return True in value or len(value) > 0
    return bool(value)

def _to_int(value, default):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default

# The "Job Settings" fields, with the defaults used both to initialize the
# widgets (job_settings_form) and to build the saved baseline, so a fresh load
# never falsely reports "unsaved changes".
_JOB_SETTINGS_DEFAULTS = {
    "overwrite": False,
    "force_single_thread": True,
    "nb_jobs": 8,
    "log_size_limit": 300,
    "ask_continue": True,
    "exit_when_done": False,
}

def _get_synth_settings_path(search: str, odatix_settings: dict) -> str:
    run_mode = get_key_from_url(search, "type")
    if run_mode == "custom_freq_synthesis":
        return odatix_settings.get(
            "custom_freq_synthesis_settings_file",
            OdatixSettings.DEFAULT_CUSTOM_FREQ_SYNTHESIS_SETTINGS_FILE,
        )
    if run_mode == "fmax_synthesis":
        return odatix_settings.get(
            "fmax_synthesis_settings_file",
            OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
        )
    if run_mode == "pnr":
        return odatix_settings.get(
            "pnr_settings_file",
            OdatixSettings.DEFAULT_PNR_SETTINGS_FILE,
        )
    if run_mode == "analyze":
        return odatix_settings.get(
            "analysis_settings_file",
            OdatixSettings.DEFAULT_ANALYSIS_SETTINGS_FILE,
        )
    if run_mode == "simulation":
        return odatix_settings.get(
            "simulation_settings_file",
            OdatixSettings.DEFAULT_SIMULATION_SETTINGS_FILE,
        )
    if run_mode == "workflow":
        # Without this, the Job Settings form of a workflow run would be filled
        # from the fmax synthesis settings file while the selection is saved to
        # the workflow one: the page would always claim "unsaved changes" and
        # Save would overwrite the workflow settings with the fmax values.
        return odatix_settings.get(
            "workflow_settings_file",
            OdatixSettings.DEFAULT_WORKFLOW_SETTINGS_FILE,
        )
    return odatix_settings.get(
        "fmax_synthesis_settings_file",
        OdatixSettings.DEFAULT_FMAX_SYNTHESIS_SETTINGS_FILE,
    )

def _select_all_buttons(button_type: str, id_keys: dict) -> html.Div:
    """Build a 'Select all' / 'Clear' button pair for a checklist.

    button_type is the pattern-matching id "type"; id_keys holds the other
    wildcard keys identifying the target checklist (e.g. arch/domain).
    """
    return html.Div(
        children=[
            html.Button("Select all", id={"type": button_type, "action": "show", **id_keys}, n_clicks=0, className="odx-mini-button small-button"),
            html.Button("Clear", id={"type": button_type, "action": "hide", **id_keys}, n_clicks=0, className="odx-mini-button small-button"),
        ],
        className="xp-filter-buttons",
    )

def _preview_title(n_combos: int, default_enabled: bool, n_selected: int = 0) -> list:
    """Content of the preview panel heading: the "Preview" label plus a badge
    counting the selected combinations, accounting for the default config.

    n_combos is the total number of non-default combinations and n_selected how
    many of them are currently checked, shown as "n_selected/n_combos". The
    default config is counted separately: "+1 default" when it is enabled
    alongside other combos, or "1 default" when it is the only selected entry.
    """
    if n_combos <= 0:
        detail = "1 default" if default_enabled else "0 combinations"
    else:
        word = "combination" if n_combos == 1 else "combinations"
        suffix = " +1 default" if default_enabled else ""
        detail = f"{n_selected}/{n_combos} {word}{suffix}"
    return [html.Span("Preview"), html.Span(detail, className="odx-badge")]


def _arch_badge_text(n_combos: int, n_selected: int, default_enabled: bool, arch_enabled: bool=True) -> str:
    """Badge shown next to an architecture name: how many of its configurations
    are currently selected (the default config counts as one). A disabled
    architecture runs nothing, so only its total is shown."""
    total = n_combos + 1
    word = "config" if total == 1 else "configs"
    if not arch_enabled:
        return f"{total} {word}"
    selected = n_selected + (1 if default_enabled else 0)
    return f"{selected}/{total} {word}"

def _analysis_tools_selection(search: str, settings_path: str) -> list:
    """Tools the analysis 'Tools' checklist is initialized to: the "tools" list
    saved in the analysis settings file plus the tool selected on the "Choose
    EDA Tool" page (?tool=...). Shared by init_form (widget init) and the saved
    baseline so a refresh does not falsely report "unsaved changes"."""
    selected_tools = list(job_config(settings_path, "analysis").settings.tools)
    url_tool = get_key_from_url(search, "tool")
    if url_tool and url_tool not in selected_tools:
        selected_tools.append(url_tool)
    return selected_tools

def _simulation_badge_text(n_entries, n_selected, enabled=True):
    word = "config" if n_entries == 1 else "configs"
    if not enabled:
        return f"{n_entries} {word}"
    return f"{n_selected}/{n_entries} {word}"

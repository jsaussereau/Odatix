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

"""The "Job Settings" form of the page."""

from dash import dcc, html

import odatix.gui.ui_components as ui
from odatix.lib.utils import AUTO_NB_JOBS_KEYWORD, is_auto_nb_jobs, resolve_nb_jobs

from odatix.gui.jobs_config.common import (
    _JOB_SETTINGS_DEFAULTS,
    _analysis_tool_options,
    _analysis_tools,
)

def job_settings_form(settings, run_mode="default", selected_tools=None):
    frequencies = settings.get("frequencies", {})
    range = frequencies.get("range", {})
    fmax_bounds = settings.get("fmax_synthesis", {})
    if not isinstance(fmax_bounds, dict):
        fmax_bounds = {}

    auto_nb_jobs = is_auto_nb_jobs(settings.get("nb_jobs"))

    if selected_tools is None:
        selected_tools = settings.get("tools", [])
    selected_tools = [tool for tool in selected_tools if tool in _analysis_tools()]

    return html.Div(
        children=[
            html.Div([
                html.Div("Execution", className="odx-panel-caption"),
                html.Div(
                    children=[
                        ui.switch_row(
                            "Overwrite existing result",
                            id="overwrite",
                            checked=settings.get("overwrite", False),
                            tooltip="If enabled, previous results will be overwritten. (overridden by -o / --overwrite).",
                        ),
                        ui.switch_row(
                            "Force single threading",
                            id="force_single_thread",
                            checked=settings.get("force_single_thread", True),
                            tooltip="If enabled, each job will run using a single thread.",
                        ),
                    ],
                    className="odx-switch-stack",
                ),
                html.Div(
                    children=[
                        ui.form_field(
                            label="Maximum number of parallel jobs",
                            id="nb_jobs",
                            type="number",
                            value=str(resolve_nb_jobs(AUTO_NB_JOBS_KEYWORD)) if auto_nb_jobs else str(settings.get("nb_jobs", 8)),
                            disabled=auto_nb_jobs,
                            tooltip="Maximum number of jobs to run in parallel. (overridden by -j / --jobs)",
                            style={"flex": "1"},
                        ),
                        ui.inline_switch(
                            "Auto",
                            id="auto-nb-jobs",
                            checked=auto_nb_jobs,
                            tooltip="Automatically use the number of available CPUs minus one.",
                        ),
                    ],
                    className="odx-field-row",
                ),
            ], className="odx-panel padded"),
            html.Div([
                html.Div("Monitor", className="odx-panel-caption"),
                ui.form_field(
                    label="Size of the log history per job",
                    id="log_size_limit",
                    type="number",
                    value=str(settings.get("log_size_limit", 300)),
                    tooltip="Number of log lines to keep per job. (overridden by --logsize)",
                ),
                html.Div("Command line", className="odx-panel-caption"),
                html.Div(
                    children=[
                        ui.switch_row(
                            "Ask for confirmation after checking settings",
                            id="ask_continue",
                            checked=settings.get("ask_continue", _JOB_SETTINGS_DEFAULTS["ask_continue"]),
                            tooltip="Prompt 'Continue? (Y/n)' after settings checks. (overridden by -y / --noask).",
                        ),
                        ui.switch_row(
                            "Exit terminal monitor when all jobs are done",
                            id="exit_when_done",
                            checked=settings.get("exit_when_done", _JOB_SETTINGS_DEFAULTS["exit_when_done"]),
                            tooltip="Exit the monitor automatically when all jobs are finished. (overridden by -E / --exit).",
                        ),
                    ],
                    className="odx-switch-stack",
                    style={"marginTop": "var(--space-2)"},
                ),
            ], className="odx-panel padded"),
            html.Div([
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                html.Span("EDA tools", style={"display": "inline-block"}),
                            ],
                            className="odx-panel-caption",
                            style={"display": "inline-block"},
                        ),
                        ui.tooltip_icon("Select every eda tool the RTL analysis should run with (saved as the 'tools' list of the analysis settings file, overridden by -t / --tool). The jobs of all selected tools run together in a single monitor session.", tooltip_options="secondary bottom"),
                    ],
                ),
                dcc.Checklist(
                    options=_analysis_tool_options(),
                    value=selected_tools,
                    id="analysis-tools",
                    className="checklist-switch list",
                ),
            ], className="odx-panel padded", style={"display": "block" if run_mode == "analyze" else "none"}),
            html.Div([
                html.Div("Synthesis constraints", className="odx-panel-caption"),
                html.Div(
                    ui.switch_row(
                        "Override frequencies",
                        id="override-arch-frequencies",
                        checked=(
                            fmax_bounds.get("override", False) if run_mode == "fmax_synthesis"
                            else frequencies.get("override", False)
                        ),
                        tooltip="Override architecture-specific frequencies.",
                    ),
                    className="odx-switch-stack",
                ),
                html.Div(
                    children=[
                        ui.inline_switch(
                            "List",
                            id="use-custom-freq-list",
                            checked=frequencies.get("use_custom_freq_list", False),
                            tooltip="Synthesize at each frequency of the list below.",
                        ),
                        ui.form_field(
                            label="Target frequencies (MHz)",
                            id="target_frequencies",
                            type="text",
                            value=", ".join(str(f) for f in frequencies.get("list", [])),
                            tooltip="Comma-separated target frequencies for the synthesis.",
                            style={"flex": "1"},
                        ),
                    ],
                    className="odx-field-row",
                    style={"display": "flex" if run_mode == "custom_freq_synthesis" else "none", "marginBottom": "var(--space-3)"},
                ),
                html.Div(
                    children=[
                        ui.inline_switch(
                            "Range",
                            id="use-custom-freq-range",
                            checked=frequencies.get("use_custom_freq_range", False),
                            tooltip="Synthesize at every frequency of the range below.",
                        ),
                        ui.form_field(
                            label="From (MHz)",
                            id="from_frequency",
                            type="number",
                            value=str(range.get("from", "")),
                            tooltip="Lower frequency for the synthesis.",
                        ),
                        ui.form_field(
                            label="To (MHz)",
                            id="to_frequency",
                            type="number",
                            value=str(range.get("to", "")),
                            tooltip="Upper frequency for the synthesis.",
                        ),
                        ui.form_field(
                            label="Step (MHz)",
                            id="step_frequency",
                            type="number",
                            value=str(range.get("step", "")),
                            tooltip="Frequency step for the synthesis.",
                        ),
                    ],
                    className="odx-field-row",
                    style={"display": "flex" if run_mode == "custom_freq_synthesis" else "none"},
                ),
                html.Div(
                    children=[
                        ui.form_field(
                            label="Lower Bound (MHz)",
                            id="lower_bound",
                            type="number",
                            value=str(fmax_bounds.get("lower_bound", "")),
                            tooltip="Lower bound of the binary search for the maximum frequency.",
                            style={"flex": "1"},
                        ),
                        ui.form_field(
                            label="Upper Bound (MHz)",
                            id="upper_bound",
                            type="number",
                            value=str(fmax_bounds.get("upper_bound", "")),
                            tooltip="Upper bound of the binary search for the maximum frequency.",
                            style={"flex": "1"},
                        ),
                    ],
                    className="odx-field-row",
                    style={"display": "flex" if run_mode == "fmax_synthesis" else "none"},
                )
            ], className="odx-panel padded", style={"display": "block" if run_mode in ("custom_freq_synthesis", "fmax_synthesis") else "none"}),
        ], className="odx-grid",
    )

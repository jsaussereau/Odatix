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

"""Callbacks of the page itself: the Job Settings form, the instance cards and
their parameter-domain / preview widgets, and the Save button."""

import os
import threading

import dash
import natsort
from dash import ctx, dcc, html, Input, Output, State

from odatix.workspace.configs import combinations
from odatix.workspace.jobs import FmaxBoundsSettings, FrequenciesSettings
from odatix.workspace.yaml_io import read_yaml
import odatix.gui.ui_components as ui
import odatix.lib.eda_tools as eda_tools
import odatix.lib.hard_settings as hard_settings
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
from odatix.lib.parallel_job_handler import daemon_control
from odatix.lib.utils import AUTO_NB_JOBS_KEYWORD, resolve_nb_jobs

from odatix.gui.jobs_config.arch_widgets import _arch_config_widgets, _group_arch_selections
from odatix.gui.jobs_config.common import (
    ARCHITECTURES_BASELINE_KEY,
    RUN_MODE_LABELS,
    _JOB_SETTINGS_DEFAULTS,
    _analysis_tools_selection,
    _arch_badge_text,
    _checklist_enabled,
    _get_synth_settings_path,
    _preview_title,
    _session_option,
    _simulation_badge_text,
    _to_int,
    page_path,
    rerun_step_names,
)
from odatix.gui.jobs_config.context import _run_context
from odatix.gui.jobs_config.pnr import _pnr_job_sections, _pnr_sync_preview_values
from odatix.gui.jobs_config.settings_form import frequency_fields_class, frequency_note, job_settings_form
from odatix.gui.jobs_config.settings_io import _collect_run_settings, _job_settings_baseline, write_run_settings
from odatix.gui.jobs_config.arch_widgets import compact_selection
from odatix.gui.jobs_config.simulation import (
    _collect_listed_architectures,
    _save_listed_architectures,
    _simulation_job_sections,
    compact_simulation_selection,
)
from odatix.gui.page_scope import page_callback, page_clientside_callback

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "jobs_config"

def _compacted_selection(context, run_mode, selection):
    """
    The selection as it is written to the settings file: domains where every
    configuration is selected are written as a wildcard ("Design/* +
    domain/config") instead of as the full list of their configurations.

    Place & route selectors name synthesis results rather than an architecture
    design space, so they are written as they are.
    """
    if selection is None or run_mode == "pnr":
        return selection
    workspace = context["workspace"]
    if run_mode == "simulation":
        return compact_simulation_selection(workspace.architectures, selection, context["mode"])
    instances = workspace.workflows if context["mode"] == "workflow" else workspace.architectures
    return compact_selection(instances, selection, context["mode"])


def _list_workspace_sessions():
    try:
        daemons = daemon_control.list_daemons()
        daemons, _root, _scoped = daemon_control.scope_daemons(daemons)
    except Exception:
        daemons = []
    return daemons


# Listing the sessions probes every session of the machine, which takes
# seconds when there are many: the list is refreshed in the background and
# the dropdown is answered from the last listing, so a slow probe never holds
# the callback (it used to, until the next refresh superseded it and the list
# never showed up).
_sessions_cache = {"daemons": None, "refreshing": False}
_sessions_lock = threading.Lock()


def _refresh_sessions():
    daemons = _list_workspace_sessions()
    with _sessions_lock:
        _sessions_cache["daemons"] = daemons
        _sessions_cache["refreshing"] = False


def _workspace_sessions():
    """
    The sessions jobs can be added to: those of the workspace the page runs in,
    as "odatix ps" lists them. A session of another workspace runs its jobs
    with that workspace's files: adding these jobs to it is never what is meant.
    """
    with _sessions_lock:
        daemons = _sessions_cache["daemons"]
        start = not _sessions_cache["refreshing"] and daemons is not None
        if start:
            _sessions_cache["refreshing"] = True
    if daemons is None:
        # Never listed yet: the first answer is worth waiting for.
        _refresh_sessions()
        daemons = _sessions_cache["daemons"]
    elif start:
        threading.Thread(target=_refresh_sessions, daemon=True).start()
    daemons = list(daemons or [])

    def started_at(daemon):
        try:
            return float(daemon.get("started_at") or 0)
        except (TypeError, ValueError):
            return 0.0

    # The latest first: it is the one a run is most likely to join.
    return sorted(daemons, key=started_at, reverse=True)


@dash.callback(
    Output({"page": page_path, "action": "session-dropdown"}, "options"),
    Output({"page": page_path, "action": "session-dropdown"}, "value"),
    Input(f"url_{page_path}", "search"),
    Input("session-list-interval", "n_intervals"),
    State({"page": page_path, "action": "session-dropdown"}, "value"),
)
def update_session_dropdown(_search, _n, current_value):
    options = [{"label": "New session...", "value": "__new_session__", "title": "Run jobs in a new session"}]
    options.extend(_session_option(daemon) for daemon in _workspace_sessions())

    values = {option.get("value") for option in options}
    selected = str(current_value).strip() if current_value is not None else "__new_session__"
    if selected not in values:
        selected = "__new_session__"

    return options, selected

@dash.callback(
    Output({"page": page_path, "action": "session-access"}, "value"),
    Input(f"url_{page_path}", "search"),
)
def default_session_access(_search):
    """What the workspace says ("session_access" in odatix.yml), each time the page opens."""
    try:
        return daemon_control.workspace_session_access(os.getcwd())
    except daemon_control.DaemonControlError:
        return "user"


@dash.callback(
    Output({"page": page_path, "action": "session-access"}, "disabled"),
    Input({"page": page_path, "action": "session-dropdown"}, "value"),
)
def session_access_applies(selected_session):
    """Only a new session is given an access: one that runs already keeps its own."""
    return selected_session not in (None, "", "__new_session__")


#: The job types whose selection is a list of architecture configurations
#: ("architectures" of their run settings file): one can be loaded from another.
ARCH_SELECTION_MODES = (
    ("fmax_synthesis", "Fmax synthesis"),
    ("custom_freq_synthesis", "Fixed-frequency synthesis"),
    ("analyze", "RTL analysis"),
)


def selection_source_text(search, odatix_settings, loaded_from=None):
    """
    The line under the header: the settings file the selection is loaded from,
    or the one "Load from" took it from, which Save does not write to.
    """
    path = _get_synth_settings_path(search, odatix_settings or {})
    if not path:
        return ""
    if loaded_from:
        return html.Span(
            ["Selection loaded from ", html.B(os.path.basename(loaded_from)), html.Span(" (unsaved)", className="odx-muted")],
            title="Save all writes it to " + path,
        )
    return ["Selection loaded from ", html.B(os.path.basename(path))]


def load_from_options(search, odatix_settings):
    """
    The run settings files a selection of this page can be loaded from: its
    own first (back to what it holds), then those of the other job types.
    """
    run_mode = get_key_from_url(search, "type") or "fmax_synthesis"
    modes = dict(ARCH_SELECTION_MODES)
    if run_mode not in modes:
        return []
    own = _get_synth_settings_path(search, odatix_settings or {})
    options = [{
        "label": "{} ({})".format(modes[run_mode], os.path.basename(own)),
        "value": own,
        "title": "The selection this page's file holds ({}), what the page opened with.".format(own),
    }]
    for mode, label in ARCH_SELECTION_MODES:
        if mode == run_mode:
            continue
        path = _get_synth_settings_path("?type=" + mode, odatix_settings or {})
        if not path or not os.path.isfile(path):
            continue
        selection = read_yaml(path, default={}).get("architectures") if path else None
        if not selection:
            continue
        options.append({
            "label": "{} ({})".format(label, os.path.basename(path)),
            "value": path,
            "title": "Select the configurations {} runs ({}). Save all writes them to this page's file.".format(
                label.lower(), path),
        })
    return options


@dash.callback(
    Output("jobs-selection-source", "children"),
    Input(f"url_{page_path}", "search"),
    Input("jobs-selection-from", "data"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def update_selection_source(search, loaded, page, odatix_settings):
    if page != page_path:
        return dash.no_update
    loaded_from = (loaded or {}).get("path") if ctx.triggered_id == "jobs-selection-from" else None
    if loaded_from == _get_synth_settings_path(search, odatix_settings or {}):
        loaded_from = None
    return selection_source_text(search, odatix_settings, loaded_from)


@dash.callback(
    Output("jobs-load-selection-from", "options"),
    Output("jobs-load-selection-from", "style"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def update_load_from(search, page, odatix_settings):
    """Only offered where there is another selection to load."""
    if page != page_path:
        return dash.no_update, dash.no_update
    options = load_from_options(search, odatix_settings)
    return options, {"width": "140px"} if options else {"display": "none"}


@dash.callback(
    Output("jobs-selection-from", "data"),
    Output("jobs-load-selection-from", "value"),
    Input("jobs-load-selection-from", "value"),
    prevent_initial_call=True,
)
def load_selection_from(path):
    """Load the picked file, and leave the menu ready to pick again."""
    if not path:
        raise dash.exceptions.PreventUpdate
    import time

    return {"path": path, "at": time.time()}, None

@dash.callback(
    Output("job-settings-form-container", "children"),
    Output("job-settings-initial-settings", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_form(search, page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update

    run_mode = get_key_from_url(search, "type")
    settings_path = _get_synth_settings_path(search, odatix_settings or {})
    
    settings = read_yaml(settings_path, default={})
    if run_mode == "custom_freq_synthesis":
        # Normalize the frequencies for the form, but keep the other job
        # settings (overwrite, nb_jobs, ...) so their widgets reflect the file.
        settings = {**settings, "frequencies": FrequenciesSettings.from_dict(settings.get("frequencies", {})).to_dict()}

    selected_tools = None
    if run_mode == "analyze":
        selected_tools = _analysis_tools_selection(search, settings_path)

    return job_settings_form(
        settings, run_mode, selected_tools=selected_tools, rerun_steps=rerun_step_names(search),
    ), settings

@dash.callback(
    Output("nb_jobs", "disabled"),
    Output("nb_jobs", "value"),
    Input("auto-nb-jobs", "value"),
    State("nb_jobs", "value"),
    prevent_initial_call=True,
)
def toggle_auto_nb_jobs(auto_nb_jobs, nb_jobs):
    """Disable (and blank) the nb_jobs input while the Auto switch is on; restore
    a sensible value when it is turned back off."""
    if _checklist_enabled(auto_nb_jobs):
        return True, str(resolve_nb_jobs(AUTO_NB_JOBS_KEYWORD))
    restored = nb_jobs if nb_jobs not in (None, "") else _JOB_SETTINGS_DEFAULTS["nb_jobs"]
    return False, str(restored)

@dash.callback(
    Output("frequency-override-note", "children"),
    Output("frequency-fields", "className"),
    Input("override-arch-frequencies", "value"),
    State(f"url_{page_path}", "search"),
    prevent_initial_call=True,
)
def update_frequency_note(override, search):
    """Say what the frequency fields mean with the override switch as it is."""
    enabled = _checklist_enabled(override)
    return frequency_note(get_key_from_url(search, "type"), enabled), frequency_fields_class(enabled)


@dash.callback(
    Output("job-section", "children"),
    Output("job-section-heading", "children"),
    Output("jobs-config-main-title", "children"),
    Output("jobs-config-saved-selection", "data", allow_duplicate=True),
    Input(f"url_{page_path}", "search"),
    Input("jobs-selection-from", "data"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_param_domains_callback(search, loaded, page, odatix_settings):
    return update_param_domains(search, page, odatix_settings, loaded=loaded)


def update_param_domains(search, page, odatix_settings, loaded=None):
    """The cards of the page, from its run settings file, or `loaded` ("Load from")."""
    triggered_id = ctx.triggered_id

    if triggered_id == "url":
        if page != page_path:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    context = _run_context(search, odatix_settings)
    arch_path = context["base_path"]
    architectures = context["instances"]
    run_mode = get_key_from_url(search, "type")

    settings_path = context["settings_path"]
    selection_settings = read_yaml(settings_path, default={})

    # Simulations select architecture configurations rather than their own, so
    # they get their own sections (see _simulation_job_sections).
    if context["mode"] == "simulation":
        job_sections, baseline_selection, baseline_listed = _simulation_job_sections(
            context, selection_settings
        )
        if not job_sections:
            job_sections = [
                html.Div(
                    f"No simulation found in {context['base_path']}.",
                    className="odx-panel odx-empty",
                )
            ]
        saved_baseline = {
            context["selection_key"]: baseline_selection,
            # Lives in the simulations' own settings files rather than in the run
            # settings, but is edited here, so Save covers it too (see
            # _save_listed_architectures).
            ARCHITECTURES_BASELINE_KEY: baseline_listed,
            **_job_settings_baseline(selection_settings),
        }
        return job_sections, context["title"], "Select the configurations each simulation runs on", saved_baseline

    # A place & route run selects completed synthesis jobs, grouped by tool then
    # by architecture, so it gets the same nested sections (see
    # _pnr_job_sections).
    if context["mode"] == "pnr":
        job_sections, baseline_selection = _pnr_job_sections(context, selection_settings)
        # A place & route starts from what a synthesis left: say so first, and
        # what to run when there is nothing to start from yet.
        prerequisite = (
            "A place & route starts from a synthesis already run: an Fmax or a fixed-frequency synthesis, "
            "with a tool that writes a netlist this tool reads (Design Compiler or Genus for an ASIC flow). "
            "Each tool that left one in the work directory is listed below."
        )
        if not job_sections:
            job_sections = [
                html.Div(
                    [
                        html.Div(f"No completed synthesis found in {context['base_path']}."),
                        html.Div(prerequisite, className="odx-panel-note"),
                    ],
                    className="odx-panel odx-empty",
                )
            ]
        else:
            job_sections = [html.Div(prerequisite, className="odx-panel-note odx-pnr-prerequisite")] + list(job_sections)
        saved_baseline = {
            context["selection_key"]: baseline_selection,
            **_job_settings_baseline(selection_settings),
        }
        return job_sections, context["title"], "Select the synthesized designs to place & route", saved_baseline

    # "Load from": the selection of another job type, the rest (job settings,
    # where Save writes) staying this page's.
    loaded_from = None
    if triggered_id == "jobs-selection-from" and context["mode"] == "arch":
        loaded_from = (loaded or {}).get("path")
        if loaded_from == settings_path:
            # Its own file: back to the selection it opened with.
            loaded_from = None
    selection_source = read_yaml(loaded_from, default={}) if loaded_from else selection_settings
    selection_map = _group_arch_selections(selection_source.get(context["selection_key"], []))
    # Baseline of the "saved" selection, computed exactly like the widgets are
    # initialized below, so a fresh page load does not falsely report "unsaved
    # changes" (the store starts empty and is only written on Save otherwise).
    baseline_selection = []
    job_sections = []
    for arch_name in architectures:
        arch_enabled = arch_name in selection_map
        domain_tiles, preview_tile, info = _arch_config_widgets(
            context["workspace"].workflows if context["mode"] == "workflow" else context["workspace"].architectures,
            arch_name,
            selection_map.get(arch_name, []),
            arch_enabled,
            context["mode"],
        )
        n_combos = info["n_combos"]
        n_selected = info["n_selected"]
        default_selected = info["default_selected"]
        domains_configs = info["domains_configs"]

        # Enabled architectures contribute their (rendered) preview selection to
        # the saved baseline, exactly like save_architecture_selections() builds
        # its "current" selection from the switch + preview widgets.
        if arch_enabled:
            baseline_selection.extend(info["filtered_selected"])

        arch_buttons = html.Div(
            children=[
                ui.icon_button(
                    icon=icon("gear", className="icon"),
                    text=context["settings_text"],
                    tooltip=f"Open the settings of this {context['mode']}",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["settings_link"](arch_name),
                    multiline=True,
                    width="135px",
                ),
                ui.icon_button(
                    icon=icon("edit", className="icon blue"),
                    text=context.get("config_text", "Edit Configs"),
                    tooltip=f"Open the {context.get('config_text', 'Edit Configs')} page for this {context['mode']}",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["config_link"](arch_name),
                    multiline=False,
                    width="135px",
                ),
            ],
            className="jobs-arch-buttons",
        )
        job_section = html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                dcc.Checklist(
                                    options=[{"label": "", "value": True}],
                                    value=[True] if arch_enabled else [],
                                    id={"type": "arch-title", "arch": arch_name, "is_switch": True},
                                    className="checklist-switch",
                                ),
                                html.Span(arch_name, id={"type": "arch-title", "arch": arch_name}, className="jobs-arch-name"),
                                html.Span(
                                    _arch_badge_text(n_combos, n_selected, default_selected, arch_enabled),
                                    id={"type": "arch-count", "arch": arch_name},
                                    className="odx-badge",
                                ),
                            ],
                            className="jobs-arch-headline",
                        ),
                        arch_buttons,
                    ],
                    className="jobs-arch-header",
                ),
                html.Div(
                    children=html.Div(
                        children=[
                            html.Div(domain_tiles, className="jobs-domains"),
                            preview_tile,
                        ],
                        className="jobs-arch-grid",
                    ),
                    id={"type": "param-domains-container", "arch": arch_name},
                    className="jobs-arch-body animated-section" + ("" if arch_enabled else " hide"),
                ),
                dcc.Store(
                    id={"type": "arch-metadata", "arch": arch_name},
                    data={
                        "arch_name": arch_name,
                        "n_combos": n_combos,
                        "virtual_variants": info["virtual_variants"],
                        "excluded": info.get("excluded") or [],
                        "virtual_domains": info["virtual_domains"],
                    },
                ),
                dcc.Store(
                    id={"type": "domain-selections", "arch": arch_name},
                    data=info["initial_selections"],
                ),
            ],
            id={"type": "job-section", "arch": arch_name},
            className="jobs-arch-card" + (" enabled" if arch_enabled else ""),
        )
        job_sections.append(job_section)

    if not job_sections:
        job_sections = [
            html.Div(
                f"No {context['title'].lower()} found in {context['base_path']}.",
                className="odx-panel odx-empty",
            )
        ]
    main_title = f"Select {context['mode'] if context['mode'] == 'workflow' else 'architecture'} configurations to run"

    # Build the "saved" baseline in the exact same shape as the "current"
    # selection computed by save_architecture_selections(), so a fresh load
    # compares equal (no false "unsaved changes").
    saved_baseline = {
        # A selection loaded from another file is not what this page's file
        # holds: it shows as unsaved until Save all writes it.
        context["selection_key"]: None if loaded_from else list(dict.fromkeys(baseline_selection)),
        **_job_settings_baseline(selection_settings),
    }
    if run_mode == "analyze":
        saved_baseline["tools"] = [t for t in _analysis_tools_selection(search, settings_path) if t]
    if run_mode == "custom_freq_synthesis":
        saved_baseline["frequencies"] = FrequenciesSettings.from_dict(
            selection_settings.get("frequencies", {})
        ).to_dict()
    if run_mode == "fmax_synthesis":
        fmax_bounds = selection_settings.get("fmax_synthesis", {})
        if not isinstance(fmax_bounds, dict):
            fmax_bounds = {}
        saved_baseline["fmax_synthesis"] = FmaxBoundsSettings.from_dict(fmax_bounds).to_dict()

    return job_sections, context["title"], main_title, saved_baseline


# Collapse/expand the configurations of an architecture with its switch, and
# highlight the card while it is selected to run. Answered in the browser: a
# round trip per card for a class name made the page slow to load and to react
# (see assets/jobs_config.js). The classes a card is rendered with already
# match its switch, hence no initial call.
page_clientside_callback(PAGE_SCOPE,
    dash.ClientsideFunction(namespace="odatix_jobs", function_name="toggle_card"),
    Output({"type": "param-domains-container", "arch": dash.MATCH}, "className"),
    Output({"type": "job-section", "arch": dash.MATCH}, "className"),
    Input({"type": "arch-title", "arch": dash.MATCH, "is_switch": True}, "value"),
    prevent_initial_call=True,
)


@page_callback(PAGE_SCOPE,
    Output({"type": "arch-count", "arch": dash.ALL}, "children"),
    Input({"type": "preview-config-checklist", "arch": dash.ALL}, "value"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
    State({"type": "arch-count", "arch": dash.ALL}, "id"),
    State({"type": "arch-metadata", "arch": dash.ALL}, "data"),
    # The badges are rendered with their counts: only a change recounts them.
    prevent_initial_call=True,
)
def update_arch_count(preview_values, switch_values, preview_ids, switch_ids, count_ids, metadatas):
    """Keep the "selected/total configs" badge of every architecture in sync with
    its preview checklist and its switch.

    Written with ALL rather than MATCH because architectures with too many
    combinations have no preview checklist at all: a MATCH group would then be
    incomplete and Dash would report a nonexistent object.
    """
    previews = {
        pid.get("arch"): value
        for value, pid in zip(preview_values or [], preview_ids or [])
        if isinstance(pid, dict)
    }
    enabled = {
        sid.get("arch"): bool(value)
        for value, sid in zip(switch_values or [], switch_ids or [])
        if isinstance(sid, dict)
    }
    metadata_by_arch = {
        (data or {}).get("arch_name"): (data or {})
        for data in (metadatas or [])
    }

    children = []
    for cid in count_ids or []:
        arch_name = cid.get("arch") if isinstance(cid, dict) else None
        if arch_name not in previews:
            # No preview checklist (too many combinations): nothing to recount.
            children.append(dash.no_update)
            continue
        selected = previews.get(arch_name) or []
        metadata = metadata_by_arch.get(arch_name, {})
        n_combos = metadata.get("n_combos", 0)
        if metadata.get("kind") == "pnr":
            # A source is picked whole: there is no default configuration to
            # count apart, and nothing to combine.
            children.append(
                _simulation_badge_text(n_combos, len(selected), enabled.get(arch_name, False))
            )
            continue
        default_enabled = arch_name in selected
        n_selected = len([v for v in selected if v != arch_name])
        children.append(_arch_badge_text(n_combos, n_selected, default_enabled, enabled.get(arch_name, False)))
    return children


@dash.callback(
    Output("jobs-summary", "children"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    Input({"type": "preview-config-checklist", "arch": dash.ALL}, "value"),
    Input({"type": "sim-selection", "sim": dash.ALL}, "data"),
    Input("nb_jobs", "value"),
    Input("auto-nb-jobs", "value"),
    Input("rerun-from", "value"),
    Input(f"url_{page_path}", "search"),
    # Written by update_param_domains along with the cards: until then the
    # selection is not on the page yet, and counting it would say "0".
    Input("jobs-config-saved-selection", "data"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State({"type": "sim-selection", "sim": dash.ALL}, "id"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
)
def update_jobs_summary(
    switch_values, preview_values, sim_selection_values, nb_jobs, auto_nb_jobs, rerun_from, search,
    saved_selection, preview_ids, sim_selection_ids, switch_ids,
):
    """Live recap of what the Run button is about to launch: job type, eda tool,
    how many instances are enabled and how many configurations they add up to."""
    return jobs_summary(
        search, switch_values, switch_ids, preview_values, preview_ids,
        sim_selection_values, sim_selection_ids, nb_jobs, auto_nb_jobs, rerun_from,
        loaded=saved_selection is not None,
    )


def _instances_labels(run_mode):
    """How the summary names the instances and what they select, singular then plural."""
    if run_mode == "workflow":
        return ("workflow", "workflows"), ("configuration selected", "configurations selected")
    if run_mode == "simulation":
        return ("simulation", "simulations"), ("configuration selected", "configurations selected")
    if run_mode == "pnr":
        # The cards of a place & route are the tools that ran the syntheses it
        # starts from, and what they select are those syntheses.
        return ("source tool", "source tools"), ("synthesis selected", "syntheses selected")
    return ("architecture", "architectures"), ("configuration selected", "configurations selected")


def jobs_summary(
    search, switch_values, switch_ids, preview_values, preview_ids,
    sim_selection_values, sim_selection_ids, nb_jobs, auto_nb_jobs, rerun_from, loaded=True,
):
    """
    The summary strip of the header. `loaded` is False while the cards are not
    on the page yet: the counts then show an ellipsis rather than a "0" that
    would read as "nothing selected".
    """
    enabled = set()
    for value, sid in zip(switch_values or [], switch_ids or []):
        arch = sid.get("arch") if isinstance(sid, dict) else None
        if arch and value:
            enabled.add(arch)

    n_configs = 0
    for value, pid in zip(preview_values or [], preview_ids or []):
        arch = pid.get("arch") if isinstance(pid, dict) else None
        if arch in enabled:
            n_configs += len(value or [])
    for value, pid in zip(sim_selection_values or [], sim_selection_ids or []):
        sim_name = pid.get("sim") if isinstance(pid, dict) else None
        if sim_name in enabled:
            n_configs += len(value or [])

    run_mode = get_key_from_url(search, "type")
    tool = get_key_from_url(search, "tool")
    flow = get_key_from_url(search, "flow")
    until_step = get_key_from_url(search, "until")

    if _checklist_enabled(auto_nb_jobs):
        parallel = str(resolve_nb_jobs(AUTO_NB_JOBS_KEYWORD)) + " (auto)"
    else:
        parallel = str(_to_int(nb_jobs, _JOB_SETTINGS_DEFAULTS["nb_jobs"]))

    (instance_one, instance_many), (config_one, config_many) = _instances_labels(run_mode)
    instances_label = instance_one if len(enabled) == 1 else instance_many
    configs_label = config_one if n_configs == 1 else config_many

    children = [
        html.Span(RUN_MODE_LABELS.get(run_mode, "Jobs"), className="odx-tag"),
    ]
    if tool and run_mode not in ("workflow", "simulation"):
        children.extend(html.Span(text, className="odx-tag neutral") for text in run_scope_tags(search))
        # Re-running steps already done costs what they cost the first time:
        # it is not what a run does by default, so it stands out.
        if rerun_from and rerun_from in rerun_step_names(search):
            children.append(html.Span("re-run from " + rerun_from, className="odx-tag warning"))
    children.append(html.Div(className="odx-spacer"))
    if not loaded:
        children.append(ui.stat("…", instance_many, "muted"))
        children.append(ui.stat("…", config_many, "muted"))
    else:
        children.append(ui.stat(len(enabled), instances_label, "" if enabled else "muted"))
        children.append(ui.stat(n_configs, configs_label, "accent" if n_configs else "muted"))
    children.append(ui.stat(parallel, "in parallel"))
    return children


def run_scope_tags(search):
    """
    What a run opened with this url runs with, in words: the eda tool, its flow
    when the tool has several, and the step it stops at. Shared by the summary
    strip and the run popup, so both say the same thing.
    """
    run_mode = get_key_from_url(search, "type")
    tool = get_key_from_url(search, "tool")
    if not tool or run_mode in ("workflow", "simulation"):
        return []
    flow = get_key_from_url(search, "flow")
    tags = [eda_tools.get_tool_label(tool)]
    try:
        # Show the flow only when the tool has a choice to make: a
        # single-flow tool would just add noise.
        if len(eda_tools.list_flows(tool, job_type=run_mode)) > 1:
            tags.append(eda_tools.get_flow_label(tool, flow=flow, job_type=run_mode))
        # Where the run stops is always said for a flow split into steps: it
        # is what makes a run take minutes or hours, and the step a run stops
        # at by default is not the last one of every flow.
        steps = eda_tools.get_flow_step_names(tool, flow=flow, job_type=run_mode)
        until_step = get_key_from_url(search, "until")
        if steps and until_step not in steps:
            # No "until": the step the flow stops at by default, or its last.
            until_step = eda_tools.get_default_step(tool, flow=flow, job_type=run_mode) or steps[-1]
        if steps and until_step in steps:
            tags.append("up to " + until_step)
    except Exception:
        pass
    return tags


# Filtering the cards by name (and "Selected only"), and the "Select all" /
# "Clear" buttons, are answered in the browser (assets/jobs_config.js): they
# only read and write what the page already holds, and a round trip made "Clear"
# take seconds to show on a loaded machine.
dash.clientside_callback(
    dash.ClientsideFunction(namespace="odatix_jobs", function_name="filter_cards"),
    Output({"type": "job-section", "arch": dash.ALL}, "style"),
    Input("jobs-arch-search", "value"),
    Input("jobs-arch-filter", "value"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    State({"type": "job-section", "arch": dash.ALL}, "id"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    dash.ClientsideFunction(namespace="odatix_jobs", function_name="select_all"),
    Output({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    Input("jobs-select-all", "n_clicks"),
    Input("jobs-select-none", "n_clicks"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    prevent_initial_call=True,
)


# Folding the Job Settings section away is done on the client, on the document,
# by the handler in assets/folds.js: nothing outside the browser reads whether
# it is open.


@page_callback(PAGE_SCOPE,
    Output({"type": "domain-selections", "arch": dash.MATCH}, "data"),
    Input({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "id"),
    # Rendered with the selections of the checklists it mirrors.
    prevent_initial_call=True,
)
def update_domain_selections(selected_per_domain, domain_ids):
    domains_configs = {}
    for values, did in zip(selected_per_domain or [], domain_ids or []):
        domain = did.get("domain")
        if not domain:
            continue
        if values:
            domains_configs[domain] = values
    return domains_configs

@page_callback(PAGE_SCOPE,
    Output({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.MATCH}, "value"),
    Input({"type": "domain-config-select-all", "arch": dash.MATCH, "domain": dash.MATCH, "action": dash.ALL}, "n_clicks"),
    State({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.MATCH}, "options"),
    prevent_initial_call=True,
)
def domain_select_all(n_clicks, options):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not any(n_clicks or []):
        raise dash.exceptions.PreventUpdate
    if triggered.get("action") == "show":
        return [option["value"] for option in options or []]
    return []

@page_callback(PAGE_SCOPE,
    Output({"type": "preview-config-checklist", "arch": dash.MATCH}, "value", allow_duplicate=True),
    Input({"type": "preview-config-select-all", "arch": dash.MATCH, "action": dash.ALL}, "n_clicks"),
    State({"type": "preview-config-checklist", "arch": dash.MATCH}, "options"),
    prevent_initial_call=True,
)
def preview_select_all(n_clicks, options):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not any(n_clicks or []):
        raise dash.exceptions.PreventUpdate
    if triggered.get("action") == "show":
        # A disabled entry cannot run (a place & route source with no netlist
        # handed over): "Select all" must not check it.
        return [option["value"] for option in options or [] if not option.get("disabled")]
    return []

@page_callback(PAGE_SCOPE,
    Output({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    Input({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "id"),
    State({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    State({"type": "domain-selections", "arch": dash.MATCH}, "data"),
    # The preview is rendered matching its panels: only a click changes it.
    # Firing once per card on load held the summary back until every card had
    # answered (several seconds for the examples).
    prevent_initial_call=True,
)
def sync_preview_values(
    selected_per_domain,
    domain_ids,
    current_preview_values,
    arch_metadata,
    prev_selections
):
    arch_name = arch_metadata.get("arch_name", "")

    # Build the current state of the domains
    current_domains = {}
    for values, did in zip(selected_per_domain or [], domain_ids or []):
        domain = did.get("domain")
        if not domain:
            continue
        if values:
            current_domains[domain] = values

    # Previous state of the domains (can be None on first call)
    prev_domains = prev_selections or {}

    # Find the domain that changed and the added/removed values
    changed_domain = None
    added_values = set()
    removed_values = set()

    # Domains present either before or now
    all_domains = set(prev_domains.keys()) | set(current_domains.keys())
    # Use a deterministic order (Dash provides domain_ids in display order).
    ordered_domains = []
    for did in (domain_ids or []):
        d = did.get("domain") if isinstance(did, dict) else None
        if d and d not in ordered_domains:
            ordered_domains.append(d)
    for d in sorted(all_domains):
        if d not in ordered_domains:
            ordered_domains.append(d)

    for domain in ordered_domains:
        prev_vals = set(prev_domains.get(domain, []))
        curr_vals = set(current_domains.get(domain, []))
        if prev_vals != curr_vals:
            changed_domain = domain
            added_values = curr_vals - prev_vals
            removed_values = prev_vals - curr_vals
            break

    # If no clear change is found, do nothing. The title is intentionally left
    # untouched: it reflects the total number of available combinations
    # (fixed at render time in update_param_domains), not how many are
    # currently checked -- recomputing it from len(current_preview_values)
    # here would show the checked count instead once any items are unchecked.
    if not changed_domain:
        return current_preview_values or []

    if (arch_metadata or {}).get("kind") == "pnr":
        return _pnr_sync_preview_values(
            arch_metadata, current_domains, current_preview_values, changed_domain, added_values, removed_values
        )

    # Start from the current preview value (including manual changes)
    preview_set = set(current_preview_values or [])

    # Helper: generate all complete combinations from current_domains. Virtual
    # parameter domains have chips of their own, but their values are generated
    # as whole variants (a variant may tie several variables together), so they
    # are not expanded as a cartesian product: the selection filters the
    # variants instead, then every kept variant multiplies every physical
    # combination -- including the bare architecture, exactly like in
    # _arch_config_widgets.
    virtual_variants = (arch_metadata or {}).get("virtual_variants") or []
    virtual_domains = set((arch_metadata or {}).get("virtual_domains") or [])
    physical_domains = {d: v for d, v in current_domains.items() if d not in virtual_domains}

    all_combos = combinations(physical_domains, arch_name)
    if virtual_variants:
        kept_variants = [
            tokens
            for tokens in virtual_variants
            if all(
                token.partition("/")[2] in current_domains.get(token.partition("/")[0], [])
                for token in tokens
                if token.partition("/")[0] in virtual_domains
            )
        ]
        all_combos = [
            base + list(tokens)
            for base in [[arch_name]] + all_combos
            for tokens in kept_variants
        ]
    # A combination the architecture excludes was never offered when the page
    # was rendered, and is not added back by a click on one of its domains.
    excluded = set((arch_metadata or {}).get("excluded") or [])
    if excluded:
        def physical_part(combo):
            return " + ".join(
                token for token in combo
                if token.partition("/")[0] not in virtual_domains
            )

        all_combos = [combo for combo in all_combos if physical_part(combo) not in excluded]
    all_combo_strings = {" + ".join(c) for c in all_combos}

    # Values are domain-scoped in combos as "<domain>/<cfg>" (or "<arch_name>/<cfg>" for main).
    display_domain = arch_name if changed_domain == hard_settings.main_parameter_domain else changed_domain
    added_tokens = {f"{display_domain}/{v}" for v in added_values}
    removed_tokens = {f"{display_domain}/{v}" for v in removed_values}

    # Handle added values in the modified domain
    if added_values:
        for combo in all_combos:
            combo_str = " + ".join(combo)
            # Only handle combos that contain an added value for the changed domain.
            if any(part in added_tokens for part in combo):
                preview_set.add(combo_str)

    # Handle removed values in the modified domain
    if removed_values:
        to_remove = set()
        for item in preview_set:
            # Do not touch the 'default' item
            if item == arch_name:
                continue
            parts = [p.strip() for p in str(item).split(" + ")]
            # Only remove combos that explicitly contain the removed token for the changed domain.
            if any(part in removed_tokens for part in parts):
                to_remove.add(item)
        preview_set -= to_remove

    # Keep the "default" item if it was already selected
    if current_preview_values and arch_name in current_preview_values:
        preview_set.add(arch_name)

    # Return a sorted list for display stability ("8bits" before "16bits")
    result = []
    if arch_name in preview_set:
        result.append(arch_name)
        preview_set.remove(arch_name)
    result.extend(natsort.natsorted(preview_set))

    return result


@page_callback(PAGE_SCOPE,
    Output({"type": "preview-config-checklist", "arch": dash.MATCH}, "value", allow_duplicate=True),
    Input({"type": "default-config-checklist", "arch": dash.MATCH, "domain": "default"}, "value"),
    State({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sync_default_to_preview(default_value, preview_value, arch_metadata):
    """Mirror the 'Default Configuration' checkbox onto the default preview entry."""
    arch_name = (arch_metadata or {}).get("arch_name", "")
    default_on = arch_name in (default_value or [])
    preview_list = list(preview_value or [])
    has_default = arch_name in preview_list
    if default_on and not has_default:
        return [arch_name] + preview_list
    if not default_on and has_default:
        return [val for val in preview_list if val != arch_name]
    raise dash.exceptions.PreventUpdate


@page_callback(PAGE_SCOPE,
    Output({"type": "default-config-checklist", "arch": dash.MATCH, "domain": "default"}, "value"),
    Input({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sync_preview_to_default(preview_value, arch_metadata):
    """Mirror the default preview entry back onto the 'Default Configuration' checkbox."""
    arch_name = (arch_metadata or {}).get("arch_name", "")
    return [arch_name] if arch_name in (preview_value or []) else []


@page_callback(PAGE_SCOPE,
    Output({"type": "preview-config-title", "arch": dash.MATCH}, "children"),
    Input({"type": "preview-config-checklist", "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def update_preview_title(preview_value, arch_metadata):
    """Recompute the preview heading, reflecting whether the default config is selected."""
    metadata = arch_metadata or {}
    arch_name = metadata.get("arch_name", "")
    n_combos = metadata.get("n_combos", 0)
    selected = preview_value or []
    default_enabled = arch_name in selected
    n_selected = len([v for v in selected if v != arch_name])
    return _preview_title(n_combos, default_enabled, n_selected)


def changed_settings(current_settings, saved_settings):
    """
    What Save writes: only the settings the page changed since it loaded them.
    The file is updated in place, so what is left out stays as it is written
    there -- a key the file never had is not added (force_single_thread, the
    frequencies of a run that does not override them...), and a block the page
    does not edit (the "expected" findings of an analysis) is not rewritten.
    """
    if not isinstance(saved_settings, dict):
        return dict(current_settings)
    return {
        key: value
        for key, value in current_settings.items()
        if key not in saved_settings or saved_settings.get(key) != value
    }


@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output("jobs-config-saved-selection", "data"),
    Output("jobs-config-save-feedback", "children"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    Input({"type": "preview-config-checklist", "arch": dash.ALL}, "value"),
    Input({"type": "sim-selection", "sim": dash.ALL}, "data"),
    Input({"type": "sim-architectures", "sim": dash.ALL}, "data"),
    Input("override-arch-frequencies", "value"),
    Input("use-custom-freq-list", "value"),
    Input("target_frequencies", "value"),
    Input("use-custom-freq-range", "value"),
    Input("from_frequency", "value"),
    Input("to_frequency", "value"),
    Input("step_frequency", "value"),
    Input("lower_bound", "value"),
    Input("upper_bound", "value"),
    Input("analysis-tools", "value"),
    Input("overwrite", "value"),
    Input("force_single_thread", "value"),
    Input("nb_jobs", "value"),
    Input("auto-nb-jobs", "value"),
    Input("log_size_limit", "value"),
    Input("ask_continue", "value"),
    Input("exit_when_done", "value"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State({"type": "sim-selection", "sim": dash.ALL}, "id"),
    State({"type": "sim-architectures", "sim": dash.ALL}, "id"),
    State("jobs-config-saved-selection", "data"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_architecture_selections(
    save_n_clicks,
    switch_values,
    preview_values,
    sim_selection_values,
    sim_listed_values,
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
    overwrite,
    force_single_thread,
    nb_jobs,
    auto_nb_jobs,
    log_size_limit,
    ask_continue,
    exit_when_done,
    switch_ids,
    preview_ids,
    sim_selection_ids,
    sim_listed_ids,
    saved_selection,
    search,
    page,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    context = _run_context(search, odatix_settings)
    run_mode = get_key_from_url(search, "type")
    selection_key = context["selection_key"]
    current_settings = _collect_run_settings(
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
        sim_selection_values=sim_selection_values,
        sim_selection_ids=sim_selection_ids,
    )

    if isinstance(saved_selection, dict):
        saved_settings = saved_selection
    else:
        saved_settings = {selection_key: saved_selection or []}

    # Not part of the run settings file: each simulation stores its own list.
    current_listed = _collect_listed_architectures(sim_listed_values, sim_listed_ids)
    saved_listed = saved_settings.get(ARCHITECTURES_BASELINE_KEY, {})

    if triggered_id == {"page": page_path, "action": "save-all"}:
        try:
            settings_path = context["settings_path"]
            payload = changed_settings(current_settings, saved_settings)
            if selection_key in payload:
                # Written with domain wildcards ("Design/* + domain/config"),
                # so a selection covering a whole domain keeps covering it when
                # a configuration is added to that domain later.
                payload[selection_key] = _compacted_selection(context, run_mode, payload[selection_key])
            write_run_settings(
                settings_path,
                payload,
                run_mode,
                _checklist_enabled(use_custom_freq_list),
                _checklist_enabled(use_custom_freq_range),
            )
            _save_listed_architectures(context["workspace"], current_listed, saved_listed)
            return (
                "color-button disabled icon-button tooltip delay bottom small",
                "Nothing to save",
                {**current_settings, ARCHITECTURES_BASELINE_KEY: current_listed},
                ui.success(),
            )
        except Exception as e:
            return (
                "color-button error-status icon-button tooltip bottom small",
                "Failed to save...",
                dash.no_update,
                ui.error(f"Not saved: {e}"),
            )

    # The baseline is only set once update_param_domains() has finished loading
    # the page (it can be slower than init_form, which renders the form widgets
    # and triggers this callback first). Until then, do not judge/flash
    # "Unsaved changes!": leave the button untouched (it starts disabled).
    if saved_selection is None:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    if saved_settings.get(selection_key, []) != current_settings.get(selection_key, []):
        return (
            "color-button warning icon-button tooltip bottom small tooltip",
            "Unsaved changes!",
            dash.no_update,
            dash.no_update,
        )

    if isinstance(saved_selection, dict) and saved_listed != current_listed:
        return (
            "color-button warning icon-button tooltip bottom small tooltip",
            "Unsaved changes!",
            dash.no_update,
            dash.no_update,
        )

    # Job Settings fields (only compare once a real baseline dict exists, i.e.
    # after the page has finished loading, to avoid a transient false positive).
    if isinstance(saved_selection, dict):
        for key in _JOB_SETTINGS_DEFAULTS:
            if saved_settings.get(key) != current_settings.get(key):
                return (
                    "color-button warning icon-button tooltip bottom small tooltip",
                    "Unsaved changes!",
                    dash.no_update,
                    dash.no_update,
                )

    if run_mode == "custom_freq_synthesis":
        saved_frequencies = saved_settings.get("frequencies", {})
        if saved_frequencies != current_settings.get("frequencies", {}):
            return (
                "color-button warning icon-button tooltip bottom small tooltip",
                "Unsaved changes!",
                dash.no_update,
                dash.no_update,
            )

    if run_mode == "fmax_synthesis":
        if saved_settings.get("fmax_synthesis", {}) != current_settings.get("fmax_synthesis", {}):
            return (
                "color-button warning icon-button tooltip bottom small tooltip",
                "Unsaved changes!",
                dash.no_update,
                dash.no_update,
            )

    if run_mode == "analyze":
        if saved_settings.get("tools", []) != current_settings.get("tools", []):
            return (
                "color-button warning icon-button tooltip bottom small tooltip",
                "Unsaved changes!",
                dash.no_update,
                dash.no_update,
            )

    return (
        "color-button disabled icon-button tooltip delay bottom small",
        "Nothing to save",
        dash.no_update,
        dash.no_update,
    )

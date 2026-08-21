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

import dash
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
)
from odatix.gui.jobs_config.context import _run_context
from odatix.gui.jobs_config.pnr import _pnr_job_sections, _pnr_sync_preview_values
from odatix.gui.jobs_config.settings_form import job_settings_form
from odatix.gui.jobs_config.settings_io import _collect_run_settings, _job_settings_baseline, write_run_settings
from odatix.gui.jobs_config.simulation import (
    _collect_listed_architectures,
    _save_listed_architectures,
    _simulation_job_sections,
)
from odatix.gui.page_scope import page_callback

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "jobs_config"

@dash.callback(
    Output({"page": page_path, "action": "session-dropdown"}, "options"),
    Output({"page": page_path, "action": "session-dropdown"}, "value"),
    Input(f"url_{page_path}", "search"),
    Input("session-list-interval", "n_intervals"),
    State({"page": page_path, "action": "session-dropdown"}, "value"),
)
def update_session_dropdown(_search, _n, current_value):
    options = [{"label": "New session...", "value": "__new_session__", "title": "Run jobs in a new session"}]
    try:
        daemons = daemon_control.list_daemons()
    except Exception:
        daemons = []

    options.extend(_session_option(daemon) for daemon in daemons)

    values = {option.get("value") for option in options}
    selected = str(current_value).strip() if current_value is not None else "__new_session__"
    if selected not in values:
        selected = "__new_session__"

    return options, selected

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

    return job_settings_form(settings, run_mode, selected_tools=selected_tools), settings

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
    Output("job-section", "children"),
    Output("job-section-heading", "children"),
    Output("jobs-config-main-title", "children"),
    Output("jobs-config-saved-selection", "data", allow_duplicate=True),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_param_domains(
    search, page, odatix_settings
):
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
        if not job_sections:
            job_sections = [
                html.Div(
                    f"No completed synthesis found in {context['base_path']}.",
                    className="odx-panel odx-empty",
                )
            ]
        saved_baseline = {
            context["selection_key"]: baseline_selection,
            **_job_settings_baseline(selection_settings),
        }
        return job_sections, context["title"], "Select the synthesized designs to place & route", saved_baseline

    selection_map = _group_arch_selections(selection_settings.get(context["selection_key"], []))
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
        context["selection_key"]: list(dict.fromkeys(baseline_selection)),
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


@page_callback(PAGE_SCOPE,
    Output({"type": "param-domains-container", "arch": dash.MATCH}, "className"),
    Output({"type": "job-section", "arch": dash.MATCH}, "className"),
    Input({"type": "arch-title", "arch": dash.MATCH, "is_switch": True}, "value"),
)
def toggle_param_domains(switch_value):
    """Collapse/expand the configurations of an architecture with its switch,
    and highlight the card while it is selected to run."""
    enabled = bool(switch_value)
    return (
        "jobs-arch-body animated-section" + ("" if enabled else " hide"),
        "jobs-arch-card" + (" enabled" if enabled else ""),
    )


@page_callback(PAGE_SCOPE,
    Output({"type": "arch-count", "arch": dash.ALL}, "children"),
    Input({"type": "preview-config-checklist", "arch": dash.ALL}, "value"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
    State({"type": "arch-count", "arch": dash.ALL}, "id"),
    State({"type": "arch-metadata", "arch": dash.ALL}, "data"),
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
    Input(f"url_{page_path}", "search"),
    State({"type": "preview-config-checklist", "arch": dash.ALL}, "id"),
    State({"type": "sim-selection", "sim": dash.ALL}, "id"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
)
def update_jobs_summary(
    switch_values, preview_values, sim_selection_values, nb_jobs, auto_nb_jobs, search,
    preview_ids, sim_selection_ids, switch_ids,
):
    """Live recap of what the Run button is about to launch: job type, eda tool,
    how many instances are enabled and how many configurations they add up to."""
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

    if run_mode == "workflow":
        instances_label = "workflow" if len(enabled) == 1 else "workflows"
    elif run_mode == "simulation":
        instances_label = "simulation" if len(enabled) == 1 else "simulations"
    else:
        instances_label = "architecture" if len(enabled) == 1 else "architectures"
    configs_label = "configuration selected" if n_configs == 1 else "configurations selected"

    children = [
        html.Span(RUN_MODE_LABELS.get(run_mode, "Jobs"), className="odx-tag"),
    ]
    if tool and run_mode not in ("workflow", "simulation"):
        children.append(html.Span(eda_tools.get_tool_label(tool), className="odx-tag neutral"))
        # Show the flow only when the tool has a choice to make: a single-flow
        # tool would just add noise.
        if len(eda_tools.list_flows(tool, job_type=run_mode)) > 1:
            children.append(
                html.Span(eda_tools.get_flow_label(tool, flow=flow, job_type=run_mode), className="odx-tag neutral")
            )
        # A run stopping short of the last step is worth spelling out: the rest
        # of the flow is left for a later run.
        steps = eda_tools.get_flow_step_names(tool, flow=flow, job_type=run_mode)
        if until_step in steps and until_step != steps[-1]:
            children.append(html.Span("up to " + until_step, className="odx-tag neutral"))
    children.append(html.Div(className="odx-spacer"))
    children.append(ui.stat(len(enabled), instances_label, "" if enabled else "muted"))
    children.append(ui.stat(n_configs, configs_label, "accent" if n_configs else "muted"))
    children.append(ui.stat(parallel, "in parallel"))
    return children


@dash.callback(
    Output({"type": "job-section", "arch": dash.ALL}, "style"),
    Input("jobs-arch-search", "value"),
    Input("jobs-arch-filter", "value"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    State({"type": "job-section", "arch": dash.ALL}, "id"),
)
def filter_arch_cards(search_text, filter_value, switch_values, section_ids):
    """Filter the instance cards by name and, optionally, hide the ones that are
    not selected to run."""
    needle = (search_text or "").strip().lower()
    only_enabled = "enabled" in (filter_value or [])
    styles = []
    for enabled, sid in zip(switch_values or [], section_ids or []):
        arch = sid.get("arch", "") if isinstance(sid, dict) else ""
        visible = (not needle or needle in str(arch).lower()) and (not only_enabled or bool(enabled))
        styles.append({} if visible else {"display": "none"})
    # The switch list and the card list always have the same length; if a card
    # has no switch yet (page still rendering), leave it visible.
    styles.extend([{}] * (len(section_ids or []) - len(styles)))
    return styles


@dash.callback(
    Output({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    Input("jobs-select-all", "n_clicks"),
    Input("jobs-select-none", "n_clicks"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    prevent_initial_call=True,
)
def select_all_archs(select_all_clicks, select_none_clicks, switch_values):
    """Enable / disable every instance at once."""
    if ctx.triggered_id == "jobs-select-all":
        return [[True]] * len(switch_values or [])
    if ctx.triggered_id == "jobs-select-none":
        return [[]] * len(switch_values or [])
    raise dash.exceptions.PreventUpdate


@dash.callback(
    Output("jobs-settings-body", "className"),
    Output("jobs-settings-toggle", "children"),
    Input("jobs-settings-toggle", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_job_settings(n_clicks):
    """Fold the Job Settings section away once it is set up."""
    collapsed = bool(n_clicks) and n_clicks % 2 == 1
    return (
        "animated-section" + (" hide" if collapsed else ""),
        "Show" if collapsed else "Hide",
    )



@page_callback(PAGE_SCOPE,
    Output({"type": "domain-selections", "arch": dash.MATCH}, "data"),
    Input({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "arch": dash.MATCH, "domain": dash.ALL}, "id"),
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

    # Return a sorted list for display stability
    result = []
    if arch_name in preview_set:
        result.append(arch_name)
        preview_set.remove(arch_name)
    result.extend(sorted(preview_set))

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


@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output("jobs-config-saved-selection", "data"),
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
        return dash.no_update, dash.no_update, dash.no_update

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
            payload = {
                **read_yaml(settings_path, default={}),
                **current_settings,
            }
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
            )
        except Exception:
            return (
                "color-button error-status icon-button tooltip bottom small",
                "Failed to save...",
                dash.no_update,
            )

    # The baseline is only set once update_param_domains() has finished loading
    # the page (it can be slower than init_form, which renders the form widgets
    # and triggers this callback first). Until then, do not judge/flash
    # "Unsaved changes!": leave the button untouched (it starts disabled).
    if saved_selection is None:
        return dash.no_update, dash.no_update, dash.no_update

    if saved_settings.get(selection_key, []) != current_settings.get(selection_key, []):
        return (
            "color-button warning icon-button tooltip bottom small tooltip",
            "Unsaved changes!",
            dash.no_update,
        )

    if isinstance(saved_selection, dict) and saved_listed != current_listed:
        return (
            "color-button warning icon-button tooltip bottom small tooltip",
            "Unsaved changes!",
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
                )

    if run_mode == "custom_freq_synthesis":
        saved_frequencies = saved_settings.get("frequencies", {})
        if saved_frequencies != current_settings.get("frequencies", {}):
            return (
                "color-button warning icon-button tooltip bottom small tooltip",
                "Unsaved changes!",
                dash.no_update,
            )

    if run_mode == "fmax_synthesis":
        if saved_settings.get("fmax_synthesis", {}) != current_settings.get("fmax_synthesis", {}):
            return (
                "color-button warning icon-button tooltip bottom small tooltip",
                "Unsaved changes!",
                dash.no_update,
            )

    if run_mode == "analyze":
        if saved_settings.get("tools", []) != current_settings.get("tools", []):
            return (
                "color-button warning icon-button tooltip bottom small tooltip",
                "Unsaved changes!",
                dash.no_update,
            )

    return (
        "color-button disabled icon-button tooltip delay bottom small",
        "Nothing to save",
        dash.no_update,
    )

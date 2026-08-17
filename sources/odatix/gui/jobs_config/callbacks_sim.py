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

import dash
from dash import Input, Output, State

from odatix.gui.utils import get_workspace

from odatix.gui.jobs_config.callbacks_config import (
    domain_select_all,
    preview_select_all,
    sync_default_to_preview,
    sync_preview_to_default,
    sync_preview_values,
    update_arch_count,
    update_domain_selections,
    update_preview_title,
)
from odatix.gui.jobs_config.common import _simulation_badge_text
from odatix.gui.jobs_config.simulation import _sim_arch_card, _sim_entry_from_combo

######################################
# Simulation callbacks
######################################
#
# The architecture panels nested in a simulation card are the same widgets the
# other job types use, with an extra "sim" id key (see _simulation_job_sections).
# Dash matches patterns on the exact set of id keys, so they form callback groups
# of their own: the callbacks below wire them up, delegating to the very same
# implementations the architecture-keyed widgets use.


@dash.callback(
    Output({"type": "sim-architectures", "sim": dash.MATCH}, "data"),
    Output({"type": "sim-arch-card", "sim": dash.MATCH, "arch": dash.ALL}, "style"),
    Output({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.ALL}, "value"),
    Output({"type": "sim-architecture-add", "sim": dash.MATCH}, "options"),
    Output({"type": "sim-architecture-add", "sim": dash.MATCH}, "value"),
    Output({"type": "sim-metadata", "sim": dash.MATCH}, "data"),
    Output({"type": "sim-added-archs", "sim": dash.MATCH}, "children"),
    Output({"type": "sim-no-arch", "sim": dash.MATCH}, "style"),
    Input({"type": "sim-arch-remove", "sim": dash.MATCH, "arch": dash.ALL}, "n_clicks"),
    Input({"type": "sim-architecture-add", "sim": dash.MATCH}, "value"),
    State({"type": "sim-architectures", "sim": dash.MATCH}, "data"),
    State({"type": "sim-arch-card", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.ALL}, "data"),
    State({"type": "sim-metadata", "sim": dash.MATCH}, "data"),
    State({"type": "sim-added-archs", "sim": dash.MATCH}, "children"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def update_listed_architectures(
    remove_clicks, added_arch, listed, card_ids, arch_metadatas, sim_metadata,
    added_cards, odatix_settings
):
    """
    Add or remove an architecture from the ones a simulation declares it runs
    on. The list is only kept in the "sim-architectures" store here:
    it reaches the simulation's settings file when the page is saved, so that
    the Save button reflects the change like every other edit
    (see _save_listed_architectures).

    The card of an architecture that is removed is hidden and its switch turned
    off, so the simulation stops running it; every other card is left untouched
    (dash.no_update), or turning one architecture off would reset the others.

    Only the architectures a simulation shows have a card, so adding one that
    never had one builds it here and appends it to the simulation's
    "sim-added-archs" container; an architecture that was removed still has its
    (hidden) card, and is simply shown again.
    """
    triggered = dash.ctx.triggered_id
    if not isinstance(triggered, dict):
        raise dash.exceptions.PreventUpdate

    arch_names = [cid.get("arch") for cid in (card_ids or []) if isinstance(cid, dict)]
    listed = [str(name) for name in (listed or [])]
    workspace = get_workspace(odatix_settings or {})
    all_arch_names = list(workspace.architectures.names())

    removed = None
    if triggered.get("type") == "sim-arch-remove":
        # A card built after a removal starts at n_clicks=0 and would remove its
        # own architecture again on the next render: only a real click counts.
        clicked = {
            cid.get("arch"): clicks
            for clicks, cid in zip(remove_clicks or [], card_ids or [])
            if isinstance(cid, dict)
        }.get(triggered.get("arch"))
        if not clicked:
            raise dash.exceptions.PreventUpdate
        removed = triggered.get("arch")
        if removed not in listed:
            raise dash.exceptions.PreventUpdate
        listed = [name for name in listed if name != removed]
    else:
        if not added_arch or added_arch in listed:
            raise dash.exceptions.PreventUpdate
        # Keep the order the architectures are listed in, so the settings file
        # does not depend on the order things were clicked in.
        listed = [
            name for name in all_arch_names if name in listed or name == added_arch
        ] + [name for name in listed if name not in all_arch_names]

    shown = set(listed)
    styles = [
        {} if arch in shown else {"display": "none"}
        for arch in arch_names
    ]
    switches = [
        [] if (removed is not None and arch == removed) else dash.no_update
        for arch in arch_names
    ]
    options = [{"label": name, "value": name} for name in all_arch_names if name not in shown]

    # The simulation badge counts the configurations of the architectures it
    # shows: a card appearing or disappearing changes that total.
    n_configs = {
        (data or {}).get("arch_name"): (data or {}).get("n_combos", 0) + 1
        for data in (arch_metadatas or [])
    }

    new_children = dash.no_update
    if removed is None and added_arch not in arch_names:
        # First time this architecture is shown here: it has no card yet.
        card, info = _sim_arch_card(
            workspace.architectures, triggered.get("sim"), added_arch, [], False, "simulation"
        )
        new_children = list(added_cards or []) + [card]
        n_configs[added_arch] = info["n_combos"] + 1

    metadata = dict(sim_metadata or {})
    delta = n_configs.get(removed if removed is not None else added_arch, 0)
    metadata["n_entries"] = max(0, metadata.get("n_entries", 0) + (-delta if removed is not None else delta))

    note_style = {} if not listed else {"display": "none"}

    return listed, styles, switches, options, None, metadata, new_children, note_style


@dash.callback(
    Output({"type": "sim-arch-body", "sim": dash.MATCH, "arch": dash.MATCH}, "className"),
    Output({"type": "sim-arch-card", "sim": dash.MATCH, "arch": dash.MATCH}, "className"),
    Input({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
)
def toggle_sim_arch(switch_value):
    """Collapse/expand an architecture inside a simulation card with its switch."""
    enabled = bool(switch_value)
    return (
        "jobs-arch-body animated-section" + ("" if enabled else " hide"),
        "jobs-arch-card nested" + (" enabled" if enabled else ""),
    )


@dash.callback(
    Output({"type": "domain-selections", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
    Input({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.ALL}, "id"),
)
def sim_update_domain_selections(selected_per_domain, domain_ids):
    return update_domain_selections(selected_per_domain, domain_ids)


@dash.callback(
    Output({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.MATCH}, "value"),
    Input({"type": "domain-config-select-all", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.MATCH, "action": dash.ALL}, "n_clicks"),
    State({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.MATCH}, "options"),
    prevent_initial_call=True,
)
def sim_domain_select_all(n_clicks, options):
    return domain_select_all(n_clicks, options)


@dash.callback(
    Output({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value", allow_duplicate=True),
    Input({"type": "preview-config-select-all", "sim": dash.MATCH, "arch": dash.MATCH, "action": dash.ALL}, "n_clicks"),
    State({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "options"),
    prevent_initial_call=True,
)
def sim_preview_select_all(n_clicks, options):
    return preview_select_all(n_clicks, options)


@dash.callback(
    Output({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
    Input({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State({"type": "domain-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": dash.ALL}, "id"),
    State({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
    State({"type": "domain-selections", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
)
def sim_sync_preview_values(selected_per_domain, domain_ids, current_preview_values, arch_metadata, prev_selections):
    return sync_preview_values(
        selected_per_domain, domain_ids, current_preview_values, arch_metadata, prev_selections
    )


@dash.callback(
    Output({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value", allow_duplicate=True),
    Input({"type": "default-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": "default"}, "value"),
    State({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sim_sync_default_to_preview(default_value, preview_value, arch_metadata):
    return sync_default_to_preview(default_value, preview_value, arch_metadata)


@dash.callback(
    Output({"type": "default-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH, "domain": "default"}, "value"),
    Input({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sim_sync_preview_to_default(preview_value, arch_metadata):
    return sync_preview_to_default(preview_value, arch_metadata)


@dash.callback(
    Output({"type": "preview-config-title", "sim": dash.MATCH, "arch": dash.MATCH}, "children"),
    Input({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.MATCH}, "value"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def sim_update_preview_title(preview_value, arch_metadata):
    return update_preview_title(preview_value, arch_metadata)


@dash.callback(
    Output({"type": "arch-count", "sim": dash.MATCH, "arch": dash.ALL}, "children"),
    Input({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.ALL}, "value"),
    Input({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.ALL}, "value"),
    State({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "arch-count", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "arch-metadata", "sim": dash.MATCH, "arch": dash.ALL}, "data"),
)
def sim_update_arch_count(preview_values, switch_values, preview_ids, switch_ids, count_ids, metadatas):
    """The "selected/total configs" badge of an architecture inside a simulation.

    Written with ALL rather than MATCH on the architecture because an
    architecture with too many combinations has no preview checklist at all: a
    MATCH group would then be incomplete and Dash would report a nonexistent
    object.
    """
    return update_arch_count(preview_values, switch_values, preview_ids, switch_ids, count_ids, metadatas)


@dash.callback(
    Output({"type": "sim-selection", "sim": dash.MATCH}, "data"),
    Input({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.ALL}, "value"),
    Input({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.ALL}, "value"),
    State({"type": "preview-config-checklist", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "sim-arch-switch", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "sim-arch-extra", "sim": dash.MATCH, "arch": dash.ALL}, "data"),
    State({"type": "sim-arch-extra", "sim": dash.MATCH, "arch": dash.ALL}, "id"),
    State({"type": "sim-orphan-entries", "sim": dash.MATCH}, "data"),
)
def sync_simulation_selection(
    preview_values, switch_values, preview_ids, switch_ids, extra_values, extra_ids, orphan_entries
):
    """
    What a simulation runs is the union of what the architectures enabled inside
    it have checked -- not a cross product: a simulation runs each selected
    configuration once.
    """
    enabled = {
        sid.get("arch"): bool(value)
        for value, sid in zip(switch_values or [], switch_ids or [])
        if isinstance(sid, dict)
    }

    entries = []
    for values, pid in zip(preview_values or [], preview_ids or []):
        if not isinstance(pid, dict) or not enabled.get(pid.get("arch")):
            continue
        entries.extend(_sim_entry_from_combo(value) for value in (values or []) if value is not None)
    for values, eid in zip(extra_values or [], extra_ids or []):
        if not isinstance(eid, dict) or not enabled.get(eid.get("arch")):
            continue
        entries.extend(str(value) for value in (values or []) if value is not None)
    entries.extend(str(value) for value in (orphan_entries or []))
    return list(dict.fromkeys(entries))


@dash.callback(
    Output({"type": "sim-count", "sim": dash.ALL}, "children"),
    Input({"type": "sim-selection", "sim": dash.ALL}, "data"),
    Input({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "value"),
    # An Input rather than a State: adding or removing a listed
    # architecture changes the total the badge shows, and nothing else.
    Input({"type": "sim-metadata", "sim": dash.ALL}, "data"),
    State({"type": "sim-selection", "sim": dash.ALL}, "id"),
    State({"type": "arch-title", "arch": dash.ALL, "is_switch": True}, "id"),
    State({"type": "sim-count", "sim": dash.ALL}, "id"),
)
def update_simulation_counts(selection_values, switch_values, metadatas, selection_ids, switch_ids, count_ids):
    """
    Keep every simulation's badge in sync with its selection and its switch.

    Written with ALL rather than MATCH because the switch is keyed by "arch"
    (it is the shared instance switch) while the selection is keyed by "sim": a
    single MATCH group cannot span two different wildcard key names.
    """
    selected = {
        pid.get("sim"): len(value or [])
        for value, pid in zip(selection_values or [], selection_ids or [])
        if isinstance(pid, dict)
    }
    enabled = {
        sid.get("arch"): bool(value)
        for value, sid in zip(switch_values or [], switch_ids or [])
        if isinstance(sid, dict)
    }
    n_entries_by_sim = {
        (data or {}).get("sim_name"): (data or {}).get("n_entries", 0)
        for data in (metadatas or [])
    }

    return [
        _simulation_badge_text(
            n_entries_by_sim.get(cid.get("sim"), 0),
            selected.get(cid.get("sim"), 0),
            enabled.get(cid.get("sim"), False),
        )
        for cid in (count_ids or [])
    ]

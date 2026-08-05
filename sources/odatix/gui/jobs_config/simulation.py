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

from dash import dcc, html

import odatix.gui.ui_components as ui
from odatix.gui.icons import icon

from odatix.gui.jobs_config.arch_widgets import _arch_config_widgets
from odatix.gui.jobs_config.common import _arch_badge_text, _simulation_badge_text

######################################
# Simulation mode
######################################
#
# A simulation run is set up the other way around from every other job type: the
# instances are the simulations, and what each of them selects is a set of
# *architecture configurations* to run on -- not configurations of its own (a
# simulation has none). The settings file mirrors that shape:
#
#   simulations:
#     - TB_Example:
#       - Example_Counter_vhdl/04bits
#       - Example_Counter_vhdl/08bits+width/16
#
# A simulation card therefore nests one collapsible sub-card per architecture,
# each holding the very same widgets an architecture gets in every other job
# type (parameter-domain panels plus the preview checklist), built by
# _arch_config_widgets. Those nested widgets carry an extra "sim" id key, which
# keeps them in callback groups of their own while the layout stays shared.
#
# The union of what the nested previews have checked is mirrored into a
# per-simulation store ("sim-selection"), which is what Save and Run read.
#
# A simulation only shows the architectures it declares itself compatible with
# ("compatible_architectures" in its settings file), and a card is built for
# those only: building one per architecture and hiding the rest made the page
# grow as simulations x architectures, which is what made it slow. Adding one
# back (the dropdown at the bottom of the card) builds its card on the spot, and
# removing one (the cross next to its name) hides it, so it can be added back
# without rebuilding. Either way the list is rewritten in the simulation's
# settings file right away: it describes the simulation, not the run being
# configured, so it does not wait for the page's Save.


def _compatible_architectures(simulations, sim_name, architectures):
    """
    The architectures a simulation card shows, and whether that is a choice or a
    fallback.

    A simulation that lists none makes no claim: everything is shown, and
    nothing is written to its settings file until the user removes something.
    """
    try:
        declared = list(simulations.entry(sim_name).settings.compatible_architectures)
    except Exception:
        declared = []
    declared = [str(name) for name in declared if str(name).strip() != ""]
    if not declared:
        return list(architectures), False
    return declared, True


def _sim_entry_from_combo(combo: str) -> str:
    """Convert a preview combination ("Arch + domain/value") into the syntax the
    simulation settings file uses ("Arch+domain/value")."""
    return "+".join(part.strip() for part in str(combo).split(" + ") if part.strip())


def _combo_from_sim_entry(entry: str) -> str:
    """Inverse of _sim_entry_from_combo."""
    return " + ".join(part.strip() for part in str(entry).split("+") if part.strip())


def _sim_entry_arch(entry: str) -> str:
    """The architecture a simulation settings entry runs on."""
    return str(entry).split("+", 1)[0].split("/", 1)[0].strip()


def _sim_arch_card(architectures_collection, sim_name, arch_name, saved_values, arch_enabled, mode):
    """One collapsible architecture sub-card of a simulation card.

    Also used to build the card of an architecture added from the dropdown,
    which is why it is a function of its own: cards are built only for the
    architectures a simulation actually shows (see _simulation_job_sections).

    Returns:
        tuple: (card, info) with info as returned by _arch_config_widgets.
    """
    domain_tiles, preview_tile, info = _arch_config_widgets(
        architectures_collection,
        arch_name,
        saved_values,
        arch_enabled,
        mode,
        id_extra={"sim": sim_name},
    )

    card = html.Div(
        children=[
            html.Div(
                children=[
                    html.Div(
                        children=[
                            dcc.Checklist(
                                options=[{"label": "", "value": True}],
                                value=[True] if arch_enabled else [],
                                id={"type": "sim-arch-switch", "sim": sim_name, "arch": arch_name},
                                className="checklist-switch",
                            ),
                            html.Span(arch_name, className="jobs-arch-name"),
                            html.Span(
                                _arch_badge_text(
                                    info["n_combos"],
                                    info["n_selected"],
                                    info["default_selected"],
                                    arch_enabled,
                                ),
                                id={"type": "arch-count", "sim": sim_name, "arch": arch_name},
                                className="odx-badge",
                            ),
                        ],
                        className="jobs-arch-headline",
                    ),
                    html.Button(
                        "×",
                        id={"type": "sim-arch-remove", "sim": sim_name, "arch": arch_name},
                        n_clicks=0,
                        title="Remove " + arch_name + " from the architectures "
                              + sim_name + " is compatible with",
                        className="odx-mini-button small-button jobs-sim-arch-remove",
                    ),
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
                id={"type": "sim-arch-body", "sim": sim_name, "arch": arch_name},
                className="jobs-arch-body animated-section" + ("" if arch_enabled else " hide"),
            ),
            dcc.Store(
                id={"type": "arch-metadata", "sim": sim_name, "arch": arch_name},
                data={
                    "arch_name": arch_name,
                    "n_combos": info["n_combos"],
                    "virtual_variants": info["virtual_variants"],
                },
            ),
            dcc.Store(
                id={"type": "domain-selections", "sim": sim_name, "arch": arch_name},
                data=info["domains_configs"],
            ),
            # Saved entries no combination accounts for: kept aside
            # and re-contributed to the selection as they are.
            dcc.Store(
                id={"type": "sim-arch-extra", "sim": sim_name, "arch": arch_name},
                data=[_sim_entry_from_combo(value) for value in info["unmatched"]],
            ),
        ],
        id={"type": "sim-arch-card", "sim": sim_name, "arch": arch_name},
        className="jobs-arch-card nested" + (" enabled" if arch_enabled else ""),
    )
    return card, info


def _simulation_job_sections(context, selection_settings):
    """
    Build one card per simulation, each holding a collapsible sub-card per
    architecture where the configurations that simulation runs are picked, the
    same way they are picked for a synthesis.

    Returns:
        tuple: (sections, baseline_selection) where baseline_selection is the
        simulation -> entries mapping a fresh page load is equivalent to (used
        as the "saved" baseline so nothing falsely reads as unsaved).
    """
    architectures_collection = context["workspace"].architectures
    simulations = context["instances"]

    selection_map = context["workspace"].jobs.simulation.settings.simulations
    architectures = architectures_collection.names()

    baseline_selection = {}
    sections = []
    for sim_name in simulations:
        sim_enabled = sim_name in selection_map

        compatible, explicit = _compatible_architectures(
            context["workspace"].simulations, sim_name, architectures
        )
        compatible_set = set(compatible)

        # Group the saved entries by the architecture they belong to, converted
        # to the preview syntax _arch_config_widgets expects.
        saved_by_arch = {}
        for entry in selection_map.get(sim_name, []):
            saved_by_arch.setdefault(_sim_entry_arch(entry), []).append(_combo_from_sim_entry(entry))

        arch_cards = []
        shown_architectures = []
        # Kept apart, and concatenated at the end in this exact order, so the
        # baseline matches how sync_simulation_selection() rebuilds the store:
        # the "unsaved changes" check compares the two lists element by element.
        checked_entries = []
        extra_entries = []
        n_total = 0
        n_selected_total = 0
        for arch_name in architectures:
            # An architecture this simulation does not mention runs nothing yet;
            # its sub-card is off, with everything pre-checked so that turning it
            # on is a single click (exactly like a disabled architecture card).
            arch_enabled = sim_enabled and arch_name in saved_by_arch
            # An architecture the simulation runs on is shown whatever the
            # compatibility list says: hiding a card would hide a selection.
            arch_shown = arch_name in compatible_set or arch_enabled
            # A card is built only for the architectures the simulation shows:
            # building the hidden ones too made the page grow as
            # simulations x architectures, for widgets nobody can see.
            if not arch_shown:
                continue
            shown_architectures.append(arch_name)
            card, info = _sim_arch_card(
                architectures_collection,
                sim_name,
                arch_name,
                saved_by_arch.get(arch_name, []),
                arch_enabled,
                context["mode"],
            )

            n_total += info["n_combos"] + 1
            selected = list(info["filtered_selected"])
            # Entries this architecture cannot enumerate (too many combinations)
            # or no longer offers are carried untouched so saving never silently
            # drops a hand-written selection.
            extra = list(info["unmatched"])
            if arch_enabled:
                n_selected_total += len(selected) + len(extra)
                checked_entries.extend(_sim_entry_from_combo(value) for value in selected)
                extra_entries.extend(_sim_entry_from_combo(value) for value in extra)

            arch_cards.append(card)

        # Entries of a saved selection whose architecture does not exist anymore
        # have no sub-card to live in. They are still this simulation's, so they
        # ride along in a store rather than being dropped on the next Save.
        orphan_entries = [
            _sim_entry_from_combo(value)
            for arch_name, values in saved_by_arch.items()
            if arch_name not in architectures
            for value in values
        ]
        if sim_enabled and orphan_entries:
            n_selected_total += len(orphan_entries)
            n_total += len(orphan_entries)

        if not architectures:
            arch_cards.append(
                ui.panel(
                    title="Architectures",
                    body=html.Div(f"No architecture found in {architectures_collection.path}.", className="odx-panel-note"),
                )
            )

        # Where the cards of the architectures added from the dropdown below are
        # appended: they are built on demand rather than upfront (see
        # update_compatible_architectures).
        arch_cards.append(html.Div(id={"type": "sim-added-archs", "sim": sim_name}, children=[]))

        # Names the simulation declares but this workspace does not offer: kept
        # so that adding or removing an architecture here never drops them.
        missing_compatible = [name for name in compatible if name not in architectures]
        compatible_data = shown_architectures + missing_compatible

        arch_cards.append(
            html.Div(
                children=[
                    dcc.Dropdown(
                        id={"type": "sim-compatible-add", "sim": sim_name},
                        options=[
                            {"label": name, "value": name}
                            for name in architectures
                            if name not in shown_architectures
                        ],
                        placeholder="Add a compatible architecture...",
                        value=None,
                        className="jobs-sim-arch-add",
                    ),
                ],
                className="jobs-sim-arch-add-row",
            )
        )

        sim_entries = list(dict.fromkeys(checked_entries + extra_entries + orphan_entries))
        if sim_enabled:
            baseline_selection[sim_name] = sim_entries

        sim_buttons = html.Div(
            children=[
                ui.icon_button(
                    icon=icon("gear", className="icon"),
                    text=context["settings_text"],
                    tooltip="Open the settings of this simulation",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["settings_link"](sim_name),
                    multiline=True,
                    width="135px",
                ),
                ui.icon_button(
                    icon=icon("metrics", className="icon blue"),
                    text=context["config_text"],
                    tooltip="Open the Exported Metrics Editor for this simulation",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["config_link"](sim_name),
                    multiline=False,
                    width="135px",
                ),
            ],
            className="jobs-arch-buttons",
        )

        sections.append(
            html.Div(
                children=[
                    html.Div(
                        children=[
                            html.Div(
                                children=[
                                    dcc.Checklist(
                                        options=[{"label": "", "value": True}],
                                        value=[True] if sim_enabled else [],
                                        id={"type": "arch-title", "arch": sim_name, "is_switch": True},
                                        className="checklist-switch",
                                    ),
                                    html.Span(sim_name, id={"type": "arch-title", "arch": sim_name}, className="jobs-arch-name"),
                                    html.Span(
                                        _simulation_badge_text(n_total, n_selected_total, sim_enabled),
                                        id={"type": "sim-count", "sim": sim_name},
                                        className="odx-badge",
                                    ),
                                ],
                                className="jobs-arch-headline",
                            ),
                            sim_buttons,
                        ],
                        className="jobs-arch-header",
                    ),
                    html.Div(
                        children=html.Div(arch_cards, className="jobs-sim-archs"),
                        id={"type": "param-domains-container", "arch": sim_name},
                        className="jobs-arch-body animated-section" + ("" if sim_enabled else " hide"),
                    ),
                    dcc.Store(
                        id={"type": "sim-metadata", "sim": sim_name},
                        data={"sim_name": sim_name, "n_entries": n_total},
                    ),
                    dcc.Store(
                        id={"type": "sim-orphan-entries", "sim": sim_name},
                        data=orphan_entries,
                    ),
                    # The architectures this simulation says it runs on. Written
                    # straight to its settings file when it changes, so it is
                    # not part of what the page's Save button covers.
                    dcc.Store(
                        id={"type": "sim-compatible", "sim": sim_name},
                        data=compatible_data,
                    ),
                    # What this simulation runs, kept in sync with the nested
                    # architecture cards and read by Save / Run.
                    dcc.Store(
                        id={"type": "sim-selection", "sim": sim_name},
                        data=sim_entries,
                    ),
                ],
                id={"type": "job-section", "arch": sim_name},
                className="jobs-arch-card" + (" enabled" if sim_enabled else ""),
            )
        )

    return sections, baseline_selection

def _collect_simulation_selection(switch_values, switch_ids, selection_values, selection_ids) -> dict:
    """
    The simulation -> architecture entries mapping the page currently describes,
    keeping only the simulations whose switch is on.
    """
    by_sim = {}
    for value, sel_id in zip(selection_values or [], selection_ids or []):
        sim_name = sel_id.get("sim") if isinstance(sel_id, dict) else None
        if sim_name:
            by_sim[sim_name] = list(dict.fromkeys([str(v) for v in (value or []) if v is not None]))

    selection = {}
    for value, sid in zip(switch_values or [], switch_ids or []):
        sim_name = sid.get("arch") if isinstance(sid, dict) else None
        if sim_name and bool(value):
            selection[sim_name] = by_sim.get(sim_name, [])
    return selection

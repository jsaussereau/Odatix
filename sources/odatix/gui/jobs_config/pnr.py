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
import odatix.lib.eda_tools as eda_tools
import odatix.lib.hard_settings as hard_settings
import odatix.lib.pnr_source as pnr_source
from odatix.gui.icons import icon

from odatix.gui.jobs_config.common import (
    _preview_title,
    _select_all_buttons,
    _simulation_badge_text,
)

######################################
# Place & route mode
######################################
#
# A place & route run is the only job type whose input is not in the workspace
# configuration but in the work tree: it starts from synthesis jobs that have
# already run and succeeded, possibly with another eda tool (see
# odatix.lib.pnr_source).
#
# The page keeps the shape a simulation has: one card per eda tool, holding one
# nested card per architecture that tool synthesized, where the completed jobs
# are picked with the very same widgets an architecture gets everywhere else —
# one panel per parameter domain plus the preview checklist.
#
# There is nothing to *combine* here though (what a job is was decided by the
# synthesis): the domains are read back from what is on disk, by splitting the
# work directory names of the sources, and checking a domain value selects the
# sources that have it rather than generating a new combination.


def _pnr_tool_of(work_dirname):
    """The eda tool a work directory name belongs to ("genus@fast" -> "genus")."""
    return eda_tools.split_tool_work_dirname(str(work_dirname))[0]


def _pnr_sources_by_tool(work_root, odatix_settings):
    """
    The completed synthesis jobs of the workspace, grouped by the work directory
    of the tool that produced them ("design_compiler", "genus@fast", ...).

    Jobs that did not write the handoff files are listed too, so a synthesis that
    cannot be placed & routed shows up as unusable rather than silently missing.
    """
    result_types = None
    if isinstance(odatix_settings, dict):
        result_types = {
            job_type: {"path": odatix_settings.get(f"{job_type}_work_path") or job_type}
            for job_type in pnr_source.SOURCE_JOB_TYPES
        }

    grouped = {}
    for source in pnr_source.discover_sources(work_root, result_types=result_types, require_handoff=False):
        grouped.setdefault(source.work_dirname, []).append(source)
    return grouped


def _group_pnr_selections(sources_setting, work_dirnames) -> dict:
    """
    Group the saved selectors by the card they belong to, i.e. by the work
    directory of the tool that ran the synthesis.

    The generic _group_arch_selections cannot be used here for two reasons: the
    first "/"-separated segment of a selector is the source job type, not the
    tool, and a selector may name the tool with a wildcard, in which case it
    belongs to *every* card rather than to one named "*" (which would leave them
    all switched off while the settings file selects them).
    """
    grouped = {}
    for entry in sources_setting or []:
        if entry is None:
            continue
        parsed = pnr_source.parse_selector(str(entry))
        if parsed is None:
            continue
        if parsed["work_dirname"] == pnr_source.WILDCARD:
            targets = list(work_dirnames)
        else:
            targets = [parsed["work_dirname"]]
        for work_dirname in targets:
            grouped.setdefault(work_dirname, []).append(str(entry))
    return grouped


# The levels of a source that are not parameter domains but still tell two
# sources apart. They get a panel of their own, keyed with a "@" prefix so they
# can never collide with the name of a real parameter domain.
PNR_JOB_TYPE_DOMAIN = "@job_type"
PNR_TARGET_DOMAIN = "@target"
PNR_FREQUENCY_DOMAIN = "@frequency"

PNR_DOMAIN_TITLES = {
    PNR_JOB_TYPE_DOMAIN: "Synthesis type",
    PNR_TARGET_DOMAIN: "Target",
    PNR_FREQUENCY_DOMAIN: "Frequency",
}


def _pnr_split_config_token(token, known_domains):
    """
    Split a "<domain>_<configuration>" token of a work directory name back into
    the domain and the configuration it was built from (see
    ArchitectureHandler: the work directory of a configuration with parameter
    domains is "<config>+<domain>_<value>+...").

    The separator is also a legal character of both names, so the known domains
    of the architecture are tried first, longest first; the split falls back to
    the first "_" for an architecture that does not exist anymore.
    """
    for domain in sorted(known_domains or [], key=len, reverse=True):
        prefix = str(domain) + "_"
        if token.startswith(prefix):
            return str(domain), token[len(prefix):]
    domain, _, value = token.partition("_")
    return domain, value


def _pnr_source_tokens(source, known_domains):
    """The domain -> value mapping describing one source: its parameter domains,
    read back from the work directory name, plus the levels above it."""
    tokens = {
        PNR_JOB_TYPE_DOMAIN: source.job_type,
        PNR_TARGET_DOMAIN: source.target,
        PNR_FREQUENCY_DOMAIN: source.frequency_segment,
    }
    parts = [part for part in str(source.configuration).split("+") if part]
    if parts:
        tokens[hard_settings.main_parameter_domain] = parts[0]
    for part in parts[1:]:
        domain, value = _pnr_split_config_token(part, known_domains)
        if domain and value:
            tokens[domain] = value
    return tokens


def _pnr_domain_values(tokens_by_selector, known_domains):
    """
    The panels an architecture card shows, in display order: its main parameter
    domain, its parameter domains, then the target and the frequency. A level
    every source of the card shares says nothing (a single chip to pick from),
    so only the synthesis type is dropped when it is uniform — the target and
    the frequency are kept, they are what a place & route job is named after.
    """
    values = {}
    for tokens in tokens_by_selector.values():
        for domain, value in tokens.items():
            values.setdefault(domain, set()).add(value)

    order = [hard_settings.main_parameter_domain]
    order += [domain for domain in (known_domains or []) if domain in values]
    order += [domain for domain in sorted(values) if domain not in order and not domain.startswith("@")]
    order += [PNR_TARGET_DOMAIN, PNR_FREQUENCY_DOMAIN, PNR_JOB_TYPE_DOMAIN]

    ordered = {}
    for domain in order:
        if domain not in values:
            continue
        if domain == PNR_JOB_TYPE_DOMAIN and len(values[domain]) < 2:
            continue
        ordered[domain] = sorted(values[domain])
    return ordered


def _pnr_domain_title(domain):
    if domain in PNR_DOMAIN_TITLES:
        return PNR_DOMAIN_TITLES[domain]
    if domain == hard_settings.main_parameter_domain:
        return "Main parameter domain"
    return domain


def _pnr_value_label(domain, value):
    """A domain value as a chip reads it. Only the frequency needs help: it is
    stored as the work directory name ("50MHz", or "fmax" for an fmax search)."""
    if domain == PNR_FREQUENCY_DOMAIN and value.endswith("MHz"):
        return value[: -len("MHz")] + " MHz"
    return value


def _pnr_source_label(source):
    """How a source reads in the preview checklist of its architecture card (the
    architecture itself is the card, so it is not repeated)."""
    label = source.configuration + "  ·  " + source.target
    if source.frequency is not None:
        label += "  ·  " + str(source.frequency) + " MHz"
    else:
        label += "  ·  fmax"
    return label


def _pnr_unusable_badge_text(n_unusable: int) -> str:
    """The badge counting the synthesis jobs left out of an architecture card
    because they handed no netlist over."""
    word = "synthesis" if n_unusable == 1 else "syntheses"
    return f"{n_unusable} {word} without netlist"


def _pnr_config_widgets(work_dirname, arch_name, sources, selected_values, enabled, architectures):
    """
    Build the body an architecture gets inside a place & route card: one panel
    per parameter domain of its completed synthesis jobs, and the preview
    checklist holding those jobs.

    Returns the same (domain_tiles, preview_tile, info) triple as
    _arch_config_widgets, so the nested-card layout and the callbacks keyed on
    those widget ids apply unchanged. Unlike an architecture card, the domain
    panels enumerate nothing: they *select* among the sources that exist.

    Args:
        selected_values: the saved selectors of this tool (wildcards included);
            the ones this architecture matches are checked.
        enabled: whether that saved selection applies. Nothing saved yet means
            everything runnable is pre-checked, so enabling the card is a single
            click (exactly like a disabled architecture card).
    """
    id_extra = {"sim": work_dirname}
    architecture = architectures.get(arch_name) if architectures is not None else None
    known_domains = architecture.domains.sub_names() if architecture is not None else []

    # A synthesis that handed no netlist over cannot be placed & routed. Listing
    # it would only add unselectable noise, so it is left out of the card and
    # only counted, in a badge next to the configuration count.
    options = []
    tokens_by_selector = {}
    n_unusable = 0
    for source in sources:
        if source.missing_handoff_files():
            n_unusable += 1
            continue
        options.append({"label": _pnr_source_label(source), "value": source.selector})
        tokens_by_selector[source.selector] = _pnr_source_tokens(source, known_domains)

    available = list(tokens_by_selector.keys())

    if enabled:
        parsed_selectors = [pnr_source.parse_selector(entry) for entry in selected_values or []]
        selected = [
            source.selector
            for source in sources
            if source.selector in tokens_by_selector
            and any(parsed and pnr_source.source_matches(source, parsed) for parsed in parsed_selectors)
        ]
    else:
        selected = list(available)

    domains_values = _pnr_domain_values(tokens_by_selector, known_domains)

    # A domain chip is checked when at least one selected source has that value:
    # the panels describe what the preview holds, the same way they do for an
    # architecture.
    checked_by_domain = {}
    for selector in selected:
        for domain, value in tokens_by_selector.get(selector, {}).items():
            checked_by_domain.setdefault(domain, set()).add(value)

    domain_tiles = []
    for domain, values in domains_values.items():
        checklist = dcc.Checklist(
            options=[{"label": _pnr_value_label(domain, value), "value": value} for value in values],
            id={"type": "domain-config-checklist", "arch": arch_name, "domain": domain, **id_extra},
            value=[value for value in values if value in checked_by_domain.get(domain, set())],
            className="odx-chips",
        )
        domain_tiles.append(
            ui.panel(
                title=[
                    html.Span(_pnr_domain_title(domain)),
                    html.Span(f"{len(values)}", className="odx-badge"),
                ],
                tools=_select_all_buttons(
                    "domain-config-select-all", {"arch": arch_name, "domain": domain, **id_extra}
                ),
                body=checklist,
            )
        )

    # A source is picked whole or not at all: there is no default configuration
    # to mirror. The checkbox is still rendered (empty, hidden) because the
    # callbacks shared with the simulation cards are keyed on it.
    domain_tiles.append(
        html.Div(
            dcc.Checklist(
                options=[],
                id={"type": "default-config-checklist", "arch": arch_name, "domain": "default", **id_extra},
                value=[],
            ),
            style={"display": "none"},
        )
    )

    preview_tile = ui.panel(
        title=_preview_title(len(options), False, len(selected)),
        title_id={"type": "preview-config-title", "arch": arch_name, **id_extra},
        tools=_select_all_buttons("preview-config-select-all", {"arch": arch_name, **id_extra}),
        body=dcc.Checklist(
            options=options,
            id={"type": "preview-config-checklist", "arch": arch_name, **id_extra},
            value=selected,
            className="odx-check-list",
        ),
        body_className="scroll tall",
    )

    info = {
        "n_combos": len(options),
        "n_selected": len(selected),
        "default_selected": False,
        "filtered_selected": selected,
        # Only the domains that got a panel: this store is the "previous state"
        # sync_preview_values compares the panels against, so a domain it cannot
        # see must not appear in it (it would read as a domain just emptied).
        "domains_configs": {
            domain: sorted(checked_by_domain[domain])
            for domain in domains_values
            if checked_by_domain.get(domain)
        },
        "sources": tokens_by_selector,
        "n_unusable": n_unusable,
        "unmatched": [],
        "too_many": False,
    }
    return domain_tiles, preview_tile, info


def _pnr_sync_preview_values(
    arch_metadata, current_domains, current_preview_values, changed_domain, added_values, removed_values
):
    """
    What checking (or unchecking) a domain value does to the preview of a place
    & route card. The sources are not combined, they exist or they do not, so
    the panels select among them instead of generating combinations:

      * a value checked selects every source that has it *and* whose other
        levels are checked too, so the panels read as a filter,
      * a value unchecked deselects every source that has it.

    Called by sync_preview_values once it has worked out what changed, so both
    kinds of card share the "which domain moved" bookkeeping.
    """
    sources = (arch_metadata or {}).get("sources") or {}
    preview_set = set(current_preview_values or [])

    for selector, tokens in sources.items():
        value = tokens.get(changed_domain)
        if value in removed_values:
            preview_set.discard(selector)
        elif value in added_values:
            if all(
                tokens.get(domain) in set(values)
                for domain, values in current_domains.items()
                if domain != changed_domain
            ):
                preview_set.add(selector)

    return sorted(preview_set)


def _pnr_job_sections(context, selection_settings):
    """
    Build one card per eda tool that ran a synthesis, each holding a nested card
    per architecture it synthesized, exactly like a simulation card holds the
    architectures it runs on.

    Returns:
        tuple: (sections, baseline_selection) where baseline_selection is the
        flat selector list a fresh page load is equivalent to (used as the
        "saved" baseline so nothing falsely reads as unsaved).
    """
    architectures = context["workspace"].architectures
    sources_by_tool = context["sources_by_tool"]
    selection_map = _group_pnr_selections(
        selection_settings.get(context["selection_key"], []), context["instances"]
    )

    baseline_selection = []
    sections = []
    for work_dirname in context["instances"]:
        tool_sources = sources_by_tool.get(work_dirname, [])
        tool_enabled = work_dirname in selection_map
        saved_selectors = selection_map.get(work_dirname, [])

        sources_by_arch = {}
        for source in tool_sources:
            sources_by_arch.setdefault(source.architecture, []).append(source)

        arch_cards = []
        tool_entries = []
        n_total = 0
        n_selected_total = 0
        n_unusable_total = 0
        for arch_name, arch_sources in sources_by_arch.items():
            domain_tiles, preview_tile, info = _pnr_config_widgets(
                work_dirname, arch_name, arch_sources, saved_selectors, tool_enabled, architectures
            )
            # An architecture none of the saved selectors names runs nothing yet;
            # its sub-card is off, with everything pre-checked.
            arch_enabled = tool_enabled and bool(info["filtered_selected"])

            n_total += info["n_combos"]
            n_unusable_total += info["n_unusable"]
            if arch_enabled:
                n_selected_total += info["n_selected"]
                tool_entries.extend(info["filtered_selected"])

            arch_cards.append(
                html.Div(
                    children=[
                        html.Div(
                            children=html.Div(
                                children=[
                                    dcc.Checklist(
                                        options=[{"label": "", "value": True}],
                                        value=[True] if arch_enabled else [],
                                        id={"type": "sim-arch-switch", "sim": work_dirname, "arch": arch_name},
                                        className="checklist-switch",
                                    ),
                                    html.Span(arch_name, className="jobs-arch-name"),
                                    html.Span(
                                        _simulation_badge_text(
                                            info["n_combos"], info["n_selected"], arch_enabled
                                        ),
                                        id={"type": "arch-count", "sim": work_dirname, "arch": arch_name},
                                        className="odx-badge",
                                    ),
                                ] + ([
                                    html.Span(
                                        _pnr_unusable_badge_text(info["n_unusable"]),
                                        title="These syntheses handed no netlist over: they cannot be placed & routed.",
                                        className="odx-badge caution",
                                    )
                                ] if info["n_unusable"] else []),
                                className="jobs-arch-headline",
                            ),
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
                            id={"type": "sim-arch-body", "sim": work_dirname, "arch": arch_name},
                            className="jobs-arch-body animated-section" + ("" if arch_enabled else " hide"),
                        ),
                        dcc.Store(
                            id={"type": "arch-metadata", "sim": work_dirname, "arch": arch_name},
                            data={
                                "kind": "pnr",
                                "arch_name": arch_name,
                                "n_combos": info["n_combos"],
                                "sources": info["sources"],
                            },
                        ),
                        dcc.Store(
                            id={"type": "domain-selections", "sim": work_dirname, "arch": arch_name},
                            data=info["domains_configs"],
                        ),
                        dcc.Store(
                            id={"type": "sim-arch-extra", "sim": work_dirname, "arch": arch_name},
                            data=[],
                        ),
                    ],
                    id={"type": "sim-arch-card", "sim": work_dirname, "arch": arch_name},
                    className="jobs-arch-card nested" + (" enabled" if arch_enabled else ""),
                )
            )

        if not arch_cards:
            arch_cards.append(
                ui.panel(
                    title="Synthesized designs",
                    body=html.Div("No completed synthesis found for this tool.", className="odx-panel-note"),
                )
            )

        tool_entries = list(dict.fromkeys(tool_entries))
        if tool_enabled:
            baseline_selection.extend(tool_entries)

        tool_buttons = html.Div(
            children=[
                ui.icon_button(
                    icon=icon("gear", className="icon"),
                    text=context["settings_text"],
                    tooltip="Open the settings of this tool",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["settings_link"](work_dirname),
                    multiline=True,
                    width="135px",
                ),
                ui.icon_button(
                    icon=icon("metrics", className="icon blue"),
                    text=context["config_text"],
                    tooltip="Open the Exported Metrics Editor for this tool",
                    tooltip_options="bottom delay",
                    color="default",
                    link=context["config_link"](work_dirname),
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
                                        value=[True] if tool_enabled else [],
                                        id={"type": "arch-title", "arch": work_dirname, "is_switch": True},
                                        className="checklist-switch",
                                    ),
                                    html.Span(
                                        work_dirname,
                                        id={"type": "arch-title", "arch": work_dirname},
                                        className="jobs-arch-name",
                                    ),
                                    html.Span(
                                        _simulation_badge_text(n_total, n_selected_total, tool_enabled),
                                        id={"type": "sim-count", "sim": work_dirname},
                                        className="odx-badge",
                                    ),
                                ] + ([
                                    html.Span(
                                        _pnr_unusable_badge_text(n_unusable_total),
                                        title="These syntheses handed no netlist over: they cannot be placed & routed.",
                                        className="odx-badge caution",
                                    )
                                ] if n_unusable_total else []),
                                className="jobs-arch-headline",
                            ),
                            tool_buttons,
                        ],
                        className="jobs-arch-header",
                    ),
                    html.Div(
                        children=html.Div(arch_cards, className="jobs-sim-archs"),
                        id={"type": "param-domains-container", "arch": work_dirname},
                        className="jobs-arch-body animated-section" + ("" if tool_enabled else " hide"),
                    ),
                    dcc.Store(
                        id={"type": "sim-metadata", "sim": work_dirname},
                        data={"sim_name": work_dirname, "n_entries": n_total},
                    ),
                    dcc.Store(id={"type": "sim-orphan-entries", "sim": work_dirname}, data=[]),
                    # What this tool places & routes, kept in sync with the
                    # nested architecture cards and read by Save / Run.
                    dcc.Store(id={"type": "sim-selection", "sim": work_dirname}, data=tool_entries),
                ],
                id={"type": "job-section", "arch": work_dirname},
                className="jobs-arch-card" + (" enabled" if tool_enabled else ""),
            )
        )

    return sections, list(dict.fromkeys(baseline_selection))

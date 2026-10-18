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

"""The widgets an architecture gets on the page: one panel per parameter domain,
the "Default configuration" panel, and the preview checklist holding the
resulting combinations. Shared by every job type -- the architecture cards, and
the architecture sub-cards nested in a simulation card."""

import itertools

import natsort
from dash import dcc, html

import odatix.gui.ui_components as ui
import odatix.lib.hard_settings as hard_settings
from odatix.workspace.configs import combinations, count_combinations
from odatix.workspace.selection import ExclusionFilter
import odatix.lib.virtual_param_domain as virtual_param_domain

from odatix.gui.jobs_config.common import (
    MAX_PREVIEW_COMBINATIONS,
    _preview_title,
    _select_all_buttons,
)

def _arch_name_from_entry(entry: str) -> str:
    first_part = str(entry).split(" + ")[0].strip()
    if "/" in first_part:
        return first_part.split("/")[0].strip()
    return first_part

def _group_arch_selections(architectures_setting) -> dict:
    if not architectures_setting:
        return {}
    if isinstance(architectures_setting, dict):
        architectures = list(architectures_setting)
    else:
        architectures = list(architectures_setting)
    grouped = {}
    for entry in architectures:
        if entry is None:
            continue
        arch_name = _arch_name_from_entry(entry)
        if not arch_name:
            continue
        grouped.setdefault(arch_name, []).append(str(entry))
    return grouped

def _virtual_variant_tokens(instances, name, mode):
    """
    Resolve the virtual parameter domains of a workflow or an architecture
    (command-placeholder variables defined under "variables" in its
    _settings.yml), by
    reusing the exact generation logic used at run time
    (run_workflow.check_settings() / ArchitectureHandler.expand_virtual_param_domains()).

    For architectures, the variables only become a parameter domain when
    "generate_command" actually references them; otherwise they keep their sole
    original meaning (generating configuration files), exactly like
    ArchitectureHandler._expand_arch_virtual_param_domains() decides.

    Returns:
        variants      : list of ["domain/value", ...] token lists, one per
                        generated variant (empty if there is none). These are
                        meant to be appended to every physical combination.
        domain_values : dict domain name -> sorted list of distinct values
                        seen across variants (for display only).
        error         : error message if the variable settings are invalid,
                         else None.
    """
    instance = instances.entry(name)
    settings = instance.settings.to_dict()
    virtual_domain_names = virtual_param_domain.get_virtual_domain_names(settings)
    if not virtual_domain_names:
        return [], {}, None

    if mode != "workflow":
        # Only "generate_command" consumes these variables as a parameter domain.
        generate_command = settings.get("generate_command", "") if settings.get("generate_rtl", False) else ""
        if not (virtual_param_domain.referenced_variable_names(generate_command) & virtual_domain_names):
            return [], {}, None

    settings_file = instance.settings_path
    variants = virtual_param_domain.build_variants(settings=settings, settings_file=settings_file, debug=False)
    if variants is None:
        return [], {}, "Invalid variable settings. Check the settings file."

    token_lists = [list(variant.get("requested_param_domains", [])) for variant in variants]
    token_lists = [tokens for tokens in token_lists if tokens]
    domain_values = {}
    for tokens in token_lists:
        for token in tokens:
            domain, _, value = token.partition("/")
            domain_values.setdefault(domain, set()).add(value)
    # Natural order: "500, 1000, 2000" and "1km, 10km", not the order of text.
    domain_values = {domain: natsort.natsorted(values) for domain, values in domain_values.items()}
    return token_lists, domain_values, None

def _extract_domain_values(arch_name: str, selections) -> dict:
    """Return mapping of domain -> set(values) found in preview selection strings."""
    values_by_domain = {}
    for entry in selections or []:
        if entry is None:
            continue
        parts = [p.strip() for p in str(entry).split(" + ") if p.strip()]
        for part in parts:
            if "/" not in part:
                continue
            domain, value = part.split("/", 1)
            if domain == arch_name:
                domain = hard_settings.main_parameter_domain
            if not domain or value == "":
                continue
            values_by_domain.setdefault(domain, set()).add(value)
    return values_by_domain

def _expand_wildcard_selection(entry: str, domains_configs: dict, arch_name: str) -> list:
    """
    Expand a saved selection entry that uses a domain-value wildcard (e.g.
    "Arch + addr/* + data/5", or the bare main-domain form "Arch/*"), mirroring
    the wildcard syntax ArchitectureHandler.configuration_wildcard() understands
    at run time, into every concrete "arch + domain/value + ..." combo string it
    represents (the exact format produced by odatix.workspace.configs.combinations).

    Returns [entry] unchanged if it uses no wildcard ("*") value.
    """
    parts = [p.strip() for p in str(entry).split(" + ") if p.strip()]
    if not parts:
        return []

    constraints = {}
    order = []
    for part in parts:
        if "/" not in part:
            continue
        domain, value = part.split("/", 1)
        if domain == arch_name:
            domain = hard_settings.main_parameter_domain
        constraints[domain] = value
        order.append(domain)

    if "*" not in constraints.values():
        return [entry]

    value_lists = [
        domains_configs.get(domain, []) if constraints[domain] == "*" else [constraints[domain]]
        for domain in order
    ]

    expanded = []
    for combo_values in itertools.product(*value_lists):
        replaced_parts = [
            f"{arch_name if domain == hard_settings.main_parameter_domain else domain}/{value}"
            for domain, value in zip(order, combo_values)
        ]
        if order and order[0] != hard_settings.main_parameter_domain:
            combo = [arch_name] + replaced_parts
        else:
            combo = replaced_parts
        expanded.append(" + ".join(combo))
    return expanded


def _arch_domains_configs(instances, arch_name) -> dict:
    """The configurations of every parameter domain of an architecture that
    actually uses parameters, keyed by domain (main domain included)."""
    instance = instances.get(arch_name)
    if instance is None:
        return {}
    # Natural order, so that "8bits" comes before "16bits" whatever the names.
    return {
        domain: natsort.natsorted(configurations)
        for domain, configurations in instance.parameter_domains().items()
    }


def _arch_config_widgets(instances, arch_name, selected_values, arch_enabled, mode, id_extra=None):
    """
    Build the body an architecture gets on this page: one panel per parameter
    domain to pick values from, the "Default configuration" panel, and the
    preview checklist holding the resulting combinations (the fine-grained
    control over what actually runs).

    id_extra is merged into every pattern-matching id. It is empty for the
    architecture-keyed job types, and {"sim": <name>} for the architecture
    panels nested in a simulation card, which keeps the two sets of widgets in
    separate callback groups while they share this layout (see
    _simulation_job_sections).

    Args:
        selected_values: the saved selection of this architecture, in preview
            format ("Arch + domain/value + ..."); wildcards are expanded here.
        arch_enabled: whether that saved selection applies. A disabled
            architecture has nothing saved yet, so everything is pre-checked:
            enabling it is then a single click.

    Returns:
        tuple: (domain_tiles, preview_tile, info) where info holds
        n_combos / n_selected / default_selected / filtered_selected (what the
        preview checklist renders as checked) / domains_configs / unmatched
        (saved entries no combination of this architecture accounts for).
    """
    id_extra = id_extra or {}
    domains_configs = _arch_domains_configs(instances, arch_name)

    selected_domain_values = _extract_domain_values(arch_name, selected_values) if arch_enabled else {}
    domain_tiles = []
    initial_selections = {}
    for domain, configurations in domains_configs.items():
        if arch_enabled:
            domain_selected = selected_domain_values.get(domain, set())
            if "*" in domain_selected:
                # Wildcard ("domain/*" or the bare "arch_name/*" main-domain
                # form): select every configuration in this domain, like
                # ArchitectureHandler.configuration_wildcard() does at run time.
                checklist_values = list(configurations)
            else:
                checklist_values = [cfg for cfg in configurations if cfg in domain_selected]
        else:
            checklist_values = list(configurations)
        if checklist_values:
            initial_selections[domain] = checklist_values
        checklist = dcc.Checklist(
            options=[{"label": cfg, "value": cfg} for cfg in configurations],
            id={"type": "domain-config-checklist", "arch": arch_name, "domain": domain, **id_extra},
            value=checklist_values,
            className="odx-chips",
        )
        domain_tiles.append(
            ui.panel(
                title=[
                    html.Span(domain if domain != hard_settings.main_parameter_domain else "Main parameter domain"),
                    html.Span(f"{len(configurations)}", className="odx-badge"),
                ],
                tools=_select_all_buttons(
                    "domain-config-select-all", {"arch": arch_name, "domain": domain, **id_extra}
                ),
                body=checklist,
            )
        )

    # Virtual parameter domains (command-placeholder variables)
    virtual_panel_title = "Variable"
    virtual_variants, virtual_domain_values, virtual_error = _virtual_variant_tokens(instances, arch_name, mode)
    if virtual_error:
        domain_tiles.append(
            ui.panel(
                title=virtual_panel_title,
                body=html.Div(virtual_error, className="error-message"),
            )
        )
    elif virtual_domain_values:
        for domain, values in virtual_domain_values.items():
            if arch_enabled:
                domain_selected = selected_domain_values.get(domain, set())
                if "*" in domain_selected:
                    checklist_values = list(values)
                else:
                    checklist_values = [value for value in values if value in domain_selected]
            else:
                checklist_values = list(values)
            if checklist_values:
                initial_selections[domain] = checklist_values
            domain_tiles.append(
                ui.panel(
                    title=[
                        html.Span(f"{virtual_panel_title}: {domain}"),
                        html.Span(f"{len(values)}", className="odx-badge"),
                    ],
                    tools=_select_all_buttons(
                        "domain-config-select-all", {"arch": arch_name, "domain": domain, **id_extra}
                    ),
                    body=dcc.Checklist(
                        options=[{"label": value, "value": value} for value in values],
                        id={"type": "domain-config-checklist", "arch": arch_name, "domain": domain, **id_extra},
                        value=checklist_values,
                        className="odx-chips",
                    ),
                )
            )

    # Compute the preview data up-front so the "Default Configuration" tile
    # and the preview stay consistent about whether the default config
    # (the bare "<arch_name>" entry) is selected. n_combos counts the
    # non-default combinations only; the default config is counted apart.
    # Virtual parameter domains behave like any other parameter domain: every
    # variant is combined with every physical combination (and with the bare
    # architecture, which has no physical configuration of its own), exactly
    # like the expansion performed at run time.
    n_physical_combos = count_combinations(domains_configs)
    if virtual_variants:
        n_combos = (n_physical_combos + 1) * len(virtual_variants)
    else:
        n_combos = n_physical_combos
    too_many = n_combos > MAX_PREVIEW_COMBINATIONS
    formatted_combinations = []
    filtered_selected = []
    unmatched = []
    excluded = []
    if not too_many:
        physical_combos = combinations(domains_configs, arch_name)
        # What the architecture says its design space does not hold is not
        # offered: a combination an exclusion rules out is not a run waiting to
        # be checked, it is a design that does not exist (see
        # odatix.workspace.exclusions).
        excluder = ExclusionFilter.of(instances.get(arch_name))
        if not excluder.empty:
            kept = []
            for combo in physical_combos:
                if excluder.keeps("+".join(combo)):
                    kept.append(combo)
                else:
                    excluded.append(" + ".join(combo))
            physical_combos = kept
            n_physical_combos = len(physical_combos)
            n_combos = (n_physical_combos + 1) * len(virtual_variants) if virtual_variants else n_physical_combos
        if virtual_variants:
            non_default_combos = [
                base + tokens
                for base in [[f"{arch_name}"]] + physical_combos
                for tokens in virtual_variants
            ]
        else:
            non_default_combos = physical_combos
        all_combinations = [[f"{arch_name}"]] + non_default_combos
        if len(all_combinations) > MAX_PREVIEW_COMBINATIONS:
            all_combinations = [{comb[0]} for comb in all_combinations]  # Only show default if too many combinations
        formatted_combinations = [{"label": " + ".join(comb), "value": " + ".join(comb)} for comb in all_combinations]
        available_values = [opt.get("value") for opt in formatted_combinations]
        # Expand domain-value wildcards ("domain/*", or the bare "arch/*"
        # main-domain form) into every concrete combo they represent before
        # matching against the available combinations: a raw wildcard entry
        # never matches literally, which used to silently drop it from the
        # preview (and from what gets saved back on the next Save).
        # Virtual domains are wildcard-expandable too ("Arch + width/*").
        wildcard_domains = dict(domains_configs)
        wildcard_domains.update(virtual_domain_values or {})
        expanded_selected = []
        for entry in selected_values or []:
            expanded_selected.extend(_expand_wildcard_selection(entry, wildcard_domains, arch_name))
        filtered_selected = [val for val in expanded_selected if val in available_values]
        unmatched = [val for val in expanded_selected if val not in available_values]
        # Select all combinations for disabled architectures, so that turning
        # one on is a single click. The default configuration is left out when
        # there is anything else to run, the way "<arch>/*" leaves it out: it
        # added a job per frequency nobody asked for. Its commands may also
        # take their values from what is swept, and get none when run bare.
        if not arch_enabled:
            filtered_selected = [" + ".join(comb) for comb in all_combinations]
            unmatched = []
            if non_default_combos:
                filtered_selected = [value for value in filtered_selected if value != arch_name]
        default_selected = arch_name in filtered_selected
        n_selected = len([v for v in filtered_selected if v != arch_name])
    else:
        default_selected = (not arch_enabled) or (arch_name in (selected_values or []))
        # Nothing is enumerated, so nothing can be matched: the saved entries are
        # carried over untouched rather than dropped.
        unmatched = list(selected_values or []) if arch_enabled else []
        n_selected = 0

    # Default configuration tile. Its checkbox is kept in sync with the
    # default "<arch_name>" entry of the preview checklist (both directions),
    # see sync_default_to_preview / sync_preview_to_default.
    domain_tiles.append(
        ui.panel(
            title="Default configuration",
            body=dcc.Checklist(
                options=[{"label": f"{arch_name} (default)", "value": arch_name}],
                id={"type": "default-config-checklist", "arch": arch_name, "domain": "default", **id_extra},
                value=[arch_name] if default_selected else [],
                className="odx-check-list",
            ),
        )
    )

    if too_many:
        preview_tile = ui.panel(
            title=_preview_title(n_combos, default_selected, n_selected),
            title_id={"type": "preview-config-title", "arch": arch_name, **id_extra},
            body=html.Div(
                f"Too many combinations to display (> {MAX_PREVIEW_COMBINATIONS}).",
                className="odx-panel-note",
            ),
        )
    else:
        preview_tile = ui.panel(
            title=_preview_title(n_combos, default_selected, n_selected),
            title_id={"type": "preview-config-title", "arch": arch_name, **id_extra},
            tools=_select_all_buttons("preview-config-select-all", {"arch": arch_name, **id_extra}),
            body=dcc.Checklist(
                options=formatted_combinations,
                id={"type": "preview-config-checklist", "arch": arch_name, **id_extra},
                value=filtered_selected,
                className="odx-check-list",
            ),
            body_className="scroll tall",
        )

    info = {
        "n_combos": n_combos,
        "n_selected": n_selected,
        "default_selected": default_selected,
        "filtered_selected": filtered_selected,
        "domains_configs": domains_configs,
        "unmatched": unmatched,
        "too_many": too_many,
        "virtual_variants": virtual_variants,
        "excluded": excluded,
        "virtual_domains": list(virtual_domain_values or {}),
        "initial_selections": initial_selections,
    }
    return domain_tiles, preview_tile, info


######################################
# Wildcard compaction (writing side)
######################################
#
# _expand_wildcard_selection() reads "Arch/* + domain/value" back into the
# concrete combinations the preview checklist shows. These helpers do the
# inverse: when every configuration of a domain is checked, the domain is
# written as a wildcard rather than as the full list of its configurations, so
# a selection stays valid when a configuration is added to that domain later.

def _entry_tokens(entry: str, arch_name: str):
    """Split a preview entry into its ordered (domain, value) tokens, with the
    main domain normalized like _expand_wildcard_selection() does. Returns None
    for an entry that is not in the expected form, and [] for the bare default
    configuration entry."""
    parts = [p.strip() for p in str(entry).split(" + ") if p.strip()]
    tokens = []
    for index, part in enumerate(parts):
        if "/" not in part:
            if index == 0 and part == arch_name:
                continue
            return None
        domain, value = part.split("/", 1)
        if domain == arch_name:
            domain = hard_settings.main_parameter_domain
        if not domain or value == "":
            return None
        tokens.append((domain, value))
    return tokens


def _format_entry(arch_name: str, tokens) -> str:
    """Inverse of _entry_tokens(): the preview/selector string of a token list."""
    if not tokens:
        return arch_name
    parts = [
        f"{arch_name if domain == hard_settings.main_parameter_domain else domain}/{value}"
        for domain, value in tokens
    ]
    if tokens[0][0] != hard_settings.main_parameter_domain:
        parts = [arch_name] + parts
    return " + ".join(parts)


def _compact_cubes(cubes, order, domain_values):
    """
    Collapse a set of value tuples (all sharing the same domain order) by
    replacing, domain by domain, a group that holds every configuration of that
    domain with a "*" wildcard.
    """
    cubes = list(dict.fromkeys(cubes))
    for index, domain in enumerate(order):
        available = set(domain_values.get(domain) or [])
        if len(available) < 2:
            continue
        groups = {}
        for cube in cubes:
            groups.setdefault(cube[:index] + (None,) + cube[index + 1:], []).append(cube)
        compacted = []
        for key, group in groups.items():
            if {cube[index] for cube in group} == available:
                compacted.append(key[:index] + ("*",) + key[index + 1:])
            else:
                compacted.extend(group)
        cubes = list(dict.fromkeys(compacted))
    return cubes


def _selection_domain_values(instances, arch_name, mode) -> dict:
    """Every value each parameter domain of an architecture can take, virtual
    parameter domains included (the wildcard-expandable domains)."""
    domain_values = dict(_arch_domains_configs(instances, arch_name))
    try:
        _, virtual_domain_values, error = _virtual_variant_tokens(instances, arch_name, mode)
    except Exception:
        return domain_values
    if not error:
        domain_values.update(virtual_domain_values or {})
    return domain_values


def _compact_arch_entries(instances, arch_name, entries, mode) -> list:
    """The selection of one architecture, with fully selected domains written as
    wildcards. Falls back to the entries as given whenever the compacted form
    would not read back into the exact same selection."""
    domain_values = _selection_domain_values(instances, arch_name, mode)
    if not domain_values:
        return list(entries)

    shapes = {}
    compacted = []
    for entry in entries:
        tokens = _entry_tokens(entry, arch_name)
        if not tokens:
            # The bare default configuration entry, or something this syntax
            # does not describe: carried over untouched.
            compacted.append(str(entry))
            continue
        order = tuple(domain for domain, _ in tokens)
        shapes.setdefault(order, []).append(tuple(value for _, value in tokens))

    for order, cubes in shapes.items():
        for cube in _compact_cubes(cubes, order, domain_values):
            compacted.append(_format_entry(arch_name, list(zip(order, cube))))

    expanded = []
    for entry in compacted:
        expanded.extend(_expand_wildcard_selection(entry, domain_values, arch_name))
    if len(expanded) != len(set(expanded)) or set(expanded) != {str(entry) for entry in entries}:
        return list(entries)
    return compacted


def compact_selection(instances, entries, mode) -> list:
    """
    Rewrite a flat selection ("Arch + domain/value + ...") using domain
    wildcards wherever every configuration of a domain is selected, e.g.
    "Design/* + domain1/config1 + domain2/*". The result reads back (through
    _expand_wildcard_selection) into exactly the same combinations.
    """
    compacted = []
    for arch_name, arch_entries in _group_arch_selections(entries).items():
        compacted.extend(_compact_arch_entries(instances, arch_name, arch_entries, mode))
    return list(dict.fromkeys(compacted))

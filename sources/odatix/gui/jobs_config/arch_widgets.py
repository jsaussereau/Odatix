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

from dash import dcc, html

import odatix.components.workspace as workspace
import odatix.gui.ui_components as ui
import odatix.lib.hard_settings as hard_settings
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

def _virtual_variant_tokens(base_path, name, mode):
    """
    Resolve the virtual parameter domains of a workflow or an architecture
    (command-placeholder variables defined under
    "generate_configurations_settings.variables" in its _settings.yml), by
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
    settings = workspace.load_workflow_settings(base_path, name)
    virtual_domain_names = virtual_param_domain.get_virtual_domain_names(settings)
    if not virtual_domain_names:
        return [], {}, None

    if mode != "workflow":
        # Only "generate_command" consumes these variables as a parameter domain.
        generate_command = settings.get("generate_command", "") if settings.get("generate_rtl", False) else ""
        if not (virtual_param_domain.referenced_variable_names(generate_command) & virtual_domain_names):
            return [], {}, None

    settings_file = workspace.get_workflow_settings_path(base_path, name)
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
    domain_values = {domain: sorted(values) for domain, values in domain_values.items()}
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
    represents (the exact format produced by workspace.generate_config_combinations).

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


def _arch_domains_configs(arch_path, arch_name) -> dict:
    """The configurations of every parameter domain of an architecture that
    actually uses parameters, keyed by domain (main domain included)."""
    domains_configs = {}
    domains = [hard_settings.main_parameter_domain] + workspace.get_param_domains(arch_path, arch_name)
    for domain in domains:
        if not workspace.check_parameter_domain_use_parameters(arch_path, arch_name, domain):
            continue
        configurations = workspace.get_config_files(arch_path, arch_name, domain)
        if not configurations:
            continue
        # Remove .txt extension
        domains_configs[domain] = [cfg[:-4] if cfg.endswith(".txt") else cfg for cfg in configurations]
    return domains_configs


def _arch_config_widgets(arch_path, arch_name, selected_values, arch_enabled, mode, id_extra=None):
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
    domains_configs = _arch_domains_configs(arch_path, arch_name)

    selected_domain_values = _extract_domain_values(arch_name, selected_values) if arch_enabled else {}
    domain_tiles = []
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
    virtual_panel_title = "Workflow variables" if mode == "workflow" else "Variables"
    virtual_variants, virtual_domain_values, virtual_error = _virtual_variant_tokens(arch_path, arch_name, mode)
    if virtual_error:
        domain_tiles.append(
            ui.panel(
                title=virtual_panel_title,
                body=html.Div(virtual_error, className="error-message"),
            )
        )
    elif virtual_domain_values:
        domain_tiles.append(
            ui.panel(
                title=virtual_panel_title,
                body=[
                    html.Div(
                        [
                            html.Span(f"{domain}:", className="jobs-var-name"),
                            html.Span(", ".join(values)),
                        ],
                        className="jobs-var-line",
                    )
                    for domain, values in virtual_domain_values.items()
                ],
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
    n_physical_combos = workspace.count_combinations(domains_configs)
    if virtual_variants:
        n_combos = (n_physical_combos + 1) * len(virtual_variants)
    else:
        n_combos = n_physical_combos
    too_many = n_combos > MAX_PREVIEW_COMBINATIONS
    formatted_combinations = []
    filtered_selected = []
    unmatched = []
    if not too_many:
        physical_combos = workspace.generate_config_combinations(domains_configs, arch_name)
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
        # Select all combinations for disabled architectures
        if not arch_enabled:
            filtered_selected = [" + ".join(comb) for comb in all_combinations]
            unmatched = []
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
    }
    return domain_tiles, preview_tile, info

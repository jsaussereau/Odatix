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

import copy as copy_module
import fnmatch
import json

import dash
from dash import html, dcc, Input, Output, State, ctx

from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url, get_workspace
from odatix.gui.css_helper import Style
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.gui.builtin_variables as builtin_variables
import odatix.lib.hard_settings as hard_settings
import odatix.workspace.sim_architectures as sim_architectures

page_path = "/sim_editor"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Simulation Editor",
    name="Simulation Editor",
    order=7,
)


######################################
# Helpers
######################################

def _parse_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        val = value.strip().lower()
        if val in ["yes", "true", "1"]:
            return True
        if val in ["no", "false", "0"]:
            return False
    return default

def parse_invariant_domains_text(text):
    """
    Parse the invariant domains field, written the same way parameter domains are
    written everywhere else: "MEM/1024I_1024D, Voltage" -- a domain alone lets
    Odatix pick which value to run, a "domain/value" pins the one to run.
    """
    domains = {}
    for item in str(text or "").split(","):
        item = item.strip()
        if item == "":
            continue
        if "/" in item:
            domain, value = item.split("/", 1)
            domain = domain.strip()
            if domain != "":
                domains[domain] = value.strip() or None
        else:
            domains[item] = None
    return domains


def format_invariant_domains(domains):
    """Render an invariant domains mapping back into the editable text form."""
    if not isinstance(domains, dict):
        return ""
    return ", ".join(
        domain if value in (None, "") else str(domain) + "/" + str(value)
        for domain, value in sorted(domains.items())
    )


PARAM_DOMAIN_TEXT_KEYS = (
    "param_target_file", "start_delimiter", "stop_delimiter", "param_file", "param_dir",
)

# The text fields of a parameter domain row, by the suffix their component id
# carries.
FIELD_KEYS = {
    "target-file": "param_target_file",
    "start-delimiter": "start_delimiter",
    "stop-delimiter": "stop_delimiter",
    "param-file": "param_file",
    "param-dir": "param_dir",
}

# What a parameter domain row says about being substituted at all. "Inherit"
# says nothing, which leaves the architecture's own setting for the domain
# untouched.
DOMAIN_MODE_OPTIONS = [
    {"label": "Inherit", "value": "inherit"},
    {"label": "Replace", "value": "yes"},
    {"label": "No replacement", "value": "no"},
]

# Whether the substitution the simulation describes for a domain is done instead
# of the architecture's own, or as well as it.
DOMAIN_COMBINE_OPTIONS = [
    {"label": "Instead of the architecture's", "value": sim_architectures.COMBINE_REPLACE},
    {"label": "As well as the architecture's", "value": sim_architectures.COMBINE_BOTH},
]


def normalize_param_domain(overrides):
    """
    Reduce one entry of "param_domains" to the keys this page edits.

    Only the keys actually written are kept: an absent key means "inherit from
    the architecture's own settings for that domain", which is not the same as
    an empty one.
    """
    if not isinstance(overrides, dict):
        return {}
    normalized = {}
    if "use_parameters" in overrides:
        normalized["use_parameters"] = _parse_bool(overrides["use_parameters"], True)
    if sim_architectures.combine_mode(overrides) == sim_architectures.COMBINE_BOTH:
        normalized["combine"] = sim_architectures.COMBINE_BOTH
    for key in PARAM_DOMAIN_TEXT_KEYS:
        if key in overrides and str(overrides[key] or "") != "":
            normalized[key] = str(overrides[key])
    return normalized


def normalize_architectures(value):
    """
    Reduce the "architectures" block to the shape this page compares and writes:
    a list of entries, in the order they are written, each holding its name and
    what the simulation changes for it.

    Everything an entry holds is kept, not only what this page edits: a metrics
    file declared for one architecture must survive being edited here.
    """
    if isinstance(value, list) and all(
        isinstance(entry, dict) and "name" in entry for entry in value
    ):
        # Already the shape this page works with, coming back from its own store
        # or from what it just built out of the cards.
        value = architectures_to_yaml(value)

    messages = []
    normalized = []
    for entry in sim_architectures.parse(value, messages=messages):
        settings = dict(entry.settings)
        param_domains = settings.pop("param_domains", None)
        if isinstance(param_domains, dict):
            param_domains = {
                str(domain): normalize_param_domain(overrides)
                for domain, overrides in param_domains.items()
                if str(domain).strip() != ""
            }
        else:
            param_domains = {}
        normalized.append(dict(settings, name=entry.name, param_domains=param_domains))
    return normalized


def architectures_to_yaml(architectures):
    """Turn normalized entries back into what the settings file holds."""
    return sim_architectures.to_yaml([
        sim_architectures.ArchitectureEntry(
            entry.get("name", ""),
            {key: value for key, value in entry.items() if key != "name"},
        )
        for entry in architectures or []
        if str(entry.get("name", "")).strip() != ""
    ])


# What an architecture card holds besides the settings the section edits: any
# other key the entry carried is kept as it is, so a settings file is never
# truncated by a version of the page that does not know a key yet.
ARCH_CARD_KEYS = ("param_domains", "metrics_file")


def arch_cards_from_settings(architectures):
    """
    Turn the normalized "architectures" entries into what the cards show: one
    card per architecture, holding its parameter domains in the order they are
    written and whatever else the entry carries.
    """
    cards = []
    for entry in architectures or []:
        if not isinstance(entry, dict):
            continue
        domains = [
            dict(
                normalize_param_domain(overrides),
                name=str(domain),
                mode=(
                    "inherit" if not isinstance(overrides, dict) or "use_parameters" not in overrides
                    else ("yes" if _parse_bool(overrides["use_parameters"], True) else "no")
                ),
                combine=sim_architectures.combine_mode(overrides),
            )
            for domain, overrides in (entry.get("param_domains") or {}).items()
        ]
        cards.append({
            "name": str(entry.get("name", "")),
            "metrics_file": str(entry.get("metrics_file", "") or ""),
            "extra": {
                key: value for key, value in entry.items()
                if key != "name" and key not in ARCH_CARD_KEYS
            },
            "domains": domains,
            # A loaded architecture starts folded: the page opens on the list of
            # what the simulation runs on, and a card is unfolded to work on it.
            "collapsed": True,
        })
    return cards


def arch_cards_to_settings(cards):
    """
    Turn what the cards hold back into "architectures" entries.

    An architecture with nothing under it stays an architecture the simulation
    runs on, and a domain with an empty name is one being filled in: neither is
    written out as an override.
    """
    entries = []
    for card in cards or []:
        name = str(card.get("name", "") or "").strip()
        if name == "":
            continue

        domains = {}
        for domain in card.get("domains") or []:
            domain_name = str(domain.get("name", "") or "").strip()
            if domain_name == "":
                continue
            overrides = {}
            if domain.get("mode") in ("yes", "no"):
                overrides["use_parameters"] = domain.get("mode") == "yes"
            # Replacing is the default, and stays unwritten.
            if domain.get("combine") == sim_architectures.COMBINE_BOTH:
                overrides["combine"] = sim_architectures.COMBINE_BOTH
            for key in PARAM_DOMAIN_TEXT_KEYS:
                value = str(domain.get(key, "") or "").strip()
                if value != "":
                    overrides[key] = value
            domains[domain_name] = overrides

        settings = {"name": name}
        if domains:
            settings["param_domains"] = domains
        metrics_file = str(card.get("metrics_file", "") or "").strip()
        if metrics_file != "":
            settings["metrics_file"] = metrics_file
        settings.update(card.get("extra") or {})
        entries.append(settings)
    return entries


legacy_parameter_keys = (
    "use_parameters", "param_target_file", "start_delimiter", "stop_delimiter",
    "override_parameters", "override_param_file", "override_param_target_file",
    "override_start_delimiter", "override_stop_delimiter",
)


def uses_legacy_parameters(settings):
    """
    Whether a simulation still relies on the pre-"param_domains" keys. They are
    only shown when it does, so a simulation that has moved on is not offered a
    deprecated way of doing the same thing.
    """
    if not isinstance(settings, dict):
        return False
    return any(key in settings for key in legacy_parameter_keys)


def settings_as_written(settings):
    """
    The settings as a plain dict, minus the deprecated keys the settings file
    does not actually hold: ``to_dict`` fills every declared key with its
    default, which would make every simulation look like a legacy one.
    """
    data = settings.to_dict()
    in_file = settings.file_keys()
    for key in legacy_parameter_keys:
        if key not in in_file:
            data.pop(key, None)
    return data


def normalize_simulation_settings(settings):
    """
    Reduce a simulation settings file to the keys this page edits, with stable
    types, so the current state and the saved one can be compared field by field
    (that comparison is what drives the "unsaved changes" state of Save).
    """
    if not isinstance(settings, dict):
        settings = {}

    progress = settings.get("progress", {})
    if not isinstance(progress, dict):
        progress = {}

    tasks = settings.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    invariant_domains = settings.get("invariant_domains")
    if isinstance(invariant_domains, str):
        invariant_domains = parse_invariant_domains_text(invariant_domains)
    elif isinstance(invariant_domains, list):
        invariant_domains = {str(domain): None for domain in invariant_domains if domain is not None}
    elif isinstance(invariant_domains, dict):
        invariant_domains = {
            str(domain): (None if value in (None, "") else str(value))
            for domain, value in invariant_domains.items()
        }
    else:
        invariant_domains = {}

    normalized = {
        "invariant_domains": invariant_domains,
        "architectures": normalize_architectures(settings.get("architectures")),
        "progress": {
            "file": str(progress.get("file", "") or ""),
            "regex": str(progress.get("regex", "") or ""),
        },
        "tasks": tasks,
    }

    # The deprecated keys are only carried when the simulation actually sets them, so that
    # editing a simulation that has moved on to "param_domains" does not write them back.
    legacy = {
        "use_parameters": _parse_bool(settings.get("use_parameters", True), True),
        "param_target_file": str(settings.get("param_target_file", "") or ""),
        "start_delimiter": str(settings.get("start_delimiter", "") or ""),
        "stop_delimiter": str(settings.get("stop_delimiter", "") or ""),
        "override_parameters": _parse_bool(settings.get("override_parameters", False), False),
        "override_param_file": str(settings.get("override_param_file", "") or ""),
        "override_param_target_file": str(settings.get("override_param_target_file", "") or ""),
        "override_start_delimiter": str(settings.get("override_start_delimiter", "") or ""),
        "override_stop_delimiter": str(settings.get("override_stop_delimiter", "") or ""),
    }
    if uses_legacy_parameters(settings):
        normalized.update(legacy)

    return normalized

def build_tasks_list(names, dependencies_vals, commands_vals, path_vals, platforms_vals):
    """
    Build the simulation task list from the task card field values.

    Unlike a workflow, a simulation may legitimately define no task at all: it
    then falls back to the historical "make sim" command, so an empty list is
    kept empty instead of being seeded with a "main" task.
    """
    tasks = []
    nb = len(names) if isinstance(names, list) else 0
    for idx in range(nb):
        name = str(names[idx]).strip() if idx < len(names) and names[idx] is not None else ""
        if name == "":
            continue

        dependencies_raw = dependencies_vals[idx] if idx < len(dependencies_vals) else ""
        dependencies = [
            x.strip() for x in str(dependencies_raw).split(",")
            if x is not None and str(x).strip() != ""
        ]

        commands_raw = commands_vals[idx] if idx < len(commands_vals) else ""
        commands = [
            line.strip() for line in str(commands_raw).splitlines()
            if line is not None and str(line).strip() != ""
        ]

        task = {"name": name, "commands": commands}
        if len(dependencies) > 0:
            task["dependencies"] = dependencies

        task_path = str(path_vals[idx]).strip() if idx < len(path_vals) and path_vals[idx] is not None else ""
        if task_path != "":
            task["path"] = task_path

        platforms_raw = platforms_vals[idx] if idx < len(platforms_vals) else ""
        platforms = [
            x.strip() for x in str(platforms_raw).split(",")
            if x is not None and str(x).strip() != ""
        ]
        if len(platforms) == 1:
            task["platforms"] = platforms[0]
        elif len(platforms) > 1:
            task["platforms"] = platforms

        tasks.append(task)

    return tasks


######################################
# UI Components
######################################

def simulation_title(sim_name):
    title_buttons = html.Div(
        children=[
            ui.icon_button(
                id="button-open-sim-metric-editor",
                icon=icon("metrics", className="icon blue"),
                text="Edit Metrics",
                tooltip="Open the Exported Metrics Editor for this simulation",
                tooltip_options="bottom delay",
                color="default",
                link=f"/metric_editor?simulation={sim_name}",
                multiline=False,
                width="135px",
            ),
            ui.save_button(
                id={"page": page_path, "action": "save-all"},
                tooltip="Save all changes",
                disabled=True,
            ),
        ],
        className="inline-flex-buttons",
    )

    return html.Div(
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                dcc.Input(
                                    value=f"{sim_name}",
                                    type="text",
                                    id="sim-title",
                                    placeholder="Simulation Name...",
                                    className="title-input",
                                    style={"width": "100%", "transform": "translate(-5px, 5px)"},
                                )
                            ],
                            id="sim-title-container",
                        ),
                        html.Div([title_buttons]),
                    ],
                    className="title-tile-flex",
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "padding": "0px",
                        "justifyContent": "space-between",
                    },
                ),
                ui.back_button(link="/architectures"),
            ],
            className="tile title",
            style={"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "0px", "marginBottom": "10px"},
    )

def sim_form_field(label, id, value="", tooltip="", placeholder="", tooltip_options="secondary"):
    return html.Div(
        children=[
            html.Label(label),
            ui.tooltip_icon(tooltip, tooltip_options),
            dcc.Input(id=id, value=value, type="text", placeholder=placeholder, style={"width": "100%"}),
        ],
        style={"marginBottom": "12px"},
    )

def sim_form(settings):
    defval = lambda k, v=None: settings.get(k, v)

    progress = defval("progress", {}) or {}
    use_parameters = True if defval("use_parameters", True) else False
    override_parameters = True if defval("override_parameters", False) else False

    legacy_style = {} if uses_legacy_parameters(settings) else Style.hidden

    return html.Div(
        children=[
            html.Div(
                [
                    html.H3("Parameters Replacement (deprecated)"),
                    html.Div(
                        "Superseded by the Architectures section below, which does the same per "
                        "architecture and per parameter domain instead of once for all of them. "
                        "Clear these fields once the architectures cover them.",
                        className="odx-panel-note",
                        style={"marginBottom": "12px"},
                    ),
                    html.Div(
                        children=[
                            dcc.Checklist(
                                options=[{"label": "Enable parameter replacement", "value": True}],
                                value=[True] if use_parameters else [],
                                id="sim-use-parameters",
                                className="checklist-switch",
                                style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                            ),
                            ui.tooltip_icon(
                                "Replace values in a testbench file using the configuration files of the "
                                "architecture the simulation runs on."
                            ),
                        ],
                        style={"marginBottom": "12px"},
                    ),
                    html.Div(
                        children=[
                            sim_form_field(
                                label="Parameter Target File",
                                id="sim-param-target-file",
                                value=defval("param_target_file", ""),
                                placeholder="tb/tb_counter.vhdl",
                                tooltip="File of the simulation sources where replacements are applied.",
                            ),
                            sim_form_field(
                                label="Start Delimiter",
                                id="sim-start-delimiter",
                                value=defval("start_delimiter", ""),
                                tooltip="Start marker for replacement. Escape sequences such as \\n are supported.",
                            ),
                            sim_form_field(
                                label="Stop Delimiter",
                                id="sim-stop-delimiter",
                                value=defval("stop_delimiter", ""),
                                tooltip="Stop marker for replacement. Escape sequences such as \\n are supported.",
                            ),
                        ],
                        id="sim-params-config-fields",
                        className="animated-section" if use_parameters else "animated-section hide",
                        style={"overflow": "visible"},
                    ),
                ],
                className="tile config",
                style=legacy_style,
            ),
            html.Div(
                [
                    html.H3("Parameters Override (deprecated)"),
                    html.Div(
                        "Superseded by the Architectures section below: under an architecture, a domain "
                        "name matching none of its own declares a replacement of the simulation's own, "
                        "which is what this did.",
                        className="odx-panel-note",
                        style={"marginBottom": "12px"},
                    ),
                    html.Div(
                        children=[
                            dcc.Checklist(
                                options=[{"label": "Enable parameter override", "value": True}],
                                value=[True] if override_parameters else [],
                                id="sim-override-parameters",
                                className="checklist-switch",
                                style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                            ),
                            ui.tooltip_icon(
                                "Apply a second replacement pass, from a file of the simulation itself, on top "
                                "of the architecture configuration (e.g. to force testbench-only parameters)."
                            ),
                        ],
                        style={"marginBottom": "12px"},
                    ),
                    html.Div(
                        children=[
                            sim_form_field(
                                label="Override Parameter File",
                                id="sim-override-param-file",
                                value=defval("override_param_file", ""),
                                tooltip="File of the simulation holding the overriding values.",
                            ),
                            sim_form_field(
                                label="Override Parameter Target File",
                                id="sim-override-param-target-file",
                                value=defval("override_param_target_file", ""),
                                tooltip="File where the overriding values are written.",
                            ),
                            sim_form_field(
                                label="Override Start Delimiter",
                                id="sim-override-start-delimiter",
                                value=defval("override_start_delimiter", ""),
                                tooltip="Start marker for the override replacement. Escape sequences such as \\n are supported.",
                            ),
                            sim_form_field(
                                label="Override Stop Delimiter",
                                id="sim-override-stop-delimiter",
                                value=defval("override_stop_delimiter", ""),
                                tooltip="Stop marker for the override replacement. Escape sequences such as \\n are supported.",
                            ),
                        ],
                        id="sim-override-config-fields",
                        className="animated-section" if override_parameters else "animated-section hide",
                        style={"overflow": "visible"},
                    ),
                ],
                className="tile config",
                style=legacy_style,
            ),
            html.Div(
                [
                    html.H3("Progress Tracking"),
                    sim_form_field(
                        label="Progress File",
                        id="sim-progress-file",
                        value=progress.get("file", ""),
                        placeholder=hard_settings.sim_progress_file,
                        tooltip="Path of the progress file written by the simulation.",
                    ),
                    sim_form_field(
                        label="Progress Regex",
                        id="sim-progress-regex",
                        value=progress.get("regex", ""),
                        placeholder=hard_settings.sim_status_pattern.pattern,
                        tooltip="Regex containing one capture group for the completion percentage.",
                    ),
                ],
                className="tile config",
            ),
            html.Div(
                [
                    html.H3("Invariant Parameter Domains"),
                    sim_form_field(
                        label="Domains",
                        id="sim-invariant-domains",
                        value=format_invariant_domains(defval("invariant_domains", {})),
                        tooltip=(
                            "Parameter domains this simulation's result does not depend on. Only one value "
                            "of each is run instead of all of them, and the result carries no such dimension, "
                            "so it applies to every value of it when a synthesis result borrows a metric from "
                            'it. Write "domain" to let Odatix pick the value to run, or "domain/value" to '
                            "choose it."
                        ),
                    ),
                ],
                className="tile config",
            ),
        ],
        className="tiles-container config",
        style={"marginTop": "-10px", "marginBottom": "20px"},
    )

def architecture_options(odatix_settings=None, current=""):
    """
    Options of the architecture dropdown of an architecture card: every
    architecture of the workspace, with "All architectures" ("*") on top.

    A value the file already held (a wildcard, or an architecture that no longer
    exists) is kept as an option of its own so opening the page does not silently
    drop it.
    """
    options = [{"label": "All architectures", "value": "*"}]
    options.extend(
        {"label": name, "value": name}
        for name in workspace_architecture_names(odatix_settings)
    )
    return with_architecture_option(options, current)


def workspace_architecture_names(odatix_settings=None):
    """The architectures of the workspace, sorted, empty when there is no reading them."""
    try:
        return sorted(get_workspace(odatix_settings).architectures.names())
    except Exception:
        return []


def with_architecture_option(options, arch):
    """Same options, plus `arch` itself when the workspace does not list it."""
    if not arch or arch in [option["value"] for option in options]:
        return options
    return options[:1] + [{"label": arch, "value": arch}] + options[1:]


def architecture_domain_names(arch, odatix_settings=None):
    """
    The parameter domains of one architecture of the workspace, the main one
    first. A wildcard entry applies to several architectures at once, so it gets
    the domains of all of them.
    """
    try:
        architectures = get_workspace(odatix_settings).architectures
        if arch and "*" not in arch and "?" not in arch:
            return architectures[arch].domains.names()
        names = []
        for name in sorted(architectures.names()):
            if arch and not fnmatch.fnmatch(name, arch):
                continue
            for domain in architectures[name].domains.names():
                if domain not in names:
                    names.append(domain)
        return names
    except Exception:
        return []


def domain_options(arch, odatix_settings=None):
    """
    Options of the domain dropdown of a parameter domain row: the domains the
    architecture of the card defines, named the way the config editor names them.
    """
    return [
        {
            "label": "Main parameter domain" if name == hard_settings.main_parameter_domain else name,
            "value": name,
        }
        for name in architecture_domain_names(arch, odatix_settings)
    ]


def with_domain_option(options, domain):
    """
    Same options, plus `domain` itself when the architecture does not declare it:
    a domain it no longer declares, or one the simulation substitutes on its own,
    must not silently disappear when the page opens.
    """
    if not domain or domain in [option["value"] for option in options]:
        return options
    return list(options) + [{"label": domain, "value": domain}]


def _uid(prefix, index):
    return "{0}{1:03d}".format(prefix, index)


def domain_row(arch_uid, domain_uid, domain, options=None):
    """
    One parameter domain of one architecture: what the simulation does with the
    values that domain sets, instead of what the architecture says.

    What a row leaves empty is inherited from the architecture's own settings for
    that domain, which is not the same as clearing it. A row whose name matches
    no domain of the architecture declares a replacement of the simulation's own,
    which is what the parameter file is for.
    """
    name = str(domain.get("name", "") or "")

    def field(label, key, placeholder="", tooltip="", style=None):
        return ui.form_field(
            label,
            {"type": "sim-domain-" + key, "arch": arch_uid, "domain": domain_uid},
            value=str(domain.get(FIELD_KEYS[key], "") or ""),
            placeholder=placeholder,
            tooltip=tooltip,
            style=style
        )

    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Div(
                        dcc.Dropdown(
                            id={"type": "sim-domain-name", "arch": arch_uid, "domain": domain_uid},
                            options=with_domain_option(options or [], name),
                            value=name or None,
                            placeholder="Domain...",
                            clearable=False,
                        ),
                        className="odx-domain-name",
                        style={"marginRight": "8px"}
                    ),
                    dcc.RadioItems(
                        id={"type": "sim-domain-mode", "arch": arch_uid, "domain": domain_uid},
                        options=DOMAIN_MODE_OPTIONS,
                        value=domain.get("mode", "inherit"),
                        className="odx-chips",
                    ),
                    ui.duplicate_button(
                        id={"type": "sim-domain-duplicate", "arch": arch_uid, "domain": domain_uid},
                        tooltip="Duplicate this parameter domain",
                    ),
                    ui.delete_button(
                        id={"type": "sim-domain-delete", "arch": arch_uid, "domain": domain_uid},
                        tooltip="Delete this parameter domain",
                    ),
                ],
                className="odx-domain-head",
            ),
            html.Div(
                children=[
                    field(
                        "Target file", "target-file", placeholder="tb/tb_cordic.sv",
                        tooltip="File of the simulation sources the values are written into, "
                                "instead of the one the architecture writes them into.",
                    ),
                    ui.form_dropdown(
                        "Rule application",
                        {"type": "sim-domain-combine", "arch": arch_uid, "domain": domain_uid},
                        options=DOMAIN_COMBINE_OPTIONS,
                        value=domain.get("combine") or sim_architectures.COMBINE_REPLACE,
                        clearable=False,
                        tooltip="Whether the substitution described here replaces the one the "
                                "architecture does for this domain, or is done as well as it, so "
                                "the domain is written in two places.",
                    ),
                ],
                className="odx-field-row",
            ),
            html.Div(
                children=[
                    html.Div(
                        children=[
                            field(
                                "Parameter directory", "param-dir", placeholder="sim_params/width",
                                tooltip="Directory of the simulation holding one configuration per value of "
                                        "the domain, written as \".txt\" files or described by rules in its "
                                        "own \"_settings.yml\", like the configurations of an architecture.",
                                style={"width": "100%"},
                            ),
                            ui.icon_button(
                                id={"type": "sim-domain-configs", "arch": arch_uid, "domain": domain_uid},
                                icon=icon("edit", className="icon"),
                                color="default",
                                tooltip="Edit the configurations of this directory",
                                tooltip_options="bottom auto delay",
                                link="",
                                style={"marginBottom": "0"},
                            ),
                        ],
                        # The button opens what the field names, so it sits with
                        # it rather than in a row of its own.
                        style={"display": "flex", "alignItems": "flex-end", "gap": "8px", "flex": "1"},
                    ),
                    field(
                        "Default parameter file", "param-file", placeholder="sim_params.txt",
                        tooltip="File of the simulation holding the values, whichever configuration "
                                "of the domain runs. Given along a parameter directory, it is the "
                                "default the configurations that directory does not describe fall "
                                "back to. Required for a domain the architecture does not define, "
                                "unless a parameter directory is given.",
                        style={"width": "100%"},
                    ),
                ],
                className="odx-field-row",
            ),
            html.Div(
                children=[
                    field(
                        "Start delimiter", "start-delimiter",
                        tooltip="Start marker for replacement. Escape sequences such as \\n are supported.",
                    ),
                    field(
                        "Stop delimiter", "stop-delimiter",
                        tooltip="Stop marker for replacement. Escape sequences such as \\n are supported.",
                    ),
                ],
                className="odx-field-row",
            ),
        ],
        className="odx-domain-row",
    )


def arch_card(arch_uid, card, arch_options=None, odatix_settings=None):
    """
    One architecture the simulation runs on, and what it changes for it: the
    parameter domains it substitutes differently, and the metrics file it exports
    through.

    A card can be folded down to its head, so a testbench running on a handful of
    designs stays readable. Whether it is folded is held in the page like the
    other states the server owns, so it survives the re-render a structural
    change triggers.
    """
    name = str(card.get("name", "") or "")
    domains = card.get("domains") or []
    collapsed = bool(card.get("collapsed"))
    options = arch_options if arch_options is not None else architecture_options(current=name)
    # The domains to pick from are the architecture's own, so they follow the
    # dropdown above them.
    own_domains = domain_options(name, odatix_settings) if domains else []

    head = html.Div(
        children=[
            ui.icon_button(
                id={"type": "sim-arch-toggle", "arch": arch_uid},
                icon=icon(
                    "more",
                    className="icon normal rotate" + ("" if collapsed else " rotated"),
                    id={"type": "sim-arch-toggle-icon", "arch": arch_uid},
                ),
                color="default",
                tooltip="Fold or unfold this architecture",
                tooltip_options="bottom auto delay",
            ),
            dcc.Input(
                id={"type": "sim-arch-collapsed", "arch": arch_uid},
                value="1" if collapsed else "",
                type="hidden",
            ),
            # Whatever else the entry carried, kept as it is so a key this page
            # does not edit survives being saved from here.
            dcc.Input(
                id={"type": "sim-arch-extra", "arch": arch_uid},
                value=json.dumps(card.get("extra") or {}),
                type="hidden",
            ),
            html.Div(
                dcc.Dropdown(
                    id={"type": "sim-arch-name", "arch": arch_uid},
                    options=with_architecture_option(options, name),
                    value=name or None,
                    placeholder="Architecture...",
                    clearable=False,
                ),
                className="odx-arch-name",
            ),
            ui.badge(
                "no override" if not domains
                else ("1 domain" if len(domains) == 1 else "{0} domains".format(len(domains))),
                className="odx-arch-badge",
            ),
            html.Div(style={"flex": "1"}),
            ui.duplicate_button(
                id={"type": "sim-arch-duplicate", "arch": arch_uid},
                tooltip="Duplicate this architecture",
            ),
            ui.delete_button(
                id={"type": "sim-arch-delete", "arch": arch_uid},
                tooltip="Remove this architecture from the ones the simulation runs on",
            ),
        ],
        className="odx-card-head odx-arch-head",
    )

    body = html.Div(
        children=[
            ui.form_field(
                "Metrics file",
                {"type": "sim-arch-metrics-file", "arch": arch_uid},
                value=str(card.get("metrics_file", "") or ""),
                placeholder="_metrics.yml",
                tooltip="Metrics definition file used when exporting this simulation's results "
                        "for this architecture, instead of the simulation's own.",
            ),
            ui.caption(
                "Parameter domains",
                tooltip="How this simulation substitutes the values of the architecture's parameter "
                        "domains. A domain that is not listed is substituted the way the architecture "
                        "declares it.",
            ),
            html.Div(
                children=[
                    domain_row(arch_uid, _uid("d", index), domain, options=own_domains)
                    for index, domain in enumerate(domains)
                ] or [
                    html.Div(
                        "Every parameter domain of this architecture is substituted the way the "
                        "architecture declares it.",
                        className="odx-domain-empty",
                    )
                ],
                className="odx-domain-rows",
            ),
            html.Button(
                "+ Add parameter domain rules",
                id={"type": "sim-domain-new", "arch": arch_uid},
                n_clicks=0,
                className="odx-jobstep-add",
            ),
        ],
        id={"type": "sim-arch-body", "arch": arch_uid},
        className="animated-section" + (" hide" if collapsed else ""),
    )

    return html.Div(
        children=[head, body],
        id={"type": "sim-arch-card", "arch": arch_uid},
        className="tile config" + (" collapsed" if collapsed else ""),
    )


def arch_no_entry_note():
    """
    Shown instead of architecture cards when the simulation lists none. Listing
    them is an indication, not a restriction: running a simulation on an
    architecture it does not list works, and only warns.
    """
    return html.Div(
        [
            html.Div("No architecture listed", style={"fontWeight": "bold", "marginBottom": "6px"}),
            html.Div(
                "This simulation says nothing about the designs it is written for. Add one to say "
                "what it runs on, to substitute one of its parameter domains differently, or to "
                "export its results through a metrics file of its own.",
                className="odx-panel-note",
            ),
        ],
        className="odx-panel padded odx-empty",
    )


def arch_cards(cards, odatix_settings=None):
    """The whole Architectures section: one card per entry, plus the "add" card."""
    options = architecture_options(odatix_settings)
    children = [
        arch_card(_uid("a", index), card, arch_options=options, odatix_settings=odatix_settings)
        for index, card in enumerate(cards or [])
    ]
    if not children:
        children.append(arch_no_entry_note())
    children.append(ui.add_card(id="sim-arch-new", text="Add an architecture", className="horizontal tile config add hover"))
    return children


def new_arch_card(used, available):
    """
    An architecture the simulation runs on with nothing to change yet, folded:
    listing an architecture is most of what an entry is for, and a card that has
    nothing under it has nothing to show. It starts on the first architecture of
    the workspace the simulation does not already list, and falls back to every
    architecture at once when it already lists them all.
    """
    return {
        "name": next((name for name in available or [] if name not in (used or [])), "*"),
        "metrics_file": "",
        "extra": {},
        "domains": [],
        "collapsed": True,
    }


def new_domain():
    """A parameter domain override that changes nothing yet."""
    return {"name": "", "mode": "inherit", "combine": sim_architectures.COMBINE_REPLACE,
            "param_target_file": "", "start_delimiter": "", "stop_delimiter": "",
            "param_file": "", "param_dir": ""}


def sim_task_card(name="main", dependencies_value="", commands_value="", path_value="", platforms_value=""):
    is_main = str(name).strip() == "main"
    return html.Div([
        html.Div(
            children=[
                dcc.Input(
                    value=name,
                    type="text",
                    id={"type": "sim-task-field-name", "name": name},
                    className="title-input",
                    disabled=is_main,
                    style={
                        "width": "100%",
                        "marginLeft": "5px",
                        "marginRight": "5px",
                        "marginTop": "-5px",
                        "marginBottom": "2px",
                        "fontWeight": "bold",
                        "fontSize": "1.1em",
                        "height": "10px",
                        "textAlign": "center",
                    },
                ),
                html.Label("Dependencies", style={"fontWeight": "bold", "fontSize": "1em"}),
                dcc.Input(
                    value=dependencies_value,
                    type="text",
                    placeholder="e.g., task_a, task_b",
                    id={"type": "sim-task-field-dependencies", "name": name},
                    className="value-input",
                    style={"width": "100%", "marginBottom": "8px"},
                ),
                html.Label("Commands (one per line)", style={"fontWeight": "bold", "fontSize": "1em"}),
                dcc.Textarea(
                    value=commands_value,
                    id={"type": "sim-task-field-commands", "name": name},
                    className="auto-resize-textarea odatix-command-field",
                    style={
                        "width": "100%",
                        "minHeight": "110px",
                        "resize": "vertical",
                        "fontFamily": "monospace",
                        "fontWeight": "500",
                        "marginBottom": "8px",
                        "boxSizing": "border-box",
                    },
                ),
                html.Div(
                    children=[
                        html.Label("Path (optional)", style={"fontWeight": "bold", "fontSize": "1em"}),
                        dcc.Input(
                            value=path_value,
                            type="text",
                            id={"type": "sim-task-field-path", "name": name},
                            className="value-input",
                            style={"width": "100%", "marginBottom": "8px"},
                        ),
                        html.Label("Platforms (optional)", style={"fontWeight": "bold", "fontSize": "1em"}),
                        dcc.Input(
                            value=platforms_value,
                            type="text",
                            placeholder="linux, win32",
                            id={"type": "sim-task-field-platforms", "name": name},
                            className="value-input",
                            style={"width": "100%", "marginBottom": "8px"},
                        ),
                    ],
                    id={"type": "sim-more-task-field-div", "name": name},
                    className="expandable-area",
                    style=Style.hidden,
                ),
            ],
            style={"width": "100%"}
        ),
        html.Div([
            html.Div([
                ui.icon_button(
                    icon=icon("more", className="icon normal rotate", id={"type": "sim-more-task-fields-icon", "name": name}),
                    color="default",
                    id={"type": "sim-more-fields-task", "name": name},
                    tooltip="Show/Hide extra fields",
                    tooltip_options="bottom small",
                )
            ], id={"type": "sim-more-fields-task-div", "name": name}, style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": "sim-duplicate-task", "name": name}),
                ui.delete_button(id={"type": "sim-delete-task", "name": name}),
            ], style={"display": "flex", "flexDirection": "horizontal", "alignItems": "center", "gap": "5px"}),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
    ],
    className="tile config",
    id={"type": "sim-task-card", "name": name},
)

def sim_add_task_card():
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div("+", style={"fontSize": "2.5em", "lineHeight": "80px", "height": "80px", "marginTop": "-2px", "marginBottom": "-16px"}),
                    html.Div("Add new task", style={"fontWeight": "bold", "fontSize": "1.2em", "paddingBottom": "20px"}),
                ],
                style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
            ),
            id="sim-task-new",
            n_clicks=0,
            style={"textDecoration": "none", "height": "100%"},
        ),
        className="tile config add hover",
        id="sim-task-add-card",
    )

def sim_default_task_note():
    """
    Shown instead of task cards when the simulation defines none: the run then
    falls back to the Makefile's "sim" rule.
    """
    return html.Div(
        [
            html.Div("No task defined", style={"fontWeight": "bold", "marginBottom": "6px"}),
            html.Div(
                'This simulation runs "make sim" from its Makefile, the default since before tasks existed. '
                "Add a task to take over: the Makefile is then no longer required.",
                className="odx-panel-note",
            ),
        ],
        id="sim-default-task-note",
        className="tile config",
    )

def sim_cards_from_tasks(tasks):
    cards = []
    if isinstance(tasks, list):
        for idx, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            name = str(task.get("name", "")).strip()
            if name == "":
                name = f"task{idx + 1}"

            dependencies = task.get("dependencies", [])
            if isinstance(dependencies, str):
                dependencies_value = dependencies
            elif isinstance(dependencies, list):
                dependencies_value = ", ".join([str(x) for x in dependencies if str(x).strip()])
            else:
                dependencies_value = ""

            commands = task.get("commands", [])
            if isinstance(commands, list):
                commands_value = "\n".join([str(x) for x in commands if str(x).strip()])
            elif isinstance(commands, str):
                commands_value = commands
            else:
                commands_value = ""

            path_value = str(task.get("path", "")) if task.get("path", "") is not None else ""

            platforms = task.get("platforms", "")
            if isinstance(platforms, list):
                platforms_value = ", ".join([str(x) for x in platforms if str(x).strip()])
            else:
                platforms_value = str(platforms) if platforms is not None else ""

            cards.append(
                sim_task_card(
                    name=name,
                    dependencies_value=dependencies_value,
                    commands_value=commands_value,
                    path_value=path_value,
                    platforms_value=platforms_value,
                )
            )

    if not cards:
        cards.append(sim_default_task_note())
    cards.append(sim_add_task_card())
    return cards


######################################
# Reading the architectures back from the page
######################################
# Every architecture card is rendered at once, so what the user typed lives in
# the page and never has to be mirrored into a store. Component ids carry the
# card (and, for a parameter domain, the row) they belong to: "a000" / "d000",
# zero padded so the order dash returns pattern matching values in is the order
# they are displayed in.

def _by_arch(ids, values):
    """{card uid: value} for a one-per-architecture pattern matching input."""
    return {i.get("arch"): v for i, v in zip(ids or [], values or []) if isinstance(i, dict)}


def gather_architectures(
    arch_ids, arch_names, arch_metrics_files, arch_extras, arch_collapsed,
    domain_ids, domain_names, domain_modes,
    domain_target_files, domain_param_files, domain_start_delimiters, domain_stop_delimiters,
    domain_param_dirs=None, domain_combines=None,
):
    """
    Rebuild the architecture cards from what is currently in the page. Used both
    to save and to re-render the section after a structural change, so an edit in
    one card survives adding, duplicating or deleting another.
    """
    names = _by_arch(arch_ids, arch_names)
    metrics_files = _by_arch(arch_ids, arch_metrics_files)
    extras = _by_arch(arch_ids, arch_extras)
    collapsed = _by_arch(arch_ids, arch_collapsed)

    domains = {}
    domain_count = len(domain_ids or [])
    domain_param_dirs = list(domain_param_dirs or []) + [""] * domain_count
    domain_combines = list(domain_combines or []) + [""] * domain_count
    for (
        domain_id, name, mode, target_file, param_file, start_delimiter, stop_delimiter,
        param_dir, combine,
    ) in zip(
        domain_ids or [], domain_names or [], domain_modes or [],
        domain_target_files or [], domain_param_files or [],
        domain_start_delimiters or [], domain_stop_delimiters or [],
        domain_param_dirs, domain_combines,
    ):
        if not isinstance(domain_id, dict):
            continue
        domains.setdefault(domain_id.get("arch"), []).append((
            domain_id.get("domain"),
            {
                "name": str(name or ""),
                "mode": mode or "inherit",
                "param_target_file": str(target_file or ""),
                "param_file": str(param_file or ""),
                "param_dir": str(param_dir or ""),
                "combine": combine or sim_architectures.COMBINE_REPLACE,
                "start_delimiter": str(start_delimiter or ""),
                "stop_delimiter": str(stop_delimiter or ""),
            },
        ))

    cards = []
    for uid in sorted(names):
        try:
            extra = json.loads(extras.get(uid) or "{}")
        except ValueError:
            extra = {}
        cards.append({
            "uid": uid,
            "name": str(names.get(uid) or ""),
            "metrics_file": str(metrics_files.get(uid) or ""),
            "extra": extra if isinstance(extra, dict) else {},
            "collapsed": bool(collapsed.get(uid)),
            "domains": [domain for _domain_uid, domain in sorted(domains.get(uid, []))],
        })
    return cards


# The pattern matching dependencies holding the architecture cards, in the order
# the callbacks using them take their arguments (dash hands them over in
# declaration order). Ids and server owned values are always read as State;
# `field_dep` says whether the rest wake the callback up: the structural callback
# only reads them, while the save callback watches them to keep its dirty state
# fresh.
def arch_dependencies(field_dep):
    domain_pattern = {"arch": dash.ALL, "domain": dash.ALL}
    return [
        State({"type": "sim-arch-name", "arch": dash.ALL}, "id"),
        field_dep({"type": "sim-arch-name", "arch": dash.ALL}, "value"),
        field_dep({"type": "sim-arch-metrics-file", "arch": dash.ALL}, "value"),
        # Hidden, server owned values: they only ever change with a re-render.
        State({"type": "sim-arch-extra", "arch": dash.ALL}, "value"),
        State({"type": "sim-arch-collapsed", "arch": dash.ALL}, "value"),
        State(dict(domain_pattern, type="sim-domain-name"), "id"),
        field_dep(dict(domain_pattern, type="sim-domain-name"), "value"),
        field_dep(dict(domain_pattern, type="sim-domain-mode"), "value"),
        field_dep(dict(domain_pattern, type="sim-domain-target-file"), "value"),
        field_dep(dict(domain_pattern, type="sim-domain-param-file"), "value"),
        field_dep(dict(domain_pattern, type="sim-domain-start-delimiter"), "value"),
        field_dep(dict(domain_pattern, type="sim-domain-stop-delimiter"), "value"),
        field_dep(dict(domain_pattern, type="sim-domain-param-dir"), "value"),
        field_dep(dict(domain_pattern, type="sim-domain-combine"), "value"),
    ]


def _arch_index(cards, uid):
    for index, card in enumerate(cards):
        if card.get("uid") == uid:
            return index
    return None


def _domain_index(domain_ids, arch_uid, domain_uid):
    """Position of a parameter domain in its card, from the ids in the page."""
    uids = sorted(
        i.get("domain") for i in domain_ids or []
        if isinstance(i, dict) and i.get("arch") == arch_uid
    )
    return uids.index(domain_uid) if domain_uid in uids else None


######################################
# Callbacks
######################################

@dash.callback(
    Output({"type": "sim-arch-body", "arch": dash.MATCH}, "className"),
    Output({"type": "sim-arch-toggle-icon", "arch": dash.MATCH}, "className"),
    Output({"type": "sim-arch-card", "arch": dash.MATCH}, "className"),
    Output({"type": "sim-arch-collapsed", "arch": dash.MATCH}, "value"),
    Input({"type": "sim-arch-toggle", "arch": dash.MATCH}, "n_clicks"),
    State({"type": "sim-arch-collapsed", "arch": dash.MATCH}, "value"),
    State({"type": "sim-arch-card", "arch": dash.MATCH}, "className"),
    prevent_initial_call=True,
)
def toggle_architecture(n_clicks, collapsed, card_class):
    """
    Fold an architecture card down to its head, or unfold it. The new state is
    written back to the hidden value the card carries, so a re-render of the
    section keeps every card as it was.
    """
    if not n_clicks:
        return (dash.no_update,) * 4

    collapsed = not collapsed
    classes = [name for name in str(card_class or "").split() if name != "collapsed"]
    if collapsed:
        classes.append("collapsed")
    return (
        "animated-section hide" if collapsed else "animated-section",
        "icon normal rotate" if collapsed else "icon normal rotate rotated",
        " ".join(classes),
        "1" if collapsed else "",
    )


@dash.callback(
    Output({"type": "sim-domain-name", "arch": dash.MATCH, "domain": dash.ALL}, "options"),
    Input({"type": "sim-arch-name", "arch": dash.MATCH}, "value"),
    State({"type": "sim-domain-name", "arch": dash.MATCH, "domain": dash.ALL}, "value"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def update_domain_options(arch, domains, odatix_settings):
    """
    A card pointed at another architecture overrides the domains of that one:
    every domain dropdown of the card follows its architecture dropdown. A name
    already picked is kept as an option, so changing the architecture does not
    clear what the file holds.
    """
    options = domain_options(str(arch or ""), odatix_settings)
    return [with_domain_option(options, str(domain or "")) for domain in domains or []]


@dash.callback(
    Output("sim-hl-param-domains", "data"),
    Input({"type": "sim-arch-name", "arch": dash.ALL}, "value"),
    State("odatix-settings", "data"),
)
def update_sim_param_domains(arch_names, odatix_settings):
    """
    The parameter domains the commands of this simulation can use: Odatix
    substitutes one variable per parameter domain of the architecture under
    test, so they are those of the architectures listed in the Architectures
    section, not of the simulation itself.

    A simulation listing no architecture may still run on any of them, so it
    gets the domains of all the architectures of the workspace.
    """
    names = [str(name or "") for name in arch_names or [] if str(name or "")]
    if not names:
        names = ["*"]
    domains = []
    for arch in names:
        for domain in architecture_domain_names(arch, odatix_settings):
            if domain not in domains:
                domains.append(domain)
    return domains


# Push the parameter domains to the client and ask the highlighter to redraw.
dash.clientside_callback(
    """
    function(domains) {
        window.__odatixHlParamDomains = domains || [];
        // A simulation defines no variable of its own.
        window.__odatixHlVariables = [];
        document.dispatchEvent(new CustomEvent("odatix:refresh-var-highlight"));
        return "";
    }
    """,
    Output("sim-hl-dummy", "data"),
    Input("sim-hl-param-domains", "data"),
)


@dash.callback(
    Output("sim-arch-container", "children", allow_duplicate=True),
    # An architecture or a parameter domain added, duplicated or deleted changes
    # the settings without any field changing, and the save callback cannot watch
    # the section itself without closing a dependency cycle through the url: mark
    # the button from here.
    Output({"page": page_path, "action": "save-all"}, "className", allow_duplicate=True),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip", allow_duplicate=True),
    Input("sim-arch-new", "n_clicks"),
    Input({"type": "sim-arch-duplicate", "arch": dash.ALL}, "n_clicks"),
    Input({"type": "sim-arch-delete", "arch": dash.ALL}, "n_clicks"),
    Input({"type": "sim-domain-new", "arch": dash.ALL}, "n_clicks"),
    Input({"type": "sim-domain-duplicate", "arch": dash.ALL, "domain": dash.ALL}, "n_clicks"),
    Input({"type": "sim-domain-delete", "arch": dash.ALL, "domain": dash.ALL}, "n_clicks"),
    *arch_dependencies(State),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def update_architectures(
    new_click, duplicate_clicks, delete_clicks,
    domain_new_clicks, domain_duplicate_clicks, domain_delete_clicks,
    arch_ids, arch_names, arch_metrics_files, arch_extras, arch_collapsed,
    domain_ids, domain_names, domain_modes,
    domain_target_files, domain_param_files, domain_start_delimiters, domain_stop_delimiters,
    domain_param_dirs, domain_combines,
    odatix_settings,
):
    """
    Apply a structural change (an architecture or one of its parameter domains
    added, duplicated or deleted) and re-render the whole section from what the
    page currently holds, so every unsaved edit is carried over.
    """
    trigger = ctx.triggered_id
    # A click is only an action once the button has actually been clicked;
    # a value of 0 is a button that was just rendered.
    if not (ctx.triggered[0]["value"] if ctx.triggered else None):
        return dash.no_update, dash.no_update, dash.no_update

    action = trigger if isinstance(trigger, str) else (trigger or {}).get("type")
    arch_uid = trigger.get("arch") if isinstance(trigger, dict) else None

    cards = gather_architectures(
        arch_ids, arch_names, arch_metrics_files, arch_extras, arch_collapsed,
        domain_ids, domain_names, domain_modes,
        domain_target_files, domain_param_files, domain_start_delimiters, domain_stop_delimiters,
        domain_param_dirs, domain_combines,
    )
    index = _arch_index(cards, arch_uid) if arch_uid is not None else None

    if action == "sim-arch-new":
        cards.append(new_arch_card(
            [card["name"] for card in cards], workspace_architecture_names(odatix_settings),
        ))

    elif action == "sim-arch-duplicate" and index is not None:
        copy = copy_module.deepcopy(cards[index])
        # The copy keeps the architecture it was made from: nothing is dropped
        # behind the user's back, and pointing it at another design is one click
        # away in its dropdown. It is folded exactly like the card it copies.
        cards.insert(index + 1, copy)

    elif action == "sim-arch-delete" and index is not None:
        cards.pop(index)

    elif action == "sim-domain-new" and index is not None:
        cards[index]["domains"].append(new_domain())
        cards[index]["collapsed"] = False

    elif action in ("sim-domain-duplicate", "sim-domain-delete") and index is not None:
        domains = cards[index]["domains"]
        domain_index = _domain_index(domain_ids, arch_uid, trigger.get("domain"))
        if domain_index is not None and domain_index < len(domains):
            if action == "sim-domain-delete":
                domains.pop(domain_index)
            else:
                copy = copy_module.deepcopy(domains[domain_index])
                # Two rows for the same domain say nothing: the copy is there to
                # be pointed at another one, so it starts with none picked.
                copy["name"] = ""
                domains.insert(domain_index + 1, copy)

    return (
        arch_cards(cards, odatix_settings),
        "color-button warning icon-button tooltip bottom small",
        "Unsaved changes!",
    )


@dash.callback(
    Output("sim-task-cards-row", "children", allow_duplicate=True),
    Input("sim-task-new", "n_clicks"),
    Input({"type": "sim-duplicate-task", "name": dash.ALL}, "n_clicks"),
    Input({"type": "sim-delete-task", "name": dash.ALL}, "n_clicks"),
    State("sim-task-cards-row", "children"),
    State({"type": "sim-task-field-name", "name": dash.ALL}, "value"),
    State({"type": "sim-task-field-dependencies", "name": dash.ALL}, "value"),
    State({"type": "sim-task-field-commands", "name": dash.ALL}, "value"),
    State({"type": "sim-task-field-path", "name": dash.ALL}, "value"),
    State({"type": "sim-task-field-platforms", "name": dash.ALL}, "value"),
    prevent_initial_call=True,
)
def update_sim_task_cards(
    new_click,
    duplicate_clicks,
    delete_clicks,
    cards,
    task_names,
    task_dependencies,
    task_commands,
    task_paths,
    task_platforms,
):
    trigger_id = ctx.triggered_id

    if cards is None:
        cards = []

    def card_id_of(card):
        return card.get("props", {}).get("id") if isinstance(card, dict) else None

    # Drop the trailing "Add" card and the "no task" note; both are rebuilt below.
    cards = [
        card for card in cards
        if card_id_of(card) not in ("sim-task-add-card", "sim-default-task-note")
    ]

    if trigger_id == "sim-task-new" and new_click:
        existing_names = [
            cid.get("name", "") for cid in map(card_id_of, cards) if isinstance(cid, dict)
        ]
        # The first task of a simulation is its entry point, and the task graph
        # always starts at "main".
        if not existing_names:
            cards.append(sim_task_card(name="main"))
        else:
            idx = 1
            while f"task{idx}" in existing_names:
                idx += 1
            cards.append(sim_task_card(name=f"task{idx}"))

    if isinstance(trigger_id, dict):
        trig_type = trigger_id.get("type")
        trig_name = trigger_id.get("name")

        idx = None
        for i, card in enumerate(cards):
            cid = card_id_of(card)
            if isinstance(cid, dict) and cid.get("type") == "sim-task-card" and cid.get("name") == trig_name:
                idx = i
                break

        if trig_type == "sim-delete-task" and idx is not None and idx < len(delete_clicks) and delete_clicks[idx]:
            cards = [
                card for card in cards
                if not (
                    isinstance(card_id_of(card), dict)
                    and card_id_of(card).get("type") == "sim-task-card"
                    and card_id_of(card).get("name") == trig_name
                )
            ]
        elif trig_type == "sim-duplicate-task" and idx is not None and idx < len(duplicate_clicks) and duplicate_clicks[idx]:
            existing_names = [
                cid.get("name", "") for cid in map(card_id_of, cards) if isinstance(cid, dict)
            ]
            copy_idx = 1
            while f"{trig_name}_copy{copy_idx}" in existing_names:
                copy_idx += 1

            cards.append(
                sim_task_card(
                    name=f"{trig_name}_copy{copy_idx}",
                    dependencies_value=task_dependencies[idx] if idx < len(task_dependencies) else "",
                    commands_value=task_commands[idx] if idx < len(task_commands) else "",
                    path_value=task_paths[idx] if idx < len(task_paths) else "",
                    platforms_value=task_platforms[idx] if idx < len(task_platforms) else "",
                )
            )

    if not cards:
        cards.append(sim_default_task_note())
    cards.append(sim_add_task_card())
    return cards


@dash.callback(
    Output("sim-form-container", "children"),
    Output("sim-initial-settings", "data"),
    Output("sim-task-cards-row", "children"),
    Output("sim-arch-container", "children"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_form(search, page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    sim_name = get_key_from_url(search, "sim")
    if not sim_name:
        settings = normalize_simulation_settings({})
    else:
        simulations = get_workspace(odatix_settings).simulations
        settings = normalize_simulation_settings(settings_as_written(simulations.entry(sim_name).settings))

    return (
        sim_form(settings),
        settings,
        sim_cards_from_tasks(settings.get("tasks", [])),
        arch_cards(arch_cards_from_settings(settings.get("architectures")), odatix_settings),
    )


@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output(f"url_{page_path}", "search"),
    Output("sim-saved-settings", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input("sim-title", "value"),
    Input("sim-use-parameters", "value"),
    Input("sim-param-target-file", "value"),
    Input("sim-start-delimiter", "value"),
    Input("sim-stop-delimiter", "value"),
    Input("sim-override-parameters", "value"),
    Input("sim-override-param-file", "value"),
    Input("sim-override-param-target-file", "value"),
    Input("sim-override-start-delimiter", "value"),
    Input("sim-override-stop-delimiter", "value"),
    Input("sim-progress-file", "value"),
    Input("sim-progress-regex", "value"),
    Input("sim-invariant-domains", "value"),
    *arch_dependencies(Input),
    Input({"type": "sim-task-field-name", "name": dash.ALL}, "value"),
    Input({"type": "sim-task-field-dependencies", "name": dash.ALL}, "value"),
    Input({"type": "sim-task-field-commands", "name": dash.ALL}, "value"),
    Input({"type": "sim-task-field-path", "name": dash.ALL}, "value"),
    Input({"type": "sim-task-field-platforms", "name": dash.ALL}, "value"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("sim-initial-settings", "data"),
    State("sim-saved-settings", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(
    n_clicks,
    sim_title_value,
    use_parameters,
    param_target_file,
    start_delimiter,
    stop_delimiter,
    override_parameters,
    override_param_file,
    override_param_target_file,
    override_start_delimiter,
    override_stop_delimiter,
    progress_file,
    progress_regex,
    invariant_domains,
    arch_ids,
    arch_names,
    arch_metrics_files,
    arch_extras,
    arch_collapsed,
    domain_ids,
    domain_names,
    domain_modes,
    domain_target_files,
    domain_param_files,
    domain_start_delimiters,
    domain_stop_delimiters,
    domain_param_dirs,
    domain_combines,
    task_names,
    task_dependencies,
    task_commands,
    task_paths,
    task_platforms,
    search,
    page,
    initial_settings,
    saved_settings,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    if saved_settings is None:
        reference_settings = normalize_simulation_settings(initial_settings)
    else:
        reference_settings = normalize_simulation_settings(saved_settings)

    current_values = {
        # The whole "architectures" block comes from the cards, including what
        # this page does not edit: each card carries the keys its entry held.
        "architectures": arch_cards_to_settings(gather_architectures(
            arch_ids, arch_names, arch_metrics_files, arch_extras, arch_collapsed,
            domain_ids, domain_names, domain_modes,
            domain_target_files, domain_param_files, domain_start_delimiters, domain_stop_delimiters,
            domain_param_dirs, domain_combines,
        )),
        "progress": {
            "file": progress_file or "",
            "regex": progress_regex or "",
        },
        "invariant_domains": parse_invariant_domains_text(invariant_domains),
        "tasks": build_tasks_list(
            task_names, task_dependencies, task_commands, task_paths, task_platforms
        ),
    }

    # The deprecated fields are only written back for a simulation that already used them,
    # so editing anything else does not resurrect them.
    if uses_legacy_parameters(reference_settings):
        current_values.update({
            "use_parameters": True if use_parameters else False,
            "param_target_file": param_target_file or "",
            "start_delimiter": start_delimiter or "",
            "stop_delimiter": stop_delimiter or "",
            "override_parameters": True if override_parameters else False,
            "override_param_file": override_param_file or "",
            "override_param_target_file": override_param_target_file or "",
            "override_start_delimiter": override_start_delimiter or "",
            "override_stop_delimiter": override_stop_delimiter or "",
        })

    current_settings = normalize_simulation_settings(current_values)

    sim_name = get_key_from_url(search, "sim")
    simulations = get_workspace(odatix_settings).simulations

    if not sim_title_value:
        return (
            "color-button error-status icon-button tooltip bottom",
            "Simulation name cannot be empty",
            dash.no_update,
            saved_settings,
        )

    for character in hard_settings.invalid_filename_characters:
        if character in sim_title_value:
            label = "' ' (space)" if character == " " else f"'{character}'"
            return (
                "color-button error-status icon-button tooltip bottom",
                f"Unauthorized character in simulation name: {label}",
                dash.no_update,
                saved_settings,
            )

    if triggered_id == {"page": page_path, "action": "save-all"}:
        new_search = dash.no_update

        if sim_name and sim_title_value != sim_name:
            if sim_title_value in simulations:
                return (
                    "color-button error-status icon-button tooltip bottom",
                    f"'{sim_title_value}' already exists",
                    dash.no_update,
                    saved_settings,
                )
            if sim_name in simulations:
                simulations.rename(sim_name, sim_title_value)
            sim_name = sim_title_value
            new_search = f"?sim={sim_name}"
        elif not sim_name:
            sim_name = sim_title_value
            new_search = f"?sim={sim_name}"

        simulation = simulations.get(sim_name)
        if simulation is None:
            simulation = simulations.create(sim_name)

        try:
            simulation.update(
                dict(current_settings, architectures=architectures_to_yaml(current_settings.get("architectures")))
            )
            return (
                "color-button disabled icon-button tooltip delay bottom small",
                "Nothing to save",
                new_search,
                current_settings,
            )
        except Exception:
            return (
                "color-button error-status icon-button tooltip bottom small",
                "Failed to save...",
                dash.no_update,
                saved_settings,
            )

    if current_settings != reference_settings or sim_title_value != (sim_name or ""):
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
        saved_settings,
    )


@dash.callback(
    Output("sim-params-config-fields", "className"),
    Input("sim-use-parameters", "value"),
)
def toggle_parameter_fields(use_parameters):
    return "animated-section" if use_parameters else "animated-section hide"


@dash.callback(
    Output("sim-override-config-fields", "className"),
    Input("sim-override-parameters", "value"),
)
def toggle_override_fields(override_parameters):
    return "animated-section" if override_parameters else "animated-section hide"


@dash.callback(
    Output({"page": page_path, "type": "sim-title-div"}, "children"),
    Input(f"url_{page_path}", "search"),
)
def update_sim_title(search):
    return simulation_title(get_key_from_url(search, "sim") or "")


@dash.callback(
    Output({"type": "sim-more-task-field-div", "name": dash.ALL}, "style"),
    Output({"type": "sim-more-task-fields-icon", "name": dash.ALL}, "className"),
    Input({"type": "sim-more-fields-task", "name": dash.ALL}, "n_clicks"),
    State({"type": "sim-more-task-field-div", "name": dash.ALL}, "style"),
    State({"type": "sim-more-task-fields-icon", "name": dash.ALL}, "className"),
    State({"type": "sim-task-field-name", "name": dash.ALL}, "value"),
)
def toggle_sim_task_more_fields(n_clicks, expandable_area_styles, icon_classes, task_names):
    trigger_id = ctx.triggered_id
    if not isinstance(trigger_id, dict) or "name" not in trigger_id:
        return [dash.no_update] * len(n_clicks), [dash.no_update] * len(n_clicks)

    index = None
    for i, current_name in enumerate(task_names):
        if trigger_id.get("name") == current_name:
            index = i
            break

    new_expandable_area_styles = list(expandable_area_styles)
    new_icon_classes = list(icon_classes)
    if index is not None:
        if n_clicks[index] % 2 == 0:
            new_expandable_area_styles[index] = Style.hidden
            new_icon_classes[index] = "icon normal rotate"
        else:
            new_expandable_area_styles[index] = Style.visible
            new_icon_classes[index] = "icon normal rotate rotated"
    return new_expandable_area_styles, new_icon_classes


# The configuration editor opens on a directory, so the link of a row follows
# what its "parameter directory" field says, before it is even saved. A row
# naming no directory has nothing to open: its button stays in place, greyed
# out, and says why through its tooltip.
dash.clientside_callback(
    dash.ClientsideFunction(namespace="odatix_sim", function_name="domainConfigLinks"),
    Output({"type": "sim-domain-configs", "arch": dash.ALL, "domain": dash.ALL, "is_link": True}, "href"),
    Output({"type": "sim-domain-configs", "arch": dash.ALL, "domain": dash.ALL, "is_link": True}, "style"),
    Output({"type": "sim-domain-configs", "arch": dash.ALL, "domain": dash.ALL}, "className"),
    Output({"type": "sim-domain-configs", "arch": dash.ALL, "domain": dash.ALL}, "data-tooltip"),
    Input({"type": "sim-domain-param-dir", "arch": dash.ALL, "domain": dash.ALL}, "value"),
    Input(f"url_{page_path}", "search"),
)


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        html.Div(id={"page": page_path, "type": "sim-title-div"}, style={"marginTop": "20px"}),
        html.Div(id="sim-form-container"),
        html.Div(
            children=[
                ui.title_tile(
                    text="Architectures",
                    id="sim-arch-title",
                    tooltip=(
                        "The architectures this testbench is written for, and what the simulation "
                        "changes for each of them: how their parameter domains are substituted (where "
                        "the values are written, whether they are written at all, or where they come "
                        "from) and which metrics file its results are exported through. An architecture "
                        "listed with nothing under it is simply one the simulation runs on. Listing "
                        "them is an indication, not a restriction: running the simulation on an "
                        "architecture it does not list works, and only warns. \"All architectures\" "
                        "(\"*\") applies to every one of them, and the entries matching a design apply "
                        "in the order they are written, so an architecture placed after a wildcard "
                        "refines it."
                    ),
                ),
                html.Div(
                    id="sim-arch-container",
                    children=[
                        ui.add_card(id="sim-arch-new", text="Add an architecture", className="tile config")
                    ],
                    className="card-matrix configs wide",
                ),
            ],
        ),
        html.Div(
            children=[
                ui.title_tile(
                    text="Task Definition",
                    id="sim-task-title",
                    tooltip=(
                        "Tasks define the steps of the simulation. Without any task, the simulation runs "
                        '"make sim" from its Makefile. Commands can use the built-in placeholders listed '
                        'under "Variables", and one placeholder per parameter domain.'
                    ),
                    buttons=builtin_variables.variable_list("simulation", id="sim-builtin-variables"),
                ),
                html.Div([
                    html.Div(
                        id="sim-task-cards-row",
                        children=[sim_add_task_card()],
                        className="tiles-container config",
                        style={
                            "display": "flex",
                            "justifyContent": "flex-start",
                            "alignItems": "flex-start",
                            "flexWrap": "wrap",
                            "marginBottom": "30px",
                            "columnGap": "var(--tile-gap)",
                        },
                    ),
                ]),
            ],
        ),
        dcc.Store(id="sim-initial-settings", data=None),
        dcc.Store(id="sim-saved-settings", data=None),
        # The parameter domains of the architectures the simulation runs on,
        # pushed to the command highlighter.
        dcc.Store(id="sim-hl-param-domains", data=[]),
        dcc.Store(id="sim-hl-dummy", data=""),
        # What the command highlighter colors as built-in variables.
        builtin_variables.highlight_data("simulation", id="sim-hl-builtins", declares_variables=True),
    ],
    className="page-content",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

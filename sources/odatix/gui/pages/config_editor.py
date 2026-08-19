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

import os
import re
import json
import dash
from dash import html, dcc, Input, Output, State, ctx, Patch
from dash.exceptions import MissingCallbackContextException
import uuid
import random
from natsort import natsorted

import odatix.gui.ui_components as ui
import odatix.gui.config_rules as config_rules
import odatix.gui.replacement_help as replacement_help
import odatix.gui.sim_domains as sim_domains
from odatix.gui.utils import get_instance_mode, get_instance_collection_context, get_key_from_url, get_workspace
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
import odatix.components.replace_params as replace_params
import odatix.workspace.sim_architectures as sim_architectures
from odatix.workspace.domains import ParameterDomain
from odatix.workspace.space import ORIGIN_BLACKLISTED, ORIGIN_GENERATED, ORIGIN_EDITED, ORIGIN_MANUAL
from odatix.gui.icons import icon
from odatix.gui.css_helper import Style

verbose = False

page_path = "/config_editor"

# How many configuration cards a domain shows before it stops and offers to show
# more. A card is a text area, two stores and four buttons: a domain holding
# hundreds of them is what makes the page slow, and most of them are not being
# looked at.
configs_per_page = 30

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Configuration Editor',
    name='Configuration Editor',
    order=4,
)

######################################
# Helper Functions
######################################

def split_by_domain(flat_list, lengths):
    result = []
    idx = 0
    for l in lengths:
        result.append(flat_list[idx:idx+l])
        idx += l
    return result

def get_uuid():
    return str(uuid.uuid4())

def sim_arch_name(search):
    """
    The architecture a simulation page is opened on, or None: what
    "?sim=<simulation>&arch=<architecture>" names, which is a simulation's
    parameter domain overrides for that architecture rather than the
    configuration directories of the whole simulation.
    """
    mode, instance_name = get_instance_mode(search)
    if mode != "simulation" or not instance_name:
        return None
    arch = get_key_from_url(search, "arch")
    return str(arch) if arch else None


def sim_arch_context(search, odatix_settings):
    """
    What a "?sim=&arch=" page works on: ``(simulation, arch, entries, position)``.
    The simulation is None when the URL names none or names one that does not
    exist, and the position is None when it lists no such architecture.
    """
    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    arch = sim_arch_name(search)
    if not arch or instance_name not in instances:
        return None, arch, [], None
    simulation = instances[instance_name]
    entries, position = sim_domains.find_entry(simulation, arch, get_key_from_url(search, "entry"))
    return simulation, arch, entries, position


def config_title_error(title, other_titles, initial_title):
    """
    Reason why a configuration cannot be saved under `title`, or None if it is valid.
    `other_titles` is the list of the names already in use (the config's own current
    name included, hence the `initial_title` exception).
    """
    if not title:
        return "Configuration name cannot be empty"
    for c in hard_settings.invalid_filename_characters:
        if c in title:
            c = "' ' (space)" if c == " " else f"'{c}'"
            return f"Unauthorized character in configuration name: {c}"
    if title in other_titles and title != initial_title:
        return "A configuration with this name already exists in the domain."
    return None

def params_are_dirty(use_parameters, param_target_file, start_delimiter, stop_delimiter, domain_settings):
    """Whether the configuration parameters form differs from the saved settings."""
    if domain_settings is None:
        domain_settings = {}
    use_parameters = True if use_parameters else False # Convert from [True]/[] to True/False
    return (
        use_parameters != domain_settings.get("use_parameters", True)
        or param_target_file != domain_settings.get("param_target_file", "")
        or start_delimiter != domain_settings.get("start_delimiter", "")
        or stop_delimiter != domain_settings.get("stop_delimiter", "")
    )

######################################
# UI Components
######################################

#: What each origin says on a configuration card, and how it is presented. The
#: rules preview labels the same configurations, so the labels live with it.
ORIGIN_LABELS = config_rules.ORIGIN_LABELS

#: How the delete button of a card reads, per origin. A configuration that only
#: exists as a rule has no file to delete, so its button is inert and says why.
DELETE_TOOLTIPS = {
    ORIGIN_GENERATED: ("caution", "Blacklist this generated configuration"),
    ORIGIN_EDITED: ("caution", "Discard this edit and go back to what the rules produce"),
    ORIGIN_MANUAL: ("caution", "Delete"),
    ORIGIN_BLACKLISTED: ("primary", "Remove this configuration from the blacklist"),
}

def origin_badge(origin):
    """The origin badge of a card, empty for a plain hand-written configuration."""
    if origin not in ORIGIN_LABELS:
        return []
    text, color, _tooltip = ORIGIN_LABELS[origin]
    return ui.badge(text, color=color)

def origin_chip(domain_uuid, config_uuid, origin):
    tooltip = ORIGIN_LABELS.get(origin, ("", "", ""))[2]
    return html.Div(
        origin_badge(origin),
        id={"type": "config-origin", "domain_uuid": domain_uuid, "config_uuid": config_uuid},
        className="odx-config-origin tooltip delay bottom auto" if tooltip else "odx-config-origin",
        **{"data-tooltip": tooltip},
    )

def delete_button_class(origin):
    color = DELETE_TOOLTIPS.get(origin, DELETE_TOOLTIPS[ORIGIN_MANUAL])[0]
    return f"color-button {color} icon-button icon-only tooltip bottom auto"


def config_action_button(domain_uuid, config_uuid, origin):
    """Delete a file, blacklist a generated config, or restore a blacklisted one."""
    action_id = {"type": "delete-config", "domain_uuid": domain_uuid, "config_uuid": config_uuid}
    tooltip = DELETE_TOOLTIPS.get(origin, DELETE_TOOLTIPS[ORIGIN_MANUAL])[1]
    if origin == ORIGIN_BLACKLISTED:
        return ui.icon_button(
            icon=icon(
                "reset",
                className="icon",
                id={"type": "restore-config-icon", "domain_uuid": domain_uuid, "config_uuid": config_uuid},
            ),
            color="primary",
            id=action_id,
            tooltip=tooltip,
            tooltip_options="bottom auto",
        )
    return ui.delete_button(id=action_id, tooltip=tooltip)


def card_class(config_layout, is_blacklisted):
    """The classes of a configuration card. Everything it looks like is a class:
    the layout switch below rewrites this same string."""
    classes = ["card", "configs", "odx-config-card"]
    if config_layout == "wide":
        classes.append("wide")
    if is_blacklisted:
        classes.append("odx-config-blacklisted")
    return " ".join(classes)


def config_card(domain_uuid, config_uuid, config_name, content, initial_content, config_layout="normal", origin=ORIGIN_MANUAL):
    display_name = config_name[:-4] if config_name.endswith(".txt") else config_name

    save_class =  "color-button disabled"
    status_text = ""
    status_class = "status"
    # A configuration the rules produce is named by the name template: renaming
    # the file here would only make a copy, and leave the rule's own name to
    # reappear beside it.
    from_rules = origin in (ORIGIN_GENERATED, ORIGIN_EDITED, ORIGIN_BLACKLISTED)
    is_blacklisted = origin == ORIGIN_BLACKLISTED
    return html.Div([
        html.Div([
            dcc.Input(
                value=f"{display_name}",
                type="text",
                id={"type": "config-title", "domain_uuid": domain_uuid, "config_uuid": config_uuid},
                className="title-input odx-config-name preview" if from_rules else "title-input odx-config-name",
                readOnly=from_rules,
            )
        ]),
        dcc.Textarea(
            id={"type": "config-content", "domain_uuid": domain_uuid, "config_uuid": config_uuid},
            value=content,
            readOnly=is_blacklisted,
            className="odx-config-content odx-config-content-compact" if config_layout == "compact"
                      else "odx-config-content auto-resize-textarea",
        ),
        dcc.Store(
            id={"type": "config-metadata", "domain_uuid": domain_uuid, "config_uuid": config_uuid},
            data={
                "domain_uuid": domain_uuid,
                "config_uuid": config_uuid,
                "config_name": config_name,
                "config_content": content,
                "origin": origin,
            }
        ),
        html.Div([
            html.Div([
                html.Div([ui.icon_button(
                    icon=icon("save", className="icon", id={"type": "save-config-icon", "domain_uuid": domain_uuid, "config_uuid": config_uuid}),
                    color="disabled",
                    text="Save",
                    width="78px",
                    id={"type": "save-config", "domain_uuid": domain_uuid, "config_uuid": config_uuid},
                ),], className="odx-config-card-save-button"),
                html.Div(status_text, id={"type": "save-status", "domain_uuid": domain_uuid, "config_uuid": config_uuid}, className=f"{status_class} odx-config-card-status"),
            ], className="odx-config-card-save"),
            html.Div([
                origin_chip(domain_uuid, config_uuid, origin),
                ui.duplicate_button(id={"type": "duplicate-config", "domain_uuid": domain_uuid, "config_uuid": config_uuid}),
                config_action_button(domain_uuid, config_uuid, origin),
            ], className="inline-flex-buttons odx-config-card-actions"),
        ], className="odx-config-card-footer"),
        dcc.Store(id={"type": "initial-title", "domain_uuid": domain_uuid, "config_uuid": config_uuid}, data=display_name),
        dcc.Store(id={"type": "initial-content", "domain_uuid": domain_uuid, "config_uuid": config_uuid}, data=initial_content),
    ],
    className=card_class(config_layout, is_blacklisted),
    id={"type": "config-card", "domain_uuid": domain_uuid, "config_uuid": config_uuid})

def card_index(cards, domain_uuid, config_uuid):
    """Index of the config card of that uuid in a row of cards, -1 when it is not there anymore."""
    for i, card in enumerate(cards):
        card_id = card.get("props", {}).get("id") if isinstance(card, dict) else getattr(card, "id", None)
        if isinstance(card_id, dict) and card_id.get("type") == "config-card" \
                and card_id.get("domain_uuid") == domain_uuid and card_id.get("config_uuid") == config_uuid:
            return i
    return -1

def add_card(text: str = "Add design configuration", domain_uuid: str = hard_settings.main_parameter_domain):
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div("+", style={"fontSize": "2.5em", "lineHeight": "80px", "height": "80px", "marginTop": "-2px", "marginBottom": "-16px"}),
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "paddingBottom": "20px"}),
                ],
                style={"textAlign": "center"}
            ),
            id={"type": "new-config", "domain_uuid": domain_uuid},
            n_clicks=0,
            style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
        ),
        className=f"card configs add hover",
        id={"type": "add-config-card", "domain_uuid": domain_uuid},
        style={
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box"
        },
    )

#: How each kind of instance the page edits is named to a user.
INSTANCE_LABELS = {"workflow": "Workflow", "simulation": "Simulation", "arch": "Architecture"}


def instance_label(mode:str="arch"):
    return INSTANCE_LABELS.get(mode, INSTANCE_LABELS["arch"])


def no_instance_message(mode:str="arch"):
    return "No " + instance_label(mode).lower() + " selected."


def main_domain_placeholder():
    """
    Stands in for the main domain title of a simulation, which has none: the
    callback filling that title needs its div to exist whatever is shown.
    """
    return html.Div(
        id=f"param-domain-title-div-{hard_settings.main_parameter_domain}",
        style={"display": "none"},
    )


def instance_title(mode:str="arch", instance_name:str="", arch:str=None):
    title = instance_name
    if mode == "simulation" and arch:
        # What this simulation substitutes for one architecture: the page is
        # opened from that architecture's card, and goes back to it.
        title = instance_name + "  \u2192  " + arch
    if mode == "workflow":
        back_link = "/workflows"
        settings_link = f"/workflow_editor?workflow={instance_name}"
        settings_text = "Workflow Settings"
    elif mode == "simulation":
        settings_link = f"/sim_editor?sim={instance_name}"
        # Opened on one architecture, the page goes back to the card it was
        # opened from rather than to the list of designs.
        back_link = settings_link if arch else "/architectures"
        settings_text = "Simulation Settings"
    else:
        back_link = "/architectures"
        settings_link = f"/arch_editor?arch={instance_name}"
        settings_text = "Architecture Settings"

    title_content = html.Div(
        children=[
            html.H3(title, id=f"main_title", style={"marginBottom": "0px"}),
            html.Div(
                children=[
                    ui.icon_button(
                        id=f"button-open-config-editor",
                        icon=icon("gear", className="icon"),
                        text=settings_text,
                        color="default",
                        link=settings_link,
                        multiline=True,
                        width="135px",
                    ),
                    dcc.Dropdown(
                        id="config-layout-dropdown",
                        options=[
                            {"label": "Compact Layout", "value": "compact"},
                            {"label": "Normal Layout", "value": "normal"},
                            {"label": "Wide Layout", "value": "wide"},
                        ],
                        value="normal",
                        clearable=False,
                        style={"width": "155px"},
                    ),
                    ui.save_button(
                        id={"page": page_path, "action": "save-all"},
                        tooltip="Save all changes",
                        disabled=True,
                    ),
                ],
                className="inline-flex-buttons",
            )
        ],
        className="title-tile-flex",
        style={
            "display": "flex",
            "alignItems": "center",
            "padding": "0px",
            "justifyContent": "space-between",
        }
    )
    back_btn = ui.back_button(link=back_link)
    return html.Div([
        html.Div(style={"display": "none"}),
        html.Div(style={"display": "none"}),
        html.Div(style={"display": "none"}),
        html.Div(
            children=[
                back_btn,
                title_content
            ],
            className="tile title",
            style={"position": "relative"},
        )],
        className="card-matrix config",
        style={"marginBottom": "0px"},
    )

def sim_arch_domain_title(domain_uuid, entry):
    """
    The head of a section of the "?sim=&arch=" page: which parameter domain of
    the architecture the simulation substitutes its own way.

    The name is picked among the domains the architecture declares, since that
    is what an override is attached to -- a name it does not declare is a
    substitution of the simulation's own, and stays an option of its own.
    """
    name = str(entry.get("name", "") or "")
    return html.Div(
        [html.Div(
            children=[
                html.Div([
                    html.H3(
                        "Parameter domain:",
                        style={"display": "inline-block", "marginBottom": "0px", "marginRight": "10px"},
                    ),
                    html.Div(
                        dcc.Dropdown(
                            id={"type": "simarch-domain", "domain_uuid": domain_uuid},
                            options=entry.get("options") or [],
                            value=name or None,
                            placeholder="Domain...",
                            clearable=False,
                        ),
                        style={"minWidth": "260px"},
                    ),
                    # The rename machinery of an architecture domain has nothing
                    # to do here -- the name is a key of the simulation settings,
                    # saved with the rest of the section -- but every callback
                    # keyed on a domain still expects to find its components.
                    html.Div(
                        children=[
                            dcc.Input(
                                value=name,
                                type="text",
                                id={"type": "domain-title-input", "domain_uuid": domain_uuid},
                            ),
                            ui.icon_button(
                                id={"type": "save-domain-title", "domain_uuid": domain_uuid},
                                icon=icon("check", className="icon invisible"),
                                color="invisible",
                            ),
                        ],
                        style={"display": "none"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "justifyContent": "flex-start"}),
                html.Div(
                    # The same domain is never listed twice under one
                    # architecture, so there is nothing to duplicate here.
                    children=[
                        ui.delete_button(
                            id={"action": "delete-domain", "domain_uuid": domain_uuid},
                            large=False,
                            tooltip="Stop substituting this domain the simulation's way",
                        ),
                    ],
                    className="inline-flex-buttons param-domain-title",
                ),
            ],
            className="title-tile-flex",
            style={
                "display": "flex",
                "alignItems": "center",
                "padding": "0px",
                "justifyContent": "space-between",
            },
        )],
        id={"type": "param-domain-title", "domain_uuid": domain_uuid},
        className="tile title",
        style={"marginTop": "50px"},
    )


def parameter_domain_title(domain_name:str=hard_settings.main_parameter_domain, domain_uuid:str=hard_settings.main_parameter_domain, mode:str="arch", instance_name:str="", entry=None):
    # A simulation does not own its domains: they are the directories its
    # settings point at, so they are named, duplicated and deleted there --
    # unless the page is opened on one architecture, where each section is one
    # domain of that architecture the simulation substitutes its own way.
    is_simulation = mode == "simulation" and entry is None
    if domain_uuid == hard_settings.main_parameter_domain:
        text = "Main parameter domain"
        buttons = html.Div(
            children=[
                ui.duplicate_button(
                    id={"action": "duplicate-domain", "domain_uuid": domain_uuid},
                    tooltip="Duplicate as a new domain",
                ),
                # ui.icon_button(
                #     id={"action": "duplicate-domain", "domain_uuid": domain_uuid},
                #     icon=icon("duplicate", className="icon"),
                #     text="Duplicate as Domain",
                #     color="secondary",
                #     multiline=True,
                #     width="140px",
                #     tooltip="Duplicate the main parameter domain as a new domain",
                # ),
            ],
            className="inline-flex-buttons",
        )
        tooltip = "The main parameter domain is the default domain used for parameter replacement. Several parameter domains can be created to manage different sets of parameters for different design configurations or scenarios. It mainly serves as a convenient way to organize design configurations and to easily run combinations of design configurations across multiple domains."

        return ui.title_tile(text=text, id=f"domain_title_{domain_uuid}", buttons=buttons, tooltip=tooltip)
    else:
        buttons = html.Div(
            children=[
                ui.duplicate_button(
                    id={"action": "duplicate-domain", "domain_uuid": domain_uuid},
                    tooltip="Duplicate domain",
                ),
                ui.delete_button(
                    id={"action": "delete-domain", "domain_uuid": domain_uuid},
                    large=False,
                    tooltip="Delete domain",
                )
            ],
            className="inline-flex-buttons param-domain-title",
            style={"display": "none"} if is_simulation else {},
        )
        if entry is not None:
            return sim_arch_domain_title(domain_uuid, entry)

        title_content = html.Div([
            html.Div([
                html.H3(
                    "Parameter directory:" if is_simulation else "Parameter domain:",
                    style={"display": "inline-block", "marginBottom": "0px", "marginRight": "10px"},
                ),
                dcc.Input(
                    value=domain_name,
                    type="text",
                    id={"type": "domain-title-input", "domain_uuid": domain_uuid},
                    placeholder="Parameter domain name...",
                    disabled=is_simulation,
                    className="title-input domain",
                    style={
                        "marginBottom": "0",
                        "marginTop": "0",
                        "marginRight": "5px",
                        "verticalAlign": "middle",
                        "position": "relative",
                        "top": "-4px",
                    }
                ),
                ui.icon_button(
                    id={"type": "save-domain-title", "domain_uuid": domain_uuid},
                    icon=icon("check", className="icon invisible"),
                    color="invisible",
                    style={"transform": "translateY(6px)"},
                ),
            ],
            style={
                "justifyContent": "flex-start"
            }),
            buttons,
        ],
        className="title-tile-flex",
        style={
            "display": "flex",
            "alignItems": "center",
            "padding": "0px",
            "justifyContent": "space-between",
        }) 
    return html.Div(
        [title_content],
        id={"type": "param-domain-title", "domain_uuid": domain_uuid}, 
        className="tile title",
        style={"marginTop": "50px"} if domain_uuid != hard_settings.main_parameter_domain else {}
    )

def add_parameter_domain_button(text:str="Main parameter domain"):
    return html.Div(
        [
            html.Div("+", style={"fontSize": "1.5em", "transform": "translateY(-1px)"}),
            html.H3(text, style={"marginBottom": "0px"})
        ], 
        id={"type": "button", "action": "add-domain"}, 
        n_clicks=0,
        className="tile title add hover",
        style={
            "marginTop": "50px",
            "display": "flex",
            "flexDirection": "row",
            "justifyContent": "center",
            "gap": "10px",
        },
    )

#: Whether the substitution a simulation describes for a domain is done instead
#: of the architecture's own, or as well as it.
DOMAIN_COMBINE_OPTIONS = [
    {"label": "Instead of the architecture's", "value": sim_architectures.COMBINE_REPLACE},
    {"label": "As well as the architecture's", "value": sim_architectures.COMBINE_BOTH},
]


def sim_arch_entry_form(domain_uuid, entry):
    """
    What one section of the "?sim=&arch=" page points at: the directory holding
    the configurations of the domain, the file its values fall back to, and
    whether the architecture's own substitution still applies.

    Where those values are written, and with which delimiters, is said under it
    like every other set of configurations says it -- in the "_settings.yml" of
    that directory.
    """
    overrides = entry.get("overrides") or {}
    return html.Div(
        children=[
            ui.subtitle_div(text="Substituted for the architecture"),
            ui.form_dropdown(
                "Rule application",
                {"type": "simarch-combine", "domain_uuid": domain_uuid},
                options=DOMAIN_COMBINE_OPTIONS,
                value=sim_architectures.combine_mode(overrides),
                clearable=False,
                tooltip="Whether the substitution described here replaces the one the architecture "
                        "does for this domain, or is done as well as it, so the domain is written "
                        "in two places.",
            ),
            ui.form_field(
                "Parameter directory",
                {"type": "simarch-param-dir", "domain_uuid": domain_uuid},
                value=str(overrides.get("param_dir", "") or ""),
                placeholder="sim_params/width",
                tooltip="Directory of the simulation holding one configuration per value of the "
                        "domain. Its configurations are the ones edited below, and it says how "
                        "they are written into the sources, like a parameter domain of an "
                        "architecture does.",
            ),
            ui.form_field(
                "Default parameter file",
                {"type": "simarch-param-file", "domain_uuid": domain_uuid},
                value=str(overrides.get("param_file", "") or ""),
                placeholder="sim_params.txt",
                tooltip="File of the simulation holding the values, whichever configuration of "
                        "the domain runs. Given along a parameter directory, it is the default "
                        "the configurations that directory does not describe fall back to. "
                        "Required for a domain the architecture does not define, unless a "
                        "parameter directory is given.",
            ),
            # What the section was opened on: what it points at now is compared
            # to it, and what it holds that this page does not edit is kept.
            dcc.Store(
                id={"type": "simarch-entry-store", "domain_uuid": domain_uuid},
                data={
                    "name": entry.get("name", ""),
                    "overrides": overrides,
                    # Where the section sits in the file. Dash hands the fields
                    # of the page back ordered by component id, which is not the
                    # order the domains are written in.
                    "position": entry.get("position", 0),
                },
            ),
        ],
        className="odx-simarch-entry",
        style={"marginBottom": "18px"},
    )


def config_parameters_form(domain_uuid, settings, mode="arch", domain_name=None, entry=None):
    defval = lambda k, v=None: settings.get(k, v)

    save_button = html.Div(
        children=[
            ui.icon_button(
                icon=icon("save", className="icon", id={"type": "save-params-icon", "domain_uuid": domain_uuid}),
                color="disabled",
                text="Save", 
                width="78px",
                id={"type": "save-params-btn", "domain_uuid": domain_uuid},
            ),
        ],
        style={"marginBottom": "10px"},
        className="inline-flex-buttons",
    )
    use_parameters = defval("use_parameters", True)
    return html.Div(
        children=[
            sim_arch_entry_form(domain_uuid, entry) if entry is not None else html.Div(style={"display": "none"}),
            ui.subtitle_div(text="Configuration Parameters", buttons=save_button),
            dcc.Checklist(
                options=[{"label": "Enable parameter replacement", "value": True}],
                value=[True] if use_parameters else [],
                id={"type": "use_parameters", "domain_uuid": domain_uuid},
                className="checklist-switch",
                style={"marginBottom": "12px", "marginTop": "5px"},
            ),
            html.Div(
                children=[
                    html.Div([
                        html.Label("Param Target File"),
                        ui.tooltip_icon("The file used as the target for parameter replacement. This is typically the top-level design file or a design configuration file."),
                        dcc.Input(id={"type": "param_target_file", "domain_uuid": domain_uuid}, value=defval("param_target_file", ""), type="text", placeholder="Top level file used by default" if mode == "arch" else "", style={"width": "100%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Start Delimiter"),
                        ui.tooltip_icon("The delimiter that marks the beginning of a section to be replaced in the target file. Escape sequences such as \\n are supported."),
                        dcc.Input(id={"type": "start_delimiter", "domain_uuid": domain_uuid}, value=defval("start_delimiter", ""), type="text", style={"width": "100%"}),
                    ], style={"marginBottom": "12px"}),
                    html.Div([
                        html.Label("Stop Delimiter"),
                        ui.tooltip_icon("The delimiter that marks the end of a section to be replaced in the target file. Escape sequences such as \\n are supported."),
                        dcc.Input(id={"type": "stop_delimiter", "domain_uuid": domain_uuid}, value=defval("stop_delimiter", ""), type="text", style={"width": "100%"}),
                    ], style={"marginBottom": "12px"}),
                ],
                id={"type": "params-config-fields", "domain_uuid": domain_uuid}, className="animated-section" if use_parameters else "animated-section hide",
            ),
            html.Div(id={"type": "save-params-status", "domain_uuid": domain_uuid}, className="status", style={"marginLeft": "16px"}),
            # How a configuration is named and what it writes: the other half of
            # the replacement set up above, and the half most domains never have
            # to touch -- so, folded, and here rather than apart.
            config_rules.domain_advanced_section(domain_uuid, settings, domain_name=domain_name),
        ]
    )

def show_newlines(text: str):
    """Render text with a visible '↩' pilcrow before each newline, keeping the actual line break."""
    if "\n" not in text:
        return text
    components = []
    for i, line in enumerate(text.split("\n")):
        if i:
            components.append(html.Span("↩", className="newline-marker"))
            components.append("\n")
        components.append(line)
    return components

def resolve_preview_file(base_path, param_target_file):
    """
    The file a preview reads, among the directories a target file may live in.

    ``base_path`` is one directory, or several of them when the file may come
    from any of them: the first one holding it is the one read, the same way the
    run resolves it, and the first one is what an error message names when none
    does. An entry can also be a ``(directory, prefix)`` pair, for a directory
    that the run copies under ``prefix``: a target file written against the work
    directory names it through that prefix, which is stripped to read the
    sources here.
    """
    bases = [base_path] if isinstance(base_path, str) else list(base_path or [""])
    if not bases:
        bases = [""]
    for base in bases:
        if isinstance(base, tuple):
            base, prefix = base
            prefix = prefix.strip("/") + "/"
            if not param_target_file.replace(os.sep, "/").startswith(prefix):
                continue
            candidate = os.path.join(base, param_target_file.replace(os.sep, "/")[len(prefix):])
        else:
            candidate = os.path.join(base, param_target_file)
        if os.path.isfile(candidate):
            return candidate
    first = bases[0]
    if isinstance(first, tuple):
        first = first[0]
    return os.path.join(first, param_target_file)


def default_param_text(sim_dir, param_file):
    """
    What the "param_file" of a simulation holds, as the values a preview writes.

    A "param_domains" entry names its values two ways: a directory holding one
    configuration per value of the domain, and a file substituted whichever
    configuration runs. Given both, the directory is looked up first and this
    file is what the configurations it does not describe fall back to -- so it
    is what a domain with nothing to select previews.

    Returns:
        str: the content of the file, or None when the entry names none, or
        names one that does not exist.
    """
    param_file = str(param_file or "").strip()
    if not param_file:
        return None
    path = os.path.join(sim_dir or "", param_file)
    if not os.path.isfile(path):
        return None
    return replace_params.read_file(path)


def preview_pane(domain_uuid:str, mode: str, settings: dict, domain_settings: dict, replacement_text: str, base_path=None):
    """
    What the target file looks like once the selected configuration is written
    into it. ``base_path`` says where that file is looked up, for the pages that
    know it without reading the instance settings -- a simulation writes into
    its own sources, as well as into the RTL of the architecture it runs on,
    hence several directories.
    """
    # Where a simulation writes its parameters is said per architecture: opened
    # on the whole simulation, there is no single file to preview here.
    if mode == "simulation" and base_path is None:
        return None
    use_parameters = domain_settings.get("use_parameters", True)
    if not use_parameters:
        return html.Div("Parameter replacement disabled.", style={"color": "#888"})
    param_target_file = domain_settings.get("param_target_file", "")

    if base_path is not None:
        if not param_target_file:
            return html.Div(
                "No target file: say which file of the simulation the values of this domain are "
                "written into.",
                className="error warning",
            )
    elif mode == "workflow":
        sources = settings.get("sources", {})
        base_path = sources.get("path", "") if isinstance(sources, dict) else ""
        if not base_path:
            return html.Div("No source path specified in workflow settings. Unable to preview.", className="error")
        if param_target_file == "":
            param_target_file = settings.get("param_target_file", "")
    else:
        generate_rtl = settings.get("generate_rtl", False)
        generate_rtl = True if generate_rtl else False # Convert from [True]/[] to True/False
        if generate_rtl:
            base_path = settings.get("design_path", "")
            if not base_path:
                return html.Div("No design path specified in architecture settings. Unable to preview.", className="error")
            if param_target_file == "":
                param_target_file = settings.get("top_level_file", "")
        else:
            rtl_path = settings.get("rtl_path", "")
            if not rtl_path:
                return html.Div("No RTL path specified in architecture settings. Unable to preview.", className="error")
            base_path = rtl_path
            if param_target_file == "":
                param_target_file = os.path.join(settings.get("top_level_file", ""))
    param_target_file = resolve_preview_file(base_path, param_target_file)
    if os.path.isfile(param_target_file):
        base_text = replace_params.read_file(param_target_file)
        start_delimiter = domain_settings.get("start_delimiter", "")
        stop_delimiter = domain_settings.get("stop_delimiter", "")
        new_content, match_found = replace_params.replace_content(
            base_text=base_text,
            replacement_text=replacement_text,
            start_delim=start_delimiter, 
            stop_delim=stop_delimiter, 
            replace_all_occurrences=False,
        )
        start_delimiter = replace_params.unescape_delimiter(start_delimiter)
        stop_delimiter = replace_params.unescape_delimiter(stop_delimiter)
        if not match_found:
            preview_components=html.Span(base_text, style={"whiteSpace": "pre-wrap", "color": "#FA5252", "fontWeight": "800"})
        else:
            # Highlight the replaced section by character index, so delimiters may span several lines
            pattern = re.escape(start_delimiter) + ".*?" + re.escape(stop_delimiter)
            match = re.search(pattern, new_content, flags=re.DOTALL)
            section_start = match.start()
            section_stop = match.end()
            content_start = section_start + len(start_delimiter)
            content_stop = section_stop - len(stop_delimiter)
            preview_components = [
                new_content[:section_start],
                html.Span(show_newlines(start_delimiter), className="text-highlight primary"),
                html.Span(new_content[content_start:content_stop], className="text-highlight secondary"),
                html.Span(show_newlines(stop_delimiter), className="text-highlight primary"),
                new_content[section_stop:],
            ]

        pane_content = html.Pre(
            children=preview_components,
            id={"type": "preview-pre", "domain_uuid": domain_uuid},
            className="preview-pane",
            style={
                "fontFamily": "monospace",
                "fontWeight": "normal",
                "padding": "5px",
                "whiteSpace": "pre-wrap",
                "box-sizing": "border-box",
            }
        )
    else:
        if not base_path or param_target_file == "":
            label = instance_label(mode).lower()
            text = f"Invalid {label} settings. Unable to preview."
        elif settings == {}:
            text = f"No settings found."
        else:
            text = f"Preview file '{os.path.realpath(param_target_file)}' not found. Unable to preview."
        pane_content = html.Div(text, className="error")
    return pane_content

def preview_header(domain_uuid):
    """Header of the preview tile: title + config selector."""
    return html.Div(
        children=[
            html.H3("Preview Pane", style={"margin": "0px"}),
            dcc.Dropdown(
                id={"type": "preview-config-select", "domain_uuid": domain_uuid},
                options=[],
                value=None,
                clearable=False,
                placeholder="No config",
                style={"minWidth": "180px", "flex": "0 1 240px"},
            ),
        ],
        style={
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "space-between",
            "gap": "10px",
            "marginBottom": "8px",
        },
    )

def domain_section(domain: str, mode: str = "arch", instance_name: str = "", settings: dict = {}, domain_uuid=None, open_rules: bool = False, entry=None):
    # Generate a unique UUID for non-main domains
    if not domain_uuid:
        domain_uuid = get_uuid() if domain != hard_settings.main_parameter_domain else domain
    
    # Hidden divs for better animations
    hidden_count = random.randint(4, 7)
    title_hidden_divs = [html.Div(style={"display": "none"}) for _ in range(hidden_count)]
    hidden_count = random.randint(8, 12)
    content_hidden_divs = [html.Div(style={"display": "none"}) for _ in range(hidden_count)]
    
    # Domain Section
    return html.Div(
        children=[
            html.Div(
                children=[
                    *title_hidden_divs,
                    parameter_domain_title(domain_name=domain, domain_uuid=domain_uuid, mode=mode, instance_name=instance_name, entry=entry)
                ], 
                id=f"param-domain-title-div-{domain_uuid}",
                className="card-matrix config",
            ),
            html.Div(
                children=[
                    *content_hidden_divs,
                    html.Div(
                        children=[
                            config_parameters_form(domain_uuid, settings, mode, domain_name=domain, entry=entry),
                        ],
                        id={"type": "config-parameters", "domain_uuid": domain_uuid}, 
                        className="tile config"),
                    html.Div(
                        children=[
                            preview_header(domain_uuid),
                            html.Div(
                                id={"type": "preview-pane", "domain_uuid": domain_uuid},
                                className="preview-pane-container",
                            ),
                        ],
                        className="tile config preview-tile",
                    ),
                ], 
                className="card-matrix config",
                # A simulation says where its parameters go, and with which
                # delimiters, in its own settings: one entry per architecture,
                # so neither the form nor the preview means anything here. They
                # are still built, hidden, so that every callback keeps seeing
                # one of each per domain.
                style={"display": "none"} if (mode == "simulation" and entry is None) else {},
            ),
            html.Div(
                config_rules.rules_section(domain_uuid, settings, open=open_rules, domain_name=domain),
                style={"display": "none"} if (entry is not None and not domain) else {},
            ),
            # Which origins the stat strip of this domain currently filters out.
            # Only the browser reads it: hiding a card is a matter of style, and
            # nothing of the domain itself changes.
            dcc.Store(id={"type": "config-filter-state", "domain_uuid": domain_uuid}, data=[]),
            html.Div(
                id={"type": "config-counters", "domain_uuid": domain_uuid},
                # Centered over the cards it counts, like everything else of the
                # list: the rules preview heads the same column.
                style={"display": "flex", "flexWrap": "wrap", "justifyContent": "center",
                       "gap": "12px", "margin": "16px 5px 10px 5px"},
            ),
            # What the rules of this domain would produce, shown above its
            # configurations while they are edited and not saved yet.
            html.Div(id={"type": "cfg-config-preview", "domain_uuid": domain_uuid}),
            # Kept in the same wrapper as the cards it introduces: the rules
            # preview hides that whole wrapper while it stands in for it (see
            # ".odx-configs-diff" in the stylesheet).
            # A section pointing at no directory of configurations has none to
            # show: what it substitutes is one file, said above.
            html.Div([
                html.Div(
                    children=[add_card(domain_uuid=domain_uuid)],
                    id={"type": "config-cards-row", "domain_uuid": domain_uuid},
                    className=f"card-matrix configs",
                ),
            ], style={"display": "none"} if (entry is not None and not domain) else {}),
            dcc.Store(id={"type": "config-params-store", "domain_uuid": domain_uuid}, data=settings),
            # "domain_name" is what the configurations are held in -- a domain
            # of the instance, or the directory a simulation points at, which is
            # what every callback resolves a file through. A simulation section
            # also carries the domain of the architecture it substitutes, which
            # is what its settings file names it by.
            dcc.Store(
                id={"type": "domain-metadata", "domain_uuid": domain_uuid},
                data={
                    "domain_name": domain,
                    "domain_uuid": domain_uuid,
                    "entry_domain": (entry or {}).get("name", ""),
                },
            ),
        ],
        id = {"type": "param-domain-section", "domain_uuid": domain_uuid},
        # The highlighter of the two templates looks for the variables of this
        # domain, and of this domain only: a ${name} defined next door is not
        # defined here. The whole section is the scope, since the templates and
        # the variables they read now sit in two different places of it.
        **{
            "data-odatix-hl-scope": domain_uuid,
            "data-odatix-hl-unknown": "no variable of this domain is named like this",
        },
    )


def instance_domain(instances, instance_name, domain_name):
    """
    One parameter domain of the architecture or workflow being edited, or the
    directory of configurations a simulation points at.

    None when there is no such directory: a simulation may substitute one file
    whichever configuration runs, and there is then nothing holding
    configurations -- writing into the instance itself is what an empty name
    would otherwise mean.
    """
    if not domain_name:
        return None
    return ParameterDomain(instances.entry(instance_name), domain_name)


######################################
# What a simulation substitutes for one architecture
######################################

#: The fields of a "?sim=&arch=" section that point at what is substituted, as
#: the callbacks saving them read them.
SIM_ARCH_STATES = [
    State({"type": "simarch-domain", "domain_uuid": dash.ALL}, "value"),
    State({"type": "simarch-combine", "domain_uuid": dash.ALL}, "value"),
    State({"type": "simarch-param-file", "domain_uuid": dash.ALL}, "value"),
    State({"type": "simarch-param-dir", "domain_uuid": dash.ALL}, "value"),
    State({"type": "simarch-entry-store", "domain_uuid": dash.ALL}, "data"),
]


def sim_arch_values(entry_names, combines, param_files, param_dirs, stores, index):
    """What one section of the "?sim=&arch=" page currently points at."""
    def at(values, default=""):
        return values[index] if index < len(values) and values[index] is not None else default
    return {
        "name": str(at(entry_names)).strip(),
        "combine": at(combines, sim_architectures.COMBINE_REPLACE),
        "param_file": str(at(param_files)).strip(),
        "param_dir": str(at(param_dirs)).strip(),
        "store": at(stores, {}) or {},
    }


def sim_arch_param_dir(entry_names, param_dirs, index, metadata):
    """
    The directory a section holds its configurations in: what its field says,
    which is where a save writes even when the field was just changed. Empty
    when the section is not one of a "?sim=&arch=" page, or points at no
    directory.
    """
    if index >= len(entry_names):
        return metadata.get("domain_name", "")
    return str(param_dirs[index] if index < len(param_dirs) and param_dirs[index] else "").strip()


def save_sim_arch_entries(
    search, odatix_settings, domain_metadata,
    entry_names, combines, param_files, param_dirs, stores, substitutions=None,
):
    """
    Write back what every section of a "?sim=&arch=" page points at, in one go:
    the "param_domains" of that architecture entry are one mapping, so they are
    written from the whole page rather than one section at a time.

    Returns ``(reload, stores)``: whether a section now points somewhere else --
    which the sections have to be built again from -- and what each of them
    holds once saved.
    """
    if not entry_names:
        return False, []
    simulation, _arch, entries, position = sim_arch_context(search, odatix_settings)
    if simulation is None or position is None:
        return False, []

    substitutions = substitutions or {}
    reload_needed = False
    saved = {}
    for index in range(len(domain_metadata)):
        values = sim_arch_values(entry_names, combines, param_files, param_dirs, stores, index)
        store = values["store"]
        previous = store.get("overrides") or {}
        overrides = sim_domains.entry_overrides(
            dict(values, **(substitutions.get(index) or {})), previous,
        )
        saved[index] = (values["name"], overrides)
        if values["name"] != str(store.get("name", "")):
            reload_needed = True
        if overrides.get("param_dir", "") != str(previous.get("param_dir", "") or ""):
            reload_needed = True

    # Written in the order the sections are shown, which is the order the file
    # holds them in: dash hands them back ordered by component id instead.
    order = sorted(
        saved,
        key=lambda index: (stores[index] or {}).get("position", index)
        if index < len(stores) and stores[index] else index,
    )
    positions = {index: place for place, index in enumerate(order)}
    sim_domains.save_param_domains(simulation, position, [saved[index] for index in order])
    return reload_needed, [
        {
            "name": saved[index][0],
            "overrides": saved[index][1],
            "position": positions[index],
        }
        for index in range(len(domain_metadata))
    ]


def origin_of(domain, filename):
    """
    What the given configuration is, once the domain has been written to: a
    file the rules know nothing about, one they produce, or one they produce
    and that was edited since.
    """
    for config in domain.resolve_configurations():
        if config.filename == filename:
            return config.origin
    return ORIGIN_MANUAL


def domain_configurations(domain):
    """
    Everything one parameter domain holds, in the order its cards are shown:
    what it resolves to plus what its rules produce and the blacklist keeps out.
    """
    configurations = list(domain.resolve_configurations()) + list(domain.blacklisted_configurations())
    return natsorted(configurations, key=lambda configuration: configuration.name)


def show_more_class(config_layout, hidden):
    """The classes of the show more card, which says by itself whether anything
    is still hidden: the layout switch below rewrites this same string."""
    classes = ["card", "configs", "add", "hover", "odx-show-more"]
    if config_layout == "wide":
        classes.append("wide")
    if hidden <= 0:
        classes.append("odx-hidden")
    return " ".join(classes)


def show_more_label(hidden):
    """What the show more card offers, or nothing when the domain is all there."""
    return f"Show {min(configs_per_page, hidden)} more" if hidden > 0 else ""


def show_more_count(hidden):
    """How much of the domain the show more card is standing in for."""
    return f"{hidden} more configuration{'s' if hidden != 1 else ''}" if hidden > 0 else ""


def show_more_card(domain_uuid, config_layout, hidden):
    """
    The card that ends a shortened list of configurations. It holds how many
    have no card, and nothing else: a click reads them from the domain again
    rather than keeping them in the browser for a list nobody may open.
    """
    return html.Div(
        [
            html.Div(
                [
                    html.Div("⋯", className="odx-show-more-glyph"),
                    html.Div(
                        show_more_label(hidden),
                        id={"type": "show-more-label", "domain_uuid": domain_uuid},
                        className="odx-show-more-label",
                    ),
                    html.Div(
                        show_more_count(hidden),
                        id={"type": "show-more-count", "domain_uuid": domain_uuid},
                        className="odx-show-more-count",
                    ),
                ],
                id={"type": "show-more-configs", "domain_uuid": domain_uuid},
                n_clicks=0,
                className="odx-show-more-button",
            ),
            # How many configurations of this domain have no card. Adding or
            # deleting one moves the shown count and the total together, so this
            # only changes when more are revealed, or when the row is built again.
            dcc.Store(
                id={"type": "config-hidden", "domain_uuid": domain_uuid},
                data=hidden,
            ),
        ],
        className=show_more_class(config_layout, hidden),
        id={"type": "show-more-card", "domain_uuid": domain_uuid},
    )


def cards_shown(config_metadata, domain_uuid):
    """
    How many configurations of a domain have a card right now. Rebuilding a row
    keeps that many rather than folding it back to the first page: what was
    revealed was asked for.
    """
    return max(
        configs_per_page,
        sum(1 for data in (config_metadata or []) if (data or {}).get("domain_uuid", "") == domain_uuid),
    )


def insert_config_card(cards, card):
    """
    Add one card to a row, before the cards that close it. The show more and add
    cards always sit last, and a new configuration belongs with the others.
    """
    for i, existing in enumerate(cards):
        card_id = existing.get("props", {}).get("id") if isinstance(existing, dict) else getattr(existing, "id", None)
        if isinstance(card_id, dict) and card_id.get("type") in ("show-more-card", "add-config-card"):
            cards.insert(i, card)
            return
    cards.insert(max(len(cards) - 1, 0), card)


def build_config_cards(domain, domain_uuid, config_layout, shown=None):
    """
    The cards of one parameter domain: what it holds, whether it is written as
    a file or only described by the rules of the domain, plus the show more and
    add cards. Only the first `shown` configurations get a card -- the rest are
    counted, and read again when the show more card is clicked.
    """
    if domain is None:
        # A section holding no configurations still has a row: every callback
        # keyed on a domain expects to find one.
        return [add_card(domain_uuid=domain_uuid)]
    configurations = domain_configurations(domain)
    if shown is None:
        shown = configs_per_page
    shown = min(max(shown, 0), len(configurations))
    cards = []
    for config in configurations[:shown]:
        cards.append(
            config_card(
                domain_uuid=domain_uuid,
                config_uuid=get_uuid(),
                config_name=config.filename,
                content=config.content,
                initial_content=config.content,
                config_layout=config_layout,
                origin=config.origin,
            )
        )
    cards.append(show_more_card(domain_uuid, config_layout, len(configurations) - shown))
    cards.append(add_card(domain_uuid=domain_uuid))
    return cards


def rules_of(domain):
    """The configurations the rules of a domain produce, by filename."""
    if not domain.describes_configurations:
        return {}
    return {config.filename: config for config in domain.resolve_configurations() if config.from_rules}


def unsaved_rule_configurations(names, templates, stores, field_values, domain_metadata, only=None):
    """
    Generated configurations currently described by unsaved rule fields.
    `only` restricts the work to a set of domain uuids: expanding a rule space
    is the expensive half of a preview, and a domain whose pane is not being
    rebuilt has no use for it.
    """
    domain_metadata = domain_metadata or []
    uuids = config_rules.domain_uuids_of(domain_metadata)
    indices = config_rules.domain_indices(config_rules.field_ids("variable-title"), uuids)
    names_by_uuid = config_rules.domain_names_of(domain_metadata)
    stores = stores or []
    configurations_by_domain = {}

    for i, domain_uuid in enumerate(uuids):
        if only is not None and domain_uuid not in only:
            continue
        variables = config_rules.variables_of(field_values, indices.get(domain_uuid, []))
        name = names[i] if i < len(names) else ""
        template = templates[i] if i < len(templates) else ""
        saved = stores[i] if i < len(stores) and stores[i] else config_rules.rules_settings("", "", {})
        current = config_rules.form_rules_settings(
            name, template, variables, names_by_uuid.get(domain_uuid), saved,
        )
        if current == saved:
            continue

        space = config_rules.effective_rules(
            name, template, variables,
            blacklist=config_rules.configuration_blacklist(saved),
        )
        if not space.generates:
            continue
        try:
            configurations = {point.name: point.content for point in space.points()}
        except Exception:
            continue
        configurations_by_domain[domain_uuid] = configurations

    return configurations_by_domain


def replacement_text_for_preview(selected_config, domain_uuid, domain_contents, config_metadata, rule_configurations):
    """The selected configuration text, preferring an unsaved generated value."""
    selected_metadata = next(
        (
            data for data in (config_metadata or [])
            if (data or {}).get("domain_uuid") == domain_uuid
            and (data or {}).get("config_uuid") == selected_config
        ),
        None,
    )
    if selected_metadata:
        config_name = selected_metadata.get("config_name", "")
        name = config_name[:-4] if config_name.endswith(".txt") else config_name
        origin = selected_metadata.get("origin", ORIGIN_MANUAL)
        if origin == ORIGIN_GENERATED and name in rule_configurations:
            return rule_configurations[name]
        if origin in (ORIGIN_MANUAL, ORIGIN_EDITED, ORIGIN_BLACKLISTED):
            return domain_contents.get(selected_config, next(iter(domain_contents.values()), ""))

    if rule_configurations:
        return next(iter(rule_configurations.values()), "")
    if selected_config in domain_contents:
        return domain_contents[selected_config]
    return next(iter(domain_contents.values()), "")


def preview_domains_to_refresh(debounce):
    """
    The domains whose preview the current trigger made stale, or None when every
    pane has to be built again. A preview costs a file read and a substitution
    over it, so a keystroke in one domain does not pay for all the others.
    """
    try:
        triggered = ctx.triggered_prop_ids or {}
    except MissingCallbackContextException:
        # Called outside a callback: nothing says what changed, so nothing is
        # spared.
        return None
    if not triggered:
        return None
    stale = set()
    for identifier in triggered.values():
        if identifier == "config-content-debounce":
            domains = (debounce or {}).get("domains")
            if domains is None:
                return None
            stale.update(domains)
        elif isinstance(identifier, dict) and identifier.get("domain_uuid"):
            stale.add(identifier["domain_uuid"])
        else:
            # Something that is not tied to one domain: rebuild every pane.
            return None
    return stale


######################################
# Callbacks
######################################

# Typing must not reach the server: a preview reads a file and substitutes over
# it, per domain. This holds the keystrokes on the client and, once they stop,
# hands the preview the domains that actually changed.
dash.clientside_callback(
    """
    function(_contents) {
        const state = window.__odatixPreviewDebounce = window.__odatixPreviewDebounce
            || {domains: {}, all: false, timer: null};
        const context = window.dash_clientside.callback_context;
        (context.triggered || []).forEach(function(trigger) {
            const raw = trigger.prop_id || "";
            const cut = raw.lastIndexOf(".");
            let id = null;
            if (cut > 0) {
                try { id = JSON.parse(raw.slice(0, cut)); } catch (error) { id = null; }
            }
            if (id && id.domain_uuid) {
                state.domains[id.domain_uuid] = true;
            } else {
                state.all = true;
            }
        });
        if (state.timer) {
            clearTimeout(state.timer);
        }
        state.timer = setTimeout(function() {
            const payload = {
                stamp: Date.now(),
                domains: state.all ? null : Object.keys(state.domains),
            };
            state.domains = {};
            state.all = false;
            state.timer = null;
            window.dash_clientside.set_props("config-content-debounce", {data: payload});
        }, 400);
        return window.dash_clientside.no_update;
    }
    """,
    Output("config-content-debounce", "data"),
    Input({"type": "config-content", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "value"),
    prevent_initial_call=True,
)

@dash.callback(
    Output(f"param-domain-title-div-{hard_settings.main_parameter_domain}", "children"),
    Input("param-domains-section", "children"),
    State("url", "search"),
    preview_initial_call=True
)
def update_main_domain_title(_, search):
    mode, instance_name = get_instance_mode(search)
    if not instance_name:
        return no_instance_message(mode)
    return parameter_domain_title(domain_uuid=hard_settings.main_parameter_domain, mode=mode, instance_name=instance_name)

def sim_arch_error(text, hints=None):
    """One section standing in for the whole page when the URL names nothing editable."""
    return [
        main_domain_placeholder(),
        html.Div(
            html.Div(
                [html.Div(text)] + [html.Div(hint) for hint in (hints or [])],
                className="error warning",
            ),
            className="card-matrix config",
        ),
    ], True, dash.no_update


def sim_arch_sections(search, odatix_settings, triggered_id, metadata, requested_domain):
    """
    The sections of the "?sim=&arch=" page: one per parameter domain this
    simulation substitutes its own way for that architecture.

    A domain added or removed is a change of the simulation's settings, written
    before the page is built again: the sections themselves hold what the
    directories say, and are read from them.
    """
    simulation, arch, entries, position = sim_arch_context(search, odatix_settings)
    if simulation is None:
        return sim_arch_error("No such simulation.")
    if position is None:
        return sim_arch_error(
            'This simulation does not list the architecture "' + str(arch) + '".',
            ['Add it under "Architectures" in the simulation settings, then come back here.'],
        )

    architectures = get_workspace(odatix_settings).architectures
    domains = sim_domains.param_domains_of(entries[position])

    # A domain added or removed: write it, then show what the file now holds.
    # A click is only an action once the button has been clicked: a value of 0 is
    # a button that was just rendered.
    action = triggered_id.get("action", "") if isinstance(triggered_id, dict) else ""
    try:
        clicked = bool(ctx.triggered[0]["value"]) if ctx.triggered else False
    except MissingCallbackContextException:
        # Called outside a callback: what it was given is what it acts on.
        clicked = True
    if not clicked:
        action = ""
    if action == "add-domain":
        name = sim_domains.new_domain_name(
            architectures, entries[position].name, [domain for domain, _ in domains]
        )
        domains.append((name, {}))
        sim_domains.save_param_domains(simulation, position, domains)
    elif action == "delete-domain":
        deleted_uuid = triggered_id.get("domain_uuid", "")
        deleted = next(
            (data.get("entry_domain", "") for data in metadata or []
             if data.get("domain_uuid", "") == deleted_uuid),
            None,
        )
        if deleted is None:
            return dash.no_update, dash.no_update, dash.no_update
        domains = [(name, overrides) for name, overrides in domains if name != deleted]
        sim_domains.save_param_domains(simulation, position, domains)

    sections = [main_domain_placeholder()]
    for position_index, (name, overrides) in enumerate(domains):
        param_dir = str(overrides.get("param_dir", "") or "").strip()
        sections.append(domain_section(
            param_dir, "simulation", simulation.name,
            settings=sim_domains.domain_settings(simulation, overrides),
            open_rules=bool(param_dir) and param_dir == requested_domain,
            entry={
                "name": name,
                "overrides": overrides,
                "position": position_index,
                "options": sim_domains.domain_options(architectures, entries[position].name, name),
            },
        ))
    if not domains:
        sections.append(html.Div(
            html.Div([
                html.Div("This simulation substitutes nothing of its own for this architecture."),
                html.Div(
                    "Every parameter domain of the architecture is substituted the way the "
                    "architecture declares it. Add one to write its values somewhere else, to "
                    "leave them out, or to take them from configurations of the simulation."
                ),
            ], className="error warning"),
            className="card-matrix config",
        ))
    sections.append(html.Div(
        children=[add_parameter_domain_button("Add a parameter domain to substitute")],
        className="card-matrix config",
    ))
    return sections, True, dash.no_update


@dash.callback(
    Output("param-domains-section", "children"),
    Output("param-domains-section-initialized", "data"),
    Output("param-domains-section-update", "data"),
    Input({"page": page_path, "type": "instance-title-div"}, "children"), # Trigger when title is loaded
    State("url", "search"),
    State("url", "pathname"),
    Input({"action": "add-domain", "type": dash.ALL}, "n_clicks"),
    Input({"action": "duplicate-domain", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"action": "delete-domain", "domain_uuid": dash.ALL}, "n_clicks"),
    Input("sim-arch-reload", "data"),
    State("odatix-settings", "data"),
    State("param-domains-section", "children"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State("param-domains-section-update", "data"),
    prevent_initial_call=True
)
def update_param_domains(
    _, search, page, add_domain_click, duplicate_domain_click, delete_domain_click, sim_arch_reload,
    odatix_settings, domain_sections, metadata, update_flag
):
    triggered_id = ctx.triggered_id
    if triggered_id == "url":
        if page != page_path:
            return dash.no_update, dash.no_update, dash.no_update

    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    if not instance_name:
        return html.Div(
            children=[
                html.Div(no_instance_message(mode), className="error")
            ],
            className="card-matrix config",
        ), dash.no_update, dash.no_update

    requested_domain = get_key_from_url(search, "domain")

    add_domain_div = html.Div(
        children=[
            add_parameter_domain_button("Add new parameter domain")
        ],
        className="card-matrix config",
    )

    # Opened on one architecture, the page shows what the simulation substitutes
    # for it: one section per parameter domain it overrides, holding what points
    # at the configurations, how they are written, and the configurations
    # themselves.
    if mode == "simulation" and get_key_from_url(search, "arch"):
        return sim_arch_sections(search, odatix_settings, triggered_id, metadata, requested_domain)

    # The domains of a simulation are the "param_dir" directories its settings
    # point at: they are added, named and removed there, and only their
    # configurations are edited here.
    if mode == "simulation":
        if instance_name not in instances:
            return [
                main_domain_placeholder(),
                html.Div(
                    html.Div("No such simulation: " + instance_name, className="error"),
                    className="card-matrix config",
                ),
            ], True, dash.no_update
        if triggered_id != {"page": page_path, "type": "instance-title-div"}:
            return dash.no_update, dash.no_update, dash.no_update
        simulation = instances[instance_name]
        domain_sections = [main_domain_placeholder()]
        for domain in simulation.domains:
            domain_sections.append(
                domain_section(
                    domain.name, mode, instance_name, settings=domain.settings.to_dict(),
                    open_rules=(domain.name == requested_domain),
                )
            )
        if len(domain_sections) == 1:
            domain_sections.append(html.Div(
                html.Div([
                    html.Div("This simulation has no parameter directory."),
                    html.Div(
                        "Give a domain a \"parameter directory\" in the simulation settings to "
                        "run one configuration per value of that domain."
                    ),
                ], className="error warning"),
                className="card-matrix config",
            ))
        return domain_sections, True, dash.no_update

    if instance_name not in instances:
        domain_sections = []
        domain_sections.append(domain_section(hard_settings.main_parameter_domain, mode, instance_name, settings={}))
        domain_sections.append(add_domain_div)
        return domain_sections, dash.no_update, dash.no_update

    instance = instances[instance_name]
    domains = instance.domains.sub_names()

    # Generate domain sections
    if triggered_id == {"page": page_path, "type": "instance-title-div"}:
        domain_sections = []
        for domain in instance.domains:
            domain_sections.append(
                domain_section(
                    domain.name, mode, instance_name, settings=domain.settings.to_dict(),
                    # A link naming a domain -- the old configuration generator
                    # URL, among others -- opens the rules of that domain.
                    open_rules=(domain.name == requested_domain),
                )
            )
        domain_sections.append(add_domain_div)
        return domain_sections, True, dash.no_update

    elif isinstance(triggered_id, dict):
        trigger_action = triggered_id.get("action", "")
        # Add a new domain
        if trigger_action == "add-domain":
            base_name = "new_domain"
            suffix = 1
            new_domain = f"{base_name}{suffix}"
            while new_domain in domains:
                suffix += 1
                new_domain = f"{base_name}{suffix}"
            # A new domain starts with one variable, named after itself: that is
            # the shortest thing it can be, and it needs no template to say what
            # its configurations are called or contain.
            new_settings = {"variables": config_rules.default_variables()}
            instance.domains.create(new_domain, **new_settings)

            # Insert new domain section before the add domain button
            domain_sections = domain_sections[:-1] if isinstance(domain_sections, list) else []
            domain_uuid = get_uuid()
            domain_sections.append(
                domain_section(
                    new_domain, mode, instance_name, settings=new_settings,
                    domain_uuid=domain_uuid, open_rules=True,
                )
            )
            domain_sections.append(add_domain_div)
            # Its one variable already describes configurations, so the new
            # domain holds some the moment it exists: its cards are read.
            return domain_sections, dash.no_update, domain_uuid

        # Duplicate domain
        elif trigger_action == "duplicate-domain":
            domain_to_duplicate_uuid  = triggered_id.get("domain_uuid", "")

            # Check if button was actually clicked
            domain_to_duplicate = None
            domain_to_duplicate_idx = None
            for i, data in enumerate(metadata):
                domain_uuid = data.get("domain_uuid", "")
                domain_name = data.get("domain_name", "")
                if domain_uuid == domain_to_duplicate_uuid:
                    domain_to_duplicate = domain_name
                    domain_to_duplicate_idx = i - 1 # -1 to account for main domain
                    break

            if domain_to_duplicate_uuid :
                if domain_to_duplicate_uuid  == hard_settings.main_parameter_domain:
                    base_name = "main_copy"
                else:
                    base_name = f"{domain_to_duplicate}_copy"
                suffix = 1
                new_domain = f"{base_name}{suffix}"
                while new_domain in domains:
                    suffix += 1
                    new_domain = f"{base_name}{suffix}"
                instance.domains.duplicate(domain_to_duplicate, new_domain)

                # Insert new domain section before the add domain button
                domain_sections = domain_sections[:-1] if isinstance(domain_sections, list) else []
                new_domain_settings = instance.domains[new_domain].settings.to_dict()
                domain_uuid = get_uuid()
                domain_sections.append(domain_section(new_domain, mode, instance_name, settings=new_domain_settings, domain_uuid=domain_uuid))
                domain_sections.append(add_domain_div)
                return domain_sections, dash.no_update, domain_uuid

        # Delete domain
        elif trigger_action == "delete-domain":
            domain_to_delete_uuid = triggered_id.get("domain_uuid", "")

            # Check if button was actually clicked
            domain_to_delete = None
            domain_to_delete_idx = None
            for i, data in enumerate(metadata):
                domain_uuid = data.get("domain_uuid", "")
                domain_name = data.get("domain_name", "")
                if domain_uuid == domain_to_delete_uuid:
                    domain_to_delete = domain_name
                    domain_to_delete_idx = i - 1 # -1 to account for main domain
                    break
            if domain_to_delete_idx and delete_domain_click[domain_to_delete_idx] == 0:
                return dash.no_update, dash.no_update, dash.no_update

            if domain_to_delete and domain_to_delete != hard_settings.main_parameter_domain:
                instance.domains.delete(domain_to_delete)
                if isinstance(domain_sections, list):
                    for i, section in enumerate(domain_sections):
                        domain = section.get("props", {}).get("id", {}).get("domain_uuid", "")
                        if domain == domain_to_delete_uuid:
                            domain_sections.pop(i)
                            return domain_sections, dash.no_update, dash.no_update

    return dash.no_update, dash.no_update, dash.no_update

@dash.callback(
    Output({"type": "config-cards-row", "domain_uuid": dash.ALL}, "children"),
    State("url", "search"),
    Input("param-domains-section-initialized", "data"),
    Input("config-layout-dropdown", "value"),
    Input({"type": "new-config", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "save-config", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "delete-config", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "duplicate-config", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "cfg-rules-saved", "domain_uuid": dash.ALL}, "data"),
    Input("param-domains-section-update", "data"),
    State({"type": "config-cards-row", "domain_uuid": dash.ALL}, "children"),
    State({"type": "config-title", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "value"),
    State({"type": "config-content", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "value"),
    State({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def update_config_cards(
    search, _,
    config_layout, add_click, save_clicks, delete_clicks, duplicate_clicks, rules_saved, update_domain_uuid,
    config_cards_row, title_values, contents, config_metadata, domain_metadata, odatix_settings
):
    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    if not instance_name:
        return [html.Div(no_instance_message(mode), className="error")]

    triggered_id = ctx.triggered_id
    # A blacklist toggle answers the very click this callback answers. Dash holds
    # this one back until the toggle has saved the domain, then runs it with both
    # the click and the saved signal at once -- and names the click as the
    # trigger, which is the one branch below that has nothing to do. The saved
    # signal is what actually says the domain changed, so it wins over the click.
    rules_saved_trigger = next(
        (
            identifier for identifier in (ctx.triggered_prop_ids or {}).values()
            if isinstance(identifier, dict) and identifier.get("type") == "cfg-rules-saved"
        ),
        None,
    )
    if rules_saved_trigger is not None:
        triggered_id = rules_saved_trigger

    # Which rows this call rewrites. Every other one is answered with no_update:
    # a row is the whole card tree of a domain, and sending back the rows an
    # action did not touch makes adding one configuration cost as much as the
    # page holds.
    changed_rows = set()

    if not isinstance(triggered_id, dict):
        domains = {}
        for data in domain_metadata:
            domain_name = data.get("domain_name", "")
            domain_uuid = data.get("domain_uuid", "")
            domains[domain_uuid] = domain_name
    else:
        domains = {}
        trig_type = triggered_id.get("type", None)
        trig_domain_uuid = triggered_id.get("domain_uuid", hard_settings.main_parameter_domain)
        trig_domain_name = ""

        # Get domain from metadata
        trig_domain_idx = -1
        for i, data in enumerate(domain_metadata):
            domain_name = data.get("domain_name", "")
            domain_uuid = data.get("domain_uuid", "")
            domains[domain_uuid] = domain_name
            if domain_uuid == trig_domain_uuid:
                trig_domain_name = domain_name
                trig_domain_idx = i

        # The rules of a domain were saved: what the domain holds has changed,
        # so its cards are read again -- which is the whole point of editing
        # the rules next to the configurations they produce.
        if trig_type == "cfg-rules-saved" and trig_domain_idx >= 0:
            cards = build_config_cards(
                instance_domain(instances, instance_name, trig_domain_name), trig_domain_uuid, config_layout,
                shown=cards_shown(config_metadata, trig_domain_uuid),
            )
            # Only the domain whose rules changed is read again: what is being
            # edited in the other domains stays as the user left it.
            return [cards if i == trig_domain_idx else dash.no_update for i in range(len(config_cards_row))]

        # A section holding no directory of configurations shows none, so none
        # of the actions below can have come from it.
        if trig_type in ["new-config", "save-config", "delete-config", "duplicate-config"] and not trig_domain_name:
            return [dash.no_update for _ in range(len(config_cards_row))]

        if trig_type in ["new-config", "save-config", "delete-config", "duplicate-config"]:
            # Every branch below rewrites this one row, and only this one.
            changed_rows.add(trig_domain_idx)
            trig_domain_configs = []
            trig_config_uuid = triggered_id.get("config_uuid", "")
            trig_config_name = ""
            trig_config_initial_content = ""
            trig_config_origin = ORIGIN_MANUAL
            
            # Get config from metadata
            trig_global_idx = -1
            trig_config_idx = -1
            domain_config_idx = -1
            for i, data in enumerate(config_metadata):
                domain_uuid = data.get("domain_uuid", "")
                if domain_uuid == trig_domain_uuid:
                    domain_config_idx += 1
                    config_name = data.get("config_name", "")
                    config_uuid = data.get("config_uuid", "")
                    config_content = data.get("config_content", "")
                    trig_domain_configs.append(config_name)
                    if config_uuid == trig_config_uuid:
                        trig_config_name = config_name
                        trig_config_initial_content = config_content
                        trig_config_origin = data.get("origin", ORIGIN_MANUAL)
                        trig_config_idx = domain_config_idx
                        trig_global_idx = i

            # The blacklist toggle owns rule-produced cards. Its saved signal
            # rebuilds this row once the domain has been updated.
            if trig_type == "delete-config" and trig_config_origin in (ORIGIN_GENERATED, ORIGIN_BLACKLISTED):
                return [dash.no_update for _ in range(len(config_cards_row))]
            
            if trig_type == "new-config" and add_click:
                for idx in range(1, 1001):
                    new_filename = f"new_config{idx}.txt"
                    if new_filename not in trig_domain_configs:
                        instance_domain(instances, instance_name, trig_domain_name).configs.write(new_filename, "")
                        config_uuid = get_uuid()
                        insert_config_card(
                            config_cards_row[trig_domain_idx],
                            config_card(
                                domain_uuid=trig_domain_uuid,
                                config_uuid=config_uuid,
                                config_name=new_filename,
                                content="",
                                initial_content="",
                                config_layout=config_layout,
                            ),
                        )
                        break
                else:
                    error_msg = "Too many config creation fails (1000 max)."

            elif trig_type in ["save-config", "delete-config", "duplicate-config"]:         
                trig_config_content = contents[trig_global_idx] if trig_global_idx >= 0 and trig_global_idx < len(contents) else ""
                
                # Save config (and handle rename)
                if trig_type == "save-config":
                    config_new_title = title_values[trig_global_idx] if trig_global_idx >= 0 and trig_global_idx < len(title_values) else ""
                    config_old_title = trig_config_name
                    
                    if not config_new_title.endswith(".txt"):
                        config_new_title = config_new_title + ".txt"
                    if config_new_title != config_old_title:
                        if verbose:
                            print(f"Renaming config from '{config_old_title}' to '{config_new_title}'")
                        if config_new_title in trig_domain_configs:
                            if verbose:
                                print(f"File '{config_new_title}' already exists.")
                        else:
                            path = instance_domain(instances, instance_name, trig_domain_name).path
                            old_path = os.path.join(path, config_old_title)
                            new_path = os.path.join(path, config_new_title)
                            if verbose:
                                print(f"Renaming {old_path} to {new_path}")
                            os.rename(old_path, new_path)
                            config_old_title = config_new_title
                    if verbose:
                        print(f"Saving config '{config_old_title}' in domain '{trig_domain_name}'")
                    domain = instance_domain(instances, instance_name, trig_domain_name)
                    domain.configs.write(config_old_title, trig_config_content)
                    config_metadata[trig_config_idx]['config_content'] = trig_config_content
                    config_cards_row[trig_domain_idx][trig_config_idx] = config_card(
                        domain_uuid=trig_domain_uuid,
                        config_uuid=trig_config_uuid,
                        config_name=config_old_title,
                        content=trig_config_content,
                        initial_content=trig_config_content,
                        config_layout=config_layout,
                        origin=origin_of(domain, config_old_title),
                    )

                # Delete config
                if trig_type == "delete-config" and trig_config_name:
                    domain = instance_domain(instances, instance_name, trig_domain_name)
                    from_rules = rules_of(domain).get(trig_config_name)
                    if domain.configs.exists(trig_config_name):
                        domain.configs.delete(trig_config_name)
                    card_idx = card_index(config_cards_row[trig_domain_idx], trig_domain_uuid, trig_config_uuid)
                    if card_idx >= 0:
                        if from_rules is not None:
                            # The file was an edit of what the rules produce:
                            # deleting it takes the configuration back to its
                            # rule, it does not remove it from the domain.
                            generated = origin_of(domain, trig_config_name)
                            content = rules_of(domain)[trig_config_name].content
                            config_cards_row[trig_domain_idx][card_idx] = config_card(
                                domain_uuid=trig_domain_uuid,
                                config_uuid=trig_config_uuid,
                                config_name=trig_config_name,
                                content=content,
                                initial_content=content,
                                config_layout=config_layout,
                                origin=generated,
                            )
                        else:
                            config_cards_row[trig_domain_idx].pop(card_idx)

                # Duplicate config
                if trig_type == "duplicate-config":
                    base = trig_config_name[:-4] if trig_config_name.endswith(".txt") else trig_config_name
                    suffix = 1
                    new_filename = f"{base}_copy{suffix}.txt"
                    while new_filename in trig_domain_configs:
                        suffix += 1
                        new_filename = f"{base}_copy{suffix}.txt"
                    instance_domain(instances, instance_name, trig_domain_name).configs.write(new_filename, trig_config_content)
                    config_uuid = get_uuid()
                    insert_config_card(
                        config_cards_row[trig_domain_idx],
                        config_card(
                            domain_uuid=trig_domain_uuid,
                            config_uuid=config_uuid,
                            config_name=new_filename,
                            content=trig_config_content,
                            initial_content=trig_config_content,
                            config_layout=config_layout,
                        ),
                    )
  
    # Initial load
    if triggered_id == "param-domains-section-initialized":
        config_cards_row = []
        for idx, (domain_uuid, domain_name) in enumerate(domains.items()):
            config_cards_row.append(build_config_cards(
                instance_domain(instances, instance_name, domain_name), domain_uuid, config_layout,
            ))
        return config_cards_row
    
    # If a domain was duplicated, load the new domain configs
    elif triggered_id == "param-domains-section-update":
        # Reload only domain with uuid == update_domain_uuid
        for i, domain_uuid in enumerate(domains.keys()):
            if domain_uuid == update_domain_uuid:
                config_cards_row[i] = build_config_cards(
                    instance_domain(instances, instance_name, domains[domain_uuid]), domain_uuid, config_layout,
                )
                changed_rows.add(i)
                break

    return [
        row if i in changed_rows else dash.no_update
        for i, row in enumerate(config_cards_row)
    ]


@dash.callback(
    # The row is patched, not rewritten: the cards already there are what the
    # user is editing, and the point of showing them a few at a time is lost if
    # the whole list travels back and forth to add to it.
    Output({"type": "config-cards-row", "domain_uuid": dash.ALL}, "children", allow_duplicate=True),
    Output({"type": "show-more-label", "domain_uuid": dash.ALL}, "children"),
    Output({"type": "show-more-count", "domain_uuid": dash.ALL}, "children"),
    Output({"type": "show-more-card", "domain_uuid": dash.ALL}, "className", allow_duplicate=True),
    Output({"type": "config-hidden", "domain_uuid": dash.ALL}, "data"),
    Input({"type": "show-more-configs", "domain_uuid": dash.ALL}, "n_clicks"),
    State({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State({"type": "config-filter-state", "domain_uuid": dash.ALL}, "data"),
    State({"type": "config-filter-state", "domain_uuid": dash.ALL}, "id"),
    State("config-layout-dropdown", "value"),
    State("url", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def show_more_configs(
    clicks, config_metadata, domain_metadata, filter_states, filter_ids, config_layout, search, odatix_settings
):
    """
    Give cards to the next configurations of one domain. What is already shown
    is read from the cards themselves rather than from a count, so adding or
    deleting a configuration in the meantime cannot make this skip one.
    """
    nothing = [dash.no_update] * len(domain_metadata)
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict) or not any(clicks or []):
        return nothing, nothing, nothing, nothing, nothing

    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    trig_domain_uuid = trigger.get("domain_uuid", "")
    index = next(
        (i for i, data in enumerate(domain_metadata) if (data or {}).get("domain_uuid", "") == trig_domain_uuid),
        -1,
    )
    if not instance_name or index < 0:
        return nothing, nothing, nothing, nothing, nothing

    domain = instance_domain(instances, instance_name, domain_metadata[index].get("domain_name", ""))
    if domain is None:
        return nothing, nothing, nothing, nothing, nothing

    shown = [
        (data or {}).get("config_name", "")
        for data in config_metadata
        if (data or {}).get("domain_uuid", "") == trig_domain_uuid
    ]
    missing = [config for config in domain_configurations(domain) if config.filename not in set(shown)]
    # The stat filters hide cards, so a batch of filtered out configurations
    # would look like a click that did nothing: skip them to give the user the
    # promised count of cards they can actually see. They stay in "missing", and
    # so remain reachable once the filter is lifted.
    filtered = next(
        (
            filter_states[i] or []
            for i, filter_id in enumerate(filter_ids or [])
            if (filter_id or {}).get("domain_uuid", "") == trig_domain_uuid
        ),
        [],
    )
    batch = [config for config in missing if config.origin not in filtered][:configs_per_page]
    hidden = len(missing) - len(batch)

    row = Patch()
    for offset, config in enumerate(batch):
        row.insert(
            len(shown) + offset,
            config_card(
                domain_uuid=trig_domain_uuid,
                config_uuid=get_uuid(),
                config_name=config.filename,
                content=config.content,
                initial_content=config.content,
                config_layout=config_layout,
                origin=config.origin,
            ),
        )

    def only_here(value):
        return [value if i == index else dash.no_update for i in range(len(domain_metadata))]

    return (
        only_here(row),
        only_here(show_more_label(hidden)),
        only_here(show_more_count(hidden)),
        only_here(show_more_class(config_layout, hidden)),
        only_here(hidden),
    )


def rules_with_configuration_blacklist(saved_rules, config_name, blacklisted):
    """Return saved rules with one generated configuration added or removed."""
    rules = dict(saved_rules or {})
    configurations = dict(rules.get(config_rules.CONFIGURATIONS_KEY, {}) or {})
    blacklist = config_rules.configuration_blacklist(rules)
    if blacklisted:
        if config_name not in blacklist:
            blacklist.append(config_name)
    else:
        blacklist = [name for name in blacklist if name != config_name]
    if blacklist:
        configurations["blacklist"] = blacklist
    else:
        configurations.pop("blacklist", None)
    rules[config_rules.CONFIGURATIONS_KEY] = configurations
    return rules


@dash.callback(
    Output({"type": "cfg-rules-store", "domain_uuid": dash.ALL}, "data", allow_duplicate=True),
    Output({"type": "cfg-rules-saved", "domain_uuid": dash.ALL}, "data", allow_duplicate=True),
    # The cards of the domain are rewritten here rather than left to the callback
    # that owns them: it answers the same click, so waiting for it would mean
    # relying on the order Dash runs the two in, and the card kept the look it
    # had until the page was reloaded.
    Output({"type": "config-cards-row", "domain_uuid": dash.ALL}, "children", allow_duplicate=True),
    Input({"type": "delete-config", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "n_clicks"),
    State({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State({"type": "cfg-rules-store", "domain_uuid": dash.ALL}, "data"),
    State({"type": "cfg-rules-saved", "domain_uuid": dash.ALL}, "data"),
    State("config-layout-dropdown", "value"),
    State("url", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def toggle_generated_configuration_blacklist(
    delete_clicks, config_metadata, domain_metadata, rules_stores, saved_counters, config_layout, search,
    odatix_settings,
):
    """Blacklist a generated configuration, or restore it from the same card button."""
    nothing = [dash.no_update] * len(domain_metadata)
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict):
        return nothing, nothing, nothing

    # Rebuilding the row hands Dash brand new buttons, and it announces them here as
    # if they had been pressed. Only a button carrying a click count is a real press,
    # otherwise a page reload would toggle the blacklist a second time on its own.
    clicked = next(
        (
            clicks for entry, clicks in zip(ctx.inputs_list[0], delete_clicks or [])
            if entry.get("id") == trigger
        ),
        None,
    )
    if not clicked:
        return nothing, nothing, nothing

    domain_uuid = trigger.get("domain_uuid", "")
    config_uuid = trigger.get("config_uuid", "")
    metadata = next(
        (
            data for data in (config_metadata or [])
            if (data or {}).get("domain_uuid") == domain_uuid
            and (data or {}).get("config_uuid") == config_uuid
        ),
        None,
    )
    origin = (metadata or {}).get("origin")
    if origin not in (ORIGIN_GENERATED, ORIGIN_BLACKLISTED):
        return nothing, nothing, nothing

    index = next(
        (i for i, data in enumerate(domain_metadata) if (data or {}).get("domain_uuid") == domain_uuid),
        -1,
    )
    if index < 0:
        return nothing, nothing, nothing

    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    if not instance_name or instance_name not in instances:
        return nothing, nothing, nothing

    domain_name = domain_metadata[index].get("domain_name", "")
    domain = instance_domain(instances, instance_name, domain_name)
    if domain is None:
        return nothing, nothing, nothing
    saved = rules_stores[index] if index < len(rules_stores) and rules_stores[index] else domain.settings.to_dict()
    filename = (metadata or {}).get("config_name", "")
    config_name = filename[:-4] if filename.endswith(".txt") else filename
    updated = rules_with_configuration_blacklist(saved, config_name, origin == ORIGIN_GENERATED)
    if updated == saved:
        return nothing, nothing, nothing

    persisted_configurations = dict(updated[config_rules.CONFIGURATIONS_KEY])
    if not config_rules.configuration_blacklist(updated):
        # Nested settings merge mapping updates, so an absent key alone would
        # leave a previous blacklist in memory after the configuration is restored.
        persisted_configurations["blacklist"] = []
    domain.update({config_rules.CONFIGURATIONS_KEY: persisted_configurations})
    counter = (saved_counters[index] or 0) if index < len(saved_counters) else 0
    stores = list(nothing)
    counters = list(nothing)
    rows = list(nothing)
    stores[index] = updated
    counters[index] = counter + 1
    # Read once the domain has been written: what it holds now is what the cards
    # of this domain say, blacklisted one included.
    rows[index] = build_config_cards(
        domain, domain_uuid, config_layout, shown=cards_shown(config_metadata, domain_uuid),
    )
    return stores, counters, rows

# Fill the preview config selector of each domain with its configs. Renaming a
# configuration retitles its entry as it is typed, so this answers every
# keystroke of every title: it is a relabelling of data the client already
# holds, and it stays there.
PREVIEW_SELECT_JS = """
    function(_section, titles, metadata, domains, currentValues) {
        const optionsOut = [];
        const valuesOut = [];
        (domains || []).forEach(function(domain, i) {
            const domainUuid = (domain && domain.domain_uuid) || "";
            const options = [];
            (metadata || []).forEach(function(config, j) {
                if (!config || (config.domain_uuid || "") !== domainUuid) {
                    return;
                }
                const title = (titles && titles[j]) ? titles[j] : (config.config_name || "");
                options.push({label: title, value: config.config_uuid || ""});
            });
            let current = i < (currentValues || []).length ? currentValues[i] : null;
            const known = options.some(function(option) { return option.value === current; });
            if (!known) {
                current = options.length ? options[0].value : null;
            }
            optionsOut.push(options);
            valuesOut.push(current);
        });
        return [optionsOut, valuesOut];
    }
"""

dash.clientside_callback(
    PREVIEW_SELECT_JS,
    Output({"type": "preview-config-select", "domain_uuid": dash.ALL}, "options"),
    Output({"type": "preview-config-select", "domain_uuid": dash.ALL}, "value"),
    Input("param-domains-section", "children"),
    # The cards themselves are not an input: rewriting a row replaces the
    # metadata stores it holds, which is the same signal without shipping the
    # whole card tree back to the server.
    Input({"type": "config-title", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "value"),
    Input({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State({"type": "preview-config-select", "domain_uuid": dash.ALL}, "value"),
    prevent_initial_call=True
)

@dash.callback(
    Output({"type": "preview-pane", "domain_uuid": dash.ALL}, "children"),
    State("url", "search"),
    Input("param-domains-section", "children"),
    Input({"type": "use_parameters", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "param_target_file", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "start_delimiter", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "stop_delimiter", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "config-params-store", "domain_uuid": dash.ALL}, "data"),
    # The contents themselves are a State: what says they changed is the
    # debounced signal, so a keystroke costs nothing until the typing stops.
    Input("config-content-debounce", "data"),
    State({"type": "config-content", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "value"),
    Input({"type": "preview-config-select", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "cfg-gen-name", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "cfg-gen-template", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "cfg-rules-store", "domain_uuid": dash.ALL}, "data"),
    *config_rules.variable_inputs(),
    # Card rows are rebuilt after a blacklist toggle. Metadata must be an input
    # so the pane runs again once those replacement cards exist.
    Input({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State("odatix-settings", "data"),
    # The default a domain falls back to, previewed when it has no
    # configuration of its own to select.
    Input({"type": "simarch-param-file", "domain_uuid": dash.ALL}, "value"),
    prevent_initial_call=True
)
def update_preview_all(
    search, param_domains_update,
    params_enables, target_files, start_delims, stop_delims, settings_list,
    content_debounce, config_contents_list,
    selected_configs, rule_names, rule_templates, rule_stores, *rest
):
    rule_field_values = rest[:len(config_rules.FIELD_PATTERNS)]
    config_metadata = rest[len(config_rules.FIELD_PATTERNS)] if len(rest) > len(config_rules.FIELD_PATTERNS) else []
    domain_metadata = rest[len(config_rules.FIELD_PATTERNS) + 1] if len(rest) > len(config_rules.FIELD_PATTERNS) + 1 else []
    odatix_settings = rest[len(config_rules.FIELD_PATTERNS) + 2] if len(rest) > len(config_rules.FIELD_PATTERNS) + 2 else {}
    entry_param_files = rest[len(config_rules.FIELD_PATTERNS) + 3] if len(rest) > len(config_rules.FIELD_PATTERNS) + 3 else []
    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    # A simulation writes its parameters into its own sources, or into the RTL
    # of the architecture it runs on, which is copied next to them: both are
    # where the file a section previews is looked up.
    arch = sim_arch_name(search)
    base_path = None
    if arch and instance_name in instances:
        arch_paths = sim_domains.architecture_source_paths(get_workspace(odatix_settings).architectures, arch)
        base_path = [instances[instance_name].path]
        # The RTL is copied under "rtl/" in the work directory, so a target file
        # can name it either way: through that prefix, or against the sources.
        base_path += [(path, hard_settings.work_rtl_path) for path in arch_paths]
        base_path += arch_paths
    if not instance_name or instance_name not in instances:
        label = instance_label(mode)
        return [
            html.Div([
                html.Div(f"{label} is not created yet."),
                html.Div("Edit settings, then save or add a new config to create it."),
            ], className="error warning")
        ] * len(domain_metadata)

    stale_domains = preview_domains_to_refresh(content_debounce)

    # Group config contents by domain, keyed by config uuid
    contents_by_domain = []
    for domain in domain_metadata:
        domain_uuid = domain.get("domain_uuid", "")
        domain_contents = {
            config.get("config_uuid", ""): config_contents_list[i]
            for i, config in enumerate(config_metadata)
            if config.get("domain_uuid", "") == domain_uuid and i < len(config_contents_list)
        }
        contents_by_domain.append(domain_contents)

    rule_configurations_by_domain = unsaved_rule_configurations(
        rule_names, rule_templates, rule_stores, rule_field_values, domain_metadata,
        only=stale_domains,
    )

    # Generate previews for each domain
    results = []
    for i, domain in enumerate(domain_metadata):
        domain_uuid = domain.get("domain_uuid", "")
        # A domain nothing touched keeps the pane it already shows.
        if stale_domains is not None and domain_uuid not in stale_domains:
            results.append(dash.no_update)
            continue
        domain_contents = contents_by_domain[i] if i < len(contents_by_domain) else {}
        settings = settings_list[0] if 0 < len(settings_list) and settings_list[0] is not None else {}
        domain_settings = settings_list[i] if i < len(settings_list) and settings_list[i] is not None else {}
        domain_settings["use_parameters"] = params_enables[i] if i < len(params_enables) else ""
        domain_settings["param_target_file"] = target_files[i] if i < len(target_files) else ""
        domain_settings["start_delimiter"] = start_delims[i] if i < len(start_delims) else ""
        domain_settings["stop_delimiter"] = stop_delims[i] if i < len(stop_delims) else ""
        selected_config = selected_configs[i] if i < len(selected_configs) else None
        domain_rules = rule_configurations_by_domain.get(domain_uuid, {})
        replacement_text = replacement_text_for_preview(
            selected_config, domain_uuid, domain_contents, config_metadata, domain_rules,
        )
        # Nothing to select: the entry substitutes its default file, the way a
        # run does for a configuration its directory does not describe.
        if not domain_contents and not domain_rules and len(entry_param_files) == len(domain_metadata):
            default_text = default_param_text(instances[instance_name].path, entry_param_files[i])
            if default_text is not None:
                replacement_text = default_text
        results.append(preview_pane(domain_uuid, mode, settings, domain_settings, replacement_text, base_path=base_path))
    return results

# The dirty state of a card is nothing but string comparisons, and it is the one
# thing that has to answer every keystroke. Run on the client: a domain with a
# few hundred configurations would otherwise send every title and every content
# to the server, and take back a class name per card, on every character typed.
SAVE_STATUS_JS = """
function(_section, titles, contents, initialTitles, initialContents) {
    const invalid = __INVALID_CHARS__;
    const base = "icon-button tooltip delay bottom small";
    const context = window.dash_clientside.callback_context;
    const outputs = (context && context.outputs_list && context.outputs_list[0]) || [];
    // Names are only taken within their own domain: two domains can each have a "12"
    const domains = outputs.map(function(output) {
        return (output && output.id && output.id.domain_uuid) || "";
    });
    const takenByDomain = {};
    for (let i = 0; i < initialTitles.length; i++) {
        const domain = domains[i] === undefined ? "" : domains[i];
        (takenByDomain[domain] = takenByDomain[domain] || []).push(initialTitles[i]);
    }
    const classes = [];
    const tooltips = [];
    for (let i = 0; i < titles.length; i++) {
        const title = titles[i];
        const initialTitle = initialTitles[i];
        let error = null;
        if (!title) {
            error = "Configuration name cannot be empty";
        } else {
            for (let c = 0; c < invalid.length; c++) {
                if (title.indexOf(invalid[c]) !== -1) {
                    const shown = invalid[c] === " " ? "' ' (space)" : "'" + invalid[c] + "'";
                    error = "Unauthorized character in configuration name: " + shown;
                    break;
                }
            }
            if (!error && title !== initialTitle
                    && (takenByDomain[domains[i]] || []).indexOf(title) !== -1) {
                error = "A configuration with this name already exists in the domain.";
            }
        }
        if (error) {
            classes.push("color-button error-status " + base);
            tooltips.push(error);
        } else if (title !== initialTitle || contents[i] !== initialContents[i]) {
            classes.push("color-button warning " + base);
            tooltips.push("Unsaved changes!");
        } else {
            classes.push("color-button disabled " + base);
            tooltips.push("Nothing to save");
        }
    }
    return [classes, tooltips];
}
""".replace("__INVALID_CHARS__", json.dumps(hard_settings.invalid_filename_characters))

dash.clientside_callback(
    SAVE_STATUS_JS,
    Output({"type": "save-config", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "className"),
    Output({"type": "save-config", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data-tooltip"),
    Input("param-domains-section", "children"),
    Input({"type": "config-title", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "value"),
    Input({"type": "config-content", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "value"),
    Input({"type": "initial-title", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    Input({"type": "initial-content", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
)

def filter_stat(domain_uuid, origin, count, label, filtered, className=""):
    """
    A stat of the strip that also filters: clicking it takes the configurations
    it counts out of the list below, and says so by striking itself through.
    """
    is_off = origin in (filtered or [])
    classes = " ".join(c for c in (className, "odx-stat-filter", "odx-stat-off" if is_off else "") if c)
    return ui.stat(
        count,
        label,
        className=classes,
        id={"type": "config-filter", "domain_uuid": domain_uuid, "origin": origin},
        tooltip="Show these configurations again" if is_off else f"Hide the {label} configurations",
    )


@dash.callback(
    Output({"type": "config-counters", "domain_uuid": dash.ALL}, "children"),
    Input({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    Input({"type": "config-hidden", "domain_uuid": dash.ALL}, "data"),
    Input({"type": "config-filter-state", "domain_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
)
def update_config_counters(config_metadata, hidden_counts, filter_states, domain_metadata):
    """
    How many configurations each domain holds, and where they come from. A
    domain with nothing but hand-written files says only how many there are.
    The ones with no card are counted in the total and named apart: only the
    cards say where a configuration comes from, so the breakdown is of them.

    Every stat naming an origin is also the filter of that origin, struck
    through while its cards are out of the list.
    """
    counters = []
    for index, domain in enumerate(domain_metadata):
        domain_uuid = domain.get("domain_uuid", "")
        hidden = hidden_counts[index] if index < len(hidden_counts) else 0
        hidden = hidden or 0
        filtered = filter_states[index] if index < len(filter_states) else []
        origins = [
            (data or {}).get("origin", ORIGIN_MANUAL)
            for data in config_metadata
            if (data or {}).get("domain_uuid", "") == domain_uuid
        ]
        active_origins = [origin for origin in origins if origin != ORIGIN_BLACKLISTED]
        total = len(active_origins) + hidden
        stats = [ui.stat(
            total, "configurations" if total != 1 else "configuration", className="accent",
        )]
        if hidden:
            stats.append(ui.stat(hidden, "not shown"))
        for origin, label in ((ORIGIN_GENERATED, "generated"), (ORIGIN_EDITED, "edited")):
            count = active_origins.count(origin)
            if count:
                stats.append(filter_stat(domain_uuid, origin, count, label, filtered))
        manual = active_origins.count(ORIGIN_MANUAL)
        if manual and len(stats) > 1:
            stats.append(filter_stat(domain_uuid, ORIGIN_MANUAL, manual, "written by hand", filtered))
        blacklisted = origins.count(ORIGIN_BLACKLISTED)
        if blacklisted:
            stats.append(filter_stat(
                domain_uuid, ORIGIN_BLACKLISTED, blacklisted, "blacklisted", filtered, className="caution",
            ))
        counters.append(stats)
    return counters


# Clicking a filter stat only flips the origin it names, and only for its own
# domain: the strips of the other domains keep whatever they were filtering.
CONFIG_FILTER_TOGGLE_JS = """
    function(clicks, states, stateIds) {
        const dc = window.dash_clientside;
        const context = dc.callback_context;
        const trigger = context.triggered && context.triggered[0];
        if (!trigger || !trigger.value) {
            return dc.no_update;
        }
        const id = JSON.parse(trigger.prop_id.substring(0, trigger.prop_id.lastIndexOf(".")));
        return (states || []).map(function(state, i) {
            const stateId = (stateIds || [])[i] || {};
            if ((stateId.domain_uuid || "") !== (id.domain_uuid || "")) {
                return dc.no_update;
            }
            const filtered = (state || []).slice();
            const at = filtered.indexOf(id.origin);
            if (at >= 0) {
                filtered.splice(at, 1);
            } else {
                filtered.push(id.origin);
            }
            return filtered;
        });
    }
"""

dash.clientside_callback(
    CONFIG_FILTER_TOGGLE_JS,
    Output({"type": "config-filter-state", "domain_uuid": dash.ALL}, "data"),
    Input({"type": "config-filter", "domain_uuid": dash.ALL, "origin": dash.ALL}, "n_clicks"),
    State({"type": "config-filter-state", "domain_uuid": dash.ALL}, "data"),
    State({"type": "config-filter-state", "domain_uuid": dash.ALL}, "id"),
    prevent_initial_call=True,
)

# Filtered cards are hidden rather than dropped: what a card holds is unsaved
# work as often as not, and its style is the one thing the layout switch does
# not rewrite, so the two never fight over the same property.
CONFIG_FILTER_APPLY_JS = """
    function(states, metadata, stateIds) {
        const filtered = {};
        (stateIds || []).forEach(function(stateId, i) {
            filtered[(stateId && stateId.domain_uuid) || ""] = (states || [])[i] || [];
        });
        return (metadata || []).map(function(config) {
            config = config || {};
            const hidden = filtered[config.domain_uuid || ""] || [];
            return hidden.indexOf(config.origin || "manual") >= 0 ? {"display": "none"} : {};
        });
    }
"""

dash.clientside_callback(
    CONFIG_FILTER_APPLY_JS,
    Output({"type": "config-card", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "style"),
    Input({"type": "config-filter-state", "domain_uuid": dash.ALL}, "data"),
    Input({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    State({"type": "config-filter-state", "domain_uuid": dash.ALL}, "id"),
)

@dash.callback(
    Output({"type": "config-origin", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "children"),
    Output({"type": "config-origin", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data-tooltip"),
    Output({"type": "delete-config", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "className"),
    Output({"type": "delete-config", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data-tooltip"),
    Output({"type": "config-title", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "readOnly"),
    Input({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
)
def update_origin_indicators(config_metadata):
    """
    Keep what a card says about where its configuration comes from in step with
    its metadata, so saving an edit relabels the card without a reload.
    """
    badges, badge_tooltips, delete_classes, delete_tooltips, read_only = [], [], [], [], []
    for data in config_metadata:
        origin = (data or {}).get("origin", ORIGIN_MANUAL)
        badges.append(origin_badge(origin))
        badge_tooltips.append(ORIGIN_LABELS.get(origin, ("", "", ""))[2])
        delete_classes.append(delete_button_class(origin))
        delete_tooltips.append(DELETE_TOOLTIPS.get(origin, DELETE_TOOLTIPS[ORIGIN_MANUAL])[1])
        read_only.append(origin in (ORIGIN_GENERATED, ORIGIN_EDITED, ORIGIN_BLACKLISTED))
    return badges, badge_tooltips, delete_classes, delete_tooltips, read_only

@dash.callback(
    Output({"type": "save-params-btn", "domain_uuid": dash.ALL}, "className"),
    Input({"type": "use_parameters", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "param_target_file", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "start_delimiter", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "stop_delimiter", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "config-params-store", "domain_uuid": dash.ALL}, "data"),
    Input({"type": "simarch-domain", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "simarch-combine", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "simarch-param-file", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "simarch-param-dir", "domain_uuid": dash.ALL}, "value"),
    State({"type": "simarch-entry-store", "domain_uuid": dash.ALL}, "data"),
)
def update_params_save_button(
    params_enables, target_files, start_delims, stop_delims, settings_list,
    entry_names, combines, entry_param_files, entry_param_dirs, entry_stores,
):
    save_classes = []
    disabled_class = "color-button disabled icon-button"
    enabled_class = "color-button warning icon-button"

    for index, (use_parameters, param_target_file, start_delimiter, stop_delimiter, domain_settings) in enumerate(
        zip(params_enables, target_files, start_delims, stop_delims, settings_list)
    ):
        dirty = params_are_dirty(use_parameters, param_target_file, start_delimiter, stop_delimiter, domain_settings)
        # What the section points at is saved by the same button, so it makes it
        # dirty just as the substitution does.
        if not dirty and index < len(entry_names):
            values = sim_arch_values(
                entry_names, combines, entry_param_files, entry_param_dirs, entry_stores, index,
            )
            previous = values["store"].get("overrides") or {}
            dirty = (
                values["name"] != str(values["store"].get("name", ""))
                or values["param_dir"] != str(previous.get("param_dir", "") or "")
                or values["param_file"] != str(previous.get("param_file", "") or "")
                or values["combine"] != sim_architectures.combine_mode(previous)
            )
        save_classes.append(enabled_class if dirty else disabled_class)
    return save_classes

# Mirror the state of the individual save buttons on the page-wide save button.
# The "warning" class is also what the unsaved-changes guard looks for to warn
# before leaving the page. Clientside, since it answers every keystroke through
# the card save buttons -- and reading a class name needs no server.
dash.clientside_callback(
    """
    function(configClasses, paramsClasses, rulesClasses) {
        const base = "icon-button tooltip bottom auto caution";
        const all = [].concat(configClasses || [], paramsClasses || [], rulesClasses || []);
        const dirty = all.some(function(name) {
            return typeof name === "string" && name.indexOf("warning") !== -1;
        });
        if (dirty) {
            return ["color-button warning " + base, "Save all changes"];
        }
        return ["color-button disabled " + base, "Nothing to save"];
    }
    """,
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Input({"type": "save-config", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "className"),
    Input({"type": "save-params-btn", "domain_uuid": dash.ALL}, "className"),
    Input({"type": "cfg-save-rules", "domain_uuid": dash.ALL}, "className"),
)

@dash.callback(
    Output({"type": "initial-title", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    Output({"type": "initial-content", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    Output({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    Output({"type": "config-params-store", "domain_uuid": dash.ALL}, "data", allow_duplicate=True),
    Output({"type": "simarch-entry-store", "domain_uuid": dash.ALL}, "data", allow_duplicate=True),
    Output("sim-arch-reload", "data", allow_duplicate=True),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    State({"type": "config-title", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "value"),
    State({"type": "config-content", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "value"),
    State({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    State({"type": "use_parameters", "domain_uuid": dash.ALL}, "value"),
    State({"type": "param_target_file", "domain_uuid": dash.ALL}, "value"),
    State({"type": "start_delimiter", "domain_uuid": dash.ALL}, "value"),
    State({"type": "stop_delimiter", "domain_uuid": dash.ALL}, "value"),
    State({"type": "config-params-store", "domain_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    *SIM_ARCH_STATES,
    State("sim-arch-reload", "data"),
    State("url", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_all(
    n_clicks, title_values, contents, config_metadata,
    params_enables, target_files, start_delims, stop_delims, params_stores, domain_metadata,
    entry_names, combines, entry_param_files, entry_param_dirs, entry_stores, reload_count,
    search, odatix_settings
):
    """
    Save every modified configuration and every modified parameters form at once.
    Configurations whose name is invalid or already taken are left untouched, so
    their own save button keeps showing the error.
    """
    nb_configs = len(config_metadata)
    nb_domains = len(domain_metadata)
    no_config_update = [dash.no_update] * nb_configs
    no_domain_update = [dash.no_update] * nb_domains
    no_entry_update = [dash.no_update] * len(entry_names)
    nothing = (no_config_update, no_config_update, no_config_update, no_domain_update,
               no_entry_update, dash.no_update)

    if not n_clicks:
        return nothing

    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    if not instance_name:
        return nothing

    domain_names = {data.get("domain_uuid", ""): data.get("domain_name", "") for data in domain_metadata}

    new_titles = list(no_config_update)
    new_contents = list(no_config_update)
    new_metadata = list(no_config_update)

    # Configurations
    for i, metadata in enumerate(config_metadata):
        domain_uuid = metadata.get("domain_uuid", "")
        domain_name = domain_names.get(domain_uuid, domain_uuid)
        old_name = metadata.get("config_name", "")
        old_content = metadata.get("config_content", "")
        old_title = old_name[:-4] if old_name.endswith(".txt") else old_name
        new_title = title_values[i] if i < len(title_values) else ""
        new_content = contents[i] if i < len(contents) else ""

        if new_title == old_title and new_content == old_content:
            continue

        # Names already taken in this domain, this config's own name excluded
        domain_titles = [
            (data.get("config_name", "")[:-4] if data.get("config_name", "").endswith(".txt") else data.get("config_name", ""))
            for j, data in enumerate(config_metadata)
            if j != i and data.get("domain_uuid", "") == domain_uuid
        ]
        if config_title_error(new_title, domain_titles, old_title):
            continue

        new_name = new_title if new_title.endswith(".txt") else new_title + ".txt"
        domain = instance_domain(instances, instance_name, domain_name)
        if domain is None:
            continue
        if new_name != old_name:
            if verbose:
                print(f"Renaming config from '{old_name}' to '{new_name}'")
            os.rename(os.path.join(domain.path, old_name), os.path.join(domain.path, new_name))
        if verbose:
            print(f"Saving config '{new_name}' in domain '{domain_name}'")
        domain.configs.write(new_name, new_content)

        new_titles[i] = new_title
        new_contents[i] = new_content
        new_metadata[i] = {
            **metadata,
            "config_name": new_name,
            "config_content": new_content,
            "origin": origin_of(domain, new_name),
        }

    # Configuration parameters
    new_params = list(no_domain_update)
    # What each section says about the substitution, for the ones a simulation
    # writes in its own settings file rather than in a directory.
    substitutions = {}
    for i, metadata in enumerate(domain_metadata):
        use_parameters = params_enables[i] if i < len(params_enables) else False
        param_target_file = target_files[i] if i < len(target_files) else ""
        start_delimiter = start_delims[i] if i < len(start_delims) else ""
        stop_delimiter = stop_delims[i] if i < len(stop_delims) else ""
        settings = params_stores[i] if i < len(params_stores) and params_stores[i] is not None else {}

        if not params_are_dirty(use_parameters, param_target_file, start_delimiter, stop_delimiter, settings):
            continue

        settings = {
            **settings,
            "use_parameters": True if use_parameters else False, # Convert from [True]/[] to True/False
            "param_target_file": param_target_file,
            "start_delimiter": start_delimiter,
            "stop_delimiter": stop_delimiter,
        }
        domain_name = sim_arch_param_dir(
            entry_names, entry_param_dirs, i, metadata,
        ) if entry_names else metadata.get("domain_name", "")
        if domain_name:
            instance_domain(instances, instance_name, domain_name).update(settings)
        new_params[i] = settings
        substitutions[i] = settings

    # What the simulation substitutes for one architecture is written whole,
    # whether or not a section's own fields changed: it is one mapping.
    new_entry_stores = no_entry_update
    reload_needed = False
    if entry_names:
        reload_needed, new_entry_stores = save_sim_arch_entries(
            search, odatix_settings, domain_metadata,
            entry_names, combines, entry_param_files, entry_param_dirs, entry_stores,
            substitutions=substitutions,
        )

    return (
        new_titles, new_contents, new_metadata, new_params, new_entry_stores,
        (reload_count or 0) + 1 if reload_needed else dash.no_update,
    )

@dash.callback(
    Output({"type": "config-card", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "className"),
    Output({"type": "add-config-card", "domain_uuid": dash.ALL}, "className"),
    Output({"type": "show-more-card", "domain_uuid": dash.ALL}, "className"),
    Output({"type": "config-cards-row", "domain_uuid": dash.ALL}, "className"),
    Input("config-layout-dropdown", "value"),
    State({"type": "config-card", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "className"),
    State({"type": "add-config-card", "domain_uuid": dash.ALL}, "className"),
    State({"type": "show-more-card", "domain_uuid": dash.ALL}, "className"),
    State({"type": "config-cards-row", "domain_uuid": dash.ALL}, "className"),
)
def update_layout_style(layout_value, config_card_classes, add_card_classes, show_more_classes, config_row_classes):
    blacklisted = ["odx-config-blacklisted" in (class_name or "") for class_name in config_card_classes]
    config_card_classes = [card_class(layout_value, is_blacklisted) for is_blacklisted in blacklisted]
    # A hidden show more card stays hidden: its class is the only place saying
    # whether the domain still has configurations without a card.
    show_more_classes = [
        show_more_class(layout_value, 0 if "odx-hidden" in (class_name or "") else 1)
        for class_name in show_more_classes
    ]
    if layout_value == "wide":
        add_card_classes = ["card configs add wide hover" for _ in range(len(add_card_classes))]
        config_row_classes = ["card-matrix configs wide" for _ in range(len(config_row_classes))]
    else:
        add_card_classes = ["card configs add hover" for _ in range(len(add_card_classes))]
        config_row_classes = ["card-matrix configs" for _ in range(len(config_row_classes))]
    return config_card_classes, add_card_classes, show_more_classes, config_row_classes

@dash.callback(
    Output({"type": "config-params-store", "domain_uuid": dash.ALL}, "data"),
    Output({"type": "simarch-entry-store", "domain_uuid": dash.ALL}, "data"),
    Output("sim-arch-reload", "data"),
    Input({"type": "save-params-btn", "domain_uuid": dash.ALL}, "n_clicks"),
    State({"type": "use_parameters", "domain_uuid": dash.ALL}, "value"),
    State({"type": "param_target_file", "domain_uuid": dash.ALL}, "value"),
    State({"type": "start_delimiter", "domain_uuid": dash.ALL}, "value"),
    State({"type": "stop_delimiter", "domain_uuid": dash.ALL}, "value"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State({"type": "config-params-store", "domain_uuid": dash.ALL}, "data"),
    *SIM_ARCH_STATES,
    State("sim-arch-reload", "data"),
    State("url", "search"),
    State("odatix-settings", "data"),
)
def save_config_parameters(
    n_clicks, 
    use_parameters, param_target_files, start_delimiters, stop_delimiters, domain_metadata, config_params_stores,
    entry_names, combines, entry_param_files, entry_param_dirs, entry_stores, reload_count,
    search, odatix_settings
):
    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    nothing = ([dash.no_update] * len(domain_metadata), [dash.no_update] * len(entry_names), dash.no_update)

    triggered = ctx.triggered_id
    if isinstance(triggered, dict):        
        trig_domain_uuid = triggered.get("domain_uuid", hard_settings.main_parameter_domain)
        trig_domain_name = trig_domain_uuid
        
        # Get domain from metadata
        for data in domain_metadata:
            domain_name = data.get("domain_name", "")
            domain_uuid = data.get("domain_uuid", "")
            if domain_uuid == trig_domain_uuid :
                trig_domain_name = domain_name
                break

        idx = next((i for i, data in enumerate(domain_metadata) if data.get("domain_uuid") == trig_domain_uuid), -1)
        if idx != -1:
            settings = config_params_stores[idx] if idx < len(config_params_stores) and config_params_stores[idx] is not None else {}

            # Get values
            use_parameters = use_parameters[idx] if idx < len(use_parameters) else False
            use_parameters = True if use_parameters else False # Convert from [True]/[] to True/False
            param_target_file = param_target_files[idx] if idx < len(param_target_files) else ""
            start_delimiter = start_delimiters[idx] if idx < len(start_delimiters) else ""
            stop_delimiter = stop_delimiters[idx] if idx < len(stop_delimiters) else ""

            # Update settings
            settings["use_parameters"] = use_parameters
            settings["param_target_file"] = param_target_file
            settings["start_delimiter"] = start_delimiter
            settings["stop_delimiter"] = stop_delimiter

            # What this simulation substitutes for one architecture: the whole
            # mapping is written at once, since it is one mapping, and what a
            # section says about the substitution goes with the directory it
            # points at -- or with the entry itself, when it points at none.
            new_entry_stores = [dash.no_update] * len(entry_names)
            reload_needed = False
            if entry_names:
                reload_needed, new_entry_stores = save_sim_arch_entries(
                    search, odatix_settings, domain_metadata,
                    entry_names, combines, entry_param_files, entry_param_dirs, entry_stores,
                    substitutions={idx: settings},
                )
                trig_domain_name = sim_arch_param_dir(
                    entry_names, entry_param_dirs, idx, domain_metadata[idx],
                )

            if trig_domain_name:
                instance_domain(instances, instance_name, trig_domain_name).update(settings)
            return (
                [settings if i == idx else dash.no_update for i in range(len(domain_metadata))],
                new_entry_stores,
                (reload_count or 0) + 1 if reload_needed else dash.no_update,
            )
    return nothing

@dash.callback(
    Output({"type": "params-config-fields", "domain_uuid": dash.ALL}, "className"),
    Output({"type": "config-cards-row", "domain_uuid": dash.ALL}, "style"),
    # The rules preview is part of that list: it goes away with it.
    Output({"type": "cfg-config-preview", "domain_uuid": dash.ALL}, "style"),
    Input ({"type": "use_parameters", "domain_uuid": dash.ALL}, "value"),
)
def toggle_params_fields(enabled_values):
    styles = []
    classes = []
    for value in enabled_values:
        if value:
            styles.append({})
            classes.append("animated-section")
        else:
            styles.append(Style.hidden)
            classes.append("animated-section hide")
    return classes, styles, list(styles)

@dash.callback(
    Output({"page": page_path, "type": "instance-title-div"}, "children"),
    Input("url", "search"),
)
def update_instance_title(search):
    mode, instance_name = get_instance_mode(search)
    if not instance_name:
        instance_name = "New_" + instance_label(mode)
    return instance_title(mode, instance_name, arch=sim_arch_name(search))

@dash.callback(
    Output({"type": "save-domain-title", "domain_uuid": dash.ALL}, "className"),
    Output({"type": "save-domain-title", "domain_uuid": dash.ALL}, "data-tooltip"),
    Output({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    Input({"type": "save-domain-title", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "domain-title-input", "domain_uuid": dash.ALL}, "value"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State("url", "search"),
    State("odatix-settings", "data"),
)
def update_params_title_save_button(_, title_input, domain_metadata, search, odatix_settings):
    save_classes = []
    tooltips = []
    new_metadata = []

    disabled_class = "color-button invisible icon-button tooltip delay bottom small"
    enabled_class = "color-button warning icon-button tooltip bottom small"
    error_class = "color-button disabled icon-button error-status tooltip bottom small"

    triggered_id = ctx.triggered_id if isinstance(ctx.triggered_id, dict) else {}
    triggered_type = triggered_id.get("type", "")
    triggered_domain_uuid = triggered_id.get("domain_uuid", "")
    
    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    if not instance_name:
        raise dash.exceptions.PreventUpdate

    # The directories of a simulation are named in the simulation settings, not
    # here, so their titles are read-only and there is no main domain to skip.
    if mode == "simulation":
        nothing = [dash.no_update] * len(domain_metadata)
        return (
            ["color-button invisible icon-button tooltip delay bottom small"] * len(domain_metadata),
            ["Parameter directories are named in the simulation settings"] * len(domain_metadata),
            nothing,
        )

    domain_metadata = domain_metadata[1:] # Remove main domain entry
    new_metadata.append(dash.no_update)  # Placeholder for main domain
    for new_domain_name, metadata in zip(title_input, domain_metadata):
        domain_name = metadata.get("domain_name", "")
        domain_uuid = metadata.get("domain_uuid", "")

        # Save button clicked for this domain
        if triggered_type == "save-domain-title" and domain_uuid == triggered_domain_uuid:
            if new_domain_name != domain_name and new_domain_name != "":
                instances.entry(instance_name).domains.rename(domain_name, new_domain_name)

                domain_name = new_domain_name
                save_classes.append(disabled_class)
                tooltips.append("Nothing to save")
                metadata["domain_name"] = new_domain_name
                new_metadata.append(metadata)
            else:
                new_metadata.append(dash.no_update)
                save_classes.append(dash.no_update)
                tooltips.append(dash.no_update)

        # No save button clicked, just check for changes
        else:
            new_metadata.append(dash.no_update)
            if new_domain_name != domain_name:
                invalid_char_found = False
                for c in hard_settings.invalid_filename_characters:
                    if c in new_domain_name:
                        c = "' ' (space)" if c == " " else f"'{c}'"
                        invalid_char_found = True
                        save_classes.append(error_class)
                        tooltips.append(f"Unauthorized character in parameter domain name: {c}")
                        break
                if invalid_char_found:  
                    continue
                if new_domain_name == "" or " " in new_domain_name:
                    save_classes.append(error_class)
                    tooltips.append("Parameter domain name cannot be empty")
                elif new_domain_name in instances.entry(instance_name).domains:
                    save_classes.append(error_class)
                    label = instance_label(mode).lower()
                    tooltips.append(f"Parameter domain '{new_domain_name}' already exists for this {label}")
                else:
                    save_classes.append(enabled_class)
                    tooltips.append("Save new parameter domain name")
            else:
                save_classes.append(disabled_class)
                tooltips.append("Nothing to save")
    return save_classes, tooltips, new_metadata


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id="url"),
        html.Div(id={"page": page_path, "type": "instance-title-div"}, style={"marginTop": "20px"}),
        # What this page does, said once, above every domain of it -- folded
        # away, since it is only ever read once.
        html.Div(
            html.Div(
                replacement_help.help_section("page"),
                className="tile title",
                style={"marginTop": "10px"},
            ),
            className="card-matrix config",
        ),
        html.Div(id="param-domains-section", style={"marginBottom": "10px"}),
        dcc.Store(id="param-domains-section-initialized", data=False),
        dcc.Store(id="param-domains-section-update", data=""),
        # Bumped when a section of a "?sim=&arch=" page comes to point at
        # another domain or another directory: what it holds is then read from
        # somewhere else, so the sections are built again.
        dcc.Store(id="sim-arch-reload", data=0),
        # Typing in a configuration does not reach the server: this store does,
        # once the typing stops, naming the domains whose preview is now stale.
        dcc.Store(id="config-content-debounce", data=None),
    ],
    className="page-content",
    style={
        "padding": "0",
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

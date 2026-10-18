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
import uuid

import dash
from dash import html, dcc, Input, Output, State, ctx, ALL, MATCH, Patch

from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
import odatix.gui.ui_components as ui
from odatix.gui.css_helper import Style
import odatix.gui.navigation as navigation
import odatix.lib.eda_tools as eda_tools
from odatix.gui.utils import get_workspace
from odatix.gui.page_scope import page_callback, scoped
from odatix.workspace.entries import check_name
from odatix.workspace.errors import InvalidNameError

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "select_targets"

page_path = "/select_targets"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Target selection',
    name='Select targets',
    order=3,
)

save_button_disabled = "color-button disabled icon-button"
save_button_enabled = "color-button warning icon-button tooltip delay bottom auto caution"


def get_tool_display_name(tool):
    if not tool:
        return ""
    # Use the tool's own "label" (from tool.yml) when it is a discovered tool,
    # otherwise fall back to a prettified version of its identifier.
    if eda_tools.is_supported(tool):
        return eda_tools.get_tool_label(tool)
    return tool.replace("_", " ").title()


######################################
# UI Components
######################################

def card_metadata(target, new=False, source=""):
    """
    What a card remembers of the file, to tell an edit from the saved state:
    the target as the file holds it, or, for a card added on the page and not
    saved yet, nothing but where it comes from ("source": the target it
    duplicates, whose other per-target settings it takes along).
    """
    if new:
        return {"name": str(source or ""), "new": True}
    return {
        "name": target["name"],
        "enabled": target.get("enabled", True),
        "script_copy_enable": bool(target.get("script_copy_enable", False)),
        "script_copy_source": str(target.get("script_copy_source", "") or ""),
        "new": False,
    }


def target_card(target, key=None, metadata=None):
    """
    Card of one target. "key" tells the card apart in the ids of its fields: the
    name of the target in the file by default, a key of its own for a card
    added on the page (its name is the user's to change, and may be taken by a
    renamed card already).
    """
    name = target["name"]
    key = key or name
    enabled = target.get("enabled", True)
    extra_fields_open = bool(target.get("script_copy_enable", False)) or str(target.get("script_copy_source", "")).strip() != ""

    return html.Div([
        html.Div([
            dcc.Input(
                value=name,
                type="text",
                id={"type": "target-title", "name": key},
                className="title-input",
                style={
                    "width": "calc(100% - var(--tile-gap))",
                    "marginLeft": "5px",
                    "marginRight": "5px",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "marginTop": "-5px",
                    "marginBottom": "2px",
                    "textAlign": "center",
                },
            )
        ]),
        dcc.Store(id={"type": "target-metadata", "name": key}, data=metadata or card_metadata(target)),
        html.Div([
            html.Div([
                dcc.Checklist(
                    options=[{"label": "Enable", "value": True}],
                    value=[True] if enabled else [],
                    id={"type": "target-enable", "name": key},
                    className="checklist-switch",
                    style={"marginBottom": "12px", "marginTop": "10px", "marginLeft": "5px", "display": "inline-block"},
                ),
            ]),
            html.Div([
                html.Div([
                    ui.icon_button(
                        icon=icon(
                            "more",
                            className="icon normal rotate rotated" if extra_fields_open else "icon normal rotate",
                            id={"type": "target-more-icon", "name": key},
                        ),
                        color="default",
                        id={"type": "target-more", "name": key},
                        tooltip="Script copy settings",
                        tooltip_options="bottom small",
                    )
                ], style={"display": "flex", "alignItems": "center"}),
                ui.duplicate_button(id={"type": "target-duplicate", "name": key}, tooltip="Duplicate this target"),
                ui.delete_button(id={"type": "target-delete", "name": key}, tooltip="Remove this target"),
            ], style={"display": "flex", "alignItems": "center", "marginLeft": "0px"}, className="inline-flex-buttons"),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
        # Extra fields: optional per-target settings (target_settings.<name> in the yaml)
        html.Div([
            html.Div([
                html.Div(
                    [
                        html.Span("Script copy"),
                        ui.tooltip_icon(
                            "A script of yours (a technology setup, a library list...) copied into the job "
                            "directory of every job run on this target.",
                            tooltip_options="secondary small",
                        ),
                    ],
                    className="odx-field-label",
                ),
                dcc.Checklist(
                    options=[{"label": "Copy a script into each job", "value": True}],
                    value=[True] if target.get("script_copy_enable", False) else [],
                    id={"type": "target-script-copy-enable", "name": key},
                    className="checklist-switch",
                    style={"marginTop": "5px", "marginLeft": "5px"},
                ),
                html.Div("Script to copy", className="odx-field-label", style={"marginTop": "10px"}),
                # A long path is cut by the field: hovering it shows it whole
                # (dcc.Input takes no title of its own).
                html.Div(
                    dcc.Input(
                        value=target.get("script_copy_source", ""),
                        type="text",
                        placeholder="/path/to/script",
                        id={"type": "target-script-copy-source", "name": key},
                        className="value-input",
                        style={
                            "width": "calc(100% - var(--tile-gap))",
                            "marginLeft": "5px",
                            "marginRight": "5px",
                            "marginBottom": "5px",
                            "fontSize": "0.9em",
                        },
                    ),
                    title=str(target.get("script_copy_source", "") or ""),
                ),
            ], style={"marginTop": "5px", "textAlign": "left"}),
        ],
        id={"type": "target-extra-div", "name": key},
        style=Style.visible_div if extra_fields_open else Style.hidden,
        ),
    ],
    className="card configs" + ("" if enabled else " target-disabled"),
    id={"type": "target-card", "name": key},
    style={
        "padding": "10px",
        "margin": "5px",
        "display": "inline-block",
        "verticalAlign": "top",
        "boxSizing": "border-box",
    })


def add_card(text: str = "Add new target"):
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "paddingTop": "0px"}),
                    html.Div(
                        "+",
                        style={
                            "fontSize": "2.5em",
                            "lineHeight": "80px",
                            "height": "80px",
                            "marginTop": "-15px",
                            "marginBottom": "-15px",
                        }
                    ),
                ],
                style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
            ),
            id="add-target-card",
            n_clicks=0,
            style={"textDecoration": "none", "height": "100%"},
        ),
        className="card configs add hover",
        style={
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box",
        },
    )


def build_cards(search, odatix_settings):
    tool = get_key_from_url(search, "tool")
    if not tool:
        return [html.Div(
            "No tool selected. Open this page with ?tool=<tool> (e.g. from the Run jobs page).",
            className="error-message",
            style={"width": "100%", "marginTop": "20px"},
        )]
    cards = [target_card(target.to_dict()) for target in get_workspace(odatix_settings).targets[tool]]
    cards.append(add_card())
    return cards


def saved_names(search, odatix_settings):
    """The targets of the file, in its order: what the cards are compared to."""
    tool = get_key_from_url(search, "tool")
    if not tool:
        return []
    return get_workspace(odatix_settings).targets[tool].names()


def empty_message(search, odatix_settings):
    """
    What the page says above the "add" card of a tool without any target yet:
    a run needs one, and where it will be written.
    """
    tool = get_key_from_url(search, "tool")
    if not tool:
        return ""
    target_file = get_workspace(odatix_settings).targets[tool]
    if target_file.names():
        return ""
    return (
        f"{get_tool_display_name(tool)} has no target yet: add one (its name is passed to the tool as the part, "
        f"technology or platform to implement on), then save. It is written to {os.path.basename(target_file.path)}."
    )


######################################
# Callbacks
######################################

def tool_settings_values(search, odatix_settings):
    """
    The settings of the tool held by its target file (constraint file, install
    path, single thread), as the fields of the page show them.
    """
    tool = get_key_from_url(search, "tool")
    if not tool:
        return {"constraint_file": "", "tool_install_path": "", "force_single_thread": False}
    target_file = get_workspace(odatix_settings).targets[tool]
    settings = target_file.settings()
    if not target_file.exists:
        # What saving will write: a new target file spells its settings out.
        from odatix.lib.prepare_work import DEFAULT_CONSTRAINT_FILE

        settings = {"constraint_file": DEFAULT_CONSTRAINT_FILE}
    return {
        "constraint_file": str(settings.get("constraint_file") or ""),
        "tool_install_path": str(settings.get("tool_install_path") or ""),
        "force_single_thread": bool(target_file.force_single_thread),
    }


#: Said under the install path field when the tool.yml of the tool does not
#: say what to put there.
GENERIC_INSTALL_PATH_HINT = (
    "Given to the commands of the tool as $tool_install_path. "
    "Leave it empty when the tool is on your PATH."
)


def install_path_field(tool, value):
    """
    How the install path field shows for a tool: (style of the field, hint
    under it, placeholder). It is hidden for a tool that never reads the path
    (Vivado, Design Compiler... are found on the PATH only), unless the file
    already sets one, which can then still be cleared.
    """
    if not tool or not eda_tools.is_supported(tool):
        return Style.hidden, "", ""
    if not eda_tools.reads_install_path(tool) and not str(value or "").strip():
        return Style.hidden, "", ""
    hint = eda_tools.install_path_hint(tool)
    if hint:
        text = (
            f"{hint}. Used only when the tool is not on your PATH: "
            "a tool found on the PATH is always used first."
        )
        placeholder = "Empty: the tool is on your PATH"
    else:
        text = GENERIC_INSTALL_PATH_HINT
        placeholder = "Empty: the tool is on your PATH"
    if not eda_tools.reads_install_path(tool):
        text = f"{get_tool_display_name(tool)} does not read this path: it is found on your PATH. Clear it."
    return {"display": "block"}, text, placeholder


# Load the page content from the url (?tool=<tool>)
@dash.callback(
    Output("target-cards-row", "children"),
    Output("select-targets-title", "children"),
    Output("target-constraint-file", "value"),
    Output("target-install-path", "value"),
    Output("target-single-thread", "value"),
    Output("target-tool-settings", "data"),
    Output("select-targets-back", "href"),
    Output("target-saved-names", "data"),
    Output("target-empty-message", "children"),
    Output("target-install-path-field", "style"),
    Output("target-install-path-hint", "children"),
    Output("target-install-path", "placeholder"),
    Output("target-order", "data"),
    Input(f"url_{page_path}", "search"),
    State("odatix-settings", "data"),
)
def load_page(search, odatix_settings):
    tool = get_key_from_url(search, "tool")
    title = f"{get_tool_display_name(tool)} targets" if tool else "Targets"
    values = tool_settings_values(search, odatix_settings)
    field_style, hint, placeholder = install_path_field(tool, values["tool_install_path"])
    names = saved_names(search, odatix_settings)
    return (
        build_cards(search, odatix_settings),
        title,
        values["constraint_file"],
        values["tool_install_path"],
        [True] if values["force_single_thread"] else [],
        values,
        back_link(search),
        names,
        empty_message(search, odatix_settings),
        field_style,
        hint,
        placeholder,
        # Cards of the file are keyed by their name (see target_card).
        names,
    )


def back_link(search):
    """
    Where the back arrow leads: the page given by "?back=" (the run page that
    opened this one passes itself), or the choice of a job type otherwise.
    Only a path of this app is followed, never another site.
    """
    back = get_key_from_url(search, "back")
    if isinstance(back, str) and back.startswith("/") and not back.startswith("//"):
        return back
    return "/choose_job_type"


def tool_settings_changed(constraint_file, install_path, single_thread, loaded):
    """Whether the tool settings fields differ from what the file holds."""
    loaded = loaded if isinstance(loaded, dict) else {}
    return (
        str(constraint_file or "").strip() != str(loaded.get("constraint_file", ""))
        or str(install_path or "").strip() != str(loaded.get("tool_install_path", ""))
        or bool(single_thread) != bool(loaded.get("force_single_thread", False))
    )


def targets_changed(titles, enables, script_copy_enables, script_copy_sources, metadata, saved):
    """
    Whether the cards differ from the file: a card added (or duplicated) and not
    saved yet, a card removed, or an edited field.
    """
    metadata = [meta or {} for meta in (metadata or [])]
    if any(meta.get("new") for meta in metadata):
        return True
    if [meta.get("name", "") for meta in metadata] != list(saved or []):
        return True
    for i, meta in enumerate(metadata):
        if str(titles[i] or "") != str(meta.get("name", "")):
            return True
        if bool(enables[i]) != bool(meta.get("enabled", True)):
            return True
        if bool(script_copy_enables[i]) != bool(meta.get("script_copy_enable", False)):
            return True
        if str(script_copy_sources[i] or "") != str(meta.get("script_copy_source", "")):
            return True
    return False


def targets_to_save(titles, enables, script_copy_enables, script_copy_sources, metadata):
    """
    The target list the cards stand for, ready for TargetFile.targets. Refuses
    (ValueError, saying why) a list that the file could not hold as shown: an
    empty name, a name that is not a valid one, or two targets of the same name,
    one of which would silently disappear.
    """
    targets = []
    seen = set()
    for i, meta in enumerate(metadata or []):
        meta = meta or {}
        name = str(titles[i] or "").strip()
        try:
            check_name(name, "target")
        except InvalidNameError as e:
            raise ValueError(str(e))
        if name in seen:
            raise ValueError(f"two targets are named '{name}'.")
        seen.add(name)
        targets.append({
            "name": name,
            # A new card carries the settings of the target it duplicates.
            "original_name": meta.get("name", "") or name,
            "enabled": bool(enables[i]),
            "script_copy_enable": bool(script_copy_enables[i]),
            "script_copy_source": str(script_copy_sources[i] or ""),
        })
    return targets


def card_values():
    """
    The fields of the cards, as {field type: {card key: value}}, read from the
    callback context. Dash does not promise the lists of a wildcard in the
    order of the page once cards were inserted or removed: each value is matched
    to its card by the key in its id instead, and the order of the cards is the
    one the page keeps ("target-order").
    """
    values = {}
    for group in list(ctx.inputs_list or []) + list(ctx.states_list or []):
        if not isinstance(group, list):
            continue
        for item in group:
            ident = item.get("id") if isinstance(item, dict) else None
            if isinstance(ident, dict) and "type" in ident and "name" in ident:
                values.setdefault(ident["type"], {})[ident["name"]] = item.get("value")
    return values


def ordered_fields(order, values):
    """
    (titles, enables, script copy enables, script copy sources, metadata) of
    the cards, in the order of the page. A card the order misses goes last.
    """
    titles = values.get("target-title", {})
    keys = [key for key in (order or []) if key in titles]
    keys += [key for key in titles if key not in keys]
    return tuple(
        [values.get(field, {}).get(key) for key in keys]
        for field in ("target-title", "target-enable", "target-script-copy-enable",
                      "target-script-copy-source", "target-metadata")
    )


# Folding the extra fields away is done on the client, on the document, by the
# handler in assets/folds.js: nothing outside the browser reads whether a fold
# is open, and a fold answered by Dash costs a walk over every pattern-matched
# component of the page.


# Dim the card when the target is disabled
@page_callback(PAGE_SCOPE,
    Output({"type": "target-card", "name": MATCH}, "className"),
    Input({"type": "target-enable", "name": MATCH}, "value"),
    prevent_initial_call=True,
)
def update_card_enabled_style(enable_value):
    return "card configs" if enable_value else "card configs target-disabled"


# Enable the save button on any edit, save all changes on click
@page_callback(PAGE_SCOPE,
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output("target-cards-row", "children", allow_duplicate=True),
    Output("target-feedback", "children"),
    Output("target-tool-settings", "data", allow_duplicate=True),
    Output("target-saved-names", "data", allow_duplicate=True),
    Output("target-empty-message", "children", allow_duplicate=True),
    Output("target-order", "data", allow_duplicate=True),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input({"type": "target-title", "name": ALL}, "value"),
    Input({"type": "target-enable", "name": ALL}, "value"),
    Input({"type": "target-script-copy-enable", "name": ALL}, "value"),
    Input({"type": "target-script-copy-source", "name": ALL}, "value"),
    Input("target-constraint-file", "value"),
    Input("target-install-path", "value"),
    Input("target-single-thread", "value"),
    Input({"type": "target-metadata", "name": ALL}, "data"),
    State("target-tool-settings", "data"),
    State("target-saved-names", "data"),
    State("target-order", "data"),
    State(f"url_{page_path}", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_or_mark_dirty(save_n_clicks, _titles, _enables, _script_copy_enables, _script_copy_sources,
                       constraint_file, install_path, single_thread, _metadata, loaded_settings, saved,
                       order, search, odatix_settings):
    trigger_id = ctx.triggered_id
    unchanged = (dash.no_update,) * 6
    titles, enables, script_copy_enables, script_copy_sources, metadata = ordered_fields(order, card_values())

    if trigger_id == {"page": page_path, "action": "save-all"}:
        if not save_n_clicks:
            return (dash.no_update,) + unchanged
        tool = get_key_from_url(search, "tool")
        if not tool:
            return (dash.no_update,) + unchanged
        try:
            targets = targets_to_save(titles, enables, script_copy_enables, script_copy_sources, metadata)
        except ValueError as e:
            return ("color-button error-status icon-button", dash.no_update,
                    ui.error(f"Not saved: {e}"), dash.no_update, dash.no_update, dash.no_update, dash.no_update)
        target_file = get_workspace(odatix_settings).targets[tool]
        # Only what changed is written: a file that leaves a key out keeps
        # leaving it out (and its default applying).
        if tool_settings_changed(constraint_file, install_path, single_thread, loaded_settings):
            loaded = loaded_settings if isinstance(loaded_settings, dict) else {}
            changes = {}
            if str(constraint_file or "").strip() != str(loaded.get("constraint_file", "")):
                changes["constraint_file"] = str(constraint_file or "").strip()
            if str(install_path or "").strip() != str(loaded.get("tool_install_path", "")):
                changes["tool_install_path"] = str(install_path or "").strip()
            if bool(single_thread) != bool(loaded.get("force_single_thread", False)):
                changes["force_single_thread"] = bool(single_thread)
            target_file.update(save=False, **changes)
        target_file.targets = targets
        try:
            target_file.save()
        except Exception as e:
            return (save_button_enabled, dash.no_update, ui.error(f"Targets not saved: {e}"),
                    dash.no_update, dash.no_update, dash.no_update, dash.no_update)
        names = saved_names(search, odatix_settings)
        return (
            save_button_disabled,
            build_cards(search, odatix_settings),
            ui.success(),
            tool_settings_values(search, odatix_settings),
            names,
            empty_message(search, odatix_settings),
            names,
        )

    # Any other trigger: compare current values against the loaded metadata
    if tool_settings_changed(constraint_file, install_path, single_thread, loaded_settings) or targets_changed(
        titles, enables, script_copy_enables, script_copy_sources, metadata, saved
    ):
        return (save_button_enabled,) + unchanged
    return (save_button_disabled,) + unchanged


def free_name(base, taken):
    """The first name of base1, base2... that is not taken, or None."""
    for i in range(1, 1001):
        candidate = f"{base}{i}"
        if candidate not in taken:
            return candidate
    return None


def is_new_click(timestamp, last_click):
    """
    Whether a click timestamp is one no callback of the page has handled yet.

    Inserting or removing a card changes the children of the row, and Dash then
    calls again the callbacks listening to the buttons in it, with the clicks
    they already had: without this, every card added would add another one.
    """
    return bool(timestamp) and timestamp > 0 and timestamp > (last_click or 0)


# Add a new target: a card on the page, written to the file by "Save all" only
@dash.callback(
    Output("target-cards-row", "children", allow_duplicate=True),
    Output("target-feedback", "children", allow_duplicate=True),
    Output("target-empty-message", "children", allow_duplicate=True),
    Output("target-last-click", "data", allow_duplicate=True),
    Output("target-order", "data", allow_duplicate=True),
    Input("add-target-card", "n_clicks_timestamp"),
    State("target-last-click", "data"),
    State({"type": "target-title", "name": ALL}, "value"),
    State("target-order", "data"),
    State(f"url_{page_path}", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def handle_add_target(timestamp, last_click, titles, order, search, odatix_settings):
    nothing = (dash.no_update,) * 5
    if not is_new_click(timestamp, last_click):
        return nothing
    tool = get_key_from_url(search, "tool")
    if not tool:
        return nothing
    # Neither a name on the page nor one of the file (a card renamed but not
    # saved yet still holds its old name there).
    taken = set(str(title or "").strip() for title in titles or []) | set(saved_names(search, odatix_settings))
    candidate = free_name("new_target_", taken)
    if candidate is None:
        return (dash.no_update, ui.error("No target added: new_target_1 to new_target_1000 are all taken."),
                dash.no_update, timestamp, dash.no_update)

    order = list(order or [])
    key = "new-" + uuid.uuid4().hex
    cards = Patch()
    # Last card of the row is the "add" card: the new target goes before it.
    cards.insert(len(order), target_card(
        {"name": candidate, "enabled": True},
        key=key,
        metadata=card_metadata(None, new=True),
    ))
    return cards, "", "", timestamp, order + [key]


# Duplicate a target: a copy of the card as it is now, saved by "Save all"
@page_callback(PAGE_SCOPE,
    Output("target-cards-row", "children", allow_duplicate=True),
    Output("target-feedback", "children", allow_duplicate=True),
    Output("target-last-click", "data", allow_duplicate=True),
    Output("target-order", "data", allow_duplicate=True),
    Input({"type": "target-duplicate", "name": ALL}, "n_clicks_timestamp"),
    State("target-last-click", "data"),
    State({"type": "target-duplicate", "name": ALL}, "id"),
    State({"type": "target-title", "name": ALL}, "value"),
    State({"type": "target-enable", "name": ALL}, "value"),
    State({"type": "target-script-copy-enable", "name": ALL}, "value"),
    State({"type": "target-script-copy-source", "name": ALL}, "value"),
    State({"type": "target-metadata", "name": ALL}, "data"),
    State("target-order", "data"),
    State(f"url_{page_path}", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def handle_duplicate_target(timestamps, last_click, btn_ids, _titles, _enables, _script_copy_enables,
                            _script_copy_sources, _metadata, order, search, odatix_settings):
    nothing = (dash.no_update,) * 4
    if not timestamps or not btn_ids:
        return nothing

    idx = max(range(len(timestamps)), key=lambda i: timestamps[i] or 0)
    if not is_new_click(timestamps[idx], last_click):
        return nothing
    source_key = btn_ids[idx]["name"]
    values = card_values()
    titles = values.get("target-title", {})
    order = list(order or [])
    if source_key not in titles or source_key not in order:
        return nothing

    name = str(titles[source_key] or "").strip() or "target"
    taken = set(str(title or "").strip() for title in titles.values()) | set(saved_names(search, odatix_settings))
    candidate = free_name(f"{name}_copy", taken)
    if candidate is None:
        return (dash.no_update, ui.error(f"Target '{name}' not duplicated: {name}_copy1 to {name}_copy1000 are all taken."),
                timestamps[idx], dash.no_update)

    source = values.get("target-metadata", {}).get(source_key) or {}
    key = "new-" + uuid.uuid4().hex
    position = order.index(source_key) + 1
    cards = Patch()
    cards.insert(position, target_card(
        {
            "name": candidate,
            "enabled": bool(values.get("target-enable", {}).get(source_key)),
            "script_copy_enable": bool(values.get("target-script-copy-enable", {}).get(source_key)),
            "script_copy_source": str(values.get("target-script-copy-source", {}).get(source_key) or ""),
        },
        key=key,
        # The copy takes along the other per-target settings of its source,
        # as the file has them.
        metadata=card_metadata(None, new=True, source=source.get("name", "")),
    ))
    return cards, "", timestamps[idx], order[:position] + [key] + order[position:]


# Ask before removing a target
@page_callback(PAGE_SCOPE,
    Output("target-delete-popup", "className"),
    Output("target-delete-popup-message", "children"),
    Output("target-delete-info", "data"),
    Output("target-last-click", "data", allow_duplicate=True),
    Input({"type": "target-delete", "name": ALL}, "n_clicks_timestamp"),
    State("target-last-click", "data"),
    State({"type": "target-delete", "name": ALL}, "id"),
    State({"type": "target-title", "name": ALL}, "value"),
    State({"type": "target-title", "name": ALL}, "id"),
    prevent_initial_call=True,
)
def show_delete_popup(timestamps, last_click, btn_ids, titles, title_ids):
    if not timestamps or not btn_ids:
        return (dash.no_update,) * 4
    idx = max(range(len(timestamps)), key=lambda i: timestamps[i] or 0)
    if not is_new_click(timestamps[idx], last_click):
        return (dash.no_update,) * 4
    key = btn_ids[idx]["name"]
    name = next((titles[i] for i, item in enumerate(title_ids or []) if item.get("name") == key), key)
    msg = f"Remove target '{name}'?"
    return "overlay-odatix visible", msg, {"key": key}, timestamps[idx]


# Close the delete confirmation popup
@dash.callback(
    Output("target-delete-popup", "className", allow_duplicate=True),
    Input("target-delete-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_delete_popup(n_clicks):
    return "overlay-odatix"


# Remove a target: its card goes, the file loses it on "Save all"
@dash.callback(
    Output("target-delete-popup", "className", allow_duplicate=True),
    Output("target-delete-error", "children"),
    Output("target-cards-row", "children", allow_duplicate=True),
    Output("target-order", "data", allow_duplicate=True),
    Input("target-delete-confirm-btn", "n_clicks"),
    State("target-delete-info", "data"),
    State("target-order", "data"),
    prevent_initial_call=True,
)
def do_delete_target(n_clicks, info, order):
    if not n_clicks or not info:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    order = list(order or [])
    if info.get("key") not in order:
        return dash.no_update, ui.error("Target not found."), dash.no_update, dash.no_update
    position = order.index(info["key"])
    cards = Patch()
    del cards[position]
    return "overlay-odatix", "", cards, order[:position] + order[position + 1:]


######################################
# Layout
######################################

title_buttons = html.Div(
    children=[
        ui.save_button(
            id={"page": page_path, "action": "save-all"},
            tooltip="Save all changes",
            disabled=True,
        ),
    ],
    className="inline-flex-buttons",
)


layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}", refresh=False),
        ui.title_tile(
            "Targets", id="select-targets-title", buttons=title_buttons,
            # href set from the url by load_page (see back_link)
            back_button_link="/choose_job_type", back_button_id="select-targets-back",
            style={"marginTop": "10px", "marginBottom": "20px"},
        ),
        ui.feedback("target-feedback", className="centered"),
        # The settings of the tool the target file holds besides its targets.
        dcc.Store(id="target-tool-settings"),
        # The targets of the file, in its order: a card added or removed on the
        # page shows against it.
        dcc.Store(id="target-saved-names", data=[]),
        # Newest click handled by add, duplicate or remove (see is_new_click).
        dcc.Store(id="target-last-click", data=0),
        # Keys of the cards, in the order of the page (see card_values).
        dcc.Store(id="target-order", data=[]),
        # Same width as the title tile and the grid of cards, rather than the
        # whole window.
        html.Div(
            ui.panel(
                title="Tool settings",
                className="target-tool-settings",
                body=ui.grid([
                    ui.form_field(
                        "Constraint file",
                        id="target-constraint-file",
                        placeholder="constraints.sdc",
                        tooltip="File of the job directory holding the clock constraint at the target frequency. "
                                "Odatix writes it as SDC before the job runs; the scripts of a tcl tool rewrite it in "
                                "their own format. Empty: constraints.sdc.",
                    ),
                    html.Div(
                        [
                            ui.form_field(
                                "Tool install path",
                                id="target-install-path",
                                placeholder="Empty: the tool is on your PATH",
                                tooltip="Where the tool is installed, for a tool that is not on your PATH. "
                                        "Only the tools whose commands use $tool_install_path read it; "
                                        "a tool found on the PATH is used first.",
                            ),
                            html.Div(id="target-install-path-hint", className="target-field-hint"),
                        ],
                        id="target-install-path-field",
                        style=Style.hidden,
                    ),
                    ui.inline_switch(
                        "Force single thread",
                        id="target-single-thread",
                        tooltip="Make each job of this tool run on a single thread (Vivado: maxThreads 1, "
                                "LibreLane: -j 1). Jobs still run in parallel: useful when many parallel jobs, "
                                "each taking several threads, oversubscribe the processor.",
                    ),
                ]),
            ),
            className="card-matrix configs target-settings-row",
        ),
        html.Div(id="target-empty-message", className="target-empty-message"),
        html.Div(id="target-section", style={"marginBottom": "10px"}, children=[
            html.Div(
                id="target-cards-row",
                className="card-matrix configs",
            ),
        ]),
        dcc.Store(id="target-delete-info"),
        html.Div(
            id="target-delete-popup",
            className="overlay-odatix",
            children=[
                html.Div([
                    html.H2("Remove target"),
                    html.Div(id="target-delete-popup-message"),
                    html.Div(
                        "Its card goes now, and the target leaves the target file, with its settings, "
                        "when you save all. Disable it instead if you may need it later.",
                        className="target-delete-note",
                    ),
                    html.Div([
                        ui.icon_button(
                            icon=icon("delete", className="icon"),
                            color="caution",
                            text="Remove",
                            width="100px",
                            id="target-delete-confirm-btn",
                        ),
                        html.Button("Cancel", id="target-delete-cancel-btn", n_clicks=0, style={"marginLeft": "10px", "width": "90px"}),
                    ], style={"marginTop": "18px", "display": "flex", "justifyContent": "center"}),
                    ui.feedback("target-delete-error"),
                ], className="popup-odatix")
            ]
        ),
    ],
    className="page-content",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

# Anchor of PAGE_SCOPE: makes this page the only one dispatching its callbacks.
layout = scoped(PAGE_SCOPE, layout)

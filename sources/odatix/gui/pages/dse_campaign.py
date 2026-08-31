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

"""
The editor of one campaign: what evaluating a design runs, what makes a design
good, and how long to look for it.

It edits one file of the campaign directory and nothing else (see
:class:`odatix.dse.settings.CampaignSettings`); which campaigns actually run is
the other page's business ("/dse").
"""

import dash
from dash import ALL, ctx, dcc, html, Input, Output, State

import odatix.gui.navigation as navigation
import odatix.gui.ui_components as ui
from odatix.gui.icons import icon
from odatix.gui.page_scope import page_callback, scoped
from odatix.gui.utils import get_workspace

from odatix.gui.dse_config import form
from odatix.gui.dse_config.common import (
    MODE_OPTIONS,
    RUN_OPTIONS,
    STRATEGY_OPTIONS,
    architecture_entries,
    architecture_options,
    campaign_names,
    checked,
    constraint_entries,
    delete_campaign,
    dse_settings,
    editor_path,
    flow_options,
    from_names,
    int_list,
    int_list_text,
    metric_names,
    objective_entries,
    page_path,
    read_campaign,
    save_campaign,
    save_dse_settings,
    simulation_options,
    target_options,
    to_int,
    to_float,
    to_names,
    tool_options,
    unique_campaign_name,
)

PAGE_SCOPE = "dse_campaign"

SAVE_IDLE = "color-button disabled icon-button tooltip delay bottom auto"
SAVE_DIRTY = "color-button warning icon-button tooltip delay bottom auto caution"


######################################
# UI Components
######################################

def _panel_caption(text, tooltip=""):
    return ui.caption(text, tooltip)


def _what_runs_panel(workspace, campaign):
    tools = to_names(campaign.tool)
    run_mode = campaign.run or "fmax_synthesis"
    return html.Div([
        _panel_caption("What evaluating one design runs"),
        ui.form_dropdown(
            "Command", "dse-editor-run", RUN_OPTIONS, value=run_mode,
            clearable=False,
            tooltip="What each evaluation of the search runs on the design it chose.",
        ),
        ui.form_dropdown(
            "EDA tools", "dse-editor-tools", tool_options(), value=tools, multi=True,
            placeholder="the tool the evaluations run with",
            tooltip="One tool, or several: naming several makes what runs a design "
                    "one more thing the search chooses.",
        ),
        ui.form_dropdown(
            "Flows", "dse-editor-flows", flow_options(tools, run_mode),
            value=to_names(campaign.flow), multi=True,
            placeholder="the default flow of each tool",
            tooltip="Flow of that tool. Empty: the default flow of each tool.",
        ),
        ui.form_dropdown(
            "Targets", "dse-editor-targets", target_options(workspace, tools),
            value=to_names(campaign.target), multi=True,
            placeholder="every target the tool enables",
            tooltip="Targets the evaluations run on. Naming several makes the target "
                    "an axis of the search.",
        ),
        ui.form_dropdown(
            "Simulations", "dse-editor-simulations", simulation_options(workspace),
            value=campaign.simulation_names(), multi=True,
            placeholder="none",
            tooltip="Simulations every design is run through before it is measured.",
        ),
    ], className="odx-panel padded", id="dse-editor-what-runs")


def _frequencies_panel(campaign):
    frequencies = campaign.frequencies
    visible = campaign.run == "custom_freq_synthesis"
    return html.Div([
        _panel_caption(
            "Frequencies",
            "A custom frequency synthesis is the one run that is told a frequency: "
            "either it is fixed here, or the search chooses it like a parameter.",
        ),
        html.Div(
            ui.switch_row(
                "Search the frequency too", "dse-editor-freq-explore",
                checked=bool(frequencies.explore),
                tooltip="Each design gets a frequency of its own, chosen in the range below.",
            ),
            className="odx-switch-stack",
        ),
        ui.form_field(
            "Frequencies (MHz)", "dse-editor-freq-list",
            value=int_list_text(frequencies.frequencies),
            type="text", placeholder="100, 200, 300",
            tooltip="Every design is synthesized at each of those, when the frequency "
                    "is not searched.",
        ),
        html.Div([
            ui.form_field("From (MHz)", "dse-editor-freq-from", value=str(frequencies.range.start or ""), type="number", style={"flex": "1"}),
            ui.form_field("To (MHz)", "dse-editor-freq-to", value=str(frequencies.range.stop or ""), type="number", style={"flex": "1"}),
            ui.form_field("Step (MHz)", "dse-editor-freq-step", value=str(frequencies.range.step or ""), type="number", style={"flex": "1"}),
        ], className="odx-field-row"),
    ],
        className="odx-panel padded",
        id="dse-editor-frequencies",
        style={"display": "block" if visible else "none"},
    )


def _search_panel(campaign):
    search = campaign.search
    strategy = search.strategy or "genetic"
    return html.Div([
        _panel_caption("How the search looks for it"),
        html.Div([
            ui.form_dropdown("Strategy", "dse-editor-strategy", STRATEGY_OPTIONS, value=strategy, clearable=False, style={"flex": "1"},
                             tooltip="How the next designs to evaluate are chosen."),
            ui.form_dropdown("Mode", "dse-editor-mode", MODE_OPTIONS, value=search.mode or "batch", clearable=False, style={"flex": "1"},
                             tooltip="Continuous starts a new design the moment a slot frees, "
                                     "instead of waiting for the whole batch."),
        ], className="odx-field-row"),
        html.Div([
            ui.form_field("Budget", "dse-editor-budget", value=str(search.budget), type="number", style={"flex": "1"},
                          tooltip="How many designs are evaluated at most, per architecture."),
            ui.form_field("Batch", "dse-editor-batch", value=str(search.batch), type="number", style={"flex": "1"},
                          tooltip="How many designs are evaluated together, between two decisions."),
        ], className="odx-field-row"),
        html.Div([
            ui.form_field("Patience", "dse-editor-patience", value=str(search.patience), type="number", style={"flex": "1"},
                          tooltip="Stop after this many batches that do not improve the front (0: never)."),
            ui.form_field("Improvement", "dse-editor-improvement", value=str(search.improvement or 0), type="number", style={"flex": "1"},
                          tooltip="How much the front has to grow for a batch to count (0.02: 2%)."),
            ui.form_field("Seed", "dse-editor-seed", value="" if search.seed is None else str(search.seed), type="number", style={"flex": "1"},
                          tooltip="Empty: a different search every time."),
        ], className="odx-field-row"),
        html.Div([
            _panel_caption("Genetic search"),
            html.Div([
                ui.form_field("Mutation", "dse-editor-mutation", value="" if search.mutation in (None, "") else str(search.mutation), type="number", style={"flex": "1"},
                              tooltip="How often a parameter is changed when a design is derived from "
                                      "another. Empty: one parameter per design on average."),
                ui.form_field("Tournament", "dse-editor-tournament", value=str(search.tournament), type="number", style={"flex": "1"},
                              tooltip="How many designs a parent is picked out of."),
                ui.form_field("Population", "dse-editor-population", value="" if search.population is None else str(search.population), type="number", style={"flex": "1"},
                              tooltip="How many designs the search keeps to look around. Empty: four batches' worth."),
            ], className="odx-field-row"),
        ], id="dse-editor-genetic", style={"display": "block" if strategy == "genetic" else "none"}),
        html.Div([
            _panel_caption("Bayesian search"),
            html.Div([
                ui.form_field("Candidates", "dse-editor-candidates", value="" if search.candidates is None else str(search.candidates), type="number", style={"flex": "1"},
                              tooltip="How many candidates the acquisition compares before choosing one. Empty: 300."),
                ui.form_field("Samples", "dse-editor-samples", value="" if search.samples is None else str(search.samples), type="number", style={"flex": "1"},
                              tooltip="How many Monte Carlo draws value a candidate. Empty: 12."),
            ], className="odx-field-row"),
            html.Div(
                ui.switch_row(
                    "One model per constraint", "dse-editor-constraint-models",
                    checked=bool(search.constraint_models),
                    tooltip="Finer, but one more model to fit on every refit.",
                ),
                className="odx-switch-stack",
            ),
        ], id="dse-editor-bayesian", style={"display": "block" if strategy == "bayesian" else "none"}),
    ], className="odx-panel padded")


def _start_panel(campaign):
    return html.Div([
        _panel_caption("What the search starts from"),
        html.Div(
            ui.switch_row(
                "Reuse results already measured", "dse-editor-reuse",
                checked=bool(campaign.reuse_results),
                tooltip="Designs of this space that any run already measured are given to "
                        "the search for free, instead of being evaluated again.",
            ),
            className="odx-switch-stack",
        ),
    ], className="odx-panel padded")


def _list_section(title, tooltip, container_id, add_id, add_text, rows):
    return ui.section(
        title,
        html.Div(rows, id=container_id, className="dse-rows"),
        tools=html.Button(add_text, id=add_id, n_clicks=0, className="odx-mini-button small-button"),
        tooltip=tooltip,
    )


def _header(name):
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Div(
                        children=[
                            dcc.Link(
                                icon("back", className="icon back-button", width="26px", height="26px"),
                                href=page_path,
                                id="dse-editor-back",
                                className="dse-editor-back",
                            ),
                            ui.title_input(value=name, id="dse-editor-name", placeholder="campaign name"),
                        ],
                        className="odx-header-titles dse-editor-titles",
                    ),
                    html.Div(
                        children=[
                            ui.icon_button(
                                icon=icon("delete", className="icon"),
                                color="caution",
                                text="Delete",
                                id="dse-editor-delete",
                                tooltip="Delete this campaign",
                                tooltip_options="bottom",
                            ),
                            ui.save_button(id="dse-editor-save", text="Save", disabled=True),
                        ],
                        className="odx-header-actions",
                    ),
                ],
                className="odx-header-row",
            ),
            html.Div(id="dse-editor-summary", className="odx-summary"),
        ],
        className="odx-header",
    )


######################################
# Layout
######################################

def layout(campaign=None, **_kwargs):
    """The editor, built for the campaign the url names."""
    workspace = get_workspace()
    name = str(campaign or "").strip()
    if not name:
        name = unique_campaign_name(workspace, "New_Campaign")
    settings = read_campaign(workspace, name)
    run_mode = settings.run or "fmax_synthesis"

    body = html.Div(
        children=[
            dcc.Location(id="url_dse_campaign", refresh=False),
            dcc.Store(id="dse-editor-original-name", data=name),
            # What is on disk, to tell an edit from a widget being rendered.
            dcc.Store(id="dse-editor-baseline", data={"name": name, "campaign": settings.to_dict()}),
            dcc.Store(id="dse-editor-known-names", data=campaign_names(workspace)),
            form.metric_datalist(metric_names(workspace)),
            _header(name),
            html.Div(id="dse-editor-feedback", className="dse-feedback"),
            ui.section(
                "Evaluation",
                ui.grid([
                    _what_runs_panel(workspace, settings),
                    _frequencies_panel(settings),
                    _start_panel(settings),
                ]),
            ),
            _list_section(
                "Objectives",
                "Each objective is a metric to minimize or to maximize. A design is kept "
                "when nothing beats it on all of them at once.",
                "dse-objectives-list", "dse-add-objective", "Add objective",
                form.objective_rows(objective_entries(settings)),
            ),
            _list_section(
                "Constraints",
                "What a design has to be for it to count at all: a metric with a lower "
                "bound, an upper one, or both.",
                "dse-constraints-list", "dse-add-constraint", "Add constraint",
                form.constraint_rows(constraint_entries(settings)),
            ),
            ui.section("Search", _search_panel(settings)),
            _list_section(
                "Architectures",
                "The architectures whose parameters are searched, one search each -- the "
                "workflows, when what evaluates a design is a workflow. The "
                "second field says what to do with the other domains: \"+ MEM/1024I\" "
                "fixes one, \"+ Mul/*\" searches it.",
                "dse-architectures-list", "dse-add-architecture", "Add architecture",
                form.architecture_rows(
                    architecture_entries(settings), architecture_options(workspace, run_mode)
                ),
            ),
            _delete_popup(),
        ],
        className="page-content odx-page dse-page",
        style={
            "display": "flex",
            "flexDirection": "column",
            "min-height": "calc(100vh - {0})".format(navigation.top_bar_height),
        },
    )
    return scoped(PAGE_SCOPE, body)


def _delete_popup():
    return html.Div(
        id="dse-editor-delete-popup",
        className="overlay-odatix",
        children=[
            html.Div([
                html.H2("Warning"),
                html.Div(id="dse-editor-delete-message"),
                html.Div("This action is irreversible.", className="dse-danger"),
                html.Div([
                    ui.icon_button(
                        icon=icon("delete", className="icon"),
                        color="caution", text="Delete", width="90px",
                        id="dse-editor-delete-confirm",
                    ),
                    html.Button("Cancel", id="dse-editor-delete-cancel", n_clicks=0, style={"marginLeft": "10px", "width": "90px"}),
                ], className="dse-popup-actions"),
            ], className="popup-odatix"),
        ],
    )


dash.register_page(
    __name__,
    path=editor_path,
    title="Odatix - Exploration Campaign",
    name="Exploration Campaign",
    layout=layout,
    order=8,
)


######################################
# Callbacks: the rows of the three lists
######################################

@page_callback(PAGE_SCOPE,
    Output("dse-objectives-list", "children"),
    Input("dse-add-objective", "n_clicks"),
    Input({"type": "dse-obj-delete", "index": ALL}, "n_clicks"),
    State({"type": "dse-obj-metric", "index": ALL}, "value"),
    State({"type": "dse-obj-goal", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def edit_objectives(add_clicks, delete_clicks, metrics, goals):
    entries = list(zip(metrics or [], goals or []))
    entries = _apply_row_edit(entries, ("", "min"), "dse-obj-delete", add_clicks, delete_clicks)
    return form.objective_rows(entries)


@page_callback(PAGE_SCOPE,
    Output("dse-constraints-list", "children"),
    Input("dse-add-constraint", "n_clicks"),
    Input({"type": "dse-con-delete", "index": ALL}, "n_clicks"),
    State({"type": "dse-con-metric", "index": ALL}, "value"),
    State({"type": "dse-con-min", "index": ALL}, "value"),
    State({"type": "dse-con-max", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def edit_constraints(add_clicks, delete_clicks, metrics, minimums, maximums):
    entries = list(zip(metrics or [], minimums or [], maximums or []))
    entries = _apply_row_edit(entries, ("", None, None), "dse-con-delete", add_clicks, delete_clicks)
    return form.constraint_rows(entries)


@page_callback(PAGE_SCOPE,
    Output("dse-architectures-list", "children"),
    Input("dse-add-architecture", "n_clicks"),
    Input({"type": "dse-arch-delete", "index": ALL}, "n_clicks"),
    Input("dse-editor-run", "value"),
    State({"type": "dse-arch-name", "index": ALL}, "value"),
    State({"type": "dse-arch-selection", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def edit_architectures(add_clicks, delete_clicks, run_mode, names, selections):
    entries = list(zip(names or [], selections or []))
    options = architecture_options(get_workspace(), run_mode)
    # Switching what evaluates a design changes what the names mean -- a
    # workflow campaign names workflows -- so the rows are offered the other
    # collection, keeping whatever was already written in them.
    if ctx.triggered_id == "dse-editor-run":
        return form.architecture_rows(entries, options)
    entries = _apply_row_edit(entries, ("", ""), "dse-arch-delete", add_clicks, delete_clicks)
    return form.architecture_rows(entries, options)


def _apply_row_edit(entries, empty, delete_type, add_clicks, delete_clicks):
    """
    The rows a click leaves behind: one more when "Add" was pressed, one less
    when a row was removed. Everything the other rows hold is kept, which is why
    the list is rebuilt from their current values rather than from the file.

    Dash fires a pattern-matching callback again as soon as the components it
    matches change, so a click is only acted upon when the button that was
    triggered really was clicked: rebuilding the list would otherwise add a row
    for every row it adds.
    """
    triggered = ctx.triggered_id
    if isinstance(triggered, dict) and triggered.get("type") == delete_type:
        index = triggered.get("index")
        clicks = list(delete_clicks or [])
        if not isinstance(index, int) or index >= len(clicks) or not clicks[index]:
            raise dash.exceptions.PreventUpdate
        if 0 <= index < len(entries):
            entries = entries[:index] + entries[index + 1:]
        return entries
    if not add_clicks:
        raise dash.exceptions.PreventUpdate
    return entries + [empty]


######################################
# Callbacks: what the form shows
######################################

@dash.callback(
    Output("dse-editor-frequencies", "style"),
    Input("dse-editor-run", "value"),
)
def show_frequencies(run_mode):
    # Only a custom frequency synthesis is told a frequency: an fmax synthesis
    # looks for one, and a workflow is whatever it is.
    return {"display": "block" if run_mode == "custom_freq_synthesis" else "none"}


@dash.callback(
    Output("dse-editor-freq-list", "disabled"),
    Output("dse-editor-freq-from", "disabled"),
    Output("dse-editor-freq-to", "disabled"),
    Output("dse-editor-freq-step", "disabled"),
    Input("dse-editor-freq-explore", "value"),
)
def toggle_frequency_fields(explore):
    """Either the frequencies are listed, or they are searched in a range: the
    half that does not apply is greyed out rather than left to be guessed."""
    searching = checked(explore)
    return searching, not searching, not searching, not searching


@dash.callback(
    Output("dse-editor-genetic", "style"),
    Output("dse-editor-bayesian", "style"),
    Input("dse-editor-strategy", "value"),
)
def show_strategy_fields(strategy):
    return (
        {"display": "block" if strategy == "genetic" else "none"},
        {"display": "block" if strategy == "bayesian" else "none"},
    )


@dash.callback(
    Output("dse-editor-flows", "options"),
    Output("dse-editor-targets", "options"),
    Input("dse-editor-tools", "value"),
    Input("dse-editor-run", "value"),
)
def update_toolchain_options(tools, run_mode):
    workspace = get_workspace()
    return flow_options(tools, run_mode), target_options(workspace, tools)


######################################
# Callbacks: saving
######################################

@page_callback(PAGE_SCOPE,
    Output("dse-editor-save", "className", allow_duplicate=True),
    Input("dse-editor-name", "value"),
    Input("dse-editor-run", "value"),
    Input("dse-editor-tools", "value"),
    Input("dse-editor-flows", "value"),
    Input("dse-editor-targets", "value"),
    Input("dse-editor-simulations", "value"),
    Input("dse-editor-freq-explore", "value"),
    Input("dse-editor-freq-list", "value"),
    Input("dse-editor-freq-from", "value"),
    Input("dse-editor-freq-to", "value"),
    Input("dse-editor-freq-step", "value"),
    Input("dse-editor-reuse", "value"),
    Input("dse-editor-strategy", "value"),
    Input("dse-editor-mode", "value"),
    Input("dse-editor-budget", "value"),
    Input("dse-editor-batch", "value"),
    Input("dse-editor-patience", "value"),
    Input("dse-editor-improvement", "value"),
    Input("dse-editor-seed", "value"),
    Input("dse-editor-mutation", "value"),
    Input("dse-editor-tournament", "value"),
    Input("dse-editor-population", "value"),
    Input("dse-editor-candidates", "value"),
    Input("dse-editor-samples", "value"),
    Input("dse-editor-constraint-models", "value"),
    Input({"type": "dse-obj-metric", "index": ALL}, "value"),
    Input({"type": "dse-obj-goal", "index": ALL}, "value"),
    Input({"type": "dse-con-metric", "index": ALL}, "value"),
    Input({"type": "dse-con-min", "index": ALL}, "value"),
    Input({"type": "dse-con-max", "index": ALL}, "value"),
    Input({"type": "dse-arch-name", "index": ALL}, "value"),
    Input({"type": "dse-arch-selection", "index": ALL}, "value"),
    State("dse-editor-original-name", "data"),
    State("dse-editor-baseline", "data"),
    prevent_initial_call=True,
)
def mark_dirty(name, run_mode, tools, flows, targets, simulations,
               freq_explore, freq_list, freq_from, freq_to, freq_step, reuse,
               strategy, mode, budget, batch, patience, improvement, seed,
               mutation, tournament, population, candidates, samples, constraint_models,
               obj_metrics, obj_goals, con_metrics, con_mins, con_maxs,
               arch_names, arch_selections, original_name, baseline):
    """
    Whether what is on screen is still what is on disk.

    Dash re-fires a pattern-matching callback as soon as the components it
    matches change, so a row being rendered would otherwise be reported as an
    edit: the state is compared to the baseline rather than trusted to only
    arrive after a keystroke.
    """
    current = _campaign_state(
        get_workspace(), original_name, name, run_mode, tools, flows, targets, simulations,
        freq_explore, freq_list, freq_from, freq_to, freq_step, reuse,
        strategy, mode, budget, batch, patience, improvement, seed,
        mutation, tournament, population, candidates, samples, constraint_models,
        obj_metrics, obj_goals, con_metrics, con_mins, con_maxs,
        arch_names, arch_selections,
    )
    return SAVE_IDLE if current == (baseline or {}) else SAVE_DIRTY


def _campaign_state(workspace, original_name, name, run_mode, tools, flows, targets, simulations,
                    freq_explore, freq_list, freq_from, freq_to, freq_step, reuse,
                    strategy, mode, budget, batch, patience, improvement, seed,
                    mutation, tournament, population, candidates, samples, constraint_models,
                    obj_metrics, obj_goals, con_metrics, con_mins, con_maxs,
                    arch_names, arch_selections):
    """The campaign the form describes, as the file would hold it."""
    settings = _campaign_from_form(
        workspace, original_name, run_mode, tools, flows, targets, simulations,
        freq_explore, freq_list, freq_from, freq_to, freq_step, reuse,
        strategy, mode, budget, batch, patience, improvement, seed,
        mutation, tournament, population, candidates, samples, constraint_models,
        obj_metrics, obj_goals, con_metrics, con_mins, con_maxs,
        arch_names, arch_selections,
    )
    return {"name": str(name or "").strip(), "campaign": settings.to_dict()}


def _campaign_from_form(workspace, original_name, run_mode, tools, flows, targets, simulations,
                        freq_explore, freq_list, freq_from, freq_to, freq_step, reuse,
                        strategy, mode, budget, batch, patience, improvement, seed,
                        mutation, tournament, population, candidates, samples, constraint_models,
                        obj_metrics, obj_goals, con_metrics, con_mins, con_maxs,
                        arch_names, arch_selections):
    """
    What the form holds, on top of the campaign as it is written.

    The file is read first so that what the page does not edit -- the exclusions
    it declares, a key someone added by hand -- survives being saved from here.
    """
    settings = read_campaign(workspace, original_name)
    settings.run = run_mode or "fmax_synthesis"
    settings.tool = from_names(tools)
    settings.flow = from_names(flows)
    settings.target = from_names(targets)
    settings.simulations = [str(entry) for entry in (simulations or [])]
    settings.reuse_results = checked(reuse)

    settings.frequencies.explore = checked(freq_explore)
    settings.frequencies.frequencies = int_list(freq_list)
    settings.frequencies.range.start = to_int(freq_from)
    settings.frequencies.range.stop = to_int(freq_to)
    settings.frequencies.range.step = to_int(freq_step)

    search = settings.search
    search.strategy = strategy or "genetic"
    search.mode = mode or "batch"
    search.budget = to_int(budget, 50)
    search.batch = to_int(batch, 8)
    search.patience = to_int(patience, 0)
    search.improvement = to_float(improvement, 0.0)
    search.seed = to_int(seed)
    search.mutation = to_float(mutation)
    search.tournament = to_int(tournament, 2)
    search.population = to_int(population)
    search.candidates = to_int(candidates)
    search.samples = to_int(samples)
    search.constraint_models = checked(constraint_models)

    settings.objectives = form.collect_objectives(obj_metrics, obj_goals)
    settings.constraints = form.collect_constraints(con_metrics, con_mins, con_maxs)
    settings.architectures = form.collect_architectures(arch_names, arch_selections)
    return settings


@page_callback(PAGE_SCOPE,
    Output("dse-editor-save", "className"),
    Output("dse-editor-feedback", "children"),
    Output("dse-editor-original-name", "data"),
    Output("url_dse_campaign", "href"),
    Output("dse-editor-baseline", "data"),
    Input("dse-editor-save", "n_clicks"),
    State("dse-editor-original-name", "data"),
    State("dse-editor-name", "value"),
    State("dse-editor-run", "value"),
    State("dse-editor-tools", "value"),
    State("dse-editor-flows", "value"),
    State("dse-editor-targets", "value"),
    State("dse-editor-simulations", "value"),
    State("dse-editor-freq-explore", "value"),
    State("dse-editor-freq-list", "value"),
    State("dse-editor-freq-from", "value"),
    State("dse-editor-freq-to", "value"),
    State("dse-editor-freq-step", "value"),
    State("dse-editor-reuse", "value"),
    State("dse-editor-strategy", "value"),
    State("dse-editor-mode", "value"),
    State("dse-editor-budget", "value"),
    State("dse-editor-batch", "value"),
    State("dse-editor-patience", "value"),
    State("dse-editor-improvement", "value"),
    State("dse-editor-seed", "value"),
    State("dse-editor-mutation", "value"),
    State("dse-editor-tournament", "value"),
    State("dse-editor-population", "value"),
    State("dse-editor-candidates", "value"),
    State("dse-editor-samples", "value"),
    State("dse-editor-constraint-models", "value"),
    State({"type": "dse-obj-metric", "index": ALL}, "value"),
    State({"type": "dse-obj-goal", "index": ALL}, "value"),
    State({"type": "dse-con-metric", "index": ALL}, "value"),
    State({"type": "dse-con-min", "index": ALL}, "value"),
    State({"type": "dse-con-max", "index": ALL}, "value"),
    State({"type": "dse-arch-name", "index": ALL}, "value"),
    State({"type": "dse-arch-selection", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def save(n_clicks, original_name, name, run_mode, tools, flows, targets, simulations,
          freq_explore, freq_list, freq_from, freq_to, freq_step, reuse,
          strategy, mode, budget, batch, patience, improvement, seed,
          mutation, tournament, population, candidates, samples, constraint_models,
          obj_metrics, obj_goals, con_metrics, con_mins, con_maxs,
          arch_names, arch_selections):
    """Write the campaign to its file, renaming it when the title changed."""
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    workspace = get_workspace()
    name = str(name or "").strip()
    if not name:
        return SAVE_DIRTY, _error("A campaign needs a name."), dash.no_update, dash.no_update, dash.no_update
    if any(character in name for character in "/\\ "):
        return SAVE_DIRTY, _error("A campaign name is a file name: no space, no slash."), dash.no_update, dash.no_update, dash.no_update
    if name != original_name and name in campaign_names(workspace):
        return SAVE_DIRTY, _error('A campaign called "{0}" already exists.'.format(name)), dash.no_update, dash.no_update, dash.no_update

    settings = _campaign_from_form(
        workspace, original_name, run_mode, tools, flows, targets, simulations,
        freq_explore, freq_list, freq_from, freq_to, freq_step, reuse,
        strategy, mode, budget, batch, patience, improvement, seed,
        mutation, tournament, population, candidates, samples, constraint_models,
        obj_metrics, obj_goals, con_metrics, con_mins, con_maxs,
        arch_names, arch_selections,
    )

    if not settings.objectives:
        return SAVE_DIRTY, _error(
            "The campaign has no objective: a search with nothing to look for cannot "
            "tell one design from another."
        ), dash.no_update, dash.no_update, dash.no_update

    try:
        save_campaign(workspace, name, settings)
        renamed = bool(original_name) and name != original_name
        if renamed:
            delete_campaign(workspace, original_name)
            _rename_in_settings(workspace, original_name, name)
    except Exception as error:
        return SAVE_DIRTY, _error(str(error)), dash.no_update, dash.no_update, dash.no_update

    # A renamed campaign is a new file and a new url: the page follows it, so a
    # refresh lands on the campaign that was just saved.
    href = "{0}?campaign={1}".format(editor_path, name) if renamed else dash.no_update
    return (
        SAVE_IDLE,
        _saved('Campaign "{0}" saved.'.format(name)),
        name,
        href,
        {"name": name, "campaign": settings.to_dict()},
    )


def _rename_in_settings(workspace, old_name, new_name):
    """A renamed campaign keeps its place in the list of the ones that run."""
    settings = dse_settings(workspace)
    entries = settings.campaign_names()
    if old_name not in entries:
        return
    settings.campaigns = [new_name if entry == old_name else entry for entry in entries]
    save_dse_settings(workspace, settings)


def _error(message):
    return html.Div(message, className="dse-message error")


def _saved(message):
    return html.Div(message, className="dse-message success")


######################################
# Callbacks: deleting
######################################

@dash.callback(
    Output("dse-editor-delete-popup", "className"),
    Output("dse-editor-delete-message", "children"),
    Input("dse-editor-delete", "n_clicks"),
    State("dse-editor-original-name", "data"),
    prevent_initial_call=True,
)
def show_delete_popup(n_clicks, name):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return "overlay-odatix visible", 'Do you really want to delete campaign "{0}"?'.format(name)


@dash.callback(
    Output("dse-editor-delete-popup", "className", allow_duplicate=True),
    Input("dse-editor-delete-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def close_delete_popup(n_clicks):
    return "overlay-odatix"


@dash.callback(
    Output("url_dse_campaign", "href", allow_duplicate=True),
    Output("dse-editor-feedback", "children", allow_duplicate=True),
    Input("dse-editor-delete-confirm", "n_clicks"),
    State("dse-editor-original-name", "data"),
    prevent_initial_call=True,
)
def do_delete(n_clicks, name):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    workspace = get_workspace()
    try:
        delete_campaign(workspace, name)
        settings = dse_settings(workspace)
        entries = settings.campaign_names()
        if name in entries:
            settings.campaigns = [entry for entry in entries if entry != name]
            save_dse_settings(workspace, settings)
    except Exception as error:
        return dash.no_update, _error(str(error))
    return page_path, dash.no_update

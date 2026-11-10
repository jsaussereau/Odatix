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
"Import an existing project" on the architectures page: the GUI of
"odatix init --detect". A path, Detect, a report of what was found (each
finding with where it comes from, the guesses editable), then Create, which
writes the architecture and opens its editor.

Detection runs on the server and can take a while on a large project; its
result stays in memory (DETECTIONS, keyed by a token held in a store) until
Create writes it.
"""

import os
import re
import uuid

import dash
from dash import html, dcc, Input, Output, State

import odatix.gui.ui_components as ui
from odatix.gui.icons import icon
from odatix.gui.utils import get_workspace
import odatix.lib.project_detect as project_detect
import odatix.components.init_detect as init_detect
import odatix.lib.rtl_generation as rtl_generation
from odatix.gui.page_scope import page_callback

#: Scope of the architectures page, which hosts the import popup (see odatix.gui.page_scope).
PAGE_SCOPE = "architectures"

#: Detections waiting for Create, by token. Only the last few are kept.
DETECTIONS = {}
MAX_DETECTIONS = 8

CONFIDENCE_COLORS = {"declared": "success", "given": "success", "inferred": "primary", "guessed": "warning"}


def import_card():
    """The card opening the import popup, next to "Create new architecture"."""
    return html.Div(
        html.Div(
            [
                html.Div(icon("folder_open", className="icon"), className="import-card-icon"),
                html.Div("Import existing project", style={"fontWeight": "bold", "fontSize": "1.05em"}),
                html.Div("File lists, Bender, FuseSoC, Vivado, Quartus, LibreLane... or plain RTL",
                         className="import-card-hint"),
            ],
            id="import-project-card",
            n_clicks=0,
            style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center",
                   "height": "100%", "textAlign": "center", "gap": "4px"},
        ),
        className="card add hover",
        style={"padding": "18px 20px", "margin": "0", "width": "100%", "boxSizing": "border-box"},
    )


def popup():
    return html.Div(
        id="import-popup",
        className="overlay-odatix",
        children=[
            html.Div(
                [
                    html.H3("Import an existing project"),
                    html.Button("×", id="import-cancel-btn", n_clicks=0, className="close"),
                    html.P(
                        "Odatix reads how the project declares its sources, or infers them from the RTL, "
                        "or runs the generator of its RTL (Chisel, SpinalHDL, Amaranth...), then checks them by elaborating "
                        "the design. The project is never changed, except for a file list, odatix_filelist.f, written at "
                        "the root of its RTL directory when the RTL is written by hand.",
                        className="import-intro",
                    ),
                    html.Div(
                        [
                            ui.form_field("Project directory", "import-path", placeholder="../my_core",
                                          tooltip="Absolute, or relative to the workspace. Best next to the "
                                                  "workspace rather than around it. The browse button opens the "
                                                  "workspace and the Browsable folders of the workspace settings.",
                                          className="import-path", browse={"mode": "dir"}),
                            ui.form_field("Top level (optional)", "import-top-hint", placeholder="guessed",
                                          className="import-top-hint"),
                            html.Div(
                                [html.Div(html.Label("\u00a0"), className="odx-field-label"),
                                 ui.icon_button(icon=icon("search", className="icon"), color="primary", text="Detect",
                                                id="import-detect-btn", width="120px")],
                                className="odx-field import-button-field",
                            ),
                        ],
                        className="import-row",
                    ),
                    ui.feedback("import-feedback"),
                    html.Div(
                        id="import-generation",
                        className="import-generation hidden",
                        children=[
                            html.Div(id="import-generation-title", className="import-generation-title"),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div(html.Label("Command generating the RTL"), className="odx-field-label"),
                                            dcc.Input(id="import-command", list="import-command-list", debounce=False),
                                            html.Datalist(id="import-command-list"),
                                        ],
                                        className="odx-field import-command",
                                    ),
                                    html.Div(
                                        [html.Div(html.Label("\u00a0"), className="odx-field-label"),
                                         ui.icon_button(icon=icon("play", className="icon"), color="primary",
                                                        text="Generate", id="import-generate-btn", width="120px")],
                                        className="odx-field import-button-field",
                                    ),
                                ],
                                className="import-row two",
                            ),
                            html.Div("It runs in a temporary copy of the project, as each job will: "
                                     "the project itself is left as it is. A first run may take minutes.",
                                     className="import-hint"),
                        ],
                    ),
                    dcc.Loading(html.Div(id="import-report", className="import-report"), type="dot"),
                    html.Div(
                        id="import-choices",
                        className="import-choices hidden",
                        children=[
                            ui.panel("Architecture", body=html.Div(
                                [
                                    ui.form_dropdown("Top level", "import-top", [], clearable=False),
                                    ui.form_dropdown("Clock", "import-clock", [], clearable=True),
                                    ui.form_dropdown("Reset", "import-reset", [], clearable=True),
                                    ui.form_field("Architecture name", "import-name"),
                                ],
                                className="import-grid",
                            )),
                            # the parameter domains come after what they belong to
                            html.Div(id="import-domains-panel", className="import-domains-panel"),
                            html.Div(
                                ui.icon_button(icon=icon("check", className="icon"), color="primary",
                                               text="Create architecture", id="import-create-btn", width="auto"),
                                className="import-actions",
                            ),
                        ],
                    ),
                    dcc.Store(id="import-token"),
                    dcc.Store(id="import-domains", data={"domains": []}),
                    dcc.Store(id="import-domains-sync"),
                ],
                className="popup-odatix large import-popup",
            )
        ],
    )

######################################
# Report
######################################

def _rel(path, root):
    return project_detect._relative(path, root)


def _row(label, value, origin="", confidence="", detail=None):
    children = [html.Div(label, className="import-label"), html.Div(value, className="import-value")]
    tags = []
    if origin:
        tags.append(ui.badge(origin, color=CONFIDENCE_COLORS.get(confidence, "")))
    if detail:
        tags.append(html.Span(detail, className="import-detail"))
    children.append(html.Div(tags, className="import-tags"))
    return html.Div(children, className="import-line")


def _finding_row(label, finding):
    if finding is None:
        return _row(label, "not found", "missing", "guessed")
    detail = "also: " + ", ".join(finding.alternatives[:4]) if finding.alternatives else None
    return _row(label, finding.value, finding.confidence if finding.confidence != finding.origin else finding.origin,
                finding.confidence, detail)


def _list(items, className=""):
    return html.Ul([html.Li(item) for item in items], className="import-list " + className)


def render_report(detection):
    root = detection.root
    sources = [
        _row("Sources", detection.origin, "declared" if detection.declarations else "inferred",
             "declared" if detection.declarations else "inferred"),
        _row("Files", "{0} ({1})".format(len(detection.files), ", ".join(detection.languages) or "none")),
    ]
    if detection.include_dirs:
        sources.append(_row("Include dirs", ", ".join(_rel(d, root) for d in detection.include_dirs[:4])
                            + (" ..." if len(detection.include_dirs) > 4 else "")))
    if detection.defines:
        sources.append(_row("Macros", " ".join(detection.defines)))
    design = [_finding_row("Top level", detection.top)]
    if detection.top_file:
        design.append(_row("Top file", _rel(detection.top_file, detection.generated_dir or root)))
    design += [_finding_row("Clock", detection.clock), _finding_row("Reset", detection.reset)]
    if detection.parameters:
        design.append(_row("Parameters", "{0} in the top level".format(len(detection.parameters))))

    validation = detection.validation
    if validation.ok is True:
        check = [_row("Check", "elaborates with " + validation.tool, "passed", "declared")]
    elif validation.ok is False:
        check = [_row("Check", "does not elaborate with " + validation.tool, "failed", "guessed"),
                 _list(validation.errors[:8], "errors")]
    else:
        check = [_row("Check", "not run")]
    if validation.fixes:
        check.append(_list(validation.fixes, "fixes"))

    notes = []
    if detection.generator is not None and detection.generator.error:
        notes.append(("warning", "Generation failed: " + detection.generator.error, [], 0))
    if detection.black_boxes:
        notes.append(("warning", "Modules defined nowhere (black boxes)", detection.black_boxes, 0))
    if detection.undefined_macros:
        notes.append(("warning", "Macros used but defined nowhere", detection.undefined_macros, 0))
    if detection.optional_macros:
        notes.append(("info", "Optional macros (tested, never defined)", detection.optional_macros, 0))
    if detection.duplicates:
        notes.append(("info", "Modules defined by several files, the nearest used", sorted(detection.duplicates), 0))
    if detection.generator is not None:
        notes.append(("info", "The RTL comes from {0} ({1})".format(detection.generator["name"], detection.generator["file"]), [], 0))
    notes += [split_note(n) for n in detection.notes]

    generation = detection.generator
    if generation is not None and detection.generated_dir:
        sources.append(_row("Generated", "{0} file(s) in {1:.0f} s".format(len(generation.generated), generation.duration),
                            generation.output or "project root", "inferred"))
    check += [_row("Tools", ", ".join(detection.tools) or "none found"),
              _row("Default", detection.default_tool or "-")]

    blocks = [html.Div([
        ui.panel("Sources", body=sources),
        ui.panel("Design", body=design),
        ui.panel("Check and tools", body=check),
    ], className="import-panels")]
    if notes:
        blocks.append(ui.panel("Notes ({0})".format(len(notes)),
                               body=html.Div([_note(*n) for n in notes], className="odx-import-notes")))
    return html.Div(blocks, className="import-report-body")


_WARNING_WORDS = ("do not exist", "fail", "cannot", "not read", "no tool", "not checked", "missing")


def split_note(text):
    """(level, title, items, hidden) from a note such as "30 file(s) added ...: a, b, c ...":
    the list after the colon becomes items, and what the note cut ("...") is counted when it says how many."""
    level = "warning" if any(w in text for w in _WARNING_WORDS) else "info"
    head, sep, tail = text.partition(": ")
    if not (sep and ", " in tail):
        return level, text, [], 0
    cut = tail.rstrip().endswith("...")
    items = [i.strip() for i in tail.rstrip(" .").split(", ") if i.strip()]
    total = re.match(r"(\d+) ", head)
    hidden = int(total.group(1)) - len(items) if cut and total else 0
    return level, head, items, max(hidden, 0)


NOTE_ITEMS_SHOWN = 6


def _note_item(item):
    short = item.rsplit("/", 1)[-1] if "/" in item else item
    return html.Span(short, title=item, className="odx-import-note-item")


def _note(level, title, items, hidden=0):
    body = [html.Div(title, className="odx-import-note-title")]
    if items:
        chips = [_note_item(i) for i in items[:NOTE_ITEMS_SHOWN]]
        rest = items[NOTE_ITEMS_SHOWN:]
        if rest:
            chips.append(html.Details([html.Summary("+{0} more".format(len(rest))),
                                       html.Div([_note_item(i) for i in rest], className="odx-import-note-items")],
                                      className="odx-import-note-more"))
        if hidden:
            chips.append(html.Span("+{0} more".format(hidden), className="odx-import-note-hidden"))
        body.append(html.Div(chips, className="odx-import-note-items"))
    return html.Div([html.Span(className="odx-import-note-dot"), html.Div(body, className="odx-import-note-body")],
                    className="odx-import-note " + level)


def _choice_options(suggested, others):
    """Dropdown options: the suggested values first, marked so, then every other one."""
    options = [{"label": html.Span([html.Span(v), html.Span("suggested", className="odx-import-suggested")],
                                   className="odx-import-option"), "value": v, "search": v} for v in suggested]
    options += [{"label": v, "value": v, "search": v} for v in others if v not in suggested]
    return options


def top_options(detection):
    suggested, others = project_detect.module_choices(detection)
    return _choice_options(suggested, others)


def signal_options(detection, top):
    """(clock options, clock, reset options, reset) for `top`: every one-bit input, the suggested ones first."""
    inputs, clocks, resets = project_detect.signal_choices(detection, top)
    same_top = detection.top is not None and top == detection.top.value
    values = []
    for finding, suggested in ((detection.clock, clocks), (detection.reset, resets)):
        # what the detection found (declared, or chosen among close candidates) stays the value of its top
        if same_top and finding is not None:
            suggested = [finding.value] + [s for s in suggested if s != finding.value]
        others = [i for i in inputs if i not in suggested]
        values.append((_choice_options(suggested, others), suggested[0] if suggested else None))
    return values[0][0], values[0][1], values[1][0], values[1][1]


def _remember(detection, token=None):
    token = token or str(uuid.uuid4())
    DETECTIONS[token] = detection
    while len(DETECTIONS) > MAX_DETECTIONS:
        _forget(next(iter(DETECTIONS)))
    return token


def _forget(token):
    detection = DETECTIONS.pop(token, None)
    if detection is not None:
        rtl_generation.cleanup(detection.generator)


def initial_domains(detection):
    """
    The parameter domains proposed at first: one per parameter when the top
    level has few of them, none otherwise (the user picks).
    """
    if detection.generated_dir or len(detection.parameters) > PRESELECTED_PARAMETERS:
        return {"domains": []}
    return {"domains": [{"name": p.name, "names": [p.name], "auto": True} for p in detection.parameters]}


def domains_spec(state):
    """The domains of the popup, as init_detect.describe takes them."""
    values_of = (state or {}).get("values") or {}
    spec = []
    for domain in (state or {}).get("domains", []):
        names = list(domain.get("names") or [])
        if not names:
            continue
        values = dict((n, values_of[n]) for n in names if (values_of.get(n) or "").strip())
        if len(names) == 1 and domain.get("name") == names[0] and not values:
            spec.append(names[0])
        else:
            item = {"group": domain.get("name") or names[0], "names": names}
            if values:
                item["values"] = values
            spec.append(item)
    return spec


def values_errors(spec):
    """Why the values typed for the parameters of `spec` are not values, one line each."""
    import odatix.workspace.detect as workspace_detect
    errors = []
    for item in spec:
        for name, text in sorted((item.get("values") or {}).items() if isinstance(item, dict) else []):
            try:
                variable = workspace_detect.values_variable(text)
            except ValueError as exception:
                errors.append("{0}: {1}".format(name, exception))
                continue
            if variable["type"] == "list" and not variable["settings"]["list"]:
                errors.append("{0}: no value".format(name))
    return errors


def domains_summary(state):
    """What Create will make of the domains, in one line."""
    domains = [d for d in (state or {}).get("domains", []) if d.get("names")]
    if not domains:
        return "No parameter explored: the architecture keeps the values written in its sources."
    count = sum(len(d["names"]) for d in domains)
    return "{0} parameter domain{1}, {2} parameter{3} explored".format(
        len(domains), "s" if len(domains) > 1 else "", count, "s" if count > 1 else "")


#: Up to this many parameters, each has a domain at first; beyond, the user picks.
PRESELECTED_PARAMETERS = 8


def parameters_panel_of(detection, top=None):
    """
    The parameter domains to create: the parameters of the top level on one
    side, the domains on the other, filled by drag and drop (see
    assets/import_domains.js). Rendered by the render_domains callback.
    """
    top = top or detection.top.value
    params = project_detect.parameters_of(detection, top)
    if not params:
        return []
    if detection.generated_dir:
        # the generated RTL is rewritten by each job: its parameters are set in the generator
        body = html.Ul([html.Li([html.Code(p.name), " = ", html.Code(p.value.strip())], title=p.value.strip())
                        for p in params], className="import-parameter-list")
        return ui.panel("Parameters of {0} ({1})".format(top, len(params)), body=body, className="import-wide")
    pool = html.Div(
        [
            html.Div(
                [
                    html.Div([html.Span("Parameters", title="Parameters of {0}".format(top)),
                              html.Span(str(len(params)), className="odx-import-count", id="import-pool-count")],
                             className="odx-import-side-title"),
                    dcc.Input(id="import-param-filter", placeholder="Filter", type="text", className="odx-import-filter",
                              autoComplete="off"),
                ],
                className="odx-import-side-head",
            ),
            html.Div(id="import-pool", className="odx-import-pool", **{"data-drop": "pool"}),
        ],
        className="odx-import-side",
    )
    domains = html.Div(
        [
            html.Div([html.Div([html.Span("Domains to explore"),
                                html.Span("0", className="odx-import-count", id="import-domain-count")],
                               className="odx-import-side-title")],
                     className="odx-import-side-head"),
            html.Div(id="import-domain-cards", className="odx-import-domains"),
        ],
        className="odx-import-side",
    )
    return ui.panel(
        "Parameter domains",
        body=[
            html.Div("Drag a parameter onto a domain to explore it with the others, or onto the dashed zone (or click "
                     "it) for a domain of its own. Type the values of each parameter below it (left empty: its current value).",
                     className="import-hint"),
            html.Div([pool, domains], className="odx-import-board"),
            html.Div(id="import-param-summary", className="odx-import-summary"),
        ],
        className="import-wide",
    )


def _chip(param, removable_from=None):
    value = param.value.strip()
    children = [html.Span(param.name, className="odx-import-chip-name"),
                html.Span(value, className="odx-import-chip-value")]
    if removable_from is not None:
        children.append(html.Span("\u00d7", className="odx-import-chip-remove", title="Do not explore it",
                                  **{"data-remove": param.name}))
    return html.Div(children, className="odx-import-chip", draggable="true", tabIndex="0",
                    title="{0} = {1}".format(param.name, value), **{"data-param": param.name})


VALUES_PLACEHOLDER = "8, 16 · 8..64 step 8 · 8..64 pow2"


def _param_row(param, index, values):
    """A parameter of a domain: its chip, and the values it takes."""
    return html.Div([
        _chip(param, removable_from=index),
        dcc.Input(id={"type": "import-param-values", "name": param.name}, value=values, type="text",
                  placeholder=VALUES_PLACEHOLDER, spellCheck=False, autoComplete="off",
                  name=param.name, className="odx-import-values"),
        html.Span(className="odx-import-values-count", **{"data-count": param.name}),
    ], className="odx-import-param-row")


def render_domains_of(detection, state, top=None):
    """(pool children, domain cards, summary, pool count, domain count) for a state of the domains."""
    parameters = project_detect.parameters_of(detection, top or detection.top.value)
    params = dict((p.name, p) for p in parameters)
    domains = [d for d in (state or {}).get("domains", []) if d.get("names")]
    values = (state or {}).get("values") or {}
    used = set(n for d in domains for n in d["names"])
    free = [p for p in parameters if p.name not in used]
    pool = [_chip(p) for p in free] or [html.Div("Every parameter is explored.", className="odx-import-empty")]
    cards = []
    for index, domain in enumerate(domains):
        names = [n for n in domain["names"] if n in params]
        cards.append(html.Div(
            [
                html.Div(
                    [
                        dcc.Input(id={"type": "import-domain-name", "index": index}, value=domain.get("name", ""),
                                  debounce=True, className="odx-import-domain-name", spellCheck=False),
                        html.Span("{0} parameter{1}".format(len(names), "s" if len(names) > 1 else ""),
                                  className="odx-import-domain-size"),
                    ],
                    className="odx-import-domain-head",
                ),
                html.Div([_param_row(params[n], index, values.get(n, "")) for n in names],
                         className="odx-import-domain-params"),
            ],
            className="odx-import-domain",
            **{"data-drop": str(index)}
        ))
    cards.append(html.Div(
        [html.Div("+", className="odx-import-new-plus"), html.Div("Drop a parameter here for a new domain")],
        className="odx-import-new", **{"data-drop": "new"}))
    return pool, cards, domains_summary(state), str(len(free)), str(len(domains))


#: What the Detect and Generate buttons both fill.
RESULT_OUTPUTS = (
    ("import-report", "children"), ("import-feedback", "children"), ("import-choices", "className"),
    ("import-top", "options"), ("import-top", "value"), ("import-clock", "options"), ("import-clock", "value"),
    ("import-reset", "options"), ("import-reset", "value"), ("import-name", "value"), ("import-token", "data"),
    ("import-generation", "className"), ("import-generation-title", "children"), ("import-command", "value"),
    ("import-command-list", "children"), ("import-domains", "data"), ("import-domains-panel", "children"),
)

#: Up to this many parameters, all are proposed for exploration; beyond, the user picks.
PRESELECTED_PARAMETERS = 8


def _result(detection, token=None, message=""):
    """The values of RESULT_OUTPUTS for a detection."""
    report = render_report(detection)
    generation = detection.generator
    if generation is not None:
        title = "The RTL is generated by {0} ({1})".format(generation.name, generation.file)
        if detection.generated_dir:
            title += ": generated, {0} file(s) in {1}".format(len(generation.generated), generation.output or "the project root")
        generation_block = ("import-generation", title, generation.command,
                            [html.Option(value=c) for c in [generation.command] + generation.entries])
    else:
        generation_block = ("import-generation hidden", "", "", [])
    token = _remember(detection, token)
    if not detection.files or detection.top is None:
        reason = message or ("Generate the RTL to describe it." if detection.needs_generation else
                             "No design found to describe" + (": no top level." if detection.files else "."))
        return (report, ui.error(reason), "import-choices hidden") + (dash.no_update,) * 7 + (token,) + generation_block \
            + ({"domains": []}, [])
    top_choices, top_value = top_options(detection), detection.top.value
    clock_options, clock_value, reset_options, reset_value = signal_options(detection, top_value)
    feedback = ui.error(message) if message else ""
    return (report, feedback, "import-choices", top_choices, top_value, clock_options, clock_value,
            reset_options, reset_value, detection.top.value, token) + generation_block \
        + (initial_domains(detection), parameters_panel_of(detection) if detection.parameters else [])


def _outputs(duplicate=False):
    return [Output(component, prop, allow_duplicate=duplicate) for component, prop in RESULT_OUTPUTS]

######################################
# Callbacks
######################################

def register(page_path):
    """The callbacks of the popup, for the page at `page_path` (whose url store Create writes)."""

    @dash.callback(
        Output("import-popup", "className"),
        Input("import-project-card", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_popup(n_clicks):
        return "overlay-odatix visible" if n_clicks else dash.no_update

    @dash.callback(
        Output("import-popup", "className", allow_duplicate=True),
        Input("import-cancel-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_popup(_):
        return "overlay-odatix"

    @dash.callback(
        *_outputs(),
        Input("import-detect-btn", "n_clicks"),
        State("import-path", "value"),
        State("import-top-hint", "value"),
        State("import-token", "data"),
        State("odatix-settings", "data"),
        running=[(Output("import-detect-btn", "disabled"), True, False)],
        prevent_initial_call=True,
    )
    def detect(n_clicks, path, top, previous, odatix_settings):
        def failed(message):
            return ("", ui.error(message), "import-choices hidden") + (dash.no_update,) * 8 + ("import-generation hidden", "", "", []) \
                + ({"domains": []}, [])
        if not n_clicks:
            return (dash.no_update,) * len(RESULT_OUTPUTS)
        if not (path or "").strip():
            return failed("Give the directory of the project.")
        root = get_workspace(odatix_settings).root
        directory = os.path.abspath(os.path.join(root, os.path.expanduser(path.strip())))
        if not os.path.isdir(directory):
            return failed("No such directory: " + directory)
        if previous:
            _forget(previous)
        try:
            detection = project_detect.detect_project(directory, top=(top or "").strip())
        except Exception as exception:
            return failed("Detection failed: {0}".format(exception))
        return _result(detection)

    @dash.callback(
        *_outputs(duplicate=True),
        Input("import-generate-btn", "n_clicks"),
        State("import-token", "data"),
        State("import-command", "value"),
        running=[(Output("import-generate-btn", "disabled"), True, False),
                 (Output("import-detect-btn", "disabled"), True, False)],
        prevent_initial_call=True,
    )
    def generate(n_clicks, token, command):
        detection = DETECTIONS.get(token or "")
        if not n_clicks or detection is None or detection.generator is None:
            return (dash.no_update,) * len(RESULT_OUTPUTS)
        if not project_detect.detect_generated(detection, command=(command or "").strip() or None):
            return _result(detection, token, "Not generated: " + (detection.generator.error or "unknown error"))
        return _result(detection, token)

    @dash.callback(
        Output({"type": "update_url", "id": page_path}, "data", allow_duplicate=True),
        Output("import-feedback", "children", allow_duplicate=True),
        Input("import-create-btn", "n_clicks"),
        State("import-token", "data"),
        State("import-top", "value"),
        State("import-clock", "value"),
        State("import-reset", "value"),
        State("import-name", "value"),
        State("import-domains", "data"),
        State({"type": "import-param-values", "name": dash.ALL}, "value"),
        State({"type": "import-param-values", "name": dash.ALL}, "id"),
        State("odatix-settings", "data"),
        running=[(Output("import-create-btn", "disabled"), True, False)],
        prevent_initial_call=True,
    )
    def create(n_clicks, token, top, clock, reset, name, domains, typed, typed_ids, odatix_settings):
        if not n_clicks:
            return dash.no_update, dash.no_update
        # what is in the fields wins: the store follows them only on the next move
        domains = dict(domains or {})
        domains["values"] = dict(domains.get("values") or {},
                                 **dict((i["name"], v or "") for i, v in zip(typed_ids or [], typed or [])))
        parameters = domains_spec(domains)
        invalid = values_errors(parameters)
        if invalid:
            return dash.no_update, ui.error("Not created: " + "; ".join(invalid))
        detection = DETECTIONS.get(token or "")
        if detection is None:
            return dash.no_update, ui.error("Not created: detect the project again (the server was restarted).")
        name = (name or "").strip() or (top or "")
        if top and detection.top is not None and top != detection.top.value:
            # another top level means another hierarchy: its sources are found again
            detection = project_detect.retarget(detection, top)
        for attribute, value in (("clock", clock), ("reset", reset)):
            if value:
                setattr(detection, attribute, project_detect.Finding(value, "chosen", "given"))
            else:
                setattr(detection, attribute, None)
        workspace = get_workspace(odatix_settings)
        try:
            result = init_detect.describe(detection, workspace, name, parameters=parameters)
        except ValueError as exception:
            return dash.no_update, ui.error("Not created: {0}".format(exception))
        except Exception as exception:
            return dash.no_update, ui.error("Not created: {0}".format(exception))
        _forget(token)
        if result["skipped"]:
            # the architecture exists: say what is missing, and let the user open it
            return dash.no_update, ui.error([
                "Created, but without a parameter domain for: " + "; ".join(result["skipped"]) + ". ",
                dcc.Link("Open the architecture", href="/arch_editor?arch={0}".format(name)),
            ])
        return {"href": "/arch_editor?arch={0}".format(name), "id": page_path}, ui.success("Created.")

    dash.clientside_callback(
        dash.ClientsideFunction(namespace="odatix_import", function_name="sync"),
        Output("import-domains-sync", "data"),
        Input("import-domains", "data"),
    )

    @dash.callback(
        Output("import-pool", "children"),
        Output("import-domain-cards", "children"),
        Output("import-param-summary", "children"),
        Output("import-pool-count", "children"),
        Output("import-domain-count", "children"),
        Input("import-domains", "data"),
        State("import-token", "data"),
        State("import-top", "value"),
        prevent_initial_call=True,
    )
    def render_domains(state, token, top):
        detection = DETECTIONS.get(token or "")
        if detection is None or detection.generated_dir or not project_detect.parameters_of(detection, top or detection.top.value):
            return (dash.no_update,) * 5
        return render_domains_of(detection, state, top)

    @page_callback(PAGE_SCOPE,
        Output("import-domains", "data", allow_duplicate=True),
        Input({"type": "import-domain-name", "index": dash.ALL}, "value"),
        State("import-domains", "data"),
        prevent_initial_call=True,
    )
    def rename_domains(names, state):
        domains = [dict(d) for d in (state or {}).get("domains", []) if d.get("names")]
        changed = False
        for domain, name in zip(domains, names):
            name = (name or "").strip()
            if name and name != domain.get("name"):
                domain["name"], domain["auto"] = name, False  # the user's name stays
                changed = True
        return {"domains": domains, "values": (state or {}).get("values") or {}} if changed else dash.no_update

    @dash.callback(
        Output("import-clock", "options", allow_duplicate=True),
        Output("import-clock", "value", allow_duplicate=True),
        Output("import-reset", "options", allow_duplicate=True),
        Output("import-reset", "value", allow_duplicate=True),
        Output("import-domains-panel", "children", allow_duplicate=True),
        Output("import-domains", "data", allow_duplicate=True),
        Input("import-top", "value"),
        State("import-token", "data"),
        prevent_initial_call=True,
    )
    def top_changed(top, token):
        """Another top level: its own inputs, and the best clock and reset among them."""
        detection = DETECTIONS.get(token or "")
        if detection is None or not top:
            return (dash.no_update,) * 6
        # its own parameters too: domains chosen for another top level would not apply
        params = project_detect.parameters_of(detection, top)
        domains = {"domains": [{"name": p.name, "names": [p.name], "auto": True} for p in params]} \
            if len(params) <= PRESELECTED_PARAMETERS and not detection.generated_dir else {"domains": []}
        return signal_options(detection, top) + (parameters_panel_of(detection, top), domains)

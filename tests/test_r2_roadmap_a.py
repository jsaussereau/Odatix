"""
Non-regression tests of the roadmap items of lot A (3rd wave of the "new user"
campaign): hangover animations, "1 record", "Nothing to run" without the tool
check, DSE campaign template, session listing, config editor and workflow
editor speed, saved view titles, table headers, Insights recipes, contrasts.
"""
import os
import re
import subprocess
import sys
import time
from types import SimpleNamespace

import dash
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODATIX = os.path.join(ROOT, "sources", "odatix")
ASSETS = os.path.join(ODATIX, "gui", "assets")


def read(*parts):
    with open(os.path.join(*parts), "r", encoding="utf-8") as f:
        return f.read()


######################################
# Themes
######################################

def test_hangover_cards_float_around_again():
    """The gag of the theme is back: its cards drift, not only tilt (UG-16 undone)."""
    css = read(ASSETS, "themes", "hangover.css")
    keyframes = re.findall(r"@keyframes float\d+ \{(.*?)\n\}", css, re.S)
    assert len(keyframes) == 12
    assert all("translate(" in body for body in keyframes)


def test_catpuccin_buttons_write_dark_text_on_their_pastel_gradients():
    css = read(ASSETS, "themes", "catpuccin.css")
    for token in ("primary-button-text-color", "warning-button-text-color", "secondary-button-text-color-hover",
                  "caution-button-text-color-hover"):
        assert re.search(r"--" + token + r": var\(--inverted-text\);", css), token
    # Tooltips and the navigation menu stay light on their dark background.
    assert "/* --theme-contrast-text-color: var(--inverted-text); */" in css


def test_frosted_dark_primary_gradient_is_dark_enough_for_white_text():
    css = read(ASSETS, "themes", "frosted_dark.css")
    gradient = re.search(r"--primary-button-background: linear-gradient\(([^;]*)\);", css).group(1)

    def luminance(hex_color):
        channels = [int(hex_color[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
        channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    for color in re.findall(r"#([0-9a-fA-F]{6})", gradient):
        assert 1.05 / (luminance(color) + 0.05) >= 4.5, color


def test_win95_feedback_line_is_a_message_box_on_the_desktop():
    css = read(ASSETS, "themes", "win95.css")
    assert ".theme.win95 .odx-message.success" in css
    rule = css[css.index(".theme.win95 .odx-message.success"):]
    assert "background: var(--win95-face);" in rule.split("}")[0]


def test_exploration_cards_show_a_spinner_until_their_chart_is_drawn():
    css = read(ASSETS, "explorer.css")
    assert '.xp-dse-card:has([data-dash-is-loading="true"])::after' in css
    assert ".xp-dse-card:has(.dash-graph):not(:has(.main-svg))::after" in css


######################################
# Explorer
######################################

def test_one_record_is_singular():
    from odatix.explorer.ui.components import status_text

    store = SimpleNamespace(
        sources=lambda: [SimpleNamespace(name="vivado", record_count=1, error=None)],
        result_path="results", last_load_time=None,
    )
    assert status_text(store) == "1 source · 1 record"
    store.sources = lambda: [SimpleNamespace(name="vivado", record_count=3, error=None)]
    assert status_text(store) == "1 source · 3 records"


def test_saved_view_keeps_the_name_it_was_given(tmp_path):
    import odatix.explorer.core.views as views

    slug = views.save_view(str(tmp_path), "slack by freq", {"kind": "lines"})
    assert slug == "slack_by_freq"
    listed = views.list_views(str(tmp_path))
    assert [(view["name"], view["title"]) for view in listed] == [("slack_by_freq", "slack by freq")]


def test_view_without_title_is_shown_under_its_file_name():
    import odatix.explorer.core.views as views

    assert views.view_title({"name": "old_view"}) == "old_view"


def test_table_headers_are_in_sentence_case():
    from odatix.explorer.callbacks.figure import dimension_header

    assert dimension_header("tool") == "Tool"
    assert dimension_header("flow") == "Flow"
    assert dimension_header("main") == "Main domain"
    assert dimension_header("Source") == "Source"


def test_insights_do_not_propose_a_share_next_to_its_count():
    from odatix.explorer.core.recommend import Context

    stat = lambda name: SimpleNamespace(metric=name, interest=0.5, direction=None)
    ctx = SimpleNamespace(
        metric_stats={name: stat(name) for name in ("lut_count", "lut_percent", "power_percent")},
        _preference=lambda name, kind: 0,
    )
    assert Context.ranked_metrics(ctx) == ["lut_count", "power_percent"]


def test_insights_dissociate_a_parameter_but_never_the_whole_name():
    """
    A parameter is pulled out of the configuration names so that one trace
    follows it; the main domain is the whole name, and pulling it out left one
    point per trace (a lines chart without a line).
    """
    from odatix.explorer.core.recommend import _dissociable

    assert _dissociable("block_size") == ["block_size"]
    assert _dissociable("main") == []
    assert _dissociable("Configuration") == []


######################################
# Run: nothing to run
######################################

class _Check(object):
    def __init__(self):
        self.calls = []

    def cancel(self):
        self.calls.append("cancel")

    def wait(self):
        self.calls.append("wait")


def test_nothing_to_run_does_not_wait_for_the_tool():
    from odatix.components.run_common import settle_tool_checks

    check = _Check()
    settle_tool_checks([check, None], needed=False)
    assert check.calls == ["cancel"]

    sunk = []
    check = _Check()
    settle_tool_checks([check], tool_check_sink=sunk.append, needed=False)
    assert check.calls == ["cancel"] and sunk == []

    check = _Check()
    settle_tool_checks([check])
    assert check.calls == ["wait"]


@pytest.mark.skipif(sys.platform == "win32", reason="uses sleep")
def test_a_cancelled_tool_check_stops_the_tool():
    from odatix.lib.check_tool import ToolCheck

    check = ToolCheck("dummy", "sleep 30", supported_tools=["dummy"], tool_install_path="")
    start = time.time()
    check.cancel()
    assert time.time() - start < 5
    assert check.process.poll() is not None
    check.wait()  # nothing left to wait for, and nothing reported


def test_every_run_flow_skips_the_tool_check_when_nothing_runs():
    for name in ("run_fixed_freq_synthesis.py", "run_fmax_synthesis.py", "run_pnr.py"):
        source = read(ODATIX, "components", name)
        assert "settle_tool_checks([context[\"tool_check\"]], tool_check_sink, needed=" in source, name
    assert "needed=anything_to_run" in read(ODATIX, "components", "run_analysis.py")


######################################
# DSE
######################################

def test_the_campaign_template_has_an_explicit_name():
    directory = os.path.join(ROOT, "sources", "odatix_init", "odatix_userconfig", "dse_campaigns")
    assert os.path.isfile(os.path.join(directory, "campaign_template.yml"))
    assert not os.path.exists(os.path.join(directory, "example.yml"))
    assert '"campaign_template.yml"' in read(ODATIX, "gui", "dse_config", "common.py")
    assert "campaign_template.yml" in read(ROOT, "sources", "odatix_init", "odatix_userconfig", "dse_settings.yml")


######################################
# Sessions
######################################

def test_sessions_of_other_workspaces_are_not_probed(monkeypatch, tmp_path):
    import odatix.lib.parallel_job_handler.daemon_control as daemon_control

    mine, theirs = str(tmp_path / "mine"), str(tmp_path / "theirs")
    os.makedirs(mine)
    os.makedirs(theirs)
    candidates = [
        {"pid": 101, "workspace_root": mine, "state_file": None, "port": 1},
        {"pid": 102, "workspace_root": theirs, "state_file": None, "port": 2},
        {"pid": 103, "workspace_root": mine, "state_file": None, "port": 3},
    ]
    probed = []

    def alive(state):
        probed.append(state["pid"])
        return True

    monkeypatch.setattr(daemon_control, "_iter_system_daemon_candidates", lambda: [dict(c) for c in candidates])
    monkeypatch.setattr(daemon_control, "_daemon_is_alive_for_listing", alive)
    daemons = daemon_control.list_daemons(only_workspace=mine)
    assert sorted(probed) == [101, 103]
    assert sorted(daemon["pid"] for daemon in daemons) == [101, 103]


def test_sessions_are_probed_at_once(monkeypatch):
    import odatix.lib.parallel_job_handler.daemon_control as daemon_control

    def slow(state):
        time.sleep(0.5)
        return state["pid"] != 2

    monkeypatch.setattr(daemon_control, "_daemon_is_alive_for_listing", slow)
    start = time.time()
    alive = daemon_control._probe_alive_in_parallel([{"pid": pid} for pid in range(6)])
    assert time.time() - start < 1.5
    assert [state["pid"] for state in alive] == [0, 1, 3, 4, 5]


######################################
# Config editor
######################################

def test_rule_fields_reach_the_previews_once_the_typing_stops():
    js = read(ASSETS, "config_editor.js")
    assert "debounce_rules" in js and '"cfg-rules-debounce"' in js
    rules = read(ODATIX, "gui", "config_rules.py")
    preview = rules[rules.index("def update_rules_preview") - 3000:rules.index("def update_rules_preview")]
    assert 'Input("cfg-rules-debounce", "data")' in preview
    assert 'State({"type": "cfg-gen-template"' in preview
    assert 'Input({"type": "cfg-gen-template"' not in preview
    editor = read(ODATIX, "gui", "pages", "config_editor.py")
    replacement = editor[editor.index("def update_preview_replacement") - 2500:editor.index("def update_preview_replacement")]
    assert 'Input("cfg-rules-debounce", "data")' in replacement
    assert 'Input({"type": "cfg-gen-template"' not in replacement


######################################
# Workflow editor
######################################

@pytest.fixture
def workflow_editor():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.workflow_editor as workflow_editor

    return workflow_editor


def _ids(component, found=None):
    found = [] if found is None else found
    identifier = getattr(component, "id", None)
    if identifier is not None:
        found.append(identifier)
    children = getattr(component, "children", None)
    for child in (children if isinstance(children, list) else [children] if children is not None else []):
        if hasattr(child, "to_plotly_json"):
            _ids(child, found)
    return found


def test_cards_live_in_slots_of_their_own(workflow_editor):
    row, slots = workflow_editor._slotted("variable", workflow_editor.wf_cards_from_variables({"a": {}, "b": {}}))
    assert slots == {"cards": {"a": 0, "b": 1}, "add": 2, "next": 3}
    assert [child.id for child in row] == [{"type": "wf-variable-slot", "slot": index} for index in range(3)]
    assert "wf-variable-new" in _ids(row[2])


def test_adding_a_card_only_touches_the_last_slot(workflow_editor, monkeypatch):
    monkeypatch.setattr(workflow_editor, "ctx", SimpleNamespace(
        triggered_id="wf-variable-new", triggered=[{"prop_id": "wf-variable-new.n_clicks", "value": 1}]))
    slot_ids = [{"type": "wf-variable-slot", "slot": index} for index in range(3)]
    card_ids = [{"type": "wf-variable-card", "name": name, "row": "variable"} for name in ("var1", "b")]
    children, slots = workflow_editor.update_wf_variable_cards(
        1, [], [], card_ids, slot_ids, {"cards": {"var1": 0, "b": 1}, "add": 2, "next": 3}, *([[]] * 16))
    assert children[:2] == [dash.no_update, dash.no_update]
    added = _ids(children[2][0])
    assert {"type": "wf-variable-card", "name": "var2", "row": "variable"} in added
    assert "wf-variable-new" in _ids(children[2][1])
    assert slots == {"cards": {"var1": 0, "b": 1, "var2": 3}, "add": 4, "next": 5}


def test_deleting_a_card_empties_its_slot(workflow_editor, monkeypatch):
    trigger = {"type": "wf-delete-var", "name": "b", "row": "variable"}
    monkeypatch.setattr(workflow_editor, "ctx", SimpleNamespace(
        triggered_id=trigger, triggered=[{"prop_id": "x.n_clicks", "value": 1}]))
    slot_ids = [{"type": "wf-variable-slot", "slot": index} for index in range(3)]
    card_ids = [{"type": "wf-variable-card", "name": name, "row": "variable"} for name in ("a", "b")]
    children, slots = workflow_editor.update_wf_variable_cards(
        None, [None, None], [None, 1], card_ids, slot_ids, {"cards": {"a": 0, "b": 1}, "add": 2, "next": 3},
        *([[]] * 16))
    assert children == [dash.no_update, [], dash.no_update]
    assert slots["cards"] == {"a": 0}


def test_a_deleted_name_is_not_taken_again(workflow_editor):
    # Its slot is gone from the cards, but a name of a card still on the page
    # or of a slot is never reused.
    assert workflow_editor._free_name("var", workflow_editor._taken_names(["var1"], {"cards": {"var2": 4}})) == "var3"


def test_variable_ids_do_not_share_their_keys_with_task_ids(workflow_editor):
    """Dash compares every id of an update with the ids of the same keys: keep the two rows apart."""
    variable_ids = [i for i in _ids(workflow_editor.wf_variable_card("v")) if isinstance(i, dict)]
    task_ids = [i for i in _ids(workflow_editor.wf_task_card("t")) if isinstance(i, dict)]
    assert variable_ids and task_ids
    assert set(tuple(sorted(i)) for i in variable_ids).isdisjoint(set(tuple(sorted(i)) for i in task_ids))


def test_insights_skip_a_lines_chart_of_lonely_points():
    """Designs sampled at random never differ by one parameter alone: no lines to draw."""
    import pandas as pd
    from odatix.explorer.core.recommend import Context

    grid = pd.DataFrame({"width": [4, 8, 16, 4, 8, 16], "depth": [1, 1, 1, 2, 2, 2], "area": [1, 2, 3, 4, 5, 6]})
    sampled = pd.DataFrame({"width": [4, 8, 16], "depth": [1, 2, 3], "area": [1, 2, 3]})
    for df, expected in ((grid, True), (sampled, False)):
        ctx = SimpleNamespace(df=df, dimensions={"width": None, "depth": None})
        assert Context.lines_connect(ctx, "width", "area") is expected

"""Regression tests of the 2nd new-user pass, workflows domain (WF-xx, DS-01)."""
import os
import time

import pytest
import yaml


def test_percent_in_a_command_is_kept(tmp_path):  # WF-02
    from odatix.lib.wosit import createTaskGraph
    maker = createTaskGraph([
        {"name": "main", "dependencies": ["a"], "commands": ["date +%s > t", 'printf "%d%%" 4']},
        {"name": "a", "commands": ["echo %s"]},
    ])
    old = os.getcwd()
    os.chdir(str(tmp_path))
    try:
        stages = maker.getStages(name="main")
    finally:
        os.chdir(old)
    commands = [task["command"] for level in sorted(stages) for task in stages[level]]
    assert commands == ["echo %s", 'date +%s > t\nprintf "%d%%" 4']


def test_percent_in_a_task_name_is_refused():
    from odatix.lib.wosit import createTaskGraph
    with pytest.raises(ValueError, match="cannot contain"):
        createTaskGraph([{"name": "a%b", "commands": []}])


def test_build_variants_is_built_once(monkeypatch):  # DS-01
    from odatix.lib import virtual_param_domain as v
    settings = {"variables": {"a": {"type": "range", "settings": {"from": 1, "to": 60}},
                              "b": {"type": "list", "settings": {"list": list(range(50))}}}}
    calls = []
    real = v._build_variants
    monkeypatch.setattr(v, "_build_variants", lambda *a, **k: calls.append(1) or real(*a, **k))
    first = v.build_variants(settings, "s.yml")
    first[0]["substitutions"]["a"] = "changed"
    second = v.build_variants(settings, "s.yml")
    assert len(calls) == 1 and len(second) == 3000
    assert second[0]["substitutions"]["a"] != "changed"


@pytest.fixture
def editor():
    import dash
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.workflow_editor as workflow_editor
    return workflow_editor


def test_reference_tasks_hold_only_what_the_cards_edit(editor):  # WF-05
    settings = editor.normalize_workflow_settings({"tasks": [{"name": "t", "commands": [], "other": 1}]})
    assert settings["tasks"] == [{"name": "t", "commands": []}]


def test_unit_field_round_trip():  # WF-12
    import odatix.gui.variable_editor as ve
    values = ve.card_field_values({"type": "list", "unit": "km", "settings": {"list": [1]}}, with_unit=True)
    assert values["unit_value"] == "km"
    variables = ve.build_variables_dict(["d"], ["list"], *([[""]] * 9), ["1"], [""], [""], [""], [""], unit_vals=["km"])
    assert variables["d"]["unit"] == "km"


def test_unmanaged_keys_keep_their_place():  # WF-12
    import odatix.gui.variable_editor as ve
    merged = ve.merge_in_file_order({"type": "list", "settings": {}}, {"unit": "s", "type": "list", "settings": {}}, ve.MANAGED_KEYS)
    assert list(merged) == ["unit", "type", "settings"]


def test_unchanged_tasks_are_not_rewritten(editor):  # WF-12
    stored = [{"name": "main", "dependencies": ["a"], "commands": ["x"]}, {"name": "a", "commands": ["y"], "phony": True}]
    edited = [{"name": "main", "commands": ["x"], "dependencies": ["a"]}, {"name": "a", "commands": ["y"]}]
    assert editor.same_tasks(edited, stored)
    assert not editor.same_tasks(edited + [{"name": "b", "commands": []}], stored)


def test_phony_switch(editor):  # WF-05
    import odatix.gui.task_editor as te
    tasks = te.apply_phony([{"name": "a", "commands": []}], te.phony_by_name([{"name": "a"}], [[]]))
    assert tasks[0]["phony"] is False

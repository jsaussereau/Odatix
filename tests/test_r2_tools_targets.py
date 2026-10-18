"""Regression tests of the 2nd new-user pass, tools/targets domain."""
import dash
import pytest

import odatix.lib.check_tool as check_tool
import odatix.lib.eda_tools as eda_tools


@pytest.fixture(scope="module")
def select_targets():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.select_targets as module
    return module


def test_new_card_marks_dirty_without_writing(select_targets):
    meta = [select_targets.card_metadata({"name": "a"}), select_targets.card_metadata(None, new=True)]
    assert select_targets.targets_changed(["a", "b"], [[True], [True]], [[], []], ["", ""], meta, ["a"])
    clean = [select_targets.card_metadata({"name": "a"})]
    assert not select_targets.targets_changed(["a"], [[True]], [[]], [""], clean, ["a"])
    # a removed card
    assert select_targets.targets_changed([], [], [], [], [], ["a"])


def test_save_refuses_duplicate_or_empty_names(select_targets):
    meta = [select_targets.card_metadata({"name": "a"})] * 2
    with pytest.raises(ValueError):
        select_targets.targets_to_save(["a", "a"], [[True]] * 2, [[]] * 2, ["", ""], meta)
    with pytest.raises(ValueError):
        select_targets.targets_to_save([""], [[True]], [[]], [""], meta[:1])


def test_duplicate_carries_source_settings(select_targets):
    meta = [select_targets.card_metadata(None, new=True, source="xc7")]
    out = select_targets.targets_to_save(["xc7_copy1"], [[True]], [[]], [""], meta)
    assert out[0]["original_name"] == "xc7"


def test_replayed_clicks_are_ignored(select_targets):
    assert select_targets.is_new_click(10, 5)
    assert not select_targets.is_new_click(5, 5)
    assert not select_targets.is_new_click(None, 0)


def test_install_path_only_for_tools_reading_it():
    assert eda_tools.reads_install_path("quartus")
    assert not eda_tools.reads_install_path("vivado")
    assert "qinit.sh" in eda_tools.install_path_hint("quartus")


def test_passed_check_is_cached():
    check_tool.forget_passed_checks()
    assert check_tool.probe("true") == (True, "")
    assert check_tool.recently_passed("true")
    ok, reason = check_tool.probe("echo boom >&2; exit 3")
    assert ok is False and reason == "boom"
    check_tool.forget_passed_checks()

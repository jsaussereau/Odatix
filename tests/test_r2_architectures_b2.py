"""Non-regression tests of the 3rd wave, architectures (lot B2)."""

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_exclusions import ARCHITECTURE, CORNERS, workspace_with  # noqa: E402

from odatix.workspace.selection import expand  # noqa: E402


TYPO = ARCHITECTURE + """
    exclusions:
      - id: typo
        when: "$corrner == 'ss'"
      - id: fine
        when: "$corner == 'ss'"
"""


def test_ar07_unknown_name_in_an_exclusion_warns_with_a_suggestion(tmp_path):
    workspace_with(tmp_path, TYPO, {"corner": CORNERS})
    root = str(tmp_path / "odatix_userconfig" / "architectures")
    messages = []
    expand(["Design/*+corner/*"], root, messages)
    warnings = [m.text for m in messages if m.level == "warning"]
    assert len(warnings) == 1
    assert 'exclusion "typo"' in warnings[0]
    assert "$corrner" in warnings[0] and "did you mean $corner?" in warnings[0]


def test_ar07_known_names_do_not_warn(tmp_path):
    workspace_with(tmp_path, ARCHITECTURE + """
    exclusions:
      - when: "$width == 32 and $corner == 'ss'"
""", {"corner": CORNERS})
    root = str(tmp_path / "odatix_userconfig" / "architectures")
    messages = []
    expand(["Design/*+corner/*"], root, messages)
    assert not [m for m in messages if m.level == "warning"]


@pytest.fixture
def ce():
    dash = pytest.importorskip("dash")
    pytest.importorskip("dash_svg")
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.config_editor as config_editor
    return config_editor


def test_ar16_deleting_a_file_takes_two_clicks(ce):
    trigger = {"type": "delete-config", "domain_uuid": "d", "config_uuid": "c1"}
    meta = [{"config_uuid": "c1", "config_name": "8bits.txt", "origin": ce.ORIGIN_MANUAL}]
    go_on, armed, message = ce.confirm_config_delete(trigger, meta, None)
    assert not go_on and armed == "c1" and message is not None
    assert ce.confirm_config_delete(trigger, meta, "c1")[:2] == (True, None)
    # A generated configuration is only blacklisted: reversible, one click.
    meta[0]["origin"] = ce.ORIGIN_GENERATED
    assert ce.confirm_config_delete(trigger, meta, None)[0]
    # Any other action disarms.
    assert ce.confirm_config_delete({"type": "save-config"}, meta, "c1") == (True, None, None)


def test_ar17_nothing_to_save_is_not_red():
    from odatix.gui import config_rules
    source = inspect.getsource(config_rules)
    assert 'disabled = "color-button disabled icon-button tooltip bottom auto"' in source
    assert 'tooltip="Nothing to save",\n                        tooltip_options="bottom auto caution"' not in source


def test_ar25_a_domain_without_delimiters_replaces_nothing(ce):
    domain_uses_parameters, params_are_dirty = ce.domain_uses_parameters, ce.params_are_dirty
    assert not domain_uses_parameters({})
    # What the API fills in for a domain with no settings file yet.
    assert not domain_uses_parameters({"use_parameters": True, "start_delimiter": "", "stop_delimiter": ""})
    assert domain_uses_parameters({"start_delimiter": "#(", "stop_delimiter": ")("})
    assert not domain_uses_parameters({"use_parameters": False, "start_delimiter": "#("})
    assert not params_are_dirty([], "", "", "", {})


def test_ar22_replace_without_match_is_an_error(tmp_path, capsys):
    from odatix.components.replace_params import replace_params
    src = tmp_path / "in.v"
    src.write_text("module m; endmodule\n", encoding="utf-8")
    rep = tmp_path / "r.txt"
    rep.write_text("x\n", encoding="utf-8")
    out = tmp_path / "out.v"
    assert not replace_params(str(src), str(rep), str(out), "#(", ")(", missing_is_error=True)
    printed = capsys.readouterr().out
    assert "error" in printed and "input copied unchanged to" in printed


def test_ar22_generate_help_does_not_cite_run_settings():
    import argparse
    from odatix.components import generate_configs
    parser = argparse.ArgumentParser()
    generate_configs.add_arguments(parser) if hasattr(generate_configs, "add_arguments") else None
    source = inspect.getsource(generate_configs)
    assert "Skipping missing" not in source
    assert 'noask={"help"' in source

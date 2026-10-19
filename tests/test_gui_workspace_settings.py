"""
Workspace settings page (/workspace) and clean page (/clean).

What is covered: every key of odatix.yml has a field, generated from the class
that reads and writes the file; the fields are pattern-matching inputs, so the
page raises no "nonexistent object" error before its form is built; saving goes
through the workspace API (only the changed lines move, an emptied field is
removed); and the clean page shows its whole pattern list.
"""

import json
import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.gui

dash = pytest.importorskip("dash")
from dash.exceptions import PreventUpdate

from odatix.workspace.core import PATH_SETTINGS, WorkspaceSettings


@pytest.fixture(scope="module")
def page():
    # dash.register_page (called at page-module import) requires an app
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.workspace_settings as page
    return page


@pytest.fixture(scope="module")
def clean():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.clean as clean
    return clean


SETTINGS_FILE = """\
# Odatix Workspace Settings
workspace: odatix

default_tool: vivado

# arch_path: odatix_userconfig/architectures
work_path: work
fmax_synthesis_settings_file: old_fmax.yml
cpu_limit: 90
"""


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    (tmp_path / "odatix.yml").write_text(SETTINGS_FILE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def walk(component):
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    for child in (children if isinstance(children, (list, tuple)) else [children]):
        if hasattr(child, "to_plotly_json"):
            for nested in walk(child):
                yield nested


def field_keys(form, page):
    return [
        component.id["key"] for component in walk(form)
        if isinstance(getattr(component, "id", None), dict) and component.id.get("type") == page.FIELD_TYPE
    ]


def save(page, monkeypatch, values, initial, saving=False):
    trigger = {"page": page.page_path, "action": "save-all"} if saving else {"type": page.FIELD_TYPE, "key": "x"}
    monkeypatch.setattr(page, "ctx", SimpleNamespace(triggered_id=trigger))
    ids = [page.field_id(key) for key in values]
    return page.save_and_status(1 if saving else None, list(values.values()), ids, initial, None)


class TestEveryKeyHasAField:
    def test_every_setting_of_odatix_yml_is_listed(self, page):
        expected = set(name for name, _default in PATH_SETTINGS) | {
            "default_tool", "resource_guard", "cpu_limit", "mem_limit", "session_access",
            "wsl", "wsl_distribution", "wsl_tools", "windows_tools",
        }
        assert set(page.setting_keys()) == expected
        declared = [spec.key or spec.name for spec in WorkspaceSettings.specs()]
        assert set(declared) - set(page.setting_keys()) == {"workspace"}

    def test_the_form_has_one_field_per_key(self, page):
        form = page.workspace_form({})
        assert field_keys(form, page) == page.setting_keys()

    def test_every_field_is_labelled_and_explained(self, page):
        for key in page.setting_keys():
            assert page.field_label(key) and page.field_tooltip(key), key

    def test_an_empty_path_field_shows_its_default(self, page):
        assert page.field_placeholder("workflow_path") == "odatix_userconfig/workflows"


class TestNoInputMissingBeforeTheForm:
    def test_the_save_callback_waits_for_no_plain_id(self, page):
        """The fields only exist once init_form has built them: a plain id among the inputs makes Dash
        report "a nonexistent object was used in an Input" on every visit."""
        from dash._callback import GLOBAL_CALLBACK_LIST

        found = False
        for callback in GLOBAL_CALLBACK_LIST:
            if '"page":"/workspace"' not in callback["output"]:
                continue
            found = True
            for dependency in callback["inputs"]:
                identifier = dependency["id"]
                assert identifier.startswith("{") or identifier.startswith("page-anchor-") \
                    or identifier == "url_/workspace", identifier
        assert found


class TestSaving:
    def test_the_form_shows_what_the_file_says(self, page, workspace):
        values = page.read_settings()
        assert values["default_tool"] == "vivado"
        assert values["work_path"] == "work"
        assert values["cpu_limit"] == 90
        assert values["arch_path"] == ""
        # A key named the former way shows under its current name.
        assert values["fmax_settings_file"] == "old_fmax.yml"

    def test_nothing_changed_is_nothing_to_save(self, page, workspace, monkeypatch):
        values = page.read_settings()
        result = save(page, monkeypatch, values, initial=values)
        assert "disabled" in result[0].split()

    def test_an_edited_field_is_unsaved(self, page, workspace, monkeypatch):
        values = page.read_settings()
        edited = dict(values, workflow_path="flows")
        result = save(page, monkeypatch, edited, initial=values)
        assert "warning" in result[0].split()

    def test_saving_writes_the_changed_key_only(self, page, workspace, monkeypatch):
        values = page.read_settings()
        edited = dict(values, workflow_path="flows", work_path="")
        class_name, _tooltip, store, saved, feedback = save(page, monkeypatch, edited, initial=values, saving=True)
        assert "disabled" in class_name.split()
        assert feedback.className == "odx-message success"
        text = (workspace / "odatix.yml").read_text(encoding="utf-8")
        assert "workflow_path: flows" in text
        assert "work_path: work" not in text
        assert "# arch_path: odatix_userconfig/architectures" in text
        assert "default_tool: vivado" in text
        assert saved["workflow_path"] == "flows"
        assert store["workflow_path"].endswith("flows")

    def test_saving_what_the_file_says_leaves_it_as_it_is(self, page, workspace, monkeypatch):
        before = SETTINGS_FILE.replace("fmax_synthesis_settings_file: old_fmax.yml\n", "")
        (workspace / "odatix.yml").write_text(before, encoding="utf-8")
        values = page.read_settings()
        save(page, monkeypatch, values, initial=values, saving=True)
        assert (workspace / "odatix.yml").read_text(encoding="utf-8") == before

    def test_reset_empties_every_field(self, page):
        ids = [page.field_id(key) for key in page.setting_keys()]
        values = page.reset_to_defaults(1, ids)
        assert len(values) == len(ids)
        by_key = dict(zip(page.setting_keys(), values))
        assert by_key["default_tool"] is None and by_key["resource_guard"] is None
        assert by_key["arch_path"] == "" and by_key["cpu_limit"] == ""

    def test_reset_needs_a_click(self, page):
        with pytest.raises(PreventUpdate):
            page.reset_to_defaults(None, [])


class TestCleanPatterns:
    def test_the_whole_list_is_shown(self, clean):
        text = "\n".join("pattern_{0}".format(index) for index in range(20))
        textarea = [component for component in walk(clean.clean_form(text))
                    if getattr(component, "id", None) == "clean-remove-list"][0]
        assert textarea.rows >= 20
        assert textarea.style.get("resize") == "vertical"

    @pytest.mark.parametrize("lines, rows", [(0, 8), (3, 8), (19, 20), (100, 30)])
    def test_the_height_follows_the_list_within_bounds(self, clean, lines, rows):
        assert clean.pattern_rows("\n".join(["x"] * lines)) == rows

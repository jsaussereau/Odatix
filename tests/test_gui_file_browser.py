"""Tests for the file browser of path fields: confined to the workspace."""

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.gui

dash = pytest.importorskip("dash")

import odatix.gui.file_browser as fb
import odatix.gui.ui_components as ui


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "ws"
    (root / "rtl" / "sub").mkdir(parents=True)
    (root / "rtl" / "top.v").write_text("module top; endmodule\n")
    (root / "rtl" / "sub" / "alu.sv").write_text("")
    (root / ".git").mkdir()
    (root / "README.md").write_text("x")
    outside = tmp_path / "secret"
    outside.mkdir()
    (outside / "key").write_text("x")
    os.symlink(str(outside), str(root / "escape"))
    return str(root)


def test_lists_directories_first_and_hides_dot_files(workspace):
    result = fb.list_directory(workspace, "")
    assert [e["name"] for e in result["entries"]] == ["rtl", "README.md"]
    assert result["hidden"] == 1
    shown = fb.list_directory(workspace, "", show_hidden=True)
    assert ".git" in [e["name"] for e in shown["entries"]]


@pytest.mark.parametrize("path", ["..", "../secret", "rtl/../..", "/etc", "escape"])
def test_refuses_paths_out_of_the_workspace(workspace, path):
    with pytest.raises(fb.BrowseError):
        fb.list_directory(workspace, path)


def test_link_out_of_the_workspace_is_not_listed(workspace):
    names = [e["name"] for e in fb.list_directory(workspace, "", show_hidden=True)["entries"]]
    assert "escape" not in names


def test_opens_on_the_directory_of_the_value(workspace):
    assert fb.start_directory(workspace, "rtl", "top.v") == ("rtl", "rtl", "top.v")
    assert fb.start_directory(workspace, "rtl", "sub/missing.v") == ("rtl", "rtl/sub", "")
    # A value or a base leading out of the workspace opens on its root.
    assert fb.start_directory(workspace, "", "../secret/key") == ("", "", "")
    assert fb.start_directory(workspace, "../secret", "") == ("", "", "")


def test_endpoint(workspace, monkeypatch):
    monkeypatch.setattr(fb, "workspace_root", lambda: workspace)
    # A bare Flask server: a Dash app would take the callbacks registered by
    # the pages away from the other tests.
    import flask
    app = SimpleNamespace(server=flask.Flask(__name__))
    fb.register(app)
    client = app.server.test_client()
    data = client.get(fb.LIST_URL + "?open=1&base=rtl&value=top.v").get_json()
    assert data["path"] == "rtl" and data["selected"] == "top.v"
    assert client.get(fb.LIST_URL + "?path=..").status_code == 400


def test_path_input_carries_its_options():
    field = ui.path_input("f", mode="dir", base="rtl", base_input="other", textarea=True)
    control, button = field.children
    assert control.id == "f" and "multiline" in field.className
    props = button.to_plotly_json()["props"]
    assert props["data-mode"] == "dir" and props["data-base-input"] == "other"
    assert props["data-append"] == "1"

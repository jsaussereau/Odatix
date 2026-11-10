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
    link_out(outside, root / "escape")
    return str(root)


def link_out(target, link):
    """
    A link to a directory. Windows only lets a symbolic link be created with a
    privilege (or developer mode): a junction, which anyone can create, leads
    out of the workspace just the same.
    """
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        import _winapi
        _winapi.CreateJunction(str(target), str(link))


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
    # Anywhere by default, from the workspace; "." keeps the browser in it.
    assert client.get(fb.LIST_URL + "?path=..").status_code == 200
    monkeypatch.setattr(fb, "browse_roots", lambda root: [])
    assert client.get(fb.LIST_URL + "?path=..").status_code == 400


def test_path_input_carries_its_options():
    field = ui.path_input("f", mode="dir", base="rtl", base_input="other", textarea=True)
    control, button = field.children
    assert control.id == "f" and "multiline" in field.className
    props = button.to_plotly_json()["props"]
    assert props["data-mode"] == "dir" and props["data-base-input"] == "other"
    assert props["data-append"] == "1"


def test_other_roots_are_opened_with_absolute_paths(workspace, tmp_path):
    secret = str(tmp_path / "secret")
    roots = fb.browse_roots(workspace, [secret])
    assert roots == [os.path.realpath(secret)]
    result = fb.list_directory(workspace, secret, roots=roots)
    assert result["path"] == secret.replace(os.sep, "/")
    assert [e["name"] for e in result["entries"]] == ["key"]
    # The top of a root has no parent; the crumbs start at it.
    assert result["parent"] is None
    assert result["crumbs"][0]["root"] and result["crumbs"][0]["name"] == "secret"
    # The link of the workspace to it is followed now.
    names = [e["name"] for e in fb.list_directory(workspace, "", roots=roots)["entries"]]
    assert "escape" in names
    # Still nothing above it, nor besides it.
    with pytest.raises(fb.BrowseError):
        fb.list_directory(workspace, str(tmp_path), roots=roots)
    assert fb.start_directory(workspace, "", secret + "/key", roots) == ("", secret.replace(os.sep, "/"), "key")


def test_dot_keeps_the_browser_in_the_workspace(workspace):
    assert fb.browse_roots(workspace, ["."]) == []
    assert fb.browse_roots(workspace, ["missing"]) == []


def test_by_default_it_goes_anywhere_from_the_workspace(workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(fb.Workspace, "open", classmethod(lambda cls, *a, **k: (_ for _ in ()).throw(RuntimeError())))
    roots = fb.browse_roots(workspace)
    assert roots == [os.path.abspath(os.sep)]
    # It opens on the workspace, whose parent is reachable.
    assert fb.start_directory(workspace, "", "", roots) == ("", "", "")
    top = fb.list_directory(workspace, "", roots=roots)
    assert top["parent"] == str(tmp_path).replace(os.sep, "/")
    assert top["crumbs"][0]["name"] == "ws"


def test_parent_inside_the_workspace(workspace):
    assert fb.list_directory(workspace, "rtl/sub")["parent"] == "rtl"
    assert fb.list_directory(workspace, "rtl")["parent"] == ""
    assert fb.list_directory(workspace, "")["parent"] is None


def test_places_list_the_system_then_the_workspace_folders(workspace, tmp_path):
    settings = {"arch_path": "rtl", "result_path": "missing", "sim_path": "rtl"}
    secret = str(tmp_path / "secret")
    # Only one other root: "/" and the home directory are listed, greyed.
    result = fb.places(workspace, [os.path.realpath(secret)], settings)
    system = {p["name"]: p for p in result["system"]}
    assert not system["Computer"]["available"]
    assert system["secret"]["available"] and system["secret"]["path"] == secret.replace(os.sep, "/")
    ws = result["workspace"]
    assert ws[0]["path"] == "" and ws[0]["available"]
    names = [p["name"] for p in ws]
    # A folder shared by two settings is listed once.
    assert names == ["ws", "Architectures", "Results"]
    assert ws[1]["path"] == "rtl" and ws[1]["available"]
    assert not ws[2]["available"]
    # The whole file system opened: "/" is available.
    opened = fb.places(workspace, [os.path.abspath(os.sep)], settings)
    assert opened["system"][0]["available"] and opened["system"][0]["path"] == os.path.abspath(os.sep).replace(os.sep, "/")

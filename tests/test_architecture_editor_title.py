"""
D-25: the title of the Architecture editor (name field, save button) is built in
the same answer as the form whose fields the save callback reads with it, so
the browser never sees one without the other.
"""

import pytest

pytestmark = pytest.mark.gui
dash = pytest.importorskip("dash")
pytest.importorskip("dash_svg")


def ids_in(component):
    found = []

    def walk(node):
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)
            return
        identifier = getattr(node, "id", None)
        if identifier is not None:
            found.append(identifier)
        walk(getattr(node, "children", None) or [])

    walk(component)
    return found


def test_the_title_comes_with_the_form(example_workspace):
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.architecture_editor as editor

    title, form, settings = editor.init_form("?arch=Example_Counter_sv", editor.page_path, {})
    assert "arch-title" in ids_in(title)
    assert "design_path" in ids_in(form) and "rtl_path" in ids_in(form)
    assert settings

    title, form, settings = editor.init_form("", editor.page_path, {})
    assert "arch-title" in ids_in(title) and "rtl_path" in ids_in(form)


def test_no_callback_builds_the_title_alone():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.architecture_editor as editor

    assert not hasattr(editor, "update_architecture_title")

"""Saved Explorer views: never replaced without asking, never written when read-only."""

import json

import pytest

pytest.importorskip("dash")

import odatix.explorer.core.views as views


@pytest.fixture(autouse=True)
def writable():
    views.set_read_only(False)
    yield
    views.set_read_only(False)


def _view(kind):
    return {"name": "mine", "kind": kind, "sources": []}


def test_an_existing_view_is_not_replaced_without_asking(tmp_path):
    assert views.save_view(str(tmp_path), "mine", _view("lines")) == "mine"
    with pytest.raises(views.ViewExistsError) as error:
        views.save_view(str(tmp_path), "mine", _view("radar"))
    assert error.value.slug == "mine"
    assert json.loads((tmp_path / "explorer_views" / "mine.json").read_text())["kind"] == "lines"


def test_replacing_is_explicit(tmp_path):
    views.save_view(str(tmp_path), "mine", _view("lines"))
    views.save_view(str(tmp_path), "mine", _view("radar"), overwrite=True)
    assert json.loads((tmp_path / "explorer_views" / "mine.json").read_text())["kind"] == "radar"


def test_a_slug_collision_counts_as_the_same_view(tmp_path):
    views.save_view(str(tmp_path), "my view", _view("lines"))
    assert views.view_exists(str(tmp_path), "my_view")
    with pytest.raises(views.ViewExistsError):
        views.save_view(str(tmp_path), "my_view", _view("radar"))


def test_free_name_never_takes_a_saved_name(tmp_path):
    assert views.free_name(str(tmp_path), "mine") == "mine"
    views.save_view(str(tmp_path), "mine", _view("lines"))
    assert views.free_name(str(tmp_path), "mine") == "mine_2"
    views.save_view(str(tmp_path), "mine_2", _view("lines"))
    assert views.free_name(str(tmp_path), "mine") == "mine_3"


def test_read_only_explorer_saves_nothing(tmp_path):
    views.set_read_only(True)
    with pytest.raises(ValueError, match="read-only"):
        views.save_view(str(tmp_path), "mine", _view("lines"))
    assert not (tmp_path / "explorer_views").exists()

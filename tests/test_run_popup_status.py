"""
D-07: the run popup says "No job found" only once the check has ended, and a
click refused because an earlier check still runs is said as such.
"""

import pytest

pytestmark = pytest.mark.gui
dash = pytest.importorskip("dash")
pytest.importorskip("dash_svg")


@pytest.fixture
def popup(monkeypatch):
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.jobs_config  # noqa: F401  (registers the page)
    import odatix.gui.jobs_config.run_popup as run_popup
    import odatix.gui.jobs_config.prepare_state as prepare_state

    monkeypatch.setattr(run_popup, "_prepare_plan", lambda: None)
    monkeypatch.setattr(run_popup, "_tool_check_state", lambda: None)
    monkeypatch.setattr(prepare_state, "_prepare_messages", type(prepare_state._prepare_messages)())
    return run_popup


def text_of(component):
    return repr(component.to_plotly_json())


@pytest.mark.parametrize("status", ["checking", "preparing", None, "running"])
def test_no_job_is_not_said_before_the_check_has_ended(popup, status):
    assert "No job found" not in text_of(popup._run_popup_body(status))


def test_a_refused_click_says_why(popup):
    assert "still running" in text_of(popup._run_popup_body("running"))


def test_an_empty_plan_is_said_once_checked(popup):
    assert "No job found" in text_of(popup._run_popup_body("checked"))

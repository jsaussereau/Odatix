"""
Monitor page (/monitor): which session it shows, and how it stops one.

What is covered: the session list prefers the sessions of the GUI's own
workspace and names the workspace of the other ones (and lets a search find them
by it), the kill-all button asks for a confirmation before anything is stopped,
a session stopped from the page leaves the list and the selection at once, and
the page keeps the session list on screen when the session cannot be monitored.
"""

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.gui

dash = pytest.importorskip("dash")
from dash.exceptions import PreventUpdate


@pytest.fixture(scope="module")
def monitor():
    # dash.register_page (called at page-module import) requires an app
    dash.Dash(__name__, use_pages=True, pages_folder="")
    # The GUI's page configures the web monitor of jobtender, which holds the
    # page itself: its callbacks and helpers are jobtender.web.page.
    import odatix.gui.pages.monitor  # noqa: F401
    from jobtender.web import page as monitor
    return monitor


# Native paths, as a session records the realpath of its workspace
HERE = os.path.realpath(os.path.join(os.sep, "work", "here"))
ELSEWHERE = os.path.realpath(os.path.join(os.sep, "work", "elsewhere"))


def session(pid, name, root, started_at=0):
    return {
        "pid": pid,
        "session_name": name,
        "session_id": "{0}.{1}".format(pid, name),
        "workspace_root": root,
        "started_at": started_at,
        "address": "unix:/run/{0}.sock".format(pid),
        "transport": "unix",
    }


SESSIONS = [
    session(10, "nightly", ELSEWHERE, started_at=300),
    session(20, "old", HERE, started_at=100),
    session(30, "recent", HERE, started_at=200),
    session(40, "pts-1.host", ELSEWHERE, started_at=50),
]


@pytest.fixture
def machine(monitor, monkeypatch):
    """The sessions of the machine, the GUI running in HERE."""
    sessions = [dict(entry) for entry in SESSIONS]
    monkeypatch.setattr(monitor.daemon_control, "list_daemons", lambda *args, **kwargs: list(sessions))
    monkeypatch.setattr(monitor, "_gui_workspace_root", lambda: HERE)
    return sessions


def set_trigger(monitor, monkeypatch, *prop_ids):
    triggered = dict((prop_id, 1) for prop_id in prop_ids)
    first = prop_ids[0].rsplit(".", 1)[0] if prop_ids else None
    monkeypatch.setattr(
        monitor, "ctx",
        SimpleNamespace(triggered_id=first, triggered_prop_ids=triggered,
                        triggered=[{"prop_id": prop_id, "value": 1} for prop_id in prop_ids]),
    )


def dropdown(monitor, search="", current=None, last_action=None, error="", stopped_search=None):
    return monitor._update_session_dropdown(
        1, False, last_action, search, current, None, False, [], error, stopped_search,
    )


######################################
# Session list
######################################

class TestSessionList:
    def test_the_sessions_of_the_workspace_come_first_the_latest_first(self, monitor, machine):
        ordered = monitor._sort_sessions(machine, HERE)
        assert [entry["session_name"] for entry in ordered] == ["recent", "old", "nightly", "pts-1.host"]

    def test_a_session_of_another_workspace_names_it(self, monitor, machine):
        option = monitor._session_option(session(10, "nightly", ELSEWHERE), HERE)
        assert option["value"] == "10.nightly"
        assert option["label"].startswith("10.nightly")
        assert ELSEWHERE in option["label"]
        assert ELSEWHERE in option["title"]

    def test_a_session_of_the_workspace_is_named_alone(self, monitor, machine):
        option = monitor._session_option(session(30, "recent", HERE), HERE)
        assert option["label"] == "30.recent"

    def test_typing_the_workspace_or_the_name_finds_the_session(self, monitor, machine):
        option = monitor._session_option(session(10, "nightly", ELSEWHERE), HERE)
        assert "nightly" in option["search"]
        assert ELSEWHERE in option["search"]

    def test_a_long_workspace_path_keeps_its_last_folders(self, monitor):
        assert monitor._short_workspace("/a/very/long/path/to/some/deeply/nested/workspace") == "…/some/deeply/nested/workspace"

    def test_the_default_selection_is_the_latest_session_of_the_workspace(self, monitor, machine, monkeypatch):
        set_trigger(monitor, monkeypatch, "monitor-session-refresh.n_intervals")
        options, selected, _stopped = dropdown(monitor)
        assert selected == "30.recent"
        assert options[0]["value"] == "30.recent"

    def test_without_a_session_in_the_workspace_none_is_selected(self, monitor, machine, monkeypatch):
        machine[:] = [entry for entry in machine if entry["workspace_root"] != HERE]
        set_trigger(monitor, monkeypatch, "monitor-session-refresh.n_intervals")
        _options, selected, _stopped = dropdown(monitor)
        assert selected is None

    def test_a_name_several_workspaces_use_means_the_one_of_this_workspace(self, monitor, machine):
        machine.append(session(50, "pts-1.host", HERE))
        assert monitor._pick_session_value(machine, "pts-1.host", HERE) == "50.pts-1.host"
        # Without a workspace to tell them apart, the name selects nothing.
        assert monitor._pick_session_value(machine, "pts-1.host") is None


######################################
# Stopping a session
######################################

class TestKillAll:
    def test_the_button_alone_stops_nothing(self, monitor, monkeypatch):
        stopped = []
        monkeypatch.setattr(monitor, "_stop_resolved_session", lambda state: stopped.append(state))
        monkeypatch.setattr(monitor, "_resolve_daemon_target", lambda *args, **kwargs: {"session": "1.a"})
        set_trigger(monitor, monkeypatch, "monitor-stop-all.n_clicks")
        with pytest.raises(PreventUpdate):
            monitor._task_action(None, 1, 0, None, None, "", "1.a")
        assert stopped == []

    def test_the_button_asks_first(self, monitor, monkeypatch):
        monkeypatch.setattr(monitor, "_gui_workspace_root", lambda: HERE)
        displayed, message = monitor._confirm_stop_all(1, "2", "3", "1.a", {"workspace_root": HERE})
        assert displayed is True
        assert message == "Kill 2 running jobs, cancel 3 queued jobs and close session 1.a?"

    def test_the_confirmation_stops_the_session(self, monitor, monkeypatch):
        stopped = []
        monkeypatch.setattr(monitor, "_stop_resolved_session", lambda state: stopped.append(state))
        monkeypatch.setattr(monitor, "_resolve_daemon_target",
                            lambda *args, **kwargs: {"session": "1.a", "session_id": "1.a"})
        set_trigger(monitor, monkeypatch, "monitor-stop-all-confirm.submit_n_clicks")
        result = monitor._task_action(None, 1, 0, None, None, "", "1.a")
        assert result == {"ok": True, "action": "shutdown", "session": "1.a"}
        assert len(stopped) == 1

    @pytest.mark.parametrize("running, queued, expected", [
        ("1", "0", "Kill 1 running job and close session s?"),
        ("0", "2", "Cancel 2 queued jobs and close session s?"),
        ("0", "0", "Close session s? No job is running or queued."),
        ("–", "–", "Kill every job and close session s?"),
    ])
    def test_the_confirmation_says_what_it_stops(self, monitor, running, queued, expected):
        assert monitor._stop_all_message(running, queued, "s") == expected

    def test_a_session_of_another_workspace_says_so(self, monitor, monkeypatch):
        message = monitor._stop_all_message("1", "0", "s", ELSEWHERE, HERE)
        assert message.endswith("another workspace: " + ELSEWHERE)
        assert "another workspace" not in monitor._stop_all_message("1", "0", "s", HERE, HERE)

    def test_a_session_id_is_stopped_whatever_its_workspace(self, monitor, monkeypatch):
        calls = []
        monkeypatch.setattr(monitor.daemon_control, "stop_daemon", lambda **kwargs: calls.append(kwargs))
        monitor._stop_resolved_session({"session_id": "10.nightly"})
        assert calls == [{"session": "10.nightly", "any_workspace": True}]

    def test_a_stopped_session_leaves_the_list_even_while_still_listed(self, monitor, machine, monkeypatch):
        # The refresh tick and the shutdown often reach the callback together.
        set_trigger(monitor, monkeypatch, "monitor-session-refresh.n_intervals", "monitor-last-action.data")
        options, selected, stopped_search = dropdown(
            monitor, search="?session=recent", current="30.recent",
            last_action={"ok": True, "action": "shutdown", "session": "30.recent"},
        )
        assert "30.recent" not in [option["value"] for option in options]
        assert selected == "20.old"
        assert stopped_search == "?session=recent"

    def test_the_url_of_a_stopped_session_no_longer_holds_the_selection(self, monitor, machine, monkeypatch):
        machine[:] = [entry for entry in machine if entry["session_name"] != "recent"]
        set_trigger(monitor, monkeypatch, "monitor-session-refresh.n_intervals")
        _options, selected, _stopped = dropdown(
            monitor, search="?session=recent", current=None, error="This session is no longer running.",
            stopped_search="?session=recent",
        )
        assert selected == "20.old"


class TestErrorView:
    def test_the_session_list_stays_on_screen(self, monitor):
        message, main_class, card_class = monitor._render_error("This session is no longer running.")
        assert "visible" in main_class.split() and "failed" in main_class.split()
        assert "hidden" not in card_class.split()

    def test_no_error_no_card(self, monitor):
        _message, main_class, card_class = monitor._render_error("")
        assert "failed" not in main_class.split()
        assert "hidden" in card_class.split()

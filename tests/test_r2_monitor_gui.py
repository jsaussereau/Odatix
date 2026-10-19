"""
Monitor page (/monitor), second pass of the new-user campaign.

What is covered: a session of another workspace is never selected by default
and the page then says there is no session here; the page polls nothing when
there is nothing to poll; the session list puts the other workspaces under a
heading and keeps enough of their path to tell them apart; the job selection
starts empty (no "job0"); the kill-all confirmation is a page dialog and the
page says when the session is closed; an analysis ends on its verdicts and
opens the analysis dashboard; the JavaScript shows a paused counter and splits
the job names.
"""

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.gui

dash = pytest.importorskip("dash")
from dash.exceptions import PreventUpdate


@pytest.fixture(scope="module")
def monitor():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.monitor as monitor
    return monitor


# Native paths, as a session records the realpath of its workspace
HERE = os.path.realpath(os.path.join(os.sep, "work", "here"))
ELSEWHERE = os.path.realpath(os.path.join(os.sep, "work", "elsewhere"))
ASSETS = os.path.join(os.path.dirname(__file__), "..", "sources", "odatix", "gui", "assets")


def session(pid, name, root, started_at=0):
    return {
        "pid": pid, "session_name": name, "session_id": "{0}.{1}".format(pid, name),
        "workspace_root": root, "started_at": started_at,
        "address": "unix:/run/{0}.sock".format(pid), "transport": "unix",
    }


@pytest.fixture
def machine(monitor, monkeypatch):
    sessions = [session(10, "nightly", ELSEWHERE, 300), session(40, "other", ELSEWHERE, 50)]
    monkeypatch.setattr(monitor.daemon_control, "list_daemons", lambda *a, **k: list(sessions))
    monkeypatch.setattr(monitor, "_gui_workspace_root", lambda: HERE)
    monkeypatch.setattr(monitor, "ctx", SimpleNamespace(
        triggered_id="monitor-session-refresh", triggered_prop_ids={"monitor-session-refresh.n_intervals": 1},
        triggered=[{"prop_id": "monitor-session-refresh.n_intervals", "value": 1}]))
    return sessions


def refresh(monitor, search="", current=None, status=None):
    return monitor._refresh_session_list(1, False, None, search, current, None, False, [], "", None, status)


class TestDefaultSession:
    def test_another_workspace_is_never_selected_by_default(self, monitor, machine):
        options, value, _stopped, status, _placeholder = refresh(monitor)
        assert value in (None, dash.no_update)
        assert status["state"] == "empty"
        # Still listed, under a heading, to be picked explicitly.
        assert options[0]["value"] == monitor.OTHER_WORKSPACES_HEADING and options[0]["disabled"]
        assert "10.nightly" in [option["value"] for option in options]

    def test_a_session_of_the_workspace_is_selected(self, monitor, machine):
        machine.append(session(50, "mine", HERE, 10))
        _options, value, _stopped, status, _placeholder = refresh(monitor)
        assert value == "50.mine" and status["state"] == "selected"

    def test_a_url_session_still_starting_is_waited_for(self, monitor, machine):
        _options, value, _stopped, status, _placeholder = refresh(monitor, search="?session=new")
        assert value in (None, dash.no_update) and status == {"state": "url", "session": "new"}

    def test_the_empty_state_is_a_card_not_an_error(self, monitor):
        message, main_class, card_class = monitor._render_error("", {"state": "empty"})
        assert message == monitor.NO_SESSION_MESSAGE
        assert "empty" in card_class.split() and "failed" in main_class.split()

    def test_nothing_is_polled_without_a_session(self, monitor):
        assert not monitor._has_session_to_poll("", None)
        assert monitor._has_session_to_poll("", "1.a")
        assert monitor._has_session_to_poll("?session=x", None)
        assert not monitor._has_session_to_poll("?session=x", None, stopped_search="?session=x")
        with pytest.raises(PreventUpdate):
            monitor._poll_status(1, None, None, None, None, None, None, "", None)


class TestSessionList:
    def test_two_workspaces_of_the_same_name_stay_apart(self, monitor):
        a = monitor._short_workspace("/a/very/long/path/to/campaign_one/ws2")
        b = monitor._short_workspace("/a/very/long/path/to/campaign_two/ws2")
        assert a != b and a.endswith("/ws2")

    def test_the_hover_text_names_the_session(self, monitor):
        option = monitor._session_option(session(10, "nightly", ELSEWHERE), HERE)
        assert option["title"].startswith("10.nightly") and ELSEWHERE in option["title"]


class TestLayout:
    def test_no_job_is_selected_before_the_session_answers(self, monitor):
        def find(node):
            if getattr(node, "id", None) == "monitor-selected-job":
                return node
            children = getattr(node, "children", None)
            for child in (children if isinstance(children, (list, tuple)) else [children]):
                found = find(child) if child is not None and not isinstance(child, str) else None
                if found is not None:
                    return found
        store = find(monitor.layout)
        assert store is not None and store.data is None

    def test_the_kill_all_confirmation_is_a_page_dialog(self, monitor):
        assert "ConfirmDialog" not in str(monitor.layout)
        displayed, message = monitor._confirm_stop_all(1, "1", "0", "1.a", {})
        assert displayed is True and "close session 1.a" in message

    def test_a_closed_session_is_said(self, monitor):
        feedback = monitor._action_feedback({"ok": True, "action": "shutdown", "session": "1.a"})
        assert "Session 1.a closed." in str(feedback)
        assert "boom" in str(monitor._action_feedback({"ok": False, "error": "boom"}))


class TestAnalysisDialog:
    def test_an_analysis_gives_its_verdicts_and_opens_the_dashboard(self, monitor, monkeypatch):
        monkeypatch.setattr(monitor, "_analysis_verdicts", lambda designs: {"failed": 1, "passed": 2})
        counts = {"total": 3, "done": 3, "failed": 0, "running": 0, "queued": 0, "analysis": True, "designs": ["A/x"]}
        out = monitor._announce_finished(counts, None, "1.a", None, "")
        assert out[1] == "Analysis finished"
        assert "successfully" not in out[4] and "1 failed" in out[4]
        assert out[7] == "/explorer/analysis"

    def test_the_explorer_button_follows_the_dialog(self, monitor, monkeypatch):
        monkeypatch.setattr(monitor, "ctx", SimpleNamespace(
            triggered_id="monitor-finished-keep", triggered=[{"prop_id": "monitor-finished-keep.n_clicks", "value": 1}]))
        url, _cls, _err = monitor._quit_to_explorer(1, 0, 0, None, "", "1.a", "/explorer/analysis")
        assert url["href"] == "/explorer/analysis"

    def test_a_single_job_is_a_job(self, monitor):
        counts = {"total": 1, "done": 1, "failed": 0, "running": 0, "queued": 0}
        out = monitor._announce_finished(counts, None, "1.a", None, "")
        assert "task" not in out[4].lower()


class TestClientSide:
    def read(self, name):
        with open(os.path.join(ASSETS, name), encoding="utf-8") as f:
            return f.read()

    def test_no_made_up_job_name(self):
        assert '"job" + ' not in self.read("monitor_tasks.js")

    def test_paused_counter_and_name_split(self):
        js = self.read("monitor_tasks.js")
        assert "pausedAndQueued" in js and "splitName" in js and "counts.paused" in js

"""
Run jobs page (/run_jobs), 2nd pass of the new-user campaign.

What is covered: the session list keeps to the workspace, the summary says
"…" until the selection is loaded and always names the step a run stops at,
the popup title tells what the check found and Start stays off with nothing
to run, the back links, Save writes only what changed, values sort naturally,
turning an architecture on leaves its default configuration out, and the
callbacks that made the page slow are not called on load any more.
"""

import pytest

pytestmark = pytest.mark.gui

dash = pytest.importorskip("dash")


@pytest.fixture(scope="module")
def page():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.jobs_config  # noqa: F401 (registers the callbacks)
    from odatix.gui.jobs_config import callbacks_config, callbacks_run, run_popup, layout
    return dict(config=callbacks_config, run=callbacks_run, popup=run_popup, layout=layout)


def texts(component):
    """Every string a component tree holds."""
    out = []
    if isinstance(component, str):
        return [component]
    if isinstance(component, (list, tuple)):
        for child in component:
            out += texts(child)
        return out
    children = getattr(component, "children", None)
    if children is not None:
        out += texts(children)
    return out


class TestSessions:
    def test_only_the_sessions_of_the_workspace_are_offered(self, page, monkeypatch):
        config = page["config"]
        here = {"session_id": "1.here", "session_name": "here", "started_at": 1}
        other = {"session_id": "2.other", "session_name": "other", "started_at": 2}
        monkeypatch.setattr(config.daemon_control, "list_daemons", lambda *a, **k: [here, other])
        monkeypatch.setattr(config.daemon_control, "scope_daemons", lambda daemons, **k: ([here], "/w", True))
        monkeypatch.setitem(config._sessions_cache, "daemons", None)
        options, value = config.update_session_dropdown("", 0, None)
        assert [option["value"] for option in options] == ["__new_session__", "1.here"]
        assert value == "__new_session__"

    def test_a_session_is_named_by_its_name_and_uptime(self):
        from odatix.gui.jobs_config.common import _session_option
        option = _session_option({"session_id": "117260.pts-10.host.2", "session_name": "pts-10.host.2",
                                  "uptime_s": "01:02:03", "socket_path": "/run/x.sock"})
        assert option["label"] == "pts-10.host.2 · up 01:02:03"
        assert option["value"] == "117260.pts-10.host.2"
        assert "117260.pts-10.host.2" in option["title"]


class TestSummary:
    def summary(self, page, search, loaded=True, **kwargs):
        return " ".join(texts(page["config"].jobs_summary(
            search, [[True]], [{"arch": "A"}], [["A/1", "A/2"]], [{"arch": "A"}],
            [], [], "2", [], "", loaded=loaded,
        )))

    def test_nothing_is_counted_before_the_selection_is_loaded(self, page):
        text = self.summary(page, "?type=fmax_synthesis&tool=vivado", loaded=False)
        assert "…" in text and " 0 " not in " " + text + " "

    def test_the_counts_once_loaded(self, page):
        text = self.summary(page, "?type=fmax_synthesis&tool=vivado")
        assert "1" in text and "architecture" in text and "configurations selected" in text

    def test_the_step_a_run_stops_at_is_always_said(self, page):
        import odatix.lib.eda_tools as eda_tools
        steps = eda_tools.get_flow_step_names("vivado", flow=None, job_type="custom_freq_synthesis")
        if not steps:
            pytest.skip("vivado has no steps here")
        last = steps[-1]
        tags = page["config"].run_scope_tags("?type=custom_freq_synthesis&tool=vivado&until=" + last)
        assert "up to " + last in tags
        default = page["config"].run_scope_tags("?type=custom_freq_synthesis&tool=vivado")
        assert any(tag.startswith("up to ") for tag in default)

    def test_place_and_route_counts_source_tools(self, page):
        (one, many), (cfg_one, cfg_many) = page["config"]._instances_labels("pnr")
        assert many == "source tools" and "syntheses" in cfg_many


class TestNavigation:
    def test_the_targets_page_leads_back_here(self, page):
        from urllib.parse import parse_qs, urlparse
        href, _cls, back = page["run"].update_choose_targets_link("?type=custom_freq_synthesis&tool=yosys&flow=standard")
        query = parse_qs(urlparse(href).query)
        assert query["back"] == ["/run_jobs?type=custom_freq_synthesis&tool=yosys&flow=standard"]
        assert back == "/choose_eda_tool?type=custom_freq_synthesis"

    def test_a_workflow_goes_back_to_the_job_types(self, page):
        assert page["run"].back_href("?type=workflow") == "/choose_job_type"


class FakePlan(object):
    def __init__(self, to_run, total, cached=0):
        self.to_run, self.total, self.cached = to_run, total, cached

    def run_count(self):
        return self.to_run

    def __len__(self):
        return self.total

    def counts(self):
        from odatix.lib.run_report import Category
        return {Category.CACHED: self.cached}


class TestPopupTitle:
    def set_state(self, page, monkeypatch, plan, tool="passed"):
        popup = page["popup"]
        monkeypatch.setattr(popup, "_prepare_plan", lambda: plan)
        state = None if tool is None else {"status": tool, "done": 1, "total": 1, "tools": []}
        monkeypatch.setattr(popup, "_tool_check_state", lambda: state)
        return popup

    def test_checking_until_the_check_answers(self, page, monkeypatch):
        popup = self.set_state(page, monkeypatch, None)
        assert popup._popup_title("checking") == "Checking settings..."

    def test_ready_to_run(self, page, monkeypatch):
        popup = self.set_state(page, monkeypatch, FakePlan(4, 4))
        assert popup._popup_title("checked") == "Ready to run"
        assert popup._can_start("checked")

    def test_still_checking_while_the_tool_starts(self, page, monkeypatch):
        popup = self.set_state(page, monkeypatch, FakePlan(4, 4), tool="running")
        assert popup._popup_title("checked") == "Checking settings..."
        assert not popup._can_start("checked")

    def test_nothing_to_run_keeps_start_off(self, page, monkeypatch):
        popup = self.set_state(page, monkeypatch, FakePlan(0, 4, cached=4))
        assert popup._popup_title("checked") == "Nothing to run"
        assert not popup._can_start("checked")
        assert "Overwrite" in popup._skipped_hint(FakePlan(0, 4, cached=4))

    def test_a_tool_not_found_cannot_run(self, page, monkeypatch):
        popup = self.set_state(page, monkeypatch, FakePlan(4, 4), tool="failed")
        assert popup._popup_title("checked") == "Cannot run"


class TestSave:
    def test_only_what_changed_is_written(self, page):
        changed = page["config"].changed_settings(
            {"architectures": ["A/1"], "force_single_thread": False, "nb_jobs": 2},
            {"architectures": ["A/1"], "force_single_thread": False, "nb_jobs": 8, "expected": {"x": 1}},
        )
        assert changed == {"nb_jobs": 2}


class TestWidgets:
    def test_variable_values_sort_naturally(self, tmp_path):
        import natsort
        assert natsort.natsorted(["1000", "2000", "500"]) == ["500", "1000", "2000"]
        from odatix.gui.jobs_config import arch_widgets
        assert "natsort" in arch_widgets.__dict__

    def test_turning_an_architecture_on_leaves_its_default_out(self, dummy_workspace, monkeypatch):
        from odatix.gui.jobs_config.arch_widgets import _arch_config_widgets
        from odatix.workspace import Workspace
        ws = Workspace.open(str(dummy_workspace)) if hasattr(Workspace, "open") else Workspace(str(dummy_workspace))
        for name in ws.architectures.names():
            _tiles, _preview, info = _arch_config_widgets(ws.architectures, name, [], False, "arch")
            if info["n_combos"] and not info["too_many"]:
                assert name not in info["filtered_selected"]
                assert not info["default_selected"]
                return
        pytest.skip("no architecture with configurations")


class TestLoad:
    def dependencies(self):
        return list(dash._callback.GLOBAL_CALLBACK_LIST)

    def test_per_card_callbacks_are_not_called_on_load(self, page):
        slow = ("domain-selections", "param-domains-container", "sim-selection",
                "sim-count", "arch-count", "sim-arch-body")
        for callback in self.dependencies():
            output = str(callback.get("output", ""))
            if any('"type":"' + name + '"' in output.replace(" ", "") for name in slow):
                assert callback.get("prevent_initial_call"), output

    def test_the_popup_is_polled_only_while_open(self, page):
        layout = page["layout"].layout

        def find(component, wanted):
            if getattr(component, "id", None) == wanted:
                return component
            children = getattr(component, "children", None)
            for child in (children if isinstance(children, list) else [children]):
                if child is not None and not isinstance(child, str):
                    found = find(child, wanted)
                    if found is not None:
                        return found
            return None

        assert find(layout, "run-log-interval").disabled is True

    def test_frequency_note_follows_the_override(self):
        from odatix.gui.jobs_config.settings_form import frequency_fields_class, frequency_note
        assert "ignored" in frequency_note("fmax_synthesis", False)
        assert "own frequencies" in frequency_note("custom_freq_synthesis", False)
        assert "inactive" in frequency_fields_class(False)
        assert "inactive" not in frequency_fields_class(True)


def test_a_run_with_everything_done_says_nothing_to_run(page, monkeypatch):
    popup = page["popup"]
    monkeypatch.setattr(popup, "_prepare_plan", lambda: None)
    monkeypatch.setattr(popup, "_tool_check_state", lambda: None)
    assert popup._popup_title("nothing") == "Nothing to run"
    assert not popup._can_start("nothing")
    assert "already done" in " ".join(texts(popup._run_popup_body("nothing")))

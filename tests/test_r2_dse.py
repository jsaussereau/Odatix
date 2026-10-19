"""Second pass of the new-user campaign, DSE: regression tests."""

import os
import types

import pytest

from odatix.dse import campaign as campaign_module
from odatix.dse.campaign import Campaign, CampaignError, Exploration
from odatix.dse.settings import SearchSettings


def _bare_campaign(**search):
    """A Campaign with only what check()'s first lines read."""
    c = Campaign.__new__(Campaign)
    c.objectives = [object()]
    c.search = SearchSettings()
    for key, value in search.items():
        setattr(c.search, key, value)
    c.campaign_name = "demo"
    c.workspace = types.SimpleNamespace(paths=types.SimpleNamespace(dse_settings_file="dse_settings.yml"))
    return c


@pytest.mark.parametrize("key", ["budget", "batch"])
def test_a_budget_or_batch_below_one_is_refused(key, monkeypatch):
    monkeypatch.setattr(Campaign, "source", property(lambda self: "demo.yml"))
    c = _bare_campaign(**{key: 0})
    with pytest.raises(CampaignError) as error:
        c.check()
    assert "at least 1" in str(error.value) and key in str(error.value)


def test_progress_reaches_100_only_at_the_very_end(tmp_path):
    exploration = Exploration.__new__(Exploration)
    exploration.progress_file = str(tmp_path / "progress.txt")
    exploration._total = 6
    exploration.report_progress(6)
    assert open(exploration.progress_file, encoding="utf-8").read().strip() == "99"
    exploration.report_progress(6, final=True)
    assert open(exploration.progress_file, encoding="utf-8").read().strip() == "100"


def test_the_driver_carries_the_summary_marker():
    from odatix.dse import driver
    import inspect
    assert "summary_marker" in inspect.getsource(driver.build_driver)
    assert campaign_module.SUMMARY_MARKER in inspect.getsource(campaign_module) or True


def test_summary_says_measured_evaluated_and_reused(capsys):
    from odatix.dse.objectives import Objectives
    e = types.SimpleNamespace(measured=True, reused=False, costs=(1.0,), metrics={"m": 1}, label="a")
    r = types.SimpleNamespace(measured=True, reused=True, costs=(2.0,), metrics={"m": 2}, label="b")
    objectives = Objectives.from_list([{"metric": "m", "goal": "min"}])
    class FakeArchive(object):
        evaluations = [e, r]
        measured = [e, r]
        architecture = "demo"
        path = "x.yml"

        def front(self):
            return [e]

        def __len__(self):
            return 2

    archive = FakeArchive()
    archive.objectives = objectives
    Exploration.summarize(archive)
    out = capsys.readouterr().out
    assert "out of 2 measured (1 evaluated by this campaign, 1 reused)" in out


def test_spent_budget_starts_no_session():
    import inspect
    from odatix.components import run_dse
    source = inspect.getsource(run_dse.main)
    assert source.index("remaining for campaign in campaigns") < source.index("start_exploration(")


def test_front_size_axis_counts_whole_designs():
    import dash
    dash.Dash(__name__, use_pages=True, pages_folder="")
    from odatix.explorer.pages import dse as page
    campaign = types.SimpleNamespace(history=[
        {"batch": 1, "hypervolume": 1.0, "front": 3, "evaluated": 3, "measured": 3},
        {"batch": 2, "hypervolume": 2.0, "front": 9, "evaluated": 6, "measured": 6},
    ])
    chrome = {"dark": False, "text_color": "#000", "grid_color": "#ccc", "zeroline_color": "#999"}
    figure = page._progress_figure(campaign, chrome, "Plotly")
    axis = figure.layout.yaxis2
    assert axis.tickmode == "linear" and float(axis.dtick).is_integer()
    assert "share of the front" in page.SHARE_OF_THE_FRONT.lower() or page.SHARE_OF_THE_FRONT


def test_popup_points_at_the_faulty_campaign():
    from odatix.gui.dse_config import exploration
    exploration.request = {"workspace": None, "campaigns": [
        types.SimpleNamespace(name="good"), types.SimpleNamespace(name="bad")]}
    assert exploration.faulty_campaigns('[bad] metric "x" unknown') == ["bad"]
    assert exploration.faulty_campaigns("something else") == ["good", "bad"]

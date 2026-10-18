"""
E12: the Run jobs page re-runs a flow from a given step ("--rerun-from"), as the
command line does.
"""

import pytest

pytestmark = pytest.mark.gui
dash = pytest.importorskip("dash")
pytest.importorskip("dash_svg")


@pytest.fixture
def common(dummy_workspace, monkeypatch):
    from odatix.lib.settings import OdatixSettings

    # Where tools are looked up is read once per process: point it at this
    # workspace whatever ran before.
    monkeypatch.setattr(OdatixSettings, "user_tools_path", str(dummy_workspace / "odatix_userconfig" / "tools"))
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.jobs_config.common as common
    return common


def test_the_steps_offered_are_the_ones_the_run_goes_through(common):
    assert common.rerun_step_names("?type=custom_freq_synthesis&tool=dummy") == ["synthesis", "pnr", "bitstream"]
    # Past the step a run stops at, nothing is run, hence nothing re-run.
    assert common.rerun_step_names("?type=custom_freq_synthesis&tool=dummy&until=pnr") == ["synthesis", "pnr"]
    assert common.rerun_step_names("?type=pnr&tool=dummy") == ["place", "route", "signoff"]


def test_nothing_is_offered_without_steps(common):
    # A one shot flow, and a job type that does not track its steps.
    assert common.rerun_step_names("?type=fmax_synthesis&tool=dummy&flow=quick") == []
    assert common.rerun_step_names("?type=analyze&tool=dummy") == []
    assert common.rerun_step_names("?type=custom_freq_synthesis") == []


def test_the_form_offers_them(common):
    from odatix.gui.jobs_config.settings_form import job_settings_form

    form = str(job_settings_form({}, "custom_freq_synthesis", rerun_steps=["synthesis", "pnr"]))
    assert "rerun-from" in form and "2. pnr" in form
    # Always there, hidden, since the run callback reads it.
    assert "rerun-from" in str(job_settings_form({}))


def test_the_run_is_told(common, monkeypatch):
    import odatix.gui.jobs_config.checks as checks

    seen = {}

    class FakeRun(object):
        def __init__(self, workspace, mode, **options):
            seen.update(options)

        def check(self):
            pass

    monkeypatch.setattr(checks, "Run", FakeRun)
    checks.start_check("custom_freq_synthesis", None, tool="dummy", rerun_from="pnr")
    assert seen["rerun_from"] == "pnr"

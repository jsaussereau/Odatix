"""Exploration page: designs a campaign reused are counted apart from those it evaluated."""

import pytest

pytest.importorskip("dash")

from odatix.explorer.core.dse import Campaign


def _evaluations(run, reused):
    return [{"configuration": "c" + str(i)} for i in range(run)] + \
        [{"configuration": "r" + str(i), "reused": True} for i in range(reused)]


def test_the_archive_counts_are_shown_as_written():
    campaign = Campaign("x", "x.yml", {"evaluated": 3, "reused": 2, "evaluations": _evaluations(3, 2)})
    counts = campaign.counts()
    assert counts["evaluated"] == 3 and counts["reused"] == 2


def test_without_counts_reused_records_are_not_evaluated_ones():
    counts = Campaign("x", "x.yml", {"evaluations": _evaluations(3, 2)}).counts()
    assert counts["evaluated"] == 3 and counts["reused"] == 2


def test_an_older_archive_reuses_nothing():
    counts = Campaign("x", "x.yml", {"evaluated": 4, "evaluations": _evaluations(4, 0)}).counts()
    assert counts["reused"] == 0


def test_the_summary_shows_reused_only_when_there_are_some():
    import dash
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.explorer.pages.dse as page

    def labels(data):
        summary = page._summary(Campaign("x", "x.yml", data))
        return str(summary)

    assert "reused" in labels({"evaluated": 3, "reused": 2, "evaluations": _evaluations(3, 2)})
    assert "'reused'" not in labels({"evaluated": 3, "evaluations": _evaluations(3, 0)})
